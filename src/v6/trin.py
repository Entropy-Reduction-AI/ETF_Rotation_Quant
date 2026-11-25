"""TRIN 日值。D45-10：全样本 99% 分位是向前看；改成含当日的扩展分位。"""

from __future__ import annotations

import pandas as pd

from src.v6.guard import assert_not_after


def raw_ratio(prices: pd.DataFrame, amount: pd.DataFrame, *, min_movers: int | None) -> pd.Series:
    """涨跌家数比 ÷ 涨跌成交额比。min_movers 只用于 A 股（少于 4 个涨跌不算）。"""
    assert_not_after(prices.index, "TRIN价格")
    change = prices.pct_change()
    up, down = change > 0, change < 0
    ratio = (
        (up.sum(axis=1) / down.sum(axis=1).replace(0, float("nan")))
        / ((amount * up).sum(axis=1) / (amount * down).sum(axis=1).replace(0, float("nan")))
    )
    ratio = ratio.replace([float("inf"), float("-inf")], float("nan"))
    if min_movers is not None:
        ratio = ratio.where(up.sum(axis=1) + down.sum(axis=1) >= min_movers)
    return ratio


def clip_full_sample(daily: pd.Series) -> pd.Series:
    """冻结代码的写法：一条序列上的 99% 分位，用到了样本后部。调用前序列必须已经停在 2015-12-31。"""
    assert_not_after(daily.index, "TRIN旧口径")
    return daily.clip(upper=daily.quantile(0.99))


def clip_expanding(daily: pd.Series) -> pd.Series:
    """D45-10：只用当日及以前的日值，分位包含当日。"""
    assert_not_after(daily.index, "TRIN新口径")
    return daily.clip(upper=daily.expanding().quantile(0.99))


def month_end_mean(daily: pd.Series) -> pd.Series:
    monthly = daily.rolling(10, min_periods=7).mean().resample("ME").last()
    monthly.index = monthly.index.to_period("M")
    return monthly
