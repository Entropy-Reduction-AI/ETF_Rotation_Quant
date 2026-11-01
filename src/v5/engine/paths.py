"""§4.1 两路合成，以及 §4.4 的 10% 离场接线。

C2 不重写离场。开着时调用 v3.1 的 `simulate_path`，阈值用它的常数，不传补位目标。
关掉时走没有离场的 `book.simulate`。两条函数的成交限制并不共用；本次不改 v3。
"""
from __future__ import annotations

import pandas as pd

from src.v3.engine.book import simulate, to_execution
from src.v3.engine.exit import EXIT_DRAWDOWN, simulate_path
from src.v4.scorecard.core import refuse_portfolio_dates

from .allocate import EngineError

# v3.1 §4.5 写死 10%。稳健性里的 8%、12% 不在这里挑。
C2_DRAWDOWN = EXIT_DRAWDOWN


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


def run_path(pnl: pd.DataFrame, fees: dict[str, float], cash_id: str, decisions: pd.DataFrame, *,
             enable_c2: bool, levels: pd.DataFrame | None = None, allow_after: bool = False):
    """一条路的成交。`enable_c2` 为真时加上单只 10% 离场，卖出所得留在现金，不补位。"""
    if C2_DRAWDOWN != 0.10:
        raise EngineError("v3.1 离场阈值不是 10%")
    dates = pd.DatetimeIndex(pnl.index)
    targets = to_execution(decisions, dates)
    if not enable_c2:
        return simulate(pnl, targets, fees, cash_id, allow_after=allow_after)
    if levels is None:
        raise EngineError("C2 要用与该路持仓收益一致的计价序列")
    return simulate_path(
        pnl, levels, fees, cash_id,
        targets=targets,
        exit_drawdown=C2_DRAWDOWN,
        refill_targets=None,
        allow_after=allow_after,
    )
