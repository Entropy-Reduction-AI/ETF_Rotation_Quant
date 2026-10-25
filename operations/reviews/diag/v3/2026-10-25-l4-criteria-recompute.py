#!/usr/bin/env python3
"""Design-period §6①②③ independent recompute (Reviewer).

Path 1 — spot formulas duplicated in this file (no import from src.v3.eval.windows/eras).
Path 2 — black-box src.v3.eval.criterion_1/2/3.

② uses sanitized pnl (NaN→0, ±inf→0) because raw U-指数 `market.pnl` contains NaN/inf
cells and `book.net` has one NaN day; otherwise criterion_2 raises EvalError.
Default 30 null trials here for runtime (~3 min); 1,000 trials and rank uniformity are in
tests/v3/eval/test_l4.py. Output JSON also written by Reviewer to
operations/reviews/diag/v3/2026-10-25-l4-criteria-compare.json.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data import db as DB
from src.v3.data.universe import containers as load_containers
from src.v3.engine.benchmark import bm_main
from src.v3.engine.market import load_market
from src.v3.engine.runner import run
from src.v3.engine.spec import load_spec
from src.v3.eval.controls import criterion_2, eligibility_on_targets, percentile_rank
from src.v3.eval.eras import ERAS, criterion_3
from src.v3.eval.windows import criterion_1

UNIVERSE = ROOT / "config" / "v3" / "universe.toml"
UNIVERSE_SHA = "693b7d4dff91dff4b9bac4a0c1241eb4692f6b3cbd444965440a265ffa32aaff"
DESIGN_END = pd.Timestamp("2015-12-31")
TRADING_DAYS = 252
FRACTION_60 = 0.60
DEFAULT_NULL_TRIALS = 30


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def spot_annualized(values) -> float:
    arr = np.asarray(values, dtype=float)
    growth = float(np.expm1(np.log1p(arr).sum()))
    return float(math.exp(math.log1p(growth) * TRADING_DAYS / len(arr)) - 1.0)


def _month_bounds(calendar):
    index = pd.DatetimeIndex(calendar).sort_values().unique()
    bounds = {}
    for day in index:
        key = (int(day.year), int(day.month))
        stamp = pd.Timestamp(day)
        bounds[key] = (bounds[key][0], stamp) if key in bounds else (stamp, stamp)
    return bounds


def _add_months(year: int, month: int, offset: int) -> tuple[int, int]:
    zero = year * 12 + (month - 1) + offset
    return zero // 12, zero % 12 + 1


def spot_rolling_windows(calendar, months: int):
    bounds = _month_bounds(calendar)
    windows = []
    for year, month in sorted(bounds):
        keys = [_add_months(year, month, offset) for offset in range(months)]
        if any(key not in bounds for key in keys):
            continue
        end = bounds[keys[-1]][1]
        if end > DESIGN_END:
            continue
        windows.append((bounds[(year, month)][0], end))
    return windows


def spot_criterion_1(strategy, benchmark, calendar) -> dict:
    sessions = pd.DatetimeIndex(calendar).sort_values().unique()
    left, right = pd.Series(strategy), pd.Series(benchmark)

    def collect(months: int) -> list[float]:
        rows = []
        for start, end in spot_rolling_windows(sessions, months):
            days = sessions[(sessions >= start) & (sessions <= end)]
            s, b = left.reindex(days), right.reindex(days)
            if s.isna().any() or b.isna().any():
                continue
            rows.append(spot_annualized(s) - spot_annualized(b))
        return rows

    e36, e60 = collect(36), collect(60)
    median_36 = float(np.median(e36)) if e36 else None
    median_60 = float(np.median(e60)) if e60 else None
    fraction = float(np.mean(np.asarray(e60) > 0.0)) if e60 else None
    eng = bool(
        median_36 is not None
        and median_60 is not None
        and fraction is not None
        and median_60 > 0.0
        and fraction >= FRACTION_60
        and median_36 > 0.0
    )
    return {
        "n_36": len(e36),
        "n_60": len(e60),
        "median_36": median_36,
        "median_60": median_60,
        "fraction_positive_60": fraction,
        "engineering_check": eng,
    }


def main() -> int:
    if sha256_file(UNIVERSE) != UNIVERSE_SHA:
        raise SystemExit("universe SHA mismatch")
    spec = load_spec()
    book = run("A", "index", str(DESIGN_END.date()), debug=True)
    market = load_market(
        DB.MARKET_DB, load_containers(), "A", "index", DESIGN_END, spec, allow_after=False
    )
    bench = bm_main(DB.MARKET_DB, DESIGN_END).reindex(book.net.index)
    strat = book.net.fillna(0.0)
    cal = book.net.index

    box_1 = criterion_1(strat, bench, cal)
    spot_1 = spot_criterion_1(strat, bench, cal)
    box_3 = criterion_3(strat, bench, cal)

    pnl = market.pnl.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    eligible = eligibility_on_targets(market, spec, book.targets)
    box_2 = criterion_2(
        strat,
        pnl,
        book.targets,
        market.fees,
        market.names,
        market.cash_id,
        n_trials=DEFAULT_NULL_TRIALS,
        seed=int(spec.seed),
        eligible=eligible,
    )
    rank_spot = percentile_rank(box_2["strategy_ann"], box_2["null_b"]["annualized"])

    out = {
        "task": "v3-L4 design-period §6①②③",
        "universe_sha256": UNIVERSE_SHA,
        "criterion_1": {"spot": spot_1, "black_box": {k: box_1[k] for k in spot_1}, "match": spot_1 == {k: box_1[k] for k in spot_1}},
        "criterion_2": {
            "n_trials": DEFAULT_NULL_TRIALS,
            "strategy_ann": box_2["strategy_ann"],
            "null_b_percentile": box_2["null_b"]["percentile"],
            "null_b_in_top_decile": box_2["null_b"]["in_top_decile"],
            "null_a_percentile": box_2["null_a"]["percentile"] if box_2["null_a"] else None,
            "spot_percentile": rank_spot["percentile"],
            "strategy_net_nan_days": int(book.net.isna().sum()),
            "pnl_sanitized": True,
        },
        "criterion_3": {"eras": box_3["eras"], "engineering_check": box_3["engineering_check"]},
        "gates": {
            "lock_exists": (ROOT / "results" / "v3" / "LOCK").exists(),
            "ledger_exists": (ROOT / "results" / "v3" / "trial-ledger.csv").exists(),
        },
    }
    compare_path = ROOT / "operations/reviews/diag/v3/2026-10-25-l4-criteria-compare.json"
    compare_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    ok = out["criterion_1"]["match"] and not out["gates"]["lock_exists"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
