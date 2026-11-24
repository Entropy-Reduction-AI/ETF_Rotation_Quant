#!/usr/bin/env python3
"""Independent PR361 raw index ingest verification (Reviewer).

    python3 -I operations/reviews/pr361-ingest-verify.py

Point-level closes only — no returns. DWRTF CNBC reference is parsed from archived
JSON under incoming/v6-us-gapfill/raw/cnbc-dwrtf/ (tradeTime YYYYMMDD…, not Dev normalizer).
"""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "operations/reviews/pr361-ingest-verify.json"
PKG = ROOT / "incoming" / "v6-us-gapfill"
CNBC_DW = PKG / "raw/cnbc-dwrtf"
FRED_RAW = PKG / "raw/fred-DJIA.csv"
TV_RAW = ROOT / "incoming/grok-d37-index-20261116/theme-道琼斯美国精选REIT指数-tradingview.csv"
SIDEcar_PATH = "operations/evidence/v6-us-raw-index-ingest/date-flags.csv"

BASE_OID = "79ba7780f7f5304d189bc49bd7dda9ff1e6325c88888165d71a0c9fae7c26a52"
AFTER_OID = "0245876256527dda58145c770d75f342e7514b74a8c2cf1213fecfb713bf72f8"
LFS = ROOT / ".git/lfs/objects"

DJIA_INSERT_START = "2024-02-02"
DJIA_INSERT_END = "2026-09-30"
DW_INSERT_START = "2017-11-24"
DW_INSERT_END = "2026-09-30"
PSEUDO = "2024-12-25"
TV_SINGLE = "2023-04-06"
CONFLICT = "2019-08-12"


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


def load_fred_raw() -> dict[str, float]:
    rows: dict[str, float] = {}
    for i, line in enumerate(FRED_RAW.read_text(encoding="utf-8").splitlines()):
        if i == 0:
            continue
        d, c = line.split(",", 1)
        if c in {"", "."}:
            continue
        rows[d] = float(c)
    return rows


def load_cnbc_dwrtf_from_json() -> tuple[dict[str, float], dict]:
    """Independent CNBC archive parse (same date rule as gapfill_compare: tradeTime[:8])."""
    meta = {"files": [], "parse_rule": "tradeTime[:8] -> YYYY-MM-DD", "timezone_note": "CNBC bar tradeTime wall date; not re-shifted to UTC"}
    rows: dict[str, float] = {}
    for path in sorted(CNBC_DW.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        details = payload.get("requestDetails", {})
        if details.get("adjusted") != "UNADJUSTED":
            raise SystemExit(f"{path.name}: not UNADJUSTED")
        meta["files"].append(
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
                "symbol": details.get("symbol"),
            }
        )
        for item in payload["barData"]["priceBars"]:
            compact = item["tradeTime"][:8]
            day = f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}"
            close = float(item["close"])
            if day in rows and rows[day] != close:
                raise SystemExit(f"CNBC raw duplicate mismatch {day}")
            rows[day] = close
    return rows, meta


def load_dev_normalized_cnbc_dw() -> dict[str, float]:
    rows = {}
    with (PKG / "normalized/dwrtf-cnbc.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["date"]] = float(r["close"])
    return rows


def load_tv_archive() -> dict[str, float]:
    rows = {}
    with TV_RAW.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["date"]] = float(r["close"])
    return rows


def git_show(path: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"ce058680:{path}"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
    )


def table_payload_hash(con: sqlite3.Connection, table: str, order_by: str) -> str:
    rows = con.execute(f"SELECT * FROM {table} ORDER BY {order_by}").fetchall()
    return hashlib.sha256(repr(rows).encode()).hexdigest()


def month_ends(dates: list[str]) -> list[str]:
    last: dict[str, str] = {}
    for d in sorted(dates):
        last[d[:7]] = d
    return [last[k] for k in sorted(last)]


