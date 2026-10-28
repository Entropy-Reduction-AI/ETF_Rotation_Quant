"""D12-1 成交限制。开关关闭时引擎不调用这里。

收盘涨停的买单、收盘跌停的卖单、停牌或没有当日价格，当天不成交，顺延到下一次
能成交的交易日。涨跌停看原始收盘，不看后复权，也不看研究指数的全收益点位。

幅度按板块和日期，触发线是涨跌停幅度再减 0.5 个百分点
（±10% 用 ±9.5%，±20% 用 ±19.5%）。预注册草案 §4.5。

- 主板以及其余在 A 股挂牌的基金：±10%。
- 跟踪创业板的 ETF：2020-08-24 起 ±20%。深交所《创业板交易特别规定》第 2.9 条
  当日施行，159915 在同日公布的 20% 基金名单里。此前 ±10%。
- 跟踪科创板的 ETF：2020-08-21 起 ±20%。上证发〔2020〕61 号自发布之日起实施。
  此前 ±10%。科创板股票自身从 2019-07-22 起就是 ±20%，基金条款以这份通知为准。
- 没有 A 股涨跌停的品种：不设板。只有停牌或无当日价才不成交。
- U-指数里的 A 股容器，没有对应 ETF 时按 ±10%。

指数池用对应 ETF 的板块和该 ETF 的原始收盘。报价四舍五入到 0.001 元，
与 `src.v3.diag.limit_close` 相同。开关关闭时引擎不调用这里。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd

from src.v3.diag.limit_close import as_tick

TICK = Decimal("0.001")
BAND_10 = Decimal("0.10")
BAND_20 = Decimal("0.20")
CHINEXT_20 = pd.Timestamp("2020-08-24")
STAR_20 = pd.Timestamp("2020-08-21")


@dataclass(frozen=True)
class FillQuote:
    """一只可交易工具的原始收盘。索引是它自己的打印日，缺日不前向填充。

    `board_by_day` 只在载体当天不是 A 股场内 ETF 时使用（场外、美股、港股没有涨跌停）。
    不传时整天用 `board`。
    """

    close: pd.Series
    board: str
    board_by_day: pd.Series | None = None


_A_SHARE = frozenset({"A股宽基", "A股行业", "A股红利"})
# 草案 §4.5：达到「涨跌停幅度减 0.5 个百分点」就视为涨停或跌停。
LIMIT_BUFFER = Decimal("0.005")


def fill_board_for(track: str, code: str, asset_class: str = "") -> str:
    """没有 A 股 ETF 的 A 股容器按主板 ±10%。美股、港股、场外不是 A 股代码时不设板。"""
    board = board_of(track, code)
    if board == "none" and asset_class in _A_SHARE:
        return "main"
    return board


def board_of(track: str, code: str) -> str:
    """由跟踪标的文字和挂牌代码决定板块。指数池传入的是对应 ETF，不是研究指数代码。"""
    text = track or ""
    if "科创" in text:
        return "star"
    if "创业板" in text:
        return "chinext"
    if str(code).isdigit() and len(str(code)) == 6:
        return "main"
    return "none"


def limit_ratio(board: str, day) -> Decimal | None:
    """返回涨跌停幅度。`none` 表示这个品种没有 A 股涨跌停。"""
    stamp = pd.Timestamp(day).normalize()
    if board == "main":
        return BAND_10
    if board == "chinext":
        return BAND_20 if stamp >= CHINEXT_20 else BAND_10
    if board == "star":
        return BAND_20 if stamp >= STAR_20 else BAND_10
    if board == "none":
        return None
    raise ValueError(board)


def limit_prices(prev_close: float, ratio: Decimal) -> tuple[Decimal, Decimal]:
    prev = as_tick(prev_close)
    up = (prev * (1 + ratio)).quantize(TICK, rounding=ROUND_HALF_UP)
    down = (prev * (1 - ratio)).quantize(TICK, rounding=ROUND_HALF_UP)
    return up, down


def _positive(value) -> float | None:
    if hasattr(value, "iloc"):
        value = value.iloc[-1]
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0.0:
        return None
    return number


def previous_and_close(series: pd.Series | None, day) -> tuple[float | None, float | None]:
    """(上一笔原始收盘, 当日原始收盘)。当日没打印时第二个值是 None。

    上一笔是这只代码自己的上一笔成交，不是上一个上交所交易日。
    """
    if series is None or len(series) == 0:
        return None, None
    stamp = pd.Timestamp(day).normalize()
    close = _positive(series.loc[stamp]) if stamp in series.index else None
    earlier = series.loc[series.index < stamp]
    prev = None
    if len(earlier):
        for value in reversed(earlier.to_numpy(dtype=float).tolist()):
            prev = _positive(value)
            if prev is not None:
                break
    return prev, close


def blocked(prev_close: float | None, close: float | None, side: str, ratio: Decimal | None) -> bool:
    """True 表示这一侧当天不能成交。没有价格一律不能成交。没有涨跌停的品种只卡无价。"""
    if side not in {"buy", "sell"}:
        raise ValueError(side)
    if close is None:
        return True
    if ratio is None or prev_close is None:
        return False
    threshold = ratio - LIMIT_BUFFER
    if threshold <= 0:
        return False
    move = (as_tick(close) - as_tick(prev_close)) / as_tick(prev_close)
    if side == "buy" and move >= threshold:
        return True
    if side == "sell" and move <= -threshold:
        return True
    return False


def session_tradable(quotes: dict[str, FillQuote] | None, day, names: list[str]) -> dict[str, tuple[bool, bool]]:
    """每个名字返回 (能买, 能卖)。没有报价就两边都不能成交。"""
    out: dict[str, tuple[bool, bool]] = {}
    stamp = pd.Timestamp(day).normalize()
    for name in names:
        quote = None if quotes is None else quotes.get(name)
        if quote is None:
            out[name] = (False, False)
            continue
        prev, close = previous_and_close(quote.close, stamp)
        board_name = quote.board
        by_day = quote.board_by_day
        if by_day is not None and stamp in by_day.index:
            value = by_day.loc[stamp]
            if value == value and str(value):
                board_name = str(value)
        ratio = limit_ratio(board_name, stamp)
        out[name] = (
            not blocked(prev, close, "buy", ratio),
            not blocked(prev, close, "sell", ratio),
        )
    return out


def legs_clear(before: dict[str, float], after: dict[str, float], tradable: dict[str, tuple[bool, bool]],
               cash_id: str, trade_eps: float) -> bool:
    """目标相对漂移后的权重，每一条需要加仓或减仓的腿当天都能成交。"""
    for name in set(before) | set(after):
        if name == cash_id:
            continue
        delta = float(after.get(name, 0.0)) - float(before.get(name, 0.0))
        if abs(delta) <= trade_eps:
            continue
        can_buy, can_sell = tradable.get(name, (False, False))
        if delta > 0.0 and not can_buy:
            return False
        if delta < 0.0 and not can_sell:
            return False
    return True


def executable_weights(current: dict[str, float], target: dict[str, float],
                       tradable: dict[str, tuple[bool, bool]], cash_id: str,
                       trade_eps: float) -> dict[str, float]:
    """成交不了的腿留在漂移后的权重。买单如果会把权重总和顶过 1，按剩余预算缩小。

    现金是残差。调用方只在 `legs_clear` 为假时使用；全部能成交时仍走原来的整笔换仓。
    """
    names = [name for name in set(current) | set(target) if name != cash_id]
    locked: dict[str, float] = {}
    buys: dict[str, float] = {}
    stays: dict[str, float] = {}
    for name in names:
        cur = float(current.get(name, 0.0))
        des = float(target.get(name, 0.0))
        can_buy, can_sell = tradable.get(name, (False, False))
        if des > cur + trade_eps and not can_buy:
            locked[name] = cur
        elif des < cur - trade_eps and not can_sell:
            locked[name] = cur
        elif des > cur + trade_eps:
            buys[name] = des
        else:
            stays[name] = des
    budget = 1.0 - sum(locked.values()) - sum(stays.values())
    if budget < 0.0:
        budget = 0.0
    raw = sum(buys.values())
    scale = 1.0 if raw <= budget + trade_eps or raw == 0.0 else budget / raw
    out = {name: 0.0 for name in names}
    out.update(locked)
    out.update(stays)
    for name, weight in buys.items():
        out[name] = weight * scale
    out[cash_id] = 1.0 - sum(out[name] for name in names)
    return out


def quotes_from_market(market) -> dict[str, FillQuote]:
    """把行情对象上的原始收盘收成成交判断用的报价。没有登记的名字不会出现。"""
    closes = getattr(market, "fill_close", None) or {}
    boards = getattr(market, "fill_board", None) or {}
    by_day = getattr(market, "fill_board_by_day", None) or {}
    names = list(dict.fromkeys([*closes.keys(), *boards.keys()]))
    quotes: dict[str, FillQuote] = {}
    for name in names:
        series = closes.get(name, pd.Series(dtype=float))
        quotes[name] = FillQuote(
            close=series, board=str(boards.get(name, "none")), board_by_day=by_day.get(name))
    return quotes
