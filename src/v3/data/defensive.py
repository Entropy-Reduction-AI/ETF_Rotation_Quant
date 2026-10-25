"""黄金、中债财富，以及海外休市被写成 0 的收盘。

不出组合收益。登记表仍由 emit 生成。
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from src.data import db as DB
from src.data import http
from src.data import store as bars

from . import parse
from . import store

ROOT = Path(__file__).resolve().parents[3]
INCOMING = ROOT / "incoming" / "2026-10-25-v3-defensive"
MANIFEST = INCOMING / "MANIFEST.csv"
END = date(2026, 9, 30)
SGE = "https://www.sge.com.cn"
DAILYHQ = SGE + "/graph/Dailyhq"
HISTORY = SGE + "/sjzx/mrhqsj"
BOND_QUERY = "https://indices.chinabond.com.cn/cbweb-mn/indices/singleIndexQueryResult"
BOND_PDF = "https://indices.chinabond.com.cn/cbweb-mn/indices/downloadIndexBzfa"
BOND_REFERER = "https://indices.chinabond.com.cn/cbweb-mn/indices/single_index_query?locale=zh_CN"
# 树节点 id 来自 queryTree。名称和财富代码以随后下载的编制说明为准，不靠这份注释。
BOND_IDS = (
    "2c9081e50e8767dc010e879acb220021",
    "8a8b2ca04b666362014b723482bc4f49",
    "8a8b2ca03a3feea1013a44b98fc533f5",
)
OVERSEAS = ("nasdaq", "yahoo", "tencent_hk_index", "stooq", "eia")
DAILYHQ_START = "2016-12-19"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _manifest(row: dict) -> None:
    INCOMING.mkdir(parents=True, exist_ok=True)
    cols = ["path", "sha256", "file_sha256", "bytes", "file_bytes", "url", "fetched_at", "note"]
    new = not MANIFEST.exists()
    with MANIFEST.open("a", encoding="utf-8") as handle:
        if new:
            handle.write(",".join(cols) + "\n")
        vals = []
        for col in cols:
            text = str(row.get(col, "")).replace('"', "'")
            if any(ch in text for ch in ",\n"):
                text = '"' + text + '"'
            vals.append(text)
        handle.write(",".join(vals) + "\n")


def save_bytes(rel: str, raw: bytes, *, url: str, note: str = "", compress: bool = True) -> Path:
    path = INCOMING / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(raw).hexdigest()
    stored = path
    file_raw = raw
    if compress and len(raw) > 32_768 and path.suffix != ".gz":
        stored = Path(str(path) + ".gz")
        with gzip.open(stored, "wb") as handle:
            handle.write(raw)
        file_raw = stored.read_bytes()
        rel = str(stored.relative_to(INCOMING))
    else:
        stored.write_bytes(raw)
    file_sha = hashlib.sha256(file_raw).hexdigest()
    _manifest({
        "path": rel, "sha256": digest, "file_sha256": file_sha,
        "bytes": len(raw), "file_bytes": len(file_raw), "url": url,
        "fetched_at": _now(), "note": note,
    })
    return stored


def _fetch(url: str, *, method: str = "GET", referer: str = "", timeout: int = 40) -> bytes:
    headers = {"Referer": referer} if referer else None
    if method == "POST":
        return http.post(url, b"", headers=headers, timeout=timeout)
    return http.get(url, headers=headers, timeout=timeout)


def _bond_url(index_id: str) -> str:
    return (
        f"{BOND_QUERY}?indexid={index_id}&&qxlxt=00&&ltcslx=&&zslxt=CFZS,XQJSL"
        "&&zslxt1=&&lx=1&&locale=zh_CN"
    )


def fetch_bonds(con, log: list[str], end: date = END) -> list[dict]:
    """三只财富指数。编制说明给出代码和基准日；查询结果是日频点位。"""
    written = []
    for index_id in BOND_IDS:
        url = _bond_url(index_id)
        raw = _fetch(url, method="POST", referer=BOND_REFERER, timeout=90)
        payload = json.loads(raw)
        pdf_url = f"{BOND_PDF}?id={index_id}&locale=zh_CN"
        pdf = _fetch(pdf_url, referer=BOND_REFERER, timeout=60)
        folder = INCOMING / "chinabond"
        folder.mkdir(parents=True, exist_ok=True)
        draft = folder / f"{index_id}.pdf"
        draft.write_bytes(pdf)
        text = subprocess.run(["pdftotext", "-layout", str(draft), "-"], check=True, capture_output=True).stdout
        ident = parse.parse_chinabond_method(text.decode("utf-8", "replace"))
        code = ident.get("wealth_code") or ""
        if not code:
            log.append(f"chinabond {index_id} 编制说明没有财富代码")
            continue
        save_bytes(f"chinabond/{code}.json", raw, url=url, note=ident.get("index_name") or index_id)
        save_bytes(f"chinabond/{code}.pdf", pdf, url=pdf_url, note="编制说明", compress=False)
        (folder / f"{code}.txt").write_text(text.decode("utf-8", "replace"), encoding="utf-8")
        if draft.name != f"{code}.pdf" and draft.exists():
            draft.unlink()
        rows = [row for row in parse.parse_chinabond_wealth(payload) if row["date"] <= end.isoformat()]
        result = store.write_series(con, code, "chinabond", rows, DB.now())
        log.append(f"chinabond {code} {ident.get('index_name')} {result} n={len(rows)} "
                   f"{rows[0]['date'] if rows else ''}→{rows[-1]['date'] if rows else ''}")
        written.append({**ident, "index_id": index_id, "rows": len(rows)})
    return written


def _quote_row(row: dict, day: str) -> dict:
    return {
        "date": day,
        "open": row.get("open"),
        "high": row.get("high"),
        "low": row.get("low"),
        "close": row["close"],
        "volume": row.get("volume"),
        "amount": row.get("amount"),
    }


def fetch_gold_dailyhq(con, log: list[str], end: date = END) -> dict:
    url = DAILYHQ + "?instid=Au99.99"
    raw = _fetch(url, referer=SGE + "/sjzx/mrhq", timeout=60)
    save_bytes("sge/dailyhq-Au99.99.json", raw, url=url, note="Au99.99 开盘收盘最低最高")
    rows = [row for row in parse.parse_sge_dailyhq(json.loads(raw)) if row["date"] <= end.isoformat()]
    have = {item[0] for item in con.execute("SELECT date, close FROM bars WHERE code='Au99.99' AND adj='raw'")}
    overlap = con.execute(
        "SELECT date, close FROM bars WHERE code='Au99.99' AND adj='raw' AND close>0").fetchall()
    by_day = {row["date"]: row["close"] for row in rows}
    mismatches = []
    for day, close in overlap:
        other = by_day.get(day)
        if other is None:
            continue
        if abs(float(other) - float(close)) > 0.02:
            mismatches.append({"date": day, "db": close, "dailyhq": other})
    if mismatches:
        log.append(f"sge dailyhq 与库内收盘不一致 {len(mismatches)} 天，不写入")
        return {"written": False, "mismatches": mismatches[:10], "rows": len(rows)}
    fresh = [_quote_row(row, row["date"]) for row in rows if row["date"] not in have]
    if fresh:
        result = store.write_series(con, "Au99.99", "sge_daily", fresh, DB.now())
    else:
        result = {"status": "reused", "rows": len(rows)}
    log.append(f"sge dailyhq {result} fresh={len(fresh)} span={rows[0]['date'] if rows else ''}→{rows[-1]['date'] if rows else ''}")
    return {"written": True, "fresh": len(fresh), "rows": len(rows), "mismatches": []}


def _http_bytes(url: str, referer: str) -> bytes:
    last = None
    for attempt in range(2):
        try:
            req = Request(url, headers={"User-Agent": http.UA, "Referer": referer, "Accept": "*/*"})
            with urlopen(req, timeout=40) as response:
                return response.read()
        except Exception as exc:  # noqa: BLE001 — 批量页失败记下来，不中断其余日期
            last = exc
            time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(str(last)[:180])


def _article_ok(html: str, day: str) -> bool:
    year, month, day_n = (int(part) for part in day.split("-"))
    return day in html or f"{year}年{month}月{day_n}日" in html


def fetch_gold_history(con, log: list[str], *, workers: int = 8) -> dict:
    """2016-12-19 之前的历史行情文章。Dailyhq 已覆盖之后的日子。"""
    articles = []

    def index_page(page: int) -> tuple[int, list[dict]]:
        url = f"{HISTORY}?p={page}"
        raw = _http_bytes(url, SGE + "/sjzx/mrhqsj")
        return page, parse.parse_sge_index_page(raw.decode("utf-8", "replace"))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(index_page, page) for page in range(1, 391)]
        for future in as_completed(futures):
            try:
                page, found = future.result()
            except Exception as exc:  # noqa: BLE001
                log.append(f"sge index FAIL {exc}")
                continue
            for item in found:
                if item["date"] < DAILYHQ_START:
                    articles.append(item)
            if page % 80 == 0:
                log.append(f"sge index p={page} queued={len(articles)}")
    # 同一天多篇文章时都抓，收盘不一致就整日不用。
    by_date: dict[str, list[dict]] = {}
    have = {row[0] for row in con.execute("SELECT date FROM bars WHERE code='Au99.99' AND adj='raw'")}

    def one(item: dict) -> dict:
        url = SGE + item["path"]
        raw = _http_bytes(url, HISTORY)
        html = raw.decode("utf-8", "replace")
        digest = hashlib.sha256(raw).hexdigest()
        if not _article_ok(html, item["date"]):
            return {"date": item["date"], "url": url, "sha256": digest, "status": "date_mismatch", "raw": raw}
        quotes = parse.parse_sge_history(html)
        return {"date": item["date"], "url": url, "sha256": digest, "status": "ok" if quotes else "no_au9999",
                "quotes": quotes, "raw": raw}

    failures = []
    labels: dict[str, int] = {}
    fresh = []
    conflicts = []
    pending = [item for item in articles if item["date"] not in have]
    log.append(f"sge history articles={len(articles)} to_fetch={len(pending)}")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, item) for item in pending]
        done = 0
        for future in as_completed(futures):
            done += 1
            try:
                got = future.result()
            except Exception as exc:  # noqa: BLE001
                failures.append(str(exc)[:180])
                continue
            by_date.setdefault(got["date"], []).append(got)
            if done % 200 == 0:
                log.append(f"sge history fetched {done}/{len(pending)}")
    for day, group in by_date.items():
        quotes = []
        for item in group:
            if item.get("status") != "ok":
                failures.append(f"{day} {item.get('status')}")
                continue
            for quote in item["quotes"]:
                quotes.append(quote)
                labels[quote["contract"]] = labels.get(quote["contract"], 0) + 1
            rel = f"sge/history/{day}.html"
            save_bytes(rel, item["raw"], url=item["url"], note="历史行情文章")
        closes = {round(float(quote["close"]), 4) for quote in quotes}
        if len(closes) > 1:
            conflicts.append(day)
            continue
        if quotes and day not in have:
            fresh.append(_quote_row(quotes[0], day))
    fresh.sort(key=lambda row: row["date"])
    result = store.write_series(con, "Au99.99", "sge_daily", fresh, DB.now()) if fresh else {"status": "reused"}
    meta = {
        "series_code": "Au99.99",
        "labels": labels,
        "conflicts": conflicts,
        "failed": len(failures),
        "fresh": len(fresh),
        "dailyhq": DAILYHQ + "?instid=Au99.99",
        "history": HISTORY,
    }
    save_bytes("gold.json", json.dumps(meta, ensure_ascii=False, indent=1).encode(), url=HISTORY, note="黄金合并摘要")
    log.append(f"sge history {result} fresh={len(fresh)} conflicts={len(conflicts)} failed={len(failures)} labels={labels}")
    if failures[:8]:
        log.append("sge history sample fails " + " | ".join(failures[:8]))
    return meta


def trim_discontinuous_prefix(con, code: str = "Au99.99", max_gap: int = 60) -> str:
    """历史行情列表在 2003-04-15 与 2008-08-11 之间没有页。

    把两段收盘拼成一条，对齐到交易日后会把这五年的涨跌记成一个交易日。只保留最后一段。
    """
    dates = [row[0] for row in con.execute(
        "SELECT date FROM bars WHERE code=? AND adj='raw' ORDER BY date", (code,))]
    start = dates[0] if dates else ""
    for prev, nxt in zip(dates, dates[1:]):
        if (date.fromisoformat(nxt) - date.fromisoformat(prev)).days > max_gap:
            start = nxt
    if start:
        con.execute("DELETE FROM bars WHERE code=? AND adj='raw' AND date < ?", (code, start))
        con.commit()
    return start


def drop_nonpositive_overseas(con, log: list[str]) -> list[dict]:
    """海外来源里收盘 ≤ 0 的行不是价格。A 股序列里的 0 不动。"""
    marks = ",".join("?" * len(OVERSEAS))
    found = con.execute(
        f"""SELECT code, date, open, high, low, close, source FROM bars
            WHERE adj='raw' AND close IS NOT NULL AND close<=0 AND source IN ({marks})
            ORDER BY code, date""",
        OVERSEAS).fetchall()
    rows = [
        {"code": code, "date": day, "open": open_, "high": high, "low": low, "close": close, "source": source}
        for code, day, open_, high, low, close, source in found
    ]
    if rows:
        con.execute(
            f"""DELETE FROM bars WHERE adj='raw' AND close IS NOT NULL AND close<=0
                AND source IN ({marks})""",
            OVERSEAS)
        con.commit()
        save_bytes("overseas-zero-close.json", json.dumps(rows, ensure_ascii=False, indent=1).encode(),
                   url="", note="删掉的非正收盘")
    log.append(f"overseas nonpositive close removed {len(rows)}")
    return rows


def audit_overseas(con) -> list[dict]:
    """原生序列上的非正收盘，以及间隔超过 4 个日历日且涨跌超过 15% 的日子。"""
    marks = ",".join("?" * len(OVERSEAS))
    frame_rows = con.execute(
        f"""SELECT code, source, date, close FROM bars
            WHERE adj='raw' AND source IN ({marks}) ORDER BY code, date""",
        OVERSEAS).fetchall()
    by_code: dict[str, list[tuple]] = {}
    for code, source, day, close in frame_rows:
        by_code.setdefault(code, []).append((source, day, close))
    out = []
    for code, rows in by_code.items():
        prev = None
        for source, day, close in rows:
            if close is None or close <= 0:
                out.append({"code": code, "source": source, "date": day, "kind": "nonpositive_close",
                            "close": close, "prev_close": None, "gap_days": "", "ret": ""})
                continue
            if prev is not None and prev[2] and prev[2] > 0:
                gap = (date.fromisoformat(day) - date.fromisoformat(prev[1])).days
                ret = close / prev[2] - 1.0
                if gap > 4 and abs(ret) >= 0.15:
                    out.append({"code": code, "source": source, "date": day, "kind": "gap_move",
                                "close": close, "prev_close": prev[2], "gap_days": gap, "ret": ret})
            prev = (source, day, close)
    path = ROOT / "results" / "v3" / "inventory" / "overseas-holiday-audit.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["code", "source", "date", "kind", "close", "prev_close", "gap_days", "ret"])
        writer.writeheader()
        writer.writerows(out)
    return out


class _PrintLog(list):
    def append(self, item):
        print(item, flush=True)
        super().append(item)


def run(end: date = END, log: list[str] | None = None) -> dict:
    printed = log if isinstance(log, _PrintLog) else _PrintLog()
    log = printed
    path = DB.MARKET_DB
    book = store.ledger(path)
    before = book.before("v3-defensive")
    con = store.connect(path)
    try:
        bonds = fetch_bonds(con, log, end)
        gold_hq = fetch_gold_dailyhq(con, log, end)
        gold_hist = fetch_gold_history(con, log)
        kept = trim_discontinuous_prefix(con)
        log.append(f"gold continuous from {kept}")
        removed = drop_nonpositive_overseas(con, log)
        audit = audit_overseas(con)
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()
    after = book.after("v3-defensive")
    return {
        "before": before, "after": after, "bonds": bonds, "gold_hq": gold_hq,
        "gold_hist": gold_hist, "removed": removed, "audit": audit,
        "integrity": integrity, "log": log,
    }
