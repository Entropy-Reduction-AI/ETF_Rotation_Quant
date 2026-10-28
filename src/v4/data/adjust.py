"""后复权与汇率补齐。只生成新序列，不改调用方传入的原始收盘。

后复权：首日收盘等于原始收盘，之后按分红再投资连乘。
拆分已经体现在收盘价里时，不再乘拆分比，避免调两次。
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

# 基金净值时间戳的日历日按北京时间。上海与台北都是 UTC+8，没有夏令时。
_BEIJING = timezone(timedelta(hours=8))


def split_price_ratio(numerator: float, denominator: float) -> float:
    """未复权时，拆分日收盘相对前收应接近的倍数。2:1 时价格约剩一半。"""
    if numerator <= 0 or denominator <= 0:
        raise ValueError(f"拆分比必须为正：{numerator}:{denominator}")
    return denominator / numerator


def split_already_in_close(prev_close: float, close: float, numerator: float, denominator: float) -> bool:
    """相邻收盘更接近 1，还是更接近未复权应有的拆分倍数。"""
    if prev_close <= 0 or close <= 0:
        raise ValueError("收盘必须为正")
    actual = close / prev_close
    untreated = split_price_ratio(numerator, denominator)
    return abs(math.log(actual)) + 1e-12 < abs(math.log(actual / untreated))


def _index(rows: list[dict], key: str = "date") -> dict[str, dict]:
    out = {}
    for row in rows:
        out[row[key]] = row
    return out


def backward_total_return(bars: list[dict], dividends: list[dict], splits: list[dict], *,
                          splits_in_price: bool) -> list[dict]:
    """分红再投资的后复权。bars 按日期升序，只读。

    splits_in_price 为真时拆分比不参与计算。返回新的 OHLC，成交量保持原样。
    当日复权收盘 / 原始收盘，用来缩放开高低。
    """
    div = {}
    for row in dividends:
        amount = float(row["amount"])
        if amount <= 0:
            raise ValueError(f"分红必须为正：{row}")
        div[row["date"]] = amount
    factor = {}
    if not splits_in_price:
        for row in splits:
            factor[row["date"]] = float(row["numerator"]) / float(row["denominator"])
    out = []
    prev_raw = None
    prev_level = None
    for bar in bars:
        raw = bar.get("close")
        if raw is None or not (float(raw) > 0):
            out.append(_scaled(bar, None))
            continue
        raw = float(raw)
        if prev_level is None:
            level = raw
        else:
            mult = factor.get(bar["date"], 1.0)
            change = (raw / prev_raw) * mult - 1.0 + div.get(bar["date"], 0.0) / prev_raw
            level = prev_level * (1.0 + change)
        out.append(_scaled(bar, level / raw, level))
        prev_raw = raw
        prev_level = level
    return out


def _scaled(bar: dict, scale: float | None, level: float | None = None) -> dict:
    def px(name):
        if scale is None:
            return None
        value = bar.get(name)
        if value is None or value == "":
            return None
        return float(value) * scale

    close = level if level is not None else px("close")
    return {
        "date": bar["date"],
        "open": px("open"),
        "high": px("high"),
        "low": px("low"),
        "close": close,
        "volume": bar.get("volume"),
    }


def fill_backward(known: list[tuple[str, float]], needed: list[str], window: int = 20) -> list[dict]:
    """已知点保留。更早的缺口用其后最近 window 个已知收盘的平均值补上，并标 filled。

    不改已知点，也不向最后一个已知点之后延伸。
    """
    if window < 1:
        raise ValueError("window 至少为 1")
    points = sorted((day, float(close)) for day, close in known if close is not None and float(close) > 0)
    if not points:
        return []
    have = {day: close for day, close in points}
    days = [day for day, _ in points]
    closes = [close for _, close in points]
    out = []
    for day in sorted(set(needed) | set(have)):
        if day in have:
            out.append({"date": day, "close": have[day], "filled": 0})
            continue
        if day >= days[-1]:
            continue
        nxt = _first_after(days, day)
        sample = closes[nxt:nxt + window]
        if not sample:
            continue
        out.append({"date": day, "close": sum(sample) / len(sample), "filled": 1})
    out.sort(key=lambda row: row["date"])
    return out


def _first_after(days: list[str], day: str) -> int:
    lo, hi = 0, len(days)
    while lo < hi:
        mid = (lo + hi) // 2
        if days[mid] <= day:
            lo = mid + 1
        else:
            hi = mid
    return lo


def cny_per_hkd(usd_cny: float, hkd_per_usd: float) -> float:
    """1 港元兑人民币。港币兑美元用「1 美元兑多少港元」。"""
    if usd_cny <= 0 or hkd_per_usd <= 0:
        raise ValueError("汇率必须为正")
    return usd_cny / hkd_per_usd


def safe_quote_to_cny(quoted_per_hundred: float) -> float:
    """外管局表是 100 外币兑人民币。"""
    if quoted_per_hundred <= 0:
        raise ValueError("中间价必须为正")
    return quoted_per_hundred / 100.0


def ms_to_date(ms: int) -> str:
    """东财净值时间戳按北京时间取日历日。"""
    return datetime.fromtimestamp(ms / 1000, _BEIJING).date().isoformat()


def compound_adjusted_nav(points: list[dict]) -> list[dict]:
    """用公布的日增长率连乘得到复权净值。没有日增长率时，用单位净值加分红回退。

    points: date, unit_nav, accum_nav, equity_return（百分数，可空）, dividend（可空）。
    """
    out = []
    level = None
    prev_unit = None
    for point in points:
        unit = point.get("unit_nav")
        ret = point.get("equity_return")
        dividend = float(point.get("dividend") or 0.0)
        if level is None:
            if unit is None or not (float(unit) > 0):
                continue
            level = float(unit)
        elif ret is not None and ret == ret:
            level = level * (1.0 + float(ret) / 100.0)
        elif prev_unit and unit is not None and float(prev_unit) > 0 and float(unit) > 0:
            level = level * (float(unit) + dividend) / float(prev_unit)
        else:
            prev_unit = float(unit) if unit not in (None, "") else prev_unit
            continue
        out.append({
            "date": point["date"],
            "unit_nav": None if unit is None else float(unit),
            "accum_nav": None if point.get("accum_nav") is None else float(point["accum_nav"]),
            "close": level,
        })
        if unit is not None and float(unit) > 0:
            prev_unit = float(unit)
    return out
