"""计划成交日是不是收盘涨停、收盘跌停，或当天没有价格。

只做统计。不改 `simulate_path` 的成交假设，v4 再决定要不要顺延。

设计期截止 2015-12-31。这一段里本池 ETF 的涨跌停是前收的 ±10%，价格四舍五入到 0.001 元
（ROUND_HALF_UP）。创业板个股改 ±20% 是 2020-08-24，科创板 2019 年才交易，都不在本段。
比较的是该代码自己的原始收盘，不是前向沿用之后的水平，也不是后复权价。
"""
from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP

DESIGN_END = "2015-12-31"
LIMIT_RATIO = Decimal("0.10")
TICK = Decimal("0.001")
MARKS = ("close_limit_up", "close_limit_down", "no_price", "has_price")


def as_tick(price: float) -> Decimal:
    """把行情里的浮点收盘收成交易所的 0.001 元报价。"""
    return Decimal(str(price)).quantize(TICK, rounding=ROUND_HALF_UP)


def limit_prices(prev_close: float) -> tuple[Decimal, Decimal]:
    """返回 (涨停价, 跌停价)。prev_close 是上一笔原始收盘。"""
    prev = as_tick(prev_close)
    up = (prev * (1 + LIMIT_RATIO)).quantize(TICK, rounding=ROUND_HALF_UP)
    down = (prev * (1 - LIMIT_RATIO)).quantize(TICK, rounding=ROUND_HALF_UP)
    return up, down


def at_limits(prev_close: float | None, close: float | None) -> tuple[bool, bool]:
    """(收盘等于涨停价, 收盘等于跌停价)。没有价格或没有前收时都是否。"""
    if prev_close is None or close is None:
        return False, False
    if not math.isfinite(prev_close) or not math.isfinite(close):
        return False, False
    if prev_close <= 0.0 or close <= 0.0:
        return False, False
    up, down = limit_prices(prev_close)
    quoted = as_tick(close)
    return quoted == up, quoted == down


def quote_pair(series, day) -> tuple[float | None, float | None]:
    """该代码在 `day` 的 (前一笔原始收盘, 当日原始收盘)。

    当日没有正的有限收盘时，第二个值是 None。前收是该代码自己的上一笔，
    不是上一个上交所交易日，这样停牌复牌的涨跌停价跟交易所一致。
    """
    import pandas as pd

    stamp = pd.Timestamp(day).normalize()
    if series is None or len(series) == 0:
        return None, None
    close = None
    if stamp in series.index:
        value = series.loc[stamp]
        if hasattr(value, "iloc"):
            value = value.iloc[-1]
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = float("nan")
        if math.isfinite(number) and number > 0.0:
            close = number
    prev_index = series.index[series.index < stamp]
    prev = None
    if len(prev_index):
        value = series.loc[prev_index[-1]]
        if hasattr(value, "iloc"):
            value = value.iloc[-1]
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = float("nan")
        if math.isfinite(number) and number > 0.0:
            prev = number
    return prev, close


def mark_planned_fill(prev_close: float | None, close: float | None, side: str) -> str:
    """买入看收盘涨停，离场看收盘跌停。另一侧碰到板仍记 has_price。

    side 是 ``buy`` 或 ``exit``。没有正的有限收盘 → ``no_price``。
    有收盘但没有前收，无法判断板，记 ``has_price``。
    """
    if side not in {"buy", "exit"}:
        raise ValueError(side)
    if close is None or not math.isfinite(close) or close <= 0.0:
        return "no_price"
    at_up, at_down = at_limits(prev_close, close)
    if side == "buy" and at_up:
        return "close_limit_up"
    if side == "exit" and at_down:
        return "close_limit_down"
    return "has_price"
