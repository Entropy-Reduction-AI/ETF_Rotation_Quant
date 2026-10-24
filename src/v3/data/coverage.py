"""按登记表和库里的实际行数写 coverage.csv。不算收益。"""
from __future__ import annotations

import csv
from pathlib import Path

from src.data import store as bars

from . import universe as U

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results" / "v3" / "inventory" / "coverage.csv"

COLUMNS = [
    "container_id", "asset_class", "name", "role", "code", "return_basis",
    "publish_date", "base_date", "list_date", "db_code", "db_adj", "db_source",
    "first_date", "last_date", "rows", "amount_missing_rows", "nav_rows", "nav_first",
    "nav_last", "subscribe_rows_from_2021", "series_status", "missing_flag",
    "pre_publish_rows", "source_url", "note",
]


def _bar_stats(con, code: str) -> dict:
    if not code:
        return {"db_code": "", "db_adj": "", "db_source": "", "first_date": "", "last_date": "",
                "rows": 0, "amount_missing_rows": "", "pre_publish_rows": ""}
    found = []
    for adj in ("raw", "hfq"):
        span = bars.span(con, code, adj)
        if span["rows"]:
            missing = con.execute(
                "SELECT count(*) FROM bars WHERE code = ? AND adj = ? AND amount IS NULL",
                (code, adj)).fetchone()[0]
            found.append((span, adj, missing))
    if not found:
        return {"db_code": code, "db_adj": "", "db_source": "", "first_date": "", "last_date": "",
                "rows": 0, "amount_missing_rows": "", "pre_publish_rows": ""}
    span, adj, missing = found[0]
    return {"db_code": code, "db_adj": adj, "db_source": span["source"] or "",
            "first_date": span["first"] or "", "last_date": span["last"] or "",
            "rows": span["rows"], "amount_missing_rows": missing, "pre_publish_rows": ""}


def _nav_stats(con, code: str) -> dict:
    empty = {"nav_rows": 0, "nav_first": "", "nav_last": "", "subscribe_rows_from_2021": 0}
    if not code:
        return empty
    have = con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'fund_nav'").fetchone()
    if not have:
        return empty
    row = con.execute(
        "SELECT count(*), min(date), max(date) FROM fund_nav WHERE code = ?", (code,)).fetchone()
    sub = con.execute(
        """SELECT count(*) FROM fund_nav
            WHERE code = ? AND date >= '2021-01-01' AND subscribe_status IS NOT NULL AND subscribe_status != ''""",
        (code,)).fetchone()[0]
    return {"nav_rows": row[0] or 0, "nav_first": row[1] or "", "nav_last": row[2] or "",
            "subscribe_rows_from_2021": sub or 0}


def _flag(status: str, rows: int, role: str, nav_rows: int, basis: str) -> str:
    if status == "see_members":
        return "rule"
    if status == "partial" or (rows and status == "partial"):
        return "partial"
    if basis == "unit_nav" and status not in U.GAP_STATUS and nav_rows:
        return "ok"
    if rows and status not in U.GAP_STATUS:
        return "partial" if status == "partial" else "ok"
    return "gap"


def _pre_publish(con, code: str, adj: str, publish: str) -> str:
    if not code or not adj or not publish or publish in {"TBD", "取不到"}:
        return ""
    n = con.execute(
        "SELECT count(*) FROM bars WHERE code = ? AND adj = ? AND date < ?",
        (code, adj, publish)).fetchone()[0]
    return str(n)


def _alt_rows(con) -> list[dict]:
    have = con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'v3_instrument'").fetchone()
    if not have:
        return []
    out = []
    for item in con.execute("SELECT * FROM v3_instrument WHERE role = 'alt' ORDER BY container_id, code"):
        stats = _bar_stats(con, item["code"])
        nav = _nav_stats(con, "")
        row = {
            "container_id": item["container_id"], "asset_class": "", "name": item["name"],
            "role": "alt", "code": item["code"], "return_basis": item["return_basis"],
            "publish_date": item["publish_date"], "base_date": item["base_date"], "list_date": item["list_date"],
            **stats, **nav, "series_status": item["series_status"], "source_url": item["source_url"],
            "note": item["note"],
        }
        row["missing_flag"] = _flag(row["series_status"], row["rows"], "alt", 0, row["return_basis"])
        out.append(row)
    return out


def build_rows(con, doc: dict | None = None) -> list[dict]:
    doc = U.load() if doc is None else doc
    out = []
    for alt in _alt_rows(con):
        out.append(alt)
    for box in U.containers(doc):
        research = box["research"]
        code = research.get("series_code") or ""
        stats = _bar_stats(con, code)
        nav_code = code if research.get("return_basis") == "unit_nav" else ""
        nav = _nav_stats(con, nav_code)
        stats["pre_publish_rows"] = _pre_publish(con, stats["db_code"], stats["db_adj"], research.get("publish_date") or "")
        row = {
            "container_id": box["id"],
            "asset_class": box.get("asset_class") or "",
            "name": box.get("name") or "",
            "role": "research",
            "code": research.get("index_code") or "",
            "return_basis": research.get("return_basis") or "",
            **stats,
            **nav,
            "series_status": research.get("series_status") or "",
            "source_url": research.get("source_url") or "",
            "note": research.get("note") or "",
            "list_date": "",
            "publish_date": research.get("publish_date") or "",
            "base_date": research.get("base_date") or "",
        }
        row["missing_flag"] = _flag(row["series_status"], row["rows"], "research", row["nav_rows"], row["return_basis"])
        out.append(row)
        for ex in box.get("execution") or []:
            stats = _bar_stats(con, ex.get("code") or "")
            nav = _nav_stats(con, ex.get("code") or "")
            erow = {
                "container_id": box["id"],
                "asset_class": box.get("asset_class") or "",
                "name": ex.get("name") or "",
                "role": "execution",
                "code": ex.get("code") or "",
                "return_basis": "price",
                "publish_date": "",
                "base_date": "",
                "list_date": ex.get("list_date") or "",
                **stats,
                **nav,
                "series_status": ex.get("bars_status") or "",
                "source_url": ex.get("track_source") or "",
                "note": ex.get("note") or "",
            }
            erow["missing_flag"] = _flag(erow["series_status"], erow["rows"], "execution", erow["nav_rows"], "price")
            out.append(erow)
    return out


def write(con, path: Path = OUT, doc: dict | None = None) -> dict:
    rows = build_rows(con, doc)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for row in rows:
            w.writerow({c: row.get(c, "") for c in COLUMNS})
    research = [r for r in rows if r["role"] == "research"]
    execution = [r for r in rows if r["role"] == "execution"]
    return {
        "path": str(path),
        "rows": len(rows),
        "research": len(research),
        "research_ok": sum(1 for r in research if r["missing_flag"] == "ok"),
        "research_partial": sum(1 for r in research if r["missing_flag"] == "partial"),
        "research_gap": sum(1 for r in research if r["missing_flag"] == "gap"),
        "research_rule": sum(1 for r in research if r["missing_flag"] == "rule"),
        "execution": len(execution),
        "execution_ok": sum(1 for r in execution if r["missing_flag"] == "ok"),
        "execution_gap": sum(1 for r in execution if r["missing_flag"] == "gap"),
    }
