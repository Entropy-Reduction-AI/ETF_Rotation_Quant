"""把 v5.1 的目标权重交给 v4 B0 已经在用的成交入口。

成本、涨跌停、QDII 溢价、跨境红利都走 `src.v3.engine.arms._run_path`，
和 `src.v5.engine.execute.run_arm` 同一组参数。池子由 `src.v4.r5.design.Markets` 装。
10% 硬闸门在配权里替换名字，这里不打开 v3.1 的 C2（C2 会卖成现金并且不补位）。
不写账本，不写 LOCK。
"""
from __future__ import annotations

import copy

import pandas as pd

from src.v3.engine.arms import _run_path, _schedule
from src.v3.engine.book import Book, assert_window
from src.v3.engine.costs import names_for
from src.v3.engine.limits import quotes_from_market
from src.v3.engine.score import lookback_panel

from .params import V51Error, load_params
from .universe import Universe, universe_from_names


def open_market(pool: str, spec, *, allow_substitute: bool = True, listed_only: bool = False):
    """U-指数或 U-可交易。成员、载体和汇率仍由 v4 的 `Markets` 构造。

    `listed_only` 默认关闭，且只允许用在 U-可交易。
    """
    loaded = load_params()
    if pool not in loaded.params.pools:
        raise V51Error(f"v5.1 没有这个池：{pool}")
    from src.v4.r5.design import Markets

    return Markets(spec).get(
        pool, t4=False, allow_substitute=allow_substitute, listed_only=listed_only)


def universe_for(market, class_of: dict[str, str] | None = None) -> Universe:
    """用行情里的名字和大类表拼第一层。大类表没有的名字会在 `classes_for` 里拒绝。"""
    from .universe import class_lookup

    mapping = class_of if class_of is not None else class_lookup(list(market.names), market.cash_id)
    names = [name for name in market.names if name != market.cash_id]
    return universe_from_names(names, mapping)


def run_book(market, spec, decisions: pd.DataFrame, *, switches=None,
             decision_delay: int = 0, cost_multiplier: float = 1.0,
             allow_after: bool = False) -> Book:
    """一条路的成交。决策日的下一交易日收盘换仓。日期晚于 2015-12-31 直接拒绝。

    `allow_after` 只给一次性检验。设计期保持关闭。
    """
    from src.v5.engine.execute import b0_switches
    from src.v5.engine.paths import delay_book, resolve_exit

    if decision_delay not in {0, 1}:
        raise V51Error("决策日只延后 0 天或 1 天")
    assert_window(market.dates, allow_after)
    assert_window(decisions.index, allow_after)
    running = copy.copy(market)
    running.cost_multiplier = float(cost_multiplier)
    chosen = switches if switches is not None else b0_switches()
    lengths = tuple(int(item) for item in spec.lookbacks)
    panels = {
        length: lookback_panel(running.signal, running.cash_id, length) for length in lengths
    }
    premium = _schedule(running, spec, panels, None, allow_after=allow_after)
    quotes = quotes_from_market(running) if chosen.fill_limits else None
    border = None
    dividend = None
    if chosen.cross_border is not None:
        border = names_for(getattr(running, "asset_classes", None))
        dividend = getattr(running, "dividend_yield", None)
    # C2 关着。硬闸门已经在目标权重里处理过。
    book = _run_path(
        running, spec, decisions, allow_after=allow_after, exit_drawdown=resolve_exit(False, None),
        premium=premium, switches=chosen, fill_quotes=quotes, refill_targets=None,
        cross_border_names=border, dividend_yield=dividend,
    )
    if decision_delay == 0:
        return book
    return delay_book(running, spec, book, resolve_exit(False, None), chosen, quotes)
