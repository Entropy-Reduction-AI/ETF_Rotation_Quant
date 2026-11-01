"""§4.1 两路合成，以及 §4.4 的离场接线。

每一条路都走 v4 B0 用的 `simulate_path`（`src/v3/engine/arms.py` 的 `_run_path`）。
C2 关着时传 `exit_drawdown=None`，不另走 `book.simulate`。不传补位目标。
"""
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from src.v3.engine.arms import _levels, _run_path
from src.v3.engine.exit import EXIT_DRAWDOWN, NO_EXIT, simulate_path
from src.v3.engine.market import market_from_returns
from src.v3.engine.switches import EngineSwitches
from src.v3.eval.robustness import delay_targets
from src.v4.scorecard.core import refuse_portfolio_dates

from .allocate import EngineError

# v3.1 §4.5 写死 10%。8%、12% 只在调用方点名时使用，这里不挑。
C2_DRAWDOWN = EXIT_DRAWDOWN
PATHS = ("week", "month")


def arm_return(week: pd.Series, month: pd.Series) -> pd.Series:
    """r_A(t) = (r_周(t) + r_月(t)) / 2。两路必须同一交易日历。"""
    left = pd.Series(week, dtype=float)
    right = pd.Series(month, dtype=float)
    left.index = pd.DatetimeIndex(pd.to_datetime(left.index))
    right.index = pd.DatetimeIndex(pd.to_datetime(right.index))
    if left.index.has_duplicates or right.index.has_duplicates:
        raise EngineError("日收益索引不能重复")
    left = left.sort_index()
    right = right.sort_index()
    refuse_portfolio_dates(left.index, what="周路日收益")
    refuse_portfolio_dates(right.index, what="月路日收益")
    if not left.index.equals(right.index):
        raise EngineError("周路和月路必须对齐同一交易日历，不能丢掉一路再平均")
    out = (left + right) / 2.0
    out.name = "r_A"
    return out


def resolve_exit(enable_c2: bool, exit_drawdown: float | None) -> float | None:
    """C2 关着时只能是不离场。开着时默认 10%，调用方可以点名 8% 或 12%。"""
    if not enable_c2:
        if exit_drawdown is not None:
            raise EngineError("C2 关着时不能另设离场阈值")
        return NO_EXIT
    if exit_drawdown is None:
        return C2_DRAWDOWN
    return exit_drawdown


def delay_book(market, spec, book, drawdown, switches, quotes):
    """决策日再延后 1 天。成交参数与 `src/v4/r5/design.py` 的 `_execute` 相同。"""
    targets = delay_targets(book.targets, market.dates)
    extra = {}
    if switches is not None and switches.fill_limits:
        extra["fill_limits"] = True
        extra["fill_quotes"] = quotes
    return simulate_path(
        market.pnl,
        _levels(market),
        market.fees,
        market.cash_id,
        targets=targets,
        exit_drawdown=drawdown,
        trade_eps=spec.trade_eps,
        cost_multiplier=market.cost_multiplier,
        allow_after=False,
        weight_eps=spec.weight_eps,
        **extra,
    )


def run_path(pnl: pd.DataFrame, fees: dict[str, float], cash_id: str, decisions: pd.DataFrame, *,
             enable_c2: bool, levels: pd.DataFrame | None = None, allow_after: bool = False,
             fill_limits: bool = False, fill_quotes: dict | None = None, premium=None,
             code_levels=None, code_returns=None, cross_border=None,
             cross_border_names: set | None = None, dividend_yield: pd.DataFrame | None = None,
             trade_eps: float = 1e-12, weight_eps: float = 1e-6, cost_multiplier: float = 1.0,
             exit_drawdown: float | None = None, decision_delay: int = 0):
    """一条路的成交。C2 关着时不离场，开着时按阈值离场。卖出所得留在现金，不补位。"""
    if decision_delay not in {0, 1}:
        raise EngineError("决策日只延后 0 天或 1 天")
    if enable_c2 and levels is None:
        raise EngineError("C2 要用与该路持仓收益一致的计价序列")
    if C2_DRAWDOWN != 0.10:
        raise EngineError("v3.1 离场阈值不是 10%")
    drawdown = resolve_exit(enable_c2, exit_drawdown)
    market = market_from_returns(
        pnl, fees, pnl=pnl, cash_id=cash_id, levels=levels, cost_multiplier=cost_multiplier,
    )
    market.code_levels = code_levels
    market.code_returns = code_returns
    market.dividend_yield = dividend_yield
    spec = SimpleNamespace(trade_eps=float(trade_eps), weight_eps=float(weight_eps))
    switches = EngineSwitches(fill_limits=bool(fill_limits), cross_border=cross_border)
    book = _run_path(
        market, spec, decisions, allow_after=allow_after, exit_drawdown=drawdown, premium=premium,
        switches=switches, fill_quotes=fill_quotes, refill_targets=None,
        cross_border_names=cross_border_names, dividend_yield=dividend_yield,
    )
    if decision_delay == 0:
        return book
    return delay_book(market, spec, book, drawdown, switches, fill_quotes)
