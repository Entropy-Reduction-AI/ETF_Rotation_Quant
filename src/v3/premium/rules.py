"""§5 的常数和四种状态。W、θ 只接受预注册写死的候选。"""
from __future__ import annotations

import math
from dataclasses import dataclass

PULSE = "脉冲"
STRUCTURAL_HIGH = "结构型冲高"
STRUCTURAL_DISCOUNT = "结构型折价"
NORMAL = "常态"

WINDOWS = (120, 250)
THETAS = (0.10, 0.15)
# §4.1：决策日 T 用不晚于 T−2 个上交所交易日的单位净值。与 config/v3/arms.toml 的 nav_lag 相同。
NAV_LAG = 2
NAV_DAYS = 20
# §1-5 看过事件清单之后定死的分界，不是待选参数。
BASELINE_CUT = 0.05
DISCOUNT = 0.05
# §5.3。权重 × max(p, 0)。
SINGLE_BUDGET = 0.02
TOTAL_BUDGET = 0.05
# 与 arms.toml 的 weight_eps 相同：更小的权重当成没有持仓。
HELD_EPS = 1e-6
PREMIUM_ASSET_CLASSES = frozenset({"美股宽基", "美股和全球主题", "港股"})
_ABS = 1e-12


class PremiumError(RuntimeError):
    pass


@dataclass(frozen=True)
class PremiumSpec:
    """(W, θ)。§7.1 的滚动选择不在本模块。"""

    window: int = 250
    theta: float = 0.10

    def __post_init__(self) -> None:
        if self.window not in WINDOWS:
            raise PremiumError(f"W 只能是 {WINDOWS}，收到 {self.window}")
        for item in THETAS:
            if math.isclose(float(self.theta), item, abs_tol=_ABS, rel_tol=0.0):
                object.__setattr__(self, "theta", item)
                return
        raise PremiumError(f"θ 只能是 {THETAS}，收到 {self.theta}")


def _finite(value) -> float:
    if value is None:
        return float("nan")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return number


def _le(left: float, right: float) -> bool:
    return left < right or math.isclose(left, right, abs_tol=_ABS, rel_tol=0.0)


def _ge(left: float, right: float) -> bool:
    return left > right or math.isclose(left, right, abs_tol=_ABS, rel_tol=0.0)


def classify_state(premium, baseline, deviation, nav_return, spec: PremiumSpec | None = None) -> str | None:
    """§5.2。同一天只取一种，自上而下：脉冲、结构型冲高、结构型折价、常态。

    当天没有溢价时返回 None。历史不足、算不出常态线时归入常态（不调整）。
    """
    spec = spec or PremiumSpec()
    p = _finite(premium)
    if p != p:
        return None
    b = _finite(baseline)
    d = _finite(deviation)
    if b != b or d != d:
        return NORMAL
    if _le(b, BASELINE_CUT) and _ge(d, spec.theta):
        return PULSE
    if not _le(b, BASELINE_CUT) and _ge(d, spec.theta):
        return STRUCTURAL_HIGH
    nav = _finite(nav_return)
    if not _le(b, BASELINE_CUT) and _le(d, -DISCOUNT) and nav == nav and nav < 0.0:
        return STRUCTURAL_DISCOUNT
    return NORMAL


def subject_to_premium(container: dict) -> bool:
    """U-可交易里会偏离净值的 QDII。指数本身不进这个模块。

    美股宽基、海外主题、港股的执行工具是 QDII ETF。原油在商品大类里，名称单独认。
    黄金、豆粕、A 股、债券、现金不认。
    """
    if container.get("asset_class") in PREMIUM_ASSET_CLASSES:
        return True
    return "原油" in str(container.get("name") or "")
