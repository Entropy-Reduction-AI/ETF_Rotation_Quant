"""日期与 12−1 锚点。公式按规范 §1.2 第 57 行括号内的字面定义。"""

from __future__ import annotations

import datetime as dt


def shift_month(ym: str, k: int) -> str:
    year, month = map(int, ym.split("-"))
    index = year * 12 + (month - 1) + k
    year2, month0 = divmod(index, 12)
    return f"{year2:04d}-{month0 + 1:02d}"


def add_months(iso: str, n: int) -> str:
    year, month, day = map(int, iso.split("-"))
    index = year * 12 + (month - 1) + n
    year2, month0 = divmod(index, 12)
    month2 = month0 + 1
    if month2 == 12:
        next_month = dt.date(year2 + 1, 1, 1)
    else:
        next_month = dt.date(year2, month2 + 1, 1)
    last = (next_month - dt.timedelta(days=1)).day
    return f"{year2:04d}-{month2:02d}-{min(day, last):02d}"


def momentum_anchors(signal_month: str) -> tuple[str, str]:
    """信号月 T 的 12−1：上月末 T−1，再往前 12 个月的月末 T−13。"""
    end_month = shift_month(signal_month, -1)
    start_month = shift_month(signal_month, -13)
    return end_month, start_month
