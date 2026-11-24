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
Exit 0 means the report was written. It does not mean the required windows
are complete, and it does not freeze a usable daily series. Session coverage
and the unresolved exceptions are written under incoming/v6-us-gapfill/evidence/.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import sys
from datetime import date, datetime, timedelta
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
# Two prints that both show cents and differ by more than half a cent are not
# treated as rounding. 2019-08-12 differs by 0.12.
CONFLICT_ABS = 0.005
# Weekday rows in raw/fred-DJIA.csv from 2017-08-01 through 2026-09-30 whose
# close is blank. They match the NYSE full closures in that span, including
# 2018-12-05 and 2025-01-09. 2021-12-31 is not here: FRED prints 36338.30.
NYSE_FULL_CLOSE = frozenset({
    "2017-09-04", "2017-11-23", "2017-12-25",
    "2018-01-01", "2018-01-15", "2018-02-19", "2018-03-30", "2018-05-28",
    "2018-07-04", "2018-09-03", "2018-11-22", "2018-12-05", "2018-12-25",
    "2019-01-01", "2019-01-21", "2019-02-18", "2019-04-19", "2019-05-27",
    "2019-07-04", "2019-09-02", "2019-11-28", "2019-12-25",
    "2020-01-01", "2020-01-20", "2020-02-17", "2020-04-10", "2020-05-25",
    "2020-07-03", "2020-09-07", "2020-11-26", "2020-12-25",
    "2021-01-01", "2021-01-18", "2021-02-15", "2021-04-02", "2021-05-31",
    "2021-07-05", "2021-09-06", "2021-11-25", "2021-12-24",
    "2022-01-17", "2022-02-21", "2022-04-15", "2022-05-30", "2022-06-20",
    "2022-07-04", "2022-09-05", "2022-11-24", "2022-12-26",
    "2023-01-02", "2023-01-16", "2023-02-20", "2023-04-07", "2023-05-29",
    "2023-06-19", "2023-07-04", "2023-09-04", "2023-11-23", "2023-12-25",
    "2024-01-01", "2024-01-15", "2024-02-19", "2024-03-29", "2024-05-27",
    "2024-06-19", "2024-07-04", "2024-09-02", "2024-11-28", "2024-12-25",
    "2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18",
    "2025-05-26", "2025-06-19", "2025-07-04", "2025-09-01", "2025-11-27",
    "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07",
})

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


def is_session(day: str) -> bool:
    return date.fromisoformat(day).weekday() < 5 and day not in NYSE_FULL_CLOSE


def sessions(start: str, end: str) -> list[str]:
    cursor = date.fromisoformat(start)
    stop = date.fromisoformat(end)
    found = []
    while cursor <= stop:
        day = cursor.isoformat()
        if is_session(day):
            found.append(day)
        cursor += timedelta(days=1)
    return found


def fred_blank_weekdays(path: Path, start: str, end: str) -> list[str]:
    found = []
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        day, close = line.split(",", 1)
        if day < start or day > end or date.fromisoformat(day).weekday() >= 5:
            continue
        if close in {"", "."}:
            found.append(day)
    return found


def archive_vs_sessions(rows: dict[str, str], start: str, end: str) -> dict:
    expected = sessions(start, end)
    expected_set = set(expected)
    have = {day for day in rows if start <= day <= end}
    missing = [day for day in expected if day not in have]
    extra = sorted(day for day in have if day not in expected_set)
    return {
        "expected_sessions": len(expected),
        "archive_rows": len(have),
        "sessions_present": len(expected_set & have),
        "missing_sessions": missing,
        "non_session_rows": extra,
        "sessions_complete": not missing,
    }


