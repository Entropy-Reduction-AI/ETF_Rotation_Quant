"""v4-R3 打分卡：任意起点、四种市场状态。

数字口径与 `results/v3/diag/2026-10-27-owner-board/` 的 `anystart.py`、`states.py`
以及 Reviewer 独立脚本 `reviewer_r3_scorecard.py` 相同。状态超额存 1 位小数；
看板整数是对该打印值再四舍五入。
"""

from .core import (
    DESIGN_END,
    DESIGN_START,
    REFERENCE,
    ScorecardError,
    acceptance,
    any_start,
    cash_weight_on,
    label_state,
    reference_scorecard,
    score_book,
)
from .gate import GATE_COLUMNS, attempt_count, candidate_gate

__all__ = [
    "DESIGN_END",
    "DESIGN_START",
    "REFERENCE",
    "ScorecardError",
    "acceptance",
    "any_start",
    "cash_weight_on",
    "GATE_COLUMNS",
    "attempt_count",
    "candidate_gate",
    "label_state",
    "reference_scorecard",
    "score_book",
]
