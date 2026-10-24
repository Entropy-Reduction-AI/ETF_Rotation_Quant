"""收盘价对齐、假跳空剔除、现金收益。发布日前的点位不进入收益。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.dividends import GAP_LIMIT
from src.indicators.build import align_to_calendar

OVERSEAS_SOURCES = {"nasdaq", "yahoo", "tencent_hk_index", "sge_daily"}
USD_CODES = {"XNDX", "^SP500TR"}


def total_return_close(bars: pd.DataFrame, dividends: dict[pd.Timestamp, float],
                       gap_limit: float = GAP_LIMIT) -> tuple[pd.Series, pd.DatetimeIndex]:
    """后复权路径：除息日加上 amount/prev_close。假跳空当日价格路径不跳，返回这些日期供信号剔除。"""
    frame = bars.sort_values("date")
    level = []
    index = []
    gaps = []
    prev_raw = None
    prev_level = None
    for record in frame.itertuples(index=False):
        raw = float(record.close) if record.close == record.close and record.close is not None else float("nan")
        day = pd.Timestamp(record.date)
        if not (raw > 0):
            continue
        if prev_raw is None:
            current = raw
        else:
            opened = float(record.open) if record.open == record.open and record.open is not None else float("nan")
            gap = opened / prev_raw - 1.0 if opened > 0 else 0.0
            if abs(gap) >= gap_limit:
                change = 0.0
                gaps.append(day)
            else:
                change = raw / prev_raw - 1.0 + dividends.get(day, 0.0)
            current = prev_level * (1.0 + change)
        level.append(current)
        index.append(day)
        prev_raw = raw
        prev_level = current
    return pd.Series(level, index=pd.DatetimeIndex(index), dtype=float), pd.DatetimeIndex(gaps)


def fresh_from_stale(stale: pd.Series, stale_limit: int) -> pd.Series:
    """连续平盘达到 stale_limit 的那天起不再有资格。价格本身仍保留。"""
    run = 0
    flags = []
    for flag in stale.astype(int).to_numpy():
        run = run + 1 if flag else 0
        flags.append(run < stale_limit)
    return pd.Series(flags, index=stale.index, dtype=bool)


def align_same_day(native: pd.Series, calendar: pd.DatetimeIndex, stale_limit: int
                   ) -> tuple[pd.Series, pd.Series]:
    """对齐到上交所日历。缺价日沿用最近收盘，最近 stale_limit 个交易日都没有打印则退出排名。"""
    on_calendar = native.reindex(calendar)
    observed = on_calendar.notna()
    level = on_calendar.ffill()
    recent = observed.astype(float).rolling(stale_limit, min_periods=1).sum()
    fresh = recent.gt(0) & level.notna()
    return level, fresh.fillna(False)


def align_overseas(bars: pd.DataFrame, calendar: pd.DatetimeIndex, stale_limit: int,
                   gap_days: pd.DatetimeIndex | None = None
                   ) -> tuple[pd.Series, pd.Series, pd.DatetimeIndex]:
    """港股、美股、上金所的收盘晚于或可能晚于 A 股 15:00，决策只用严格早于当日的 K 线。

    返回 (水平, 是否可排名, 信号里要剔除的 A 股交易日)。断档日仍保留最近收盘，避免复牌收益丢失。
    """
    frame = bars.sort_values("date").copy()
    for column in ("open", "high", "low"):
        if column not in frame.columns:
            frame[column] = frame["close"]
        frame[column] = frame[column].fillna(frame["close"])
    if "volume" not in frame.columns:
        frame["volume"] = 0.0
    frame["volume"] = frame["volume"].fillna(0.0)
    aligned, _meta = align_to_calendar(
        frame.loc[:, ["date", "open", "high", "low", "close", "volume"]], calendar, True)
    empty = pd.Series(np.nan, index=calendar, dtype=float)
    if aligned.empty:
        return empty, pd.Series(False, index=calendar), pd.DatetimeIndex([])
    dates = pd.DatetimeIndex(pd.to_datetime(aligned["date"]))
    level = pd.Series(aligned["close"].to_numpy(dtype=float), index=dates)
    fresh = fresh_from_stale(pd.Series(aligned["stale"].to_numpy(dtype=int), index=dates), stale_limit)
    level = level.reindex(calendar).ffill()
    fresh = fresh.reindex(calendar).fillna(False).astype(bool) & level.notna()
    return level, fresh, _consumed_gaps(frame["date"], calendar, gap_days)


def _consumed_gaps(native_dates, calendar: pd.DatetimeIndex,
                   gap_days: pd.DatetimeIndex | None) -> pd.DatetimeIndex:
    """A 股交易日 D 用的是日期严格早于 D 的那根 K 线。那根若是假跳空，D 的信号收益剔除。"""
    if gap_days is None or len(gap_days) == 0:
        return pd.DatetimeIndex([])
    native = pd.to_datetime(pd.Series(native_dates)).sort_values().to_numpy(dtype="datetime64[ns]")
    gap_set = set(pd.DatetimeIndex(gap_days).normalize())
    consumed = []
    for day in calendar:
        pos = int(np.searchsorted(native, np.datetime64(day), side="left")) - 1
        if pos < 0:
            continue
        if pd.Timestamp(native[pos]).normalize() in gap_set:
            consumed.append(pd.Timestamp(day))
    return pd.DatetimeIndex(consumed)


def signal_returns(level: pd.Series, gaps: pd.DatetimeIndex) -> pd.Series:
    """假跳空当日不进入 R 和波动。计价收益仍用价格路径上的 0。"""
    out = returns_from_level(level)
    if len(gaps):
        out.loc[out.index.isin(pd.DatetimeIndex(gaps))] = np.nan
    return out


def mask_publish(level: pd.Series, publish: pd.Timestamp | None) -> pd.Series:
    if publish is None:
        return level
    return level.where(level.index >= publish)


def returns_from_level(level: pd.Series) -> pd.Series:
    out = level.astype(float) / level.astype(float).shift(1) - 1.0
    out.name = "ret"
    return out


def lag_asof(events: pd.Series, calendar: pd.DatetimeIndex, lag: int) -> pd.Series:
    """每个交易日使用不晚于 T−lag 的最新数值。lag=0 表示不晚于当天。"""
    events = events.dropna().sort_index()
    events = events[~events.index.duplicated(keep="last")]
    out = np.full(len(calendar), np.nan)
    if events.empty:
        return pd.Series(out, index=calendar, dtype=float)
    published = events.index.to_numpy(dtype="datetime64[ns]")
    values = events.to_numpy(dtype=float)
    days = calendar.to_numpy(dtype="datetime64[ns]")
    if lag:
        usable = np.arange(len(calendar)) >= lag
        cutoffs = np.empty(len(calendar), dtype="datetime64[ns]")
        cutoffs[usable] = days[np.arange(len(calendar))[usable] - lag]
    else:
        usable = np.ones(len(calendar), dtype=bool)
        cutoffs = days
    found = np.full(len(calendar), -1)
    found[usable] = np.searchsorted(published, cutoffs[usable], side="right") - 1
    ok = found >= 0
    out[ok] = values[found[ok]]
    return pd.Series(out, index=calendar, dtype=float)


def dividend_yields(frame: pd.DataFrame) -> dict[pd.Timestamp, float]:
    out = {}
    if frame is None or frame.empty:
        return out
    for record in frame.itertuples(index=False):
        prev = float(record.prev_close)
        amount = float(record.amount)
        if prev > amount > 0:
            out[pd.Timestamp(record.ex_date)] = amount / prev
    return out
