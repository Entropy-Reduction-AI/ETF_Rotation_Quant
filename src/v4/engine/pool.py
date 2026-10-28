"""T4 新池的研究序列。只构造排名用的收益，不跑组合。

美股行业：后复权美元收盘严格早于 D，乘 D 当天或之前的美元中间价。
港股四个分类：价格指数对齐到严格早于 D 的收盘，再乘 D 当天或之前的港币中间价。
`filled=True` 时中间价用含 2005 年补齐的 v4 序列。开关关闭时不调用。
"""
from __future__ import annotations

import sqlite3

import pandas as pd

from src.report.blend import monthly_rebalance
from src.report.fx import cny_from_usd, latest_on_or_before
from src.v3.engine.benchmark import WEIGHTS, _closes, _cny_returns, _level_returns, _ohlc
from src.v3.engine.market import _research_level, _split_bars, _usd_level
from src.v3.engine.prices import signal_returns
from src.v3.engine.score import lookback_panel
from src.v3.engine.sessions import decision_dates
from src.v3.engine.spec import Spec
from src.v4.data.catalog import ETFS, HSI_SUB

US_SECTORS = tuple((item["container_id"], item["code"]) for item in ETFS)
HK_SECTORS = tuple((item["container_id"], item["code"]) for item in HSI_SUB)


