"""v5 §6.2 部件过关。不读候选收益文件，也不写 component-gate.csv。"""

from .gate import COMPONENT_TARGET, GATE_COLUMNS, ComponentStep, component_gate

__all__ = ["COMPONENT_TARGET", "GATE_COLUMNS", "ComponentStep", "component_gate"]
