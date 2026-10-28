#!/usr/bin/env python3
"""Reviewer 独立复核：PR #29 防御资产 + 海外假日零收盘。只读 SQLite / emit 产物。"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from src.report.fx import cny_from_usd
from src.v3.data.defensive import OVERSEAS, audit_overseas

CLAIMED = {
    "universe.toml": "04ff3572ebd82a5159eaccced0bed5bc3531b732a1b11025f86021ebd0454be0",
    "market.sqlite": "3e3e6f1d594586da2abf28db5fa88b05c1cc91fa29adf061fc699e1b8d4bc1d6",
    "coverage.csv": "577125a16c28830f38bb5bbd89ba72179efb848cbe8a725945762db9f4a039b2",
}
PARENT_SHA = "c80aa56804c8927b762ada71b232c08a24b42fc5"
BASELINE_MAIN = "4c6d4b086d28bc58e1ec107210ce1b8125cea4c5"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def bar_span(con: sqlite3.Connection, code: str) -> dict:
    row = con.execute(
        "SELECT COUNT(*), MIN(date), MAX(date) FROM bars WHERE code=? AND adj='raw' AND close>0",
        (code,),
    ).fetchone()
    return {"rows": row[0], "start": row[1], "end": row[2]}


def sandy_window(con: sqlite3.Connection) -> dict:
    usd = pd.read_sql_query(
        "SELECT date, open, high, low, close, volume FROM bars WHERE code='XNDX' AND adj='raw' ORDER BY date",
        con,
    )
    usd["date"] = pd.to_datetime(usd["date"])
    fx_rows = con.execute("SELECT date, close FROM bars WHERE code='USDCNY' AND adj='raw'").fetchall()
    fx = pd.Series({pd.Timestamp(d): c for d, c in fx_rows})
    cal = pd.to_datetime(["2012-10-26", "2012-10-29", "2012-10-30", "2012-10-31", "2012-11-01"])
    priced = cny_from_usd(usd, fx, pd.DatetimeIndex(cal))
    level = pd.Series(priced["close_cny"].values, index=pd.to_datetime(priced["date"]))
    rets = level.pct_change().dropna()
    return {
        "xndx_bar_dates": {
            d: con.execute("SELECT close FROM bars WHERE code='XNDX' AND date=?", (d,)).fetchone()
            for d in ["2012-10-26", "2012-10-29", "2012-10-30", "2012-10-31", "2012-11-01"]
        },
        "cny_levels": {str(k.date()): float(v) for k, v in level.items()},
        "cny_returns": {str(k.date()): float(v) for k, v in rets.items()},
        "returns_all_finite": bool(np.isfinite(rets.to_numpy()).all()),
        "2012_10_30_return": float(rets.loc[pd.Timestamp("2012-10-30")]),
        "2012_11_01_return": float(rets.loc[pd.Timestamp("2012-11-01")]),
    }


def main() -> int:
    out_path = Path(__file__).with_suffix(".json")
    lock = ROOT / "results" / "v3" / "LOCK"
    hashes = {
        name: sha256(ROOT / "config/v3/universe.toml" if name == "universe.toml" else ROOT / f"data/{name}" if name == "market.sqlite" else ROOT / f"results/v3/inventory/{name}")
        for name in CLAIMED
    }
    match = {k: hashes[k] == CLAIMED[k] for k in CLAIMED}

    con = sqlite3.connect(ROOT / "data/market.sqlite")
    spans = {code: bar_span(con, code) for code in ["Au99.99", "CBA04501", "CBA03101", "CBA00601", "XNDX"]}
    marks = ",".join("?" * len(OVERSEAS))
    nonpos = con.execute(
        f"SELECT code, date, close, source FROM bars WHERE adj='raw' AND close<=0 AND source IN ({marks})",
        OVERSEAS,
    ).fetchall()
    audit_hits = audit_overseas(con)
    sandy = sandy_window(con)
    con.close()

    emit_before = hashes["universe.toml"]
    subprocess.run([str(ROOT / ".venv/bin/python"), "-m", "src.v3.data", "emit"], cwd=ROOT, check=True)
    emit_after = sha256(ROOT / "config/v3/universe.toml")
    emit_stable = emit_before == emit_after

    payload = {
        "parent_delivery_sha": PARENT_SHA,
        "baseline_main_sha": BASELINE_MAIN,
        "sha256": {**hashes, "matches_dev_claim": match},
        "lock_exists": lock.exists(),
        "series_spans_close_gt_0": spans,
        "overseas_nonpositive_close_rows": [
            {"code": c, "date": d, "close": cl, "source": s} for c, d, cl, s in nonpos
        ],
        "overseas_holiday_audit_hits": len(audit_hits),
        "sandy_hurricane_window": sandy,
        "emit_idempotent": emit_stable,
        "unittest": subprocess.run(
            [str(ROOT / ".venv/bin/python"), "-m", "unittest", "discover", "-s", "tests", "-t", "."],
            cwd=ROOT,
            capture_output=True,
            text=True,
        ).stdout.splitlines()[-2:],
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"written": str(out_path), "sha_match": match, "emit_stable": emit_stable}, indent=2))
    return 0 if all(match.values()) and emit_stable and not lock.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
