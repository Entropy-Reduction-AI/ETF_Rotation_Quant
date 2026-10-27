"""v3 §6 判据和 §7 验证。

设计期数字只作工程核对。本包不写 `results/v3/LOCK`，也不计算 2016 年及之后的组合收益。
紧缩夏普比率的出处写在 `sharpe.py` 的文档字符串里。
"""

from .common import (
    DESIGN_END,
    EXPLORATION_TRIALS,
    ORCHESTRATOR_DIAGNOSTIC_TRIALS,
    TRADING_DAYS,
    EvalError,
    annualized_return,
    require_design_period,
)
from .controls import criterion_2, eligibility, percentile_rank
from .drawdown import EQUITY_CLASSES, criterion_4, drawdown_stats, equity_weight, position_matched
from .eras import ERAS, criterion_3
from .report import action_for, evaluate_design, plain
from .robustness import best_containers, delay_targets, robustness_books, robustness_table
from .selection import cscv_pbo, premium_keys, stitch_targets, walk_forward
from .sharpe import criterion_5, deflated_sharpe_ratio, expected_maximum_sharpe, probabilistic_sharpe_ratio, trial_count
from .windows import criterion_1, rolling_windows

__all__ = [
    "DESIGN_END",
    "EQUITY_CLASSES",
    "ERAS",
    "EXPLORATION_TRIALS",
    "ORCHESTRATOR_DIAGNOSTIC_TRIALS",
    "TRADING_DAYS",
    "EvalError",
    "action_for",
    "annualized_return",
    "best_containers",
    "criterion_1",
    "criterion_2",
    "criterion_3",
    "criterion_4",
    "criterion_5",
    "cscv_pbo",
    "deflated_sharpe_ratio",
    "delay_targets",
    "drawdown_stats",
    "eligibility",
    "equity_weight",
    "evaluate_design",
    "expected_maximum_sharpe",
    "percentile_rank",
    "plain",
    "position_matched",
    "premium_keys",
    "probabilistic_sharpe_ratio",
    "require_design_period",
    "robustness_books",
    "robustness_table",
    "rolling_windows",
    "stitch_targets",
    "trial_count",
    "walk_forward",
]
