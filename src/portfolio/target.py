"""目标股数和权重快照。不含区间收益。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from src.portfolio.config import (
    FallbackConfig,
    FallbackError,
    NavRow,
    code_name,
    execution_map,
)
from src.portfolio.execution import (
    _lot_floor,
    _market_value,
    _outside_band,
    _over_cap,
    _price,
    _sell_down,
    _unique,
    _whole_shares,
    published_cutoff,
    resolve_execution_fund,
    select_nav,
)
from src.portfolio.replicate import _available, _read_panel, _target_weights, monthly_legs
from src.portfolio.valve import valve_path


def valve_label(enabled: bool, in_market: bool) -> str:
    """阀关掉之后快照写「关闭（D7）」。开着时仍是在场或出场。"""
    if not enabled:
        return "关闭（D7）"
    return "在场" if in_market else "出场"

HOLDINGS_FORBIDDEN = {"cagr", "max_drawdown", "vol", "return", "returns", "rank", "sharpe", "drawdown"}

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
    """执行日的目标股数。价格和溢价用决策日收盘；不返回任何区间收益或回撤。

    valve.enabled 为假时 A 股腿永远在场，不采用调用方传来的阀状态。
    """
    if not cfg.valve_enabled:
        in_market = True
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
        "valve": valve_label(cfg.valve_enabled, in_market),
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
    """D 日目标。只含权重和阀状态。阀开着时附上 A 股腿距高点的回撤。不含任何区间收益。"""
    as_of_ts = pd.Timestamp(as_of)
    prices = _read_panel(panel, as_of_ts)
    wide = prices.pivot(index="date", columns="container", values="close").sort_index()
    signal = _month_end_on_or_before(wide.index, as_of_ts)
    drawdown = None
    in_market = True
    if cfg.valve_enabled:
        a_ret, _o_ret = monthly_legs(prices, cfg)
        path = valve_path(a_ret, cfg.out, cfg.back)
        # 月末当天的目标是下一交易日要成交的新状态；月中则沿用上一个完整月末已经生效的状态。
        signal_period = signal.to_period("M")
        if signal_period not in {ts.to_period("M") for ts in a_ret.index}:
            raise FallbackError(f"{signal.date()} 还没有影子月收益，不能定阀")
        # valve_path 的状态是最后一根影子月处理完之后的状态。目标日的信号月必须就是这根。
        if path["as_of"].to_period("M") != signal_period:
            raise FallbackError("目标日的信号月与影子净值的最后一月不一致")
        in_market = bool(path["in_market"])
        drawdown = path["drawdown"]
    closes = wide.loc[signal]
    codes = execution_map(cfg.universe)
    names = code_name(cfg.universe)
    state = 1 if in_market else 0
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
        "valve": valve_label(cfg.valve_enabled, in_market),
        "a_share_drawdown_from_high": drawdown,
        "qdii_premium": "未接入",
        "weights": rows,
    }
    forbidden = {"cagr", "max_drawdown", "vol", "return", "returns", "rank"}
    if forbidden & set(payload):
        raise FallbackError("target 输出含有绩效字段")
    return payload
