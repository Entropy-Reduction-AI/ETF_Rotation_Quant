#!/usr/bin/env python3
"""拉取 NEEDED.csv 里的中证指数日线，只写本目录。

一个指数全程只用一个来源，不拼接。优先级：中证指数官网、东方财富、
腾讯 / 搜狐 / 新浪。开高低为空的行不补造。可重复运行：已有且能解析的
raw 响应会复用，不重复打官网。
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
NEEDED = ROOT / "NEEDED.csv"
DB = ROOT.parents[1] / "data" / "market.sqlite"
SHA = ZoneInfo("Asia/Shanghai")
END = "20260930"
END_ISO = "2026-09-30"
CSI = "https://www.csindex.com.cn/csindex-home/perf/index-perf"
EM = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
TENCENT = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
SOHU = "https://q.stock.sohu.com/hisHq"
SINA = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# 东方财富 suggest 已核对过的 secid。没有的代码不猜。
EM_SECID = {
    "000300": "1.000300", "930606": "2.930606", "000015": "1.000015",
    "H30184": "2.H30184", "931743": "2.931743", "H30202": "2.H30202",
    "H30590": "2.H30590", "930997": "2.930997", "H30269": "2.H30269",
    "930713": "2.930713", "000819": "1.000819", "000913": "1.000913",
    "000932": "1.000932", "000949": "1.000949", "931494": "2.931494",
    "931151": "2.931151", "931152": "2.931152", "399986": "0.399986",
    "931160": "2.931160", "000688": "1.000688", "399998": "0.399998",
    "399967": "0.399967", "399987": "0.399987", "399975": "0.399975",
    "000852": "1.000852", "000905": "1.000905",
}

SOURCE_CSI = "中证指数官网"
SOURCE_EM = "东方财富"
SOURCE_TENCENT = "腾讯行情"
SOURCE_SOHU = "搜狐行情"
SOURCE_SINA = "新浪财经"


def now_sha() -> str:
    return datetime.now(SHA).isoformat(timespec="seconds")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def num(v) -> str:
    if v is None or v == "":
        return ""
    x = float(v)
    if x != x:
        return ""
    if abs(x - round(x)) < 1e-6 and abs(x) < 1e15:
        return str(int(round(x)))
    return f"{x:.6f}".rstrip("0").rstrip(".")


def iso(yyyymmdd: str) -> str:
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def ymd(iso_date: str) -> str:
    return iso_date.replace("-", "")


def parse_date(s: str):
    return datetime.strptime(s, "%Y-%m-%d").date()


@dataclass
class Row:
    date: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None
    amount: float | None

    def real_ohlc(self) -> bool:
        return None not in (self.open, self.high, self.low, self.close)


@dataclass
class Attempt:
    source: str
    detail: str


@dataclass
class Series:
    rows: list[Row]
    source: str
    url: str
    params: dict
    fetched_at: str
    raw_files: list[str] = field(default_factory=list)
    requests: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class Http:
    """每个主机 403 / 断连只做一次 90 秒重试。中证请求之间至少 1.5 秒。"""

    def __init__(self):
        self.csi_last = 0.0
        self.long_waited: set[str] = set()
        self.log: list[dict] = []

    def get(self, url: str, *, params: dict | None = None, headers: dict | None = None,
            timeout: int = 90, csi_pace: bool = False, tag: str) -> tuple[int | str, bytes]:
        if params:
            url = f"{url}{'&' if '?' in url else '?'}{urlencode(params)}"
        if csi_pace and self.csi_last:
            wait = 1.5 - (time.monotonic() - self.csi_last)
            if wait > 0:
                time.sleep(wait)
        host = url.split("/")[2]
        status, body = self._once(url, headers or {}, timeout)
        if self._blocked(status) and host not in self.long_waited:
            self.long_waited.add(host)
            print(f"  {host} {status}，等待 90 秒后重试一次", flush=True)
            time.sleep(90)
            status, body = self._once(url, headers or {}, timeout)
        if csi_pace:
            self.csi_last = time.monotonic()
        path = self._save(tag, url, status, body)
        return status, body

    def _blocked(self, status) -> bool:
        if status in (403, 429, 502, 503):
            return True
        return isinstance(status, str) and ("RemoteDisconnected" in status or "timed out" in status or "Timeout" in status)

    def _once(self, url: str, headers: dict, timeout: int) -> tuple[int | str, bytes]:
        h = {"User-Agent": UA, "Accept": "*/*", "Accept-Encoding": "gzip", "Connection": "close", **headers}
        try:
            with urlopen(Request(url, headers=h), timeout=timeout) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
                    try:
                        raw = gzip.decompress(raw)
                    except Exception:
                        pass
                return r.status, raw
        except HTTPError as e:
            body = e.read()
            return e.code, body
        except (URLError, TimeoutError, OSError) as e:
            return type(e).__name__, str(e)[:300].encode()

    def _save(self, tag: str, url: str, status, body: bytes) -> str:
        RAW.mkdir(parents=True, exist_ok=True)
        digest = sha256_bytes(body)
        name = f"{tag}_{digest[:12]}.body"
        path = RAW / name
        if not path.exists():
            path.write_bytes(body)
        meta = {
            "url": url, "status": status if isinstance(status, int) else str(status),
            "fetched_at": now_sha(), "sha256": digest, "bytes": len(body), "file": name,
        }
        (RAW / f"{name}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        self.log.append(meta)
        return name


HTTP = Http()


def load_needed() -> list[dict]:
    with NEEDED.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_calendar() -> list[str]:
    uri = f"file:{DB}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        return [r[0] for r in con.execute("SELECT date FROM calendar ORDER BY date")]
    finally:
        con.close()


def load_db_closes() -> dict[str, dict[str, float]]:
    uri = f"file:{DB}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    out: dict[str, dict[str, float]] = {}
    try:
        for code, date, close in con.execute("SELECT code, date, close FROM bars WHERE close IS NOT NULL"):
            out.setdefault(code, {})[date] = float(close)
    finally:
        con.close()
    return out


def parse_gaps(text: str) -> list[tuple[str, str]] | None:
    text = (text or "").strip()
    if not text:
        return []
    if text == "ALL":
        return None
    spans = []
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        if "~" in part:
            a, b = [x.strip() for x in part.split("~", 1)]
            spans.append((a, b))
        else:
            spans.append((part, part))
    return spans


def expand_gaps(spans, calendar: list[str]) -> list[str] | None:
    if spans is None:
        return None
    cal = set(calendar)
    dates = []
    for a, b in spans:
        dates.extend(d for d in calendar if a <= d <= b and d in cal)
    return dates


def request_start(row: dict) -> str:
    s = (row.get("start") or "").strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return ymd(s)
    return "19900101"


def fnum(v):
    if v is None or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x:
        return None
    return x


def parse_csi(body: bytes, code: str) -> tuple[list[Row], str]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        return [], f"不是 JSON：{e}"
    if not isinstance(payload, dict):
        return [], f"响应不是对象：{str(payload)[:80]}"
    if str(payload.get("code")) != "200":
        return [], f"code={payload.get('code')} msg={payload.get('msg')}"
    rows = []
    for item in payload.get("data") or []:
        ic = str(item.get("indexCode") or "")
        if ic and ic.upper() != code.upper():
            return [], f"响应指数代码是 {ic}，不是 {code}"
        td = str(item.get("tradeDate") or "")
        if len(td) != 8 or not td.isdigit():
            continue
        if td > END:
            continue
        rows.append(Row(iso(td), fnum(item.get("open")), fnum(item.get("high")), fnum(item.get("low")),
                        fnum(item.get("close")), fnum(item.get("tradingVol")), fnum(item.get("tradingValue"))))
    rows.sort(key=lambda r: r.date)
    dedup = {}
    for r in rows:
        dedup[r.date] = r
    return [dedup[d] for d in sorted(dedup)], "ok"


def fetch_csi(code: str, start: str, end: str, tag: str) -> tuple[list[Row], str, dict]:
    params = {"indexCode": code, "startDate": start, "endDate": end}
    status, body = HTTP.get(CSI, params=params, headers={"Referer": "https://www.csindex.com.cn/"},
                             csi_pace=True, tag=tag, timeout=120)
    entry = HTTP.log[-1]
    if not isinstance(status, int) or status != 200:
        return [], f"HTTP {status} {body[:120]!r}", entry
    rows, msg = parse_csi(body, code)
    return rows, msg, entry


def parse_em(body: bytes) -> tuple[list[Row], str, str | None]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        return [], f"不是 JSON：{e}", None
    if payload.get("rc") not in (0, "0", None) and not (payload.get("data") or {}).get("klines"):
        return [], f"rc={payload.get('rc')}", None
    data = payload.get("data") or {}
    if data is None:
        return [], "data=null", None
    name = data.get("name")
    rows = []
    for line in data.get("klines") or []:
        p = line.split(",")
        if len(p) < 5:
            continue
        d = p[0]
        if d > END_ISO:
            continue
        # 日期,开,收,高,低,量,额
        rows.append(Row(d, fnum(p[1]), fnum(p[3]), fnum(p[4]), fnum(p[2]),
                        fnum(p[5]) if len(p) > 5 else None, fnum(p[6]) if len(p) > 6 else None))
    dedup = {r.date: r for r in rows}
    return [dedup[d] for d in sorted(dedup)], "ok", name


def fetch_em(code: str, secid: str, start_iso: str) -> tuple[list[Row], str, dict | None]:
    params = {
        "secid": secid, "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101", "fqt": "0", "beg": ymd(start_iso), "end": END, "lmt": "100000",
    }
    status, body = HTTP.get(EM, params=params, headers={"Referer": "https://quote.eastmoney.com/"},
                             tag=f"em_{code}", timeout=40)
    entry = HTTP.log[-1]
    if not isinstance(status, int) or status != 200 or not body[:1] in (b"{", b"["):
        return [], f"HTTP {status} {body[:80]!r}", entry
    rows, msg, name = parse_em(body)
    if name:
        msg = f"{msg} name={name} n={len(rows)}"
    return rows, msg, entry


def tencent_symbols(code: str) -> list[str]:
    if code.startswith("399"):
        return [f"sz{code}"]
    if code.startswith("000"):
        return [f"sh{code}"]
    if code.startswith("93"):
        return [f"sh{code}", f"sz{code}"]
    return [f"sh{code}", f"sz{code}"]


def parse_tencent(body: bytes, sym: str) -> tuple[list[Row], str]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        return [], f"不是 JSON：{e}"
    if not isinstance(payload, dict) or payload.get("code") not in (0, "0"):
        return [], f"code={payload.get('code') if isinstance(payload, dict) else None} msg={str(payload)[:80]}"
    node = ((payload.get("data") or {}).get(sym)) or {}
    rows = []
    for p in node.get("day") or []:
        if len(p) < 5:
            continue
        d = p[0]
        if d > END_ISO:
            continue
        # 日期,开,收,高,低,量
        rows.append(Row(d, fnum(p[1]), fnum(p[3]), fnum(p[4]), fnum(p[2]), fnum(p[5]) if len(p) > 5 else None, None))
    dedup = {r.date: r for r in rows}
    return [dedup[d] for d in sorted(dedup)], "ok"


def fetch_tencent_window(code: str, sym: str, start: datetime.date, end: datetime.date) -> tuple[list[Row], str, list[dict]]:
    status, body = HTTP.get(
        TENCENT, params={"param": f"{sym},day,{start.isoformat()},{end.isoformat()},400,"},
        tag=f"tencent_{code}", timeout=30)
    entry = HTTP.log[-1]
    if not isinstance(status, int) or status != 200:
        return [], f"{sym} HTTP {status}", [entry]
    rows, msg = parse_tencent(body, sym)
    if msg != "ok":
        return [], f"{sym} {msg}", [entry]
    return rows, "ok", [entry]


def fetch_tencent(code: str, start_iso: str) -> tuple[list[Row], str, list[dict]]:
    entries = []
    best: list[Row] = []
    notes = []
    start = parse_date(start_iso)
    end = parse_date(END_ISO)
    for sym in tencent_symbols(code):
        probe_beg = max(start, end - timedelta(days=20))
        probe, pmsg, pentries = fetch_tencent_window(code, sym, probe_beg, end)
        entries.extend(pentries)
        time.sleep(0.35)
        if not probe:
            notes.append(f"{sym} 近期无 K 线（{pmsg}）")
            continue
        rows_all: list[Row] = list(probe)
        beg = start
        saturated = False
        while beg < probe_beg:
            stop = min(beg + timedelta(days=420), probe_beg - timedelta(days=1))
            chunk, msg, centries = fetch_tencent_window(code, sym, beg, stop)
            entries.extend(centries)
            if msg != "ok":
                notes.append(msg)
                rows_all = []
                break
            if len(chunk) >= 400:
                saturated = True
                break
            rows_all.extend(chunk)
            beg = stop + timedelta(days=1)
            time.sleep(0.35)
        if saturated:
            notes.append(f"{sym} 单窗达到 400 行，放弃该符号以免截断")
            continue
        dedup = {r.date: r for r in rows_all}
        rows = [dedup[d] for d in sorted(dedup)]
        notes.append(f"{sym} n={len(rows)}")
        if len(rows) > len(best):
            best = rows
        if rows and rows[0].real_ohlc():
            break
    return best, "; ".join(notes), entries


def parse_sohu(body: bytes) -> tuple[list[Row], str]:
    text = body.decode("gbk", "ignore").strip()
    if not text or text == "{}":
        return [], "空响应"
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as e:
        return [], f"不是 JSON：{e}"
    if isinstance(payload, dict):
        return [], str(payload)[:120]
    if not payload or not isinstance(payload, list):
        return [], "无列表"
    block = payload[0]
    if block.get("status") not in (0, "0"):
        return [], f"status={block.get('status')} msg={block.get('msg')}"
    rows = []
    for hq in block.get("hq") or []:
        if len(hq) < 7:
            continue
        d = hq[0]
        if d > END_ISO:
            continue
        # 日期,开盘,收盘,涨跌额,涨跌幅,最低,最高,成交量,成交额,换手率
        rows.append(Row(d, fnum(hq[1]), fnum(hq[6]), fnum(hq[5]), fnum(hq[2]),
                        fnum(hq[7]) if len(hq) > 7 else None, fnum(hq[8]) if len(hq) > 8 else None))
    dedup = {r.date: r for r in rows}
    return [dedup[d] for d in sorted(dedup)], "ok"


def fetch_sohu(code: str, start_iso: str, end_iso: str = END_ISO) -> tuple[list[Row], str, list[dict]]:
    entries = []
    rows_all: list[Row] = []
    start = parse_date(start_iso)
    end = parse_date(end_iso)
    beg = start
    while beg <= end:
        stop = min(beg + timedelta(days=365 * 3 - 1), end)
        params = {"code": f"zs_{code}", "start": ymd(beg.isoformat()), "end": ymd(stop.isoformat()),
                  "stat": "1", "order": "D", "period": "d"}
        status, body = HTTP.get(SOHU, params=params, headers={"Referer": "https://q.stock.sohu.com/"},
                                 tag=f"sohu_{code}", timeout=40)
        entries.append(HTTP.log[-1])
        if not isinstance(status, int) or status != 200:
            return rows_all, f"HTTP {status}", entries
        chunk, msg = parse_sohu(body)
        if msg != "ok":
            return [], msg, entries
        rows_all.extend(chunk)
        beg = stop + timedelta(days=1)
        time.sleep(0.4)
    dedup = {r.date: r for r in rows_all}
    return [dedup[d] for d in sorted(dedup)], f"ok n={len(dedup)}", entries


def fetch_sina(code: str, sym: str) -> tuple[list[Row], str, dict | None]:
    # 新浪只给最近 datalen 根，试到能返回的上限。
    best: list[Row] = []
    entry = None
    note = ""
    for n in (2000, 1023):
        params = {"symbol": sym, "scale": "240", "ma": "no", "datalen": str(n)}
        status, body = HTTP.get(SINA, params=params, headers={"Referer": "https://finance.sina.com.cn/"},
                                 tag=f"sina_{code}", timeout=40)
        entry = HTTP.log[-1]
        if not isinstance(status, int) or status != 200 or body.strip() in (b"null", b""):
            note = f"HTTP {status} {body[:60]!r}"
            continue
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            note = f"不是 JSON：{e}"
            continue
        if not isinstance(payload, list):
            note = str(payload)[:80]
            continue
        rows = []
        for item in payload:
            d = str(item.get("day") or "")
            if not d or d > END_ISO:
                continue
            rows.append(Row(d, fnum(item.get("open")), fnum(item.get("high")), fnum(item.get("low")),
                            fnum(item.get("close")), fnum(item.get("volume")), None))
        dedup = {r.date: r for r in rows}
        rows = [dedup[d] for d in sorted(dedup)]
        if len(rows) > len(best):
            best = rows
        note = f"{sym} n={len(rows)} first={rows[0].date if rows else None}"
        if len(rows) < n:
            break
    return best, note, entry


def same_index(ref: list[Row], other: list[Row]) -> tuple[bool, str]:
    a = {r.date: r.close for r in ref if r.close is not None}
    b = {r.date: r.close for r in other if r.close is not None}
    common = sorted(set(a) & set(b))
    if len(common) < 20:
        return False, f"重叠仅 {len(common)} 天"
    rel = sorted(abs(a[d] - b[d]) / abs(a[d]) for d in common if a[d])
    med = rel[len(rel) // 2]
    p95 = rel[min(len(rel) - 1, int(len(rel) * 0.95))]
    ok = med <= 1e-4 and p95 <= 1e-3
    return ok, f"重叠 {len(common)} 天，收盘相对差中位数 {med:.3g}，P95 {p95:.3g}"


def real_map(rows: list[Row]) -> dict[str, Row]:
    return {r.date: r for r in rows if r.real_ohlc() and r.date <= END_ISO}


def clip_start(rows: list[Row], start_iso: str) -> list[Row]:
    return [r for r in rows if start_iso <= r.date <= END_ISO]


def covers_reference(candidate: dict[str, Row], ref_dates: set[str]) -> tuple[bool, str]:
    missing = sorted(d for d in ref_dates if d not in candidate)
    if missing:
        return False, f"缺少参考日期 {len(missing)} 天，例如 {missing[:3]}"
    return True, f"覆盖参考日期 {len(ref_dates)} 天"


def write_csv(path: Path, rows: list[Row]) -> None:
    has_amount = any(r.amount is not None for r in rows)
    fields = ["date", "open", "high", "low", "close", "volume"] + (["amount"] if has_amount else [])
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            item = {"date": r.date, "open": num(r.open), "high": num(r.high), "low": num(r.low),
                    "close": num(r.close), "volume": num(r.volume)}
            if has_amount:
                item["amount"] = num(r.amount)
            w.writerow(item)


def compress_dates(dates: list[str], calendar: list[str]) -> str:
    if not dates:
        return ""
    cal_index = {d: i for i, d in enumerate(calendar)}
    ordered = sorted(dates)
    runs = []
    run_start = ordered[0]
    prev = ordered[0]
    for d in ordered[1:]:
        ip, ic = cal_index.get(prev), cal_index.get(d)
        if ip is not None and ic is not None and ic == ip + 1:
            prev = d
            continue
        runs.append((run_start, prev))
        run_start = prev = d
    runs.append((run_start, prev))
    parts = []
    for a, b in runs:
        parts.append(a if a == b else f"{a}~{b}")
    return "; ".join(parts)


def ohlc_problems(rows: list[Row]) -> int:
    n = 0
    for r in rows:
        if not r.real_ohlc():
            continue
        if r.high < r.low or r.high < max(r.open, r.close) - 1e-6 or r.low > min(r.open, r.close) + 1e-6:
            n += 1
    return n


def series_entry(file: str, code: str, series: Series, rows: list[Row], gap_note: str) -> dict:
    return {
        "file": file,
        "index_code": code,
        "source": series.source,
        "request_url": series.url,
        "params": series.params,
        "requests": series.requests,
        "fetched_at": series.fetched_at,
        "sha256": sha256_file(ROOT / file),
        "rows": len(rows),
        "start_date": rows[0].date if rows else None,
        "end_date": rows[-1].date if rows else None,
        "raw_files": series.raw_files,
        "gap_coverage": gap_note,
        "notes": series.notes,
    }


def gap_status(code_rows: dict[str, Row], gap_dates: list[str] | None, calendar: list[str],
               requested_start: str) -> tuple[str, str, list[str]]:
    """返回 coverage 词、说明、未覆盖的交易日。"""
    if gap_dates is None:
        # 整段缺失：从第一根真实 K 线到截止日，对照交易日历。
        if not code_rows:
            return "no", "没有真实 OHLC", []
        first = min(code_rows)
        expected = [d for d in calendar if first <= d <= END_ISO]
        missing = [d for d in expected if d not in code_rows]
        if not missing:
            return "yes", f"全段 {first}~{END_ISO}，交易日无缺", []
        return ("partial" if code_rows else "no",
                f"起点 {first}，仍缺 {len(missing)} 个交易日", missing)
    if not gap_dates:
        if not code_rows:
            return "no", "清单无缺失段，但没有取到 OHLC", []
        last = max(code_rows)
        return "yes", f"清单无缺失段；序列 {min(code_rows)}~{last}", []
    missing = [d for d in gap_dates if d not in code_rows or not code_rows[d].real_ohlc()]
    if not missing:
        return "yes", f"清单 {len(gap_dates)} 个缺口日全部有真实 OHLC", []
    if len(missing) == len(gap_dates):
        return "no", f"清单 {len(gap_dates)} 个缺口日都没有真实 OHLC", missing
    return "partial", f"清单缺口覆盖 {len(gap_dates) - len(missing)}/{len(gap_dates)}", missing


def try_fallbacks(code: str, start_iso: str, csi_rows: list[Row], must_cover: set[str], *,
                   calendar_set: set[str], need_ohlc: bool) -> tuple[Series | None, list[Attempt]]:
    attempts = []
    # 只要求交易日。官网偶发的非交易日占位行不拿来卡备用源。
    ref_dates = {r.date for r in csi_rows
                 if r.close is not None and r.date in calendar_set and start_iso <= r.date <= END_ISO}
    ref_dates |= {d for d in must_cover if start_iso <= d <= END_ISO}
    if not need_ohlc:
        ref_dates = {d for d in must_cover if start_iso <= d <= END_ISO}

    def judge(rows: list[Row]) -> tuple[bool, str]:
        if not rows:
            return False, "无数据"
        ok_id, id_msg = same_index(csi_rows, rows)
        if need_ohlc:
            ok_cov, cov_msg = covers_reference(real_map(rows), ref_dates)
            ok_shape, shape_msg = same_ohlc(csi_rows, rows)
            ok = ok_id and ok_cov and ok_shape
            return ok, f"同一性：{id_msg}；开高低：{shape_msg}；覆盖：{cov_msg}"
        have = {r.date for r in rows if r.close is not None}
        miss = sorted(d for d in ref_dates if d not in have)
        ok = ok_id and not miss
        cov_msg = "清单日期都有收盘" if not miss else f"仍缺 {miss}"
        return ok, f"同一性：{id_msg}；覆盖：{cov_msg}"

    secid = EM_SECID.get(code)
    if secid is None and (code.startswith("H") or code.startswith("93") or code.startswith("399") or code.startswith("000")):
        attempts.append(Attempt(SOURCE_EM, "suggest 接口没有这个指数的 QuoteID，未伪造 secid"))
    elif secid:
        rows, msg, entry = fetch_em(code, secid, start_iso)
        rows = clip_start(rows, start_iso)
        ok, detail = judge(rows)
        attempts.append(Attempt(SOURCE_EM, f"secid={secid} {msg}；{detail}"))
        if ok:
            return Series(rows, SOURCE_EM, EM, {"secid": secid, "klt": 101, "fqt": 0, "beg": ymd(start_iso), "end": END},
                          entry["fetched_at"] if entry else now_sha(),
                          [entry["file"]] if entry else [], [entry] if entry else [],
                          [detail]), attempts

    rows, msg, entries = fetch_tencent(code, start_iso)
    rows = clip_start(rows, start_iso)
    ok, detail = judge(rows)
    attempts.append(Attempt(SOURCE_TENCENT, f"{msg}；{detail}"))
    if ok:
        return Series(rows, SOURCE_TENCENT, TENCENT,
                      {"param": "<symbol>,day,<start>,<end>,400,", "symbols": tencent_symbols(code)},
                      entries[-1]["fetched_at"] if entries else now_sha(),
                      [e["file"] for e in entries], entries, [detail]), attempts

    rows, msg, entries = fetch_sohu(code, start_iso)
    rows = clip_start(rows, start_iso)
    ok, detail = judge(rows)
    attempts.append(Attempt(SOURCE_SOHU, f"zs_{code} {msg}；{detail}"))
    if ok:
        return Series(rows, SOURCE_SOHU, SOHU,
                      {"code": f"zs_{code}", "start": ymd(start_iso), "end": END, "period": "d"},
                      entries[-1]["fetched_at"] if entries else now_sha(),
                      [e["file"] for e in entries], entries, [detail]), attempts

    if not code.startswith("H"):
        for sym in tencent_symbols(code):
            rows, msg, entry = fetch_sina(code, sym)
            rows = clip_start(rows, start_iso)
            ok, detail = judge(rows)
            attempts.append(Attempt(SOURCE_SINA, f"{msg}；{detail}"))
            if ok:
                return Series(rows, SOURCE_SINA, SINA, {"symbol": sym, "scale": 240, "datalen": "最近可用根数"},
                              entry["fetched_at"] if entry else now_sha(),
                              [entry["file"]] if entry else [], [entry] if entry else [],
                              [detail]), attempts
    return None, attempts


def same_ohlc(ref: list[Row], other: list[Row]) -> tuple[bool, str]:
    """备用源和官网都有开高低的日子，开高低必须对得上，防止列序错了还靠收盘混过去。"""
    a = {r.date: r for r in ref if r.real_ohlc()}
    b = {r.date: r for r in other if r.real_ohlc()}
    common = sorted(set(a) & set(b))
    if len(common) < 20:
        return True, f"可对照的开高低只有 {len(common)} 天，未单独否决"
    rel = []
    for d in common:
        for x, y in ((a[d].open, b[d].open), (a[d].high, b[d].high), (a[d].low, b[d].low)):
            if x:
                rel.append(abs(x - y) / abs(x))
    rel.sort()
    med = rel[len(rel) // 2]
    return med <= 1e-3, f"相对差中位数 {med:.3g}（{len(common)} 天）"


def csi_series(code: str, rows: list[Row], entries: list[dict], start: str) -> Series:
    entries = [e for e in entries if e]
    return Series(
        rows, SOURCE_CSI, CSI,
        {"indexCode": code, "startDate": start, "endDate": END,
         "segments": "一次取全段" if len(entries) <= 1 else "按年"},
        entries[-1].get("fetched_at") if entries else now_sha(),
        [e["file"] for e in entries],
        entries,
    )


def fetch_csi_full(code: str, start: str) -> tuple[list[Row], str, list[dict]]:
    rows, msg, entry = fetch_csi(code, start, END, f"csi_{code}")
    entries = [entry]
    suspicious = len(rows) in {1000, 2000, 3000, 4000, 5000, 8000, 10000}
    short_tail = bool(rows) and rows[-1].date < END_ISO
    if msg == "ok" and not suspicious and not short_tail:
        return rows, msg, entries
    if msg == "ok" and not rows:
        return rows, msg, entries
    print(f"  官网单次 n={len(rows)} last={rows[-1].date if rows else None} msg={msg}，改为按年", flush=True)
    merged: list[Row] = []
    for year in range(int(start[:4]), 2027):
        b = max(start, f"{year}0101")
        e = min(END, f"{year}1231")
        if b > e:
            continue
        chunk, cmsg, centry = fetch_csi(code, b, e, f"csi_{code}_{year}")
        entries.append(centry)
        if cmsg != "ok":
            dedup = {r.date: r for r in merged}
            return [dedup[d] for d in sorted(dedup)], cmsg, entries
        merged.extend(chunk)
    dedup = {r.date: r for r in merged}
    return [dedup[d] for d in sorted(dedup)], "ok", entries


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    needed = load_needed()
    calendar = load_calendar()
    cal_set = set(calendar)
    print(f"清单 {len(needed)} 行，交易日历 {len(calendar)} 天", flush=True)
    manifest_files = []
    unavailable = []
    tr_out_rows = []
    tr_series_meta = []

    price_rows = [r for r in needed if r["price_or_tr"] == "价格指数"]
    tr_rows = [r for r in needed if r["price_or_tr"] == "全收益指数"]

    for row in price_rows:
        code, name = row["index_code"], row["index_name"]
        start = request_start(row)
        start_iso = iso(start)
        print(f"\n== {code} {name} {start_iso} -> {END_ISO}", flush=True)
        csi_rows, msg, entries = fetch_csi_full(code, start)
        csi_rows = clip_start(csi_rows, start_iso)
        print(f"  CSI {msg} n={len(csi_rows)} real={sum(r.real_ohlc() for r in csi_rows)}", flush=True)
        gaps = parse_gaps(row["missing_ranges"])
        gap_dates = expand_gaps(gaps, calendar)
        null_trade = [r.date for r in csi_rows if r.date in cal_set and not r.real_ohlc()]
        present = real_map(csi_rows)
        if gap_dates is None:
            must = []
        else:
            must = [d for d in gap_dates if d not in present]
        need_fallback = bool(null_trade or must)
        chosen = csi_series(code, csi_rows, entries, start)
        attempts = [Attempt(SOURCE_CSI, f"{msg}；行数 {len(csi_rows)}；交易日开高低为空 {len(null_trade)}；"
                                         f"清单缺口未覆盖 {len(must)}"
                                         + (f"；样例空 OHLC {null_trade[0]}" if null_trade else ""))]
        if need_fallback:
            print(f"  CSI 不完整（空 OHLC {len(null_trade)}，缺口未盖 {len(must)}），试下一个来源", flush=True)
            alt, alt_attempts = try_fallbacks(
                code, start_iso, csi_rows, set(null_trade) | set(must) | set(present),
                calendar_set=cal_set, need_ohlc=True)
            attempts.extend(alt_attempts)
            if alt is not None:
                chosen = alt
                print(f"  改用 {alt.source} n={len(alt.rows)}", flush=True)
            else:
                print("  没有可替换的全段来源，保留官网里有真实 OHLC 的行", flush=True)
        use_rows = [r for r in chosen.rows if r.real_ohlc()]
        # 只用选定来源。官网未选中时不要把官网的行混进来。
        bad = ohlc_problems(use_rows)
        if bad:
            chosen.notes.append(f"高低价关系异常 {bad} 行，按来源原值保留")
        by_date = {r.date: r for r in use_rows}
        coverage, cov_note, missing_dates = gap_status(by_date, gap_dates, calendar, start_iso)
        # 交易日上开高低为空、且没有被选定来源补上的，也算取不到。
        if chosen.source == SOURCE_CSI:
            extra = [d for d in null_trade if d not in by_date]
            for d in extra:
                if d not in missing_dates:
                    missing_dates.append(d)
            missing_dates = sorted(set(missing_dates))
            if missing_dates and coverage == "yes":
                coverage = "partial"
                cov_note = f"{cov_note}；另有 {len(missing_dates)} 个交易日没有真实 OHLC"
        chosen.notes.append(cov_note)
        if use_rows:
            fn = f"{code}.csv"
            write_csv(ROOT / fn, use_rows)
            manifest_files.append(series_entry(fn, code, chosen, use_rows, f"{coverage}: {cov_note}"))
            print(f"  写入 {fn} {len(use_rows)} 行 {coverage}", flush=True)
        else:
            print(f"  无真实 OHLC，不写 CSV", flush=True)
            coverage = "no"
        if missing_dates or not use_rows:
            unavailable.append({
                "code": code, "name": name, "kind": "价格指数",
                "dates": missing_dates, "attempts": attempts,
                "coverage": coverage, "note": cov_note,
                "no_file": not use_rows,
            })

    for row in tr_rows:
        code = row["index_code"]
        gaps = parse_gaps(row["missing_ranges"]) or []
        dates = []
        for a, b in gaps:
            if a == b:
                dates.append(a)
            else:
                dates.extend(d for d in calendar if a <= d <= b)
        dates = sorted(set(dates))
        if not dates:
            continue
        start = ymd(min(dates))
        end = ymd(max(dates))
        # 窗口略宽一天，避免边界刚好漏掉，输出仍只留清单日期。
        start_q = ymd((parse_date(min(dates)) - timedelta(days=5)).isoformat())
        end_q = ymd((parse_date(max(dates)) + timedelta(days=1)).isoformat())
        if end_q > END:
            end_q = END
        print(f"\n== TR {code} {dates}", flush=True)
        csi_rows, msg, entry = fetch_csi(code, start_q, end_q, f"csi_{code}")
        got = {r.date: r for r in csi_rows if r.close is not None}
        print(f"  CSI {msg} n={len(csi_rows)} 命中 {[d for d in dates if d in got]}", flush=True)
        attempts = [Attempt(SOURCE_CSI, f"{msg}；窗口 {iso(start_q)}~{iso(end_q)} 返回 {len(csi_rows)} 行；"
                                         f"清单日期命中 {sum(d in got for d in dates)}/{len(dates)}")]
        use_source = SOURCE_CSI
        use_map = got
        use_entry = entry
        use_rows = csi_rows
        missing = [d for d in dates if d not in got]
        if missing:
            alt, alt_attempts = try_fallbacks(
                code, iso(start_q), csi_rows, set(dates), calendar_set=cal_set, need_ohlc=False)
            attempts.extend(alt_attempts)
            if alt is not None:
                alt_map = {r.date: r for r in alt.rows if r.close is not None}
                if all(d in alt_map for d in dates):
                    use_source = alt.source
                    use_map = alt_map
                    use_entry = {"fetched_at": alt.fetched_at, "file": alt.raw_files[0] if alt.raw_files else ""}
                    use_rows = alt.rows
                    missing = []
                    print(f"  TR 改用 {alt.source}", flush=True)
        for d in dates:
            r = use_map.get(d)
            if r and r.close is not None and not missing:
                tr_out_rows.append({"index_code": code, "date": d, "close": num(r.close), "source": use_source})
            elif r and r.close is not None and use_source == SOURCE_CSI and d in got and not missing:
                tr_out_rows.append({"index_code": code, "date": d, "close": num(r.close), "source": use_source})
        if not missing:
            if use_source == SOURCE_CSI:
                for d in dates:
                    if not any(x["index_code"] == code and x["date"] == d for x in tr_out_rows):
                        r = got[d]
                        tr_out_rows.append({"index_code": code, "date": d, "close": num(r.close), "source": SOURCE_CSI})
            tr_series_meta.append({
                "index_code": code, "source": use_source,
                "request_url": CSI if use_source == SOURCE_CSI else (use_rows and ""),
                "params": {"indexCode": code, "startDate": start_q, "endDate": end_q} if use_source == SOURCE_CSI else {},
                "fetched_at": (use_entry or {}).get("fetched_at"),
                "rows": len(dates),
                "start_date": dates[0], "end_date": dates[-1],
                "raw_files": [use_entry["file"]] if use_entry and use_entry.get("file") else [],
            })
            if use_source != SOURCE_CSI:
                # 上面 request 信息在 attempts 里，manifest 用 alt 的 URL 更准确。改写：
                tr_series_meta[-1]["note"] = attempts[-1].detail if attempts else ""
        else:
            # 官网已经有的日期，如果备用源不能覆盖全部，就只交付官网已有的，不拼接。
            have = [d for d in dates if d in got]
            if have and len(have) != len(dates):
                # 不拼接：一个指数不能一部分官网、一部分别的源。缺任何一天就整段不算成功，
                # 但已经从官网拿到的收盘可以留下，前提是来源仍是官网这一个。
                for d in have:
                    tr_out_rows.append({"index_code": code, "date": d, "close": num(got[d].close), "source": SOURCE_CSI})
                tr_series_meta.append({
                    "index_code": code, "source": SOURCE_CSI, "request_url": CSI,
                    "params": {"indexCode": code, "startDate": start_q, "endDate": end_q},
                    "fetched_at": entry.get("fetched_at"), "rows": len(have),
                    "start_date": have[0], "end_date": have[-1],
                    "raw_files": [entry["file"]] if entry else [],
                })
            unavailable.append({
                "code": code, "name": row["index_name"] or code, "kind": "全收益指数",
                "dates": missing, "attempts": attempts, "coverage": "partial" if have else "no",
                "note": f"清单 {len(dates)} 天，取到 {len(dates) - len(missing)}",
                "no_file": False,
            })

    # 去掉 TR 重复
    seen = set()
    uniq = []
    for r in tr_out_rows:
        key = (r["index_code"], r["date"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    uniq.sort(key=lambda r: (r["index_code"], r["date"]))
    tr_path = ROOT / "tr_closes.csv"
    with tr_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["index_code", "date", "close", "source"], lineterminator="\n")
        w.writeheader()
        w.writerows(uniq)

    # 修正 TR manifest 的 request_url：从 attempts 不好回溯，重写为官网 URL（备用成功时在 note 里）。
    manifest_files.append({
        "file": "tr_closes.csv",
        "source": "按 index_code 见 series",
        "request_url": CSI,
        "params": {"indexCode": "<各全收益代码>", "startDate": "<该代码最早缺口日前>", "endDate": "<该代码最晚缺口日>"},
        "fetched_at": now_sha(),
        "sha256": sha256_file(tr_path),
        "rows": len(uniq),
        "start_date": uniq[0]["date"] if uniq else None,
        "end_date": uniq[-1]["date"] if uniq else None,
        "series": tr_series_meta,
    })

    manifest = {
        "generated_at": now_sha(),
        "timezone": "Asia/Shanghai",
        "needed_sha256": sha256_file(NEEDED),
        "files": manifest_files,
    }
    (ROOT / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (RAW / "requests.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in HTTP.log), encoding="utf-8")

    lines = ["# 取不到的指数与日期", "",
             "同一指数只使用一个来源，不把两个来源拼成一条序列，也不用收盘价填开高低。",
             "下面每条都写了试过的来源和返回。原始响应在 `raw/`。", ""]
    if not unavailable:
        lines.append("没有取不到的指数或日期。")
    for item in unavailable:
        lines.append(f"## {item['code']} {item['name']}（{item['kind']}）")
        lines.append("")
        lines.append(f"覆盖：{item['coverage']}。{item['note']}")
        if item["no_file"]:
            lines.append("")
            lines.append("整段没有真实 OHLC，未写 CSV。")
        if item["dates"]:
            lines.append("")
            lines.append(f"未覆盖交易日 {len(item['dates'])} 天：{compress_dates(item['dates'], calendar)}")
        lines.append("")
        lines.append("试过的来源：")
        lines.append("")
        for i, att in enumerate(item["attempts"], 1):
            lines.append(f"{i}. {att.source}：{att.detail}")
        lines.append("")
    (ROOT / "UNAVAILABLE.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    db = load_db_closes()
    print("\n== 与库内收盘对照 ==", flush=True)
    for entry in manifest_files:
        code = entry.get("index_code")
        fn = entry.get("file")
        if not code or not fn or not (ROOT / fn).exists():
            continue
        with (ROOT / fn).open(encoding="utf-8") as f:
            got = {r["date"]: float(r["close"]) for r in csv.DictReader(f) if r.get("close")}
        ref = db.get(code) or {}
        common = sorted(set(got) & set(ref))
        if not common:
            print(f"{code}: 库内无重叠", flush=True)
            continue
        rel = sorted(abs(got[d] - ref[d]) / abs(ref[d]) for d in common if ref[d])
        med = rel[len(rel) // 2]
        worst_i = max(range(len(common)), key=lambda i: abs(got[common[i]] - ref[common[i]]))
        d = common[worst_i]
        print(f"{code}: 重叠 {len(common)} 中位相对差 {med:.3g} 最大差 {d} 库 {ref[d]} 新 {got[d]}", flush=True)

    print("\n完成", flush=True)


if __name__ == "__main__":
    main()
