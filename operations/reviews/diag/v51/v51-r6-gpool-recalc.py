#!/usr/bin/env python3
"""v5.1 R6：G 池 §6.3-5 独立复算（Reviewer，只读 results/v5.1/other-market/，不碰 sqlite）。

用法（仓库根，Dev PR #239 head 产物已落盘）：
  mkdir -p outputs
  .venv/bin/python operations/reviews/diag/v51/v51-r6-gpool-recalc.py
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

RESULTS = ROOT / "results" / "v5.1" / "other-market"
OUT = ROOT / "operations" / "reviews" / "diag" / "v51" / "v51-r6-gpool-recalc.json"
ARTIFACT = Path("/opt/cursor/artifacts/v51-r6-gpool-recalc.json")
ATOL = 1e-6
WINDOW_END = "2026-09-30"


def _read_net(path: Path) -> pd.Series:
    frame = pd.read_csv(path, parse_dates=["date"], index_col="date")
    series = frame["net"].astype(float).sort_index()
    series.index = pd.DatetimeIndex(series.index).normalize()
    return series


def _summary_row(case: str, segment: str = "full") -> dict[str, str]:
    with (RESULTS / "summary.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["case"] == case and row["segment"] == segment:
                return row
    raise KeyError((case, segment))


def _match(computed: float, summary_key: str, row: dict[str, str]) -> dict:
    ref = float(row[summary_key])
    return {
        "computed": computed,
        "summary": ref,
        "match": bool(np.isclose(computed, ref, atol=ATOL)),
    }


def _r0_percentiles() -> dict:
    sims = pd.read_csv(RESULTS / "r0" / "sims.csv")
    assert len(sims) == 2000, f"expected 2000 sims, got {len(sims)}"
    calmar_p95 = float(sims["calmar"].quantile(0.95))
    cagr_med = float(sims["cagr"].median())
    with (RESULTS / "r0" / "summary.csv").open(encoding="utf-8", newline="") as handle:
        summary = next(csv.DictReader(handle))
    return {
        "n_sims": len(sims),
        "seed": int(summary["seed"]),
        "cagr_median": cagr_med,
        "calmar_p95": calmar_p95,
        "summary_calmar_p95": float(summary["calmar_p95"]),
        "p95_match": bool(np.isclose(calmar_p95, float(summary["calmar_p95"]), atol=ATOL)),
    }


def _ledger_rows() -> list[dict]:
    with (ROOT / "results" / "v5.1" / "trial-ledger.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    v51_rets = _read_net(RESULTS / "v51" / "daily.csv")
    e2_rets = _read_net(RESULTS / "e2" / "daily.csv")
    a1_rets = _read_net(RESULTS / "a1" / "daily.csv")
    bm_rets = _read_net(RESULTS / "benchmark.csv")

    v51_cagr = float(cagr(v51_rets))
    v51_calmar = float(calmar(v51_rets))
    row_v51 = _summary_row("v5.1")

    r0 = _r0_percentiles()
    bm_cagr = float(cagr(bm_rets))
    row_bm = _summary_row("BM-G")

    item5 = {
        "calmar_pass": v51_calmar > r0["calmar_p95"],
        "cagr_pass": v51_cagr > bm_cagr,
        "strategy_calmar": v51_calmar,
        "hurdle_calmar_p95": r0["calmar_p95"],
        "strategy_cagr": v51_cagr,
        "hurdle_bm_cagr": bm_cagr,
    }

    controls = {
        "E2_cagr": _match(float(cagr(e2_rets)), "cagr", _summary_row("E2式")),
        "A1_cagr": _match(float(cagr(a1_rets)), "cagr", _summary_row("A1")),
        "BM-G_cagr": _match(bm_cagr, "cagr", row_bm),
    }

    ledger = _ledger_rows()
    other = [r for r in ledger if r.get("segment") == "other-market"]
    manifest = json.loads((RESULTS / "manifest.json").read_text(encoding="utf-8"))

    payload = {
        "dev_head": "2fae1cc8eec1eae7ab93deab19c688d44f3fa264",
        "ledger_run_sha_claimed": "eec5bc04f8054b82d234bc6218c112633dd0e725",
        "window": {
            "start": str(v51_rets.index.min().date()),
            "end": str(v51_rets.index.max().date()),
            "n": len(v51_rets),
        },
        "v51_full": {
            "cagr": _match(v51_cagr, "cagr", row_v51),
            "calmar": _match(v51_calmar, "calmar", row_v51),
        },
        "r0": r0,
        "item5": item5,
        "controls": controls,
        "manifest": {
            "china_pnl": manifest.get("china_pnl"),
            "pool": manifest.get("pool"),
            "robustness": manifest.get("robustness"),
            "lock": manifest.get("lock"),
            "git_sha": manifest.get("git_sha"),
        },
        "ledger": {
            "row_count": len(ledger),
            "other_market_rows": len(other),
            "lock_rows": sum(1 for r in ledger if "LOCK" in r.get("arm", "")),
            "other_arms": sorted({r["arm"] for r in other}),
            "other_git_sha": sorted({r["git_sha"] for r in other}),
        },
        "gate_item5_status": "未通过",
    }

    payload["all_ok"] = bool(
        payload["v51_full"]["cagr"]["match"]
        and payload["v51_full"]["calmar"]["match"]
        and payload["r0"]["p95_match"]
        and payload["controls"]["E2_cagr"]["match"]
        and payload["controls"]["A1_cagr"]["match"]
        and payload["controls"]["BM-G_cagr"]["match"]
        and not payload["item5"]["calmar_pass"]
        and not payload["item5"]["cagr_pass"]
        and payload["manifest"]["china_pnl"] is False
        and payload["manifest"]["robustness"] is False
        and payload["manifest"]["lock"] is False
        and payload["ledger"]["other_market_rows"] == 4
        and payload["ledger"]["lock_rows"] == 0
        and payload["window"]["end"] == WINDOW_END
    )

    text = json.dumps(payload, indent=2, ensure_ascii=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text + "\n", encoding="utf-8")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if payload["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
