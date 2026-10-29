"""v4-R1e 补数：8 只后复权重试东财，520900 不复权在东财断连时改用上交所日 K。

只插入。不覆盖已有行，不算收益。bars.adj=hfq 只接受东财 fqt=2。
交易所日 K 和天天基金分红送配页都不是这条后复权，对不上就不写进 hfq。
"""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from src.data import db as DB
from src.data import http
from src.v4.data.r1c_parse import ParseError, parse_fhsp
from src.v4.data.r1e import (
    FILL_COLUMNS,
    HFQ_SOURCE,
    NAV_END,
    OUT,
    RAW_SOURCE,
    _gz,
    _kline_retry,
    _secid,
    _write_csv,
    fetch,
    summarize,
)

ROOT = Path(__file__).resolve().parents[3]
INCOMING = ROOT / "incoming" / "2026-10-29-v4-r1e-hfq-followup"
SSE_DAYK = "https://yunhq.sse.com.cn:32042/v1/sh1/dayk/{code}"
SZSE_SNAP = "https://www.szse.cn/api/report/ShowReport/data"
FHSP = "https://fundf10.eastmoney.com/fhsp_{code}.html"
QUOTE_JS = "https://quote.eastmoney.com/newstatic/build/fund2.js"
SSE_SOURCE = "sse_yunhq"

HFQ_CODES = (
    "513820", "513910", "159501", "159687", "159688", "159822", "160125", "160644",
)
RAW_CODE = "520900"

# 基金公司产品页。页面通常是净值，不是场内后复权 K 线；取不到就记下状态。
FUND_COMPANY = {
    "513820": "https://www.99fund.com/main/products/pofund/513820/index.shtml",
    "513910": "https://www.chinaamc.com/fund/513910/index.shtml",
    "159501": "https://www.jsfund.cn/main/fund/funddetail.shtml?fundcode=159501",
    "159687": "https://www.nffund.com/new/fund/index.html#/detail?fundcode=159687",
    "159688": "https://www.huaan.com.cn/funds/159688/index.shtml",
    "159822": "https://www.yhfund.com.cn/main/fund/funddetail.shtml?fundcode=159822",
    "160125": "https://www.nffund.com/new/fund/index.html#/detail?fundcode=160125",
    "160644": "https://www.phfund.com.cn/fund/160644/index.shtml",
    "520900": "https://www.gffunds.com.cn/funds/?fundcode=520900",
}


def iso_day(value) -> str:
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return text
    raise ValueError(f"认不出日期：{value}")


def parse_sse_dayk(payload: dict, end: str = NAV_END) -> list[dict]:
    """上交所 dayk：[日期, 开, 高, 低, 收, 成交量(股), 成交额(元)]。晚于 end 的丢掉。"""
    rows = []
    for item in payload.get("kline") or []:
        if not isinstance(item, (list, tuple)) or len(item) < 7:
            raise ValueError(f"上交所 K 线列数不够：{item!r}"[:160])
        day = iso_day(item[0])
        if day > end:
            continue
        open_, high, low, close = (float(item[1]), float(item[2]), float(item[3]), float(item[4]))
        if not (close > 0 and high >= low and low <= open_ <= high and low <= close <= high):
            raise ValueError(f"上交所 OHLC 不合理 {day}")
        rows.append({
            "date": day,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": float(item[5]),
            "amount": float(item[6]),
        })
    dedup = {row["date"]: row for row in rows}
    if len(dedup) != len(rows):
        raise ValueError("上交所 K 线有重复日期")
    return [dedup[day] for day in sorted(dedup)]


def failure_reason(item: dict) -> str:
    """一只后复权仍缺时写入清单的原因。必须带本轮东财错误，并说明没有写入 hfq。"""
    error = (item.get("eastmoney_error") or "").strip()
    if not error:
        raise ValueError("缺东财错误")
    parts = [f"东财 K 线 {error}"]
    for key in ("exchange_note", "fhsp_note", "company_note"):
        note = (item.get(key) or "").strip()
        if note:
            parts.append(note)
    parts.append("未写入 adj=hfq。")
    return " ".join(parts)


def _dayk(code: str, begin: int, end: int) -> dict:
    raw = fetch(
        SSE_DAYK.format(code=code),
        {"begin": str(begin), "end": str(end)},
        headers={"Referer": "https://www.sse.com.cn/"},
        timeout=20,
        retries=0,
    )
    payload = json.loads(raw)
    if not isinstance(payload, dict) or "kline" not in payload:
        raise http.FetchError(f"上交所 {code} 没有 kline")
    return payload


