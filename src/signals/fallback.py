"""R4 收手版：A 股慢阀 + 海外底仓。

慢阀与 operations/reviews/diag/d2.py 同一套月末规则：影子净值始终按 A 股腿满仓计算；
在场时月末距历史高点的回撤超过 out 才出场；出场后月末距出场以来最低月末的反弹超过 back 才回场，
回场当时把高点重置为该净值。比较都是严格不等号。

replicate 只用到设计期终点。晚于该日直接拒绝，不算收益。设计期不读基金净值和溢价。
target 只给某一天的目标持仓：A 股按月，海外按带宽，QDII 溢价只决定买卖哪一只和要不要把应买部分留在货币 ETF。
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "r4_fallback.toml"
TRADING_DAYS = 252
UNAVAILABLE = frozenset({"liquidated", "suspended", "halted"})
KNOWN_STATUS = UNAVAILABLE | {"normal"}
HOLDINGS_FORBIDDEN = {"cagr", "max_drawdown", "vol", "return", "returns", "rank", "sharpe", "drawdown"}

# d2 设计期两行（百分数已换成小数）。误差按 ±0.1 个百分点。
D2_A_CAGR = 0.271
D2_A_DD = -0.426
D2_A_SWITCHES = 6
D2_BLEND_CAGR = 0.227
D2_BLEND_DD = -0.295
D2_TOL = 0.001


class FallbackError(RuntimeError):
    pass


@dataclass(frozen=True)
class Alternate:
    code: str
    list_date: pd.Timestamp


@dataclass(frozen=True)
class AShareBook:
    container: str
    primary: str
    alternates: tuple[Alternate, ...]


@dataclass(frozen=True)
class OverseasPool:
    container: str
    codes: tuple[str, ...]


@dataclass(frozen=True)
class NavRow:
    code: str
    date: pd.Timestamp
    unit_nav: float
    fetched_at: str = ""
    source: str = ""


@dataclass(frozen=True)
class FallbackConfig:
    design_end: pd.Timestamp
    a_share: tuple[str, ...]
    a_weight: float
    overseas: tuple[str, ...]
    o_weight: float
    out: float
    back: float
    judge: str
    haven_code: str
    cash_annual: float
    rebalance: str
    cost_one_way: float
    universe: Path
    path: Path
    band: float = 0.075
    premium_cap: float = 0.10
    nav_lag: int = 2
    lot_size: int = 100
    funds: tuple[AShareBook, ...] = ()
    pools: tuple[OverseasPool, ...] = ()
    excluded: tuple[str, ...] = ()

    @property
    def cash_monthly(self) -> float:
        return self.cash_annual / 12

    @property
    def cash_daily(self) -> float:
        return self.cash_annual / TRADING_DAYS


def _universe_path(config_path: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (config_path.parent.parent / path).resolve()


def _load_books(rows: list[dict]) -> tuple[AShareBook, ...]:
    books = []
    for row in rows:
        alternates = tuple(
            Alternate(str(item["code"]).strip(), pd.Timestamp(item["list_date"]))
            for item in (row.get("alternates") or []))
        books.append(AShareBook(str(row["container"]).strip(), str(row["primary"]).strip(), alternates))
    return tuple(books)


def _load_pools(rows: list[dict]) -> tuple[OverseasPool, ...]:
    pools = []
    for row in rows:
        codes = tuple(str(code).strip() for code in row["codes"])
        pools.append(OverseasPool(str(row["container"]).strip(), codes))
    return tuple(pools)


def load_config(path: Path | None = None) -> FallbackConfig:
    path = Path(path) if path else DEFAULT_CONFIG
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    if "pending" in raw or any("pending" in section for section in raw.values() if isinstance(section, dict)):
        raise FallbackError("正式配置不再保留 pending")
    a = raw["a_share"]
    o = raw["overseas"]
    v = raw["valve"]
    ex = raw["execution"]
    cfg = FallbackConfig(
        design_end=pd.Timestamp(raw["design_end"]),
        a_share=tuple(a["containers"]),
        a_weight=float(a["weight"]),
        overseas=tuple(o["containers"]),
        o_weight=float(o["weight"]),
        out=float(v["out"]),
        back=float(v["back"]),
        judge=str(v["judge"]),
        haven_code=str(v["haven_code"]),
        cash_annual=float(v["cash_annual"]),
        rebalance=str(ex["rebalance"]),
        cost_one_way=float(ex["cost_one_way"]),
        universe=_universe_path(path, str(ex["universe"])),
        path=path,
        band=float(ex["band"]),
        premium_cap=float(ex["premium_cap"]),
        nav_lag=int(ex["nav_lag_trading_days"]),
        lot_size=int(ex["lot_size"]),
        funds=_load_books(list(a["book"])),
        pools=_load_pools(list(o["pool"])),
        excluded=tuple(str(code).strip() for code in o.get("excluded", [])),
    )
    _validate(cfg)
    return cfg


def _validate(cfg: FallbackConfig) -> None:
    if cfg.judge != "month_end":
        raise FallbackError(f"慢阀只在月末判定，配置是 {cfg.judge}")
    if cfg.rebalance != "monthly":
        raise FallbackError(f"A 股再平衡只做月度，配置是 {cfg.rebalance}")
    if not cfg.a_share or not cfg.overseas:
        raise FallbackError("A 股腿和海外腿都不能是空的")
    if abs(cfg.a_weight + cfg.o_weight - 1) > 1e-9:
        raise FallbackError("A 股权重与海外权重之和必须是 1")
    if cfg.out <= 0 or cfg.back <= 0:
        raise FallbackError("out 和 back 必须是正数")
    if cfg.band <= 0 or cfg.premium_cap <= 0:
        raise FallbackError("band 和 premium_cap 必须是正数")
    if cfg.nav_lag < 1:
        raise FallbackError("净值公布滞后至少 1 个交易日")
    if cfg.lot_size < 1:
        raise FallbackError("lot_size 必须是正整数")
    if tuple(book.container for book in cfg.funds) != cfg.a_share:
        raise FallbackError("A 股执行基金的容器顺序必须和 containers 一致")
    if tuple(pool.container for pool in cfg.pools) != cfg.overseas:
        raise FallbackError("海外池的顺序必须和 containers 一致")
    primaries = [book.primary for book in cfg.funds]
    if len(primaries) != len(set(primaries)):
        raise FallbackError("A 股主基金代码重复")
    pool_codes = [code for pool in cfg.pools for code in pool.codes]
    if len(pool_codes) != len(set(pool_codes)):
        raise FallbackError("海外池代码重复")
    banned = set(cfg.excluded)
    if banned & set(pool_codes):
        raise FallbackError(f"被排除的代码进了海外池：{sorted(banned & set(pool_codes))}")
    a_codes = set(primaries)
    for book in cfg.funds:
        seen = set()
        for alt in book.alternates:
            if alt.code == book.primary or alt.code in seen:
                raise FallbackError(f"{book.container} 的备选 {alt.code} 重复或与主基金相同")
            seen.add(alt.code)
            a_codes.add(alt.code)
    if cfg.haven_code in a_codes or cfg.haven_code in pool_codes:
        raise FallbackError("货币 ETF 不能同时又是 A 股执行基金或海外池成员")
    if a_codes & set(pool_codes):
        raise FallbackError("A 股执行基金和海外池重叠")


def execution_map(path: Path) -> dict[str, str]:
    """容器名 → execution_fund_code。只读 universe.csv。"""
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    out = {}
    for row in rows:
        name = row["theme"]
        code = (row.get("execution_fund_code") or "").strip()
        if name and code and name not in out:
            out[name] = code
    return out


def code_name(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    out = {}
    for row in rows:
        code = (row.get("execution_fund_code") or "").strip()
        if code and code not in out:
            out[code] = row["theme"]
    return out


def slow_valve(shadow: pd.Series, out: float, back: float, cash_monthly: float):
    """d2.py 的 valve。返回 (持有收益, 切换次数, 当月使用的状态)。

    当月收益先按进入该月时的状态记（在场用影子收益，出场用现金），再用该月月末的影子净值决定下月。
    状态 1 在场，0 出场。
    """
    nav = (1 + shadow).cumprod()
    state = 1
    hi = 1.0
    lo = None
    held, during = [], []
    switches = 0
    for i in range(len(shadow)):
        during.append(state)
        held.append(float(shadow.iloc[i]) if state else cash_monthly)
        level = float(nav.iloc[i])
        if state:
            hi = max(hi, level)
            if level / hi - 1 < -out:
                state = 0
                lo = level
                switches += 1
        else:
            lo = min(lo, level)
            if level / lo - 1 > back:
                state = 1
                hi = level
                switches += 1
    index = shadow.index
    return (
        pd.Series(held, index=index, dtype=float),
        switches,
        pd.Series(during, index=index, dtype=int),
    )


def valve_path(shadow: pd.Series, out: float, back: float) -> dict:
    """走到影子序列的最后一根，给出阀状态和距高点回撤。不返回收益序列。"""
    nav = (1 + shadow).cumprod()
    state = 1
    hi = 1.0
    lo = None
    level = 1.0
    for i in range(len(shadow)):
        level = float(nav.iloc[i])
        if state:
            hi = max(hi, level)
            if level / hi - 1 < -out:
                state = 0
                lo = level
        else:
            lo = min(lo, level)
            if level / lo - 1 > back:
                state = 1
                hi = level
    return {"in_market": bool(state), "level": level, "high": hi, "drawdown": level / hi - 1,
            "as_of": shadow.index[-1]}


def period_stats(returns: pd.Series, periods_per_year: float) -> dict:
    nav = (1 + returns).cumprod()
    years = len(returns) / periods_per_year
    cagr = float(nav.iloc[-1] ** (1 / years) - 1)
    drawdown = float((nav / nav.cummax() - 1).min())
    vol = float(returns.std() * periods_per_year ** 0.5)
    return {"cagr": cagr, "max_drawdown": drawdown, "vol": vol, "n": int(len(returns))}


def _read_panel(path: Path, end: pd.Timestamp) -> pd.DataFrame:
    uri = f"{Path(path).resolve().as_uri()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        frame = pd.read_sql_query(
            "SELECT date, container, close, data_hole FROM panel WHERE date <= ?",
            con, params=(end.strftime("%Y-%m-%d"),))
    finally:
        con.close()
    if frame.empty:
        raise FallbackError(f"{path} 在 {end.date()} 之前没有面板行")
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.loc[frame["data_hole"] == 0].copy()


def _month_end_returns(prices: pd.DataFrame) -> pd.DataFrame:
    # pandas 3 的 pct_change 不向前填充。与 d2.py 同一调用。
    return prices.resample("ME").last().pct_change()


def monthly_legs(panel: pd.DataFrame, cfg: FallbackConfig) -> tuple[pd.Series, pd.Series]:
    need = list(cfg.a_share) + list(cfg.overseas)
    missing = [name for name in need if name not in set(panel["container"])]
    if missing:
        raise FallbackError(f"面板缺容器：{missing}")
    wide = panel.pivot(index="date", columns="container", values="close").sort_index()
    returns = _month_end_returns(wide[need])
    a_ret = returns[list(cfg.a_share)].mean(axis=1, skipna=True).iloc[1:]
    o_ret = returns[list(cfg.overseas)].mean(axis=1).reindex(a_ret.index).fillna(0.0)
    if a_ret.empty:
        raise FallbackError("设计期不足两个月末，无法计算月收益")
    return a_ret, o_ret


def d2_deltas(monthly: dict) -> dict:
    """与 d2 印刷值的差，单位是百分点。"""
    a = monthly["a_valve"]
    b = monthly["blend"]
    return {
        "a_cagr_pp": (a["cagr"] - D2_A_CAGR) * 100,
        "a_drawdown_pp": (a["max_drawdown"] - D2_A_DD) * 100,
        "a_switches": a["switches"] - D2_A_SWITCHES,
        "blend_cagr_pp": (b["cagr"] - D2_BLEND_CAGR) * 100,
        "blend_drawdown_pp": (b["max_drawdown"] - D2_BLEND_DD) * 100,
    }


def within_d2(monthly: dict) -> bool:
    delta = d2_deltas(monthly)
    rates = ("a_cagr_pp", "a_drawdown_pp", "blend_cagr_pp", "blend_drawdown_pp")
    return abs(delta["a_switches"]) == 0 and all(abs(delta[key]) <= D2_TOL * 100 for key in rates)


def _available(closes: pd.Series, names: tuple[str, ...]) -> list[str]:
    got = []
    for name in names:
        value = closes.get(name)
        if value is None or pd.isna(value):
            continue
        got.append(name)
    return got


def _target_weights(state: int, a_names: list[str], o_names: list[str], cfg: FallbackConfig) -> dict[str, float]:
    weights: dict[str, float] = {}
    if state and a_names:
        share = cfg.a_weight / len(a_names)
        for name in a_names:
            weights[name] = share
    else:
        weights[cfg.haven_code] = cfg.a_weight
    if o_names:
        share = cfg.o_weight / len(o_names)
        for name in o_names:
            weights[name] = share
    return weights


def _portfolio_return(weights: dict[str, float], day_returns: pd.Series) -> float:
    total = 0.0
    for name, weight in weights.items():
        value = day_returns.get(name, 0.0)
        if pd.isna(value):
            value = 0.0
        total += weight * float(value)
    return total


def _drift(weights: dict[str, float], day_returns: pd.Series, port: float) -> dict[str, float]:
    scale = 1 + port
    if scale == 0:
        return dict(weights)
    out = {}
    for name, weight in weights.items():
        value = day_returns.get(name, 0.0)
        if pd.isna(value):
            value = 0.0
        out[name] = weight * (1 + float(value)) / scale
    return out


def _turnover(before: dict[str, float], after: dict[str, float]) -> float:
    keys = set(before) | set(after)
    return sum(abs(after.get(key, 0.0) - before.get(key, 0.0)) for key in keys)


def daily_book(closes: pd.DataFrame, state_during: pd.Series, cfg: FallbackConfig,
               haven_returns: pd.Series | None = None) -> pd.Series:
    """日频持有：月末信号在下一交易日收盘才成交，成交金额乘单边成本。

    state_during 的索引是月末，值是该月 d2 持有状态。该月第一个交易日的收盘收益仍用上月状态，
    收盘再换成当月状态。
    """
    wide = closes.sort_index()
    day_returns = wide.pct_change()
    if haven_returns is None:
        haven_returns = pd.Series(cfg.cash_daily, index=wide.index)
    else:
        haven_returns = haven_returns.reindex(wide.index).fillna(cfg.cash_daily)
    day_returns = day_returns.copy()
    day_returns[cfg.haven_code] = haven_returns
    by_month = {ts.to_period("M"): int(value) for ts, value in state_during.items()}
    groups = list(wide.groupby(wide.index.to_period("M")))
    if len(groups) < 2:
        raise FallbackError("日频至少需要两个月")
    # 第一个月末只作基点，收益从下一个月开始，与月频丢掉第一根 pct_change 相同。
    start_period = groups[1][0]
    active = wide.loc[wide.index.to_period("M") >= start_period]
    day_returns = day_returns.reindex(active.index)
    rebalance_days = set()
    for period, block in active.groupby(active.index.to_period("M")):
        if period == start_period:
            continue
        rebalance_days.add(block.index[0])
    signal_closes = wide.groupby(wide.index.to_period("M")).tail(1)
    signal_on = {ts.to_period("M"): signal_closes.loc[ts] for ts in signal_closes.index}

    def state_after_trade(day: pd.Timestamp) -> int:
        return by_month.get(day.to_period("M"), 1)

    base_period = groups[0][0]
    base_close = signal_on[base_period]
    weights = _target_weights(by_month.get(start_period, 1),
                              _available(base_close, cfg.a_share),
                              _available(base_close, cfg.overseas), cfg)
    held = []
    index = []
    for day in active.index:
        row = day_returns.loc[day]
        port = _portfolio_return(weights, row)
        if day in rebalance_days:
            drifted = _drift(weights, row, port)
            period = day.to_period("M")
            prev_signal = signal_on.get(period - 1)
            if prev_signal is None:
                prev_signal = base_close
            target = _target_weights(state_after_trade(day),
                                     _available(prev_signal, cfg.a_share),
                                     _available(prev_signal, cfg.overseas), cfg)
            port -= cfg.cost_one_way * _turnover(drifted, target)
            weights = target
        else:
            weights = _drift(weights, row, port)
        held.append(port)
        index.append(day)
    if not held:
        raise FallbackError("日频没有可计算的收益日")
    return pd.Series(held, index=pd.DatetimeIndex(index), dtype=float)


def _haven_returns(closes_index: pd.DatetimeIndex, haven_closes: pd.Series | None, cash_daily: float) -> pd.Series:
    if haven_closes is None or haven_closes.empty:
        return pd.Series(cash_daily, index=closes_index)
    returns = haven_closes.sort_index().pct_change()
    return returns.reindex(closes_index).fillna(cash_daily)


def load_haven_closes(db: Path, code: str, end: pd.Timestamp) -> pd.Series | None:
    if not db.exists():
        return None
    uri = f"{db.resolve().as_uri()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        rows = con.execute(
            "SELECT date, close FROM bars WHERE code = ? AND adj = 'raw' AND date <= ? AND close > 0 ORDER BY date",
            (code, end.strftime("%Y-%m-%d"))).fetchall()
    finally:
        con.close()
    if not rows:
        return None
    return pd.Series({pd.Timestamp(day): close for day, close in rows}).sort_index()


def replicate(panel: Path, end: str | pd.Timestamp, cfg: FallbackConfig,
              haven_db: Path | None = None) -> dict:
    """月频复现 d2，并给出扣成本的日频版。end 晚于设计期终点则拒绝，不读收益。"""
    end_ts = pd.Timestamp(end)
    if end_ts > cfg.design_end:
        raise FallbackError(
            f"replicate 拒绝结束日 {end_ts.date()}：晚于 {cfg.design_end.date()}。v2 样本外未用，不计算这段收益。")
    prices = _read_panel(panel, end_ts)
    if prices.empty or prices["date"].max() > cfg.design_end:
        raise FallbackError("读到的行情越过了设计期终点")
    a_ret, o_ret = monthly_legs(prices, cfg)
    held, switches, state = slow_valve(a_ret, cfg.out, cfg.back, cfg.cash_monthly)
    blend = cfg.a_weight * held + cfg.o_weight * o_ret
    wide = prices.pivot(index="date", columns="container", values="close").sort_index()
    haven_closes = load_haven_closes(haven_db, cfg.haven_code, end_ts) if haven_db else None
    daily = daily_book(wide, state, cfg, _haven_returns(wide.index, haven_closes, cfg.cash_daily))
    monthly = {
        "a_valve": {**period_stats(held, 12), "switches": switches},
        "blend": {**period_stats(blend, 12), "switches": switches},
        "first": str(a_ret.index[0].date()),
        "last": str(a_ret.index[-1].date()),
    }
    return {
        "end": str(end_ts.date()),
        "monthly": monthly,
        "d2_delta_pp": d2_deltas(monthly),
        "matches_d2": within_d2(monthly),
        "daily": {**period_stats(daily, TRADING_DAYS), "switches": switches,
                  "first": str(daily.index[0].date()), "last": str(daily.index[-1].date()),
                  "cost_one_way": cfg.cost_one_way,
                  "note": "月末收盘出信号，下一交易日收盘成交；成交金额乘单边成本。511880 有收盘的日子用它，否则现金年化按 252 个交易日分摊。"},
    }


def _month_end_on_or_before(index: pd.DatetimeIndex, as_of: pd.Timestamp) -> pd.Timestamp:
    clipped = index[index <= as_of]
    if clipped.empty:
        raise FallbackError(f"{as_of.date()} 之前没有交易日")
    period = clipped[-1].to_period("M")
    in_month = clipped[clipped.to_period("M") == period]
    last = in_month[-1]
    if last != clipped[-1]:
        # as_of 不是该月最后一个已有交易日：信号仍是上一个完整月末。
        previous = clipped[clipped.to_period("M") < period]
        if previous.empty:
            raise FallbackError(f"{as_of.date()} 之前还没有一个完整月末")
        prev_period = previous[-1].to_period("M")
        return previous[previous.to_period("M") == prev_period][-1]
    return last


def _status(statuses: dict[str, str], code: str) -> str:
    state = statuses.get(code, "normal")
    if state not in KNOWN_STATUS:
        raise FallbackError(f"{code} 的交易状态 {state} 无法识别")
    return state


def resolve_execution_fund(book: AShareBook, statuses: dict[str, str] | None = None) -> tuple[str, str | None]:
    """主基金正常交易就用主基金。清盘、停牌或暂停交易时，取同指数里上市最早且仍正常交易的备选。"""
    statuses = statuses or {}
    state = _status(statuses, book.primary)
    if state not in UNAVAILABLE:
        return book.primary, None
    ranked = sorted(book.alternates, key=lambda alt: (alt.list_date, alt.code))
    for alt in ranked:
        if _status(statuses, alt.code) not in UNAVAILABLE:
            return alt.code, state
    raise FallbackError(f"{book.container} 主基金 {book.primary} 为 {state}，同指数没有仍正常交易的备选")


def published_cutoff(as_of: str | pd.Timestamp, trading_days: list, lag: int) -> pd.Timestamp:
    """决策日 T 只能使用日期 ≤ T−lag 个交易日的净值。lag 含 T 本身往回数。"""
    if lag < 1:
        raise FallbackError("净值公布滞后至少 1 个交易日")
    day = pd.Timestamp(as_of).normalize()
    days = sorted({pd.Timestamp(item).normalize() for item in trading_days if pd.Timestamp(item).normalize() <= day})
    if not days or days[-1] != day:
        raise FallbackError(f"{day.date()} 不是交易日，不能定溢价")
    if len(days) <= lag:
        raise FallbackError("交易日不够覆盖净值公布滞后")
    return days[-1 - lag]


def select_nav(rows: list[NavRow], code: str, cutoff: pd.Timestamp) -> NavRow:
    eligible = [row for row in rows if row.code == code and row.date.normalize() <= cutoff and row.unit_nav > 0]
    if not eligible:
        raise FallbackError(f"{code} 在 {cutoff.date()} 及之前没有已公布的单位净值")
    eligible.sort(key=lambda row: (row.date, row.fetched_at))
    return eligible[-1]


def _trading_days(trading_days: list) -> list[pd.Timestamp]:
    return sorted({pd.Timestamp(item).normalize() for item in trading_days})


def a_share_session(as_of: str | pd.Timestamp, trading_days: list) -> bool:
    """A 股腿只在每月第一个交易日对齐。月末出信号，当天不再调一次。"""
    day = pd.Timestamp(as_of).normalize()
    month = [item for item in _trading_days(trading_days) if item.to_period("M") == day.to_period("M")]
    if day not in month:
        raise FallbackError(f"{day.date()} 不在交易日历这个月里")
    return day == month[0]


def next_trading_day(day: str | pd.Timestamp, trading_days: list) -> pd.Timestamp:
    """决策日的下一交易日。中间的休市日跳过。"""
    current = pd.Timestamp(day).normalize()
    days = _trading_days(trading_days)
    if current not in days:
        raise FallbackError(f"{current.date()} 不是交易日")
    later = [item for item in days if item > current]
    if not later:
        raise FallbackError(f"{current.date()} 之后没有交易日")
    return later[0]


def schedule_execution(decision: str | pd.Timestamp, trading_days: list) -> dict:
    """月末（或任一决策日）决定，下一交易日执行。A 股是否对齐看执行日是不是该月第一个交易日。"""
    decision_ts = pd.Timestamp(decision).normalize()
    execution = next_trading_day(decision_ts, trading_days)
    return {
        "decision_date": decision_ts,
        "execution_date": execution,
        "a_share_due": a_share_session(execution, trading_days),
    }


def _whole_shares(value) -> int:
    number = float(value)
    if abs(number - round(number)) > 1e-6:
        raise FallbackError("持仓股数必须是整数")
    return int(round(number))


def _price(prices: dict[str, float], code: str) -> float:
    if code not in prices:
        raise FallbackError(f"{code} 没有决策日收盘价")
    price = float(prices[code])
    if price <= 0:
        raise FallbackError(f"{code} 的收盘价必须是正数")
    return price


def _lot_floor(value: float, price: float, lot: int) -> int:
    if value <= 0:
        return 0
    return int(value / price / lot) * lot


def _market_value(shares: dict[str, int], prices: dict[str, float], codes: list[str]) -> float:
    total = 0.0
    for code in codes:
        held = shares.get(code, 0)
        if held:
            total += held * _price(prices, code)
    return total


def _sell_down(shares: dict[str, int], prices: dict[str, float], premiums: dict[str, float],
               target_value: float, lot: int) -> dict[str, int]:
    """从溢价最高的持仓开始卖，卖到市值不再高于目标。下一手会卖穿目标时停。"""
    out = dict(shares)

    def total() -> float:
        return sum(out[code] * prices[code] for code in out if out[code])

    while total() > target_value + 1e-8:
        held = [code for code, count in out.items() if count > 0]
        if not held:
            break
        held.sort(key=lambda code: (-premiums[code], code))
        code = held[0]
        step = lot if out[code] >= lot else out[code]
        if step <= 0 or total() - step * prices[code] < target_value - 1e-8:
            break
        out[code] -= step
    return out


def _outside_band(actual: float, target: float, band: float) -> bool:
    """偏离超过 band。用百分点比较，刚好等于带宽不算超过。"""
    return round(abs(actual - target) * 100, 6) > round(band * 100, 6)


def _over_cap(premium: float, cap: float) -> bool:
    return round(premium, 8) > round(cap, 8)


def _unique(items: list[str]) -> list[str]:
    out = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def _check_holdings_payload(payload: dict) -> dict:
    if HOLDINGS_FORBIDDEN & set(payload):
        raise FallbackError("目标持仓输出含有绩效字段")
    return payload


def plan_targets(cfg: FallbackConfig, *, as_of: str | pd.Timestamp, equity: float,
                 holdings: dict[str, int] | None, prices: dict[str, float],
                 nav_rows: list[NavRow], trading_days: list,
                 statuses: dict[str, str] | None = None, in_market: bool = True,
                 a_share_due: bool = False, signal_date: str | pd.Timestamp | None = None,
                 decision_date: str | pd.Timestamp | None = None,
                 execution_date: str | pd.Timestamp | None = None,
                 nav_source: str = "", nav_note: str = "") -> dict:
    """执行日的目标股数。价格和溢价用决策日收盘；不返回任何区间收益或回撤。"""
    if equity <= 0:
        raise FallbackError("账户总权益必须是正数")
    if cfg.lot_size < 1:
        raise FallbackError("lot_size 必须是正整数")
    day = pd.Timestamp(as_of).normalize()
    decided = pd.Timestamp(decision_date).normalize() if decision_date is not None else day
    executed = pd.Timestamp(execution_date).normalize() if execution_date is not None else None
    statuses = statuses or {}
    current = {str(code): _whole_shares(count) for code, count in (holdings or {}).items()}
    lot = cfg.lot_size
    rules: list[str] = []
    cutoff = None
    premium_rows = []
    premiums: dict[str, float] = {}
    pools = {pool.container: pool for pool in cfg.pools}
    if cfg.pools:
        cutoff = published_cutoff(day, trading_days, cfg.nav_lag)
        for name in cfg.overseas:
            pool = pools[name]
            for code in pool.codes:
                nav = select_nav(nav_rows, code, cutoff)
                close = _price(prices, code)
                premium = close / nav.unit_nav - 1
                premiums[code] = premium
                premium_rows.append({
                    "code": code,
                    "pool": name,
                    "close": close,
                    "unit_nav": nav.unit_nav,
                    "nav_date": str(nav.date.date()),
                    "premium": round(premium, 8),
                    "chosen": False,
                })
    pool_codes = [code for pool in cfg.pools for code in pool.codes]
    overseas_before = _market_value(current, prices, pool_codes) / equity if pool_codes else 0.0
    outside = bool(pool_codes) and _outside_band(overseas_before, cfg.o_weight, cfg.band)
    rules.append("overseas_rebalance" if outside else "overseas_inside_band")

    a_codes: list[str] = []
    for book in cfg.funds:
        a_codes.append(book.primary)
        a_codes.extend(alt.code for alt in book.alternates)
    targets: dict[str, int] = {}
    labels: dict[str, str] = {}
    sleeves: dict[str, str] = {}
    if a_share_due:
        rules.append("a_share_monthly")
        for code in a_codes:
            targets[code] = 0
        if in_market:
            if not cfg.funds:
                raise FallbackError("A 股在场但没有执行基金")
            share = cfg.a_weight / len(cfg.funds)
            for book in cfg.funds:
                code, state = resolve_execution_fund(book, statuses)
                if state:
                    rules.append(f"primary_{state}:{book.primary}->{code}")
                labels[code] = book.container
                sleeves[code] = "a_share"
                targets[code] = targets.get(code, 0) + _lot_floor(equity * share, _price(prices, code), lot)
            haven_value = 0.0
        else:
            rules.append("valve_haven")
            haven_value = equity * cfg.a_weight
    else:
        rules.append("a_share_hold")
        for code in a_codes:
            targets[code] = current.get(code, 0)
        haven_value = None

    chosen: dict[str, str] = {}
    park = 0.0
    if cfg.pools:
        per = cfg.o_weight / len(cfg.overseas)
        for name in cfg.overseas:
            codes = list(pools[name].codes)
            held = {code: current.get(code, 0) for code in codes}
            current_value = _market_value(held, prices, codes)
            target_value = equity * per
            for code in codes:
                labels.setdefault(code, name)
                sleeves[code] = "overseas"
            if not outside:
                for code in codes:
                    targets[code] = held[code]
                continue
            lowest = min(codes, key=lambda code: (premiums[code], code))
            if _over_cap(premiums[lowest], cfg.premium_cap):
                rules.append(f"premium_cap:{name}")
                for code in codes:
                    targets[code] = held[code]
                shortfall = target_value - current_value
                if shortfall > 1e-8:
                    park += shortfall
                    rules.append("park_511880")
                continue
            if target_value > current_value + 1e-8:
                bought = _lot_floor(target_value - current_value, _price(prices, lowest), lot)
                for code in codes:
                    targets[code] = held[code]
                if bought:
                    targets[lowest] = held[lowest] + bought
                    chosen[name] = lowest
                    rules.append(f"buy_lowest_premium:{name}:{lowest}")
            elif current_value > target_value + 1e-8:
                reduced = _sell_down(held, prices, premiums, target_value, lot)
                for code in codes:
                    targets[code] = reduced[code]
                rules.append(f"sell_highest_premium:{name}")
            else:
                for code in codes:
                    targets[code] = held[code]

    haven = cfg.haven_code
    labels[haven] = "货币"
    sleeves[haven] = "haven"
    if a_share_due:
        cash_value = (haven_value or 0.0) + park
        targets[haven] = _lot_floor(cash_value, _price(prices, haven), lot) if cash_value > 1e-8 else 0
    else:
        extra = _lot_floor(park, _price(prices, haven), lot) if park > 1e-8 else 0
        targets[haven] = current.get(haven, 0) + extra
    for code, count in current.items():
        if code not in targets:
            targets[code] = count
            sleeves.setdefault(code, "other")

    for row in premium_rows:
        row["chosen"] = chosen.get(row["pool"]) == row["code"]
    positions = []
    invested = 0.0
    for code, count in targets.items():
        if count <= 0:
            continue
        price = _price(prices, code)
        value = count * price
        invested += value
        positions.append({
            "code": code,
            "name": labels.get(code, code),
            "sleeve": sleeves.get(code, "other"),
            "shares": count,
            "price": price,
            "market_value": round(value, 6),
        })
    positions.sort(key=lambda row: (row["sleeve"], row["code"]))
    payload = {
        "date": str(decided.date()),
        "decision_date": str(decided.date()),
        "execution_date": str(executed.date()) if executed is not None else None,
        "signal_date": str(pd.Timestamp(signal_date).date()) if signal_date is not None else str(decided.date()),
        "equity": equity,
        "holdings_in": current,
        "valve": "在场" if in_market else "出场",
        "a_share_due": bool(a_share_due),
        "nav_source": nav_source,
        "nav_note": nav_note,
        "nav_lag_trading_days": cfg.nav_lag,
        "nav_cutoff": str(cutoff.date()) if cutoff is not None else None,
        "band": cfg.band,
        "premium_cap": cfg.premium_cap,
        "overseas_weight_before": round(overseas_before, 8),
        "rules": _unique(rules),
        "premiums": premium_rows,
        "targets": positions,
        "residual_cash": round(equity - invested, 6),
    }
    return _check_holdings_payload(payload)


def load_fund_nav(db: Path) -> list[NavRow]:
    uri = f"{Path(db).resolve().as_uri()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        found = con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'fund_nav'").fetchone()
        if not found:
            raise FallbackError(f"{db} 没有 fund_nav 表")
        rows = con.execute(
            "SELECT code, date, unit_nav, fetched_at, source FROM fund_nav").fetchall()
    finally:
        con.close()
    out = []
    for code, nav_date, unit_nav, fetched_at, source in rows:
        if unit_nav is None:
            continue
        out.append(NavRow(str(code), pd.Timestamp(nav_date), float(unit_nav), str(fetched_at or ""), str(source or "")))
    return out


def load_closes(db: Path, codes: list[str], day: str) -> dict[str, float]:
    if not codes:
        return {}
    uri = f"{Path(db).resolve().as_uri()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        marks = ",".join("?" for _ in codes)
        rows = con.execute(
            f"SELECT code, close FROM bars WHERE adj = 'raw' AND date = ? AND code IN ({marks})",
            [day, *codes]).fetchall()
    finally:
        con.close()
    return {str(code): float(close) for code, close in rows if close is not None and float(close) > 0}


def load_calendar(db: Path) -> list[pd.Timestamp]:
    uri = f"{Path(db).resolve().as_uri()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        rows = con.execute("SELECT date FROM calendar ORDER BY date").fetchall()
    finally:
        con.close()
    if not rows:
        raise FallbackError(f"{db} 的 calendar 是空的")
    return [pd.Timestamp(row[0]) for row in rows]


def decision_state(panel: Path, as_of: str | pd.Timestamp, cfg: FallbackConfig) -> dict:
    """阀的在场/出场。回撤只留在这个字典里，调用方不要把它写进目标持仓。"""
    as_of_ts = pd.Timestamp(as_of)
    prices = _read_panel(panel, as_of_ts)
    a_ret, _o_ret = monthly_legs(prices, cfg)
    path = valve_path(a_ret, cfg.out, cfg.back)
    wide = prices.pivot(index="date", columns="container", values="close").sort_index()
    signal = _month_end_on_or_before(wide.index, as_of_ts)
    signal_period = signal.to_period("M")
    if signal_period not in {ts.to_period("M") for ts in a_ret.index}:
        raise FallbackError(f"{signal.date()} 还没有影子月收益，不能定阀")
    if path["as_of"].to_period("M") != signal_period:
        raise FallbackError("目标日的信号月与影子净值的最后一月不一致")
    return {"in_market": bool(path["in_market"]), "signal_date": signal,
            "drawdown": path["drawdown"], "closes": wide.loc[signal]}


def target_snapshot(panel: Path, as_of: str | pd.Timestamp, cfg: FallbackConfig) -> dict:
    """D 日目标。只含权重、阀状态、A 股腿距高点的回撤。不含任何区间收益。"""
    as_of_ts = pd.Timestamp(as_of)
    prices = _read_panel(panel, as_of_ts)
    a_ret, _o_ret = monthly_legs(prices, cfg)
    path = valve_path(a_ret, cfg.out, cfg.back)
    wide = prices.pivot(index="date", columns="container", values="close").sort_index()
    signal = _month_end_on_or_before(wide.index, as_of_ts)
    # 月末当天的目标是下一交易日要成交的新状态；月中则沿用上一个完整月末已经生效的状态。
    signal_period = signal.to_period("M")
    if signal_period not in {ts.to_period("M") for ts in a_ret.index}:
        raise FallbackError(f"{signal.date()} 还没有影子月收益，不能定阀")
    # valve_path 的状态是最后一根影子月处理完之后的状态。目标日的信号月必须就是这根。
    if path["as_of"].to_period("M") != signal_period:
        raise FallbackError("目标日的信号月与影子净值的最后一月不一致")
    closes = wide.loc[signal]
    codes = execution_map(cfg.universe)
    names = code_name(cfg.universe)
    state = 1 if path["in_market"] else 0
    raw = _target_weights(state, _available(closes, cfg.a_share), _available(closes, cfg.overseas), cfg)
    rows = []
    ordered = list(cfg.a_share) + list(cfg.overseas)
    if cfg.haven_code in raw:
        ordered = ordered + [cfg.haven_code]
    seen = set()
    for name in ordered:
        if name not in raw or name in seen:
            continue
        seen.add(name)
        if name == cfg.haven_code:
            code = cfg.haven_code
            label = names.get(code, code)
        else:
            code = codes.get(name)
            if not code:
                raise FallbackError(f"{name} 在 universe 里没有 execution_fund_code")
            label = name
        rows.append({"container": label, "execution_code": code, "weight": raw[name], "qdii_premium": "未接入"})
    payload = {
        "date": str(as_of_ts.date()),
        "signal_date": str(signal.date()),
        "valve": "在场" if path["in_market"] else "出场",
        "a_share_drawdown_from_high": path["drawdown"],
        "qdii_premium": "未接入",
        "weights": rows,
    }
    forbidden = {"cagr", "max_drawdown", "vol", "return", "returns", "rank"}
    if forbidden & set(payload):
        raise FallbackError("target 输出含有绩效字段")
    return payload


def _fmt_pct(value: float) -> str:
    return f"{value:+.1%}"


def _print_replicate(result: dict) -> None:
    a = result["monthly"]["a_valve"]
    b = result["monthly"]["blend"]
    d = result["daily"]
    print(f"设计期 {result['monthly']['first']} → {result['monthly']['last']}")
    print(f"月频 A股等权+阀25/10  {_fmt_pct(a['cagr'])}  {_fmt_pct(a['max_drawdown'])}  切换 {a['switches']}")
    print(f"月频 A股70%(阀25/10)+海外30%  {_fmt_pct(b['cagr'])}  {_fmt_pct(b['max_drawdown'])}")
    print(f"与 d2 的差（百分点） {json.dumps(result['d2_delta_pp'], ensure_ascii=False)}")
    print(f"日频 {d['first']} → {d['last']}  {_fmt_pct(d['cagr'])}  {_fmt_pct(d['max_drawdown'])}  切换 {d['switches']}")


def _print_target(result: dict) -> None:
    print(f"{result['date']}  信号日 {result['signal_date']}  阀 {result['valve']}  "
          f"A股距高点 {_fmt_pct(result['a_share_drawdown_from_high'])}  QDII {result['qdii_premium']}")
    print(f"{'容器':<12} {'代码':<8} {'权重':>10}  QDII")
    for row in result["weights"]:
        print(f"{row['container']:<12} {row['execution_code']:<8} {row['weight']:10.6f}  {row['qdii_premium']}")


def _print_holdings(result: dict) -> None:
    print(f"决策 {result['decision_date']}  执行 {result['execution_date']}  信号日 {result['signal_date']}  "
          f"阀 {result['valve']}  海外偏离前权重 {result['overseas_weight_before']:.4f}")
    print(f"净值截止 {result['nav_cutoff']}  滞后 {result['nav_lag_trading_days']}  来源 {result['nav_source']}")
    print("规则 " + ", ".join(result["rules"]))
    print(f"{'池':<8} {'代码':<8} {'净值日':<12} {'溢价':>10}  买入")
    for row in result["premiums"]:
        mark = "是" if row["chosen"] else ""
        print(f"{row['pool']:<8} {row['code']:<8} {row['nav_date']:<12} {row['premium']:10.4%}  {mark}")
    print(f"{'代码':<8} {'名称':<10} {'腿':<10} {'股数':>10} {'价格':>10}")
    for row in result["targets"]:
        print(f"{row['code']:<8} {row['name']:<10} {row['sleeve']:<10} {row['shares']:10d} {row['price']:10.4f}")
    print(f"剩余现金 {result['residual_cash']:.2f}")


def _read_json_map(path: Path | None) -> dict:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FallbackError(f"{path} 必须是对象")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.signals.fallback")
    parser.add_argument("--config", type=Path, default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)
    rep = sub.add_parser("replicate")
    rep.add_argument("--panel", type=Path, required=True)
    rep.add_argument("--end", default=None)
    rep.add_argument("--haven-db", type=Path, default=None)
    rep.add_argument("--out", type=Path, default=None)
    tgt = sub.add_parser("target")
    tgt.add_argument("--panel", type=Path, required=True)
    tgt.add_argument("--date", required=True)
    tgt.add_argument("--equity", type=float, required=True)
    tgt.add_argument("--holdings", type=Path, default=None)
    tgt.add_argument("--nav-db", type=Path, required=True)
    tgt.add_argument("--price-db", type=Path, default=None)
    tgt.add_argument("--status", type=Path, default=None)
    tgt.add_argument("--nav-source", default="fund_nav")
    tgt.add_argument("--nav-note", default="")
    tgt.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    try:
        if args.cmd == "replicate":
            end = args.end or cfg.design_end.date().isoformat()
            haven = args.haven_db
            if haven is None:
                default_db = ROOT / "data" / "market.sqlite"
                haven = default_db if default_db.exists() else None
            result = replicate(args.panel, end, cfg, haven_db=haven)
            _print_replicate(result)
            if args.out:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            return 0 if result["matches_d2"] else 1
        holdings = {str(code): value for code, value in _read_json_map(args.holdings).items()}
        statuses = {str(code): str(value) for code, value in _read_json_map(args.status).items()}
        price_db = args.price_db or (ROOT / "data" / "market.sqlite")
        codes = [cfg.haven_code, *holdings]
        for book in cfg.funds:
            codes.append(book.primary)
            codes.extend(alt.code for alt in book.alternates)
        for pool in cfg.pools:
            codes.extend(pool.codes)
        trading_days = load_calendar(price_db)
        schedule = schedule_execution(args.date, trading_days)
        # 阀和 A 股目标用决策日（上月最后一个交易日的收盘）。溢价和带宽也用这一天的收盘：
        # 执行日的收盘当时还没有。海外带宽和 A 股对齐写在同一张执行单上。
        state = decision_state(args.panel, schedule["decision_date"], cfg)
        nav_rows = load_fund_nav(args.nav_db)
        sources = sorted({row.source for row in nav_rows if row.source})
        nav_source = sources[0] if args.nav_source == "fund_nav" and len(sources) == 1 else args.nav_source
        result = plan_targets(
            cfg, as_of=schedule["decision_date"], equity=args.equity, holdings=holdings,
            prices=load_closes(price_db, sorted(set(codes)), schedule["decision_date"].date().isoformat()),
            nav_rows=nav_rows, trading_days=trading_days, statuses=statuses,
            in_market=state["in_market"], a_share_due=schedule["a_share_due"],
            signal_date=state["signal_date"], decision_date=schedule["decision_date"],
            execution_date=schedule["execution_date"], nav_source=nav_source, nav_note=args.nav_note)
        _print_holdings(result)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return 0
    except FallbackError as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
