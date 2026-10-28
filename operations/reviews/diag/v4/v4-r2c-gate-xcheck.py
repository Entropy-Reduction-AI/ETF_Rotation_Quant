#!/usr/bin/env python3
"""Independent §6.2 candidate_gate recompute on Dev hand-made fixtures only.

Does not read market DB or real candidate returns.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.v4.scorecard.gate import GATE_COLUMNS, TARGET_STATE, candidate_gate

TRADING_DAYS = 252
SEGMENTS = (
    ("s1", "2006-01-01", "2010-12-31"),
    ("s2", "2011-01-01", "2015-12-31"),
)
STATE_ORDER = ("牛市", "回调", "熊市", "反弹")


def _annualized(values: np.ndarray) -> float:
    growth = float(np.expm1(np.log1p(values).sum()))
    if growth <= -1.0:
        return float("nan")
    return float(np.exp(np.log1p(growth) * TRADING_DAYS / len(values)) - 1.0)


def _segment_excess(strategy: pd.Series, benchmark: pd.Series, start: str, end: str) -> float:
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
    by_month = states.copy()
    by_month.index = pd.DatetimeIndex(pd.to_datetime(by_month.index)).to_period("M")
    by_month = by_month[~by_month.index.duplicated(keep="last")]
    periods = pd.DatetimeIndex(index).to_period("M")
    return by_month.reindex(periods).to_numpy()


def _excess(strategy: pd.Series, benchmark: pd.Series) -> pd.Series:
    both = pd.concat([
        strategy.rename("strategy"),
        benchmark.rename("benchmark"),
    ], axis=1).dropna().sort_index()
    return both["strategy"] - both["benchmark"]


def _state_points(excess: pd.Series, states: pd.Series) -> dict[str, float]:
    labels = _state_labels(pd.DatetimeIndex(excess.index), states)
    values = excess.to_numpy(dtype=float)
    out = {}
    for name in STATE_ORDER:
        mask = labels == name
        total = float(values[mask].sum()) if mask.any() else 0.0
        out[name] = 100.0 * total
    return out


def independent_gate(returns: pd.DataFrame, benchmark: pd.Series, states: pd.Series, *, pool: str) -> pd.DataFrame:
    frame = returns.sort_index()
    bench = benchmark.sort_index()
    b0 = frame["B0"].astype(float)
    b0_ann = {key: _segment_excess(b0, bench, start, end) for key, start, end in SEGMENTS}
    b0_points = _state_points(_excess(b0, bench), states)
    rows = []
    for name in ("B0", "T1", "T2", "T3", "T4"):
        if name not in frame.columns:
            continue
        series = frame[name].astype(float)
        points = b0_points if name == "B0" else _state_points(_excess(series, bench), states)
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
    return pd.DataFrame(rows, columns=list(GATE_COLUMNS))


def _fixture():
    states = pd.Series(
        ["反弹", "熊市", "牛市", "回调"],
        index=pd.to_datetime(["2006-01-31", "2011-01-31", "2006-02-28", "2011-02-28"]),
    )
    index = pd.to_datetime([
        "2006-01-04", "2006-01-05", "2006-02-06", "2006-02-07",
        "2011-01-04", "2011-01-05", "2011-02-08", "2011-02-09",
    ])
    benchmark = pd.Series(0.0, index=index)
    b0 = pd.Series(0.0, index=index)
    t1 = pd.Series(0.0, index=index)
    t1.loc["2006-01-04"] = 0.001
    t1.loc["2006-02-06"] = 0.01
    t1.loc["2011-01-04"] = -0.05
    t1.loc["2011-01-05"] = -0.05
    t1.loc["2011-02-08"] = 0.10
    t1.loc["2011-02-09"] = 0.10
    short = t1.copy()
    short.loc["2011-01-05"] = -0.0500001
    returns = pd.DataFrame({"B0": b0, "T1": t1, "T2": short})
    return returns, benchmark, states


def main() -> int:
    returns, benchmark, states = _fixture()
    dev = candidate_gate(returns, benchmark, states, pool="index")
    ind = independent_gate(returns, benchmark, states, pool="index")
    float_cols = [
        "ann_excess_s1", "ann_excess_s2",
        "pp_bull", "pp_correction", "pp_bear", "pp_rebound",
    ]
    ok = True
    details = []
    for col in GATE_COLUMNS:
        if not dev[col].equals(ind[col]):
            if col in float_cols:
                diff = (dev[col].astype(float) - ind[col].astype(float)).abs()
                if diff.max() > 1e-12:
                    ok = False
                    details.append({"column": col, "max_abs_diff": float(diff.max())})
            else:
                ok = False
                details.append({"column": col, "dev": dev[col].tolist(), "ind": ind[col].tolist()})
    out = {"gate_columns_match": ok, "mismatch": details, "dev_table": dev.to_dict(orient="records")}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
