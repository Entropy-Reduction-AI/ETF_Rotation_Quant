"""2016-01-01 至 2026-09-30 的数据完整性。

只标坏点。不计算年化、累计、排名、IC，也不把单日涨跌加总。
分类留给 Manager，这里不填「必须修 / 可以接受 / 需要 Orchestrator」。
"""
from __future__ import annotations

from datetime import date, timedelta

WINDOW_START = "2016-01-01"
WINDOW_END = "2026-09-30"
ETF_MOVE = 0.20
OTC_MOVE = 0.30

FINDING_COLUMNS = (
    "code", "group", "series_kind", "source", "check", "date", "end_date",
    "n_days", "detail", "manager_class",
)


def in_window(day: str) -> bool:
    return WINDOW_START <= day <= WINDOW_END


def _shift(day: str, n: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=n)).isoformat()


def contiguous_ranges(days: list[str]) -> list[tuple[str, str, int]]:
    """把升序日期收成连续日历日区间。"""
    if not days:
        return []
    ranges = []
    start = prev = days[0]
    count = 1
    for day in days[1:]:
        if day == _shift(prev, 1):
            prev = day
            count += 1
            continue
        ranges.append((start, prev, count))
        start = prev = day
        count = 1
    ranges.append((start, prev, count))
    return ranges


def missing_ranges(calendar: list[str], present: set[str], first: str, last: str) -> list[tuple[str, str, int]]:
    """[first, last] 里、日历有而序列没有的日子。不看区间外面。"""
    absent = [day for day in calendar if first <= day <= last and day not in present]
    return contiguous_ranges(absent)


def null_runs(rows: list[dict]) -> list[tuple[str, str, int]]:
    """收盘为空的连续日历日。有收盘的日子把区间断开。"""
    days = []
    for row in rows:
        close = row.get("close")
        if close is None or close == "":
            days.append(row["date"])
    return contiguous_ranges(days)


def nonpositive_days(rows: list[dict]) -> list[str]:
    out = []
    for row in rows:
        close = row.get("close")
        if close is None or close == "":
            continue
        if float(close) <= 0:
            out.append(row["date"])
    return out


def _move(prev: float, close: float) -> float:
    return close / prev - 1.0


def large_move_days(rows: list[dict], threshold: float, events: set[str],
                    other: dict[str, float] | None = None,
                    explained: set[str] | None = None) -> list[dict]:
    """单日涨跌绝对值大于 threshold、且没有公司行为的日子。

    other 给后复权收盘时，原始缺口被后复权抹平的日子单独标，仍不算收益汇总。
    explained 是已经核对过的日子（例如核实过的涨停），不当成缺陷。
    """
    usable = []
    for row in rows:
        close = row.get("close")
        if close is None or close == "" or not (float(close) > 0):
            usable.append((row["date"], None))
        else:
            usable.append((row["date"], float(close)))
    found = []
    skip = set(events)
    if explained:
        skip |= set(explained)
    prev_day = None
    prev_close = None
    for day, close in usable:
        if close is None or prev_close is None:
            if close is not None:
                prev_day, prev_close = day, close
            continue
        move = _move(prev_close, close)
        if abs(move) > threshold and day not in skip:
            other_move = None
            if other and day in other and prev_day in other and other[prev_day] > 0:
                other_move = _move(other[prev_day], other[day])
            smoothed = other_move is not None and abs(other_move) <= threshold
            found.append({
                "date": day,
                "check": "large_move_hfq_smoothed" if smoothed else "large_move",
                "detail": _move_detail(move, other_move),
            })
        prev_day, prev_close = day, close
    return found


def _move_detail(move: float, other_move: float | None) -> str:
    text = f"move={move:.6f}"
    if other_move is not None:
        text += f" other_move={other_move:.6f}"
    return text


def _split_mult(event: dict) -> float | None:
    num = event.get("numerator")
    den = event.get("denominator")
    if num in (None, "") or den in (None, ""):
        return None
    num = float(num)
    den = float(den)
    if num <= 0 or den <= 0:
        return None
    return num / den


def adj_discontinuity(raw: list[dict], adjusted: list[dict], events: list[dict]) -> list[dict]:
    """事件日的后复权是否还留着缺口。

    只有分红时，对照原始收益加分红率。只有拆分时，后复权不得超过 ETF 阈值。
    同一天既有拆分又有分红时，分红金额按拆分后的每份计算：
    期望收益 = (原始收盘 + 每股分红) × (新份额/旧份额) / 前收 − 1。
    """
    raw_close = {row["date"]: float(row["close"]) for row in raw if row.get("close") and float(row["close"]) > 0}
    adj_close = {row["date"]: float(row["close"]) for row in adjusted if row.get("close") and float(row["close"]) > 0}
    raw_days = [day for day in sorted(raw_close) if day in adj_close]
    prev = {day: raw_days[i - 1] for i, day in enumerate(raw_days) if i}
    by_day: dict[str, list[dict]] = {}
    for event in events:
        by_day.setdefault(event["date"], []).append(event)
    found = []
    for day, day_events in by_day.items():
        if day not in prev or day not in adj_close:
            continue
        prev_day = prev[day]
        raw_ret = raw_close[day] / raw_close[prev_day] - 1.0
        adj_ret = adj_close[day] / adj_close[prev_day] - 1.0
        splits = [event for event in day_events if _split_mult(event) is not None and event["kind"] != "dividend"]
        divs = [event for event in day_events if event["kind"] == "dividend"]
        if splits and divs:
            mult = 1.0
            for event in splits:
                mult *= _split_mult(event)
            amount = sum(float(event.get("amount") or 0.0) for event in divs)
            expected = (raw_close[day] + amount) * mult / raw_close[prev_day] - 1.0
            if abs(adj_ret - expected) > 0.005:
                detail = f"split+dividend raw={raw_ret:.6f} adj={adj_ret:.6f} expected={expected:.6f}"
                found.append({"date": day, "check": "adj_discontinuous", "detail": detail})
            continue
        for event in day_events:
            kind = event["kind"]
            if kind == "dividend":
                amount = float(event.get("amount") or 0.0)
                expected = raw_ret + amount / raw_close[prev_day]
                bad = abs(adj_ret - expected) > 0.005
                detail = f"raw={raw_ret:.6f} adj={adj_ret:.6f} expected={expected:.6f}"
            else:
                bad = abs(adj_ret) > ETF_MOVE
                detail = f"raw={raw_ret:.6f} adj={adj_ret:.6f}"
            if bad:
                found.append({"date": day, "check": "adj_discontinuous", "detail": f"{kind} {detail}"})
    return found


