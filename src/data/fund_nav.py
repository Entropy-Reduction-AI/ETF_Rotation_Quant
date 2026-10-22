"""东财 f10/lsjz 历史净值 → fund_nav。

接口与 operations/reviews/diag/qdii/fetch.py 相同：pageSize 最大 20，要带 Referer。
只存接口给出的日期，不插值、不把份额折算日的净值改平。
"""
from __future__ import annotations

import time
from pathlib import Path

from . import db as DB
from . import http
from . import universe as U
from .hashlog import HashLedger

# 任务给定的最低集合。universe 里 qdii_or_lof 的执行基金都要，这 7 只即使漏标也要拉。
REQUIRED = ("513100", "159941", "513300", "513500", "159612", "513650", "159509")
SOURCE = "eastmoney_f10_lsjz"
PAGE_SIZE = 20
URL = "https://api.fund.eastmoney.com/f10/lsjz"
REFERER = "https://fundf10.eastmoney.com/"
PAUSE = 0.05

_TABLE = """
CREATE TABLE IF NOT EXISTS fund_nav (
  code TEXT,
  date TEXT,
  unit_nav REAL,
  accum_nav REAL,
  subscribe_status TEXT,
  redeem_status TEXT,
  source TEXT,
  run_id INTEGER,
  fetched_at TEXT,
  PRIMARY KEY(code, date)
)
"""


def ensure(con) -> None:
    con.execute(_TABLE)


def nav_codes(rows: list[dict] | None = None) -> list[str]:
    """QDII/LOF 执行基金，再加上 REQUIRED 里尚未出现的代码。"""
    out = U.qdii_lof_codes(rows)
    for code in REQUIRED:
        if code not in out:
            out.append(code)
    return out


