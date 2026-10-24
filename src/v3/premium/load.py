"""只读行情库里的收盘价、单位净值和上交所日历。不写库，不计算收益。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from .rules import PremiumError


def connect_readonly(path: Path) -> sqlite3.Connection:
    file = Path(path)
    if not file.exists() or file.stat().st_size < 1000:
        raise PremiumError(f"行情库不可读：{file}")
    return sqlite3.connect(f"{file.resolve().as_uri()}?mode=ro", uri=True)


def load_calendar(con: sqlite3.Connection) -> pd.DatetimeIndex:
    frame = pd.read_sql_query("SELECT date FROM calendar ORDER BY date", con)
    return pd.DatetimeIndex(pd.to_datetime(frame["date"]))


def load_close(con: sqlite3.Connection, code: str) -> pd.Series:
    frame = pd.read_sql_query(
        "SELECT date, close FROM bars WHERE adj = 'raw' AND code = ? AND close > 0 ORDER BY date",
        con, params=(str(code),))
    series = pd.Series(frame["close"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
    return series[~series.index.duplicated(keep="last")].sort_index()


def load_nav(con: sqlite3.Connection, code: str) -> pd.Series:
    frame = pd.read_sql_query(
        "SELECT date, unit_nav FROM fund_nav WHERE code = ? AND unit_nav > 0 ORDER BY date",
        con, params=(str(code),))
    series = pd.Series(frame["unit_nav"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
    return series[~series.index.duplicated(keep="last")].sort_index()
