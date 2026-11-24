"""Append the authorized DJIA and DWRTF raw closes.

    python3 -I scripts/v6_us_raw_index_ingest.py
    python3 -I scripts/v6_us_raw_index_ingest.py --apply

The default is a read-only check. --apply copies a byte backup, then inserts
only the authorized new dates. Existing rows are not updated or deleted.
No returns are calculated.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


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

TAIPEI = ZoneInfo("Asia/Taipei")
LEDGER = lib.ROOT / "results" / "inventory" / "db-writes.txt"


def _die(problems: list[str]) -> None:
    for item in problems:
        print(f"STOP {item}", file=sys.stderr)
    raise SystemExit(2)


def _check(con: sqlite3.Connection, gap, plan: lib.SourcePlan) -> tuple[str, list[str]]:
    problems = list(plan.problems)
    problems.extend(lib.overlap_problems(con, gap, plan))
    status, more = lib.classify(con, plan)
    problems.extend(more)
    return status, problems


def check() -> dict:
    gap = lib.load_gap()
    plan = lib.build_source_plan(gap)
    con = lib.connect_ro()
    try:
        status, problems = _check(con, gap, plan)
        djia = lib._series_facts(con, "DJIA")
        dwrtf = lib._series_facts(con, "DWRTF")
        total = con.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
    finally:
        con.close()
    report = {
        "status": status,
        "problems": problems,
        "counts": plan.counts,
        "owner_counts": lib.OWNER_COUNTS,
        "djia_rows": djia["rows"],
        "dwrtf_rows": dwrtf["rows"],
        "bars": total,
        "flags": plan.flags,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if problems or status == "partial":
        _die(problems or ["partial insert"])
    return report


def _backup(pre_hash: str) -> None:
    lib.EVIDENCE.mkdir(parents=True, exist_ok=True)
    if lib.BACKUP_PATH.exists():
        got = lib.sha256_file(lib.BACKUP_PATH)
        if got != pre_hash:
            _die([
                f"backup {lib.BACKUP_PATH} sha256 {got} != live preimage {pre_hash}; not overwriting",
            ])
        return
    shutil.copy2(lib.DB_PATH, lib.BACKUP_PATH)
    got = lib.sha256_file(lib.BACKUP_PATH)
    if got != pre_hash:
        lib.BACKUP_PATH.unlink()
        _die([f"backup copy sha256 {got} != live preimage {pre_hash}"])
    backup = lib.connect_ro(lib.BACKUP_PATH)
    try:
        integrity = backup.execute("PRAGMA integrity_check").fetchone()[0]
        last_djia = backup.execute("SELECT MAX(date) FROM bars WHERE code = 'DJIA'").fetchone()[0]
        last_dw = backup.execute("SELECT MAX(date) FROM bars WHERE code = 'DWRTF'").fetchone()[0]
    finally:
        backup.close()
    if integrity != "ok" or last_djia != "2024-02-01" or last_dw != "2017-11-22":
        _die([f"backup integrity {integrity} DJIA {last_djia} DWRTF {last_dw}"])


def _append_ledger(before: str, after: str) -> None:
    text = LEDGER.read_bytes()
    prefix = b"" if text.endswith(b"\n") or not text else b"\n"
    line = (
        f"SHA256 BEFORE {lib.LABEL} {before}\n"
        f"SHA256 AFTER  {lib.LABEL} {after}\n"
    )
    with LEDGER.open("ab") as handle:
        handle.write(prefix + line.encode())


def _write_text(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def apply() -> None:
    report = check()
    if report["status"] != "absent":
        _die([f"refusing to write; database status is {report['status']}"])
    pre_hash = lib.sha256_file(lib.DB_PATH)
    inputs = lib.file_manifest(lib.UNCHANGED_ROOTS)
    _backup(pre_hash)
    gap = lib.load_gap()
    plan = lib.build_source_plan(gap)
    if plan.problems:
        _die(plan.problems)
    fetched_at = datetime.now(TAIPEI).isoformat(timespec="seconds")
    payload = [
        (bar.code, bar.date, bar.close, bar.source, fetched_at)
        for bar in plan.bars
    ]
    if any(row[1] == lib.PSEUDO or row[1] < "2017-11-24" or row[1] > "2026-09-30" for row in payload):
        _die(["insert payload left the authorized window"])
    if any(row[0] == "DJIA" and row[1] < lib.DJIA_NEW[0] for row in payload):
        _die(["DJIA payload includes the existing boundary or an earlier date"])

    con = sqlite3.connect(lib.DB_PATH)
    con.isolation_level = None
    try:
        con.execute("BEGIN IMMEDIATE")
        try:
            trigger_row = con.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = 'bars_one_source'"
            ).fetchone()
            if trigger_row is None:
                raise RuntimeError("bars_one_source trigger is missing")
            trigger_sql = trigger_row[0]
            before_schema = lib.schema_snapshot(con)
            before_rows = con.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
            before_counts = {
                code: lib._series_facts(con, code) for code in ("DJIA", "DWRTF")
            }
            other_before, other_before_n = lib.count_fingerprint(con, {"DJIA", "DWRTF"})
            pre_fp, pre_n = lib.fingerprint_rows(con)
            if pre_n != before_rows:
                raise RuntimeError(f"fingerprint count {pre_n} != bars {before_rows}")
            con.execute("DROP TRIGGER bars_one_source")
            con.executemany(lib.INSERT_SQL, payload)
            con.execute(trigger_sql)
            after_schema = lib.schema_snapshot(con)
            if after_schema != before_schema:
                raise RuntimeError("sqlite_master changed beyond the authorized inserts")
            exclude = {(bar.code, "raw", bar.date) for bar in plan.bars}
            post_fp, post_n = lib.fingerprint_rows(con, exclude)
            if post_fp != pre_fp or post_n != pre_n:
                raise RuntimeError(
                    f"pre-existing rows changed fingerprint {pre_fp} n={pre_n} -> {post_fp} n={post_n}"
                )
            other_after, other_after_n = lib.count_fingerprint(con, {"DJIA", "DWRTF"})
            if other_after != other_before or other_after_n != other_before_n:
                raise RuntimeError("a series other than DJIA/DWRTF changed its row count")
            problems = lib.post_problems(con, plan)
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
            if problems or integrity != "ok":
                raise RuntimeError(f"integrity {integrity}; {problems}")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        journal = con.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        con.close()

    leftovers = [
        lib.DB_PATH.with_name(suffix)
        for suffix in (
            "market.sqlite-wal",
            "market.sqlite-shm",
            "market.sqlite-journal",
        )
    ]
    hot = [str(path) for path in leftovers if path.exists()]
    if hot or journal != "delete":
        _die([f"journal {journal} leftover {hot}"])
    post_hash = lib.sha256_file(lib.DB_PATH)
    if post_hash == pre_hash:
        _die(["database file hash did not change after the insert"])
    if lib.file_manifest(lib.UNCHANGED_ROOTS) != inputs:
        _die(["an input archive, config file, or universe roster changed during ingest"])

    con = lib.connect_ro()
    try:
        after = {code: lib._series_facts(con, code) for code in ("DJIA", "DWRTF")}
        bars_after = con.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
        by_source = con.execute(
            "SELECT code, source, COUNT(*), MIN(date), MAX(date) FROM bars "
            "WHERE source IN (?, ?, ?) GROUP BY code, source ORDER BY code, source",
            lib.NEW_SOURCES,
        ).fetchall()
    finally:
        con.close()

    evidence = {
        "label": lib.LABEL,
        "authorization": lib.OWNER,
        "base_commit": lib.BASE_COMMIT,
        "fetched_at": fetched_at,
        "sha256_before": pre_hash,
        "sha256_after": post_hash,
        "bars_before": before_rows,
        "bars_after": bars_after,
        "inserted": len(payload),
        "preexisting_row_sha256": pre_fp,
        "preexisting_row_count": pre_n,
        "other_series_count_sha256": other_before,
        "other_series_rows": other_before_n,
        "journal_mode": journal,
        "trigger": (
            "bars_one_source was dropped and recreated with the same SQL inside "
            "the write transaction so the authorized source labels could be appended. "
            "sqlite_master after the recreate matches the pre-insert snapshot."
        ),
        "series": {},
        "inserted_by_source": [
            {"code": code, "source": source, "rows": count, "first": first, "last": last}
            for code, source, count, first, last in by_source
        ],
        "flags": plan.flags,
        "counts": plan.counts,
        "owner_counts": lib.OWNER_COUNTS,
        "backup": {
            "path": str(lib.BACKUP_PATH.relative_to(lib.ROOT)),
            "sha256": pre_hash,
            "bytes": lib.BACKUP_PATH.stat().st_size,
            "method": "byte copy of the quiescent database before the write",
            "gitignored": True,
            "lfs_oid_at_base": pre_hash,
        },
    }
    for code in ("DJIA", "DWRTF"):
        evidence["series"][code] = {
            "before_rows": before_counts[code]["rows"],
            "after_rows": after[code]["rows"],
            "inserted": after[code]["rows"] - before_counts[code]["rows"],
            "before_first": before_counts[code]["first"],
            "before_last": before_counts[code]["last"],
            "after_first": after[code]["first"],
            "after_last": after[code]["last"],
        }
    lib.EVIDENCE.mkdir(parents=True, exist_ok=True)
    _write_text(
        lib.EVIDENCE / "ingest.json",
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
    )
    _write_text(
        lib.EVIDENCE / "db-sha256.txt",
        f"SHA256 BEFORE {lib.LABEL} {pre_hash}\nSHA256 AFTER  {lib.LABEL} {post_hash}\n",
    )
    _write_text(
        lib.EVIDENCE / "backup.txt",
        "\n".join([
            f"path: {lib.BACKUP_PATH.relative_to(lib.ROOT)}",
            "method: byte copy of the quiescent database before any write",
            f"bytes: {lib.BACKUP_PATH.stat().st_size}",
            f"sha256: {pre_hash}",
            f"matches_live_preimage: yes",
            f"base_commit: {lib.BASE_COMMIT}",
            f"base_lfs_oid: {pre_hash}",
            "gitignored: yes (*.sqlite, except data/market.sqlite)",
            "reproduction: the preimage is the Git LFS object of data/market.sqlite at the base commit",
            f"post_sha256: {post_hash}",
            "",
        ]),
    )
    flag_lines = ["series,date,flag,adopted_source,adopted_close,reference_publisher,reference_close,level_gap_over_reference,cause"]
    for item in plan.flags:
        flag_lines.append(",".join([
            item["series"],
            item["date"],
            item["flag"],
            item["adopted_source"],
            item["adopted_close"],
            item["reference_publisher"].replace(",", " "),
            item["reference_close"],
            item["level_gap_over_reference"],
            item["cause"],
        ]))
    _write_text(lib.EVIDENCE / "date-flags.csv", "\n".join(flag_lines) + "\n")
    _write_text(
        lib.EVIDENCE / "unchanged-inputs.sha256",
        "".join(f"{digest}  {rel}\n" for digest, rel in inputs),
    )
    _append_ledger(pre_hash, post_hash)
    print(json.dumps({
        "applied": True,
        "sha256_before": pre_hash,
        "sha256_after": post_hash,
        "inserted": len(payload),
        "series": evidence["series"],
        "by_source": evidence["inserted_by_source"],
        "fetched_at": fetched_at,
    }, ensure_ascii=False, indent=2))


def main() -> None:
    if "--apply" in sys.argv[1:]:
        apply()
    else:
        check()


if __name__ == "__main__":
    main()
