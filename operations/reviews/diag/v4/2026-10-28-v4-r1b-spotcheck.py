#!/usr/bin/env python3
"""Independent v4-R1b ingest spot-check (Reviewer). No portfolio PnL or backtests."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import re
import sqlite3
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from src.data import http  # noqa: E402
from src.v4.data import catalog as C  # noqa: E402
from src.v4.data.ingest import _read_bars, _read_events, build_coverage  # noqa: E402
from src.v4.data.parse import bar_sha256, series_sha256  # noqa: E402

DB = ROOT / "data" / "market.sqlite"
MAIN_DB = Path("/tmp/etf-main-wt/data/market.sqlite")
COVERAGE = ROOT / "results/v4/inventory/coverage.csv"
UNIVERSE = ROOT / "config/v4/universe.toml"
FX_FILL = ROOT / "results/v4/inventory/fx-fill.csv"
SAFE_FILE = "https://www.safe.gov.cn/safe/file/file/20260106/0f147e5357eb4c12a6406fc575cc21e8.xlsx"
SAFE_REF = "https://www.safe.gov.cn/safe/2020/1218/17833.html"
PING = "https://fund.eastmoney.com/pingzhongdata/{code}.js"
TENCENT = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
ZERO_DAY = "2013-06-28"
ZERO_CODES = ("H20184", "H20187", "H20202", "H30184", "H30187", "H30202")
LEDGER_END = date(2026, 9, 30)
SEED = 2026102873
ARTIFACT = Path("/opt/cursor/artifacts/v4-r1b-reviewer-spotcheck.json")
ARTIFACT_FALLBACK = ROOT / "outputs" / "v4-r1b-reviewer-spotcheck.json"


def _json_safe(obj):
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    raise TypeError(type(obj))
EXPECTED_DB_SHA = "af4c5a376d084cd6254187c1107c6179d0cfd9647c008bff84b4c26f52045b78"
EXPECTED_PRE_SHA = "a130af9eab11368d71488ee48f83bb71952d17eb5abd1d5bcc00d1cd6993f1e6"

try:
    from src.v4.data.adjust import backward_total_return, compound_adjusted_nav  # noqa: E402
    from src.v4.data.r1b_parse import parse_pingzhongdata, parse_safe_mid, parse_tencent_kline_rows  # noqa: E402
except ImportError as exc:
    raise SystemExit(
        "Run this script at Dev PR #73 tip (needs src/v4/data/r1b*.py). "
        f"Import error: {exc}"
    ) from exc


def connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_v4_bars(con: sqlite3.Connection, code: str, kind: str) -> list[dict]:
    return [
        dict(r)
        for r in con.execute(
            """SELECT date, open, high, low, close, volume FROM v4_series
               WHERE code=? AND kind=? ORDER BY date""",
            (code, kind),
        )
    ]


def bars_vs_main(con: sqlite3.Connection, main: sqlite3.Connection) -> dict:
    same = 0
    expected_null = 0
    bad = []
    for row in con.execute(
        "SELECT code, date, adj, close, open, high, low, volume, source FROM bars ORDER BY code, date, adj"
    ):
        code, day, adj = row["code"], row["date"], row["adj"]
        old = main.execute(
            "SELECT close, open, high, low, volume, source FROM bars WHERE code=? AND date=? AND adj=?",
            (code, day, adj),
        ).fetchone()
        if old is None:
            bad.append(f"missing_on_main {code} {day} {adj}")
            continue
        new_t = (row["close"], row["open"], row["high"], row["low"], row["volume"], row["source"])
        old_t = tuple(old)
        if new_t == old_t:
            same += 1
            continue
        if code in ZERO_CODES and day == ZERO_DAY and old_t[0] == 0 and row["close"] is None:
            expected_null += 1
            continue
        bad.append(f"unexpected {code} {day}")
    fx_ok = {}
    for code in ("USDCNY", "HKDCNY"):
        fx_ok[code] = bar_sha256(_read_bars(con, code)) == bar_sha256(_read_bars(main, code))
    return {
        "bar_rows_pr": con.execute("SELECT COUNT(*) FROM bars").fetchone()[0],
        "bar_rows_main": main.execute("SELECT COUNT(*) FROM bars").fetchone()[0],
        "identical_rows": same,
        "zero_to_null": expected_null,
        "unexpected_count": len(bad),
        "unexpected_sample": bad[:20],
        "fx_bars_unchanged": fx_ok,
        "ok": not bad and expected_null == len(ZERO_CODES) and all(fx_ok.values()),
    }


def split_basis_checks(con: sqlite3.Connection) -> list[dict]:
    checks = [
        ("XLF", "2016-09-19", "2016-09-16", 1231, 1000),
        ("XLB", "2025-12-05", "2025-12-04", 2, 1),
        ("XLE", "2025-12-05", "2025-12-04", 2, 1),
        ("XLK", "2025-12-05", "2025-12-04", 2, 1),
        ("XLU", "2025-12-05", "2025-12-04", 2, 1),
        ("XLY", "2025-12-05", "2025-12-04", 2, 1),
    ]
    out = []
    for code, split_day, prev_day, num, den in checks:
        raw = _read_bars(con, code)
        adj = read_v4_bars(con, code, "backward")
        prev_r = next(r for r in raw if r["date"] == prev_day)
        day_r = next(r for r in raw if r["date"] == split_day)
        prev_a = next(r for r in adj if r["date"] == prev_day)
        day_a = next(r for r in adj if r["date"] == split_day)
        raw_ratio = float(day_r["close"]) / float(prev_r["close"])
        adj_ratio = float(day_a["close"]) / float(prev_a["close"])
        from src.v4.data.adjust import split_already_in_close

        in_price = split_already_in_close(
            float(prev_r["close"]), float(day_r["close"]), num, den
        )
        out.append(
            {
                "code": code,
                "split_date": split_day,
                "raw_close_ratio": raw_ratio,
                "adj_close_ratio": adj_ratio,
                "split_already_in_price": in_price,
                "ok": in_price and abs(raw_ratio - adj_ratio) < 0.02,
            }
        )
    return out


def unavailable_not_backfilled(con: sqlite3.Connection) -> dict:
    with COVERAGE.open(encoding="utf-8", newline="") as f:
        rows = [
            r
            for r in csv.DictReader(f)
            if r.get("status") == "unavailable"
            and str(r.get("note", "")).startswith("v4-R1b")
            and r.get("return_basis") == "total_return"
            and r.get("series_kind") == "bar"
        ]
    leaks = []
    for row in rows:
        code = row["code"]
        n = con.execute(
            "SELECT COUNT(*) FROM v4_series WHERE code=? AND kind='backward'", (code,)
        ).fetchone()[0]
        if n:
            leaks.append(code)
    return {"unavailable_adj_rows": len(rows), "backward_leaks": leaks, "ok": not leaks}


def registry_r1b(con: sqlite3.Connection) -> dict:
    with COVERAGE.open(encoding="utf-8", newline="") as f:
        file_rows = list(csv.DictReader(f))
    r1b = [r for r in file_rows if str(r.get("note", "")).startswith("v4-R1b")]
    mism = []
    for row in r1b:
        if row["status"] != "in_db":
            continue
        code = row["code"]
        sk = row["series_kind"]
        if sk == "fx":
            fx_rows = [
                dict(r)
                for r in con.execute(
                    """SELECT date, close, filled FROM v4_series
                       WHERE code=? AND kind='fx' ORDER BY date""",
                    (code,),
                )
            ]
            digest = series_sha256(fx_rows, ("date", "close", "filled"))
            if str(row["rows"]) != str(len(fx_rows)):
                mism.append(f"{code} rows file={row['rows']} db={len(fx_rows)}")
            elif row.get("sha256") and digest != row["sha256"]:
                mism.append(f"{code} fx sha256 mismatch")
            continue
        if sk == "nav":
            nav_rows = [
                dict(r)
                for r in con.execute(
                    """SELECT date, unit_nav, accum_nav, close FROM v4_series
                       WHERE code=? AND kind='otc_nav' ORDER BY date""",
                    (code,),
                )
            ]
            digest = series_sha256(nav_rows, ("date", "unit_nav", "accum_nav", "close"))
            if str(row["rows"]) != str(len(nav_rows)):
                mism.append(f"{code} rows file={row['rows']} db={len(nav_rows)}")
            elif row.get("sha256") and digest != row["sha256"]:
                mism.append(f"{code} nav sha256 mismatch")
            continue
        if sk == "bar" and row.get("return_basis") == "total_return" and "后复权" in row.get("name", ""):
            bars = read_v4_bars(con, code, "backward")
            if str(row["rows"]) != str(len(bars)):
                mism.append(f"{code} rows file={row['rows']} db={len(bars)}")
            elif row.get("sha256") and bar_sha256(bars) != row["sha256"]:
                mism.append(f"{code} backward sha256 mismatch")
    import tomllib

    uni = tomllib.loads(UNIVERSE.read_text(encoding="utf-8"))
    otc_uni = [c for c in uni.get("container", []) if c.get("instrument_type") == "otc_fund"]
    otc_cov = [r for r in r1b if r["series_kind"] == "nav" and r["status"] == "in_db"]
    uni_codes = {c["code"] for c in otc_uni}
    cov_codes = {r["code"] for r in otc_cov}
    if uni_codes != cov_codes:
        mism.append(f"otc universe vs coverage uni-only={uni_codes-cov_codes} cov-only={cov_codes-uni_codes}")
    built = build_coverage(con)
    base_len = len([r for r in file_rows if not str(r.get("note", "")).startswith("v4-R1b")])
    if len(built) != base_len:
        mism.append(f"build_coverage base {len(built)} vs file base {base_len}")
    return {"r1b_coverage_rows": len(r1b), "mismatches": mism, "ok": not mism}


def pick_adj_pool(con: sqlite3.Connection) -> list[str]:
    with COVERAGE.open(encoding="utf-8", newline="") as f:
        rows = [
            r["code"]
            for r in csv.DictReader(f)
            if r.get("status") == "in_db" and "后复权" in r.get("name", "")
        ]
    have = {
        r[0]
        for r in con.execute(
            "SELECT DISTINCT code FROM v4_series WHERE kind='backward'"
        )
    }
    return sorted(set(rows) & have)


def pick_otc_pool(con: sqlite3.Connection) -> list[str]:
    return sorted(
        r[0]
        for r in con.execute(
            "SELECT DISTINCT code FROM v4_series WHERE kind='otc_nav' ORDER BY code"
        )
    )


def pick_dates(bars: list[dict], n: int, rng: random.Random, prefer: list[str]) -> list[str]:
    days = [b["date"] for b in bars if b.get("close") is not None]
    chosen = [d for d in prefer if d in days][:n]
    rest = [d for d in days if d not in chosen]
    while len(chosen) < n and rest:
        chosen.append(rng.choice(rest))
        rest = [d for d in rest if d not in chosen]
    return chosen[:n]


def tencent_hfq_close(code: str, day: str) -> float | None:
    sym = f"sh{code}" if code.startswith(("5", "6")) else f"sz{code}"
    params = {"param": f"{sym},day,{day},{day},400,hfq"}
    try:
        raw = http.get(TENCENT, params, timeout=25)
        payload = json.loads(raw)
        node = payload["data"][sym]["hfqday"]
        rows = parse_tencent_kline_rows(node)
    except Exception:
        return None
    for row in rows:
        if row["date"] == day:
            return float(row["close"])
    return None


def us_recomputed_close(con: sqlite3.Connection, code: str, day: str) -> float | None:
    raw = _read_bars(con, code)
    divs = _read_events(con, code, "dividend")
    splits = _read_events(con, code, "split")
    out = backward_total_return(raw, divs, splits, splits_in_price=True)
    for row in out:
        if row["date"] == day:
            return None if row["close"] is None else float(row["close"])
    return None


def otc_refetch_close(code: str, day: str) -> float | None:
    try:
        body = http.get(
            PING.format(code=code),
            headers={"Referer": f"https://fund.eastmoney.com/{code}.html"},
            timeout=40,
        )
        text = body.decode("utf-8", "replace") if isinstance(body, bytes) else body
        points = parse_pingzhongdata(text, LEDGER_END)
        adj = compound_adjusted_nav(points)
    except Exception:
        return None
    for row in adj:
        if row["date"] == day:
            return float(row["close"])
    return None


def spot_adj(con: sqlite3.Connection, codes: list[str], rng: random.Random) -> list[dict]:
    rows = []
    us_set = {x["code"] for x in C.ETFS}
    for code in codes:
        bars = read_v4_bars(con, code, "backward")
        prefer = []
        with (ROOT / "results/v4/inventory/adjust-spotcheck.csv").open(encoding="utf-8") as f:
            for line in csv.DictReader(f):
                if line["code"] == code and line.get("date"):
                    prefer.append(line["date"])
        dates = pick_dates(bars, 5, rng, prefer)
        for day in dates:
            db = con.execute(
                "SELECT close FROM v4_series WHERE code=? AND kind='backward' AND date=?",
                (code, day),
            ).fetchone()
            db_close = None if not db or db[0] is None else float(db[0])
            if code in us_set:
                ext = us_recomputed_close(con, code, day)
                src = "recompute_yahoo_raw_div"
            else:
                ext = tencent_hfq_close(code, day)
                src = "tencent_hfqday_refetch"
            diff = None if db_close is None or ext is None else abs(db_close - ext)
            tol = 1e-4 if code in us_set else 0.02
            rows.append(
                {
                    "code": code,
                    "date": day,
                    "db_close": db_close,
                    "external_close": ext,
                    "source": src,
                    "abs_diff": diff,
                    "ok": diff is not None and diff <= tol,
                }
            )
    return rows


def spot_otc(con: sqlite3.Connection, codes: list[str], rng: random.Random) -> list[dict]:
    rows = []
    for code in codes:
        bars = read_v4_bars(con, code, "otc_nav")
        dates = pick_dates(bars, 5, rng, [])
        for day in dates:
            db = con.execute(
                "SELECT close FROM v4_series WHERE code=? AND kind='otc_nav' AND date=?",
                (code, day),
            ).fetchone()
            db_close = float(db[0]) if db else None
            ext = otc_refetch_close(code, day)
            diff = None if db_close is None or ext is None else abs(db_close - ext)
            rows.append(
                {
                    "code": code,
                    "date": day,
                    "db_close": db_close,
                    "external_close": ext,
                    "source": PING.format(code=code),
                    "abs_diff": diff,
                    "ok": diff is not None and diff <= 1e-4,
                }
            )
    return rows


def load_safe_table() -> list[dict]:
    raw = http.get(SAFE_FILE, headers={"Referer": SAFE_REF}, timeout=60)
    folder = ROOT / "outputs" / "data" / "v4-r1b-review"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "safe-rmb-mid.xlsx"
    path.write_bytes(raw)
    return parse_safe_mid(path)


def spot_fx(con: sqlite3.Connection, rng: random.Random) -> list[dict]:
    with FX_FILL.open(encoding="utf-8", newline="") as f:
        fill_rows = list(csv.DictReader(f))
    days = sorted({r["date"] for r in fill_rows})
    pick = rng.sample(days, 3)
    safe = {r["date"]: r for r in load_safe_table()}
    rows = []
    for day in pick:
        for code in ("USDCNY", "HKDCNY"):
            db = con.execute(
                "SELECT close, filled, method FROM v4_series WHERE code=? AND kind='fx' AND date=?",
                (code, day),
            ).fetchone()
            if not db:
                rows.append({"code": code, "date": day, "ok": False, "note": "missing"})
                continue
            db_close = float(db[0])
            file_row = next(r for r in fill_rows if r["code"] == code and r["date"] == day)
            file_close = float(file_row["close"])
            safe_row = safe.get(day)
            official = None
            if safe_row:
                if code == "USDCNY" and safe_row.get("usd_per_hundred") is not None:
                    official = float(safe_row["usd_per_hundred"]) / 100.0
                if code == "HKDCNY" and safe_row.get("hkd_per_hundred") is not None:
                    official = float(safe_row["hkd_per_hundred"]) / 100.0
            rows.append(
                {
                    "code": code,
                    "date": day,
                    "db_close": db_close,
                    "fx_fill_csv": file_close,
                    "safe_official": official,
                    "filled": int(db[1]),
                    "method": db[2],
                    "matches_fill_csv": abs(db_close - file_close) < 1e-6,
                    "ok": abs(db_close - file_close) < 1e-6 and int(db[1]) == 1,
                    "safe_url": SAFE_REF,
                    "workbook_url": SAFE_FILE,
                }
            )
    return rows


def h_null_check(con: sqlite3.Connection) -> dict:
    out = {}
    for code in ZERO_CODES:
        row = con.execute(
            "SELECT close FROM bars WHERE code=? AND adj='raw' AND date=?",
            (code, ZERO_DAY),
        ).fetchone()
        out[code] = None if not row else row[0]
    return {"values": out, "ok": all(v is None for v in out.values())}


def main() -> int:
    rng = random.Random(SEED)
    con = connect(DB)
    main_con = connect(MAIN_DB)
    adj_pool = pick_adj_pool(con)
    otc_pool = pick_otc_pool(con)
    adj_codes = rng.sample(adj_pool, 3)
    otc_codes = rng.sample(otc_pool, 3)
    bars_check = bars_vs_main(con, main_con)
    report = {
        "seed": SEED,
        "dev_pr_tip": "01dd5449b50db293ff51656590a46899e35492be",
        "db_sha256": sha256_file(DB),
        "expected_db_sha256": EXPECTED_DB_SHA,
        "pre_write_sha256_claim": EXPECTED_PRE_SHA,
        "integrity": con.execute("PRAGMA integrity_check").fetchone()[0],
        "adj_random_codes": adj_codes,
        "otc_random_codes": otc_codes,
        "h_null": h_null_check(con),
        "bars_vs_main": bars_check,
        "split_basis": split_basis_checks(con),
        "unavailable_adj": unavailable_not_backfilled(con),
        "registry_r1b": registry_r1b(con),
        "adj_spot": spot_adj(con, adj_codes, rng),
        "otc_spot": spot_otc(con, otc_codes, rng),
        "fx_fill_spot": spot_fx(con, rng),
    }
    con.close()
    main_con.close()

    fails = []
    if report["db_sha256"] != EXPECTED_DB_SHA:
        fails.append("db_sha256")
    if report["integrity"] != "ok":
        fails.append("integrity")
    for key in ("h_null", "bars_vs_main", "unavailable_adj", "registry_r1b"):
        if not report[key].get("ok"):
            fails.append(key)
    for row in report["split_basis"]:
        if not row.get("ok"):
            fails.append(f"split:{row['code']}")
    for block in ("adj_spot", "otc_spot", "fx_fill_spot"):
        for row in report[block]:
            if not row.get("ok"):
                fails.append(f"{block}:{row.get('code')}/{row.get('date')}")

    report["failures"] = fails
    report["decision_hint"] = "approve" if not fails else "return"
    if fails:
        report["decision_hint"] = "approve_with_follow_up" if len(fails) <= 2 else "return"

    payload = json.dumps(report, indent=2, ensure_ascii=False, default=_json_safe) + "\n"
    for path in (ARTIFACT, ARTIFACT_FALLBACK):
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(payload, encoding="utf-8")
            written = str(path)
            break
        except OSError:
            written = str(ARTIFACT_FALLBACK)
    else:
        written = str(ARTIFACT_FALLBACK)
    print(json.dumps({"artifact": written, "failures": fails, "decision_hint": report["decision_hint"]}))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
