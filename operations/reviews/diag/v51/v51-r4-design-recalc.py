#!/usr/bin/env python3
"""v5.1 R4：设计期两池指标独立复算（Reviewer，只读 results/v5.1/design/，不碰 sqlite）。

用法（仓库根，需 Dev R4 产物已落盘）：
  mkdir -p outputs
  .venv/bin/python operations/reviews/diag/v51/v51-r4-design-recalc.py
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

from src.report.metrics import calmar, cagr, max_drawdown, monthly_returns
from src.v4.scorecard.gate import SEGMENTS, state_points
from src.v51.design import WINDOW_START, market_states, monthly_excess_t, t_of, windowed

DESIGN = ROOT / "results" / "v5.1" / "design"
OUT = ROOT / "operations" / "reviews" / "diag" / "v51" / "v51-r4-design-recalc.json"
ARTIFACT = Path("/opt/cursor/artifacts/v51-r4-design-recalc.json")
RTOL = 1e-9
ATOL = 1e-6

WINDOWS = (("full", WINDOW_START, "2015-12-31"),) + tuple(SEGMENTS)
POOLS = ("index", "tradable")


def _read_net(path: Path) -> pd.Series:
    frame = pd.read_csv(path, parse_dates=["date"], index_col="date")
    series = frame["net"].astype(float).sort_index()
    series.index = pd.DatetimeIndex(series.index).normalize()
    return series


def _read_benchmark() -> pd.Series:
    frame = pd.read_csv(DESIGN / "benchmark.csv", parse_dates=["date"], index_col="date")
    series = frame["benchmark"].astype(float).sort_index()
    series.index = pd.DatetimeIndex(series.index).normalize()
    return series


def _read_summary() -> dict[tuple[str, str], dict]:
    out = {}
    with (DESIGN / "summary.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = (row["pool"], row["segment"])
            out[key] = {k: float(row[k]) if k in {
                "cagr", "max_drawdown", "calmar", "bm_cagr", "bm_max_drawdown",
                "bm_calmar", "monthly_excess_t",
            } else row[k] for k, v in row.items()}
    return out


def _metric_block(pool: str, segment: str, start: str, end: str,
                  strategy: pd.Series, benchmark: pd.Series) -> dict:
    left = windowed(strategy, start, end)
    right = windowed(benchmark, start, end)
    depth_s = max_drawdown(left)
    depth_b = max_drawdown(right)
    excess_t, n_months = monthly_excess_t(left, right)
    return {
        "pool": pool,
        "segment": segment,
        "cagr": cagr(left),
        "max_drawdown": depth_s["max_drawdown"],
        "calmar": calmar(left),
        "bm_cagr": cagr(right),
        "bm_max_drawdown": depth_b["max_drawdown"],
        "bm_calmar": calmar(right),
        "monthly_excess_t": excess_t,
        "n": int(len(left)),
        "n_months": n_months,
    }


def _date_fence() -> dict:
    files = []
    for pool in POOLS:
        for name in ("daily.csv", "decisions.csv", "held.csv"):
            files.append(DESIGN / pool / name)
    report = {}
    for path in files:
        frame = pd.read_csv(path, parse_dates=["date"])
        dates = pd.to_datetime(frame["date"])
        report[str(path.relative_to(ROOT))] = {
            "min": str(dates.min().date()),
            "max": str(dates.max().date()),
        }
    return report


def main() -> int:
    if not (DESIGN / "summary.csv").is_file():
        print("missing design summary", file=sys.stderr)
        return 2

    benchmark = _read_benchmark()
    summary = _read_summary()
    nets = {pool: _read_net(DESIGN / pool / "daily.csv") for pool in POOLS}

    metrics = []
    mismatches = []
    for pool in POOLS:
        for segment, start, end in WINDOWS:
            block = _metric_block(pool, segment, start, end, nets[pool], benchmark)
            metrics.append(block)
            ref = summary[(pool, segment)]
            for key in ("cagr", "max_drawdown", "calmar", "bm_cagr", "bm_max_drawdown",
                        "bm_calmar", "monthly_excess_t"):
                got = block[key]
                want = float(ref[key])
                if not np.isclose(got, want, rtol=RTOL, atol=ATOL):
                    mismatches.append({
                        "pool": pool, "segment": segment, "metric": key,
                        "got": got, "want": want, "delta": got - want,
                    })

    states = pd.read_csv(DESIGN / "month-states.csv", parse_dates=["month_end"], index_col="month_end")
    states = states["state"].sort_index()
    gate6 = market_states(nets["index"], benchmark, states)

    payload = {
        "head_note": "复算基于 checkout 上的 results/v5.1/design/",
        "date_fence": _date_fence(),
        "metrics": metrics,
        "summary_mismatches": mismatches,
        "gate_item_6_index": gate6,
        "pr_body_spot": {
            "index_full": {
                "cagr_pct": round(metrics[0]["cagr"] * 100, 2),
                "mdd_pct": round(metrics[0]["max_drawdown"] * 100, 2),
                "calmar": round(metrics[0]["calmar"], 2),
            },
            "tradable_full": {
                "cagr_pct": round(metrics[3]["cagr"] * 100, 2),
                "mdd_pct": round(metrics[3]["max_drawdown"] * 100, 2),
                "calmar": round(metrics[3]["calmar"], 2),
            },
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    OUT.write_text(text + "\n", encoding="utf-8")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(text + "\n", encoding="utf-8")

    if mismatches:
        print("MISMATCH", len(mismatches), file=sys.stderr)
        return 1
    print("OK", len(metrics), "blocks;", "gate6 p_bull", gate6.get("牛市"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
