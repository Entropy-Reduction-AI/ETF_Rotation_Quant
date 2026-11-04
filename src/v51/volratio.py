"""C-波动比的动态周期。数字沿用设计稿第 2 版（`layer1.py` / `adaptive.py` 的波动比）。

L = 250^(1−q) × 20^q，q 是 20 日波动 ÷ 250 日波动在自身历史里的分位。
历史不足 250 个时 q = 0.5。分位只用当天之前的值。
强度 M 是 L 天的对数涨幅减去同期现金；噪音 z = M ÷（250 日对数波动 × √L）。
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.v3.engine.book import assert_window

from .params import V51Error

SHORT = 20
LONG = 250
HISTORY = 250


@dataclass(frozen=True)
class VolRatio:
    """每个容器一列。`strength` 是 M，`noise` 是 z。"""

    quantile: pd.DataFrame
    length: pd.DataFrame
    strength: pd.DataFrame
    noise: pd.DataFrame


def past_quantile(values: np.ndarray, minimum: int = HISTORY) -> np.ndarray:
    """严格小于当天的历史占比。历史不够时取 0.5，当天不进自己的分母。"""
    out = np.full(len(values), np.nan)
    history: list[float] = []
    for i, value in enumerate(values):
        if not np.isfinite(value):
            continue
        number = float(value)
        if len(history) >= minimum:
            out[i] = bisect.bisect_left(history, number) / len(history)
        else:
            out[i] = 0.5
        bisect.insort(history, number)
    return out


def dynamic_length(quantile: np.ndarray) -> np.ndarray:
    """几何插值后四舍五入到整数天。q 没有定义时 L 也没有。"""
    q = np.asarray(quantile, dtype=float)
    with np.errstate(invalid="ignore"):
        return np.round(LONG ** (1.0 - q) * SHORT ** q)


def vol_ratio(returns: pd.DataFrame, cash_id: str, names: list[str]) -> VolRatio:
    """只算点名的容器。日期晚于 2015-12-31 直接拒绝。"""
    frame = returns.copy()
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index))
    if frame.index.tz is not None:
        raise V51Error("日收益索引不带时区")
    frame.index = frame.index.normalize()
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise V51Error("日收益要按交易日唯一排好")
    assert_window(frame.index, False)
    if cash_id not in frame.columns:
        raise V51Error("收益里没有现金列")
    missing = [name for name in names if name not in frame.columns]
    if missing:
        raise V51Error(f"波动比缺这些列：{missing}")
    cash_cum = np.log1p(frame[cash_id].astype(float).fillna(0.0)).cumsum().to_numpy(dtype=float)
    quantile: dict[str, np.ndarray] = {}
    length: dict[str, np.ndarray] = {}
    strength: dict[str, np.ndarray] = {}
    noise: dict[str, np.ndarray] = {}
    index = np.arange(len(frame))
    for name in names:
        logged = np.log1p(frame[name].astype(float))
        valid = logged.notna()
        filled = logged.fillna(0.0)
        ratio = filled.rolling(SHORT).std() / filled.rolling(LONG).std()
        q = past_quantile(ratio.to_numpy(dtype=float))
        span = dynamic_length(q)
        step = np.where(np.isfinite(span), span, 1.0e9).astype(np.int64)
        cursor = index - step
        ready = (cursor >= 0) & valid.rolling(LONG, min_periods=1).sum().ge(LONG).to_numpy()
        jumped = np.clip(cursor, 0, None)
        cum = filled.cumsum().to_numpy(dtype=float)
        excess = (cum - cum[jumped]) - (cash_cum - cash_cum[jumped])
        raw = np.where(ready, excess, np.nan)
        scale = filled.rolling(LONG).std().to_numpy(dtype=float) * np.sqrt(np.where(np.isfinite(span), span, np.nan))
        with np.errstate(divide="ignore", invalid="ignore"):
            scaled = raw / scale
        quantile[name] = q
        length[name] = span
        strength[name] = raw
        noise[name] = np.where(np.isfinite(scaled), scaled, np.nan)
    return VolRatio(
        quantile=pd.DataFrame(quantile, index=frame.index),
        length=pd.DataFrame(length, index=frame.index),
        strength=pd.DataFrame(strength, index=frame.index),
        noise=pd.DataFrame(noise, index=frame.index),
    )