def close_match(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


def main() -> int:
    base_p = lfs_path(BASE_OID)
    after_p = lfs_path(AFTER_OID)
    if not base_p.is_file() or not after_p.is_file():
        print("missing LFS objects", file=sys.stderr)
        return 2

    fred = load_fred_raw()
    cnbc_raw, cnbc_meta = load_cnbc_dwrtf_from_json()
    cnbc_norm = load_dev_normalized_cnbc_dw()
    tv = load_tv_archive()

    report: dict = {
        "pr361_head": "ce058680fabec19b12982bffce37e891808d4641",
        "pr361_base": "05e39c5650acb52e0de8632bcaef8e6d05fe5597",
        "lfs_sha256": {"before": sha256_file(base_p), "after": sha256_file(after_p)},
        "backup_retrieval": {
            "market_before_sqlite_in_repo": False,
            "reviewer_cannot_verify_local_byte_copy": True,
            "preimage_used_for_compare": "base_commit LFS object (reconstructs cited before SHA when oid matches)",
            "does_not_prove_dev_ran_copy_command": True,
        },
        "cnbc_raw_parse": cnbc_meta,
        "dev_normalized_vs_reviewer_cnbc_raw": {},
    }

    norm_vs_raw = []
    for d in sorted(set(cnbc_norm) & set(cnbc_raw)):
        if cnbc_norm[d] != cnbc_raw[d]:
            norm_vs_raw.append({"date": d, "normalized": cnbc_norm[d], "reviewer_raw_json": cnbc_raw[d]})
    report["dev_normalized_vs_reviewer_cnbc_raw"] = {
        "mismatch_count": len(norm_vs_raw),
        "mismatch_sample": norm_vs_raw[:10],
        "note": "informational; DB ingest checks use reviewer CNBC JSON parse only",
    }

    def integrity_ok(path: Path) -> str:
        with connect_ro(path) as c:
            return c.execute("PRAGMA integrity_check").fetchone()[0]

    con = connect_ro(after_p)
    con.execute(f"ATTACH DATABASE 'file:{base_p}?mode=ro' AS before_db")
    cur = con.cursor()

    def one(q, *a):
        return cur.execute(q, a).fetchone()[0]

    report["integrity_check"] = {"before": integrity_ok(base_p), "after": integrity_ok(after_p)}

    report["series_raw_counts"] = {
        "before": {
            r[0]: r[1]
            for r in cur.execute(
                "SELECT code, COUNT(*) FROM before_db.bars WHERE adj='raw' AND code IN ('DJIA','DWRTF') GROUP BY code"
            )
        },
        "after": {
            r[0]: r[1]
            for r in cur.execute(
                "SELECT code, COUNT(*) FROM bars WHERE adj='raw' AND code IN ('DJIA','DWRTF') GROUP BY code"
            )
        },
    }

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

    report["v6_gapfill_source_distribution_after"] = {
        r[0]: r[1]
        for r in cur.execute(
            "SELECT source, COUNT(*) FROM bars WHERE adj='raw' AND source LIKE 'v6_gapfill%' GROUP BY source ORDER BY source"
        )
    }

    report["max_dates_raw"] = {
        r[0]: r[1]
        for r in cur.execute(
            "SELECT code, MAX(date) FROM bars WHERE adj='raw' GROUP BY code ORDER BY code"
        )
    }
    report["max_dates_djia_dwrtf"] = {
        c: report["max_dates_raw"][c]
        for c in ("DJIA", "DWRTF")
        if c in report["max_dates_raw"]
    }
    beyond_cut = [
        (r[0], r[1])
        for r in cur.execute(
            "SELECT code, MAX(date) FROM bars WHERE adj='raw' GROUP BY code HAVING MAX(date) > '2026-09-30' ORDER BY code"
        )
    ]
    report["codes_raw_beyond_2026_09_30"] = {"count": len(beyond_cut), "codes": beyond_cut}
    before_max = {
        r[0]: r[1]
        for r in cur.execute("SELECT code, MAX(date) FROM before_db.bars WHERE adj='raw' GROUP BY code")
    }
    after_max = report["max_dates_raw"]
    max_shift = []
    for code in sorted(set(before_max) | set(after_max)):
        b, a = before_max.get(code), after_max.get(code)
        if b == a:
            continue
        if code in {"DJIA", "DWRTF"}:
            continue
        max_shift.append({"code": code, "before_max": b, "after_max": a})
    report["raw_max_date_shift_except_djia_dwrtf"] = max_shift

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

    report["aux_tables_full_hash"] = {}
    for table, order in (
        ("calendar", "date"),
        ("universe", "ord, theme_id"),
        ("meta", "key"),
    ):
        report["aux_tables_full_hash"][table] = {
            "before": table_payload_hash(con, f"before_db.{table}", order),
            "after": table_payload_hash(con, table, order),
            "identical": table_payload_hash(con, f"before_db.{table}", order)
            == table_payload_hash(con, table, order),
        }

    sm_before = {
        k: v
        for k, v in (
            (r[0], r[1])
            for r in cur.execute(
                "SELECT type||'|'||name||'|'||ifnull(tbl_name,''), ifnull(sql,'') FROM before_db.sqlite_master WHERE type IN ('table','index','trigger','view') ORDER BY 1"
            )
        )
    }
    sm_after = {
        k: v
        for k, v in (
            (r[0], r[1])
            for r in cur.execute(
                "SELECT type||'|'||name||'|'||ifnull(tbl_name,''), ifnull(sql,'') FROM sqlite_master WHERE type IN ('table','index','trigger','view') ORDER BY 1"
            )
        )
    }
    report["sqlite_master"] = {
        "object_count_before": len(sm_before),
        "object_count_after": len(sm_after),
        "keys_identical": set(sm_before) == set(sm_after),
        "sql_diff_count": sum(1 for k in set(sm_before) | set(sm_after) if sm_before.get(k) != sm_after.get(k)),
    }

    boundaries = {}
    for code, d, exp_src, exp_close in (
        ("DJIA", "2024-02-01", "eastmoney_index", 38519.84),
        ("DWRTF", "2017-11-22", "d37_r6", 275.66),
    ):
        row = cur.execute(
            "SELECT source, close FROM bars WHERE code=? AND adj='raw' AND date=?", (code, d)
        ).fetchone()
        boundaries[f"{code}_{d}"] = {
            "observed": {"source": row[0], "close": row[1]},
            "expected": {"source": exp_src, "close": exp_close},
            "ok": row[0] == exp_src and row[1] == exp_close,
        }
    report["boundary_rows"] = boundaries
    report["pseudo_session_2024_12_25_rows"] = one(
        "SELECT COUNT(*) FROM bars WHERE date=? AND code IN ('DJIA','DWRTF')", PSEUDO
    )

    djia_new = [
        r[0]
        for r in cur.execute(
            "SELECT date FROM bars WHERE code='DJIA' AND adj='raw' AND source='v6_gapfill_fred' AND date>=? AND date<=? ORDER BY date",
            (DJIA_INSERT_START, DJIA_INSERT_END),
        )
    ]
    dw_new = list(
        cur.execute(
            """
            SELECT date, source, close FROM bars
            WHERE code='DWRTF' AND adj='raw' AND source LIKE 'v6_gapfill_%'
              AND date>=? AND date<=? ORDER BY date
            """,
            (DW_INSERT_START, DW_INSERT_END),
        )
    )

    djia_full = []
    for d in djia_new:
        db_c = float(one("SELECT close FROM bars WHERE code='DJIA' AND adj='raw' AND date=?", d))
        src_c = fred.get(d)
        tag = one("SELECT source FROM bars WHERE code='DJIA' AND adj='raw' AND date=?", d)
        djia_full.append(
            {
                "date": d,
                "db_close": db_c,
                "fred_raw_close": src_c,
                "source": tag,
                "ok": src_c is not None and close_match(db_c, src_c),
            }
        )

    dw_full = []
    for d, src_tag, db_c in dw_new:
        db_c = float(db_c)
        if d == TV_SINGLE:
            ref = tv.get(d)
            ref_kind = "tv_archive_csv"
        else:
            ref = cnbc_raw.get(d)
            ref_kind = "cnbc_json_raw"
        dw_full.append(
            {
                "date": d,
                "db_close": db_c,
                "ref_close": ref,
                "ref_kind": ref_kind,
                "source": src_tag,
                "ok": ref is not None and close_match(db_c, float(ref)),
            }
        )

    djia_me_dates = month_ends(djia_new)
    dw_me_dates = month_ends([t[0] for t in dw_new])
    me_checks = [x for x in djia_full if x["date"] in djia_me_dates] + [
        x for x in dw_full if x["date"] in dw_me_dates
    ]

    def sample_entries(full: list[dict], n: int = 24) -> list[dict]:
        keys = [x["date"] for x in full]
        if len(keys) <= n:
            return full
        picks = {keys[0], keys[-1], keys[len(keys) // 2]}
        step = max(1, len(keys) // (n - len(picks)))
        for i in range(0, len(keys), step):
            picks.add(keys[i])
        return [x for x in full if x["date"] in picks]

    report["source_compare"] = {
        "djia_insert_window": {"start": DJIA_INSERT_START, "end": DJIA_INSERT_END, "n_new_rows": len(djia_new)},
        "dwrtf_insert_window": {"start": DW_INSERT_START, "end": DW_INSERT_END, "n_new_rows": len(dw_new)},
        "djia_all_new_rows_vs_fred_raw": {
            "n": len(djia_full),
            "failures": sum(1 for x in djia_full if not x["ok"]),
            "failure_sample": [x for x in djia_full if not x["ok"]][:10],
        },
        "dwrtf_all_new_rows_vs_original": {
            "n": len(dw_full),
            "failures": sum(1 for x in dw_full if not x["ok"]),
            "failure_sample": [x for x in dw_full if not x["ok"]][:10],
        },
        "month_end_count": {"djia": len(djia_me_dates), "dwrtf": len(dw_me_dates)},
        "month_end_checks": me_checks,
        "month_end_failures": sum(1 for x in me_checks if not x["ok"]),
        "sample_checks": sample_entries(djia_full) + sample_entries(dw_full),
        "sample_n": len(sample_entries(djia_full) + sample_entries(dw_full)),
    }

    conflict_row = cur.execute(
        "SELECT close, source FROM bars WHERE code='DWRTF' AND adj='raw' AND date=?",
        (CONFLICT,),
    ).fetchone()
    tv_row = cur.execute(
        "SELECT close, source FROM bars WHERE code='DWRTF' AND adj='raw' AND date=?",
        (TV_SINGLE,),
    ).fetchone()

    sidecar_text = git_show(SIDEcar_PATH)
    sidecar_rows = list(csv.DictReader(sidecar_text.splitlines()))
    report["sidecar_date_flags"] = {
        "sha256": hashlib.sha256(sidecar_text.encode()).hexdigest(),
        "rows": sidecar_rows,
        "db_conflict_day": {
            "date": CONFLICT,
            "db_close": conflict_row[0] if conflict_row else None,
            "db_source": conflict_row[1] if conflict_row else None,
            "sidecar_adopted_close": next(
                (r["adopted_close"] for r in sidecar_rows if r["date"] == CONFLICT), None
            ),
            "tv_archive_close": tv.get(CONFLICT),
        },
        "db_single_source_day": {
            "date": TV_SINGLE,
            "db_close": tv_row[0] if tv_row else None,
            "db_source": tv_row[1] if tv_row else None,
            "tv_archive_close": tv.get(TV_SINGLE),
        },
    }

    blockers: list[str] = []
    if report["lfs_sha256"]["before"] != BASE_OID:
        blockers.append("base_sha_mismatch")
    if report["lfs_sha256"]["after"] != AFTER_OID:
        blockers.append("after_sha_mismatch")
    if report["integrity_check"]["before"] != "ok" or report["integrity_check"]["after"] != "ok":
        blockers.append("integrity_check_failed")
    if report["overlap_changed_rows"] != 0:
        blockers.append("preimage_rows_changed")
    if report["overlap_unchanged_rows"] != 1_200_716:
        blockers.append("preimage_row_count_not_1200716")
    if report["new_rows"]["total"] != 2890:
        blockers.append("new_row_count_not_2890")
    if report["new_rows"]["djia_raw"] != 667:
        blockers.append("djia_new_not_667")
    if report["new_rows"]["dwrtf_raw"] != 2223:
        blockers.append("dwrtf_new_not_2223")
    exp_src = {"v6_gapfill_fred": 667, "v6_gapfill_cnbc": 2222, "v6_gapfill_tv": 1}
    for k, v in exp_src.items():
        if report["v6_gapfill_source_distribution_after"].get(k) != v:
            blockers.append(f"source_count_{k}_not_{v}")
    if report["series_raw_counts"]["before"].get("DJIA") != 8515:
        blockers.append("djia_before_not_8515")
    if report["series_raw_counts"]["after"].get("DJIA") != 9182:
        blockers.append("djia_after_not_9182")
    if report["series_raw_counts"]["before"].get("DWRTF") != 4752:
        blockers.append("dwrtf_before_not_4752")
    if report["series_raw_counts"]["after"].get("DWRTF") != 6975:
        blockers.append("dwrtf_after_not_6975")
    if report["sqlite_master"]["sql_diff_count"]:
        blockers.append("sqlite_master_sql_diff")
    if not all(b["ok"] for b in boundaries.values()):
        blockers.append("boundary_changed")
    if report["pseudo_session_2024_12_25_rows"]:
        blockers.append("pseudo_session_in_db")
    if report["raw_max_date_shift_except_djia_dwrtf"]:
        blockers.append("non_gapfill_raw_max_date_shifted")
    if report["source_compare"]["month_end_count"]["dwrtf"] != 107:
        blockers.append("dwrtf_month_end_count_not_107")
    if report["max_dates_djia_dwrtf"].get("DJIA") != "2026-09-30" or report["max_dates_djia_dwrtf"].get(
        "DWRTF"
    ) != "2026-09-30":
        blockers.append("djia_or_dwrtf_max_not_2026_09_30")
    if not all(t["identical"] for t in report["aux_tables_full_hash"].values()):
        blockers.append("aux_table_content_changed")
    if report["source_compare"]["djia_all_new_rows_vs_fred_raw"]["failures"]:
        blockers.append("djia_point_mismatch_vs_fred_raw")
    if report["source_compare"]["dwrtf_all_new_rows_vs_original"]["failures"]:
        blockers.append("dwrtf_point_mismatch_vs_original_raw")
    if report["source_compare"]["month_end_failures"]:
        blockers.append("month_end_point_mismatch")
    if conflict_row and float(conflict_row[0]) != 294.58:
        blockers.append("conflict_day_close_not_294_58")
    if conflict_row and conflict_row[1] != "v6_gapfill_cnbc":
        blockers.append("conflict_day_source_not_cnbc")
    if tv_row and float(tv_row[0]) != 259.56:
        blockers.append("single_source_day_not_259_56")

    report["blockers"] = blockers
    report["verdict_hint"] = "APPROVE_INGEST" if not blockers else "NOT_READY"

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict_hint": report["verdict_hint"], "blockers": blockers}, ensure_ascii=False))
    con.close()
    return 2 if blockers else 0


if __name__ == "__main__":
    sys.exit(main())