"""v4 引擎开关。全部默认关闭，关闭时走 v3.1 的原路径。

T2 的趋势效率窗口是占位。预注册写死之前，不把它当成正式参数，也不要用它跑候选收益。
"""
from __future__ import annotations

from dataclasses import dataclass

from .costs import CrossBorderCosts

# Kaufman 趋势效率的回看长度。占位，不是预注册参数。
T2_WINDOW_PLACEHOLDER = 60


@dataclass(frozen=True)
class EngineSwitches:
    fill_limits: bool = False
    t1_turn: bool = False
    t2_state_weights: bool = False
    t3_refill: bool = False
    t2_window: int = T2_WINDOW_PLACEHOLDER
    cross_border: CrossBorderCosts | None = None

    def idle(self) -> bool:
        """关闭全部机制，并且没有跨境成本对象。这时执行路径与 v3.1 相同。"""
        return (
            not self.fill_limits
            and not self.t1_turn
            and not self.t2_state_weights
            and not self.t3_refill
            and self.cross_border is None
        )