def _num(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def _text(value) -> str | None:
    if value is None:
        return None
    return str(value)


def parse_lsjz_row(code: str, item: dict) -> dict | None:
    day = item.get("FSRQ")
    if not day:
        return None
    return {
        "code": code,
        "date": str(day),
        "unit_nav": _num(item.get("DWJZ")),
        "accum_nav": _num(item.get("LJJZ")),
        "subscribe_status": _text(item.get("SGZT")),
        "redeem_status": _text(item.get("SHZT")),
        "source": SOURCE,
    }


def _page(code: str, page: int) -> dict:
    payload = http.get_json(URL, {"fundCode": code, "pageIndex": page, "pageSize": PAGE_SIZE},
                            headers={"Referer": REFERER}, timeout=30)
    if not isinstance(payload, dict) or payload.get("ErrCode") not in (0, "0", None):
        raise http.FetchError(f"eastmoney lsjz {code} page {page}: {str(payload)[:160]}")
    return payload


def fetch_code(code: str, *, pause: float = PAUSE) -> list[dict]:
    """翻完全部分页。同一日期以先到的那一页为准，后面的重复行丢掉。"""
    first = _page(code, 1)
    total = int(first.get("TotalCount") or 0)
    if total <= 0:
        return []
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    by_date: dict[str, dict] = {}
    raw = 0

    def take(payload: dict, page: int) -> None:
        nonlocal raw
        batch = ((payload.get("Data") or {}).get("LSJZList")) or []
        if not batch:
            raise http.FetchError(f"eastmoney lsjz {code} page {page}: 空页，TotalCount={total}")
        raw_here = 0
        for item in batch:
            raw_here += 1
            parsed = parse_lsjz_row(code, item)
            if parsed is None:
                continue
            by_date.setdefault(parsed["date"], parsed)
        raw += raw_here

    take(first, 1)
    for page in range(2, pages + 1):
        time.sleep(pause)
        take(_page(code, page), page)
    if raw < total or not by_date:
        raise http.FetchError(f"eastmoney lsjz {code}: 收到 {raw} 行、去重 {len(by_date)} 日，TotalCount={total}")
    return [by_date[day] for day in sorted(by_date)]


def store_code(con, run_id: int, rows: list[dict], fetched_at: str) -> int:
    ensure(con)
    with con:
        con.executemany(
            """INSERT OR REPLACE INTO fund_nav
               (code, date, unit_nav, accum_nav, subscribe_status, redeem_status, source, run_id, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(r["code"], r["date"], r["unit_nav"], r["accum_nav"], r["subscribe_status"], r["redeem_status"],
              r["source"], run_id, fetched_at) for r in rows])
    return len(rows)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def yearly_premium(con, code: str) -> list[dict]:
    """溢价 = 同日场内收盘 / 单位净值 − 1。这是数据质量，不是收益。"""
    buckets: dict[str, list[float]] = {}
    for day, prem in con.execute(
            """SELECT n.date, b.close / n.unit_nav - 1
                 FROM fund_nav n
                 JOIN bars b ON b.code = n.code AND b.adj = 'raw' AND b.date = n.date
                WHERE n.code = ? AND n.unit_nav > 0 AND b.close > 0""", (code,)):
        buckets.setdefault(day[:4], []).append(prem)
    out = []
    for year in sorted(buckets):
        values = buckets[year]
        out.append({
            "year": year,
            "days": len(values),
            "median": _median(values),
            "gt_3pct": sum(1 for v in values if v > 0.03) / len(values),
            "gt_10pct": sum(1 for v in values if v > 0.10) / len(values),
        })
    return out


def summarize(con) -> list[dict]:
    rows = []
    for code, n, first, last in con.execute(
            "SELECT code, count(*), min(date), max(date) FROM fund_nav GROUP BY code ORDER BY code"):
        rows.append({"code": code, "rows": n, "first": first, "last": last})
    return rows


def load(db: Path = DB.MARKET_DB, *, apply: bool = False, pause: float = PAUSE, log=print) -> dict:
    """拉取并写入。apply=False 只列出代码，不出网、不写库。"""
    codes = nav_codes()
    report: dict = {"apply": apply, "codes": codes, "funds": [], "failed": [], "hashes": [], "premium": {}}
    if not apply:
        log(f"fund_nav 将拉取 {len(codes)} 只：{', '.join(codes)}")
        return report
    http.LOG.clear()
    ledger = HashLedger(db)
    con = DB.connect(db)
    try:
        ledger.before("fund_nav start_run")
        run_id = DB.start_run(con, "backfill", args={"job": "fund_nav", "codes": codes, "source": SOURCE})
        ledger.after("fund_nav start_run")
        report["run_id"] = run_id
        for code in codes:
            try:
                rows = fetch_code(code, pause=pause)
            except http.FetchError as exc:
                report["failed"].append({"code": code, "error": str(exc)[:300]})
                log(f"  fund_nav {code}: {str(exc)[:160]}")
                continue
            ledger.before(f"fund_nav {code}")
            wrote = store_code(con, run_id, rows, DB.now())
            ledger.after(f"fund_nav {code}")
            first, last = (rows[0]["date"], rows[-1]["date"]) if rows else (None, None)
            report["funds"].append({"code": code, "rows": wrote, "first": first, "last": last})
            log(f"  fund_nav {code}: {wrote} 行 {first} → {last}")
        ledger.before("fund_nav write_requests")
        DB.write_requests(con, run_id, http.LOG)
        ledger.after("fund_nav write_requests")
        status = "ok" if not report["failed"] else "error"
        ledger.before("fund_nav finish_run")
        DB.finish_run(con, run_id, status)
        ledger.after("fund_nav finish_run")
        report["summary"] = summarize(con)
        for code in codes:
            if any(f["code"] == code for f in report["failed"]):
                continue
            report["premium"][code] = yearly_premium(con, code)
        report["integrity"] = con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()
    report["hashes"] = ledger.lines
    report["status"] = "ok" if not report["failed"] else "error"
    return report