def list_date_findings(code: str, list_date: str, first_bar: str) -> list[dict]:
    """上市日和第一根行情对不上时记一条。取不到上市日也记一条，分类交给 Manager。"""
    if not list_date or list_date in {"取不到", "未知"}:
        return [{"date": first_bar, "check": "list_date_unknown", "detail": "上市日登记为取不到"}]
    if len(list_date) != 10:
        return [{"date": first_bar, "check": "list_date_unknown", "detail": f"上市日不是日期：{list_date}"}]
    if first_bar < list_date:
        return [{"date": first_bar, "check": "starts_before_list_date", "detail": f"list_date={list_date}"}]
    if _shift(list_date, 15) < first_bar:
        return [{"date": first_bar, "check": "starts_after_list_date", "detail": f"list_date={list_date}"}]
    return []


def finding(code: str, group: str, series_kind: str, source: str, check: str, day: str,
            end: str = "", n_days: int = 1, detail: str = "") -> dict:
    return {
        "code": code,
        "group": group,
        "series_kind": series_kind,
        "source": source,
        "check": check,
        "date": day,
        "end_date": end or day,
        "n_days": str(n_days),
        "detail": detail,
        "manager_class": "",
    }


def scan_price_series(code: str, group: str, series_kind: str, source: str, rows: list[dict],
                       calendar: list[str] | None, threshold: float | None,
                       events: set[str] | None = None, other: dict[str, float] | None = None,
                       list_date: str | None = None, explained: set[str] | None = None) -> tuple[dict, list[dict]]:
    """一条序列在窗口内的起止和问题。calendar 为空表示没有外部交易日历，只查序列内部。"""
    window_rows = [row for row in rows if row.get("date") and in_window(row["date"])]
    present = {row["date"] for row in window_rows if row.get("close") not in (None, "") and float(row["close"]) > 0}
    inventory = {
        "code": code,
        "group": group,
        "series_kind": series_kind,
        "source": source,
        "first_date": min(present) if present else "",
        "last_date": max(present) if present else "",
        "rows": len(present),
    }
    found = []
    if not present:
        if any(row.get("date") and row["date"] < WINDOW_START for row in rows):
            last = max(row["date"] for row in rows if row.get("date"))
            found.append(finding(code, group, series_kind, source, "ended_before_window", last, detail="窗口内没有正收盘"))
        return inventory, found
    first, last = inventory["first_date"], inventory["last_date"]
    if last < WINDOW_END:
        found.append(finding(code, group, series_kind, source, "ended_before_cutoff", last,
                             detail=f"最后正收盘早于 {WINDOW_END}"))
    if calendar is not None:
        for start, end, n_days in missing_ranges(calendar, present, first, last):
            found.append(finding(code, group, series_kind, source, "missing_trade_days", start, end, n_days,
                                 "日历有、序列没有正收盘"))
    else:
        for start, end, n_days in _internal_holes(sorted(present), 12):
            found.append(finding(code, group, series_kind, source, "missing_trade_days", start, end, n_days,
                                 "序列内部日历间隔不少于 12 天"))
    for start, end, n_days in null_runs(window_rows):
        found.append(finding(code, group, series_kind, source, "null_close", start, end, n_days, "收盘为空"))
    for day in nonpositive_days(window_rows):
        found.append(finding(code, group, series_kind, source, "nonpositive_close", day, detail="收盘小于或等于 0"))
    if threshold is not None:
        ordered = [row for row in window_rows if row["date"] >= first and row["date"] <= last]
        for item in large_move_days(ordered, threshold, events or set(), other, explained):
            found.append(finding(code, group, series_kind, source, item["check"], item["date"], detail=item["detail"]))
    if list_date is not None:
        history = [row["date"] for row in rows if row.get("date") and row.get("close") not in (None, "")
                   and float(row["close"]) > 0]
        series_first = min(history) if history else first
        for item in list_date_findings(code, list_date, series_first):
            found.append(finding(code, group, series_kind, source, item["check"], item["date"], detail=item["detail"]))
    return inventory, found


def _internal_holes(days: list[str], minimum_gap: int) -> list[tuple[str, str, int]]:
    holes = []
    for prev, day in zip(days, days[1:]):
        span = (date.fromisoformat(day) - date.fromisoformat(prev)).days
        if span >= minimum_gap:
            start = _shift(prev, 1)
            end = _shift(day, -1)
            holes.append((start, end, span - 1))
    return holes


def count_findings(rows: list[dict]) -> dict[str, int]:
    """按检查项计数。不是收益汇总。"""
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["check"]] = counts.get(row["check"], 0) + 1
    return counts
