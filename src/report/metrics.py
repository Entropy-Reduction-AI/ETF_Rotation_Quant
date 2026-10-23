"""区间指标。年化按 252 个交易日。跟踪误差、beta、相关用月收益。"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _clean(rets: pd.Series) -> pd.Series:
    out = pd.Series(rets, dtype=float).dropna()
    if out.empty:
        raise ValueError("没有收益")
    return out


def cagr(rets: pd.Series) -> float:
    series = _clean(rets)
    nav = float((1.0 + series).prod())
    years = len(series) / TRADING_DAYS
    return nav ** (1.0 / years) - 1.0


def ann_vol(rets: pd.Series) -> float:
    series = _clean(rets)
    if len(series) < 2:
        return math.nan
    return float(series.std(ddof=1) * math.sqrt(TRADING_DAYS))


def max_drawdown(rets: pd.Series) -> dict:
    series = _clean(rets)
    nav = (1.0 + series).cumprod()
    drawdown = nav / nav.cummax() - 1.0
    trough = drawdown.idxmin()
    peak = nav.loc[:trough].idxmax()
    return {
        "max_drawdown": float(drawdown.loc[trough]),
        "peak": pd.Timestamp(peak),
        "trough": pd.Timestamp(trough),
    }


def sharpe(rets: pd.Series, rf: pd.Series) -> float:
    excess = (pd.Series(rets, dtype=float) - pd.Series(rf, dtype=float).reindex(rets.index)).dropna()
    if len(excess) < 2:
        return math.nan
    scale = float(excess.std(ddof=1))
    if scale == 0.0 or math.isnan(scale):
        return math.nan
    return float(excess.mean() / scale * math.sqrt(TRADING_DAYS))


def calmar(rets: pd.Series) -> float:
    depth = max_drawdown(rets)["max_drawdown"]
    if depth == 0.0 or math.isnan(depth):
        return math.nan
    return float(cagr(rets) / abs(depth))


def yearly_returns(rets: pd.Series) -> dict[int, float]:
    series = _clean(rets)
    out = {}
    for year, block in series.groupby(series.index.year):
        out[int(year)] = float((1.0 + block).prod() - 1.0)
    return out


def monthly_returns(rets: pd.Series) -> pd.Series:
    series = _clean(rets)
    grouped = (1.0 + series).groupby(series.index.to_period("M")).prod() - 1.0
    grouped.name = "ret"
    return grouped


def _pair(left: pd.Series, right: pd.Series) -> pd.DataFrame:
    frame = pd.concat([
        pd.Series(left, dtype=float).rename("left"),
        pd.Series(right, dtype=float).rename("right"),
    ], axis=1).dropna()
    if frame.empty:
        raise ValueError("两列收益没有重叠日期")
    return frame


def excess_cagr(left: pd.Series, right: pd.Series) -> float:
    frame = _pair(left, right)
    return cagr(frame["left"]) - cagr(frame["right"])


def tracking_error(left: pd.Series, right: pd.Series) -> float:
    months = _pair(monthly_returns(left), monthly_returns(right))
    if len(months) < 2:
        return math.nan
    return float((months["left"] - months["right"]).std(ddof=1) * math.sqrt(12))


def information_ratio(left: pd.Series, right: pd.Series) -> float:
    error = tracking_error(left, right)
    if error == 0.0 or math.isnan(error):
        return math.nan
    return float(excess_cagr(left, right) / error)


def beta(left: pd.Series, right: pd.Series) -> float:
    months = _pair(monthly_returns(left), monthly_returns(right))
    if len(months) < 2:
        return math.nan
    var = float(months["right"].var(ddof=1))
    if var == 0.0 or math.isnan(var):
        return math.nan
    return float(months["left"].cov(months["right"]) / var)


def monthly_corr(left: pd.Series, right: pd.Series) -> float:
    months = _pair(monthly_returns(left), monthly_returns(right))
    if len(months) < 2:
        return math.nan
    return float(months["left"].corr(months["right"]))


def decay_split(a_design: float, a_oos: float, benchmark_design: float, benchmark_oos: float) -> dict:
    """设计期到样本外的衰减 = 基准自身的变化 + 相对基准的变化。"""
    excess_design = a_design - benchmark_design
    excess_oos = a_oos - benchmark_oos
    total = a_oos - a_design
    benchmark_change = benchmark_oos - benchmark_design
    relative_change = excess_oos - excess_design
    if abs(total - (benchmark_change + relative_change)) > 1e-12:
        raise ValueError("衰减拆分加总不等于总衰减")
    return {
        "a_design": a_design,
        "a_oos": a_oos,
        "benchmark_design": benchmark_design,
        "benchmark_oos": benchmark_oos,
        "excess_design": excess_design,
        "excess_oos": excess_oos,
        "decay_total": total,
        "decay_benchmark": benchmark_change,
        "decay_relative": relative_change,
    }


def performance(rets: pd.Series, rf: pd.Series) -> dict:
    depth = max_drawdown(rets)
    return {
        "cagr": cagr(rets),
        "ann_vol": ann_vol(rets),
        "max_drawdown": depth["max_drawdown"],
        "max_drawdown_peak": str(depth["peak"].date()),
        "max_drawdown_trough": str(depth["trough"].date()),
        "sharpe": sharpe(rets, rf),
        "calmar": calmar(rets),
        "start": str(pd.Timestamp(rets.dropna().index[0]).date()),
        "end": str(pd.Timestamp(rets.dropna().index[-1]).date()),
        "n": int(rets.dropna().shape[0]),
    }


def versus(left: pd.Series, right: pd.Series) -> dict:
    return {
        "excess_cagr": excess_cagr(left, right),
        "tracking_error": tracking_error(left, right),
        "information_ratio": information_ratio(left, right),
        "beta": beta(left, right),
        "monthly_corr": monthly_corr(left, right),
    }
