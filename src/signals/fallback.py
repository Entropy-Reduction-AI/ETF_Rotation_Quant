"""R4 收手版：A 股慢阀 + 海外底仓。

慢阀与 operations/reviews/diag/d2.py 同一套月末规则：影子净值始终按 A 股腿满仓计算；
在场时月末距历史高点的回撤超过 out 才出场；出场后月末距出场以来最低月末的反弹超过 back 才回场，
回场当时把高点重置为该净值。比较都是严格不等号。

replicate 只用到设计期终点。晚于该日直接拒绝，不算收益。
target 只给某一天的目标权重、阀状态和当时距高点的回撤。
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
class FallbackConfig:
    pending: str
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

    @property
    def cash_monthly(self) -> float:
        return self.cash_annual / 12

    @property
    def cash_daily(self) -> float:
        return self.cash_annual / TRADING_DAYS


def load_config(path: Path | None = None) -> FallbackConfig:
    path = Path(path) if path else DEFAULT_CONFIG
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    a = raw["a_share"]
    o = raw["overseas"]
    v = raw["valve"]
    ex = raw["execution"]
    cfg = FallbackConfig(
        pending=str(raw["pending"]),
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
        universe=(path.parent.parent / ex["universe"]).resolve() if not Path(ex["universe"]).is_absolute()
        else Path(ex["universe"]),
        path=path,
    )
    if cfg.judge != "month_end":
        raise FallbackError(f"慢阀只在月末判定，配置是 {cfg.judge}")
    if cfg.rebalance != "monthly":
        raise FallbackError(f"再平衡只做月度，配置是 {cfg.rebalance}")
    if not cfg.a_share or not cfg.overseas:
        raise FallbackError("A 股腿和海外腿都不能是空的")
    if abs(cfg.a_weight + cfg.o_weight - 1) > 1e-9:
        raise FallbackError("A 股权重与海外权重之和必须是 1")
    if cfg.out <= 0 or cfg.back <= 0:
        raise FallbackError("out 和 back 必须是正数")
    return cfg


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
        "pending": cfg.pending,
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
        "pending": cfg.pending,
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
    print(f"设计期 {result['monthly']['first']} → {result['monthly']['last']}  {result['pending']}")
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
        result = target_snapshot(args.panel, args.date, cfg)
        _print_target(result)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return 0
    except FallbackError as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
