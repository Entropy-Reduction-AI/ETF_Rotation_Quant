#!/usr/bin/env python3
"""D38 A-share theme splice · Reviewer independent recheck (PR #313).

Usage:
  BEFORE_DB=/agent/repos/ETF_Rotation_Quant/data/market.sqlite \\
  AFTER_DB=/tmp/d38-pr313/data/market.sqlite \\
  DEV_WORKTREE=/tmp/d38-pr313 \\
  .venv/bin/python operations/reviews/diag/d38-a-theme/d38-a-theme-verify.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DEV = Path(os.environ.get("DEV_WORKTREE", "/tmp/d38-pr313"))
BEFORE_DB = Path(os.environ.get("BEFORE_DB", ROOT / "data/market.sqlite"))
AFTER_DB = Path(os.environ.get("AFTER_DB", DEV / "data/market.sqlite"))
OUT = Path(__file__).resolve().parent / "d38-a-theme-recalc.json"

CODES = (
    "H30184", "931743", "930713", "931160", "H30202", "H30590", "931494", "000819",
    "399998", "930606", "H30187", "930997", "931151", "399967", "000913", "931152",
    "000932", "399987", "000949", "399986", "399975", "931775", "000015", "H30269",
    "000688",
)
SPOTCHECK = (
    "931743", "000688", "H30187", "000015", "930606",
    "H30184", "000819", "930713", "399998",
)
BEFORE_SHA = "d0b947d90b444eb1d874a04df6bcb1974cbea4422b489f214a56c0a658abf0d9"
AFTER_SHA = "c07297f8372c2b4dd8f79417306f4dda3b2b49db3cb2523a6ad306c13523588b"
MEDIAN_LIMIT = 0.0001
DEV_HEAD = "ca74943a723bfd94e042b59bc24204747fbf30c9"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def row_sig(row: tuple) -> str:
    return repr(row)


def bars_fingerprint(con: sqlite3.Connection) -> dict[tuple, str]:
    cur = con.execute(
        "SELECT code, date, adj, open, high, low, close, volume, source, fetched_at "
        "FROM bars ORDER BY code, date, adj"
    )
    return {(r[0], r[1], r[2]): row_sig(r) for r in cur}


def append_only_check() -> dict:
    bcon = sqlite3.connect(f"file:{BEFORE_DB}?mode=ro", uri=True)
    acon = sqlite3.connect(f"file:{AFTER_DB}?mode=ro", uri=True)
    before = bars_fingerprint(bcon)
    after = bars_fingerprint(acon)
    mismatches = []
    for key, sig in before.items():
        if key not in after:
            mismatches.append({"key": key, "issue": "missing_in_after"})
        elif after[key] != sig:
            mismatches.append({"key": key, "issue": "value_changed"})
    new_keys = [k for k in after if k not in before]
    bcon.close()
    acon.close()
    return {
        "before_rows": len(before),
        "after_rows": len(after),
        "new_rows": len(new_keys),
        "mismatches": len(mismatches),
        "mismatch_samples": mismatches[:5],
        "new_row_codes": sorted({k[0] for k in new_keys}),
        "pass": len(mismatches) == 0,
    }


def code_db_stats(con: sqlite3.Connection, code: str) -> dict:
    row = con.execute(
        "SELECT COUNT(*), MIN(date), MAX(date), "
        "(SELECT COUNT(*) FROM bars b2 WHERE b2.code=? AND b2.adj='raw' AND b2.date < "
        "(SELECT publish FROM (SELECT 1)) ) "
        "FROM bars WHERE code=? AND adj='raw'",
        (code, code),
    ).fetchone()
    # simpler queries
    n, first, last = con.execute(
        "SELECT COUNT(*), MIN(date), MAX(date) FROM bars WHERE code=? AND adj='raw'", (code,)
    ).fetchone()
    return {"rows": n or 0, "first": first or "", "last": last or ""}


def roster_summary() -> dict:
    path = DEV / "results/v51-diag/d37/s1-splice-roster.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    by_index = {}
    for row in rows:
        ic = (row.get("index_code") or "").strip()
        if ic in CODES:
            by_index[ic] = row
    missing = [c for c in CODES if c not in by_index]
    no_pub = [c for c, r in by_index.items() if not (r.get("publish_date") or "").strip()]
    status_counts = {}
    for c in CODES:
        st = by_index.get(c, {}).get("status", "?")
        status_counts[st] = status_counts.get(st, 0) + 1
    return {
        "found": len(by_index),
        "missing_codes": missing,
        "no_publish_date": no_pub,
        "status_counts": status_counts,
        "rows": {c: {k: by_index[c].get(k, "") for k in (
            "container_id", "status", "publish_date", "bars_code", "index_code"
        )} for c in CODES if c in by_index},
    }


def evidence_publish_match() -> list[dict]:
    out = []
    for code in CODES:
        note_path = DEV / f"operations/evidence/d38-a-theme/csi-{code}-note.json"
        roster_path = DEV / "results/v51-diag/d37/s1-splice-roster.csv"
        roster_pub = ""
        for row in csv.DictReader(roster_path.open(encoding="utf-8")):
            if (row.get("index_code") or "").strip() == code:
                roster_pub = row.get("publish_date", "")
                break
        note = {}
        if note_path.is_file():
            note = json.loads(note_path.read_text(encoding="utf-8"))
        out.append({
            "code": code,
            "note_publish": note.get("publish"),
            "note_base": note.get("base_date"),
            "roster_publish": roster_pub,
            "match": note.get("publish") == roster_pub and bool(roster_pub),
            "screenshot_bytes": note.get("screenshot_bytes", 0),
        })
    return out


def dashboard_counts() -> dict:
    SKIP = {"crude-oil", "cross-border-commodity", "theme-中信证券印度ETP指数"}
    GROK = {
        "chinext", "soymeal", "theme-HSFML25", "theme-HSISC", "theme-HSSC50", "theme-HSSCAMHI",
        "theme-HSSCHKY", "theme-HSSCITI", "theme-HSSCPB", "theme-HSSCSOY", "theme-HSSCT",
        "theme-MSCI China Value Weighted Index", "theme-MSCI USA 50 Index",
        "theme-S&P 500 Energy Sector Index(NTR)", "theme-SPAHLVCP", "theme-iEdge Emerging Asia Select 50 Index",
        "theme-东证指数", "theme-富时亚太低碳精选指数", "theme-富时沙特阿拉伯指数", "theme-巴西IBOVESPA指数",
        "theme-恒生中国企业指数", "theme-恒生中国央企指数", "theme-恒生创新药指数", "theme-恒生生物科技指数",
        "theme-新交所泛东南亚科技指数", "theme-标普500信息科技指数", "theme-标普500医疗保健等权重指数",
        "theme-标普500消费精选指数", "theme-标普中国新经济行业指数", "theme-标普全球石油指数",
        "theme-标普生物科技精选行业指数", "theme-标普石油天然气勘探及生产精选行业指数",
        "theme-标普美国品质消费股票指数", "theme-法兰克福DAX指数", "theme-道琼斯美国石油开发与生产指数",
        "theme-道琼斯美国精选REIT指数",
    }

    def state(x):
        if x["status"] == "already":
            return "有自己的历史"
        if x["status"] == "spliced":
            return "已接上指数"
        if x["container_id"].startswith(("us-xl", "hk-hs")) or x["container_id"] in SKIP:
            return "无需接"
        if x["container_id"] in GROK:
            return "在 Grok 第六轮"
        return "未接上"

    rows = list(csv.DictReader((DEV / "results/v51-diag/d37/s1-splice-roster.csv").open(encoding="utf-8")))
    counts = {}
    for row in rows:
        st = state(row)
        counts[st] = counts.get(st, 0) + 1
    have = counts.get("有自己的历史", 0) + counts.get("已接上指数", 0)
    return {
        "total_containers": len(rows),
        "have_pre_list_history": have,
        "grok_r6": counts.get("在 Grok 第六轮", 0),
        "not_spliced": counts.get("未接上", 0),
        "by_state": counts,
    }


def universe_ingest_codes() -> list[dict]:
    uni = {r["research_index_code"]: r for r in csv.DictReader((DEV / "data/universe.csv").open(encoding="utf-8"))}
    roster_rows = list(csv.DictReader((DEV / "results/v51-diag/d37/s1-splice-roster.csv").open(encoding="utf-8")))
    roster_by_ic = {(r.get("index_code") or "").strip(): r for r in roster_rows}
    out = []
    for code in CODES:
        row = uni.get(code, {})
        ros = roster_by_ic.get(code, {})
        bars = (ros.get("bars_code") or "").strip() or code
        reason = ros.get("reason", "")
        tr = row.get("tr_code_candidates", "")
        out.append({
            "code": code,
            "tr_code_candidates": tr,
            "bars_code": bars,
            "ingest_is_price_index": bars == code,
            "reason_snippet": reason[:120],
        })
    return out


def bars_before_publish(con: sqlite3.Connection, code: str, publish: str) -> int:
    if not publish:
        return -1
    return int(
        con.execute(
            "SELECT COUNT(*) FROM bars WHERE code=? AND adj='raw' AND date<?", (code, publish)
        ).fetchone()[0]
    )


def db_delta_codes() -> dict:
    bcon = sqlite3.connect(f"file:{BEFORE_DB}?mode=ro", uri=True)
    acon = sqlite3.connect(f"file:{AFTER_DB}?mode=ro", uri=True)
    deltas = {}
    for code in CODES:
        br = bcon.execute("SELECT COUNT(*) FROM bars WHERE code=? AND adj='raw'", (code,)).fetchone()[0]
        ar = acon.execute("SELECT COUNT(*) FROM bars WHERE code=? AND adj='raw'", (code,)).fetchone()[0]
        if br != ar:
            bf = bcon.execute(
                "SELECT MIN(date), MAX(date) FROM bars WHERE code=? AND adj='raw'", (code,)
            ).fetchone()
            af = acon.execute(
                "SELECT MIN(date), MAX(date) FROM bars WHERE code=? AND adj='raw'", (code,)
            ).fetchone()
            deltas[code] = {
                "before_rows": br, "after_rows": ar, "delta": ar - br,
                "before_span": bf, "after_span": af,
            }
    bcon.close()
    acon.close()
    return deltas


def run_spotchecks() -> list[dict]:
    sys.path.insert(0, str(DEV))
    from src.v51.d37_round4 import fetch_eastmoney  # noqa: E402
    from src.data import http  # noqa: E402

    def em_closes(code: str) -> dict[str, float]:
        raw = http.get(
            "https://searchapi.eastmoney.com/api/suggest/get",
            {"input": code, "type": "14", "count": "12"},
            headers={"Referer": "https://www.eastmoney.com/"},
            timeout=25,
        )
        payload = json.loads(raw.decode("utf-8", "replace"))
        rows = ((payload.get("QuotationCodeTable") or {}).get("Data") or [])
        for item in rows:
            if str(item.get("Code") or "") != code:
                continue
            if "指数" not in str(item.get("SecurityTypeName") or ""):
                continue
            secid = str(item.get("QuoteID") or "")
            if not secid:
                continue
            _, bars = fetch_eastmoney(secid)
            out = {}
            for row in bars:
                day = str(row.get("date") or "")[:10]
                try:
                    px = float(row.get("close"))
                except (TypeError, ValueError):
                    continue
                if day and px > 0:
                    out[day] = px
            return out
        return {}

    roster = {(r.get("index_code") or "").strip(): r for r in csv.DictReader(
        (DEV / "results/v51-diag/d37/s1-splice-roster.csv").open(encoding="utf-8")
    )}
    acon = sqlite3.connect(f"file:{AFTER_DB}?mode=ro", uri=True)
    results = []
    for code in SPOTCHECK:
        pub = (roster.get(code, {}).get("publish_date") or "").strip()
        bars_code = (roster.get(code, {}).get("bars_code") or code).strip() or code
        em = em_closes(bars_code)
        db = {}
        for day, px in acon.execute(
            "SELECT date, close FROM bars WHERE code=? AND adj='raw' AND close>0 AND date>=? AND date<=?",
            (bars_code, pub or "1900-01-01", "2026-09-30"),
        ):
            db[str(day)[:10]] = float(px)
        days = sorted(set(em) & set(db))
        gaps = [abs(db[d] / em[d] - 1) for d in days if em[d]]
        median = statistics.median(gaps) if gaps else None
        results.append({
            "code": code,
            "bars_code": bars_code,
            "publish_date": pub,
            "overlap_days": len(days),
            "median_rel_close_gap": median,
            "median_pct": f"{median:.4%}" if median is not None else None,
            "gate_ok": median is not None and median <= MEDIAN_LIMIT,
            "bars_before_publish": bars_before_publish(acon, bars_code, pub) if pub else None,
            "db_rows": len(db),
            "em_rows_since_pub": len({d: v for d, v in em.items() if not pub or d >= pub}),
        })
    # H30187 / 000813
    h30187_rows = acon.execute(
        "SELECT COUNT(*) FROM bars WHERE code='H30187' AND adj='raw'"
    ).fetchone()[0]
    h813_after = acon.execute(
        "SELECT COUNT(*) FROM bars WHERE code='000813' AND adj='raw'"
    ).fetchone()[0]
    h813_before = sqlite3.connect(f"file:{BEFORE_DB}?mode=ro", uri=True).execute(
        "SELECT COUNT(*) FROM bars WHERE code='000813' AND adj='raw'"
    ).fetchone()[0]
    results.append({
        "code": "H30187_check",
        "h30187_db_rows": h30187_rows,
        "000813_before_rows": h813_before,
        "000813_after_rows": h813_after,
        "000813_unchanged": h813_before == h813_after,
    })
    acon.close()
    return results


def main() -> int:
    payload = {
        "dev_pr": 313,
        "dev_head": DEV_HEAD,
        "before_db": str(BEFORE_DB),
        "after_db": str(AFTER_DB),
        "sha256": {
            "before": sha256_file(BEFORE_DB),
            "after": sha256_file(AFTER_DB),
            "expected_before": BEFORE_SHA,
            "expected_after": AFTER_SHA,
            "before_match": sha256_file(BEFORE_DB) == BEFORE_SHA,
            "after_match": sha256_file(AFTER_DB) == AFTER_SHA,
        },
        "append_only": append_only_check(),
        "db_row_deltas": db_delta_codes(),
        "roster": roster_summary(),
        "evidence_publish": evidence_publish_match(),
        "dashboard": dashboard_counts(),
        "universe_ingest": universe_ingest_codes(),
        "spotchecks": [],
    }
    try:
        payload["spotchecks"] = run_spotchecks()
    except Exception as exc:
        payload["spotcheck_error"] = f"{type(exc).__name__}: {exc}"
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "out": str(OUT),
        "sha_ok": payload["sha256"]["before_match"] and payload["sha256"]["after_match"],
        "append_ok": payload["append_only"]["pass"],
        "new_rows": payload["append_only"]["new_rows"],
        "dashboard": payload["dashboard"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())