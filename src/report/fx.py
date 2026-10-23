"""海外点位换成人民币：沿用面板构造器的 D−1 对齐，再乘对齐日当天或之前的最近中间价。"""
from __future__ import annotations

import pandas as pd

from src.indicators.build import align_to_calendar


def latest_on_or_before(fx: pd.Series, days: pd.DatetimeIndex) -> pd.Series:
    """每个日期取当天或之前最近一个中间价。更早没有中间价的日子是空值。"""
    if fx.empty:
        return pd.Series(index=pd.DatetimeIndex(days), dtype=float)
    right = fx.sort_index()
    right = right[~right.index.duplicated(keep="last")].rename("fx")
    right = right.rename_axis("date").reset_index()
    left = pd.DataFrame({"date": pd.to_datetime(days)})
    merged = pd.merge_asof(left.sort_values("date"), right, on="date", direction="backward")
    out = pd.Series(merged["fx"].to_numpy(dtype=float), index=pd.DatetimeIndex(merged["date"]))
    return out.reindex(pd.DatetimeIndex(pd.to_datetime(days)))


def cny_from_usd(usd: pd.DataFrame, fx: pd.Series, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """A 股交易日 D 使用日期严格早于 D 的最后一根美元 K 线，再乘 D 当天或之前的中间价。

    返回列含 date、close（美元）、close_cny、data_hole。中间价还没有的日子 close_cny 为空。
    """
    frame = usd.sort_values("date").reset_index(drop=True)
    aligned, _meta = align_to_calendar(frame, pd.DatetimeIndex(pd.to_datetime(calendar)), True)
    if aligned.empty:
        return aligned.assign(close_cny=pd.Series(dtype=float))
    aligned = aligned.copy()
    aligned["date"] = pd.to_datetime(aligned["date"])
    rate = latest_on_or_before(fx, pd.DatetimeIndex(aligned["date"]))
    aligned["close_cny"] = aligned["close"].to_numpy(dtype=float) * rate.to_numpy(dtype=float)
    return aligned
