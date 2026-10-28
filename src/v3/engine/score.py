"""§4.1–§4.2：区间收益、风险调整得分、绝对过滤、top N。"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Lookback:
    total: pd.DataFrame
    score: pd.DataFrame
    ok: pd.DataFrame
    # 够排名、但还没套用“跑赢现金”的那一层。T1 反弹换挡用。v3.1 的 `ok` 不读它。
    rankable: pd.DataFrame | None = None


def min_observations(length: int) -> int:
    return max(20, length // 2)


def history_ok(finite: pd.DataFrame, length: int) -> pd.DataFrame:
    """窗口必须完全落在该容器已有收益之后。不足 L 日不参与。"""
    arr = finite.to_numpy()
    rows, cols = arr.shape
    first = np.where(arr.any(axis=0), arr.argmax(axis=0), rows)
    pos = np.arange(rows)[:, None]
    ok = pos >= (first + length - 1)
    return pd.DataFrame(ok, index=finite.index, columns=finite.columns)


def lookback_panel(ret: pd.DataFrame, cash_id: str, length: int) -> Lookback:
    """R 是窗口内有效简单收益的连乘。假跳空等被标成空值的日子不进入连乘，也不进入标准差。

    s = R / (样本标准差 × √L)，ddof=1。有效个数少于 max(20, ⌊L/2⌋) 则不参与。
    """
    values = ret.to_numpy(dtype=float)
    finite = np.isfinite(values) & (values > -1.0)
    logged = np.zeros(values.shape, dtype=float)
    np.log1p(values, where=finite, out=logged)
    finite_df = pd.DataFrame(finite, index=ret.index, columns=ret.columns)
    log_df = pd.DataFrame(logged, index=ret.index, columns=ret.columns)
    count = finite_df.astype(float).rolling(length, min_periods=1).sum()
    total = np.expm1(log_df.rolling(length, min_periods=1).sum())
    observed = ret.where(finite_df)
    std = observed.rolling(length, min_periods=2).std(ddof=1)
    scale = std * math.sqrt(length)
    score = total / scale
    score = score.mask(std.eq(0) & total.gt(0), np.inf)
    score = score.mask(std.eq(0) & total.lt(0), -np.inf)
    score = score.mask(std.eq(0) & total.eq(0), 0.0)
    need = min_observations(length)
    cash_r = total[cash_id]
    ok = (
        history_ok(finite_df, length)
        & count.ge(need)
        & finite_df
        & total.gt(cash_r, axis=0)
        & score.notna()
    )
    ok[cash_id] = False
    rankable = (
        history_ok(finite_df, length)
        & count.ge(need)
        & finite_df
        & score.notna()
    )
    rankable[cash_id] = False
    return Lookback(total=total, score=score, ok=ok, rankable=rankable)


def pick_row(panel: Lookback, day: pd.Timestamp, n: int, names: list[str], cash_id: str,
             sort_ids: dict[str, str], liquidity: pd.DataFrame | None,
             eligible: pd.Series | None = None) -> dict[str, float]:
    """有资格的按 s 降序，其次 R 降序，其次容器 id 升序。不足 N 个时每个入选者仍是 1/N，其余给现金。

    `eligible` 仅在 T1 打开时传入。不传时用面板自己的 `ok`，和 v3.1 相同。
    """
    total = panel.total.loc[day]
    score = panel.score.loc[day]
    ok = panel.ok.loc[day] if eligible is None else eligible
    if liquidity is not None:
        gate = liquidity.loc[day]
        ranked = []
        for name in names:
            if not bool(ok[name]) or not bool(gate[name]):
                continue
            ranked.append((float(score[name]), float(total[name]), sort_ids[name], name))
    else:
        ranked = [
            (float(score[name]), float(total[name]), sort_ids[name], name)
            for name in names if bool(ok[name])
        ]
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    weights = {cash_id: 1.0}
    for _, _, _, name in ranked[:n]:
        weights[name] = 1.0 / n
        weights[cash_id] -= 1.0 / n
    return weights


def average_weights(rows: list[dict[str, float]], names: list[str], cash_id: str) -> dict[str, float]:
    keys = [*names, cash_id]
    acc = {key: 0.0 for key in keys}
    for row in rows:
        for key in keys:
            acc[key] += float(row.get(key, 0.0))
    count = float(len(rows))
    return {key: value / count for key, value in acc.items()}


def weighted_average(rows: list[dict[str, float]], weights: list[float], names: list[str],
                     cash_id: str) -> dict[str, float]:
    """四组权重不再固定 1/4。`weights` 与 `rows` 对齐，且和为 1。T2 用。"""
    keys = [*names, cash_id]
    acc = {key: 0.0 for key in keys}
    for row, weight in zip(rows, weights):
        scale = float(weight)
        for key in keys:
            acc[key] += scale * float(row.get(key, 0.0))
    return acc
