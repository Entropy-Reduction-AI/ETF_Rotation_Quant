"""设计期门禁和 §6 的年化。"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.v3.engine.book import DESIGN_END

# §6①：年化 = (1+R)^(252/n) − 1。
TRADING_DAYS = 252
# §1-2 的探索配置，计入 §6⑤。
EXPLORATION_TRIALS = 28


class EvalError(RuntimeError):
    pass


def require_design_period(index) -> None:
    """组合收益的日期不得晚于 2015-12-31。空序列放过。"""
    if index is None:
        return
    stamps = pd.DatetimeIndex(pd.to_datetime(index))
    stamps = stamps[~stamps.isna()]
    if len(stamps) == 0:
        return
    last = pd.Timestamp(stamps.max())
    if last > DESIGN_END:
        raise EvalError(
            f"拒绝计算 {last.date()} 的组合收益：晚于 {DESIGN_END.date()}。G3 之前不跑全期。"
        )


def _values(returns) -> np.ndarray:
    values = np.asarray(returns, dtype=float)
    if values.ndim != 1:
        raise EvalError("收益必须是一列")
    if len(values) == 0:
        raise EvalError("没有收益")
    if not np.isfinite(values).all():
        raise EvalError("收益里有空值或无穷")
    if np.any(values <= -1.0):
        raise EvalError("简单收益小于等于 -100%，年化没有定义")
    return values


def annualized_return(returns) -> float:
    """(1+R)^(252/n) − 1。n 是这列收益的个数。"""
    values = _values(returns)
    growth = float(np.expm1(np.log1p(values).sum()))
    if growth <= -1.0:
        raise EvalError("区间净值不是正数，年化没有定义")
    return float(math.exp(math.log1p(growth) * TRADING_DAYS / len(values)) - 1.0)


def compound_return(returns) -> float:
    values = _values(returns)
    return float(np.expm1(np.log1p(values).sum()))