def cnbc_ohlc(directory: Path, day: str) -> dict[str, str] | None:
    compact = day.replace("-", "")
    for path in sorted(directory.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload["barData"]["priceBars"]:
            if item["tradeTime"][:8] == compact:
                return {key: str(item[key]) for key in ("open", "high", "low", "close")}
    return None


def close_conflicts(left: dict[str, str], right: dict[str, str], start: str, end: str) -> list[dict]:
    found = []
    for day in sessions(start, end):
        if day not in left or day not in right:
            continue
        gap = abs(float(left[day]) - float(right[day]))
        if gap > CONFLICT_ABS:
            found.append({
                "date": day,
                "left": left[day],
                "right": right[day],
                "abs_diff": gap,
                "adopted_close": None,
                "kind": "unresolved_source_conflict",
            })
    return found


def write_session_table(path: Path, header: tuple[str, ...], rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def session_coverage(
    fred: dict[str, str],
    yahoo: dict[str, str],
    sina: dict[str, str],
    cnbc_dji: dict[str, str],
    cnbc_dw: dict[str, str],
    tv: dict[str, str],
) -> dict:
    blanks = fred_blank_weekdays(RAW / "fred-DJIA.csv", "2017-08-01", "2026-09-30")
    calendar_ok = set(blanks) == set(NYSE_FULL_CLOSE)
    djia_sources = {
        "fred": archive_vs_sessions(fred, *DJIA_REQUIRED),
        "yahoo": archive_vs_sessions(yahoo, *DJIA_REQUIRED),
        "sina": archive_vs_sessions(sina, *DJIA_REQUIRED),
        "cnbc": archive_vs_sessions(cnbc_dji, *DJIA_REQUIRED),
    }
    dw_sources = {
        "cnbc": archive_vs_sessions(cnbc_dw, *DWRTF_REQUIRED),
        "tradingview_prior": archive_vs_sessions(tv, *DWRTF_REQUIRED),
    }
    conflicts = close_conflicts(cnbc_dw, tv, *DWRTF_REQUIRED)
    pseudo = []
    for series, directory in (("DJIA", RAW / "cnbc-dji"), ("DWRTF", RAW / "cnbc-dwrtf")):
        copied = cnbc_ohlc(directory, "2024-12-24")
        phantom = cnbc_ohlc(directory, "2024-12-25")
        pseudo.append({
            "series": series,
            "date": "2024-12-25",
            "kind": "pseudo_session_not_counted",
            "is_session": False,
            "ohlc_equals_2024_12_24": copied == phantom and copied is not None,
            "close": None if phantom is None else phantom["close"],
            "adopted_close": None,
        })
    missing = {
        "series": "DWRTF",
        "date": "2023-04-06",
        "kind": "missing_real_session",
        "is_session": is_session("2023-04-06"),
        "fred_djia_close": fred.get("2023-04-06"),
        "cnbc": cnbc_dw.get("2023-04-06"),
        "tradingview_prior": tv.get("2023-04-06"),
        "adopted_close": None,
    }
    yahoo_attempt = RAW / "yahoo-DWRTF-20190812-chart-no-history.json"
    yahoo_has_bars = False
    if yahoo_attempt.exists():
        payload = json.loads(yahoo_attempt.read_text(encoding="utf-8"))
        yahoo_has_bars = "timestamp" in payload["chart"]["result"][0]

    djia_rows = []
    for day in sessions(*DJIA_REQUIRED):
        djia_rows.append((
            day,
            fred.get(day, ""),
            yahoo.get(day, ""),
            sina.get(day, ""),
            cnbc_dji.get(day, ""),
        ))
    dw_rows = []
    conflict_days = {item["date"] for item in conflicts}
    for day in sessions(*DWRTF_REQUIRED):
        if day not in cnbc_dw:
            note = "missing_from_fresh_cnbc"
        elif day in conflict_days:
            note = "unresolved_source_conflict"
        elif day not in tv:
            note = "missing_from_tradingview_prior"
        else:
            note = ""
        dw_rows.append((day, cnbc_dw.get(day, ""), tv.get(day, ""), note))
    write_session_table(
        EVIDENCE / "djia-sessions.csv",
        ("date", "fred", "yahoo", "sina", "cnbc"),
        djia_rows,
    )
    write_session_table(
        EVIDENCE / "dwrtf-sessions.csv",
        ("date", "cnbc", "tradingview_prior", "note"),
        dw_rows,
    )
    exception_rows = [
        ("DJIA", "2024-12-25", "pseudo_session_not_counted", pseudo[0]["close"] or "", ""),
        ("DWRTF", "2024-12-25", "pseudo_session_not_counted", pseudo[1]["close"] or "", ""),
        (
            "DWRTF", "2023-04-06", "missing_real_session",
            f"fred_djia={fred.get('2023-04-06', '')}; tradingview_prior={tv.get('2023-04-06', '')}; not_adopted",
            "",
        ),
    ]
    for item in conflicts:
        exception_rows.append((
            "DWRTF", item["date"], item["kind"],
            f"cnbc={item['left']}; tradingview_prior={item['right']}", "",
        ))
    write_session_table(
        EVIDENCE / "session-exceptions.csv",
        ("series", "date", "kind", "evidence", "adopted_close"),
        exception_rows,
    )
    fresh_dw = dw_sources["cnbc"]
    report = {
        "deliverable": "source_archive",
        "usable_series_frozen": False,
        "common_date_max_rel_below_0_1pct_is_not_completeness": True,
        "calendar_matches_fred_blank_weekdays": calendar_ok,
        "fred_blank_weekdays": len(blanks),
        "named_full_closes": len(NYSE_FULL_CLOSE),
        "djia_required": djia_sources,
        "dwrtf_required": dw_sources,
        "djia_fresh_sessions_complete": all(
            item["sessions_complete"] and not item["non_session_rows"]
            for item in (djia_sources["fred"], djia_sources["yahoo"], djia_sources["sina"])
        ),
        "dwrtf_fresh_sessions_complete": fresh_dw["sessions_complete"] and not fresh_dw["non_session_rows"],
        "pseudo_sessions": pseudo,
        "missing_real_session": missing,
        "unresolved_source_conflicts": conflicts,
        "third_source_for_2019_08_12": {
            "yahoo_chart_file": yahoo_attempt.name,
            "yahoo_chart_has_timestamps": yahoo_has_bars,
            "close_adopted": None,
        },
        "selection_rules": [
            "Raw downloads stay unchanged, including non-sessions and disagreements.",
            "A trading day is a weekday that is not in NYSE_FULL_CLOSE.",
            "2024-12-25 is not a trading day. The CNBC bar copies 2024-12-24 and is not coverage.",
            "2023-04-06 is a trading day. It is absent from fresh CNBC and is not filled from the prior TradingView file.",
            "A same-session absolute difference above 0.005 is an unresolved conflict. Neither close is adopted.",
            "The prior TradingView file is not a fresh download and is the database upstream, so it is not a second independent source.",
        ],
    }
    (EVIDENCE / "session-coverage.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


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
    coverage_report = session_coverage(fred, yahoo, sina, cnbc_dji, cnbc_dw, tv)

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
        "session_coverage": coverage_report,
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
    print(
        "usable_series_frozen", coverage_report["usable_series_frozen"],
        "djia_fresh_sessions_complete", coverage_report["djia_fresh_sessions_complete"],
        "dwrtf_fresh_sessions_complete", coverage_report["dwrtf_fresh_sessions_complete"],
        "conflicts", coverage_report["unresolved_source_conflicts"],
    )
    if blocked:
        print("STOP database relative difference > 0.1%:", ", ".join(blocked))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
