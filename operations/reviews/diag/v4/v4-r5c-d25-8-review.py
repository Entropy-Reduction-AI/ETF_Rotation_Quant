#!/usr/bin/env python3
"""Independent v4-R5c D25-8 / D25-9 review (Dev PR #136). Design period ≤2015-12-31."""
from __future__ import annotations

import csv
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

from src.report.metrics import cagr, max_drawdown
from src.v3.engine.arms import execute
from src.v3.engine.spec import load_spec
from src.v4.data.d25_8 import (
    BAD_HFQ,
    BAD_RAW,
    CODE,
    DAY,
    PREV_DAY,
    corrected_hfq_close,
)
from src.v4.data.hfq import CORRECTION_KIND, canonical_hfq
from src.v4.r5.design import (
    DESIGN_END,
    Job,
    Markets,
    file_sha256,
    prepare_market,
    read_net,
    require_frozen_db,
    series_sha256,
    LEDGER,
)

EXPECTED_DB_SHA = "167d4e39ffab4302e6f55d2b3436b3400ea28b2282cd7f9b9bda644d87c1acf3"
EXPECTED_INDEX_NET_SHA = "77fc2f7bdeae577f6329924fa590a5813414a65d626b4c9cf393c16cc3015482"
EXPECTED_TRAD_NET_SHA = "f02d20ca7e848d0a1c817022a594e5c404c2d1012d8ceb8bb77e30bd79a42bab"
DEV_TRAD_GIT_SHA = "38d8c20d666e2b180841b40c58b417e0c6b6653e"
INDEX_D25_1_SHA = "c700ca095057baa524be01f6566d342c43976bea"
ORCH_TRAD_CAGR_FROM_2006 = 0.09
SPIKE_CSV = ROOT / "results/v4/inventory/r5c/d25-9-reversal-spikes.csv"
V4_SERIES_ROWS = 593_481


def personality(net: pd.Series) -> dict:
    depth = max_drawdown(net)
    sub = net.loc["2006-01-01":]
    return {
        "cagr_full": cagr(net),
        "cagr_from_2006": cagr(sub) if len(sub) else None,
        "max_drawdown": depth["max_drawdown"],
        "mdd_trough": str(depth["trough"].date()),
    }


def insert_checks(con: sqlite3.Connection) -> dict:
    chosen = canonical_hfq(con, CODE, DESIGN_END)
    ts = pd.Timestamp(DAY)
    prev_ts = pd.Timestamp(PREV_DAY)
    next_ts = pd.Timestamp("2008-01-03")
    c_day = float(chosen.closes.loc[ts])
    c_prev = float(chosen.closes.loc[prev_ts])
    c_next = float(chosen.closes.loc[next_ts])
    ret1 = c_day / c_prev - 1.0
    ret2 = c_next / c_day - 1.0
    corr = con.execute(
        """SELECT close, source, method FROM v4_series
           WHERE code = ? AND date = ? AND kind = ?""",
        (CODE, DAY, CORRECTION_KIND),
    ).fetchone()
    raw = con.execute(
        "SELECT close FROM bars WHERE code = ? AND adj = 'raw' AND date = ?",
        (CODE, DAY),
    ).fetchone()[0]
    hfq = con.execute(
        """SELECT close FROM v4_series
           WHERE code = ? AND kind = 'backward' AND date = ?
             AND source LIKE 'tencent%'""",
        (CODE, DAY),
    ).fetchone()[0]
    rows = con.execute("SELECT COUNT(*) FROM v4_series").fetchone()[0]
    return {
        "v4_series_row_count": rows,
        "v4_series_row_count_ok": rows == V4_SERIES_ROWS,
        "bars_raw_close": float(raw),
        "tencent_backward_close": float(hfq),
        "correction_close": float(corr[0]) if corr else None,
        "correction_source": corr[1] if corr else None,
        "canonical_tier": chosen.tier,
        "canonical_close_day": c_day,
        "expected_correction_close": corrected_hfq_close(),
        "raw_unchanged": abs(float(raw) - BAD_RAW) < 1e-9,
        "hfq_row_unchanged": abs(float(hfq) - BAD_HFQ) < 1e-9,
        "canonical_uses_correction": abs(c_day - corrected_hfq_close()) < 1e-9,
        "neighbor_prev_close": c_prev,
        "neighbor_next_close": c_next,
        "ret_prev_to_day": ret1,
        "ret_day_to_next": ret2,
    }


def spike_checks() -> dict:
    rows = list(csv.DictReader(open(SPIKE_CSV)))
    codes = {r["code"] for r in rows}
    xlf = [r for r in rows if r["code"] == "XLF"]
    held = [r for r in rows if r.get("affects_holding") == "yes"]
    return {
        "n_rows": len(rows),
        "unique_codes": sorted(codes),
        "xlf_rows": len(xlf),
        "510880_present": "510880" in codes or CODE in codes,
        "any_affects_holding_yes": len(held),
        "all_affects_holding_no": all(r.get("affects_holding") == "no" for r in rows),
        "dates": [r["date"] for r in rows],
    }


def ledger_checks() -> dict:
    rows = list(csv.DictReader(open(LEDGER)))
    parsed = [(r, json.loads(r["params"])) for r in rows]
    index_d25_1 = [r for r, p in parsed if p.get("pool") == "index" and p.get("fix") == "D25-1"]
    trad_d25_8 = [r for r, p in parsed if p.get("pool") == "tradable" and p.get("fix") == "D25-8"]
    trad_d25_3 = [r for r, p in parsed if p.get("pool") == "tradable" and p.get("fix") == "D25-3"]
    git_shas = {r.get("git_sha") for r in rows}
    trad_shas = {r.get("git_sha") for r, p in parsed if p.get("pool") == "tradable"}
    index_shas = {r.get("git_sha") for r, p in parsed if p.get("pool") == "index"}
    return {
        "ledger_rows": len(rows),
        "index_fix_d25_1": len(index_d25_1),
        "tradable_fix_d25_8": len(trad_d25_8),
        "tradable_fix_d25_3_remaining": len(trad_d25_3),
        "tradable_git_shas": sorted(trad_shas),
        "index_git_shas": sorted(index_shas),
        "tradable_sha_is_d25_8_commit": trad_shas == {DEV_TRAD_GIT_SHA},
        "index_sha_unchanged": index_shas == {INDEX_D25_1_SHA},
    }