def _last_index_on_or_before(code: str, end: str, total: int) -> int:
    """按下标二分。超过 end 的响应不落盘，只用来把下标停在截止日。"""
    end_num = int(end.replace("-", ""))
    lo, hi = 0, total - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        rows = _dayk(code, mid, mid + 1).get("kline") or []
        if not rows:
            raise http.FetchError(f"上交所 {code} 下标 {mid} 为空")
        if int(rows[0][0]) <= end_num:
            lo = mid
        else:
            hi = mid - 1
    return lo


def fetch_sse_raw(code: str, end: str = NAV_END) -> tuple[list[dict], bytes, str]:
    head = _dayk(code, 0, 1)
    total = int(head.get("total") or 0)
    if total < 1:
        raise http.FetchError(f"上交所 {code} 没有日 K")
    last = _last_index_on_or_before(code, end, total)
    payload = _dayk(code, 0, last + 1)
    rows = parse_sse_dayk(payload, end)
    if not rows:
        raise http.FetchError(f"上交所 {code} 在 {end} 之前没有收盘")
    if any(row["date"] > end for row in rows):
        raise http.FetchError(f"上交所 {code} 滤过后仍有 {end} 之后的日期")
    if int(payload["kline"][-1][0]) > int(end.replace("-", "")):
        raise http.FetchError(f"上交所 {code} 整段请求越过了 {end}")
    kept = [item for item in payload["kline"] if iso_day(item[0]) <= end]
    blob = json.dumps({"code": code, "kline": kept}, ensure_ascii=False, separators=(",", ":")).encode()
    url = SSE_DAYK.format(code=code) + f"?begin=0&end={last + 1}"
    return rows, blob, url


def _stored_close(con, code: str, adj: str, day: str):
    row = con.execute(
        "SELECT close, source FROM bars WHERE code = ? AND adj = ? AND date = ?",
        (code, adj, day)).fetchone()
    if row is None:
        return None
    return float(row[0]), row[1]


def _series_pairs(con, code: str, adj: str) -> list[tuple]:
    return [tuple(row) for row in con.execute(
        "SELECT date, close, source FROM bars WHERE code = ? AND adj = ? ORDER BY date",
        (code, adj))]


def _covered(con, code: str, adj: str, start: str, end: str) -> bool:
    """已经覆盖到截止日的序列不再请求，也不改清单里的插入行数。"""
    rows = _series_pairs(con, code, adj)
    if not rows:
        return False
    first, last = rows[0][0], rows[-1][0]
    if last < end:
        return False
    if start and first > start:
        return False
    return True


def _try_eastmoney(code: str, fqt: int, end: str) -> dict:
    secid = _secid(code)
    kind = "hfq" if fqt == 2 else "raw"
    if not secid:
        return {"code": code, "kind": kind, "rows": None, "raw": b"", "eastmoney_error": "代码没有东财 secid"}
    try:
        rows, raw = _kline_retry(secid, fqt, end)
    except (http.FetchError, ValueError) as exc:
        return {"code": code, "kind": kind, "rows": None, "raw": b"", "eastmoney_error": str(exc)[:300]}
    return {"code": code, "kind": kind, "rows": rows, "raw": raw, "eastmoney_error": ""}


def _quote_host_note() -> str:
    try:
        raw = fetch(QUOTE_JS, headers={"Referer": "https://quote.eastmoney.com/"}, timeout=20, retries=0)
    except http.FetchError as exc:
        return f"东财行情页脚本取不到：{exc}"[:180]
    text = raw.decode("utf-8", "replace")
    INCOMING.mkdir(parents=True, exist_ok=True)
    marker = 'quote_history_api:"'
    pos = text.find(marker)
    if pos < 0:
        note = "东财行情页脚本里没有 quote_history_api。"
    else:
        snippet = text[pos:pos + 80].replace("\n", "")
        note = f"东财行情页脚本 {snippet}"
    (INCOMING / "fund2-kline-host.txt").write_text(note + "\n", encoding="utf-8")
    return note


def _fhsp_note(code: str) -> str:
    url = FHSP.format(code=code)
    try:
        raw = fetch(url, headers={"Referer": "https://fundf10.eastmoney.com/"}, timeout=25, retries=0)
    except http.FetchError as exc:
        return f"天天基金分红送配页取不到：{exc}"[:180]
    _gz(INCOMING / "fhsp" / f"{code}.html.gz", raw)
    try:
        parsed = parse_fhsp(raw.decode("utf-8", "replace"))
    except ParseError as exc:
        return f"天天基金分红送配页解析失败：{exc}"[:180]
    return (
        f"天天基金分红送配页 {url} 分红 {len(parsed['dividends'])} 次、"
        f"拆分 {len(parsed['splits'])} 次，没有场内后复权 K 线。"
    )


