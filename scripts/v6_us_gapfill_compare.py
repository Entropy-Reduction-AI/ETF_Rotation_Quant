"""Read raw DJIA / DWRTF closes and compare them. No returns, no database writes.

Reproduce from the repository root:

    python3 -I scripts/v6_us_gapfill_compare.py

The command uses only the standard library. It reads data/market.sqlite in
read-only mode and only the raw closes of DJIA and DWRTF inside the overlap
windows named below. It rewrites normalized CSVs and evidence JSON under
incoming/v6-us-gapfill/. It does not download. Download commands are in
incoming/v6-us-gapfill/MANIFEST.md.

Relative difference, right-hand series as the denominator:

    abs(left - right) / abs(right)

A database overlap above 0.1% (0.001) exits 2. Dates are not dropped.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "incoming" / "v6-us-gapfill"
RAW = PKG / "raw"
NORM = PKG / "normalized"
EVIDENCE = PKG / "evidence"
DB = ROOT / "data" / "market.sqlite"
PRIOR_TV = (
    ROOT
    / "incoming/grok-d37-index-20261116/theme-道琼斯美国精选REIT指数-tradingview.csv"
)
PRIOR_OFFICIAL = (
    ROOT
    / "incoming/grok-d37-index-20261116"
    / "theme-道琼斯美国精选REIT指数-official-usd-pr-daily-20251117-20261116.csv"
)
NY = ZoneInfo("America/New_York")
STOP = 0.001  # 0.1%

DJIA_REQUIRED = ("2024-02-01", "2026-09-30")
DJIA_OVERLAP = ("2023-11-01", "2024-02-01")
DWRTF_REQUIRED = ("2017-11-22", "2026-09-30")
DWRTF_OVERLAP = ("2017-08-01", "2017-11-22")


def sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_close_csv(path: Path, rows: dict[str, str], start: str, end: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    chosen = [(day, rows[day]) for day in sorted(rows) if start <= day <= end]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("date", "close"))
        writer.writerows(chosen)
    return len(chosen)


def load_csv_closes(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            day = record["date"]
            close = record["close"].strip()
            if day in rows and rows[day] != close:
                raise SystemExit(f"{path} duplicate {day}: {rows[day]} vs {close}")
            rows[day] = close
    return rows


def load_fred(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "observation_date,DJIA":
        raise SystemExit(f"unexpected FRED header: {lines[:1]}")
    for line in lines[1:]:
        day, close = line.split(",", 1)
        if close in {"", "."}:
            continue
        rows[day] = close
    return rows


def load_yahoo_dji(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    result = payload["chart"]["result"][0]
    meta = result["meta"]
    if meta.get("symbol") != "^DJI" or "Dow Jones Industrial Average" not in str(meta.get("longName")):
        raise SystemExit(f"Yahoo chart is not DJIA price: {meta.get('symbol')} {meta.get('longName')}")
    rows: dict[str, str] = {}
    quotes = result["indicators"]["quote"][0]["close"]
    for stamp, close in zip(result["timestamp"], quotes):
        if close is None:
            continue
        day = datetime.fromtimestamp(stamp, NY).date().isoformat()
        text = format(float(close), ".12g")
        if day in rows and rows[day] != text:
            raise SystemExit(f"Yahoo duplicate {day}: {rows[day]} vs {text}")
        rows[day] = text
    return rows


def load_sina_dji(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for record in json.loads(path.read_text(encoding="utf-8")):
        day = record["d"]
        close = str(record["c"])
        if day in rows and rows[day] != close:
            raise SystemExit(f"Sina duplicate {day}")
        rows[day] = close
    return rows


def load_cnbc(directory: Path, symbol: str, company: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise SystemExit(f"no CNBC files in {directory}")
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        details = payload["requestDetails"]
        bar = payload["barData"]
        if details.get("symbol") != symbol or details.get("adjusted") != "UNADJUSTED":
            raise SystemExit(f"{path.name} is not unadjusted {symbol}: {details}")
        if bar.get("companyName") != company:
            raise SystemExit(f"{path.name} companyName {bar.get('companyName')!r}")
        for item in bar["priceBars"]:
            compact = item["tradeTime"][:8]
            day = f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}"
            close = str(item["close"])
            if day in rows and rows[day] != close:
                raise SystemExit(f"CNBC {symbol} duplicate {day}: {rows[day]} vs {close}")
            rows[day] = close
    return rows


def slice_rows(rows: dict[str, str], start: str, end: str) -> dict[str, str]:
    return {day: rows[day] for day in rows if start <= day <= end}


def db_closes(code: str, start: str, end: str) -> tuple[str, dict[str, str]]:
    uri = f"file:{DB}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        source_row = connection.execute(
            "SELECT source FROM bars WHERE code = ? AND adj = 'raw' LIMIT 1",
            (code,),
        ).fetchone()
        if source_row is None:
            raise SystemExit(f"no raw bars for {code}")
        fetched = connection.execute(
            "SELECT date, close FROM bars "
            "WHERE code = ? AND adj = 'raw' AND date >= ? AND date <= ? "
            "ORDER BY date",
            (code, start, end),
        ).fetchall()
    finally:
        connection.close()
    rows = {day: format(float(close), ".12g") for day, close in fetched}
    return str(source_row[0]), rows


def compare(left: dict[str, str], right: dict[str, str], start: str, end: str) -> dict:
    only_left = []
    only_right = []
    paired = []
    worst = None
    for day in sorted(set(left) | set(right)):
        if day < start or day > end:
            continue
        if day not in right:
            only_left.append(day)
            continue
        if day not in left:
            only_right.append(day)
            continue
        a = float(left[day])
        b = float(right[day])
        if b == 0:
            raise SystemExit(f"zero denominator on {day}")
        ratio = abs(a - b) / abs(b)
        row = {
            "date": day,
            "left": left[day],
            "right": right[day],
            "rel": ratio,
        }
        paired.append(row)
        if worst is None or ratio > worst["rel"]:
            worst = row
    return {
        "start": start,
        "end": end,
        "n_overlap": len(paired),
        "only_left": only_left,
        "only_right": only_right,
        "max_rel": None if worst is None else worst["rel"],
        "worst": worst,
        "n_above_0_1pct": sum(1 for row in paired if row["rel"] > STOP),
        "n_above_0_01pct": sum(1 for row in paired if row["rel"] > 0.0001),
        "rows": paired,
    }


def coverage(rows: dict[str, str], start: str, end: str) -> dict:
    chosen = sorted(day for day in rows if start <= day <= end)
    return {
        "start_requested": start,
        "end_requested": end,
        "n": len(chosen),
        "first": chosen[0] if chosen else None,
        "last": chosen[-1] if chosen else None,
        "has_start": start in rows,
        "has_end": end in rows,
        "file_first": min(rows) if rows else None,
        "file_last": max(rows) if rows else None,
        "file_n": len(rows),
    }


def write_pair_csv(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("date", "left", "right", "abs_left_minus_right_over_abs_right"))
        for row in result["rows"]:
            writer.writerow((row["date"], row["left"], row["right"], f"{row['rel']:.12e}"))
        for day in result["only_left"]:
            writer.writerow((day, "ONLY_LEFT", "", ""))
        for day in result["only_right"]:
            writer.writerow((day, "", "ONLY_RIGHT", ""))


def public(result: dict) -> dict:
    copied = dict(result)
    copied.pop("rows", None)
    return copied


def file_record(path: Path) -> dict:
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> int:
    fred = load_fred(RAW / "fred-DJIA.csv")
    yahoo = load_yahoo_dji(RAW / "yahoo-DJI-chart.json")
    sina = load_sina_dji(RAW / "sina-DJI-daily.json")
    cnbc_dji = load_cnbc(RAW / "cnbc-dji", ".DJI", "Dow Jones Industrial Average")
    cnbc_dw = load_cnbc(RAW / "cnbc-dwrtf", ".DWRTF", "DJUSslct REIT")
    tv = load_csv_closes(PRIOR_TV)
    official = load_csv_closes(PRIOR_OFFICIAL)

    dji_source, dji_db = db_closes("DJIA", *DJIA_OVERLAP)
    dw_source, dw_db = db_closes("DWRTF", *DWRTF_OVERLAP)

    NORM.mkdir(parents=True, exist_ok=True)
    normalized = {
        "djia-fred.csv": write_close_csv(NORM / "djia-fred.csv", fred, DJIA_OVERLAP[0], DJIA_REQUIRED[1]),
        "djia-yahoo.csv": write_close_csv(NORM / "djia-yahoo.csv", yahoo, DJIA_OVERLAP[0], DJIA_REQUIRED[1]),
        "djia-sina.csv": write_close_csv(NORM / "djia-sina.csv", sina, DJIA_OVERLAP[0], DJIA_REQUIRED[1]),
        "djia-cnbc.csv": write_close_csv(NORM / "djia-cnbc.csv", cnbc_dji, DJIA_OVERLAP[0], DJIA_REQUIRED[1]),
        "dwrtf-cnbc.csv": write_close_csv(NORM / "dwrtf-cnbc.csv", cnbc_dw, DWRTF_OVERLAP[0], DWRTF_REQUIRED[1]),
        "dwrtf-tradingview-prior.csv": write_close_csv(
            NORM / "dwrtf-tradingview-prior.csv", tv, DWRTF_OVERLAP[0], DWRTF_REQUIRED[1]
        ),
        "dwrtf-official-prior.csv": write_close_csv(
            NORM / "dwrtf-official-prior.csv", official, "2025-11-17", DWRTF_REQUIRED[1]
        ),
    }

    pairs = {
        "djia-fred-vs-cnbc-required": compare(fred, cnbc_dji, *DJIA_REQUIRED),
        "djia-yahoo-vs-cnbc-required": compare(yahoo, cnbc_dji, *DJIA_REQUIRED),
        "djia-sina-vs-cnbc-required": compare(sina, cnbc_dji, *DJIA_REQUIRED),
        "djia-fred-vs-yahoo-required": compare(fred, yahoo, *DJIA_REQUIRED),
        "djia-fred-vs-db": compare(fred, dji_db, *DJIA_OVERLAP),
        "djia-yahoo-vs-db": compare(yahoo, dji_db, *DJIA_OVERLAP),
        "djia-sina-vs-db": compare(sina, dji_db, *DJIA_OVERLAP),
        "djia-cnbc-vs-db": compare(cnbc_dji, dji_db, *DJIA_OVERLAP),
        "dwrtf-cnbc-vs-tv-required": compare(cnbc_dw, tv, *DWRTF_REQUIRED),
        "dwrtf-cnbc-vs-official": compare(cnbc_dw, official, "2025-11-17", DWRTF_REQUIRED[1]),
        "dwrtf-cnbc-vs-db": compare(cnbc_dw, dw_db, *DWRTF_OVERLAP),
        "dwrtf-tv-vs-db": compare(tv, dw_db, *DWRTF_OVERLAP),
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    for name, result in pairs.items():
        write_pair_csv(EVIDENCE / f"{name}.csv", result)

    blocked = []
    for name in (
        "djia-fred-vs-db",
        "djia-yahoo-vs-db",
        "djia-sina-vs-db",
        "djia-cnbc-vs-db",
        "dwrtf-cnbc-vs-db",
        "dwrtf-tv-vs-db",
    ):
        if pairs[name]["n_above_0_1pct"]:
            blocked.append(name)

    report = {
        "formula": "abs(left - right) / abs(right)",
        "stop_if_database_rel_gt": STOP,
        "database_stop": blocked,
        "djia": {
            "required": DJIA_REQUIRED,
            "overlap_requested": DJIA_OVERLAP,
            "db_source": dji_source,
            "db_overlap_n": len(dji_db),
            "db_overlap_ge_60": len(dji_db) >= 60,
            "coverage": {
                "fred": coverage(fred, *DJIA_REQUIRED),
                "yahoo": coverage(yahoo, *DJIA_REQUIRED),
                "sina": coverage(sina, *DJIA_REQUIRED),
                "cnbc": coverage(cnbc_dji, *DJIA_REQUIRED),
            },
        },
        "dwrtf": {
            "required": DWRTF_REQUIRED,
            "overlap_requested": DWRTF_OVERLAP,
            "db_source": dw_source,
            "db_overlap_n": len(dw_db),
            "db_overlap_ge_60": len(dw_db) >= 60,
            "coverage": {
                "cnbc": coverage(cnbc_dw, *DWRTF_REQUIRED),
                "tradingview_prior": coverage(tv, *DWRTF_REQUIRED),
                "official_prior_clipped": coverage(official, "2025-11-17", DWRTF_REQUIRED[1]),
            },
            "prior_files_not_redownloaded": {
                "tradingview": str(PRIOR_TV.relative_to(ROOT)),
                "official_csv": str(PRIOR_OFFICIAL.relative_to(ROOT)),
            },
        },
        "normalized_rows": normalized,
        "files": [file_record(path) for path in sorted(RAW.rglob("*")) if path.is_file()]
        + [file_record(path) for path in sorted(NORM.glob("*.csv"))]
        + [file_record(PRIOR_TV), file_record(PRIOR_OFFICIAL)],
        "pairs": {name: public(result) for name, result in pairs.items()},
    }
    (EVIDENCE / "comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({name: public(result) for name, result in pairs.items()}, ensure_ascii=False, indent=2))
    print("normalized", normalized)
    print("db", dji_source, len(dji_db), dw_source, len(dw_db))
    if blocked:
        print("STOP database relative difference > 0.1%:", ", ".join(blocked))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
