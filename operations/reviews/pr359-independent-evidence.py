#!/usr/bin/env python3
"""Independent PR359 archive evidence — explanatory recompute for Reviewer only.

Run from repo root (read-only sqlite; reads delivered gapfill if present on branch):

    python3 -I operations/reviews/pr359-independent-evidence.py

Does not download, does not write gapfill paths, does not merge or approve on GitHub.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "incoming" / "v6-us-gapfill"
PRIOR_TV = (
    ROOT
    / "incoming/grok-d37-index-20261116/theme-道琼斯美国精选REIT指数-tradingview.csv"
)
DB = ROOT / "data" / "market.sqlite"
OUT = ROOT / "operations/reviews/pr359-independent-evidence.json"
ART = Path("/opt/cursor/artifacts/reviewer-pr359")

LIVE359 = "e9b12dc6a4b24c6e0f470ddbec0fadaf2082b7bf"
FIRST359 = "74ea30699d184c01971ee55a0abdbcc1e36d5d84"

DJIA_REQ = ("2024-02-01", "2026-09-30")
DJIA_OVL = ("2023-11-01", "2024-02-01")
DW_REQ = ("2017-11-22", "2026-09-30")
DW_OVL = ("2017-08-01", "2017-11-22")
STOP_DB = 0.001


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_show_live(path: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"pr359-live:{path}"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def load_norm(name: str) -> dict[str, float]:
    p = PKG / "normalized" / name
    if not p.is_file():
        return {}
    rows: dict[str, float] = {}
    with p.open(encoding="utf-8", newline="") as f:
        for rec in csv.DictReader(f):
            rows[rec["date"]] = float(rec["close"])
    return rows


def load_fred_raw(path: Path) -> dict[str, float]:
    rows: dict[str, float] = {}
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if i == 0:
            continue
        day, close = line.split(",", 1)
        if close in {"", "."}:
            continue
        rows[day] = float(close)
    return rows


def in_window(d: str, start: str, end: str) -> bool:
    return start <= d <= end


def rel_diff(left: float, right: float) -> float:
    if right == 0:
        raise ValueError("zero denominator")
    return abs(left - right) / abs(right)


def pairwise(
    left: dict[str, float],
    right: dict[str, float],
    start: str,
    end: str,
    denom_side: str = "right",
) -> dict:
    only_l, only_r, paired = [], [], []
    worst = None
    for day in sorted(set(left) | set(right)):
        if not in_window(day, start, end):
            continue
        if day not in right:
            only_l.append(day)
            continue
        if day not in left:
            only_r.append(day)
            continue
        a, b = left[day], right[day]
        r = rel_diff(a, b)
        row = {"date": day, "left": a, "right": b, "rel": r}
        paired.append(row)
        if worst is None or r > worst["rel"]:
            worst = row
    return {
        "start": start,
        "end": end,
        "denominator": denom_side,
        "n_overlap": len(paired),
        "only_left": only_l,
        "only_right": only_r,
        "max_rel": None if worst is None else worst["rel"],
        "worst": worst,
        "n_above_0_01pct": sum(1 for p in paired if p["rel"] > 0.0001),
        "n_above_0_1pct": sum(1 for p in paired if p["rel"] > 0.001),
    }


def db_raw(code: str, start: str, end: str) -> tuple[str | None, dict[str, float]]:
    if not DB.is_file() or DB.read_text(encoding="utf-8", errors="ignore").startswith("version https://git-lfs"):
        return None, {}
    uri = f"file:{DB}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        src = con.execute(
            "SELECT source FROM bars WHERE code=? AND adj='raw' LIMIT 1", (code,)
        ).fetchone()
        if not src:
            return None, {}
        rows = con.execute(
            "SELECT date, close FROM bars WHERE code=? AND adj='raw' AND date>=? AND date<=? ORDER BY date",
            (code, start, end),
        ).fetchall()
    finally:
        con.close()
    return src[0], {d: float(c) for d, c in rows}


def sample_dates(
    rows: dict[str, float], start: str, end: str, label: str, n: int = 24
) -> list[dict]:
    keys = sorted(d for d in rows if in_window(d, start, end))
    if not keys:
        return []
    picks = {keys[0], keys[-1], keys[len(keys) // 2]}
    step = max(1, len(keys) // max(1, n - len(picks)))
    for i in range(0, len(keys), step):
        picks.add(keys[i])
        if len(picks) >= n:
            break
    return [
        {
            "provenance": "delivered_normalized_csv",
            "label": label,
            "date": d,
            "close": rows[d],
        }
        for d in sorted(picks)[:n]
    ]


def audit_fred_independent() -> dict:
    pr = PKG / "raw" / "fred-DJIA.csv"
    ind = ART / "raw" / "fred-DJIA-independent.csv"
    pr_h = sha256_file(pr)
    ind_h = sha256_file(ind)
    out: dict = {
        "method": "fresh_download_vs_pr_delivered_raw",
        "independent_url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DJIA",
        "pr_path": str(pr.relative_to(ROOT)) if pr.is_file() else None,
        "independent_path": str(ind) if ind.is_file() else None,
        "pr_sha256": pr_h,
        "independent_sha256": ind_h,
        "retrieved_at": datetime.now().astimezone().isoformat(),
    }
    if not pr_h or not ind_h:
        out["sha256_match"] = None
        out["note"] = "missing file; no byte comparison performed"
        return out
    out["sha256_match"] = pr_h == ind_h
    if pr.is_file() and ind.is_file():
        pr_rows = load_fred_raw(pr)
        ind_rows = load_fred_raw(ind)
        mism = [
            {"date": d, "pr": pr_rows[d], "ind": ind_rows[d]}
            for d in sorted(set(pr_rows) & set(ind_rows))
            if pr_rows[d] != ind_rows[d]
        ]
        out["parsed_close_mismatches"] = len(mism)
        out["mismatches_sample"] = mism[:5]
    return out


def audit_cnbc_independent() -> dict:
    pr = PKG / "raw/cnbc-dwrtf/cnbc_dwrtf_20170801_20171231.json"
    ind = ART / "raw/cnbc_dwrtf_20170801_20171231-independent.json"
    pr_h = sha256_file(pr)
    ind_h = sha256_file(ind)
    out = {
        "method": "fresh_download_vs_pr_delivered_raw",
        "url": "https://ts-api.cnbc.com/harmony/app/bars/.DWRTF/1D/20170801000000/20171231235959/adjusted/GMT",
        "note": "CNBC may require browser User-Agent; 403 without UA",
        "pr_sha256": pr_h,
        "independent_sha256": ind_h,
        "retrieved_at": datetime.now().astimezone().isoformat(),
    }
    if pr_h and ind_h:
        out["sha256_match"] = pr_h == ind_h
    else:
        out["sha256_match"] = None
    return out


def main() -> int:
    fred = load_norm("djia-fred.csv")
    cnbc_d = load_norm("djia-cnbc.csv")
    yahoo = load_norm("djia-yahoo.csv")
    dw_cnbc = load_norm("dwrtf-cnbc.csv")
    dw_tv = load_norm("dwrtf-tradingview-prior.csv")

    dji_src, dji_db = db_raw("DJIA", *DJIA_OVL)
    dw_src, dw_db = db_raw("DWRTF", *DW_OVL)

    pairs: dict = {}
    if fred and cnbc_d:
        pairs["djia_fred_vs_cnbc_req"] = pairwise(fred, cnbc_d, *DJIA_REQ)
    if fred and dji_db:
        pairs["djia_fred_vs_db_ovl"] = pairwise(fred, dji_db, *DJIA_OVL)
    if cnbc_d and dji_db:
        pairs["djia_cnbc_vs_db_ovl"] = pairwise(cnbc_d, dji_db, *DJIA_OVL)
    if yahoo and dji_db:
        pairs["djia_yahoo_vs_db_ovl"] = pairwise(yahoo, dji_db, *DJIA_OVL)
    if dw_cnbc and dw_tv:
        pairs["dw_cnbc_vs_tv_req"] = pairwise(dw_cnbc, dw_tv, *DW_REQ)
    if dw_cnbc and dw_db:
        pairs["dw_cnbc_vs_db_ovl"] = pairwise(dw_cnbc, dw_db, *DW_OVL)

    db_stop = [
        k
        for k in (
            "djia_fred_vs_db_ovl",
            "djia_cnbc_vs_db_ovl",
            "djia_yahoo_vs_db_ovl",
            "dw_cnbc_vs_db_ovl",
        )
        if k in pairs and pairs[k]["n_above_0_1pct"] > 0
    ]

    live_body_snip = git_show_live("incoming/v6-us-gapfill/COVERAGE.md")
    dev_doc_blocker = None
    if live_body_snip and "不能再算作独立于库的第二来源" in live_body_snip:
        dev_doc_blocker = (
            "PR359 live COVERAGE.md/BODY still state TradingView is not gap "
            "independent source; Owner 2026-11-24 21:21 Asia/Taipei allows "
            "CNBC(LSEG)+archived TV(ICE) as gap publishers (TV/sqlite lineage "
            "only bars independent DB-overlap). Dev sync pending."
        )

    report = {
        "owner_ruling_ref": "2026-11-24 21:21 Asia/Taipei SOURCE_ARCHIVES_ONLY",
        "prior_github_review": {
            "id": 6035852626,
            "state_at_submit": "COMMENTED not approved",
            "commit_id": FIRST359,
            "url": "https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/359#pullrequestreview-6035852626",
            "supersedes": "Owner-authorized ARCHIVE-ONLY acceptance; not a usable-daily-series approval",
        },
        "pr359_heads": {
            "live": LIVE359,
            "first_evidence_commit": FIRST359,
            "delta_commits": ["e9b12dc6a4b24c6e0f470ddbec0fadaf2082b7bf"],
        },
        "pr360_branch_note": {
            "ancestry_artifact": "PR360 vs main shows ~50 files because branch includes 359 tree; "
            "NET after 359 merged is only operations/reviews/* (3 files at last append)",
        },
        "verdict_for_coordinator": {
            "reviewer_recommendation": "APPROVE_PR359_SOURCE_ARCHIVES_ONLY",
            "not_claimed": [
                "frozen_usable_daily_series",
                "strategy_returns",
                "db_or_config_or_roster_writes",
                "ingestion_complete_for_required_trading_days",
            ],
            "dev_doc_sync_blocker": dev_doc_blocker,
        },
        "owner_ruling_mapping": {
            "gap_publishers_djia": "FRED(SPDJI re-publish) + CNBC(LSEG) — independent",
            "gap_publishers_dwrtf": "CNBC(LSEG) + archived TradingView(ICE) — independent for archive gap compare",
            "tv_sqlite_lineage": "disqualifies only TV↔sqlite as independent DB-overlap; not second gap publisher",
            "later_usable_excludes": ["2024-12-25"],
            "dwrtf_2023_04_06": "TV 259.56 single-source only; not adopted close",
            "dwrtf_2019_08_12": {
                "cnbc": 294.58,
                "tv_archive": 294.46,
                "classification": "source_conflict",
                "cause_inference": "forbidden",
            },
            "931743": "roster unchanged; Orchestrator Appendix A eligibility 2023-07-27",
        },
        "formula": "abs(left - right) / abs(right)",
        "sqlite_readonly": {
            "DJIA_source": dji_src,
            "DWRTF_source": dw_src,
            "overlap_n": {"DJIA": len(dji_db), "DWRTF": len(dw_db)},
        },
        "pairs_from_delivered_normalized": pairs,
        "database_stop_pairs_gt_0_1pct": db_stop,
        "fresh_download_audits": {
            "fred_djia": audit_fred_independent(),
            "cnbc_dwrtf_overlap_chunk": audit_cnbc_independent(),
        },
        "flagged_dates": {
            "2024-12-25": "exclude from later usable series; CNBC raw retained",
            "2023-04-06": "DWRTF CNBC missing; TV archive 259.56 single_source",
            "2019-08-12": "DWRTF source_conflict CNBC 294.58 vs TV 294.46; no adopted side",
        },
        "tv_prior_sha256": sha256_file(PRIOR_TV),
    }

    report["delivered_normalized_samples"] = {
        "djia_required": sample_dates(fred, *DJIA_REQ, "fred", 24)
        + sample_dates(cnbc_d, *DJIA_REQ, "cnbc", 24),
        "djia_overlap": sample_dates(fred, *DJIA_OVL, "fred", 24)
        + sample_dates(dji_db, *DJIA_OVL, "sqlite", 24),
        "dwrtf_required": sample_dates(dw_cnbc, *DW_REQ, "cnbc", 24)
        + sample_dates(dw_tv, *DW_REQ, "tv_archive", 24),
        "dwrtf_overlap": sample_dates(dw_cnbc, *DW_OVL, "cnbc", 24)
        + sample_dates(dw_db, *DW_OVL, "sqlite", 24),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())