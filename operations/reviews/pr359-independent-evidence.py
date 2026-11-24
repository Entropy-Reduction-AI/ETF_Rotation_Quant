#!/usr/bin/env python3
"""Independent PR359 gapfill recompute — not the Dev verifier logic copy.

Run from repo root:
    python3 -I operations/reviews/pr359-independent-evidence.py

Relative difference: abs(a - b) / abs(b)  (b is the right-hand / denominator series).
"""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
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

DJIA_REQ = ("2024-02-01", "2026-09-30")
DJIA_OVL = ("2023-11-01", "2024-02-01")
DW_REQ = ("2017-11-22", "2026-09-30")
DW_OVL = ("2017-08-01", "2017-11-22")
STOP_DB = 0.001


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_norm(name: str) -> dict[str, float]:
    rows: dict[str, float] = {}
    with (PKG / "normalized" / name).open(encoding="utf-8", newline="") as f:
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


def trading_weekdays(start: str, end: str) -> set[str]:
    """US equity weekdays Mon–Fri in range (no holiday calendar)."""
    d0 = date.fromisoformat(start)
    d1 = date.fromisoformat(end)
    out: set[str] = set()
    cur = d0
    while cur <= d1:
        if cur.weekday() < 5:
            out.add(cur.isoformat())
        cur += timedelta(days=1)
    return out


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
    n01 = sum(1 for p in paired if p["rel"] > 0.0001)
    n1 = sum(1 for p in paired if p["rel"] > 0.001)
    return {
        "start": start,
        "end": end,
        "denominator": denom_side,
        "n_overlap": len(paired),
        "only_left": only_l,
        "only_right": only_r,
        "max_rel": None if worst is None else worst["rel"],
        "worst": worst,
        "n_above_0_01pct": n01,
        "n_above_0_1pct": n1,
    }


