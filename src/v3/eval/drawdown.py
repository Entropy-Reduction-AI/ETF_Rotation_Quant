"""§6④ 最大回撤和水下时间，以及只作报告的 BM-仓位匹配。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .common import EvalError, require_design_period

# 预注册写的是「美股主题」。登记表里的资产类别是「美股和全球主题」。
# S2 是附录 2 的 A 股容器，登记类别不是「A股宽基 / A股行业」，经济上仍是股票。
EQUITY_CLASSES = frozenset({
    "A股宽基", "A股行业", "A股红利", "港股", "美股宽基", "美股和全球主题", "S2",
})
DRAWDOWN_GAP = 0.05


def drawdown_stats(returns) -> dict:
    """扣成本后的日度净值。起点资金是 1，最大回撤是历史峰值到其后谷底的百分比跌幅，记成负数。

    第一天的亏损也算从起点 1 跌下去。水下时间是净值严格低于历史峰值的交易日：
    个数、占全部交易日的比例，以及最长连续水下天数。
    峰值如果一直是起点资金，`peak` 为空。
    """
    series = pd.Series(returns, dtype=float).sort_index()
    require_design_period(series.index)
    if series.empty:
        raise EvalError("没有收益")
    if series.isna().any():
        raise EvalError("回撤用的收益里有空值")
    nav = (1.0 + series).cumprod()
    running_peak = np.maximum(nav.cummax().to_numpy(dtype=float), 1.0)
    drawdown = nav.to_numpy(dtype=float) / running_peak - 1.0
    trough_pos = int(np.argmin(drawdown))
    history = nav.iloc[:trough_pos + 1]
    peak_level = float(running_peak[trough_pos])
    if float(history.max()) + 1e-15 < peak_level:
        peak = None
    else:
        peak = pd.Timestamp(history.idxmax())
    underwater = nav.to_numpy(dtype=float) < running_peak
    longest = 0
    current = 0
    for flag in underwater:
        if flag:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    days = int(underwater.sum())
    return {
        "max_drawdown": float(drawdown[trough_pos]),
        "depth": float(-drawdown[trough_pos]),
        "peak": peak,
        "trough": pd.Timestamp(nav.index[trough_pos]),
        "underwater_days": days,
        "underwater_fraction": days / len(series),
        "longest_underwater_days": int(longest),
    }


def criterion_4(strategy, benchmark) -> dict:
    """全期最大回撤不比 BM-主 深 5 个百分点以上。深 5 个百分点恰好仍算通过这道数值比较。"""
    left = drawdown_stats(strategy)
    right = drawdown_stats(benchmark)
    gap = left["depth"] - right["depth"]
    return {
        "strategy": left,
        "benchmark": right,
        "deeper_by": gap,
        "engineering_check": bool(gap <= DRAWDOWN_GAP),
        "formal_pass": None,
    }


def equity_weight(held: pd.DataFrame, classes: dict[str, str]) -> pd.Series:
    """股票类仓位 = 权重和。商品、债券、现金不计入。"""
    require_design_period(held.index)
    columns = [name for name in held.columns if classes.get(name) in EQUITY_CLASSES]
    if not columns:
        return pd.Series(0.0, index=held.index, dtype=float)
    return held[columns].sum(axis=1).astype(float)


def position_matched(benchmark, cash, equity) -> dict:
    """BM-主 × 评价窗里的平均股票类仓位 + 现金 ×（1 − 该仓位）。只报告。"""
    frame = pd.concat([
        pd.Series(benchmark, dtype=float).rename("benchmark"),
        pd.Series(cash, dtype=float).rename("cash"),
        pd.Series(equity, dtype=float).rename("equity"),
    ], axis=1).dropna()
    require_design_period(frame.index)
    if frame.empty:
        raise EvalError("仓位匹配没有重叠日期")
    weight = float(frame["equity"].mean())
    series = weight * frame["benchmark"] + (1.0 - weight) * frame["cash"]
    series.name = "bm_matched"
    return {"average_equity_weight": weight, "returns": series}
