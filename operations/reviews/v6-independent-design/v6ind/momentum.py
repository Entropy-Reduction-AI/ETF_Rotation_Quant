"""选人。去重、12−1、10 个月均线的字面实现。不计算分位票和把握。"""

from __future__ import annotations

from dataclasses import dataclass

from .calendar_math import add_months, momentum_anchors, shift_month


@dataclass(frozen=True)
class Score:
    name: str
    code: str
    tag: str
    score: float
    end_date: str
    end_level: float
    start_date: str
    start_level: float


def month_ends(rows: list[tuple[str, float]]) -> dict[str, tuple[str, float]]:
    out: dict[str, tuple[str, float]] = {}
    for date, close in rows:
        month = date[:7]
        prev = out.get(month)
        if prev is None or date >= prev[0]:
            out[month] = (date, close)
    return out


def score_ready(eligible_from: str) -> str:
    return add_months(eligible_from, 12)


def twelve_one(ends: dict[str, tuple[str, float]], signal_month: str) -> tuple[float, str, float, str, float] | None:
    end_month, start_month = momentum_anchors(signal_month)
    end = ends.get(end_month)
    start = ends.get(start_month)
    if end is None or start is None or start[1] == 0.0:
        return None
    return end[1] / start[1] - 1.0, end[0], end[1], start[0], start[1]


def ten_month_ma(ends: dict[str, tuple[str, float]], signal_month: str) -> tuple[str, float, float] | None:
    """Faber 10 个月均线：含信号月在内的 10 个月末点位。跌破 = 月末点位 < 均线。"""
    levels = []
    month = signal_month
    for _ in range(10):
        point = ends.get(month)
        if point is None:
            return None
        levels.append(point[1])
        month = shift_month(month, -1)
    close_date, close = ends[signal_month]
    return close_date, close, sum(levels) / 10.0


def dedupe_top(scores: list[Score], n: int = 3, *, positive_only: bool) -> tuple[list[Score], int, list[Score]]:
    pool = [row for row in scores if row.score > 0.0] if positive_only else list(scores)
    dropped: list[Score] = []
    chosen: list[Score] = []
    used: set[str] = set()
    for row in sorted(pool, key=lambda item: (-item.score, item.code)):
        if row.tag:
            if row.tag in used:
                dropped.append(row)
                continue
            used.add(row.tag)
        chosen.append(row)
        if len(chosen) == n:
            break
    return chosen, n - len(chosen), dropped
