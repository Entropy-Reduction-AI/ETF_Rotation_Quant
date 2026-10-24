"""写入 market.sqlite。已有序列只补缺日；来源不同则整条不动。"""
from __future__ import annotations

from pathlib import Path

from src.data import db as DB
from src.data import fund_nav
from src.data import hashlog
from src.data import store as bars

INSTRUMENT = """
CREATE TABLE IF NOT EXISTS v3_instrument (
    container_id TEXT NOT NULL,
    role         TEXT NOT NULL,
    code         TEXT NOT NULL,
    name         TEXT NOT NULL DEFAULT '',
    return_basis TEXT NOT NULL DEFAULT '',
    publish_date TEXT NOT NULL DEFAULT '',
    base_date    TEXT NOT NULL DEFAULT '',
    list_date    TEXT NOT NULL DEFAULT '',
    source       TEXT NOT NULL DEFAULT '',
    source_url   TEXT NOT NULL DEFAULT '',
    series_status TEXT NOT NULL DEFAULT '',
    note         TEXT NOT NULL DEFAULT '',
    run_id       INTEGER,
    fetched_at   TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (container_id, role, code)
)
"""


def connect(path: Path = DB.MARKET_DB):
    con = DB.connect(path)
    con.execute(INSTRUMENT)
    con.commit()
    return con


def ledger(path: Path) -> hashlog.HashLedger:
    return hashlog.HashLedger(path)


def write_series(con, code: str, route: str, rows: list[dict], fetched_at: str) -> dict:
    """新代码整段写入。已有同一来源只插入没有的日期。另一来源拒绝拼接。"""
    adj = bars.adj_of(route)
    span = bars.span(con, code, adj)
    if span["rows"] and span["source"] != route:
        return {"code": code, "route": route, "status": "skipped_other_source",
                "existing_source": span["source"], "rows": span["rows"]}
    if not rows:
        return {"code": code, "route": route, "status": "empty", "rows": span["rows"]}
    if not span["rows"]:
        bars.replace(con, code, route, rows, fetched_at)
        return {"code": code, "route": route, "status": "fetched", "added": len(rows)}
    have = {r[0] for r in con.execute("SELECT date FROM bars WHERE code = ? AND adj = ?", (code, adj))}
    fresh = [r for r in rows if r["date"] not in have]
    if not fresh:
        return {"code": code, "route": route, "status": "reused", "rows": span["rows"]}
    bars.upsert(con, code, route, fresh, fetched_at)
    return {"code": code, "route": route, "status": "appended", "added": len(fresh), "rows": span["rows"]}


def ensure_nav(con) -> None:
    fund_nav.ensure(con)


def write_instruments(con, run_id: int, rows: list[dict], fetched_at: str) -> None:
    with con:
        con.executemany(
            """INSERT INTO v3_instrument
               (container_id, role, code, name, return_basis, publish_date, base_date, list_date,
                source, source_url, series_status, note, run_id, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(container_id, role, code) DO UPDATE SET
                 name = excluded.name,
                 return_basis = excluded.return_basis,
                 publish_date = excluded.publish_date,
                 base_date = excluded.base_date,
                 list_date = excluded.list_date,
                 source = excluded.source,
                 source_url = excluded.source_url,
                 series_status = excluded.series_status,
                 note = excluded.note,
                 run_id = excluded.run_id,
                 fetched_at = excluded.fetched_at""",
            [(r["container_id"], r["role"], r["code"], r.get("name") or "", r.get("return_basis") or "",
              r.get("publish_date") or "", r.get("base_date") or "", r.get("list_date") or "",
              r.get("source") or "", r.get("source_url") or "", r.get("series_status") or "",
              r.get("note") or "", run_id, fetched_at) for r in rows])
