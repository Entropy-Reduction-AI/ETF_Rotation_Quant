"""设计期复现。晚于设计期终点则拒绝，不算收益。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from src.portfolio.config import TRADING_DAYS, FallbackConfig, FallbackError
from src.portfolio.valve import slow_valve

# d2 设计期两行（百分数已换成小数）。误差按 ±0.1 个百分点。
D2_A_CAGR = 0.271
D2_A_DD = -0.426
D2_A_SWITCHES = 6
D2_BLEND_CAGR = 0.227
D2_BLEND_DD = -0.295
D2_TOL = 0.001

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
    """月频复现 d2，并给出扣成本的日频版。end 晚于设计期终点则拒绝，不读收益。

    生产开关 valve.enabled 不作用在这里。慢阀 25/10 留作设计期历史记录。
    """
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
