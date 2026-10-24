"""BM-主：70% 沪深300全收益 + 15% 纳指100全收益 + 15% 标普500全收益，月初再平衡。

与第一阶段 `src/report/evidence.py` 同一条汇率和同一条再平衡。结束日默认停在设计期。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from src.report.blend import monthly_rebalance
from src.report.fx import cny_from_usd
from src.research.prereg_v2.engine import cash_daily, haven_total_return, load_haven

from .book import DESIGN_END, RunnerError, assert_window

WEIGHTS = {"H00300": 0.70, "XNDX": 0.15, "SP500TR": 0.15}


def _connect(path: Path) -> sqlite3.Connection:
    if not Path(path).exists() or Path(path).stat().st_size < 1000:
        raise RunnerError(f"行情库不可读：{path}")
    uri = f"{Path(path).resolve().as_uri()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _calendar(con: sqlite3.Connection, end: str) -> pd.DatetimeIndex:
    frame = pd.read_sql_query(
        "SELECT date FROM calendar WHERE date <= ? ORDER BY date", con, params=(end,))
    return pd.DatetimeIndex(pd.to_datetime(frame["date"]))


def _fx(con: sqlite3.Connection, end: str) -> pd.Series:
    frame = pd.read_sql_query(
        "SELECT date, close, source FROM bars WHERE code = 'USDCNY' AND adj = 'raw' AND close > 0 "
        "AND date <= ? ORDER BY date",
        con, params=(end,))
    if frame.empty:
        raise RunnerError("bars 里没有 USDCNY")
    if set(frame["source"]) != {"chinamoney"}:
        raise RunnerError(f"USDCNY 来源不是 chinamoney：{set(frame['source'])}")
    series = pd.Series(frame["close"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
    return series[~series.index.duplicated(keep="last")].sort_index()


def _closes(con: sqlite3.Connection, code: str, calendar: pd.DatetimeIndex, end: str) -> pd.Series:
    frame = pd.read_sql_query(
        "SELECT date, close FROM bars WHERE code = ? AND adj = 'raw' AND close > 0 AND date <= ? ORDER BY date",
        con, params=(code, end))
    if frame.empty:
        raise RunnerError(f"bars 里没有 {code}")
    series = pd.Series(frame["close"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
    series = series[~series.index.duplicated(keep="last")].sort_index()
    return series.loc[series.index.isin(calendar)]


def _ohlc(con: sqlite3.Connection, code: str, end: str) -> pd.DataFrame:
    frame = pd.read_sql_query(
        "SELECT date, open, high, low, close, volume FROM bars WHERE code = ? AND adj = 'raw' "
        "AND close > 0 AND date <= ? ORDER BY date",
        con, params=(code, end))
    if frame.empty:
        raise RunnerError(f"bars 里没有 {code}")
    frame["date"] = pd.to_datetime(frame["date"])
    for column in ("open", "high", "low"):
        frame[column] = frame[column].fillna(frame["close"])
    frame["volume"] = frame["volume"].fillna(0.0)
    return frame


def _level_returns(level: pd.Series) -> pd.Series:
    clean = level.sort_index().astype(float)
    clean = clean[~clean.index.duplicated(keep="last")]
    returns = clean.pct_change().iloc[1:].dropna()
    returns.name = "ret"
    return returns.astype(float)


def _cny_returns(frame: pd.DataFrame) -> pd.Series:
    level = pd.Series(frame["close_cny"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
    return _level_returns(level)


def bm_main(db: Path, end: str | pd.Timestamp = DESIGN_END, *, allow_after: bool = False) -> pd.Series:
    """设计期调用不得读入 2016 年之后的行情。"""
    end_ts = pd.Timestamp(end)
    if not allow_after and end_ts > DESIGN_END:
        raise RunnerError(f"BM-主 拒绝结束日 {end_ts.date()}")
    end_text = str(end_ts.date())
    con = _connect(db)
    try:
        calendar = _calendar(con, end_text)
        fx = _fx(con, end_text)
        h00300 = _level_returns(_closes(con, "H00300", calendar, end_text))
        xndx = _cny_returns(cny_from_usd(_ohlc(con, "XNDX", end_text), fx, calendar))
        spx = _cny_returns(cny_from_usd(_ohlc(con, "^SP500TR", end_text), fx, calendar))
    finally:
        con.close()
    parts = pd.concat([h00300.rename("H00300"), xndx.rename("XNDX"), spx.rename("SP500TR")], axis=1).dropna()
    series, _weights = monthly_rebalance(parts, WEIGHTS)
    assert_window(series.index, allow_after)
    return series


def cash_returns(db: Path, calendar: pd.DatetimeIndex, end: str | pd.Timestamp,
                 annual: float = 0.02) -> pd.Series:
    """511880 上市前每个上交所交易日 0.02/252；上市后用收盘价收益，除息日加分红。"""
    end_ts = pd.Timestamp(end)
    closes, dividends = load_haven(Path(db), "511880", end_ts)
    if closes.empty:
        return pd.Series(cash_daily(annual), index=pd.DatetimeIndex(calendar), dtype=float)
    series = haven_total_return(closes, dividends, calendar, cash_daily(annual))
    series.index = pd.to_datetime(series.index)
    return series.astype(float)
