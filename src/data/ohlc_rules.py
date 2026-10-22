"""I-28 / I-29：开高低换算与 A 股缺口的机械处理。只看日期和价格是否存在，不看收益。"""
from __future__ import annotations

import math

SHORT_GAP = 3


def is_positive(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _missing(value) -> bool:
    return value is None


def ohlc_state(row: dict) -> str:
    """ok：开高低收都是正的有限数。missing：有字段空着。invalid：字段在，但不是正的有限数。"""
    close = row.get("close")
    if _missing(close):
        return "missing"
    if not is_positive(close):
        return "invalid"
    missing = False
    for key in ("open", "high", "low"):
        value = row.get(key)
        if _missing(value):
            missing = True
            continue
        if not is_positive(value):
            return "invalid"
    return "missing" if missing else "ok"


def price_book(bar_rows: list[dict], supplement_rows: list[dict]) -> dict[str, dict]:
    """同一天优先用 bars 里已经为正的收盘；开高低用 bars 自己的，否则用补充表。"""
    book: dict[str, dict] = {}
    for row in supplement_rows:
        book[row["date"]] = {"date": row["date"], "open": row.get("open"), "high": row.get("high"),
                             "low": row.get("low"), "close": row.get("close")}
    for row in bar_rows:
        current = book.get(row["date"], {"date": row["date"]})
        if is_positive(row.get("close")):
            current["close"] = row["close"]
        if ohlc_state(row) == "ok":
            current["open"], current["high"], current["low"] = row["open"], row["high"], row["low"]
        book[row["date"]] = current
    return book


def apply_i28(rows: list[dict], prices: dict[str, dict]) -> tuple[list[dict], str]:
    """研究序列缺开高低时，用价格版本同日开高低乘 k。k = 研究收盘 / 价格收盘。收盘保留研究序列原值。"""
    used = False
    out = []
    for row in rows:
        item = dict(row)
        if ohlc_state(item) == "missing" and is_positive(item.get("close")):
            price = prices.get(item["date"])
            if price and ohlc_state(price) == "ok":
                scale = item["close"] / price["close"]
                for key in ("open", "high", "low"):
                    item[key] = scale * price[key]
                used = True
        out.append(item)
    return out, ("price_version" if used else "self")


def _jan1(day: str) -> bool:
    return day.endswith("-01-01")


def decide_i29(real_dates: list[str], calendar: list[str], end: str) -> dict:
    """A 股路由的窗口与占位。1 月 1 日占位不算真实 K 线。终点上的缺口不进 V1，哪怕只有 1 天。"""
    cal = [day for day in calendar if day <= end]
    real = sorted({day for day in real_dates if day in set(cal) and not _jan1(day)})
    result = {"enters_v1": False, "blocks_pool": False, "window_start": None,
              "placeholder_runs": [], "reason": ""}
    if not cal:
        result["blocks_pool"] = True
        result["reason"] = "没有交易日"
        return result
    if not real:
        result["reason"] = "I-29(4) 没有真实 K 线，缺口延伸到终点"
        return result
    index = {day: i for i, day in enumerate(cal)}
    present = set(real)
    gaps = []
    cursor = index[real[0]]
    last = len(cal) - 1
    while cursor <= last:
        if cal[cursor] not in present:
            stop = cursor
            while stop <= last and cal[stop] not in present:
                stop += 1
            gaps.append((cal[cursor], cal[stop - 1], stop - cursor))
            cursor = stop
        else:
            cursor += 1
    terminal = [gap for gap in gaps if gap[1] == cal[-1]]
    if terminal:
        first, final, rows = terminal[0]
        result["reason"] = f"I-29(4) 缺口 {first}→{final}（{rows} 个交易日）延伸到终点"
        return result
    long = [gap for gap in gaps if gap[2] > SHORT_GAP]
    if long:
        start = cal[index[long[-1][1]] + 1]
        reason = "I-29(3)"
    else:
        start = real[0]
        reason = "I-29(1)"
    result.update(enters_v1=True, window_start=start, reason=reason, placeholder_runs=[
        {"first": first, "last": final, "rows": rows, "trailing": False, "hole_rows": rows}
        for first, final, rows in gaps if first >= start
    ])
    return result
