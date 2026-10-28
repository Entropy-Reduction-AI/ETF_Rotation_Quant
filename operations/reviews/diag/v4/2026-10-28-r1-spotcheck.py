#!/usr/bin/env python3
"""Independent v4-R1 data spot-check (Reviewer). No backtests or portfolio PnL."""
from __future__ import annotations

import csv
import hashlib
import json
import random
import sqlite3
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from src.data import sources as S  # noqa: E402
from src.v4.data import catalog as C  # noqa: E402
from src.v4.data.ingest import _read_bars, _read_events, build_coverage  # noqa: E402
from src.v4.data.parse import bar_sha256, series_sha256  # noqa: E402

DB = ROOT / "data" / "market.sqlite"
MAIN_DB = Path("/tmp/etf-main-wt/data/market.sqlite")
COVERAGE = ROOT / "results" / "v4" / "inventory" / "coverage.csv"
UNIVERSE = ROOT / "config" / "v4" / "universe.toml"
SPOT_DEV = ROOT / "results" / "v4" / "inventory" / "spotcheck.csv"
SEED = 20261028
ARTIFACT = Path("/opt/cursor/artifacts/v4-r1-reviewer-spotcheck.json")


def connect(path: Path, *, ro: bool = True) -> sqlite3.Connection:
    uri = f"file:{path}?mode={'ro' if ro else 'rw'}"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    return con


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_coverage_rows() -> list[dict]:
    with COVERAGE.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_universe_bars() -> list[dict]:
    import tomllib

    data = tomllib.loads(UNIVERSE.read_text(encoding="utf-8"))
    out = []
    for item in data.get("container", []):
        if item.get("status") != "in_db" or item.get("return_basis") in {"cash_dividend", "split"}:
            continue
        if not item.get("code"):
            continue
        out.append(item)
    return out


def pick_dates(con: sqlite3.Connection, code: str, n: int, rng: random.Random) -> list[str]:
    rows = [r[0] for r in con.execute(
        "SELECT date FROM bars WHERE code=? AND adj='raw' ORDER BY date", (code,))]
    if len(rows) <= n:
        return rows
    return sorted(rng.sample(rows, n))


def yahoo_close(code: str, day: str) -> float | None:
    from src.data import http
    from src.v4.data.parse import parse_yahoo_chart

    if code == "SP500-60":
        symbol = "^SP500-60"
    else:
        symbol = code
    url = C.YAHOO.format(symbol=symbol)
    d = date.fromisoformat(day)
    params = {
        "period1": str(int(datetime(d.year, d.month, d.day).timestamp()) - 86400),
        "period2": str(int(datetime(d.year, d.month, d.day).timestamp()) + 86400 * 2),
        "interval": "1d",
        "events": "div,split",
    }
    try:
        raw = http.get(url, params, timeout=25)
        payload = json.loads(raw)
        parsed = parse_yahoo_chart(payload, d, d)
    except Exception:
        return None
    for row in parsed.get("bars") or []:
        if row["date"] == day:
            return float(row["close"])
    return None


def cnbc_close(code: str, day: str) -> float | None:
    from src.v4.data.ingest import _cnbc

    if code == "SP500-60":
        return None
    try:
        table = _cnbc(code)
    except Exception:
        return None
    return table.get(day)


def us_external_close(code: str, day: str) -> tuple[float | None, str]:
    """Second source: CNBC when in 1Y window; else live Yahoo re-fetch vs DB (Yahoo ingest)."""
    c = cnbc_close(code, day)
    if c is not None:
        return c, "cnbc"
    y = yahoo_close(code, day)
    if y is not None:
        return y, "yahoo_refetch"
    s = stooq_close(code, day)
    if s is not None:
        return s, "stooq"
    return None, "none"


def stooq_close(code: str, day: str) -> float | None:
    sym = f"{code.lower()}.us" if code.isalpha() and len(code) <= 5 else code
    if code == "SP500-60":
        sym = "^sp500-60"
    start = date.fromisoformat(day)
    try:
        got = S.fetch_stooq(sym, start, start)
    except Exception:
        return None
    for row in got.rows:
        if row["date"] == day:
            return float(row["close"])
    return None


def tencent_close(code: str, day: str) -> float | None:
    item = next((x for x in C.HSI_SUB if x["code"] == code or x["tr_code"] == code), None)
    if not item:
        return None
    sym = item["tr_tencent"] if code.endswith("GTR") or code in {
        "HSFGTR", "HSUGTR", "HSPGTR", "HSCGTR"} else item["tencent"]
    start = date.fromisoformat(day)
    try:
        got = S.fetch_tencent(sym, start, start)
    except Exception:
        return None
    for row in got.rows:
        if row["date"] == day:
            return float(row["close"])
    return None


