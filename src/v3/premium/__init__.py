"""v3 §5 QDII 溢价模块。

只调整权重、选执行代码、复现已看过的事件清单。不计算组合收益，不写 LOCK。
"""

from .apply import adjust_weights, allocate_container, representative_code
from .episodes import scan_explore
from .rules import (
    NORMAL,
    PULSE,
    STRUCTURAL_DISCOUNT,
    STRUCTURAL_HIGH,
    PremiumError,
    PremiumSpec,
    classify_state,
    subject_to_premium,
)
from .series import premium_frame

__all__ = [
    "NORMAL",
    "PULSE",
    "STRUCTURAL_DISCOUNT",
    "STRUCTURAL_HIGH",
    "PremiumError",
    "PremiumSpec",
    "adjust_weights",
    "allocate_container",
    "classify_state",
    "premium_frame",
    "representative_code",
    "scan_explore",
    "subject_to_premium",
]
