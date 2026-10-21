"""F-2：为 T16 追加一条 coverage，研究序列指向 518880 的 tencent_etf 不复权日线。

只 INSERT 新的 runs / coverage 行，不删除、不更新已有 coverage。已是目标口径时直接退出。
不改 bars。数据层若拒绝把这条不复权序列当研究序列，本脚本不改校验。
"""
from __future__ import annotations

import hashlib
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data import db as DB  # noqa: E402
from src.data import store  # noqa: E402

DB_PATH = ROOT / "data" / "market.sqlite"
THEME = "T16"
CODE = "518880"
ADJ = "raw"
ROUTE = "tencent_etf"
END = date(2026, 9, 30)
NOTES = "F-2：518880 不分红，不复权 = 后复权；见 docs/prereg-v1-implementation-notes.md F 节"
OHLC = ("open", "high", "low")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _missing(rows: list[dict], cols: tuple[str, ...]) -> int:
    return sum(1 for row in rows if not all((row.get(col) or 0) > 0 for col in cols))


def _max_gap_days(rows: list[dict]) -> int:
    worst = 0
    for left, right in zip(rows, rows[1:]):
        gap = (date.fromisoformat(right["date"]) - date.fromisoformat(left["date"])).days
        if gap > worst:
            worst = gap
    return worst


def _desired(base: dict, rows: list[dict]) -> dict:
    cov = {key: base[key] for key in DB.COVERAGE_COLUMNS}
    first, last = rows[0]["date"], rows[-1]["date"]
    cov.update(
        route_used=ROUTE,
        series_code=CODE,
        series_adj=ADJ,
        series_name=base.get("series_name") or "华安黄金易ETF",
        first_date=first,
        last_date=last,
        rows=str(len(rows)),
        tr_code_used="",
        price_only="False",
        error="",
        max_gap_days=str(_max_gap_days(rows)),
        price_first_date=first,
        ohlc_missing_rows=str(_missing(rows, OHLC)),
        volume_missing_rows=str(_missing(rows, ("volume",))),
        notes=NOTES,
    )
    return cov


def _same(left: dict, right: dict) -> bool:
    return all(str(left.get(key, "")) == str(right.get(key, "")) for key in DB.COVERAGE_COLUMNS if key != "checked_at")


def main() -> int:
    if not DB_PATH.is_file():
        print(f"缺 {DB_PATH}", file=sys.stderr)
        return 1
    before = sha256(DB_PATH)
    print(f"sha256_before {before}")
    con = DB.connect(DB_PATH)
    try:
        base = con.execute("SELECT * FROM coverage_latest WHERE theme_id = ?", (THEME,)).fetchone()
        if base is None:
            print("coverage_latest 没有 T16", file=sys.stderr)
            return 1
        base = {key: base[key] for key in base.keys()}
        span = store.span(con, CODE, ADJ)
        if span["rows"] == 0 or span["sources"] != 1 or span["source"] != ROUTE:
            print(
                f"拒绝写入：{CODE}/{ADJ} rows={span['rows']} sources={span['sources']} source={span['source']}，"
                f"需要单一来源 {ROUTE}",
                file=sys.stderr,
            )
            return 1
        rows = store.read(con, CODE, ADJ)
        desired = _desired(base, rows)
        old_rows = [tuple(row) for row in con.execute("SELECT * FROM coverage WHERE theme_id = ? ORDER BY run_id", (THEME,))]
        if _same(base, desired):
            print(f"T16 coverage_latest 已是 F-2 口径（run_id={base['run_id']}），不另写")
            print(f"sha256_after  {before}")
            return 0
        run_id = DB.start_run(
            con,
            "update",
            end=END,
            args={
                "f2_t16_coverage": True,
                "theme_id": THEME,
                "series": f"{CODE}/{ADJ}",
                "route": ROUTE,
                "note": "append coverage only; bars unchanged",
            },
        )
        try:
            desired["checked_at"] = DB.now()
            DB.write_coverage(con, run_id, [desired])
            DB.finish_run(con, run_id, "ok")
        except BaseException:
            DB.finish_run(con, run_id, "error")
            raise
        kept = [tuple(row) for row in con.execute(
            "SELECT * FROM coverage WHERE theme_id = ? AND run_id != ? ORDER BY run_id", (THEME, run_id)
        )]
        if kept != old_rows:
            print("旧 T16 coverage 行被改动，停止", file=sys.stderr)
            return 1
        latest = con.execute("SELECT * FROM coverage_latest WHERE theme_id = ?", (THEME,)).fetchone()
        if latest["run_id"] != run_id or latest["series_code"] != CODE or latest["notes"] != NOTES or latest["error"]:
            print("写入后 coverage_latest 与 F-2 口径不符", file=sys.stderr)
            return 1
        print(f"appended run_id={run_id} T16 {CODE}/{ADJ} {ROUTE} {desired['first_date']}→{desired['last_date']} rows={desired['rows']}")
    finally:
        con.close()
    after = sha256(DB_PATH)
    print(f"sha256_after  {after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