def chinamoney_hkdcny(day: str) -> float | None:
    from src.v4.data.ingest import _fx_year

    y = date.fromisoformat(day).year
    try:
        rows = _fx_year("HKD/CNY", y, date.fromisoformat(day))
    except Exception:
        return None
    for row in rows:
        if row["date"] == day:
            return float(row["close"])
    return None


def yahoo_dividend(code: str, day: str) -> float | None:
    from src.data import http
    from src.v4.data.parse import parse_yahoo_chart

    url = C.YAHOO.format(symbol=code)
    params = {"period1": "0", "period2": str(int(datetime.now().timestamp())), "interval": "1d", "events": "div"}
    try:
        raw = http.get(url, params, timeout=25)
        payload = json.loads(raw)
        parsed = parse_yahoo_chart(payload, date(1990, 1, 1), date(2030, 1, 1))
    except Exception:
        return None
    for row in parsed.get("dividends") or []:
        if row["date"] == day:
            return float(row["amount"])
    return None


def registry_check(con: sqlite3.Connection) -> dict:
    built = build_coverage(con)
    file_rows = load_coverage_rows()
    mismatches = []
    if len(built) != len(file_rows):
        mismatches.append(f"row_count built={len(built)} file={len(file_rows)}")
    for i, (a, b) in enumerate(zip(built, file_rows)):
        for key in ("code", "series_kind", "first_date", "last_date", "rows", "sha256", "status"):
            if a.get(key) != b.get(key):
                mismatches.append(f"line {i+2} {key} built={a.get(key)!r} file={b.get(key)!r}")
    uni = load_universe_bars()
    cov_bars = [r for r in file_rows if r["series_kind"] == "bar" and r["status"] == "in_db"]
    uni_keys = {(u["code"], u.get("return_basis", "")) for u in uni}
    cov_keys = {(r["code"], r["return_basis"]) for r in cov_bars}
    if uni_keys != cov_keys:
        mismatches.append(f"universe vs coverage bar keys uni-only={uni_keys-cov_keys} cov-only={cov_keys-uni_keys}")
    hash_cli = {}
    for code in sorted({r["code"] for r in cov_bars if r["rows"] not in {"", "0"}}):
        proc = subprocess.run(
            [str(ROOT / ".venv/bin/python"), "-m", "src.v4.data", "hash", code],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        hash_cli[code] = proc.stdout.strip()
        row = next(r for r in cov_bars if r["code"] == code and r["series_kind"] == "bar")
        expected = f"bars {row['rows']} {row['sha256']}"
        if expected not in proc.stdout:
            mismatches.append(f"hash CLI {code}: expected {expected!r} got {proc.stdout!r}")
    return {"ok": not mismatches, "mismatches": mismatches, "hash_cli_sample": hash_cli}


def sentinel_check(con: sqlite3.Connection, main: sqlite3.Connection) -> dict:
    out = {"integrity": con.execute("PRAGMA integrity_check").fetchone()[0], "sentinels": {}, "ok": True}
    for code in C.SENTINELS:
        cur = _read_bars(con, code)
        old = _read_bars(main, code)
        match = bar_sha256(cur) == bar_sha256(old) and len(cur) == len(old)
        out["sentinels"][code] = {
            "rows": len(cur),
            "sha256": bar_sha256(cur),
            "matches_main": match,
        }
        if not match:
            out["ok"] = False
    old_count = main.execute("SELECT COUNT(*) FROM bars WHERE adj='raw'").fetchone()[0]
    new_codes = {x["code"] for x in C.ETFS} | {x["code"] for x in C.HSI_SUB} | {
        x["tr_code"] for x in C.HSI_SUB} | {"HKDCNY", C.SP_PRICE_AVAILABLE["code"]}
    preserved = con.execute(
        "SELECT COUNT(*) FROM bars WHERE adj='raw' AND code NOT IN ({})".format(
            ",".join("?" * len(new_codes))), tuple(new_codes)).fetchone()[0]
    out["bars_main"] = old_count
    out["bars_preserved_non_v4"] = preserved
    out["bars_preserved_matches_main"] = preserved == old_count
    if preserved != old_count:
        out["ok"] = False
    out["universe_rows"] = con.execute("SELECT COUNT(*) FROM universe").fetchone()[0]
    out["cash_dividends"] = con.execute("SELECT COUNT(*) FROM cash_dividends").fetchone()[0]
    return out


def spot_market(con: sqlite3.Connection, market: str, codes: list[str], rng: random.Random,
                *, fetch_fn, tol: float) -> list[dict]:
    rows = []
    for code in codes:
        dates = pick_dates(con, code, 5, rng)
        for day in dates:
            db_close = con.execute(
                "SELECT close FROM bars WHERE code=? AND adj='raw' AND date=?", (code, day)).fetchone()
            db_val = None if not db_close else float(db_close[0])
            if market == "US":
                ext, src = fetch_fn(code, day)
            else:
                ext = fetch_fn(code, day)
                src = "tencent_refetch" if market == "HK" else "chinamoney_refetch"
            diff = None if db_val is None or ext is None else abs(db_val - ext)
            ok = diff is not None and diff <= tol
            rows.append({
                "market": market, "code": code, "date": day, "db_close": db_val,
                "external_close": ext, "external_source": src, "abs_diff": diff, "ok": ok,
            })
    return rows


def dev_spotcheck(con: sqlite3.Connection) -> list[dict]:
    out = []
    with SPOT_DEV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code, day = row["code"], row["date"]
            db = con.execute(
                "SELECT close FROM bars WHERE code=? AND adj='raw' AND date=?", (code, day)).fetchone()
            out.append({
                "code": code, "date": day, "dev_spot": float(row["close"]),
                "db_close": None if not db else float(db[0]),
                "match": db and abs(float(db[0]) - float(row["close"])) < 1e-4,
            })
    return out


def dividend_spot(con: sqlite3.Connection, rng: random.Random) -> list[dict]:
    codes = [x["code"] for x in C.ETFS]
    picks = rng.sample(codes, 3)
    rows = []
    for code in picks:
        ev = _read_events(con, code, "dividend")
        if not ev:
            continue
        sample = rng.choice(ev)
        day = sample["date"]
        db_amt = float(sample["amount"])
        yahoo = yahoo_dividend(code, day)
        rows.append({
            "code": code, "ex_date": day, "db_amount": db_amt, "yahoo_amount": yahoo,
            "abs_diff": None if yahoo is None else abs(db_amt - yahoo),
            "ok": yahoo is not None and abs(db_amt - yahoo) < 1e-6,
        })
    return rows


def main() -> int:
    rng = random.Random(SEED)
    us_pool = [x["code"] for x in C.ETFS] + [C.SP_PRICE_AVAILABLE["code"]]
    hk_pool = [x["code"] for x in C.HSI_SUB] + [x["tr_code"] for x in C.HSI_SUB]
    us_codes = rng.sample(us_pool, 3)
    hk_codes = rng.sample(hk_pool, 3)

    con = connect(DB)
    main_con = connect(MAIN_DB)
    report = {
        "seed": SEED,
        "db_sha256": sha256_file(DB),
        "main_db_sha256": sha256_file(MAIN_DB),
        "expected_db_sha256": "a130af9eab11368d71488ee48f83bb71952d17eb5abd1d5bcc00d1cd6993f1e6",
        "expected_main_sha256": "3e3e6f1d594586da2abf28db5fa88b05c1cc91fa29adf061fc699e1b8d4bc1d6",
        "us_random_codes": us_codes,
        "hk_random_codes": hk_codes,
        "registry": registry_check(con),
        "sentinels": sentinel_check(con, main_con),
        "dev_spotcheck": dev_spotcheck(con),
        "us_spot_second_source": spot_market(
            con, "US", us_codes, rng, fetch_fn=us_external_close, tol=1e-4),
        "hk_spot_tencent_refetch": spot_market(
            con, "HK", hk_codes, rng, fetch_fn=tencent_close, tol=0.01),
        "fx_spot_chinamoney": spot_market(
            con, "FX", ["HKDCNY"], rng, fetch_fn=lambda _c, d: chinamoney_hkdcny(d), tol=1e-4),
        "dividend_spot_yahoo": dividend_spot(con, rng),
    }
    con.close()
    main_con.close()

    fails = []
    if report["db_sha256"] != report["expected_db_sha256"]:
        fails.append("db_sha256")
    if not report["registry"]["ok"]:
        fails.append("registry")
    if not report["sentinels"]["ok"]:
        fails.append("sentinels")
    if report["sentinels"]["integrity"] != "ok":
        fails.append("integrity")
    for block in ("dev_spotcheck", "us_spot_second_source", "hk_spot_tencent_refetch", "fx_spot_chinamoney"):
        for row in report[block]:
            if row.get("ok") is False or row.get("match") is False:
                fails.append(f"{block}:{row.get('code')}/{row.get('date')}")
    for row in report["dividend_spot_yahoo"]:
        if not row.get("ok"):
            fails.append(f"dividend:{row.get('code')}")

    report["failures"] = fails
    report["decision_hint"] = "approve" if not fails else "return"
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"artifact": str(ARTIFACT), "failures": fails, "decision_hint": report["decision_hint"]}))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
