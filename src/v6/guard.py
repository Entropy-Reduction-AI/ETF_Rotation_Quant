"""设计期隔离。默认任何晚于 2015-12-31 的行情索引在使用前失败。

正式考试授权后，只能把隔离打开到官方窗口终点 2026-09-30。
不能打开到无上限，也不能晚于这一天。行情 SQL 仍然必须自带日期上限。
"""

from __future__ import annotations

import pandas as pd

DESIGN_END = pd.Timestamp("2015-12-31")
DESIGN_END_TEXT = "2015-12-31"
OFFICIAL_WINDOW_END = pd.Timestamp("2026-09-30")
OFFICIAL_WINDOW_END_TEXT = "2026-09-30"

_active_end = DESIGN_END
_active_end_text = DESIGN_END_TEXT


class IsolationError(RuntimeError):
    """读到了允许窗口之后的数据，或查询没有日期上限。"""


def load_end_text() -> str:
    """装载用的日期上限。未打开正式窗口时仍是 2015-12-31。"""
    return _active_end_text


def open_official_isolation(end: str, *, authorized: bool) -> str:
    """把隔离放到这次窗口的终点。未授权时不能晚于设计期，任何时候不能晚于 2026-09-30。"""
    stamp = pd.Timestamp(end)
    text = stamp.date().isoformat()
    if stamp > OFFICIAL_WINDOW_END:
        raise IsolationError(f"隔离不能晚于 {OFFICIAL_WINDOW_END_TEXT}")
    if stamp > DESIGN_END and not authorized:
        raise IsolationError("正式窗口未授权，隔离仍停在设计期")
    global _active_end, _active_end_text
    _active_end = stamp
    _active_end_text = text
    return text


def assert_not_after(index, what: str) -> None:
    stamps = pd.DatetimeIndex(pd.to_datetime(index)).dropna()
    if len(stamps) == 0:
        return
    last = pd.Timestamp(stamps.max())
    if last > _active_end:
        raise IsolationError(f"{what} 最晚 {last.date()}，晚于 {_active_end_text}")


def sql_is_capped(sql: str) -> bool:
    """行情类查询必须自带日期上限。没有日期列的语句不在此列。"""
    low = " ".join(sql.lower().split())
    tables = ("bars", "fund_nav", "v4_series", "cash_dividends", "ohlc")
    if not any(name in low for name in tables):
        return True
    markers = ("date<=", "date <=", "ex_date<=", "ex_date <=")
    return any(mark in low for mark in markers)


def assert_sql(sql: str, params=None) -> None:
    if not sql_is_capped(sql):
        raise IsolationError(f"查询没有日期上限：{sql}")
    if not params:
        return
    values = params.values() if isinstance(params, dict) else params
    for value in values:
        if isinstance(value, str) and len(value) >= 10 and value[4] == "-" and value[:10] > _active_end_text:
            raise IsolationError(f"查询参数晚于隔离窗口：{value}")


def install_readers(pandas_module, pathlib_read=None):
    """包一层读取器：行情 SQL 必须封顶；欧洲普查目录和 2016 以后的外部文件不打开。"""
    original_sql = pandas_module.read_sql_query
    original_csv = pandas_module.read_csv

    def read_sql_query(sql, con, params=None, *args, **kwargs):
        assert_sql(sql, params)
        return original_sql(sql, con, params=params, *args, **kwargs)

    def read_csv(path, *args, **kwargs):
        text = str(path)
        blocked = ("data_census", "europe-japan", "49_Industry_Portfolios", "DTB3.csv")
        if any(piece in text for piece in blocked):
            raise IsolationError(f"本轮不读这个文件：{text}")
        return original_csv(path, *args, **kwargs)

    pandas_module.read_sql_query = read_sql_query
    pandas_module.read_csv = read_csv
    return original_sql, original_csv


def restore_readers(pandas_module, originals) -> None:
    pandas_module.read_sql_query, pandas_module.read_csv = originals
