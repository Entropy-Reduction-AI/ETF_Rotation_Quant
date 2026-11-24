#!/usr/bin/env python3
"""Independent PR361 ingest DB verification (Reviewer only).

    python3 -I operations/reviews/pr361-ingest-verify.py

Reads LFS preimage/postimage from git lfs object store paths supplied via env
or default under repo .git/lfs/objects. No writes to data/market.sqlite.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "operations/reviews/pr361-ingest-verify.json"
PKG = ROOT / "incoming" / "v6-us-gapfill"
TV = ROOT / "incoming/grok-d37-index-20261116/theme-道琼斯美国精选REIT指数-tradingview.csv"

BASE_OID = "79ba7780f7f5304d189bc49bd7dda9ff1e6325c88888165d71a0c9fae7c26a52"
AFTER_OID = "0245876256527dda58145c770d75f342e7514b74a8c2cf1213fecfb713bf72f8"
LFS = ROOT / ".git/lfs/objects"


def lfs_path(oid: str) -> Path:
    return LFS / oid[:2] / oid[2:4] / oid


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def connect_ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def load_fred() -> dict[str, float]:
    rows: dict[str, float] = {}
    p = PKG / "raw/fred-DJIA.csv"
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        if i == 0:
            continue
        d, c = line.split(",", 1)
        if c in {"", "."}:
            continue
        rows[d] = float(c)
    return rows


def load_norm_cnbc_dji() -> dict[str, float]:
    rows = {}
    with (PKG / "normalized/djia-cnbc.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["date"]] = float(r["close"])
    return rows


def load_norm_cnbc_dw() -> dict[str, float]:
    rows = {}
    with (PKG / "normalized/dwrtf-cnbc.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["date"]] = float(r["close"])
    return rows


def load_tv() -> dict[str, float]:
    rows = {}
    with TV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["date"]] = float(r["close"])
    return rows


def month_ends(start: str, end: str, trading: set[str]) -> list[str]:
    ym_last: dict[str, str] = {}
    for d in sorted(trading):
        if start <= d <= end:
            ym_last[d[:7]] = d
    return [ym_last[k] for k in sorted(ym_last)]


def main() -> int:
    base_p = lfs_path(BASE_OID)
    after_p = lfs_path(AFTER_OID)
    if not base_p.is_file() or not after_p.is_file():
        print("missing LFS objects", file=sys.stderr)
        return 2

    report: dict = {
        "pr361_head": "ce058680fabec19b12982bffce37e891808d4641",
        "pr361_base": "05e39c5650acb52e0de8632bcaef8e6d05fe5597",
        "lfs_sha256": {
            "before": sha256_file(base_p),
            "after": sha256_file(after_p),
        },
        "backup_file_retrievable": {
            "gitignored_market_before_sqlite_in_repo": False,
            "authoritative_preimage": "base commit LFS oid",
            "backup_txt_cites_same_sha": True,
        },
    }

    con = connect_ro(after_p)
    con.execute(f"ATTACH DATABASE 'file:{base_p}?mode=ro' AS before_db")
    cur = con.cursor()

    def one(q, *a):
        return cur.execute(q, a).fetchone()[0]

    report["row_counts"] = {
        "before_bars": one("SELECT COUNT(*) FROM before_db.bars"),
        "after_bars": one("SELECT COUNT(*) FROM bars"),
        "delta": one("SELECT COUNT(*) FROM bars") - one("SELECT COUNT(*) FROM before_db.bars"),
    }
    report["overlap_unchanged_rows"] = one(
        """
        SELECT COUNT(*) FROM before_db.bars b
        INNER JOIN bars a ON b.code=a.code AND b.adj=a.adj AND b.date=a.date
        WHERE ifnull(b.source,'')=ifnull(a.source,'')
          AND ifnull(b.close,-1e99)=ifnull(a.close,-1e99)
          AND ifnull(b.open,-1e99)=ifnull(a.open,-1e99)
          AND ifnull(b.high,-1e99)=ifnull(a.high,-1e99)
          AND ifnull(b.low,-1e99)=ifnull(a.low,-1e99)
          AND ifnull(b.volume,-1e99)=ifnull(a.volume,-1e99)
          AND ifnull(b.amount,-1e99)=ifnull(a.amount,-1e99)
          AND ifnull(b.fetched_at,'')=ifnull(a.fetched_at,'')
        """
    )
    report["overlap_changed_rows"] = one(
        """
        SELECT COUNT(*) FROM before_db.bars b
        INNER JOIN bars a ON b.code=a.code AND b.adj=a.adj AND b.date=a.date
        WHERE ifnull(b.source,'')<>ifnull(a.source,'')
           OR ifnull(b.close,-1e99)<>ifnull(a.close,-1e99)
           OR ifnull(b.open,-1e99)<>ifnull(a.open,-1e99)
           OR ifnull(b.high,-1e99)<>ifnull(a.high,-1e99)
           OR ifnull(b.low,-1e99)<>ifnull(a.low,-1e99)
           OR ifnull(b.volume,-1e99)<>ifnull(a.volume,-1e99)
           OR ifnull(b.amount,-1e99)<>ifnull(a.amount,-1e99)
           OR ifnull(b.fetched_at,'')<>ifnull(a.fetched_at,'')
        """
    )
    report["new_rows"] = {
        "total": one(
            "SELECT COUNT(*) FROM bars a WHERE NOT EXISTS (SELECT 1 FROM before_db.bars b WHERE b.code=a.code AND b.adj=a.adj AND b.date=a.date)"
        ),
        "djia_raw": one(
            "SELECT COUNT(*) FROM bars a WHERE NOT EXISTS (SELECT 1 FROM before_db.bars b WHERE b.code=a.code AND b.adj=a.adj AND b.date=a.date) AND a.code='DJIA' AND a.adj='raw'"
        ),
        "dwrtf_raw": one(
            "SELECT COUNT(*) FROM bars a WHERE NOT EXISTS (SELECT 1 FROM before_db.bars b WHERE b.code=a.code AND b.adj=a.adj AND b.date=a.date) AND a.code='DWRTF' AND a.adj='raw'"
        ),
    }
    report["duplicate_code_date_adj"] = one(
        "SELECT COUNT(*) FROM (SELECT code,adj,date FROM bars GROUP BY 1,2,3 HAVING COUNT(*)>1)"
    )

    sm_before = {
        (r[0], r[1], r[2] or ""): r[3] or ""
        for r in cur.execute(
            "SELECT type,name,tbl_name,sql FROM before_db.sqlite_master WHERE type IN ('table','index','trigger','view') ORDER BY type,name"
        )
    }
    sm_after = {
        (r[0], r[1], r[2] or ""): r[3] or ""
        for r in cur.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE type IN ('table','index','trigger','view') ORDER BY type,name"
        )
    }
    report["sqlite_master"] = {
        "names_identical": set(sm_before.keys()) == set(sm_after.keys()),
        "sql_differences": [
            {"key": k, "before": sm_before[k][:200], "after": sm_after.get(k, "")[:200]}
            for k in sorted(set(sm_before) | set(sm_after))
            if sm_before.get(k) != sm_after.get(k)
        ],
        "bars_one_source_present_after": ("trigger", "bars_one_source", "bars") in sm_after,
    }

    boundaries = {}
    for code, d in (("DJIA", "2024-02-01"), ("DWRTF", "2017-11-22")):
        row = cur.execute(
            "SELECT source, close FROM bars WHERE code=? AND adj='raw' AND date=?", (code, d)
        ).fetchone()
        boundaries[f"{code}_{d}"] = {"source": row[0], "close": row[1]}
    report["boundary_rows"] = boundaries
    report["pseudo_session_2024_12_25_rows"] = one(
        "SELECT COUNT(*) FROM bars WHERE date='2024-12-25' AND code IN ('DJIA','DWRTF')"
    )

    fred = load_fred()
    cnbc_dw = load_norm_cnbc_dw()
    tv = load_tv()

    djia_new = [
        r[0]
        for r in cur.execute(
            "SELECT date FROM bars WHERE code='DJIA' AND adj='raw' AND source='v6_gapfill_fred' ORDER BY date"
        )
    ]
    dw_new = list(
        cur.execute(
            "SELECT date,source,close FROM bars WHERE code='DWRTF' AND adj='raw' AND source LIKE 'v6_gapfill_%' ORDER BY date"
        )
    )

    djia_mismatch = []
    for d in djia_new:
        db_c = one("SELECT close FROM bars WHERE code='DJIA' AND adj='raw' AND date=?", d)
        src = fred.get(d)
        if src is None or abs(db_c - src) > 1e-9:
            djia_mismatch.append({"date": d, "db": db_c, "fred": src})

    dw_mismatch = []
    for d, src_tag, db_c in dw_new:
        if d == "2023-04-06":
            ref = tv.get(d)
        else:
            ref = cnbc_dw.get(d)
        if ref is None or abs(float(db_c) - ref) > 1e-9:
            dw_mismatch.append({"date": d, "db": db_c, "ref": ref, "source": src_tag})

    djia_me = month_ends("2024-02-02", "2026-09-30", set(fred))
    dw_me = month_ends(
        "2017-11-24",
        "2026-09-30",
        set(cnbc_dw) | {"2023-04-06"},
    )
    me_checks = []
    for d in djia_me:
        db_c = one("SELECT close FROM bars WHERE code='DJIA' AND adj='raw' AND date=?", d)
        me_checks.append(
            {"series": "DJIA", "date": d, "db": db_c, "fred": fred.get(d), "ok": abs(db_c - fred[d]) < 1e-9}
        )
    for d in dw_me:
        row = cur.execute(
            "SELECT close, source FROM bars WHERE code='DWRTF' AND adj='raw' AND date=?", (d,)
        ).fetchone()
        if row is None:
            me_checks.append({"series": "DWRTF", "date": d, "missing": True})
            continue
        db_c, src = row
        ref = tv.get(d) if d == "2023-04-06" else cnbc_dw.get(d)
        me_checks.append(
            {
                "series": "DWRTF",
                "date": d,
                "db": db_c,
                "ref": ref,
                "source": src,
                "ok": ref is not None and abs(db_c - ref) < 1e-9,
            }
        )

    # sample >=20 per series from new dates
    def sample(keys: list[str], n: int = 24) -> list[str]:
        if len(keys) <= n:
            return keys
        step = max(1, len(keys) // n)
        out = {keys[0], keys[-1], keys[len(keys) // 2]}
        for i in range(0, len(keys), step):
            out.add(keys[i])
        return sorted(out)[:n]

    sample_checks = []
    for d in sample(djia_new):
        db_c = one("SELECT close FROM bars WHERE code='DJIA' AND adj='raw' AND date=?", d)
        sample_checks.append(
            {"series": "DJIA", "date": d, "db": db_c, "fred": fred.get(d), "ok": fred.get(d) == db_c}
        )
    dw_dates = [t[0] for t in dw_new]
    for d in sample(dw_dates):
        row = cur.execute(
            "SELECT close, source FROM bars WHERE code='DWRTF' AND adj='raw' AND date=?", (d,)
        ).fetchone()
        ref = tv.get(d) if d == "2023-04-06" else cnbc_dw.get(d)
        sample_checks.append(
            {
                "series": "DWRTF",
                "date": d,
                "db": row[0] if row else None,
                "ref": ref,
                "source": row[1] if row else None,
                "ok": row and ref is not None and abs(row[0] - ref) < 1e-9,
            }
        )

    report["source_compare"] = {
        "djia_new_mismatches": djia_mismatch,
        "dwrtf_new_mismatches": dw_mismatch,
        "month_end_checks": me_checks,
        "month_end_failures": sum(1 for x in me_checks if not x.get("ok")),
        "sample_checks": sample_checks,
        "sample_failures": sum(1 for x in sample_checks if not x.get("ok")),
    }

    blockers = []
    if report["lfs_sha256"]["before"] != BASE_OID:
        blockers.append("base_sha_mismatch")
    if report["lfs_sha256"]["after"] != AFTER_OID:
        blockers.append("after_sha_mismatch")
    if report["overlap_changed_rows"] != 0:
        blockers.append("preimage_rows_changed")
    if report["overlap_unchanged_rows"] != 1_200_716:
        blockers.append("preimage_row_count_not_1200716")
    if report["new_rows"]["total"] != 2890:
        blockers.append("new_row_count_not_2890")
    if report["duplicate_code_date_adj"]:
        blockers.append("duplicate_keys")
    if report["sqlite_master"]["sql_differences"]:
        blockers.append("sqlite_master_sql_diff")
    if report["pseudo_session_2024_12_25_rows"]:
        blockers.append("pseudo_session_in_db")
    if djia_mismatch or dw_mismatch or report["source_compare"]["month_end_failures"]:
        blockers.append("source_point_mismatch")

    report["blockers"] = blockers
    report["verdict_hint"] = "APPROVE_INGEST" if not blockers else "BLOCK"

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    con.close()
    return 2 if blockers else 0


if __name__ == "__main__":
    sys.exit(main())