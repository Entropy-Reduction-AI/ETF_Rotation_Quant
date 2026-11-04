#!/usr/bin/env python3
"""v5.1 wrap-up：R1 / S1–S17 / turnover / gate 独立复算（Reviewer，只读 results/v5.1/ CSV）。

用法（仓库根）：
  mkdir -p outputs
  .venv/bin/python operations/reviews/diag/v51/v51-wrap-recalc.py
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.report.metrics import cagr, calmar
from src.v51.design import WINDOW_START, windowed

RESULTS = ROOT / "results" / "v5.1"
OUT = ROOT / "operations" / "reviews" / "diag" / "v51" / "v51-wrap-recalc.json"
ARTIFACT = Path("/opt/cursor/artifacts/v51-wrap-recalc.json")
METRIC_END = "2015-12-31"
ATOL = 1e-6
DESIGN_CAGR_INDEX = 0.301419149909


def _read_net(path: Path) -> pd.Series:
    frame = pd.read_csv(path, parse_dates=["date"], index_col="date")
    series = frame["net"].astype(float).sort_index()
    series.index = pd.DatetimeIndex(series.index).normalize()
    return series


def _r1_pool(pool: str) -> dict:
    sims_path = RESULTS / "controls" / "r1" / pool / "sims.csv"
    frame = pd.read_csv(sims_path)
    assert len(frame) == 2000, f"{sims_path}: expected 2000 sims, got {len(frame)}"
    cagr_med = float(frame["cagr"].median())
    calmar_p95 = float(frame["calmar"].quantile(0.95))
    with (RESULTS / "controls" / "r1" / pool / "summary.csv").open(encoding="utf-8", newline="") as handle:
        summary = next(csv.DictReader(handle))
    seed = int(summary["seed"])
    strat_cagr = float(summary["v51_cagr"])
    strat_calmar = float(summary["v51_calmar"])
    return {
        "pool": pool,
        "n_sims": len(frame),
        "seed": seed,
        "cagr_median": cagr_med,
        "calmar_p95": calmar_p95,
        "summary_cagr_median": float(summary["cagr_median"]),
        "summary_calmar_p95": float(summary["calmar_p95"]),
        "v51_cagr": strat_cagr,
        "v51_calmar": strat_calmar,
        "median_match": bool(np.isclose(cagr_med, float(summary["cagr_median"]), atol=ATOL)),
        "p95_match": bool(np.isclose(calmar_p95, float(summary["calmar_p95"]), atol=ATOL)),
        "cagr_above_median": strat_cagr >= cagr_med,
        "calmar_above_p95": strat_calmar > calmar_p95,
    }


def _robustness_cases() -> dict:
    path = RESULTS / "robustness" / "summary.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    cases = sorted({r["case"] for r in rows})
    full_rows = [r for r in rows if r["segment"] == "full"]
    return {
        "n_rows": len(rows),
        "cases": cases,
        "n_cases": len(cases),
        "full_rows": len(full_rows),
    }


def _spot_cagr(case: str, pool: str) -> dict:
    daily = _read_net(RESULTS / "robustness" / case / "daily.csv")
    window = windowed(daily, WINDOW_START, METRIC_END)
    calc = float(cagr(window))
    with (RESULTS / "robustness" / "summary.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["case"] == case and row["pool"] == pool and row["segment"] == "full":
                reported = float(row["cagr"])
                return {
                    "case": case,
                    "pool": pool,
                    "cagr_recalc": calc,
                    "cagr_summary": reported,
                    "match": bool(np.isclose(calc, reported, atol=ATOL)),
                }
    raise KeyError((case, pool))


def _turnover_sources(pool: str) -> dict:
    fname = "g.csv" if pool == "G" else f"{pool}.csv"
    path = RESULTS / "turnover" / fname
    frame = pd.read_csv(path)
    sources = set(frame["source"].unique()) - {"合计"}
    expected = {"第一层档位", "换市场", "周度替换", "前沿离场", "硬闸门", "换防守", "未分解"}
    totals = frame[frame["source"] == "合计"]
    by_year = totals[totals["year"] != "全部"]
    grand = totals[totals["year"] == "全部"]
    sum_turn = float(by_year["turnover_one_way"].sum())
    grand_turn = float(grand["turnover_one_way"].iloc[0]) if len(grand) else float("nan")
    return {
        "pool": pool,
        "sources_present": sorted(sources),
        "expected_ok": expected <= sources,
        "year_sum_turnover": sum_turn,
        "grand_total": grand_turn,
        "totals_reconcile": bool(np.isclose(sum_turn, grand_turn, rtol=1e-4, atol=1e-3)),
    }


def _turnover_vs_daily(pool: str) -> dict:
    """Compare index/tradable daily cost sum to turnover 合计 cost (全部)."""
    if pool == "G":
        daily_path = RESULTS / "other-market" / "v51" / "daily.csv"
    else:
        daily_path = RESULTS / "design" / pool / "daily.csv"
    daily = pd.read_csv(daily_path, parse_dates=["date"])
    daily = daily[(daily["date"] >= WINDOW_START) & (daily["date"] <= METRIC_END)]
    cost_sum = float(daily["cost"].sum())
    turn = pd.read_csv(RESULTS / "turnover" / f"{pool}.csv")
    reported_cost = float(turn[(turn["year"] == "全部") & (turn["source"] == "合计")]["cost"].iloc[0])
    return {
        "pool": pool,
        "daily_cost_sum": cost_sum,
        "turnover_total_cost": reported_cost,
        "match": bool(np.isclose(cost_sum, reported_cost, rtol=1e-3, atol=1e-4)),
    }


def _gate_diff() -> dict:
    draft = list(csv.DictReader((RESULTS / "design" / "gate-draft.csv").open(encoding="utf-8")))
    final = list(csv.DictReader((RESULTS / "design" / "gate.csv").open(encoding="utf-8")))
    changed = []
    for i, (d, f) in enumerate(zip(draft, final)):
        if d != f:
            changed.append({"row": i + 2, "item": d.get("item"), "draft_status": d.get("status"), "final_status": f.get("status")})
    entry_draft = draft[-1]
    entry_final = final[-1]
    return {
        "n_draft": len(draft),
        "n_final": len(final),
        "changed_rows": changed,
        "entry_final_status": entry_final.get("status"),
        "entry_final_note": entry_final.get("note"),
        "items_0_4_unchanged": all(
            draft[i]["status"] == final[i]["status"]
            for i in range(len(draft))
            if draft[i]["item"] in {"0", "1", "2", "3", "4", "报告"}
            or (draft[i]["item"] in {"0", "1", "2", "3", "4"} and draft[i]["status"] == final[i]["status"])
        ),
        "items_5_6_fail": all(
            final[i]["status"] == "未通过"
            for i in range(len(final))
            if final[i]["item"] in {"5", "6"} and final[i]["metric"] in {"calmar", "cagr", "p_bull", "rebound_t"}
        ),
    }


def _ledger() -> dict:
    with (RESULTS / "trial-ledger.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    arms = Counter(r["arm"] for r in rows)
    r1 = [r for r in rows if r["arm"] == "R1"]
    s_rows = [r for r in rows if r["arm"].startswith("S")]
    sha_r1 = {r["git_sha"] for r in r1}
    sha_s = {r["git_sha"] for r in s_rows}
    return {
        "total_rows": len(rows),
        "r1_rows": len(r1),
        "s_rows": len(s_rows),
        "arm_counts": dict(arms),
        "r1_sha": sorted(sha_r1),
        "s_sha": sorted(sha_s),
    }


def _china_date_fence() -> list[dict]:
    paths = []
    for case in [f"S{i}" for i in range(1, 18)]:
        paths.append(RESULTS / "robustness" / case / "daily.csv")
    paths += [
        RESULTS / "design" / "index" / "daily.csv",
        RESULTS / "design" / "tradable" / "daily.csv",
        RESULTS / "controls" / "r1" / "index" / "sims.csv",
    ]
    out = []
    for path in paths:
        if path.name == "sims.csv":
            elig = pd.read_csv(path.parent / "eligibility.csv", parse_dates=["date"])
            max_d = elig["date"].max()
        else:
            frame = pd.read_csv(path, parse_dates=["date"])
            max_d = frame["date"].max()
        out.append({"path": str(path.relative_to(ROOT)), "max_date": str(max_d.date())})
    return out


def main() -> None:
    r1_index = _r1_pool("index")
    r1_tradable = _r1_pool("tradable")
    robust = _robustness_cases()
    spots = [_spot_cagr("S1", "index"), _spot_cagr("S2", "index"), _spot_cagr("S17", "tradable")]
    turnover = [_turnover_sources(p) for p in ("index", "tradable", "G")]
    turnover_daily = [_turnover_vs_daily(p) for p in ("index", "tradable")]
    gate = _gate_diff()
    ledger = _ledger()
    fence = _china_date_fence()

    payload = {
        "r1": {"index": r1_index, "tradable": r1_tradable},
        "robustness": robust,
        "spot_cagr": spots,
        "turnover": turnover,
        "turnover_daily_cost": turnover_daily,
        "gate": gate,
        "ledger": ledger,
        "date_fence": fence,
        "design_index_cagr": DESIGN_CAGR_INDEX,
        "s2_above_design": spots[1]["cagr_recalc"] > DESIGN_CAGR_INDEX,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    OUT.write_text(text + "\n", encoding="utf-8")
    ARTIFACT.write_text(text + "\n", encoding="utf-8")
    print(text)
    assert r1_index["median_match"] and r1_index["p95_match"]
    assert r1_tradable["median_match"] and r1_tradable["p95_match"]
    assert robust["n_cases"] == 17
    assert all(s["match"] for s in spots)
    assert gate["entry_final_status"] == "不入围"
    assert all(f["max_date"] <= "2015-12-31" for f in fence if "robustness" in f["path"] or "design" in f["path"])


if __name__ == "__main__":
    main()
