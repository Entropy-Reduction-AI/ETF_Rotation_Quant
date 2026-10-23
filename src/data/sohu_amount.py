"""用搜狐历史行情补 bars.amount。

只填已有 raw 行的成交额，不改开高低收、不新增日期、不改 source。
hq[8] 按万元理解，入库为人民币元（×10000），与东财成交额的「元」对齐。
同一来源连续失败两次就停，不再改用别的来源把剩下的填满。
"""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

from . import db as DB
from . import http
from . import store
from . import universe as U
from .hashlog import HashLedger

URL = "https://q.stock.sohu.com/hisHq"
WAN_TO_YUAN = 10000.0
PAUSE = 0.2


def parse_sohu(payload, code: str) -> dict[str, float]:
    """日期 → 成交额（元）。status 不是 0，或正文不是行情数组，算这次失败。"""
    if isinstance(payload, (bytes, str)):
        text = payload.decode("gbk", "replace") if isinstance(payload, bytes) else payload
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise http.FetchError(f"sohu {code}: 不是 JSON") from exc
    if not isinstance(payload, list) or not payload:
        raise http.FetchError(f"sohu {code}: 空响应")
    node = None
    for item in payload:
        if isinstance(item, dict) and item.get("code") in (f"cn_{code}", code):
            node = item
            break
    if node is None:
        node = payload[0] if isinstance(payload[0], dict) else None
    if not isinstance(node, dict) or node.get("status") not in (0, "0"):
        status = None if not isinstance(node, dict) else node.get("status")
        raise http.FetchError(f"sohu {code}: status={status}")
    out: dict[str, float] = {}
    for row in node.get("hq") or []:
        if not isinstance(row, (list, tuple)) or len(row) < 9 or not row[0]:
            continue
        try:
            amount = float(row[8])
        except (TypeError, ValueError):
            continue
        if amount != amount:
            continue
        out.setdefault(str(row[0]), amount * WAN_TO_YUAN)
    return out


def fetch_code(code: str, start: date, end: date) -> dict[str, float]:
    raw = http.get(URL, {
        "code": f"cn_{code}", "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"),
        "stat": "1", "order": "D", "period": "d",
    }, timeout=60)
    return parse_sohu(raw, code)


def apply_amounts(con, code: str, amounts: dict[str, float]) -> dict:
    """只改 amount 仍为空或数值不同的行。价格、来源、fetched_at 保持原样。"""
    rows = list(con.execute(
        """SELECT date, open, high, low, close, volume, amount, source, fetched_at
             FROM bars WHERE code = ? AND adj = 'raw' ORDER BY date""", (code,)))
    if not rows:
        return {"code": code, "bars": 0, "updated": 0, "matched": 0}
    sources = {row["source"] for row in rows}
    if sources != {"tencent_etf"}:
        return {"code": code, "bars": len(rows), "updated": 0, "matched": 0,
                "skipped": f"来源不是 tencent_etf：{sorted(sources)}"}
    payload = []
    matched = 0
    for row in rows:
        amount = amounts.get(row["date"])
        if amount is None:
            continue
        matched += 1
        if row["amount"] is not None and abs(row["amount"] - amount) < 0.5:
            continue
        payload.append((code, "raw", row["date"], row["open"], row["high"], row["low"], row["close"],
                        row["volume"], amount, row["source"], row["fetched_at"]))
    if payload:
        with con:
            con.executemany(
                """INSERT OR REPLACE INTO bars
                   (code, adj, date, open, high, low, close, volume, amount, source, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", payload)
    return {"code": code, "bars": len(rows), "updated": len(payload), "matched": matched,
            "close_unchanged": True}


def fill(db: Path = DB.MARKET_DB, *, codes: list[str] | None = None, apply: bool = False,
         pause: float = PAUSE, log=print) -> dict:
    """88 只执行基金逐只试搜狐。连续两只失败就停，已写入的留下。"""
    codes = list(codes) if codes is not None else U.execution_fund_codes()
    report: dict = {"apply": apply, "codes": len(codes), "funds": [], "failures": [], "stopped": None, "hashes": []}
    if not apply:
        log(f"将试搜狐成交额 {len(codes)} 只。未出网、未写库。")
        return report
    http.LOG.clear()
    ledger = HashLedger(db)
    con = DB.connect(db)
    streak = 0
    try:
        ledger.before("sohu_amount start_run")
        run_id = DB.start_run(con, "update", args={"job": "sohu_amount", "codes": len(codes), "unit": "yuan=hq8*10000"})
        ledger.after("sohu_amount start_run")
        report["run_id"] = run_id
        for index, code in enumerate(codes):
            span = store.span(con, code, "raw")
            if not span["rows"] or not span["first"]:
                report["funds"].append({"code": code, "bars": 0, "updated": 0, "skipped": "没有 raw 行情"})
                log(f"  sohu {code}: 没有 raw 行情，跳过")
                continue
            try:
                amounts = fetch_code(code, date.fromisoformat(span["first"]), date.fromisoformat(span["last"]))
            except http.FetchError as exc:
                streak += 1
                report["failures"].append({"code": code, "error": str(exc)[:300]})
                log(f"  sohu {code}: {str(exc)[:160]}")
                if streak >= 2:
                    report["stopped"] = f"搜狐连续失败两次（{report['failures'][-2]['code']}、{code}），停止。不换别的来源。"
                    log("  " + report["stopped"])
                    break
                continue
            streak = 0
            ledger.before(f"sohu_amount {code}")
            detail = apply_amounts(con, code, amounts)
            ledger.after(f"sohu_amount {code}")
            detail["sohu_rows"] = len(amounts)
            report["funds"].append(detail)
            log(f"  sohu {code}: 行情 {detail['sohu_rows']} 行，对上 {detail['matched']} 天，写入额 {detail['updated']} 天")
            if pause and index + 1 < len(codes) and report["stopped"] is None:
                time.sleep(pause)
        ledger.before("sohu_amount write_requests")
        DB.write_requests(con, run_id, http.LOG)
        ledger.after("sohu_amount write_requests")
        status = "ok" if report["stopped"] is None and not report["failures"] else "partial"
        ledger.before("sohu_amount finish_run")
        DB.finish_run(con, run_id, status)
        ledger.after("sohu_amount finish_run")
        report["status"] = status
        report["integrity"] = con.execute("PRAGMA integrity_check").fetchone()[0]
        filled = [f for f in report["funds"] if f.get("updated")]
        report["updated_funds"] = len(filled)
        report["updated_rows"] = sum(f.get("updated") or 0 for f in report["funds"])
    finally:
        con.close()
    report["hashes"] = ledger.lines
    return report
