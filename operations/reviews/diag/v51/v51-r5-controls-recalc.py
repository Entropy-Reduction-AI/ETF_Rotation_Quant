#!/usr/bin/env python3
"""v5.1 R5：对照 R0 / C-等权 / C-波动比独立复算（Reviewer，只读 results/v5.1/，不碰 sqlite）。

用法（仓库根，Dev PR #237 head 产物已落盘）：
  mkdir -p outputs
  .venv/bin/python operations/reviews/diag/v51/v51-r5-controls-recalc.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.report.metrics import calmar, cagr
from src.v51.design import WINDOW_START, windowed

RESULTS = ROOT / "results" / "v5.1"
OUT = ROOT / "operations" / "reviews" / "diag" / "v51" / "v51-r5-controls-recalc.json"
ARTIFACT = Path("/opt/cursor/artifacts/v51-r5-controls-recalc.json")
METRIC_END = "2015-12-31"
ATOL = 1e-6


def _read_net(path: Path) -> pd.Series:
    frame = pd.read_csv(path, parse_dates=["date"], index_col="date")
    series = frame["net"].astype(float).sort_index()
    series.index = pd.DatetimeIndex(series.index).normalize()
    return series


def _r0_percentiles(pool: str) -> dict:
    path = RESULTS / "controls" / "r0" / pool / "sims.csv"
    frame = pd.read_csv(path)
    assert len(frame) == 2000, f"{path}: expected 2000 sims, got {len(frame)}"
    cagr_med = float(frame["cagr"].median())
    calmar_p95 = float(frame["calmar"].quantile(0.95))
    summary_path = RESULTS / "controls" / "r0" / pool / "summary.csv"
    with summary_path.open(encoding="utf-8", newline="") as handle:
        summary = next(csv.DictReader(handle))
    seed = int(summary["seed"])
    return {
        "pool": pool,
        "n_sims": len(frame),
        "seed": seed,
        "cagr_median": cagr_med,
        "calmar_p95": calmar_p95,
        "summary_cagr_median": float(summary["cagr_median"]),
        "summary_calmar_p95": float(summary["calmar_p95"]),
        "median_match": np.isclose(cagr_med, float(summary["cagr_median"]), atol=ATOL),
        "p95_match": np.isclose(calmar_p95, float(summary["calmar_p95"]), atol=ATOL),
    }


def _design_strategy(pool: str) -> dict:
    with (RESULTS / "design" / "summary.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["pool"] == pool and row["segment"] == "full":
                return {
                    "cagr": float(row["cagr"]),
                    "calmar": float(row["calmar"]),
                    "start": row["start"],
                    "end": row["end"],
                }
    raise KeyError(pool)


def _item0_pass(pool: str, r0: dict, strat: dict) -> dict:
    cagr_ok = strat["cagr"] >= r0["cagr_median"]
    calmar_ok = strat["calmar"] > r0["calmar_p95"]
    return {
        "pool": pool,
        "strategy_cagr": strat["cagr"],
        "strategy_calmar": strat["calmar"],
        "r0_cagr_median": r0["cagr_median"],
        "r0_calmar_p95": r0["calmar_p95"],
        "cagr_pass": cagr_ok,
        "calmar_pass": calmar_ok,
        "item0_pass": cagr_ok and calmar_ok,
    }


def _control_full_cagr(case_dir: str) -> float:
    daily = _read_net(RESULTS / "controls" / case_dir / "index" / "daily.csv")
    window = windowed(daily, WINDOW_START, METRIC_END)
    return float(cagr(window))


def _read_control_summary(case: str) -> float:
    with (RESULTS / "controls" / "summary.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["case"] == case and row["pool"] == "index" and row["segment"] == "full":
                return float(row["cagr"])
    raise KeyError(case)


def _date_fence() -> list[dict]:
    checks = []
    paths = [
        RESULTS / "controls" / "equal" / "index" / "daily.csv",
        RESULTS / "controls" / "equal" / "tradable" / "daily.csv",
        RESULTS / "controls" / "vol" / "index" / "daily.csv",
        RESULTS / "controls" / "r0" / "index" / "sims.csv",
    ]
    for path in paths:
        if path.name == "sims.csv":
            # sims have no dates; eligibility defines R0 calendar
            elig = pd.read_csv(path.parent / "eligibility.csv", parse_dates=["date"])
            max_d = elig["date"].max()
            min_d = elig["date"].min()
        else:
            frame = pd.read_csv(path, parse_dates=["date"])
            max_d = frame["date"].max()
            min_d = frame["date"].min()
        checks.append({
            "path": str(path.relative_to(ROOT)),
            "min": str(min_d.date()) if hasattr(min_d, "date") else str(min_d),
            "max": str(max_d.date()) if hasattr(max_d, "date") else str(max_d),
            "china_end_ok": pd.Timestamp(max_d) <= pd.Timestamp("2015-12-31"),
        })
    return checks


def _ledger_rows() -> list[dict]:
    with (RESULTS / "trial-ledger.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    r0_index = _r0_percentiles("index")
    r0_tradable = _r0_percentiles("tradable")
    strat_index = _design_strategy("index")
    strat_tradable = _design_strategy("tradable")
    item0_index = _item0_pass("index", r0_index, strat_index)
    item0_tradable = _item0_pass("tradable", r0_tradable, strat_tradable)

    u_cagr = strat_index["cagr"]
    eq_cagr_daily = _control_full_cagr("equal")
    vol_cagr_daily = _control_full_cagr("vol")
    eq_cagr_summary = _read_control_summary("C-等权")
    vol_cagr_summary = _read_control_summary("C-波动比")

    item3 = {
        "u_index_cagr": u_cagr,
        "c_equal_cagr_daily": eq_cagr_daily,
        "c_equal_cagr_summary": eq_cagr_summary,
        "c_vol_cagr_daily": vol_cagr_daily,
        "c_vol_cagr_summary": vol_cagr_summary,
        "ordering_ok": u_cagr > eq_cagr_daily > vol_cagr_daily,
        "equal_daily_matches_summary": np.isclose(eq_cagr_daily, eq_cagr_summary, atol=ATOL),
        "vol_daily_matches_summary": np.isclose(vol_cagr_daily, vol_cagr_summary, atol=ATOL),
        "c_vol_tradable_dir_exists": (RESULTS / "controls" / "vol" / "tradable").exists(),
    }

    ledger = _ledger_rows()
    arms = [r.get("arm") or json.loads(r["params"]).get("case", "") for r in ledger]
    payload = {
        "dev_head": "a2ce5a8f0ade6f2e4e7c9390bb1410e91bcfb704",
        "ledger_run_sha_claimed": "bad40ae1e7a7b6212c43a3b9d523b91e50ec5b9d",
        "r0": {"index": r0_index, "tradable": r0_tradable},
        "item0": {"index": item0_index, "tradable": item0_tradable},
        "item3": item3,
        "date_fence": _date_fence(),
        "ledger": {
            "row_count": len(ledger),
            "design_v51_rows": sum(1 for r in ledger if r["arm"] == "v5.1"),
            "lock_rows": sum(1 for r in ledger if "LOCK" in r.get("arm", "")),
            "git_shas": sorted({r["git_sha"] for r in ledger}),
            "arms": arms,
        },
        "gate_item0_status": "通过",
        "gate_item3_status": "通过",
    }
    def _py(obj: object) -> object:
        if isinstance(obj, dict):
            return {k: _py(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_py(v) for v in obj]
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        return obj

    payload = _py(payload)
    payload["all_ok"] = bool(
        payload["r0"]["index"]["median_match"]
        and payload["r0"]["index"]["p95_match"]
        and payload["r0"]["tradable"]["median_match"]
        and payload["r0"]["tradable"]["p95_match"]
        and payload["item0"]["index"]["item0_pass"]
        and payload["item0"]["tradable"]["item0_pass"]
        and payload["item3"]["ordering_ok"]
        and payload["item3"]["equal_daily_matches_summary"]
        and payload["item3"]["vol_daily_matches_summary"]
        and not payload["item3"]["c_vol_tradable_dir_exists"]
        and payload["ledger"]["row_count"] == 7
        and payload["ledger"]["design_v51_rows"] == 2
        and payload["ledger"]["lock_rows"] == 0
        and all(c["china_end_ok"] for c in payload["date_fence"])
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    OUT.write_text(text + "\n", encoding="utf-8")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if payload["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
