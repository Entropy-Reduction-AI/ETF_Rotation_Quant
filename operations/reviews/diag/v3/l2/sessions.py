"""上交所交易日上的决策日。每周、每月取该周或该月最后一个交易日。"""
from __future__ import annotations

import pandas as pd


def decision_dates(dates: pd.DatetimeIndex, freq: str) -> pd.DatetimeIndex:
    if freq not in {"week", "month"}:
        raise ValueError(freq)
    if len(dates) == 0:
        return pd.DatetimeIndex([])
    index = pd.DatetimeIndex(pd.to_datetime(dates)).sort_values().unique()
    frame = pd.Series(index, index=index)
    if freq == "month":
        key = pd.Series(index.to_period("M"), index=index)
    else:
        iso = index.isocalendar()
        label = iso["year"].astype(str) + "-W" + iso["week"].astype(int).astype(str).str.zfill(2)
        key = pd.Series(label.to_numpy(), index=index)
    last = frame.groupby(key, sort=False).max()
    return pd.DatetimeIndex(pd.to_datetime(last.to_numpy())).sort_values()


def next_session(dates: pd.DatetimeIndex, day: pd.Timestamp) -> pd.Timestamp | None:
    """day 之后的第一个交易日。day 当天不是成交日。"""
    index = pd.DatetimeIndex(pd.to_datetime(dates))
    pos = int(index.searchsorted(pd.Timestamp(day), side="right"))
    if pos >= len(index):
        return None
    return pd.Timestamp(index[pos])
