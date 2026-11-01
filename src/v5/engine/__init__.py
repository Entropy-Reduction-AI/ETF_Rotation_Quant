"""v5 配权。S0、C1、结构对照和两路合成。不算组合收益。"""

from .allocate import (
    LOOKBACKS,
    STRUCTURE_FIXED_BUDGET,
    STRUCTURE_NO_DEFENSE,
    STRUCTURE_S0,
    STRUCTURE_STRONGEST,
    Sleeve,
    apply_c1,
    average_lookbacks,
    blend_lookbacks,
    group_weights,
    path_decisions,
    vol_multiplier,
)
from .classes import class_map, load_classes
from .paths import arm_return, run_path

__all__ = [
    "LOOKBACKS",
    "STRUCTURE_FIXED_BUDGET",
    "STRUCTURE_NO_DEFENSE",
    "STRUCTURE_S0",
    "STRUCTURE_STRONGEST",
    "Sleeve",
    "apply_c1",
    "arm_return",
    "average_lookbacks",
    "blend_lookbacks",
    "class_map",
    "group_weights",
    "load_classes",
    "path_decisions",
    "run_path",
    "vol_multiplier",
]
