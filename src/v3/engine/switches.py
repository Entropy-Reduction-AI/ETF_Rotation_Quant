"""v4 引擎开关。全部默认关闭，关闭时走 v3.1 的原路径。

T2 的窗口按预注册草案固定为 60 日，权重用百分位直线换算，不再把效率本身当权重。
`allow_substitute` 只在 `carriers` 打开时有意义。草案的主路径包含相近替身；
关掉它是 §7.2 的「不含相近替身」对照。
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
    t4_pool: bool = False
    carriers: bool = False
    fx_v4: bool = False
    allow_substitute: bool = True

    def idle(self) -> bool:
        """关闭全部机制，并且没有跨境成本对象。这时执行路径与 v3.1 相同。"""
        return (
            not self.fill_limits
            and not self.t1_turn
            and not self.t2_state_weights
            and not self.t3_refill
            and self.cross_border is None
            and not self.t4_pool
            and not self.carriers
            and not self.fx_v4
        )
