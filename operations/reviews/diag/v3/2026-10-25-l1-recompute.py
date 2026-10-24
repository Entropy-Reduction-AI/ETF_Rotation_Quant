#!/usr/bin/env python3
"""Independent L1 spot-check helpers (Reviewer). No backtests."""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
UNIVERSE = ROOT / "config/v3/universe.toml"
COVERAGE = ROOT / "results/v3/inventory/coverage.csv"
SQLITE = ROOT / "data/market.sqlite"
INCOMING = ROOT / "incoming/2026-10-24-v3-l1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def spotcheck_sqlite(sample_stride_research: int = 10, sample_stride_execution: int = 10) -> dict:
    cov = list(csv.DictReader(COVERAGE.open()))
    research = sorted([r for r in cov if r["role"] == "research"], key=lambda r: r["code"])
    execution = sorted([r for r in cov if r["role"] == "execution"], key=lambda r: r["code"])
    pick_r = research[:: max(1, len(research) // sample_stride_research)]
    pick_e = execution[:: max(1, len(execution) // sample_stride_execution)]
    conn = sqlite3.connect(SQLITE)
    cur = conn.cursor()
    out = []
    for r in pick_r + pick_e:
        code, adj, src = r["db_code"] or r["code"], r["db_adj"] or "raw", r["db_source"]
        cur.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM bars WHERE code=? AND adj=? AND source=?",
            (code, adj, src),
        )
        cnt, fd, ld = cur.fetchone()
        out.append(
            {
                "code": r["code"],
                "role": r["role"],
                "ok": cnt == int(r["rows"] or 0) and fd == r["first_date"] and ld == r["last_date"],
            }
        )
    conn.close()
    return {"n": len(out), "all_pass": all(x["ok"] for x in out), "rows": out}


def main() -> None:
    print("universe.toml", sha256_file(UNIVERSE))
    print("coverage.csv", sha256_file(COVERAGE))
    if SQLITE.stat().st_size > 1_000_000:
        print("market.sqlite", sha256_file(SQLITE))
    sc = spotcheck_sqlite()
    print(json.dumps(sc, indent=2))


if __name__ == "__main__":
    main()