def _company_note(code: str) -> str:
    url = FUND_COMPANY.get(code) or ""
    if not url:
        return ""
    try:
        raw = fetch(url, timeout=15, retries=0)
    except http.FetchError as exc:
        return f"基金公司页面 {url} 取不到：{type(exc).__name__} {str(exc)[:120]}"
    text = raw.decode("utf-8", "replace")
    _gz(INCOMING / "fund-company" / f"{code}.html.gz", raw)
    if "后复权" in text and ("开盘" in text or "最高" in text):
        return f"基金公司页面 {url} 同时出现后复权与开盘字样，需人工看原件，本轮没有从中抄价。"
    return f"基金公司页面 {url} 已保存，正文没有场内后复权 K 线。"


def _sse_spot(con, code: str, end: str) -> str:
    try:
        rows, _blob, url = fetch_sse_raw(code, end)
    except (http.FetchError, ValueError) as exc:
        return f"上交所 dayk 取不到：{exc}"[:180]
    last = rows[-1]
    stored = _stored_close(con, code, "raw", last["date"])
    if stored is None:
        return f"上交所 dayk {url} 收到截止 {last['date']} 的不复权 K 线，库内没有同日 raw 可对照。"
    match = abs(stored[0] - last["close"]) < 1e-4
    if not match:
        return (
            f"上交所 dayk {last['date']} 收盘 {last['close']} 与库内 {stored[1]} 收盘 {stored[0]} 不一致，"
            "不能当作后复权。"
        )
    return (
        f"上交所 dayk 是不复权 OHLC。{last['date']} 收盘 {last['close']} 与库内 {stored[1]} 一致。"
        "成交量单位是股，成交额单位是元。没有后复权列。"
    )


def _num(value) -> float:
    return float(str(value).replace(",", ""))


def _szse_spot(con, code: str) -> str:
    params = {
        "SHOWTYPE": "JSON",
        "CATALOGID": "1815_stock_snapshot",
        "TABKEY": "tab2",
        "txtBeginDate": "2026-09-30",
        "txtEndDate": "2026-09-30",
        "txtDMorJC": code,
        "PAGENO": "1",
    }
    url = SZSE_SNAP
    try:
        raw = fetch(url, params, headers={"Referer": "https://www.szse.cn/market/trend/index.html"}, timeout=20, retries=0)
    except http.FetchError as exc:
        return f"深交所基金日行情取不到：{exc}"[:180]
    payload = json.loads(raw)
    data = (payload[0].get("data") if isinstance(payload, list) and payload else None) or []
    row = next((item for item in data if str(item.get("zqdm")) == code), None)
    if row is None:
        return f"深交所基金日行情 {url} 在 2026-09-30 没有 {code}。"
    close = _num(row["ss"])
    slim = {
        "date": row.get("jyrq"),
        "code": code,
        "open": _num(row["ks"]),
        "high": _num(row["zg"]),
        "low": _num(row["zd"]),
        "close": close,
        "volume_wan_gu": _num(row["cjgs"]),
        "amount_wan_yuan": _num(row["cjje"]),
    }
    _gz(INCOMING / "szse" / f"{code}-2026-09-30.json.gz", json.dumps(slim, ensure_ascii=False).encode())
    stored = _stored_close(con, code, "raw", "2026-09-30")
    if stored is None:
        return f"深交所 2026-09-30 今收 {close}，库内没有同日 raw。字段是开高低收，没有后复权。"
    if abs(stored[0] - close) >= 1e-3:
        return (
            f"深交所 2026-09-30 今收 {close} 与库内 {stored[1]} 收盘 {stored[0]} 不一致，不能当作后复权。"
        )
    return (
        f"深交所基金日行情 2026-09-30 今收 {close} 与库内 {stored[1]} 一致。"
        "字段是开高低收，没有后复权列。"
    )


def _exchange_note(con, code: str, end: str) -> str:
    if code.startswith("5"):
        return _sse_spot(con, code, end)
    return _szse_spot(con, code)


