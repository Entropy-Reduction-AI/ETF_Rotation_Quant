"""月初再平衡。每月第一根收益回到目标权重，月内随收益漂移。"""
from __future__ import annotations

import numpy as np
import pandas as pd


def monthly_rebalance(returns: pd.DataFrame, weights: dict[str, float]) -> tuple[pd.Series, pd.DataFrame]:
    """返回组合日收益，以及当日收益发生前的权重（月初已重置）。"""
    names = list(weights)
    missing = [name for name in names if name not in returns.columns]
    if missing:
        raise ValueError(f"缺收益列：{missing}")
    frame = returns.loc[:, names].astype(float)
    if frame.empty:
        raise ValueError("没有收益")
    if frame.isna().any().any():
        raise ValueError("收益里有空值")
    target = np.array([float(weights[name]) for name in names], dtype=float)
    if abs(float(target.sum()) - 1.0) > 1e-9:
        raise ValueError(f"权重之和不是 1：{float(target.sum())}")
    held = target.copy()
    prev = None
    port: list[float] = []
    rows: list[np.ndarray] = []
    for day, row in frame.iterrows():
        period = pd.Timestamp(day).to_period("M")
        if prev is None or period != prev:
            held = target.copy()
        values = row.to_numpy(dtype=float)
        rows.append(held.copy())
        gain = float(np.dot(held, values))
        scale = 1.0 + gain
        if scale != 0.0:
            held = held * (1.0 + values) / scale
        port.append(gain)
        prev = period
    series = pd.Series(port, index=frame.index, dtype=float, name="ret")
    weight_path = pd.DataFrame(rows, index=frame.index, columns=names)
    return series, weight_path
