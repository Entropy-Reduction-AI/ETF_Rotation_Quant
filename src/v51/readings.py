"""§2：28 把尺子、速度、响度权重、H / F / E。

一年预热期（任何一把尺子的分位历史不足 250 个）28 把全部等权。
分位只用当天之前的响度，算法与设计评审画像 `profile33.py` 的 `state` 相同：
样本标准差、σ 不含当天、`bisect_left` 分位。
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.v3.engine.book import assert_window

from .params import SLOW_STEPS, Params, V51Error, long_rulers


@dataclass(frozen=True)
class PanelReadings:
    """每个容器一列。`warmup` 为真表示当天用了等权。"""

    H: pd.DataFrame
    F: pd.DataFrame
    E: pd.DataFrame
    warmup: pd.DataFrame
    weight: dict[str, pd.DataFrame]


def _percentile(values: np.ndarray, minimum: int) -> np.ndarray:
    """当天的分位 = 严格小于它的历史个数 / 历史个数。先算再把当天放进历史。"""
    out = np.full(len(values), np.nan)
    history: list[float] = []
    for i, value in enumerate(values):
        if np.isnan(value):
            continue
        if len(history) >= minimum:
            out[i] = bisect.bisect_left(history, float(value)) / len(history)
        bisect.insort(history, float(value))
    return out


def _prepare(returns: pd.DataFrame) -> pd.DataFrame:
    frame = returns.copy()
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index))
    if frame.index.tz is not None:
        raise V51Error("日收益索引不带时区")
    frame.index = frame.index.normalize()
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise V51Error("日收益要按交易日唯一排好")
    return frame


def read_series(asset: pd.Series, cash_log: pd.Series, params: Params | None = None) -> dict[str, pd.Series | pd.DataFrame | bool]:
    """一条序列的速度、权重和三个读数。现金对数收益由调用方先算好。"""
    frozen = Params() if params is None else params
    rulers = list(frozen.rulers)
    logged = np.log1p(asset.astype(float))
    ready = logged.notna().rolling(frozen.sigma_window, min_periods=1).sum().ge(frozen.sigma_window)
    filled = logged.fillna(0.0)
    excess = filled - cash_log.reindex(filled.index)
    sigma = filled.rolling(frozen.sigma_window).std().shift(1)
    velocity = pd.DataFrame(
        {n: excess.rolling(n).sum() / (sigma * np.sqrt(n)) for n in rulers},
        index=filled.index,
    ).where(ready, axis=0)
    loudness = pd.DataFrame(
        {n: _percentile(velocity[n].abs().rolling(n).mean().to_numpy(dtype=float), frozen.quantile_min) for n in rulers},
        index=velocity.index,
    )
    weight = loudness.div(loudness.sum(axis=1), axis=0)
    warmup = loudness.isna().any(axis=1) & velocity.notna().all(axis=1)
    weight.loc[warmup] = 1.0 / len(rulers)
    level = (weight * velocity).sum(axis=1, min_count=len(rulers))
    frontier = (velocity < 0).mean(axis=1).where(velocity.notna().all(axis=1))
    slow = velocity.loc[:, list(long_rulers(frozen.rulers, frozen.long_min_days))].mean(axis=1, skipna=False)
    gap = frozen.slow_gap
    earlier = slow.shift(gap)
    oldest = slow.shift(gap * SLOW_STEPS)
    defined = slow.notna() & oldest.notna()
    easing = ((slow > earlier) & (earlier > oldest)).astype(float).where(defined)
    return {
        "H": level,
        "F": frontier,
        "E": easing,
        "warmup": warmup.fillna(False),
        "weight": weight,
        "velocity": velocity,
    }


def read_panel(returns: pd.DataFrame, cash_id: str, *, allow_after: bool = False,
               params: Params | None = None) -> PanelReadings:
    """面板上除现金外的每一列。默认拒绝晚于 2015-12-31 的日期。"""
    frozen = Params() if params is None else params
    frame = _prepare(returns)
    assert_window(frame.index, allow_after)
    if cash_id not in frame.columns:
        raise V51Error("收益里没有现金列")
    cash_log = np.log1p(frame[cash_id].fillna(0.0))
    level: dict[str, pd.Series] = {}
    turned: dict[str, pd.Series] = {}
    easing: dict[str, pd.Series] = {}
    warmup: dict[str, pd.Series] = {}
    weight: dict[str, pd.DataFrame] = {}
    for name in frame.columns:
        if name == cash_id:
            continue
        one = read_series(frame[name], cash_log, frozen)
        level[name] = one["H"]
        turned[name] = one["F"]
        easing[name] = one["E"]
        warmup[name] = one["warmup"]
        weight[name] = one["weight"]
    index = frame.index
    return PanelReadings(
        H=pd.DataFrame(level, index=index),
        F=pd.DataFrame(turned, index=index),
        E=pd.DataFrame(easing, index=index),
        warmup=pd.DataFrame(warmup, index=index),
        weight=weight,
    )


def level_index(returns: pd.DataFrame) -> pd.DataFrame:
    """由简单收益累成的价格。缺日按 0 收益接上，不把缺口当成下跌。画像用的就是这条。"""
    frame = _prepare(returns)
    values = frame.astype(float)
    logged = np.log1p(values.where(np.isfinite(values) & (values > -1.0)))
    return np.exp(logged.fillna(0.0).cumsum())
