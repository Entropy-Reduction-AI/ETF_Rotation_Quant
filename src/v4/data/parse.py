"""把公开接口的原文解析成行。不做收益、不复权。"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from src.data.sources import _f, _finish, _row


def _num(value) -> str:
    if value is None or value == "":
        return ""
    return format(float(value), ".10g")


def series_sha256(rows: list[dict], columns: tuple[str, ...]) -> str:
    """入库后按日期升序重读，再用这个函数复算。空值留空，浮点用 .10g。"""
    lines = []
    for row in rows:
        lines.append(",".join([row["date"] if col == "date" else _num(row.get(col)) for col in columns]))
    text = "\n".join(lines) + ("\n" if lines else "")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def bar_sha256(rows: list[dict]) -> str:
    return series_sha256(rows, ("date", "open", "high", "low", "close", "volume"))


def _zone(name: str | None):
    try:
        return ZoneInfo(name) if name else None
    except Exception:  # noqa: BLE001 — 时区名无效时退回 gmtoffset
        return None


def _session_date(ts: int, tz, offset: int) -> str:
    if tz is not None:
        return datetime.fromtimestamp(int(ts), tz).date().isoformat()
    return (datetime.fromtimestamp(int(ts), timezone.utc)).date().isoformat() if not offset else (
        datetime.fromtimestamp(int(ts) + int(offset), timezone.utc).date().isoformat()
    )


def parse_yahoo_chart(payload: dict, start: date, end: date) -> dict:
    """未复权 OHLC，外加 events 里的分红和拆分。不使用 adjclose。"""
    result = ((payload or {}).get("chart") or {}).get("result") or []
    if not result:
        err = ((payload or {}).get("chart") or {}).get("error")
        raise ValueError(f"yahoo chart 没有结果: {err}")
    node = result[0]
    meta = node.get("meta") or {}
    stamps = node.get("timestamp") or []
    quote = ((node.get("indicators") or {}).get("quote") or [{}])[0]
    tz = _zone(meta.get("exchangeTimezoneName"))
    offset = int(meta.get("gmtoffset") or 0)

    def col(key):
        values = quote.get(key) or []
        return values if len(values) == len(stamps) else [None] * len(stamps)

    opened, high, low, close, volume = col("open"), col("high"), col("low"), col("close"), col("volume")
    bars = []
    for i, ts in enumerate(stamps):
        row = _row(_session_date(ts, tz, offset), opened[i], high[i], low[i], close[i], volume[i])
        if row and row["close"] > 0:
            bars.append(row)
    events = node.get("events") or {}
    dividends = _events(events.get("dividends"), tz, offset, start, end, kind="dividend")
    splits = _events(events.get("splits"), tz, offset, start, end, kind="split")
    return {
        "name": meta.get("longName") or meta.get("shortName") or "",
        "currency": meta.get("currency") or "",
        "bars": _finish(bars, start, end),
        "dividends": dividends,
        "splits": splits,
    }


def _events(raw, tz, offset: int, start: date, end: date, *, kind: str) -> list[dict]:
    items = []
    if isinstance(raw, dict):
        seq = list(raw.values())
    elif isinstance(raw, list):
        seq = raw
    else:
        seq = []
    lo, hi = start.isoformat(), end.isoformat()
    for item in seq:
        if not isinstance(item, dict) or item.get("date") is None:
            continue
        day = _session_date(item["date"], tz, offset)
        if not lo <= day <= hi:
            continue
        if kind == "dividend":
            amount = _f(item.get("amount"))
            if amount is None or amount <= 0:
                continue
            items.append({"date": day, "amount": amount})
        else:
            num = _f(item.get("numerator"))
            den = _f(item.get("denominator"))
            ratio = str(item.get("splitRatio") or "")
            if num is None or den is None or den == 0:
                continue
            items.append({"date": day, "numerator": num, "denominator": den, "ratio": ratio})
    items.sort(key=lambda r: r["date"])
    dedup = {}
    for item in items:
        dedup[item["date"]] = item
    return [dedup[day] for day in sorted(dedup)]


def parse_chinamoney(payload: dict, pair: str, start: date, end: date) -> list[dict]:
    """CcprHisNew。只取请求的那一个货币对，中间价写入 close。"""
    data = (payload or {}).get("data") or {}
    wanted = data.get("searchlist") or []
    if wanted != [pair]:
        raise ValueError(f"chinamoney searchlist={wanted!r}，不是 {pair}")
    rows = []
    for rec in (payload or {}).get("records") or []:
        values = rec.get("values") or []
        if len(values) != 1:
            raise ValueError(f"{pair} {rec.get('date')} values 长度 {len(values)}")
        close = _f(values[0])
        day = str(rec.get("date") or "")
        if close is None or close <= 0 or len(day) != 10:
            continue
        rows.append({"date": day, "open": None, "high": None, "low": None, "close": close,
                     "volume": None, "amount": None})
    return _finish(rows, start, end)
