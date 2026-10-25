"""§6① 随机起点。起点月算第 1 个月，窗口可以重叠。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.v3.engine.book import DESIGN_END

from .common import EvalError, annualized_return, require_design_period

SPANS = (36, 60)
FRACTION_60 = 0.60


def _month(stamp) -> tuple[int, int]:
    day = pd.Timestamp(stamp)
    return int(day.year), int(day.month)


def _add_months(year: int, month: int, offset: int) -> tuple[int, int]:
    zero = year * 12 + (month - 1) + offset
    return zero // 12, zero % 12 + 1


def month_bounds(calendar) -> dict[tuple[int, int], tuple[pd.Timestamp, pd.Timestamp]]:
    """每个自然月在这条交易日序列里的第一天和最后一天。"""
    index = pd.DatetimeIndex(pd.to_datetime(calendar)).sort_values().unique()
    bounds: dict[tuple[int, int], tuple[pd.Timestamp, pd.Timestamp]] = {}
    for day in index:
        key = _month(day)
        stamp = pd.Timestamp(day)
        if key not in bounds:
            bounds[key] = (stamp, stamp)
        else:
            bounds[key] = (bounds[key][0], stamp)
    return bounds


def rolling_windows(calendar, months: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """起点是该月第一个交易日，终点是第 `months` 个月的最后一个交易日。

    中间任何一个自然月在交易日序列里不存在，这个窗口就不要。
    终点晚于 2015-12-31 的窗口不打开。
    """
    if months not in SPANS:
        raise EvalError("随机起点只接受 36 或 60 个月")
    bounds = month_bounds(calendar)
    windows = []
    for year, month in sorted(bounds):
        keys = [_add_months(year, month, offset) for offset in range(months)]
        if any(key not in bounds for key in keys):
            continue
        end = bounds[keys[-1]][1]
        if end > DESIGN_END:
            continue
        windows.append((bounds[(year, month)][0], end))
    return windows


def _records(strategy: pd.Series, benchmark: pd.Series, calendar, months: int) -> list[dict]:
    sessions = pd.DatetimeIndex(pd.to_datetime(calendar)).sort_values().unique()
    rows = []
    for start, end in rolling_windows(sessions, months):
        days = sessions[(sessions >= start) & (sessions <= end)]
        left = strategy.reindex(days)
        right = benchmark.reindex(days)
        if left.isna().any() or right.isna().any():
            continue
        ann_strategy = annualized_return(left.to_numpy())
        ann_benchmark = annualized_return(right.to_numpy())
        rows.append({
            "start": pd.Timestamp(start),
            "end": pd.Timestamp(end),
            "months": months,
            "n": int(len(days)),
            "ann_strategy": ann_strategy,
            "ann_benchmark": ann_benchmark,
            "excess": ann_strategy - ann_benchmark,
        })
    return rows


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.median(np.asarray(values, dtype=float)))


def engineering_check_1(median_36, median_60, fraction_60) -> bool:
    """60 个月中位超额 > 0，且至少 60% 的窗口超额 > 0，并且 36 个月中位超额 > 0。"""
    if median_36 is None or median_60 is None or fraction_60 is None:
        return False
    return bool(median_60 > 0.0 and fraction_60 >= FRACTION_60 and median_36 > 0.0)


def criterion_1(strategy, benchmark, calendar) -> dict:
    """相对 BM-主 的随机起点超额。`engineering_check` 不是正式通过。"""
    require_design_period(pd.Series(strategy).index)
    require_design_period(pd.Series(benchmark).index)
    left = pd.Series(strategy, dtype=float).sort_index()
    right = pd.Series(benchmark, dtype=float).sort_index()
    windows_36 = _records(left, right, calendar, 36)
    windows_60 = _records(left, right, calendar, 60)
    excess_36 = [row["excess"] for row in windows_36]
    excess_60 = [row["excess"] for row in windows_60]
    fraction = None if not excess_60 else float(np.mean(np.asarray(excess_60) > 0.0))
    median_36 = _median(excess_36)
    median_60 = _median(excess_60)
    return {
        "windows_36": windows_36,
        "windows_60": windows_60,
        "n_36": len(windows_36),
        "n_60": len(windows_60),
        "median_36": median_36,
        "median_60": median_60,
        "fraction_positive_60": fraction,
        "engineering_check": engineering_check_1(median_36, median_60, fraction),
        "formal_pass": None,
    }
