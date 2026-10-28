"""§6.2 候选过关和 §6.3 ⑤ 尝试次数。不读真实候选收益，也不写 ledger。"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd

from src.v3.eval.common import C1_SHADOW_ARM, EXPLORATION_TRIALS, ORCHESTRATOR_DIAGNOSTIC_TRIALS
from src.v3.engine.spec import LEDGER

from .core import STATE_ORDER, ScorecardError, classify_months, refuse_portfolio_dates

# 段内年化与 v3 §6 ① 相同：(1+R)^(252/n) − 1。
TRADING_DAYS = 252
SEGMENTS = (
    ("s1", "2006-01-01", "2010-12-31"),
    ("s2", "2011-01-01", "2015-12-31"),
)
# 目标状态：T1 反弹，T2 回调，T3 牛市，T4 牛市。
TARGET_STATE = {"T1": "反弹", "T2": "回调", "T3": "牛市", "T4": "牛市"}
RUN_ORDER = ("B0", "T1", "T2", "T3", "T4")
GATE_COLUMNS = (
    "arm", "pool", "ann_excess_s1", "ann_excess_s2",
    "pp_bull", "pp_correction", "pp_bear", "pp_rebound",
    "pass_segments", "pass_target", "pass_bear", "pass",
)
V4_LEDGER = LEDGER.parent.parent / "v4" / "trial-ledger.csv"
_OFFSET = EXPLORATION_TRIALS + ORCHESTRATOR_DIAGNOSTIC_TRIALS


def _annualized(values: np.ndarray) -> float:
    growth = float(np.expm1(np.log1p(values).sum()))
    if growth <= -1.0:
        return float("nan")
    return float(np.exp(np.log1p(growth) * TRADING_DAYS / len(values)) - 1.0)


def _segment_excess(strategy: pd.Series, benchmark: pd.Series, start: str, end: str) -> float:
    """A_X(S) = (1+R_X)^(252/n) − (1+R_B)^(252/n)。两列用同一段、同一个 n。"""
    both = pd.concat([
        strategy.rename("strategy"),
        benchmark.rename("benchmark"),
    ], axis=1).dropna().sort_index()
    both = both.loc[start:end]
    if len(both) == 0:
        return float("nan")
    left = both["strategy"].to_numpy(dtype=float)
    right = both["benchmark"].to_numpy(dtype=float)
    return _annualized(left) - _annualized(right)


def _state_labels(index: pd.DatetimeIndex, states: pd.Series) -> np.ndarray:
    """每个交易日用它所在月份的状态。月份标签来自 classify_months 的月末索引。"""
    by_month = states.copy()
    by_month.index = pd.DatetimeIndex(pd.to_datetime(by_month.index)).to_period("M")
    by_month = by_month[~by_month.index.duplicated(keep="last")]
    periods = pd.DatetimeIndex(index).to_period("M")
    return by_month.reindex(periods).to_numpy()


def _excess(strategy: pd.Series, benchmark: pd.Series) -> pd.Series:
    """两列都有数的交易日。缺一天就两边都不算，避免把基准缺日当成 0。"""
    both = pd.concat([
        strategy.rename("strategy"),
        benchmark.rename("benchmark"),
    ], axis=1).dropna().sort_index()
    return both["strategy"] - both["benchmark"]


def state_points(excess: pd.Series, states: pd.Series) -> dict[str, float]:
    """P_X(状态) = 100 × Σ e_X(t)，不四舍五入。没有该状态的月份记 0。"""
    labels = _state_labels(pd.DatetimeIndex(excess.index), states)
    values = excess.to_numpy(dtype=float)
    out = {}
    for name in STATE_ORDER:
        mask = labels == name
        total = float(values[mask].sum()) if mask.any() else 0.0
        out[name] = 100.0 * total
    return out


def candidate_gate(returns: pd.DataFrame, benchmark: pd.Series, states: pd.Series, *,
                   pool: str = "index") -> pd.DataFrame:
    """§6.2。`returns` 的列是 B0 和 T1–T4 的 A 臂日净收益。`arm` 列写运行名。

    B0 的 pass 四列留空。只接受调用方给的序列，不读行情库，也不算 2016 年以后的收益。
    """
    frame = returns.sort_index()
    bench = benchmark.sort_index()
    refuse_portfolio_dates(frame.index, what="候选日收益")
    refuse_portfolio_dates(bench.index, what="BM-主")
    if "B0" not in frame.columns:
        raise ScorecardError("candidate_gate 需要 B0 列")
    unknown = [name for name in frame.columns if name not in RUN_ORDER]
    if unknown:
        raise ScorecardError(f"不认识的运行 {unknown}")
    if not isinstance(states, pd.Series) or len(states) == 0:
        raise ScorecardError("需要 classify_months 给出的月份状态")
    b0 = frame["B0"].astype(float)
    b0_ann = {key: _segment_excess(b0, bench, start, end) for key, start, end in SEGMENTS}
    b0_points = state_points(_excess(b0, bench), states)
    rows = []
    for name in RUN_ORDER:
        if name not in frame.columns:
            continue
        series = frame[name].astype(float)
        points = b0_points if name == "B0" else state_points(_excess(series, bench), states)
        ann = {key: _segment_excess(series, bench, start, end) for key, start, end in SEGMENTS}
        row = {
            "arm": name,
            "pool": pool,
            "ann_excess_s1": ann["s1"] if name != "B0" else b0_ann["s1"],
            "ann_excess_s2": ann["s2"] if name != "B0" else b0_ann["s2"],
            "pp_bull": points["牛市"],
            "pp_correction": points["回调"],
            "pp_bear": points["熊市"],
            "pp_rebound": points["反弹"],
        }
        if name == "B0":
            row["pass_segments"] = None
            row["pass_target"] = None
            row["pass_bear"] = None
            row["pass"] = None
        else:
            segments_ok = bool(ann["s1"] > b0_ann["s1"] and ann["s2"] > b0_ann["s2"])
            target = TARGET_STATE[name]
            target_ok = bool(points[target] > b0_points[target])
            bear_ok = bool(points["熊市"] >= b0_points["熊市"] - 10.0)
            row["pass_segments"] = segments_ok
            row["pass_target"] = target_ok
            row["pass_bear"] = bear_ok
            row["pass"] = bool(segments_ok and target_ok and bear_ok)
        rows.append(row)
    out = pd.DataFrame(rows, columns=list(GATE_COLUMNS))
    for column in ("pass_segments", "pass_target", "pass_bear", "pass"):
        out[column] = out[column].astype(object)
    return out


def states_from_index(level: pd.Series) -> pd.Series:
    """给手造的沪深300 收盘。真实候选不要从这里喂。"""
    refuse_portfolio_dates(level.index, what="状态指数")
    return classify_months(level)


def _deduped(path: Path | None) -> list[dict]:
    if path is None or not Path(path).exists():
        return []
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    seen = set()
    kept = []
    for row in rows:
        key = (row.get("arm") or "", row.get("params") or "", row.get("segment") or "")
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept


def attempt_count(v3_ledger: Path | None = None, v4_ledger: Path | None = None) -> int:
    """§6.3 ⑤。两个 ledger 各自按 arm、params、segment 去重后相加，再减去 C1-shadow。

    文件不存在当作 0 行。不创建、不修改文件。只有 v3 ledger 时与补充文本 A3 的
    `trial_count()` 一致（现有文件没有重复行、也没有 C1-shadow）。
    """
    v3_path = LEDGER if v3_ledger is None else Path(v3_ledger)
    v4_path = V4_LEDGER if v4_ledger is None else Path(v4_ledger)
    rows = _deduped(v3_path) + _deduped(v4_path)
    shadow = sum(1 for row in rows if (row.get("arm") or "") == C1_SHADOW_ARM)
    return len(rows) - shadow + _OFFSET
