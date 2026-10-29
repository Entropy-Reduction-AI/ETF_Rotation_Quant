"""附表 A 的月末。SF-6，待 Manager 确认。

月末决策日是上交所交易日历里、每个自然月的最后一个交易日。调用方传入的
`dates` 就是这本日历，不是某一条腿自己的打印日，也不是自然月的最后一天。

一个交易日是该月月末，当下一交易日已经落在更晚的自然月。日历停在月中、
后面没有下个月的交易日时，这最后一个月不算月末，除非 `calendar_closed=True`
（调用方保证日历已经收到该月最后一个上交所交易日）。后者与
`decision_dates(dates, "month")` 相同。

成交日是决策日之后的下一个交易日，用 `next_session`。决策日当天不成交。
"""
from __future__ import annotations

import pandas as pd

from src.v3.engine.sessions import next_session

MONTH_END_RULE = "sse-last-session-of-calendar-month"
SF6_STATUS = "pending-manager"


def month_end_sessions(dates, *, calendar_closed: bool = False) -> pd.DatetimeIndex:
    """返回月末决策日。`dates` 是上交所交易日。"""
    index = pd.DatetimeIndex(pd.to_datetime(dates)).normalize().sort_values().unique()
    if len(index) == 0:
        return pd.DatetimeIndex([])
    periods = index.to_period("M")
    last = pd.Series(index, index=index).groupby(periods, sort=False).max()
    kept: list[pd.Timestamp] = []
    final = periods[-1]
    for period, day in last.items():
        stamp = pd.Timestamp(day)
        nxt = next_session(index, stamp)
        complete = nxt is not None and pd.Timestamp(nxt).to_period("M") > period
        if complete or (calendar_closed and period == final):
            kept.append(stamp)
    if not kept:
        return pd.DatetimeIndex([])
    return pd.DatetimeIndex(kept).sort_values()