def load_mid(con: sqlite3.Connection, code: str, end: str, *, filled: bool) -> pd.Series:
    """`filled` 读 v4_series 的 fx（含 2005 补齐）。否则读 bars 里的 chinamoney。"""
    if filled:
        frame = pd.read_sql_query(
            "SELECT date, close FROM v4_series WHERE code = ? AND kind = 'fx' AND close > 0 "
            "AND date <= ? ORDER BY date",
            con, params=(code, end))
    else:
        frame = pd.read_sql_query(
            "SELECT date, close FROM bars WHERE code = ? AND adj = 'raw' AND close > 0 "
            "AND date <= ? ORDER BY date",
            con, params=(code, end))
    if frame.empty:
        return pd.Series(dtype=float)
    series = pd.Series(frame["close"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
    return series[~series.index.duplicated(keep="last")].sort_index()


def _closes_frame(con: sqlite3.Connection, code: str, end: str, *, kind: str) -> pd.DataFrame:
    if kind == "backward":
        frame = pd.read_sql_query(
            "SELECT date, close FROM v4_series WHERE code = ? AND kind = 'backward' AND close > 0 "
            "AND date <= ? ORDER BY date",
            con, params=(code, end))
    else:
        frame = pd.read_sql_query(
            "SELECT date, close FROM bars WHERE code = ? AND adj = 'raw' AND close > 0 "
            "AND date <= ? ORDER BY date",
            con, params=(code, end))
    if frame.empty:
        return pd.DataFrame(columns=["date", "open", "close"])
    frame["date"] = pd.to_datetime(frame["date"])
    frame["open"] = frame["close"]
    return frame.loc[:, ["date", "open", "close"]]


def _hk_level(code: str, bars: dict, calendar, spec: Spec, hkd: pd.Series | None):
    level, fresh, gaps = _research_level(code, "tencent_hk_index", bars, {}, calendar, None, spec, None)
    if hkd is None:
        return level, fresh, gaps
    rate = latest_on_or_before(hkd, calendar)
    priced = level * rate.reindex(calendar).to_numpy(dtype=float)
    fresh = fresh.reindex(calendar).fillna(False).astype(bool) & rate.notna().to_numpy() & priced.notna()
    return priced, fresh, gaps


def added_signals(con: sqlite3.Connection, calendar: pd.DatetimeIndex, spec: Spec, end: str, *,
                  adjusted: bool, hk_fx: bool, usd_filled: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    """返回 (信号收益, 是否可排名)。列是新容器。不含组合净值。"""
    usd = load_mid(con, "USDCNY", end, filled=usd_filled)
    hkd = load_mid(con, "HKDCNY", end, filled=True) if hk_fx else None
    hk_codes = [code for _name, code in HK_SECTORS]
    hk_bars = {}
    if hk_codes:
        marks = ",".join("?" * len(hk_codes))
        frame = pd.read_sql_query(
            "SELECT code, date, open, close FROM bars WHERE adj = 'raw' AND date <= ? "
            f"AND code IN ({marks})",
            con, params=[end, *hk_codes])
        hk_bars = _split_bars(frame)
    signals = {}
    fresh = {}
    for name, code in US_SECTORS:
        block = _closes_frame(con, code, end, kind="backward" if adjusted else "raw")
        if block.empty:
            continue
        level, flag, _gaps = _usd_level(block, usd, calendar, spec.stale_limit, None)
        signals[name] = signal_returns(level, pd.DatetimeIndex([])).reindex(calendar)
        fresh[name] = flag.reindex(calendar).fillna(False).astype(bool)
    for name, code in HK_SECTORS:
        level, flag, gaps = _hk_level(code, hk_bars, calendar, spec, hkd)
        signals[name] = signal_returns(level, gaps).reindex(calendar)
        fresh[name] = flag.reindex(calendar).fillna(False).astype(bool)
    if not signals:
        empty = pd.DataFrame(index=calendar)
        return empty, empty
    return pd.DataFrame(signals, index=calendar), pd.DataFrame(fresh, index=calendar)


def top_names(signal: pd.DataFrame, fresh: pd.DataFrame, cash_id: str, names: list[str],
              spec: Spec, day: pd.Timestamp, length: int, n: int = 8) -> list[str]:
    """一个决策日、一个回看期的前 n 名。排序与 v3.1 的 pick_row 相同。不算组合收益。"""
    panel = lookback_panel(signal, cash_id, length)
    stamp = pd.Timestamp(day)
    total = panel.total.loc[stamp]
    score = panel.score.loc[stamp]
    ok = panel.ok.loc[stamp]
    gate = fresh.loc[stamp]
    ranked = []
    for name in names:
        if name == cash_id or not bool(ok[name]) or not bool(gate[name]):
            continue
        ranked.append((float(score[name]), float(total[name]), name))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [item[2] for item in ranked[:n]]


def month_decision(dates: pd.DatetimeIndex, year: int, month: int) -> pd.Timestamp:
    days = decision_dates(dates, "month")
    matched = [day for day in days if int(day.year) == year and int(day.month) == month]
    if len(matched) != 1:
        raise RuntimeError(f"{year}-{month:02d} 的月末决策日不是 1 个")
    return pd.Timestamp(matched[0])


def bm_nav_level(con: sqlite3.Connection, calendar: pd.DatetimeIndex, end: str) -> pd.Series:
    """T2 用的 BM-主净值。汇率用含 2005 补齐的美元中间价。返回的是净值水平，不是收益汇总。"""
    fx = load_mid(con, "USDCNY", end, filled=True)
    h00300 = _level_returns(_closes(con, "H00300", calendar, end))
    xndx = _cny_returns(cny_from_usd(_ohlc(con, "XNDX", end), fx, calendar))
    spx = _cny_returns(cny_from_usd(_ohlc(con, "^SP500TR", end), fx, calendar))
    parts = pd.concat([
        h00300.rename("H00300"),
        xndx.rename("XNDX"),
        spx.rename("SP500TR"),
    ], axis=1).dropna()
    rets, _weights = monthly_rebalance(parts, WEIGHTS)
    nav = (1.0 + rets).cumprod()
    prior = calendar[calendar < nav.index.min()] if len(nav) else calendar[:0]
    if len(prior):
        start = pd.Series([1.0], index=pd.DatetimeIndex([prior[-1]]))
        nav = pd.concat([start, nav])
    nav = nav[~nav.index.duplicated(keep="last")].sort_index()
    return nav.reindex(calendar).ffill()
