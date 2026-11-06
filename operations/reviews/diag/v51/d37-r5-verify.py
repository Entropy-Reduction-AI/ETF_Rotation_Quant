#!/usr/bin/env python3
"""D37 round 5 Reviewer 独立复算（只读 #284 产物 + main 同段 V0）。

用法：
  git fetch origin pull/284/head:refs/remotes/origin/pr-284-head
  git worktree add /tmp/d37-r5-pr284 origin/pr-284-head
  cd /tmp/d37-r5-pr284 && git lfs pull -I data/market.sqlite

  cd /agent/repos/ETF_Rotation_Quant
  DEV_WORKTREE=/tmp/d37-r5-pr284 \\
    python operations/reviews/diag/v51/d37-r5-verify.py

写入 operations/reviews/diag/v51/d37-r5-recalc.json。
不修改 Dev 分支、不 push `cursor/d37-r5`。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
DEV = Path(os.environ.get("DEV_WORKTREE", "/tmp/d37-r5-pr284"))
OUT_JSON = ROOT / "operations/reviews/diag/v51/d37-r5-recalc.json"
MAIN = ROOT
sys.path.insert(0, str(DEV))

from src.v4.r5.design import benchmark_returns  # noqa: E402
from src.v51.diag_d37 import DESIGN, INSPECT  # noqa: E402
from src.v51.diag_stats import performance, trade_cost  # noqa: E402

EXPECTED_DB_SHA = "d0b947d90b444eb1d874a04df6bcb1974cbea4422b489f214a56c0a658abf0d9"
PR284_HEAD = "770b22b2779309f70936b59ff210905922676d3f"
PR284_NUMBER = 284
MERGE_BASE_A0 = "a0ede094c5e5d604d1d9b5cb1c08da0d64641b40"

CELLS = [
    ("S0", "设计期", "设计期", "2015-12-31", False),
    ("S0", "别的市场", "别的市场", INSPECT[1], True),
    ("S0", "检验段", "检验段", INSPECT[1], True),
    ("S1", "检验段", "检验段", INSPECT[1], True),
]

REQUIRED_B_FILES = (
    "daily.csv",
    "stats.json",
    "market_days.csv",
    "markets.csv",
    "vs-v0.csv",
    "trades.csv",
    "sells.csv",
)


def _json_default(obj):  # noqa: ANN001
    if isinstance(obj, (np.integer, np.floating)):
        return float(obj) if isinstance(obj, np.floating) else int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(type(obj))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stats_window(daily: pd.DataFrame, segment: str) -> pd.DataFrame:
    if segment == "设计期":
        start, end = DESIGN
        return daily.loc[start:end]
    return daily


def recalc_cell(folder: Path, segment: str, bm_end: str, allow_after: bool) -> dict:
    daily = pd.read_csv(folder / "daily.csv", parse_dates=["date"], index_col="date")
    w = _stats_window(daily, segment)
    bm = benchmark_returns(end=bm_end, allow_after=allow_after)
    perf = performance(w["net"], bm)
    tc = trade_cost(w, segment)
    numbers = {k: perf[k] for k in ("ann", "max_drawdown", "n") if k in perf}
    numbers.update({k: tc[k] for k in ("trades_per_year", "cost_per_year", "trades", "cost")})
    return {"reviewer": numbers}


def load_dev_performance(folder: Path) -> dict:
    payload = json.loads((folder / "stats.json").read_text(encoding="utf-8"))
    p = payload["performance"]
    return {
        "ann": float(p["ann"]),
        "max_drawdown": float(p["max_drawdown"]),
        "trades_per_year": float(p["trades_per_year"]),
        "cost_per_year": float(p["cost_per_year"]),
        "trades": int(p["trades"]),
        "cost": float(p["cost"]),
    }


def near(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


def compare_vs_v0(
    reviewer_b: dict,
    v0_perf: dict,
    folder: Path,
) -> dict:
    """独立 (B − V0) 与同路径 Dev vs-v0.csv。"""
    dev_rows = pd.read_csv(folder / "vs-v0.csv")
    map_key = {
        "ann": "ann",
        "max_drawdown": "max_drawdown",
        "trades": "trades",
        "trades_per_year": "trades_per_year",
        "cost": "cost",
        "cost_per_year": "cost_per_year",
    }
    out = []
    ok = True
    for _, row in dev_rows.iterrows():
        metric = row["metric"]
        key = map_key[metric]
        b = reviewer_b[key]
        v0 = float(v0_perf[key]) if key != "trades" else int(v0_perf[key])
        got_minus = float(b) - float(v0)
        dev_minus = float(row["B_minus_V0"])
        if metric in {"ann", "max_drawdown", "cost", "cost_per_year"}:
            match = near(got_minus, dev_minus, 1e-9)
        elif metric in {"trades", "trades_per_year"}:
            match = near(got_minus, dev_minus, 0.05)
        else:
            match = near(got_minus, dev_minus, 1e-6)
        if not match:
            ok = False
        out.append(
            {
                "metric": metric,
                "reviewer_B_minus_V0": got_minus,
                "dev_B_minus_V0": dev_minus,
                "match": match,
            }
        )
    return {"rows": out, "all_match": ok}


def merge_tree_check() -> dict:
    base = subprocess.check_output(
        ["git", "merge-base", "HEAD", "origin/pr-284-head"],
        cwd=ROOT,
        text=True,
    ).strip()
    raw = subprocess.check_output(
        ["git", "merge-tree", base, "HEAD", "origin/pr-284-head"],
        cwd=ROOT,
        text=True,
        stderr=subprocess.STDOUT,
    )
    conflictish = any(
        token in raw
        for token in ("CONFLICT", "<<<<<<<", "changed in both")
    )
    return {
        "merge_base_with_pr284_head": base,
        "manager_expected_base_a0ede09": MERGE_BASE_A0,
        "merge_tree_has_conflict_markers": conflictish,
        "clean_merge_read": not conflictish,
    }


def completeness() -> dict:
    out = {}
    for scope, segment, _, _, _ in CELLS:
        folder = DEV / "results/v51-diag/d37" / scope / segment / "B"
        name = f"{scope}/{segment}/B"
        files = {n: (folder / n).is_file() for n in REQUIRED_B_FILES}
        extra_design = True
        if scope == "S0" and segment == "设计期":
            extra_design = (folder / "markets-window.csv").is_file()
        out[name] = {
            "folder_exists": folder.is_dir(),
            "required_files": files,
            "markets_window_csv_design": extra_design if name.startswith("S0/设计期") else None,
            "complete": folder.is_dir() and all(files.values()) and extra_design,
        }
    return out


def design_daily_match_main_r4() -> dict:
    main_design = MAIN / "results/v51-diag/d37/S0/设计期/B/daily.csv"
    dev_design = DEV / "results/v51-diag/d37/S0/设计期/B/daily.csv"
    if not main_design.is_file() or not dev_design.is_file():
        return {"both_present": False, "sha256_match": None}
    return {
        "both_present": True,
        "main_sha256": sha256_file(main_design),
        "pr284_sha256": sha256_file(dev_design),
        "sha256_match": sha256_file(main_design) == sha256_file(dev_design),
    }


def main() -> int:
    db_path = DEV / "data/market.sqlite"
    db_sha = sha256_file(db_path) if db_path.is_file() and db_path.stat().st_size > 1000 else None
    if db_path.is_file() and db_path.stat().st_size < 1000:
        db_sha = None

    comp = completeness()
    must_fix = []
    if not all(v["complete"] for v in comp.values()):
        must_fix.append("missing_required_B_outputs")
    if db_sha != EXPECTED_DB_SHA:
        must_fix.append("db_sha256_mismatch")

    design_match = design_daily_match_main_r4()
    if design_match.get("sha256_match") is False:
        must_fix.append("S0_design_B_daily_changed_vs_main_r4")

    cells_out = {}
    all_stats_match = True
    for scope, segment, stats_segment, bm_end, allow_after in CELLS:
        key = f"{scope}/{segment}/B"
        folder = DEV / "results/v51-diag/d37" / scope / segment / "B"
        if not folder.is_dir():
            continue
        rc = recalc_cell(folder, stats_segment, bm_end, allow_after)
        dev_p = load_dev_performance(folder)
        r = rc["reviewer"]
        match = {
            "ann": near(r["ann"], dev_p["ann"], 1e-9),
            "max_drawdown": near(r["max_drawdown"], dev_p["max_drawdown"], 1e-9),
            "trades_per_year": near(r["trades_per_year"], dev_p["trades_per_year"], 0.05),
            "cost_per_year": near(r["cost_per_year"], dev_p["cost_per_year"], 0.0005),
            "trades": int(r["trades"]) == int(dev_p["trades"]),
            "cost": near(r["cost"], dev_p["cost"], 1e-6),
        }
        v0_folder = DEV / "results/v51-diag/d37" / scope / segment / "V0"
        dev_v0_full = json.loads((v0_folder / "stats.json").read_text(encoding="utf-8"))["performance"]
        vs_check = compare_vs_v0(r, dev_v0_full, folder)
        if not all(match.values()) or not vs_check["all_match"]:
            all_stats_match = False
        cells_out[key] = {
            "reviewer": r,
            "dev": dev_p,
            "stats_match": match,
            "vs_v0_rows": vs_check,
        }

    if not all_stats_match:
        must_fix.append("stats_recalc_mismatch")

    gpool_limits_false = False
    gpool_run_v51_simulate = False
    gp = DEV / "src/v51/gpool.py"
    if gp.is_file():
        text = gp.read_text(encoding="utf-8")
        gpool_limits_false = '"limits": False' in text or "'limits': False" in text
        gpool_run_v51_simulate = "def run_v51" in text and "book = simulate" in text

    payload = {
        "diagnostic": "D37-r5-plan-B",
        "counts_toward_gate": False,
        "pr284": {
            "number": PR284_NUMBER,
            "head": PR284_HEAD,
            "branch": "cursor/d37-r5",
            "state": "OPEN",
        },
        "main_head_at_review": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "pr284_base_oid_from_gh": "87089f9a4f0b968e30101a82917f89fa74f7ffb2",
        "merge_check": merge_tree_check(),
        "db_sha256": {
            "dev_worktree_resolved": db_sha,
            "expected_d37_round4_after": EXPECTED_DB_SHA,
            "match_expected": db_sha == EXPECTED_DB_SHA,
        },
        "completeness_B_dirs": comp,
        "S0_design_B_vs_main_r4_daily": design_match,
        "cells": cells_out,
        "engine": {
            "china_B_execution_fields_in_stats_json": {
                "S0/设计期": json.loads(
                    (DEV / "results/v51-diag/d37/S0/设计期/B/stats.json").read_text(encoding="utf-8")
                ).get("execution"),
                "S0/检验段": json.loads(
                    (DEV / "results/v51-diag/d37/S0/检验段/B/stats.json").read_text(encoding="utf-8")
                ).get("execution"),
                "S1/检验段": json.loads(
                    (DEV / "results/v51-diag/d37/S1/检验段/B/stats.json").read_text(encoding="utf-8")
                ).get("execution"),
            },
            "other_market_B_execution": json.loads(
                (DEV / "results/v51-diag/d37/S0/别的市场/B/stats.json").read_text(encoding="utf-8")
            ).get("execution"),
            "d37_plan_b_docstring_notes_run_book_vs_gpool": (
                (DEV / "src/v51/d37_plan_b.py").is_file()
                and "run_book" in (DEV / "src/v51/d37_plan_b.py").read_text(encoding="utf-8")
                and "gpool.run_v51" in (DEV / "src/v51/d37_plan_b.py").read_text(encoding="utf-8")
            ),
            "gpool_manifest_limits_false_in_source": gpool_limits_false,
            "gpool_run_v51_uses_simulate": gpool_run_v51_simulate,
        },
        "must_fix_flags": must_fix,
        "must_fix_count": len(must_fix),
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default))
    return 0 if len(must_fix) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