def _census_row(code: str) -> dict:
    with (OUT / "census.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["code"] == code:
                return row
    return {}


def _insert_eastmoney(con, item: dict, fetched_at: str, start: str, end: str) -> dict:
    kind = item["kind"]
    source = HFQ_SOURCE if kind == "hfq" else RAW_SOURCE
    digest = _gz(INCOMING / "kline" / f"{item['code']}-{kind}.json.gz", item["raw"])
    result = insert_missing(con, item["code"], kind, source, item["rows"], fetched_at, start, end)
    return {
        "code": item["code"], "kind": kind, "source": source,
        "source_url": "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        "sha256": digest, **result,
    }


def insert_missing(con, code, kind, source, rows, fetched_at, start, end) -> dict:
    from src.v4.data.r1e import insert_missing_bars
    return insert_missing_bars(con, code, kind, source, rows, fetched_at, start=start, end=end)


def _validate_against_hfq(con, code: str, rows: list[dict], list_date: str, end: str) -> None:
    if not rows:
        raise ValueError(f"{code} 没有可写的不复权")
    if rows[0]["date"] != list_date:
        raise ValueError(f"{code} 首日 {rows[0]['date']} 不是上市日 {list_date}")
    if rows[-1]["date"] != end:
        raise ValueError(f"{code} 末日 {rows[-1]['date']} 不是 {end}")
    if any(row["date"] > end for row in rows):
        raise ValueError(f"{code} 含有 {end} 之后的日期")
    hfq_days = [row[0] for row in _series_pairs(con, code, "hfq")]
    got = [row["date"] for row in rows]
    if got != hfq_days:
        missing = sorted(set(hfq_days) - set(got))[:8]
        extra = sorted(set(got) - set(hfq_days))[:8]
        raise ValueError(f"{code} 交易日与已有后复权不一致 缺 {missing} 多 {extra}")


def _apply_reports(reports: list[dict]) -> None:
    with (OUT / "fill.csv").open(encoding="utf-8", newline="") as handle:
        previous = list(csv.DictReader(handle))
    replaced = {(row["code"], row["kind"]) for row in reports}
    merged = [row for row in previous if (row.get("code"), row.get("kind")) not in replaced]
    merged.extend(reports)
    _write_csv(OUT / "fill.csv", FILL_COLUMNS, merged)

    with (OUT / "gaps.csv").open(encoding="utf-8", newline="") as handle:
        gaps = list(csv.DictReader(handle))
    written = {(row["code"], row["kind"]) for row in reports if row.get("status") == "in_db" and int(row.get("inserted") or 0) > 0}
    kept_gaps = []
    for row in gaps:
        code = row["code"]
        kind = "hfq" if "[hfq]" in row["name"] else "raw" if "[raw]" in row["name"] else ""
        if (code, kind) in written:
            continue
        fresh = next((item for item in reports if item["code"] == code and item["kind"] == kind and item.get("status") == "unfillable"), None)
        if fresh:
            row = dict(row)
            row["reason"] = fresh.get("reason") or row["reason"]
            row["source"] = fresh.get("source_url") or row["source"]
        kept_gaps.append(row)
    _write_csv(OUT / "gaps.csv", ("code", "name", "reason", "source"), kept_gaps)


def _rewrite_summary(con) -> dict:
    with (OUT / "census.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with (OUT / "diff.csv").open(encoding="utf-8", newline="") as handle:
        diff_rows = list(csv.DictReader(handle))
    with (OUT / "fill.csv").open(encoding="utf-8", newline="") as handle:
        fill_rows = list(csv.DictReader(handle))
    summary = summarize(rows, diff_rows, fill_rows)
    summary["integrity"] = con.execute("PRAGMA integrity_check").fetchone()[0]
    summary["sha256"] = DB.sha256_file(DB.MARKET_DB)
    summary["bytes"] = DB.MARKET_DB.stat().st_size
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def run() -> dict:
    con = DB.connect(DB.MARKET_DB)
    reports: list[dict] = []
    evidence: list[dict] = []
    try:
        INCOMING.mkdir(parents=True, exist_ok=True)
        fetched_at = DB.now()
        run_id = DB.start_run(con, "backfill", end=date.fromisoformat(NAV_END), args={
            "job": "v4-r1e-hfq-followup",
            "portfolio_returns": False,
            "overwrites_existing_rows": False,
            "nav_end": NAV_END,
        })
        guards = {
            (code, adj): _series_pairs(con, code, adj)
            for code in (*HFQ_CODES, RAW_CODE)
            for adj in ("hfq", "raw")
        }
        host_note = _quote_host_note()
        print(host_note, flush=True)
        pending = [(code, 2, "hfq") for code in HFQ_CODES] + [(RAW_CODE, 0, "raw")]
        pulled = []
        for code, fqt, _kind in pending:
            item = _try_eastmoney(code, fqt, NAV_END)
            pulled.append(item)
            print(f"eastmoney {code} {_kind_label(fqt)} {'OK' if item['rows'] else 'FAIL'}", flush=True)
        for item in pulled:
            meta = _census_row(item["code"])
            start = meta.get("list_date") or ""
            end = NAV_END
            if _covered(con, item["code"], item["kind"], start, end):
                print(f"skip {item['code']} {item['kind']} already covered", flush=True)
                continue
            if item["rows"]:
                reports.append(_insert_eastmoney(con, item, fetched_at, start, end))
                evidence.append({"code": item["code"], "kind": item["kind"], "written": "eastmoney"})
                continue
            if item["kind"] == "raw" and item["code"] == RAW_CODE:
                reports.append(_fill_sse_raw(con, item, fetched_at, start, end))
                evidence.append({"code": item["code"], "kind": "raw", "written": reports[-1]["status"]})
                continue
            note = {
                "code": item["code"],
                "kind": "hfq",
                "eastmoney_error": item["eastmoney_error"],
                "exchange_note": _exchange_note(con, item["code"], end),
                "fhsp_note": _fhsp_note(item["code"]),
                "company_note": _company_note(item["code"]),
            }
            reason = failure_reason(note)
            evidence.append({**note, "written": False, "reason": reason})
            reports.append({
                "code": item["code"], "kind": "hfq", "status": "unfillable", "inserted": 0,
                "kept": 0, "first": "", "last": "", "source": HFQ_SOURCE,
                "source_url": "https://push2his.eastmoney.com/api/qt/stock/kline/get",
                "sha256": "", "reason": reason,
            })
            print(f"still missing {item['code']} hfq", flush=True)
        inserted = {
            (row["code"], row["kind"])
            for row in reports
            if int(row.get("inserted") or 0) > 0
        }
        for (code, adj), before in guards.items():
            after = _series_pairs(con, code, adj)
            if set(before) - set(after):
                raise RuntimeError(f"{code} {adj} 已有行情被改动")
            if (code, adj) not in inserted and before != after:
                raise RuntimeError(f"{code} {adj} 不应变化")
        _apply_reports(reports)
        DB.write_requests(con, run_id, http.LOG)
        DB.finish_run(con, run_id, "ok")
        summary = _rewrite_summary(con)
    except Exception:
        con.close()
        raise
    else:
        con.close()
    for suffix in ("-wal", "-shm"):
        leftover = Path(str(DB.MARKET_DB) + suffix)
        if leftover.exists():
            raise RuntimeError(f"库文件旁还有 {leftover.name}")
    (INCOMING / "attempts.json").write_text(
        json.dumps({"host": host_note, "items": evidence, "reports": reports}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(json.dumps({
        "integrity": summary.get("integrity"),
        "sha256": summary.get("sha256"),
        "bytes": summary.get("bytes"),
        "inserted_rows": summary.get("inserted_rows"),
        "unfillable": summary.get("unfillable"),
    }, ensure_ascii=False, indent=2))
    return summary


def _kind_label(fqt: int) -> str:
    return "hfq" if fqt == 2 else "raw"


def _fill_sse_raw(con, item: dict, fetched_at: str, start: str, end: str) -> dict:
    code = item["code"]
    try:
        rows, blob, url = fetch_sse_raw(code, end)
        _validate_against_hfq(con, code, rows, start, end)
    except (http.FetchError, ValueError) as exc:
        return {
            "code": code, "kind": "raw", "status": "unfillable", "inserted": 0,
            "kept": 0, "first": "", "last": "", "source": SSE_SOURCE, "source_url": SSE_DAYK.format(code=code),
            "sha256": "", "reason": f"东财不复权 {item['eastmoney_error']} 上交所日 K 未写入：{exc}"[:500],
        }
    digest = _gz(INCOMING / "sse" / f"{code}-raw.json.gz", blob)
    result = insert_missing(con, code, "raw", SSE_SOURCE, rows, fetched_at, start, end)
    print(f"sse raw {code} {result['status']} +{result['inserted']}", flush=True)
    return {
        "code": code, "kind": "raw", "source": SSE_SOURCE, "source_url": url, "sha256": digest,
        **result,
        "reason": "东财不复权断连。上交所 dayk 不复权，成交量单位股，成交额单位元。只插入，未改后复权。",
    }
