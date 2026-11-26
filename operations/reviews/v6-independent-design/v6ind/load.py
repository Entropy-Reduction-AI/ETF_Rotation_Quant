"""只读行情。每条 SQL 都先写 date <= 截止日，不把更晚的收盘读进进程。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from . import CUTOFF

CLOSE_SQL = (
    "SELECT date, close FROM bars "
    "WHERE code = ? AND adj = ? AND date <= ? "
    "ORDER BY date"
)
FIELD_SQL = (
    "SELECT date, close, volume, amount FROM bars "
    "WHERE code = ? AND adj = ? AND date <= ? "
    "ORDER BY date"
)
FX_SQL = (
    "SELECT date, close FROM v4_series "
    "WHERE code = ? AND kind = 'fx' AND close > 0 AND date <= ? "
    "ORDER BY date"
)
PROVENANCE_SQL = (
    "SELECT source, COUNT(*), MIN(date), MAX(date), "
    "SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END), "
    "SUM(CASE WHEN volume IS NULL THEN 1 ELSE 0 END), "
    "SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) "
    "FROM bars WHERE code = ? AND adj = ? AND date <= ? "
    "GROUP BY source"
)
EXCLUDED_SQL = "SELECT COUNT(*) FROM bars WHERE code = ? AND adj = ? AND date > ?"
NULL_DATE_SQL = (
    "SELECT date FROM bars WHERE code = ? AND adj = ? AND date <= ? AND close IS NULL ORDER BY date"
)


class CutoffBreach(RuntimeError):
    pass


def connect_readonly(path: Path) -> sqlite3.Connection:
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        con.execute("CREATE TABLE reviewer_write_probe (x INTEGER)")
    except sqlite3.OperationalError:
        return con
    raise RuntimeError(f"连接不是只读：{path}")


def load_closes(con: sqlite3.Connection, code: str, adj: str = "raw", cutoff: str = CUTOFF) -> list[tuple[str, float]]:
    if "date <= ?" not in CLOSE_SQL:
        raise CutoffBreach("收盘查询缺少日期过滤")
    rows: list[tuple[str, float]] = []
    for date, close in con.execute(CLOSE_SQL, (code, adj, cutoff)):
        date = str(date)
        if date > cutoff:
            raise CutoffBreach(f"{code} {date} 晚于 {cutoff}")
        if close is None:
            continue
        rows.append((date, float(close)))
    return rows


def load_fields(con: sqlite3.Connection, code: str, adj: str = "raw", cutoff: str = CUTOFF) -> list[tuple[str, float | None, float | None, float | None]]:
    if "date <= ?" not in FIELD_SQL:
        raise CutoffBreach("字段查询缺少日期过滤")
    rows = []
    for date, close, volume, amount in con.execute(FIELD_SQL, (code, adj, cutoff)):
        date = str(date)
        if date > cutoff:
            raise CutoffBreach(f"{code} {date} 晚于 {cutoff}")
        rows.append((date, None if close is None else float(close),
                     None if volume is None else float(volume),
                     None if amount is None else float(amount)))
    return rows


def load_fx(con: sqlite3.Connection, code: str = "USDCNY", cutoff: str = CUTOFF) -> list[tuple[str, float]]:
    if "date <= ?" not in FX_SQL:
        raise CutoffBreach("汇率查询缺少日期过滤")
    rows = []
    for date, close in con.execute(FX_SQL, (code, cutoff)):
        date = str(date)
        if date > cutoff:
            raise CutoffBreach(f"{code} {date} 晚于 {cutoff}")
        rows.append((date, float(close)))
    return rows


def provenance(con: sqlite3.Connection, code: str, adj: str = "raw", cutoff: str = CUTOFF) -> dict:
    kept = [
        {
            "source": source,
            "rows": int(rows),
            "first": first,
            "last": last,
            "null_close": int(null_close),
            "null_volume": int(null_volume),
            "null_amount": int(null_amount),
        }
        for source, rows, first, last, null_close, null_volume, null_amount in con.execute(
            PROVENANCE_SQL, (code, adj, cutoff)
        )
    ]
    excluded = int(con.execute(EXCLUDED_SQL, (code, adj, cutoff)).fetchone()[0])
    null_dates = [str(row[0]) for row in con.execute(NULL_DATE_SQL, (code, adj, cutoff))]
    for date in null_dates:
        if date > cutoff:
            raise CutoffBreach(f"{code} null date {date}")
    for item in kept:
        if item["last"] is not None and item["last"] > cutoff:
            raise CutoffBreach(f"{code} provenance last {item['last']}")
    return {
        "code": code,
        "adj": adj,
        "cutoff": cutoff,
        "kept": kept,
        "excluded_rows": excluded,
        "null_close_dates": null_dates,
    }