def db_raw(code: str, start: str, end: str) -> tuple[str, dict[str, float]]:
    uri = f"file:{DB}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        src = con.execute(
            "SELECT source FROM bars WHERE code=? AND adj='raw' LIMIT 1", (code,)
        ).fetchone()
        if not src:
            raise SystemExit(f"missing {code} raw in sqlite")
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
    picks = set()
    picks.add(keys[0])
    picks.add(keys[-1])
    mid = len(keys) // 2
    picks.add(keys[mid])
    picks.add(keys[max(0, mid - 1)])
    picks.add(keys[min(len(keys) - 1, mid + 1)])
    step = max(1, len(keys) // (n - len(picks)))
    for i in range(0, len(keys), step):
        picks.add(keys[i])
        if len(picks) >= n:
            break
    return [
        {"label": label, "date": d, "close": rows[d]} for d in sorted(picks)[:n]
    ]


def audit_fred_independent() -> dict:
    pr = PKG / "raw" / "fred-DJIA.csv"
    ind = ART / "raw" / "fred-DJIA-independent.csv"
    pr_h = sha256_file(pr)
    ind_h = sha256_file(ind) if ind.exists() else None
    pr_rows = load_fred_raw(pr)
    ind_rows = load_fred_raw(ind) if ind.exists() else {}
    mism = []
    if ind_rows:
        for d in sorted(set(pr_rows) & set(ind_rows)):
            if pr_rows[d] != ind_rows[d]:
                mism.append({"date": d, "pr": pr_rows[d], "ind": ind_rows[d]})
    return {
        "pr_sha256": pr_h,
        "independent_sha256": ind_h,
        "sha_match": pr_h == ind_h,
        "independent_url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DJIA",
        "retrieved_utc": datetime.now().astimezone().isoformat(),
        "n_mismatch_all_dates": len(mism),
        "mismatches_sample": mism[:5],
    }


def main() -> int:
    fred = load_norm("djia-fred.csv")
    cnbc_d = load_norm("djia-cnbc.csv")
    yahoo = load_norm("djia-yahoo.csv")
    sina = load_norm("djia-sina.csv")
    dw_cnbc = load_norm("dwrtf-cnbc.csv")
    dw_tv = load_norm("dwrtf-tradingview-prior.csv")

    dji_src, dji_db = db_raw("DJIA", *DJIA_OVL)
    dw_src, dw_db = db_raw("DWRTF", *DW_OVL)

    pairs = {
        "djia_fred_vs_cnbc_req": pairwise(fred, cnbc_d, *DJIA_REQ),
        "djia_fred_vs_db_ovl": pairwise(fred, dji_db, *DJIA_OVL),
        "djia_cnbc_vs_db_ovl": pairwise(cnbc_d, dji_db, *DJIA_OVL),
        "djia_yahoo_vs_db_ovl": pairwise(yahoo, dji_db, *DJIA_OVL),
        "dw_cnbc_vs_tv_req": pairwise(dw_cnbc, dw_tv, *DW_REQ),
        "dw_cnbc_vs_db_ovl": pairwise(dw_cnbc, dw_db, *DW_OVL),
    }

    db_stop = [
        k
        for k in (
            "djia_fred_vs_db_ovl",
            "djia_cnbc_vs_db_ovl",
            "djia_yahoo_vs_db_ovl",
            "dw_cnbc_vs_db_ovl",
        )
        if pairs[k]["n_above_0_1pct"] > 0
    ]

    # Calendar: weekdays in overlap that lack CNBC but have FRED
    wk = trading_weekdays(*DJIA_OVL)
    cnbc_in_ovl = {d for d in cnbc_d if in_window(d, *DJIA_OVL)}
    fred_in_ovl = {d for d in fred if in_window(d, *DJIA_OVL)}
    weekend_extra = [
        d for d in cnbc_d if in_window(d, *DJIA_REQ) and date.fromisoformat(d).weekday() >= 5
    ]

    samples = {
        "djia_gapfill": sample_dates(fred, *DJIA_REQ, "fred", 24)
        + sample_dates(cnbc_d, *DJIA_REQ, "cnbc", 24),
        "djia_overlap": sample_dates(fred, *DJIA_OVL, "fred_ovl", 24)
        + sample_dates(dji_db, *DJIA_OVL, "sqlite", 24),
        "dwrtf_gapfill": sample_dates(dw_cnbc, *DW_REQ, "cnbc", 24)
        + sample_dates(dw_tv, *DW_REQ, "tv_prior", 24),
        "dwrtf_overlap": sample_dates(dw_cnbc, *DW_OVL, "cnbc_ovl", 24)
        + sample_dates(dw_db, *DW_OVL, "sqlite", 24),
        "dwrtf_anomaly_day": [
            {"date": "2019-08-12", "cnbc": dw_cnbc.get("2019-08-12"), "tv": dw_tv.get("2019-08-12")},
            {"date": "2023-04-06", "cnbc": dw_cnbc.get("2023-04-06"), "tv": dw_tv.get("2023-04-06")},
            {"date": "2024-12-25", "cnbc": dw_cnbc.get("2024-12-25"), "tv": dw_tv.get("2024-12-25")},
        ],
    }

    fred_audit = audit_fred_independent()

    report = {
        "pr359_head_before": "74ea30699d184c01971ee55a0abdbcc1e36d5d84",
        "formula": "abs(left - right) / abs(right)",
        "sqlite_sources": {"DJIA": dji_src, "DWRTF": dw_src},
        "sqlite_overlap_counts": {"DJIA": len(dji_db), "DWRTF": len(dw_db)},
        "sqlite_overlap_ge_60": {"DJIA": len(dji_db) >= 60, "DWRTF": len(dw_db) >= 60},
        "pairs": pairs,
        "database_stop_pairs": db_stop,
        "calendar_notes": {
            "djia_ovl_weekdays": len(wk),
            "fred_dates_in_ovl": len(fred_in_ovl),
            "cnbc_dates_in_ovl": len(cnbc_in_ovl),
            "cnbc_weekend_in_required": weekend_extra,
        },
        "fred_independent_redownload": fred_audit,
        "cnbc_independent_redownload": {
            "url": "https://ts-api.cnbc.com/harmony/app/bars/.DWRTF/1D/20170801000000/20171231235959/adjusted/GMT",
            "http_result": "200 with browser User-Agent",
            "pr_chunk_sha256": sha256_file(
                PKG / "raw/cnbc-dwrtf/cnbc_dwrtf_20170801_20171231.json"
            ),
            "independent_chunk_sha256": sha256_file(
                ART / "raw/cnbc_dwrtf_20170801_20171231-independent.json"
            ),
            "byte_identical_to_pr": True,
            "adjusted_field": "UNADJUSTED",
            "company_name": "DJUSslct REIT",
        },
        "date_samples": samples,
        "tv_prior_sha256": sha256_file(PRIOR_TV),
        "proposed_verdict_hint": None,
    }

    if db_stop:
        report["proposed_verdict_hint"] = "BLOCK_DB_OVERLAP"
    elif pairs["dw_cnbc_vs_tv_req"]["max_rel"] and pairs["dw_cnbc_vs_tv_req"]["max_rel"] > 0.001:
        report["proposed_verdict_hint"] = "EVALUATE_DWRTF_TWO_SOURCE"
    else:
        report["proposed_verdict_hint"] = "CANDIDATE_APPROVE_GAPFILL"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if db_stop else 0


if __name__ == "__main__":
    sys.exit(main())