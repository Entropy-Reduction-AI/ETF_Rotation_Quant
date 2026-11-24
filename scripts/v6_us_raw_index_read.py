"""Read-only month-end and sample comparison for the authorized raw append.

    python3 -I scripts/v6_us_raw_index_read.py

Writes evidence CSVs. Does not write data/market.sqlite and does not compute returns.
Exit 2 when the source plan or the database disagrees with the authorization.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


def _load_lib():
    path = Path(__file__).resolve().parent / "v6_us_raw_index_lib.py"
    spec = importlib.util.spec_from_file_location("v6_us_raw_index_lib", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lib = _load_lib()


def _show(value) -> str:
    if value is None or value == "":
        return ""
    return format(float(value), ".10f").rstrip("0").rstrip(".")


def _db_map(con, code: str, start: str, end: str) -> dict[str, tuple[str, str]]:
    rows = {}
    for day, close, source in con.execute(
        "SELECT date, close, source FROM bars "
        "WHERE code = ? AND adj = 'raw' AND date >= ? AND date <= ? ORDER BY date",
        (code, start, end),
    ):
        rows[day] = (_show(close), source)
    return rows


def _write_csv(path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def _djia_row(day: str, fred, cnbc, yahoo, sina, db) -> list[str]:
    fred_close = fred.get(day, "")
    db_close, db_source = db.get(day, ("", ""))
    return [
        day,
        fred_close,
        cnbc.get(day, ""),
        yahoo.get(day, ""),
        sina.get(day, ""),
        db_close,
        db_source,
        lib.level_gap(cnbc.get(day), fred_close),
        lib.level_gap(yahoo.get(day), fred_close),
        lib.level_gap(sina.get(day), fred_close),
        lib.level_gap(db_close, fred_close),
    ]


def _dw_row(day: str, cnbc, tv, db, adopted: dict[str, lib.Bar]) -> list[str]:
    bar = adopted.get(day)
    db_close, db_source = db.get(day, ("", ""))
    flag = ""
    if day == lib.SINGLE_DAY:
        flag = "single_source"
    elif day == lib.CONFLICT_DAY:
        flag = "source_conflict"
    reference = tv.get(day, "")
    return [
        day,
        cnbc.get(day, ""),
        reference,
        "" if bar is None else bar.source,
        "" if bar is None else bar.close_text,
        flag,
        db_close,
        db_source,
        lib.level_gap(cnbc.get(day), reference),
        lib.level_gap(db_close, None if bar is None else bar.close_text),
    ]


DJIA_HEADER = [
    "date", "fred", "cnbc", "yahoo", "sina", "db_close", "db_source",
    "abs_level_gap_cnbc_over_fred", "abs_level_gap_yahoo_over_fred",
    "abs_level_gap_sina_over_fred", "abs_level_gap_db_over_fred",
]
DWRTF_HEADER = [
    "date", "cnbc", "tradingview", "adopted_source", "adopted_close", "flag",
    "db_close", "db_source", "abs_level_gap_cnbc_over_tv", "abs_level_gap_db_over_adopted",
]


def main() -> int:
    gap = lib.load_gap()
    plan = lib.build_source_plan(gap)
    con = lib.connect_ro()
    try:
        status, problems = lib.classify(con, plan)
        problems = list(plan.problems) + lib.overlap_problems(con, gap, plan) + problems
        fred = gap.load_fred(gap.RAW / "fred-DJIA.csv")
        yahoo = gap.load_yahoo_dji(gap.RAW / "yahoo-DJI-chart.json")
        sina = gap.load_sina_dji(gap.RAW / "sina-DJI-daily.json")
        cnbc_dj = gap.load_cnbc(gap.RAW / "cnbc-dji", ".DJI", "Dow Jones Industrial Average")
        cnbc_dw = gap.load_cnbc(gap.RAW / "cnbc-dwrtf", ".DWRTF", "DJUSslct REIT")
        tv = gap.load_csv_closes(gap.PRIOR_TV)
        djia_db = _db_map(con, "DJIA", *lib.DJIA_FULL)
        dw_db = _db_map(con, "DWRTF", *lib.DWRTF_FULL)
        facts = {code: lib._series_facts(con, code) for code in ("DJIA", "DWRTF")}
    finally:
        con.close()

    adopted = {bar.date: bar for bar in plan.dwrtf}
    djia_days = plan.djia_full
    dw_days = plan.dwrtf_full
    djia_new = [bar.date for bar in plan.djia]
    dw_new = [bar.date for bar in plan.dwrtf]
    djia_months = lib.month_ends(djia_days)
    dw_months = lib.month_ends(dw_days)
    djia_sample = lib.sample_dates(djia_new, ["2024-02-02", "2024-12-24", "2024-12-26", "2026-09-30"])
    dw_sample = lib.sample_dates(
        dw_new,
        ["2017-11-24", lib.CONFLICT_DAY, lib.SINGLE_DAY, "2024-12-24", "2024-12-26", "2026-09-30"],
    )
    out = lib.EVIDENCE
    _write_csv(out / "monthend-djia.csv", DJIA_HEADER, [
        _djia_row(day, fred, cnbc_dj, yahoo, sina, djia_db) for day in djia_months
    ])
    _write_csv(out / "monthend-dwrtf.csv", DWRTF_HEADER, [
        _dw_row(day, cnbc_dw, tv, dw_db, adopted) for day in dw_months
    ])
    _write_csv(out / "sample-djia.csv", DJIA_HEADER, [
        _djia_row(day, fred, cnbc_dj, yahoo, sina, djia_db) for day in djia_sample
    ])
    _write_csv(out / "sample-dwrtf.csv", DWRTF_HEADER, [
        _dw_row(day, cnbc_dw, tv, dw_db, adopted) for day in dw_sample
    ])
    pseudo_rows = []
    for series, cnbc, db in (
        ("DJIA", cnbc_dj, djia_db),
        ("DWRTF", cnbc_dw, dw_db),
    ):
        for day in ("2024-12-24", lib.PSEUDO, "2024-12-26"):
            db_close, db_source = db.get(day, ("", ""))
            pseudo_rows.append([
                series,
                day,
                "yes" if gap.is_session(day) else "no",
                cnbc.get(day, ""),
                "yes" if (series == "DJIA" and day in djia_new) or (series == "DWRTF" and day in dw_new) else "no",
                db_close,
                db_source,
            ])
    _write_csv(
        out / "pseudo-session-2024-12-25.csv",
        ["series", "date", "is_session", "cnbc_close", "authorized_insert", "db_close", "db_source"],
        pseudo_rows,
    )
    report = {
        "status": status,
        "problems": problems,
        "counts": plan.counts,
        "owner_counts": lib.OWNER_COUNTS,
        "series": facts,
        "monthend_djia": len(djia_months),
        "monthend_dwrtf": len(dw_months),
        "sample_djia": djia_sample,
        "sample_dwrtf": dw_sample,
        "flags": plan.flags,
        "pseudo_session_excluded": lib.PSEUDO,
        "level_gap_is_not_a_return": True,
    }
    (out / "read-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": status,
        "problems": problems,
        "monthend_djia": len(djia_months),
        "monthend_dwrtf": len(dw_months),
        "sample_djia": len(djia_sample),
        "sample_dwrtf": len(dw_sample),
        "series_last": {code: facts[code]["last"] for code in facts},
    }, ensure_ascii=False, indent=2))
    return 2 if problems or status == "partial" else 0


if __name__ == "__main__":
    raise SystemExit(main())
