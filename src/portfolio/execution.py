"""D5 执行规则：海外带宽与溢价、A 股月度对齐、执行日、股数取整。"""
from __future__ import annotations

import pandas as pd

from src.portfolio.config import AShareBook, FallbackError, NavRow

UNAVAILABLE = frozenset({"liquidated", "suspended", "halted"})
KNOWN_STATUS = UNAVAILABLE | {"normal"}

def _status(statuses: dict[str, str], code: str) -> str:
    state = statuses.get(code, "normal")
    if state not in KNOWN_STATUS:
        raise FallbackError(f"{code} 的交易状态 {state} 无法识别")
    return state


def resolve_execution_fund(book: AShareBook, statuses: dict[str, str] | None = None) -> tuple[str, str | None]:
    """主基金正常交易就用主基金。清盘、停牌或暂停交易时，取同指数里上市最早且仍正常交易的备选。"""
    statuses = statuses or {}
    state = _status(statuses, book.primary)
    if state not in UNAVAILABLE:
        return book.primary, None
    ranked = sorted(book.alternates, key=lambda alt: (alt.list_date, alt.code))
    for alt in ranked:
        if _status(statuses, alt.code) not in UNAVAILABLE:
            return alt.code, state
    raise FallbackError(f"{book.container} 主基金 {book.primary} 为 {state}，同指数没有仍正常交易的备选")


def published_cutoff(as_of: str | pd.Timestamp, trading_days: list, lag: int) -> pd.Timestamp:
    """决策日 T 只能使用日期 ≤ T−lag 个交易日的净值。lag 含 T 本身往回数。"""
    if lag < 1:
        raise FallbackError("净值公布滞后至少 1 个交易日")
    day = pd.Timestamp(as_of).normalize()
    days = sorted({pd.Timestamp(item).normalize() for item in trading_days if pd.Timestamp(item).normalize() <= day})
    if not days or days[-1] != day:
        raise FallbackError(f"{day.date()} 不是交易日，不能定溢价")
    if len(days) <= lag:
        raise FallbackError("交易日不够覆盖净值公布滞后")
    return days[-1 - lag]


def select_nav(rows: list[NavRow], code: str, cutoff: pd.Timestamp) -> NavRow:
    eligible = [row for row in rows if row.code == code and row.date.normalize() <= cutoff and row.unit_nav > 0]
    if not eligible:
        raise FallbackError(f"{code} 在 {cutoff.date()} 及之前没有已公布的单位净值")
    eligible.sort(key=lambda row: (row.date, row.fetched_at))
    return eligible[-1]


def _trading_days(trading_days: list) -> list[pd.Timestamp]:
    return sorted({pd.Timestamp(item).normalize() for item in trading_days})


def a_share_session(as_of: str | pd.Timestamp, trading_days: list) -> bool:
    """A 股腿只在每月第一个交易日对齐。月末出信号，当天不再调一次。"""
    day = pd.Timestamp(as_of).normalize()
    month = [item for item in _trading_days(trading_days) if item.to_period("M") == day.to_period("M")]
    if day not in month:
        raise FallbackError(f"{day.date()} 不在交易日历这个月里")
    return day == month[0]


def next_trading_day(day: str | pd.Timestamp, trading_days: list) -> pd.Timestamp:
    """决策日的下一交易日。中间的休市日跳过。"""
    current = pd.Timestamp(day).normalize()
    days = _trading_days(trading_days)
    if current not in days:
        raise FallbackError(f"{current.date()} 不是交易日")
    later = [item for item in days if item > current]
    if not later:
        raise FallbackError(f"{current.date()} 之后没有交易日")
    return later[0]


def schedule_execution(decision: str | pd.Timestamp, trading_days: list) -> dict:
    """月末（或任一决策日）决定，下一交易日执行。A 股是否对齐看执行日是不是该月第一个交易日。"""
    decision_ts = pd.Timestamp(decision).normalize()
    execution = next_trading_day(decision_ts, trading_days)
    return {
        "decision_date": decision_ts,
        "execution_date": execution,
        "a_share_due": a_share_session(execution, trading_days),
    }


def _whole_shares(value) -> int:
    number = float(value)
    if abs(number - round(number)) > 1e-6:
        raise FallbackError("持仓股数必须是整数")
    return int(round(number))


def _price(prices: dict[str, float], code: str) -> float:
    if code not in prices:
        raise FallbackError(f"{code} 没有决策日收盘价")
    price = float(prices[code])
    if price <= 0:
        raise FallbackError(f"{code} 的收盘价必须是正数")
    return price


def _lot_floor(value: float, price: float, lot: int) -> int:
    if value <= 0:
        return 0
    return int(value / price / lot) * lot


def _market_value(shares: dict[str, int], prices: dict[str, float], codes: list[str]) -> float:
    total = 0.0
    for code in codes:
        held = shares.get(code, 0)
        if held:
            total += held * _price(prices, code)
    return total


def _sell_down(shares: dict[str, int], prices: dict[str, float], premiums: dict[str, float],
               target_value: float, lot: int) -> dict[str, int]:
    """从溢价最高的持仓开始卖，卖到市值不再高于目标。下一手会卖穿目标时停。"""
    out = dict(shares)

    def total() -> float:
        return sum(out[code] * prices[code] for code in out if out[code])

    while total() > target_value + 1e-8:
        held = [code for code, count in out.items() if count > 0]
        if not held:
            break
        held.sort(key=lambda code: (-premiums[code], code))
        code = held[0]
        step = lot if out[code] >= lot else out[code]
        if step <= 0 or total() - step * prices[code] < target_value - 1e-8:
            break
        out[code] -= step
    return out


def _outside_band(actual: float, target: float, band: float) -> bool:
    """偏离超过 band。用百分点比较，刚好等于带宽不算超过。"""
    return round(abs(actual - target) * 100, 6) > round(band * 100, 6)


def _over_cap(premium: float, cap: float) -> bool:
    return round(premium, 8) > round(cap, 8)


def _unique(items: list[str]) -> list[str]:
    out = []
    for item in items:
        if item not in out:
            out.append(item)
    return out
