"""跨境成本挂钩。数值是占位，正式数字等 v4 预注册写死。

换汇点差和佣金加在跨境品种的单边成交费率上。分红预扣税从当日分红收益里扣，
不改价格本身。三项默认都是 0。调用方不传入时，v3.1 的费率公式不动。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CrossBorderCosts:
    """占位参数。不要把这里的默认值当成已经冻结的成本。"""

    fx_spread: float = 0.0
    commission: float = 0.0
    dividend_withholding: float = 0.0

    def trade_surcharge(self) -> float:
        """单边成交额外费率：换汇点差 + 佣金。"""
        return float(self.fx_spread) + float(self.commission)


# 测试用来钉公式的一组占位，不是预注册数值。
PLACEHOLDER_COSTS = CrossBorderCosts(
    fx_spread=0.0015,
    commission=0.0005,
    dividend_withholding=0.10,
)

# 场内 QDII、美股宽基、港股。A 股和境内商品、国债不走这条。
CROSS_BORDER_CLASSES = frozenset({"美股宽基", "美股和全球主题", "港股"})


def withheld_dividend(gross_yield: float, withholding: float) -> float:
    """预扣之后还留在组合里的分红收益。gross_yield 是分红贡献的简单收益。"""
    return float(gross_yield) * (1.0 - float(withholding))


def names_for(asset_classes: dict[str, str] | None) -> set[str]:
    if not asset_classes:
        return set()
    return {name for name, kind in asset_classes.items() if kind in CROSS_BORDER_CLASSES}
