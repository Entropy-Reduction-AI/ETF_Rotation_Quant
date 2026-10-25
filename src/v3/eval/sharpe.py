"""Bailey & López de Prado (2014) 紧缩夏普比率。

David H. Bailey and Marcos López de Prado, "The Deflated Sharpe Ratio:
Correcting for Selection Bias, Backtest Overfitting, and Non-Normality",
Journal of Portfolio Management, 40(5), 94–107, 2014.

非年化夏普（和收益同一频率）::

    SR0 = μ + σ * ((1 − γ) Φ^{-1}(1 − 1/N) + γ Φ^{-1}(1 − 1/(N e)))
    DSR = Φ( (SR − SR0) * sqrt(T − 1) / sqrt(1 − γ3*SR + (γ4 − 1)/4 * SR^2) )

γ 是 Euler–Mascheroni 常数，取论文附录代码里的 0.5772156649。
Φ 是标准正态。γ3 是收益偏度，γ4 是 Pearson 峰度（正态为 3，不是超额峰度）。
§6⑤ 在「真实夏普为 0」的原假设下取 μ = 0。σ² 是各次试验夏普估计的方差，由调用方给出。
N = `results/v3/trial-ledger.csv` 的行数 + §1-2 的 28。数值门槛是 DSR ≥ 0.90。
正式通过与否留到 G3。报告里要注明本段出处。

公开例题（论文 "A Numerical Example"）：年化夏普 2.5，每年 250 个观测，
试验夏普的年化方差 0.5，N = 100，T = 1250，偏度 −3，峰度 10。
换到日频后 SR0 ≈ 0.1132，DSR ≈ 0.9004。N = 46 时 DSR ≈ 0.9505。
收益改成正态（偏度 0、峰度 3）且 N = 88 时 DSR ≈ 0.9505。
"""
from __future__ import annotations

import csv
import math
from pathlib import Path
from statistics import NormalDist

import pandas as pd

from src.v3.engine.spec import LEDGER

from .common import EXPLORATION_TRIALS, EvalError, require_design_period

EULER_MASCHERONI = 0.5772156649
DSR_THRESHOLD = 0.90


def expected_maximum_sharpe(sr_variance: float, n_trials: int, sr_mean: float = 0.0) -> float:
    """原假设下 N 次独立试验的期望最大夏普。σ = sqrt(方差)，μ 默认 0。"""
    if n_trials < 2:
        raise EvalError("试验次数至少为 2")
    if sr_variance < 0.0 or not math.isfinite(sr_variance) or not math.isfinite(sr_mean):
        raise EvalError("夏普的均值或方差不是有限数")
    sigma = math.sqrt(sr_variance)
    normal = NormalDist()
    max_z = (1.0 - EULER_MASCHERONI) * normal.inv_cdf(1.0 - 1.0 / n_trials)
    max_z += EULER_MASCHERONI * normal.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
    return float(sr_mean + sigma * max_z)


def probabilistic_sharpe_ratio(observed_sr: float, benchmark_sr: float, n_obs: int,
                               skew: float, kurtosis: float) -> float:
    """PSR。kurtosis 是 Pearson 峰度。夏普和 benchmark_sr 都必须是非年化的。"""
    if n_obs < 2:
        raise EvalError("样本长度至少为 2")
    inside = 1.0 - skew * observed_sr + ((kurtosis - 1.0) / 4.0) * observed_sr ** 2
    if inside <= 0.0 or not math.isfinite(inside):
        raise EvalError("夏普标准误的根号内不是正数")
    z_score = (observed_sr - benchmark_sr) * math.sqrt(n_obs - 1) / math.sqrt(inside)
    return float(NormalDist().cdf(z_score))


def deflated_sharpe_ratio(observed_sr: float, sr_variance: float, n_trials: int, n_obs: int,
                          skew: float, kurtosis: float, *, sr_mean: float = 0.0) -> dict:
    """DSR 概率。`engineering_check` 只是和 0.90 比大小，不是正式通过。"""
    sr0 = expected_maximum_sharpe(sr_variance, n_trials, sr_mean)
    probability = probabilistic_sharpe_ratio(observed_sr, sr0, n_obs, skew, kurtosis)
    return {
        "probability": probability,
        "sr0": sr0,
        "observed_sr": float(observed_sr),
        "sr_variance": float(sr_variance),
        "n_trials": int(n_trials),
        "n_obs": int(n_obs),
        "skew": float(skew),
        "kurtosis": float(kurtosis),
        "engineering_check": bool(probability >= DSR_THRESHOLD),
        "formal_pass": None,
    }


def sharpe_moments(returns, cash=None) -> dict:
    """非年化夏普 = mean / std(ddof=1)。有现金列时先减现金。

    偏度是 pandas `Series.skew()`。峰度是 `Series.kurtosis()`（超额）加 3，变成 Pearson 峰度。
    """
    series = pd.Series(returns, dtype=float)
    if cash is None:
        values = series.dropna()
        require_design_period(values.index)
    else:
        both = pd.concat([
            series.rename("strategy"),
            pd.Series(cash, dtype=float).rename("cash"),
        ], axis=1).dropna()
        require_design_period(both.index)
        values = both["strategy"] - both["cash"]
    if len(values) < 4:
        raise EvalError("收益短于 4 天，不计算紧缩夏普")
    scale = float(values.std(ddof=1))
    if not math.isfinite(scale) or scale <= 1e-12:
        raise EvalError("收益标准差为 0")
    skew = float(values.skew())
    kurtosis = float(values.kurtosis()) + 3.0
    if not math.isfinite(skew) or not math.isfinite(kurtosis):
        raise EvalError("偏度或峰度不是有限数")
    return {
        "sr": float(values.mean() / scale),
        "skew": skew,
        "kurtosis": kurtosis,
        "n_obs": int(len(values)),
    }


def criterion_5(returns, *, n_trials: int, sr_variance: float, cash=None) -> dict:
    """用这列收益的矩，和调用方给出的试验次数、夏普方差，计算 §6⑤。"""
    moments = sharpe_moments(returns, cash)
    result = deflated_sharpe_ratio(
        moments["sr"], sr_variance, n_trials, moments["n_obs"], moments["skew"], moments["kurtosis"])
    return result


def trial_count(ledger_path: Path | None = None) -> int:
    """ledger 里的数据行数 + 28。文件不存在当作 0 行。不创建文件。"""
    path = LEDGER if ledger_path is None else Path(ledger_path)
    if not path.exists():
        return EXPLORATION_TRIALS
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return len(rows) + EXPLORATION_TRIALS


def variance_of_sharpes(sharpes) -> float:
    """试验夏普的样本方差，ddof=1。至少两个有限数。"""
    series = pd.Series(sharpes, dtype=float).dropna()
    if len(series) < 2:
        raise EvalError("至少要两个试验夏普才有方差")
    return float(series.var(ddof=1))