def reexec_b0_tradable() -> tuple[pd.Series, float]:
    spec = load_spec()
    job = Job(case="B0", pool="tradable", kind="single")
    market = prepare_market("tradable", t4=False, allow_substitute=True, spec=spec)
    book = execute(
        market,
        spec,
        "A",
        allow_after=False,
        exit_drawdown=job.exit_drawdown,
        switches=job.switches(),
    )
    published = read_net("B0", "tradable")
    re_net = book.net.astype(float)
    aligned = re_net.reindex(published.index)
    max_diff = float((aligned.fillna(0) - published).abs().max())
    return re_net, max_diff


def net_files_identical(a: Path, b: Path) -> bool:
    if not a.is_file() or not b.is_file():
        return False
    return file_sha256(a) == file_sha256(b)


def main() -> int:
    out: dict = {
        "design_end": DESIGN_END,
        "dev_pr": 136,
        "dev_head_note": "Run at Dev PR #136 head (7dbc3ce…)",
    }
    db_sha = require_frozen_db()
    out["db_sha256"] = db_sha
    out["db_sha_matches"] = db_sha == EXPECTED_DB_SHA

    con = sqlite3.connect(f"file:{ROOT / 'data/market.sqlite'}?mode=ro", uri=True)
    out["insert"] = insert_checks(con)
    con.close()
    out["spikes"] = spike_checks()

    b0_trad = read_net("B0", "tradable")
    final_trad = read_net("final", "tradable")
    b0_index = read_net("B0", "index")
    pub_tr = json.loads((ROOT / "results/v4/r5/design/B0/tradable/summary.json").read_text())
    pub_idx = json.loads((ROOT / "results/v4/r5/design/B0/index/summary.json").read_text())

    pers_tr = personality(b0_trad)
    out["b0_tradable_metrics"] = {
        **pers_tr,
        "published_cagr_full": pub_tr["cagr"],
        "published_cagr_from_2006": pub_tr.get("cagr_from_2006"),
        "published_mdd": pub_tr["max_drawdown"],
        "net_sha256": pub_tr["net_sha256"],
        "net_sha256_recomputed": series_sha256(b0_trad),
        "net_sha256_ok": pub_tr["net_sha256"] == EXPECTED_TRAD_NET_SHA,
    }
    out["b0_index_net_sha256"] = {
        "published": pub_idx["net_sha256"],
        "recomputed": series_sha256(b0_index),
        "expected": EXPECTED_INDEX_NET_SHA,
        "unchanged": pub_idx["net_sha256"] == EXPECTED_INDEX_NET_SHA,
    }
    out["final_vs_b0_tradable"] = {
        "max_abs_diff": float((b0_trad - final_trad.reindex(b0_trad.index).fillna(0)).abs().max()),
        "net_csv_identical": net_files_identical(
            ROOT / "results/v4/r5/design/B0/tradable/net.csv",
            ROOT / "results/v4/r5/design/final/tradable/net.csv",
        ),
    }

    _, reexec_max_diff = reexec_b0_tradable()
    out["b0_tradable_reexec_max_diff"] = reexec_max_diff

    out["vs_orchestrator_tradable"] = {
        "orch_cagr_from_2006_approx": ORCH_TRAD_CAGR_FROM_2006,
        "reviewer_cagr_from_2006": pers_tr["cagr_from_2006"],
        "cagr_gap_pp": 100.0 * (pers_tr["cagr_from_2006"] - ORCH_TRAD_CAGR_FROM_2006),
    }

    out["ledger"] = ledger_checks()
    out["lock_exists"] = (ROOT / "results/v4/LOCK").exists()

    out_path = ROOT / "operations/reviews/diag/v4/v4-r5c-d25-8-review.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = (
        out["db_sha_matches"]
        and out["insert"]["canonical_uses_correction"]
        and out["insert"]["raw_unchanged"]
        and out["insert"]["hfq_row_unchanged"]
        and not out["spikes"]["510880_present"]
        and out["spikes"]["n_rows"] == 4
        and out["ledger"]["ledger_rows"] == 41
        and out["b0_index_net_sha256"]["unchanged"]
        and out["b0_tradable_metrics"]["net_sha256_ok"]
        and reexec_max_diff < 1e-10
        and abs(pers_tr["cagr_full"] - pub_tr["cagr"]) < 1e-12
        and abs(pers_tr["cagr_from_2006"] - pub_tr["cagr_from_2006"]) < 1e-12
        and abs(pers_tr["max_drawdown"] - pub_tr["max_drawdown"]) < 1e-12
        and abs(out["vs_orchestrator_tradable"]["cagr_gap_pp"]) < 0.5
    )
    summary = {
        "ok": ok,
        "cagr_full_pct": round(100 * pers_tr["cagr_full"], 4),
        "cagr_from_2006_pct": round(100 * pers_tr["cagr_from_2006"], 4),
        "mdd_pct": round(100 * pers_tr["max_drawdown"], 4),
        "vs_orch_pp": round(out["vs_orchestrator_tradable"]["cagr_gap_pp"], 4),
    }
    print(json.dumps(summary, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
