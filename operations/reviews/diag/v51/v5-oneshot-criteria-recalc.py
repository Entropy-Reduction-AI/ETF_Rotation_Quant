#!/usr/bin/env python3
"""Independent oneshot criteria.csv recalc (Reviewer D34-4/5).

Reads published net.csv + month-states.csv only. Does not import src.v51.oneshot
criteria builder helpers (_criteria_row, run_oneshot, _store_arm).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.report.metrics import cagr, max_drawdown, monthly_returns
from src.v3.eval.common import (
    C1_SHADOW_ARM,
    EXPLORATION_TRIALS,
    ORCHESTRATOR_DIAGNOSTIC_TRIALS,
    annualized_return,
)
from src.v3.eval.windows import engineering_check_1, rolling_windows
from src.v4.scorecard.core import STATE_ORDER
from src.v4.scorecard.gate import _deduped, state_points
from src.v51.design import t_of

OUT = ROOT / "results" / "v5" / "oneshot"
WINDOW_START = "2016-01-01"
WINDOW_END = "2026-09-30"
HURDLE_T = -2.0
POOLS = ("index", "tradable")
POOL_LABEL = {"index": "U-指数", "tradable": "U-可交易"}
PRIMARY = "E2-B0"
ARM_ROLE = {
    "E2-B0": "入围",
    "A1": "对照",
    "A2": "对照",
    "v5.1-对照": "对照",
}
BENCHMARKS = ("BM-main", "HS300", "SPX", "NDX")
NUMERIC_COLS = [
    "cagr", "max_drawdown", "n", "median_36", "median_60", "fraction_positive_60",
    "n_36", "n_60", "pp_bull", "pp_correction", "pp_bear", "pp_rebound", "rebound_t", "rebound_n",
]


def load_net(path: Path) -> pd.Series:
    frame = pd.read_csv(path, parse_dates=["date"], index_col="date")
    series = frame["net"].astype(float).sort_index()
    block = series.loc[WINDOW_START:WINDOW_END]
    if block.empty:
        raise RuntimeError(f"empty window in {path}")
    return block


def load_states() -> pd.Series:
    frame = pd.read_csv(OUT / "month-states.csv", parse_dates=["month_end"])
    states = frame.set_index("month_end")["state"].astype(str)
    states.index = pd.DatetimeIndex(states.index)
    return states


def is_formal(arm: str, pool: str) -> bool:
    return arm == PRIMARY and pool == "index"


def criterion_1(strategy: pd.Series, benchmark: pd.Series) -> dict:
    both = pd.concat([
        strategy.rename("strategy"),
        benchmark.rename("benchmark"),
    ], axis=1).dropna().sort_index()
    calendar = pd.DatetimeIndex(both.index)

    def records(months: int) -> list[dict]:
        rows = []
        for start, end in rolling_windows(calendar, months, end_limit=WINDOW_END):
            if pd.Timestamp(start) < pd.Timestamp(WINDOW_START):
                continue
            days = calendar[(calendar >= start) & (calendar <= end)]
            left = both["strategy"].reindex(days)
            right = both["benchmark"].reindex(days)
            if left.isna().any() or right.isna().any():
                continue
            ann_s = annualized_return(left.to_numpy())
            ann_b = annualized_return(right.to_numpy())
            rows.append(ann_s - ann_b)
        return rows

    excess_36 = records(36)
    excess_60 = records(60)
    median_36 = None if not excess_36 else float(np.median(excess_36))
    median_60 = None if not excess_60 else float(np.median(excess_60))
    fraction = None if not excess_60 else float(np.mean(np.asarray(excess_60) > 0.0))
    return {
        "n_36": len(excess_36),
        "n_60": len(excess_60),
        "median_36": median_36,
        "median_60": median_60,
        "fraction_positive_60": fraction,
        "pass_1": bool(engineering_check_1(median_36, median_60, fraction)),
    }


def criterion_6(strategy: pd.Series, benchmark: pd.Series, states: pd.Series) -> dict:
    both = pd.concat([
        strategy.rename("strategy"),
        benchmark.rename("benchmark"),
    ], axis=1).dropna().sort_index()
    excess = both["strategy"] - both["benchmark"]
    points = state_points(excess, states)
    labels = states.copy()
    labels.index = pd.DatetimeIndex(pd.to_datetime(labels.index)).to_period("M")
    labels = labels[~labels.index.duplicated(keep="last")]
    paired = pd.concat([
        monthly_returns(both["strategy"]).rename("strategy"),
        monthly_returns(both["benchmark"]).rename("benchmark"),
    ], axis=1).dropna()
    month_excess = paired["strategy"] - paired["benchmark"]
    rebound = month_excess[labels.reindex(month_excess.index) == "反弹"]
    rebound_t = t_of(rebound)
    pass_bull = bool(points["牛市"] >= 0.0)
    pass_rebound = bool(math.isfinite(rebound_t) and rebound_t >= HURDLE_T)
    return {
        **{name: float(points[name]) for name in STATE_ORDER},
        "rebound_t": rebound_t,
        "rebound_n": int(len(rebound)),
        "pass_bull": pass_bull,
        "pass_rebound": pass_rebound,
        "pass_6": bool(pass_bull and pass_rebound),
    }


def summary_numbers(series: pd.Series) -> dict:
    depth = max_drawdown(series)
    return {"cagr": cagr(series), "max_drawdown": depth["max_drawdown"], "n": int(len(series))}


def build_row(pool: str | None, arm: str, numbers: dict, rule1: dict | None, rule6: dict | None) -> dict:
    formal = is_formal(arm, pool or "")
    row = {
        "pool": pool or "",
        "pool_label": "" if pool is None else POOL_LABEL[pool],
        "arm": arm,
        "role": ARM_ROLE.get(arm, "对照"),
        "contender": arm == PRIMARY,
        "formal": formal,
        "cagr": numbers["cagr"],
        "max_drawdown": numbers["max_drawdown"],
        "n": numbers["n"],
        "median_36": None if rule1 is None else rule1["median_36"],
        "median_60": None if rule1 is None else rule1["median_60"],
        "fraction_positive_60": None if rule1 is None else rule1["fraction_positive_60"],
        "n_36": None if rule1 is None else rule1["n_36"],
        "n_60": None if rule1 is None else rule1["n_60"],
        "pass_1": None if rule1 is None or not formal else rule1["pass_1"],
        "pp_bull": None if rule6 is None else rule6["牛市"],
        "pp_correction": None if rule6 is None else rule6["回调"],
        "pp_bear": None if rule6 is None else rule6["熊市"],
        "pp_rebound": None if rule6 is None else rule6["反弹"],
        "rebound_t": None if rule6 is None else rule6["rebound_t"],
        "rebound_n": None if rule6 is None else rule6["rebound_n"],
        "pass_bull": None if rule6 is None or not formal else rule6["pass_bull"],
        "pass_rebound": None if rule6 is None or not formal else rule6["pass_rebound"],
        "pass_6": None if rule6 is None or not formal else rule6["pass_6"],
        "pass": None,
    }
    if formal and rule1 is not None and rule6 is not None:
        row["pass"] = bool(rule1["pass_1"] and rule6["pass_6"])
    return row


def attempt_inventory() -> dict:
    v3 = _deduped(ROOT / "results/v3/trial-ledger.csv")
    v4 = _deduped(ROOT / "results/v4/trial-ledger.csv")
    v5_path = ROOT / "results/v5/trial-ledger.csv"
    v51_path = ROOT / "results/v5.1/trial-ledger.csv"
    v5 = _deduped(v5_path) if v5_path.is_file() else []
    v51 = _deduped(v51_path) if v51_path.is_file() else []
    shadow = sum(1 for row in v3 + v4 if (row.get("arm") or "") == C1_SHADOW_ARM)
    l3, l4 = len(v3), len(v4)
    l5_v5 = len(v5)
    # Inventory: design + other-market rows on v5.1 ledger (deduped), for cross-check only.
    v51_design_om = [r for r in v51 if json.loads(r.get("params") or "{}").get("kind") in ("design", "other-market")]
    l5_dev_style = l5_v5  # oneshot uses only v5 ledger on tree
    count_dev = l3 + l4 + l5_dev_style - shadow + EXPLORATION_TRIALS + ORCHESTRATOR_DIAGNOSTIC_TRIALS + 1
    return {
        "L3": l3,
        "L4": l4,
        "L5_v5_ledger": l5_v5,
        "L5_dev_oneshot": l5_dev_style,
        "C": shadow,
        "exploration": EXPLORATION_TRIALS,
        "diagnostic": ORCHESTRATOR_DIAGNOSTIC_TRIALS,
        "evidence": 1,
        "attempts_dev_formula": count_dev,
        "v5_ledger_present": v5_path.is_file(),
        "v51_dedup_rows_total": len(v51),
        "v51_design_other_market_dedup": len(v51_design_om),
        "v51_arms_design_om": sorted({r.get("arm") for r in v51_design_om}),
    }


def _blank(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _norm_string(value) -> str:
    blank = _blank(value)
    return "" if blank is None else str(blank)


def close(a, b) -> bool:
    a, b = _blank(a), _blank(b)
    if a is None or b is None:
        return a is b
    if isinstance(a, (bool, np.bool_)) or isinstance(b, (bool, np.bool_)):
        return bool(a) == bool(b)
    # Dev CSV uses float_format="%.12g"; allow one ULP past that display.
    return bool(np.isclose(float(a), float(b), rtol=0, atol=5e-7))


def main() -> int:
    states = load_states()
    bm = load_net(OUT / "benchmarks/BM-main/net.csv")
    rows = []
    for name in BENCHMARKS:
        net = load_net(OUT / f"benchmarks/{name}/net.csv")
        rows.append(build_row(None, name, summary_numbers(net), None, None))
    for pool in POOLS:
        for arm in ("E2-B0", "v5.1-对照", "A1", "A2"):
            net = load_net(OUT / pool / arm / "net.csv")
            nums = summary_numbers(net)
            rule1 = criterion_1(net, bm.reindex(net.index))
            rule6 = criterion_6(net, bm, states)
            rows.append(build_row(pool, arm, nums, rule1, rule6))
    got = pd.DataFrame(rows)
    dev = pd.read_csv(OUT / "criteria.csv")
    for frame in (got, dev):
        frame["pool"] = frame["pool"].fillna("").astype(str)
        frame["pool_label"] = frame["pool_label"].fillna("").astype(str)
    key = ["pool", "arm"]
    merged = dev.merge(got, on=key, suffixes=("_dev", "_got"), how="outer", indicator=True)
    if (merged["_merge"] != "both").any():
        raise RuntimeError(f"criteria row keys mismatch: {merged['_merge'].value_counts().to_dict()}")
    mismatches = []
    string_cols = {"pool", "pool_label", "arm", "role"}
    bool_cols = {"contender", "formal", "pass_1", "pass_bull", "pass_rebound", "pass_6", "pass"}
    for _, row in merged.iterrows():
        for col in dev.columns:
            if col in key:
                continue
            left, right = row[f"{col}_got"], row[f"{col}_dev"]
            if col in string_cols:
                ok = _norm_string(left) == _norm_string(right)
            else:
                ok = close(left, right)
            if not ok:
                mismatches.append({
                    "arm": row["arm"],
                    "pool": row["pool"],
                    "col": col,
                    "dev": right,
                    "got": left,
                })
    report = {
        "window": [WINDOW_START, WINDOW_END],
        "criteria_rows": len(dev),
        "all_match": len(mismatches) == 0,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:20],
        "attempts": attempt_inventory(),
        "formal_pass": bool(got.loc[(got.arm == PRIMARY) & (got.pool == "index"), "pass"].iloc[0]),
    }
    out_json = Path(__file__).with_suffix(".json")
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["all_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
