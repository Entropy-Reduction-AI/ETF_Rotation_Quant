"""§2 执行层。设计期主判是指数池，这里只把规则写成可测的函数，不读基金行情。"""

from __future__ import annotations

import math


def deviation(premium_today: float, trailing_median: float) -> float:
    """当日溢价减去过去 60 个交易日溢价的中位数，单位与输入相同（百分点）。"""
    return premium_today - trailing_median


def choose_listing(rows: list[dict]) -> str | None:
    """同一指数的场内基金里，溢价偏离最小、且不超过 5 个点的一只。

    rows: {"id", "deviation", "held"}。已持有的不因为溢价被换掉。
    没有可买的新基金时返回 None，调用方按 §2 交给下一名候选。
    """
    held = [row for row in rows if row.get("held")]
    if held:
        return str(held[0]["id"])
    fresh = [row for row in rows if row["deviation"] <= 5.0 and not math.isnan(row["deviation"])]
    if not fresh:
        return None
    fresh.sort(key=lambda row: (row["deviation"], str(row["id"])))
    return str(fresh[0]["id"])
