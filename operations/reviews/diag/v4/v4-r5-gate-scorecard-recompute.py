#!/usr/bin/env python3
"""Independent v4-R5 design gate + §7.5 key numbers (PR #122 review).

Reads Dev-published gate inputs and net series; does not treat candidate-gate.csv as truth.
Design period only (end ≤ 2015-12-31). Does not modify ledger or DB.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.report.metrics import ann_vol, cagr, calmar, max_drawdown, monthly_returns
from src.v3.engine.arms import execute
from src.v3.engine.benchmark import bm_main
from src.v3.engine.book import DESIGN_END
from src.v3.engine.spec import load_spec
from src.v4.r5.design import (
    DB_SHA256,
    Job,
    Markets,
    file_sha256,
    read_net,
    require_frozen_db,
    series_sha256,
)
from src.v4.scorecard.core import (
    DESIGN_START,
    any_start,
    any_start_summary,
    capture_ratios,
    cash_weight_on,
    classify_months,
    growth_nav,
    index_levels,
    level_nav,
    load_h00300,
    state_frame,
    state_table,
)
from src.v4.scorecard.gate import GATE_COLUMNS, TARGET_STATE, candidate_gate

R5 = ROOT / "results" / "v4" / "r5"
TRADING_DAYS = 252
SEGMENTS = (
    ("s1", "2006-01-01", "2010-12-31"),
    ("s2", "2011-01-01", "2015-12-31"),
)
STATE_ORDER = ("牛市", "回调", "熊市", "反弹")
RUN_ORDER = ("B0", "T1", "T2", "T3", "T4")
EXPECTED_GATE_SHA = "32058828326f5155ce9b9a678746d2f55d7a4a023b3d20a883e01676383c1b42"
EXPECTED_LEDGER_SHA = "37a43abe5586ff4f24640a02f419e8296a03d05c285337fddec6489b402bf2a3"
RUN_GIT_SHA = "18b5a82f0e874bcaa32cb4c26b001f8311d42819"
SERIES_NET_SHA = "6f92c0388825e210623400e9743ff6672f244b143f0d6b4b3f56223bd4eeb87f"


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
    for name in RUN_ORDER:
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
    out = pd.DataFrame(rows, columns=list(GATE_COLUMNS))
    for column in ("pass_segments", "pass_target", "pass_bear", "pass"):
        out[column] = out[column].astype(object)
    return out


def _read_net(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    series = pd.Series(frame["net"].astype(float).values, index=pd.to_datetime(frame["date"]))
    return series.sort_index()


def _personality(net: pd.Series, label: str) -> dict:
    depth = max_drawdown(net)
    monthly = monthly_returns(net)
    down = monthly[monthly < 0]
    down_vol = float(down.std(ddof=1) * np.sqrt(12)) if len(down) > 1 else None
    return {
        "label": label,
        "cagr_full": cagr(net),
        "cagr_from_2006": cagr(net.loc["2006-01-01":]) if len(net.loc["2006-01-01":]) else None,
        "max_drawdown": depth["max_drawdown"],
        "drawdown_peak": str(depth["peak"].date()),
        "drawdown_trough": str(depth["trough"].date()),
        "ann_vol": ann_vol(net),
        "monthly_ret_std": float(monthly.std(ddof=1)),
        "downside_vol_ann": down_vol,
        "calmar": calmar(net),
        "n_days": int(len(net)),
        "last_date": str(net.index[-1].date()),
    }


def _scorecard_from_net(net: pd.Series, db: Path, *, name: str = "B0") -> dict:
    end = str(DESIGN_END.date())
    window = net.loc[DESIGN_START:end]
    benchmark = bm_main(db, DESIGN_END).reindex(window.index).fillna(0.0)
    levels = index_levels(db, end)
    navs = {
        name: growth_nav(window, window.index),
        "基准": growth_nav(benchmark, window.index),
    }
    for level_name in ("沪深300", "标普500", "纳指100"):
        navs[level_name] = level_nav(levels[level_name], window.index)
    tables = any_start(navs, strategy=name)
    return {
        "summary": any_start_summary(tables, strategy=name),
        "capture": capture_ratios(window, benchmark),
    }


def _scorecard_with_held(net: pd.Series, held_cash: pd.Series, db: Path, *, name: str = "B0") -> dict:
    end = str(DESIGN_END.date())
    window = net.loc[DESIGN_START:end]
    benchmark = bm_main(db, DESIGN_END).reindex(window.index).fillna(0.0)
    states = classify_months(load_h00300(db, end))
    monthly = state_frame(
        window,
        benchmark,
        cash_weight_on(held_cash, window.index),
        states,
    )
    base = _scorecard_from_net(net, db, name=name)
    base["states"] = state_table(monthly)
    return base


def _reexecute_b0_index() -> tuple[pd.Series, pd.Series, object]:
    spec = load_spec()
    markets = Markets(spec)
    job = Job(case="B0", pool="index", kind="single")
    market = markets.get("index", t4=False, allow_substitute=True)
    switches = job.switches()
    book = execute(
        market, spec, "A", allow_after=False,
        exit_drawdown=job.exit_drawdown, switches=switches)
    net = book.net.astype(float)
    cash_id = market.cash_id
    held = book.held[cash_id].astype(float)
    return net, held, book


def _gate_diff(dev: pd.DataFrame, ind: pd.DataFrame) -> dict:
    float_cols = [
        "ann_excess_s1", "ann_excess_s2",
        "pp_bull", "pp_correction", "pp_bear", "pp_rebound",
    ]
    ok = True
    mismatches = []
    for col in GATE_COLUMNS:
        if dev[col].equals(ind[col]):
            continue
        if col in float_cols:
            diff = (dev[col].astype(float) - ind[col].astype(float)).abs()
            mx = float(diff.max())
            if mx > 1e-9:
                ok = False
                mismatches.append({"column": col, "max_abs_diff": mx})
        else:
            ok = False
            mismatches.append({
                "column": col,
                "dev": dev[col].tolist(),
                "ind": ind[col].tolist(),
            })
    return {"match": ok, "mismatches": mismatches}


def main() -> int:
    out: dict = {"repo": str(ROOT)}

    db_digest = require_frozen_db()
    out["db_sha256"] = db_digest
    out["db_sha_ok"] = db_digest == DB_SHA256

    gate_path = R5 / "candidate-gate.csv"
    out["candidate_gate_sha256"] = file_sha256(gate_path)
    out["candidate_gate_sha_ok"] = out["candidate_gate_sha256"] == EXPECTED_GATE_SHA

    ledger_path = ROOT / "results" / "v4" / "trial-ledger.csv"
    out["trial_ledger_rows"] = sum(1 for _ in open(ledger_path, encoding="utf-8")) - 1
    out["trial_ledger_sha256"] = file_sha256(ledger_path)
    out["trial_ledger_sha_ok"] = out["trial_ledger_sha256"] == EXPECTED_LEDGER_SHA

    import csv
    with ledger_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    git_shas = {row.get("git_sha") for row in rows}
    out["ledger_git_shas"] = sorted(git_shas)
    out["ledger_git_sha_ok"] = git_shas == {RUN_GIT_SHA}

    inputs = pd.read_csv(R5 / "gate-inputs.csv", parse_dates=["date"]).set_index("date").sort_index()
    states = pd.read_csv(R5 / "month-states.csv", parse_dates=["month_end"]).set_index("month_end")["state"]
    benchmark = inputs["benchmark"].astype(float)
    returns = inputs[list(RUN_ORDER)].astype(float)

    dev_gate = pd.read_csv(gate_path)
    ind_gate = independent_gate(returns, benchmark, states, pool="index")
    dev_impl = candidate_gate(returns, benchmark, states, pool="index")
    out["gate_independent_vs_dev"] = _gate_diff(dev_gate, ind_gate)
    out["gate_dev_impl_vs_independent"] = _gate_diff(dev_impl, ind_gate)
    out["independent_gate_records"] = ind_gate.to_dict(orient="records")
    out["any_candidate_pass"] = any(bool(x) for x in ind_gate["pass"] if x is not None and x == x)

    b0_net = read_net("B0", "index")
    final_net = read_net("final", "index")
    out["b0_final_index_net_identical"] = bool(np.allclose(b0_net.values, final_net.values, rtol=0, atol=0))
    out["b0_index_series_sha256"] = series_sha256(b0_net)
    out["b0_index_series_sha_ok"] = out["b0_index_series_sha256"] == SERIES_NET_SHA
    out["b0_index_file_sha256"] = file_sha256(R5 / "design" / "B0" / "index" / "net.csv")

    for arm in RUN_ORDER:
        path = R5 / "design" / arm / "index" / "net.csv"
        if path.exists():
            s = _read_net(path)
            out[f"net_end_{arm}"] = str(s.index[-1].date())

    re_net, held, re_book = _reexecute_b0_index()
    out["reexec_net_max_abs_diff_vs_published"] = float(
        (re_net.reindex(b0_net.index).fillna(0) - b0_net).abs().max()
    )
    out["reexec_net_match"] = out["reexec_net_max_abs_diff_vs_published"] < 1e-12
    years = (pd.Timestamp(b0_net.index[-1]) - pd.Timestamp(b0_net.index[0])).days / 365.25
    turnover = float((re_book.buy.sum() + re_book.sell.sum()) / max(years, 1e-9))
    out["b0_index_turnover_per_year"] = round(turnover, 2)

    db = ROOT / "data" / "market.sqlite"
    score = _scorecard_with_held(b0_net, held, db, name="B0")
    out["scorecard_B0_index"] = {
        "any_start": score["summary"].to_dict(orient="records"),
        "states": score["states"].reset_index().to_dict(orient="records"),
        "capture": score["capture"],
    }

    out["personality"] = {
        "B0_index_full": _personality(b0_net, "B0 index full calendar"),
        "B0_index_2006_2010": _personality(b0_net.loc["2006-01-01":"2010-12-31"], "2006-2010"),
        "B0_index_2011_2015": _personality(b0_net.loc["2011-01-01":"2015-12-31"], "2011-2015"),
    }

    # Spot-check published CAGR (full calendar) vs independent from net.csv
    cagr_spot = {}
    for arm in RUN_ORDER:
        summary_path = R5 / "design" / arm / "index" / "summary.json"
        if summary_path.exists():
            published = json.loads(summary_path.read_text(encoding="utf-8"))
            net = _read_net(R5 / "design" / arm / "index" / "net.csv")
            cagr_spot[arm] = {
                "published_cagr": published.get("cagr"),
                "recomputed_cagr": cagr(net),
                "published_cagr_from_2006": published.get("cagr_from_2006"),
                "recomputed_cagr_from_2006": cagr(net.loc["2006-01-01":]),
                "published_mdd": published.get("max_drawdown"),
                "recomputed_mdd": max_drawdown(net)["max_drawdown"],
            }
    out["u_index_cagr_spotcheck"] = cagr_spot

    # Adaptability: B0 vs selected §7.2 runs (CAGR delta, full calendar)
    adapt = []
    for case in ("no-substitute", "lookback-15-50-100-200", "delay-1d", "drop-best-1"):
        for pool in ("index", "tradable"):
            p = R5 / "design" / case / pool / "summary.json"
            if not p.exists():
                continue
            pub = json.loads(p.read_text(encoding="utf-8"))
            adapt.append({
                "case": case,
                "pool": pool,
                "cagr": pub.get("cagr"),
                "max_drawdown": pub.get("max_drawdown"),
            })
    out["adaptability_samples"] = adapt

    # E2 new (B0) vs frozen P1 reference any-start 5y (from scorecard acceptance constants)
    p1_book = ROOT / "results/v3/design-period/9b421c0294a8509e5283aa871034ff0e8ed66c75/P1"
    if p1_book.exists():
        from src.v4.scorecard.core import score_book as sb
        p1_report = sb(p1_book / "paths.csv", p1_book / "held.csv", db, name="E2")
        out["p1_frozen_any_start_5y"] = p1_report["summary"][p1_report["summary"]["years"] == 5].to_dict(
            orient="records"
        )
        five_b0 = score["summary"][score["summary"]["years"] == 5]
        out["b0_any_start_5y"] = five_b0.to_dict(orient="records")

    # Integrity: no LOCK, no 2016+ in gate inputs
    out["lock_exists"] = (ROOT / "results" / "v4" / "LOCK").exists()
    out["gate_inputs_max_date"] = str(inputs.index.max().date())

    tag = "milestone/v4-prereg-freeze"
    import subprocess
    tag_sha = subprocess.check_output(["git", "rev-parse", tag], cwd=ROOT, text=True).strip()
    out["tag_v4_prereg_freeze"] = tag_sha

    artifact = ROOT / "operations" / "reviews" / "diag" / "v4" / "v4-r5-gate-scorecard-recompute.json"
    artifact.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    gate_ok = out["gate_independent_vs_dev"]["match"] and out["gate_dev_impl_vs_independent"]["match"]
    return 0 if gate_ok and out["reexec_net_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
