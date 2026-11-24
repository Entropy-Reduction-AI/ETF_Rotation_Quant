"""Authorized DJIA / DWRTF raw append. Standard library only.

The calendar and raw loaders come from scripts/v6_us_gapfill_compare.py.
This module does not write the database and does not compute returns.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "market.sqlite"
EVIDENCE = ROOT / "operations" / "evidence" / "v6-us-raw-index-ingest"
BACKUP_PATH = EVIDENCE / "market-before.sqlite"
LABEL = "v6-us-raw-index"
OWNER = "Owner 2026-11-24 21:21 Asia/Taipei"
BASE_COMMIT = "05e39c5650acb52e0de8632bcaef8e6d05fe5597"

DJIA_FULL = ("2024-02-01", "2026-09-30")
DJIA_NEW = ("2024-02-02", "2026-09-30")
DJIA_OVERLAP = ("2023-11-01", "2024-02-01")
DWRTF_FULL = ("2017-11-22", "2026-09-30")
DWRTF_NEW = ("2017-11-24", "2026-09-30")
DWRTF_OVERLAP = ("2017-08-01", "2017-11-22")
PSEUDO = "2024-12-25"
SINGLE_DAY = "2023-04-06"
CONFLICT_DAY = "2019-08-12"
SINGLE_CLOSE = "259.56"
CONFLICT_CNBC = "294.58"
CONFLICT_TV = "294.46"

OWNER_COUNTS = {
    "djia_full_sessions": 668,
    "djia_new": 667,
    "dwrtf_full_sessions": 2224,
    "dwrtf_new": 2223,
    "djia_overlap": 63,
    "dwrtf_overlap": 81,
}

FRED_SOURCE = "v6_gapfill_fred"
CNBC_SOURCE = "v6_gapfill_cnbc"
TV_SOURCE = "v6_gapfill_tv"
NEW_SOURCES = (FRED_SOURCE, CNBC_SOURCE, TV_SOURCE)

INSERT_SQL = (
    "INSERT INTO bars "
    "(code, adj, date, open, high, low, close, volume, amount, source, fetched_at) "
    "VALUES (?, 'raw', ?, NULL, NULL, NULL, ?, NULL, NULL, ?, ?)"
)


def load_gap():
    path = ROOT / "scripts" / "v6_us_gapfill_compare.py"
    spec = importlib.util.spec_from_file_location("v6_us_gapfill_compare", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def connect_ro(path: Path = DB_PATH) -> sqlite3.Connection:
    uri = f"file:{path.resolve()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def level_gap(left: str | None, right: str | None) -> str:
    """Absolute close gap divided by the absolute reference close. Not a return."""
    if left is None or right is None or left == "" or right == "":
        return ""
    base = float(right)
    if base == 0:
        return ""
    return f"{abs(float(left) - base) / abs(base):.12e}"


@dataclass(frozen=True)
class Bar:
    code: str
    date: str
    close_text: str
    source: str

    @property
    def close(self) -> float:
        return float(self.close_text)


@dataclass
class SourcePlan:
    djia: list[Bar]
    dwrtf: list[Bar]
    djia_full: list[str]
    dwrtf_full: list[str]
    flags: list[dict]
    counts: dict
    problems: list[str] = field(default_factory=list)

    @property
    def bars(self) -> list[Bar]:
        return self.djia + self.dwrtf


def _dates(bars: list[Bar]) -> list[str]:
    return [bar.date for bar in bars]


def build_source_plan(gap=None) -> SourcePlan:
    """Rows the authorization allows. Does not read or write the database."""
    gap = gap or load_gap()
    problems: list[str] = []
    fred = gap.load_fred(gap.RAW / "fred-DJIA.csv")
    cnbc = gap.load_cnbc(gap.RAW / "cnbc-dwrtf", ".DWRTF", "DJUSslct REIT")
    tv = gap.load_csv_closes(gap.PRIOR_TV)

    djia_full = gap.sessions(*DJIA_FULL)
    dwrtf_full = gap.sessions(*DWRTF_FULL)
    djia_new = [day for day in djia_full if day >= DJIA_NEW[0]]
    dwrtf_new = [day for day in dwrtf_full if day >= DWRTF_NEW[0]]

    counts = {
        "djia_full_sessions": len(djia_full),
        "djia_new": len(djia_new),
        "dwrtf_full_sessions": len(dwrtf_full),
        "dwrtf_new": len(dwrtf_new),
        "djia_full_first": djia_full[0] if djia_full else None,
        "djia_full_last": djia_full[-1] if djia_full else None,
        "djia_new_first": djia_new[0] if djia_new else None,
        "djia_new_last": djia_new[-1] if djia_new else None,
        "dwrtf_full_first": dwrtf_full[0] if dwrtf_full else None,
        "dwrtf_full_last": dwrtf_full[-1] if dwrtf_full else None,
        "dwrtf_new_first": dwrtf_new[0] if dwrtf_new else None,
        "dwrtf_new_last": dwrtf_new[-1] if dwrtf_new else None,
    }
    for key, expected in OWNER_COUNTS.items():
        if key not in counts:
            continue
        if counts[key] != expected:
            problems.append(
                f"{key} computed {counts[key]} owner_expected {expected}; not trimming the date list"
            )
    if djia_full[:1] != ["2024-02-01"] or djia_full[-1:] != ["2026-09-30"]:
        problems.append(f"DJIA full window endpoints {djia_full[:1]} {djia_full[-1:]}")
    if dwrtf_full[:1] != ["2017-11-22"] or dwrtf_full[-1:] != ["2026-09-30"]:
        problems.append(f"DWRTF full window endpoints {dwrtf_full[:1]} {dwrtf_full[-1:]}")
    if PSEUDO in djia_new or PSEUDO in dwrtf_new or gap.is_session(PSEUDO):
        problems.append("2024-12-25 is inside the session calendar")

    fred_window = {day: fred[day] for day in fred if DJIA_NEW[0] <= day <= DJIA_NEW[1]}
    missing_fred = [day for day in djia_new if day not in fred_window]
    extra_fred = sorted(set(fred_window) - set(djia_new))
    if missing_fred:
        problems.append(f"FRED missing {len(missing_fred)} new DJIA sessions, first {missing_fred[:5]}")
    if extra_fred:
        problems.append(f"FRED has {len(extra_fred)} non-session dates in the new DJIA window, first {extra_fred[:5]}")

    cnbc_window = {day: cnbc[day] for day in cnbc if DWRTF_NEW[0] <= day <= DWRTF_NEW[1]}
    missing_cnbc = sorted(set(dwrtf_new) - set(cnbc_window))
    extra_cnbc = sorted(set(cnbc_window) - set(dwrtf_new))
    if missing_cnbc != [SINGLE_DAY]:
        problems.append(f"CNBC DWRTF missing sessions {missing_cnbc}, expected only {SINGLE_DAY}")
    if extra_cnbc != [PSEUDO]:
        problems.append(f"CNBC DWRTF extra dates {extra_cnbc}, expected only {PSEUDO}")
    if tv.get(SINGLE_DAY) != SINGLE_CLOSE:
        problems.append(f"TradingView {SINGLE_DAY} is {tv.get(SINGLE_DAY)!r}, expected {SINGLE_CLOSE}")
    if SINGLE_DAY in cnbc_window:
        problems.append(f"CNBC has {SINGLE_DAY}; authorized fill is TradingView only")
    cnbc_conflict = cnbc.get(CONFLICT_DAY)
    tv_conflict = tv.get(CONFLICT_DAY)
    if cnbc_conflict is None or float(cnbc_conflict) != float(CONFLICT_CNBC):
        problems.append(f"CNBC {CONFLICT_DAY} is {cnbc_conflict!r}, expected {CONFLICT_CNBC}")
    if tv_conflict != CONFLICT_TV:
        problems.append(f"TradingView {CONFLICT_DAY} is {tv_conflict!r}, expected {CONFLICT_TV}")

    conflicts = []
    tv_missing = []
    for day in dwrtf_new:
        if day == SINGLE_DAY:
            continue
        if day not in cnbc_window:
            continue
        if day not in tv:
            tv_missing.append(day)
            continue
        if abs(float(cnbc_window[day]) - float(tv[day])) > 0.005:
            conflicts.append(day)
    if conflicts != [CONFLICT_DAY]:
        problems.append(f"close disagreements above half a cent: {conflicts}")
    if tv_missing:
        problems.append(f"TradingView missing {len(tv_missing)} CNBC sessions, first {tv_missing[:5]}")

    djia = [
        Bar("DJIA", day, fred_window[day], FRED_SOURCE)
        for day in djia_new
        if day in fred_window
    ]
    dwrtf: list[Bar] = []
    for day in dwrtf_new:
        if day == SINGLE_DAY and tv.get(day) == SINGLE_CLOSE:
            dwrtf.append(Bar("DWRTF", day, SINGLE_CLOSE, TV_SOURCE))
        elif day in cnbc_window and day != PSEUDO:
            dwrtf.append(Bar("DWRTF", day, cnbc_window[day], CNBC_SOURCE))
    if [bar.date for bar in djia] != djia_new or any(bar.date == PSEUDO for bar in djia):
        problems.append("DJIA insert list is not the new session list")
    if [bar.date for bar in dwrtf] != dwrtf_new or any(bar.date == PSEUDO for bar in dwrtf):
        problems.append("DWRTF insert list is not the new session list")
    if len({(bar.code, bar.date) for bar in djia + dwrtf}) != len(djia) + len(dwrtf):
        problems.append("duplicate insert keys")

    gap_text = ""
    if cnbc_conflict and tv_conflict:
        gap_text = level_gap(cnbc_conflict, tv_conflict)
    flags = [
        {
            "series": "DWRTF",
            "date": SINGLE_DAY,
            "flag": "single_source",
            "adopted_source": TV_SOURCE,
            "adopted_close": SINGLE_CLOSE,
            "reference_publisher": "archived TradingView/ICE",
            "reference_close": SINGLE_CLOSE,
            "level_gap_over_reference": "",
            "cause": "",
            "ruling": OWNER,
        },
        {
            "series": "DWRTF",
            "date": CONFLICT_DAY,
            "flag": "source_conflict",
            "adopted_source": CNBC_SOURCE,
            "adopted_close": CONFLICT_CNBC,
            "source_token": cnbc_conflict,
            "reference_publisher": "archived TradingView/ICE",
            "reference_close": CONFLICT_TV,
            "level_gap_over_reference": gap_text,
            "cause": "",
            "ruling": OWNER,
        },
    ]
    return SourcePlan(djia, dwrtf, djia_full, dwrtf_full, flags, counts, problems)


def _window_rows(con: sqlite3.Connection, code: str, start: str, end: str) -> list[tuple]:
    return con.execute(
        "SELECT date, close, source, open, high, low, volume, amount "
        "FROM bars WHERE code = ? AND adj = 'raw' AND date >= ? AND date <= ? ORDER BY date",
        (code, start, end),
    ).fetchall()


def _series_facts(con: sqlite3.Connection, code: str) -> dict:
    row = con.execute(
        "SELECT COUNT(*), MIN(date), MAX(date), COUNT(DISTINCT source), "
        "MIN(source), SUM(adj <> 'raw') "
        "FROM bars WHERE code = ?",
        (code,),
    ).fetchone()
    return {
        "rows": int(row[0]),
        "first": row[1],
        "last": row[2],
        "sources": int(row[3] or 0),
        "source_min": row[4],
        "non_raw": int(row[5] or 0),
    }


def overlap_problems(con: sqlite3.Connection, gap, plan: SourcePlan) -> list[str]:
    problems = []
    fred = gap.load_fred(gap.RAW / "fred-DJIA.csv")
    cnbc = gap.load_cnbc(gap.RAW / "cnbc-dwrtf", ".DWRTF", "DJUSslct REIT")
    checks = (
        ("DJIA", DJIA_OVERLAP, fred, "eastmoney_index", OWNER_COUNTS["djia_overlap"]),
        ("DWRTF", DWRTF_OVERLAP, cnbc, "d37_r6", OWNER_COUNTS["dwrtf_overlap"]),
    )
    for code, window, source, expect_source, expect_n in checks:
        sessions = gap.sessions(*window)
        rows = _window_rows(con, code, *window)
        got_dates = [row[0] for row in rows]
        if got_dates != sessions:
            missing = [day for day in sessions if day not in set(got_dates)]
            extra = [day for day in got_dates if day not in set(sessions)]
            problems.append(
                f"{code} overlap {window[0]}..{window[1]} db {len(got_dates)} "
                f"sessions {len(sessions)} missing {missing[:5]} extra {extra[:5]}"
            )
        elif len(rows) != expect_n:
            problems.append(f"{code} overlap count {len(rows)} owner_expected {expect_n}")
        mismatched = []
        for day, close, src, *_rest in rows:
            if src != expect_source:
                mismatched.append(f"{day} source {src}")
                continue
            if day not in source or float(source[day]) != float(close):
                left = source.get(day)
                mismatched.append(f"{day} source {left} db {close}")
        if mismatched:
            problems.append(f"{code} overlap close mismatch {mismatched[:5]} n={len(mismatched)}")
    return problems


def boundary_problems(con: sqlite3.Connection) -> list[str]:
    """Preconditions for an empty append. Fail closed if the stored edges differ."""
    problems = []
    expected = {
        "DJIA": {
            "last": "2024-02-01",
            "source": "eastmoney_index",
            "rows_after": ("2024-02-01", 0),
            "window": DJIA_FULL,
            "window_dates": ["2024-02-01"],
        },
        "DWRTF": {
            "last": "2017-11-22",
            "source": "d37_r6",
            "rows_after": ("2017-11-22", 0),
            "window": DWRTF_FULL,
            "window_dates": ["2017-11-22"],
        },
    }
    for code, spec in expected.items():
        facts = _series_facts(con, code)
        if facts["non_raw"]:
            problems.append(f"{code} has {facts['non_raw']} non-raw rows")
        if facts["last"] != spec["last"]:
            problems.append(f"{code} last date {facts['last']} expected {spec['last']}")
        if facts["sources"] != 1 or facts["source_min"] != spec["source"]:
            problems.append(f"{code} sources {facts['sources']} min {facts['source_min']}")
        after = con.execute(
            "SELECT COUNT(*) FROM bars WHERE code = ? AND adj = 'raw' AND date > ?",
            (code, spec["rows_after"][0]),
        ).fetchone()[0]
        if after != spec["rows_after"][1]:
            problems.append(f"{code} rows after {spec['rows_after'][0]}: {after}")
        window = [row[0] for row in _window_rows(con, code, *spec["window"])]
        if window != spec["window_dates"]:
            problems.append(f"{code} dates inside {spec['window']}: {window[:8]} n={len(window)}")
    pseudo = con.execute(
        "SELECT code, source FROM bars WHERE code IN ('DJIA', 'DWRTF') AND date = ?",
        (PSEUDO,),
    ).fetchall()
    if pseudo:
        problems.append(f"database already has {PSEUDO}: {pseudo}")
    return problems


def inserted_map(con: sqlite3.Connection) -> dict[tuple[str, str], tuple]:
    rows = con.execute(
        "SELECT code, date, close, source, open, high, low, volume, amount "
        "FROM bars WHERE source IN (?, ?, ?) ORDER BY code, date",
        NEW_SOURCES,
    ).fetchall()
    return {(row[0], row[1]): row for row in rows}


def post_problems(con: sqlite3.Connection, plan: SourcePlan) -> list[str]:
    problems = []
    found = inserted_map(con)
    expected = {(bar.code, bar.date): bar for bar in plan.bars}
    missing = sorted(set(expected) - set(found))
    extra = sorted(set(found) - set(expected))
    if missing:
        problems.append(f"missing inserted keys {missing[:5]} n={len(missing)}")
    if extra:
        problems.append(f"extra inserted keys {extra[:5]} n={len(extra)}")
    mismatched = []
    for key, bar in expected.items():
        row = found.get(key)
        if row is None:
            continue
        _code, _day, close, source, open_, high, low, volume, amount = row
        if source != bar.source or float(close) != bar.close:
            mismatched.append(f"{key} db {close} {source} plan {bar.close_text} {bar.source}")
        if any(value is not None for value in (open_, high, low, volume, amount)):
            mismatched.append(f"{key} non-close field was filled")
    if mismatched:
        problems.append(f"inserted value mismatch {mismatched[:5]} n={len(mismatched)}")
    if any(key[1] == PSEUDO for key in found):
        problems.append(f"{PSEUDO} was inserted")
    for code, last in (("DJIA", "2026-09-30"), ("DWRTF", "2026-09-30")):
        got = con.execute("SELECT MAX(date) FROM bars WHERE code = ? AND adj = 'raw'", (code,)).fetchone()[0]
        if got != last:
            problems.append(f"{code} final date {got} expected {last}")
    djia_edge = con.execute(
        "SELECT close, source, open FROM bars WHERE code = 'DJIA' AND adj = 'raw' AND date = '2024-02-01'"
    ).fetchone()
    dw_edge = con.execute(
        "SELECT close, source, open FROM bars WHERE code = 'DWRTF' AND adj = 'raw' AND date = '2017-11-22'"
    ).fetchone()
    if djia_edge != (38519.84, "eastmoney_index", 38175.34):
        problems.append(f"DJIA 2024-02-01 changed: {djia_edge}")
    if dw_edge is None or float(dw_edge[0]) != 275.66 or dw_edge[1] != "d37_r6" or dw_edge[2] is not None:
        problems.append(f"DWRTF 2017-11-22 changed: {dw_edge}")
    return problems


def classify(con: sqlite3.Connection, plan: SourcePlan) -> tuple[str, list[str]]:
    found = 0
    for code, dates in (
        ("DJIA", [bar.date for bar in plan.djia]),
        ("DWRTF", [bar.date for bar in plan.dwrtf]),
    ):
        if not dates:
            continue
        marks = ",".join("?" * len(dates))
        found += con.execute(
            f"SELECT COUNT(*) FROM bars WHERE code = ? AND adj = 'raw' AND date IN ({marks})",
            (code, *dates),
        ).fetchone()[0]
    expected = len(plan.bars)
    if found == 0:
        return "absent", boundary_problems(con)
    if found == expected:
        return "complete", post_problems(con, plan)
    return "partial", [f"partial insert {found} of {expected} authorized dates"]


def canon_row(row: tuple) -> bytes:
    parts = []
    for index, value in enumerate(row):
        if value is None:
            parts.append("")
        elif 3 <= index <= 8:
            parts.append(format(float(value), ".17g"))
        else:
            parts.append(str(value))
    return ("\t".join(parts) + "\n").encode()


def fingerprint_rows(con: sqlite3.Connection, exclude: set[tuple[str, str, str]] | None = None) -> tuple[str, int]:
    digest = hashlib.sha256()
    count = 0
    query = (
        "SELECT code, adj, date, open, high, low, close, volume, amount, source, fetched_at "
        "FROM bars ORDER BY code, adj, date"
    )
    for row in con.execute(query):
        if exclude and (row[0], row[1], row[2]) in exclude:
            continue
        digest.update(canon_row(row))
        count += 1
    return digest.hexdigest(), count


def count_fingerprint(con: sqlite3.Connection, skip_codes: set[str] | None = None) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    for code, adj, count in con.execute(
        "SELECT code, adj, COUNT(*) FROM bars GROUP BY code, adj ORDER BY code, adj"
    ):
        if skip_codes and code in skip_codes:
            continue
        digest.update(f"{code}\t{adj}\t{count}\n".encode())
        total += int(count)
    return digest.hexdigest(), total


def schema_snapshot(con: sqlite3.Connection) -> list[tuple]:
    return con.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name, tbl_name"
    ).fetchall()


def reinstall_source_guard(con: sqlite3.Connection, sql: str) -> None:
    con.execute("DROP TRIGGER IF EXISTS bars_one_source")
    con.execute(sql)


def sample_dates(days: list[str], forced: list[str]) -> list[str]:
    if not days:
        return []
    last = len(days) - 1
    picked = {days[round(i * last / 19)] for i in range(20)}
    have = set(days)
    for day in forced:
        if day in have:
            picked.add(day)
    return sorted(picked)


def month_ends(days: list[str]) -> list[str]:
    last: dict[str, str] = {}
    for day in days:
        last[day[:7]] = day
    return [last[key] for key in sorted(last)]


def file_manifest(paths: list[Path]) -> list[tuple[str, str]]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(item for item in path.rglob("*") if item.is_file() and not item.is_symlink())
    rows = []
    for path in sorted(set(files)):
        rows.append((sha256_file(path), str(path.relative_to(ROOT))))
    return rows


UNCHANGED_ROOTS = [
    ROOT / "incoming" / "v6-us-gapfill",
    ROOT / "incoming" / "grok-d37-index-20261116" / "theme-道琼斯美国精选REIT指数-tradingview.csv",
    ROOT / "incoming" / "grok-d37-index-20261116"
    / "theme-道琼斯美国精选REIT指数-official-usd-pr-daily-20251117-20261116.csv",
    ROOT / "config",
    ROOT / "data" / "universe.csv",
]
