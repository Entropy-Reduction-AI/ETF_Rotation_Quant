"""S1 跟踪指数：只从已经登记的中证官网接口补发布日和点位。

已有行不覆盖。拿不到发布日或行情的容器保持冻结规则，写进登记表。
"""
from __future__ import annotations

import csv
import json
import re
import sqlite3
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from src.data import db as DB
from src.data import http
from src.data import store
from src.data.hashlog import HashLedger
from src.data.sources import fetch_csindex
from src.v3.data.universe import containers as load_containers

from .diag_d37 import OUT
from .universe import S1_BOND, S1_EXTRA

ROOT = Path(__file__).resolve().parents[2]
CLASSES = ROOT / "config" / "v5" / "classes.csv"
TAIPEI = ZoneInfo("Asia/Taipei")
CSI_INFO = "https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info/{code}"
CSI_HEADERS = {"Referer": "https://www.csindex.com.cn/", "Accept": "application/json"}
CODE_RE = re.compile(r"index-basic-info/([0-9A-Za-z]+)")
BASIS_CODE = re.compile(r"[（(]([0-9A-Za-z]{4,})[）)]")
END = date(2026, 9, 30)
START = date(1990, 1, 1)


def _class_map() -> dict[str, str]:
    frame = pd.read_csv(CLASSES)
    return dict(zip(frame["container_id"], frame["class"]))


def _urls() -> dict[str, str]:
    frame = pd.read_csv(CLASSES)
    return dict(zip(frame["container_id"], frame["source_url"].fillna("")))


def _targets() -> list[dict]:
    classes = _class_map()
    urls = _urls()
    by_id = {str(row.get("id") or ""): row for row in load_containers()}
    rows = []
    for name, kind in sorted(classes.items()):
        if kind not in S1_EXTRA or name == S1_BOND:
            continue
        container = by_id.get(name) or {}
        research = container.get("research") or {}
        source = str(urls.get(name) or research.get("source_url") or "")
        found = CODE_RE.search(source) or CODE_RE.search(str(research.get("publish_date_source") or ""))
        rows.append({
            "container_id": name,
            "class": kind,
            "source_url": source,
            "index_code": found.group(1) if found else "",
            "research_status": str(research.get("series_status") or ""),
        })
    return rows


def _publish(code: str) -> tuple[str, str]:
    payload = http.get_json(CSI_INFO.format(code=code), headers=CSI_HEADERS)
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return "", "中证基本信息没有 data"
    publish = str(data.get("publishDate") or "")[:10]
    name = str(data.get("indexFullNameCn") or data.get("indexNameCn") or "")
    if not publish:
        return "", f"中证基本信息没有发布日（{name}）"
    return publish, name


def _append(con, code: str, rows: list[dict], route: str) -> tuple[bool, str]:
    existing = store.span(con, code, "raw")
    if existing["rows"]:
        source = existing.get("source") or ""
        if source not in {"", route}:
            return False, f"已有序列来自 {source}，不覆盖、不拼接"
        return True, f"已有 {existing['rows']} 行 {existing['first']}→{existing['last']}，不覆盖"
    fetched_at = datetime.now(TAIPEI).isoformat(timespec="seconds")
    store.upsert(con, code, route, rows, fetched_at)
    return True, f"新增 {len(rows)} 行"


def _norm_name(text: str) -> str:
    name = str(text or "")
    for token in ("指数", "人民币", "港元", "港币", "全收益", "净收益", "价格指数", " ", "（", "）", "(", ")"):
        name = name.replace(token, "")
    return name.lower()


def _name_score(left: str, right: str) -> int:
    a, b = _norm_name(left), _norm_name(right)
    if not a or not b or len(a) < 2 or len(b) < 2:
        return 0
    if a == b:
        return 3
    if a in b or b in a:
        return 2
    return 0


def _bar_first(con, code: str) -> str:
    if not code:
        return ""
    row = con.execute("SELECT min(date) FROM bars WHERE code = ? AND adj = 'raw' AND close > 0", (code,)).fetchone()
    return str(row[0] or "")[:10] if row else ""


def _nav_first(con, code: str) -> str:
    if not code:
        return ""
    row = con.execute("SELECT min(date) FROM fund_nav WHERE code = ? AND unit_nav > 0", (code,)).fetchone()
    return str(row[0] or "")[:10] if row else ""


def _signal_first(con, container: dict) -> str:
    research = container.get("research") or {}
    code = str(research.get("series_code") or "").strip()
    executions = container.get("execution") or []
    traded = str(executions[0].get("code") or "").strip() if executions else ""
    asset = str(container.get("asset_class") or "")
    basis = str(research.get("return_basis") or "")
    if asset == "美股和全球主题" or basis == "unit_nav":
        return _nav_first(con, traded or code) or _bar_first(con, traded or code)
    return _bar_first(con, code)


def _basis_codes() -> dict[str, str]:
    frame = pd.read_csv(CLASSES)
    found = {}
    for _, row in frame.iterrows():
        blob = " ".join(str(row.get(key) or "") for key in ("basis", "source_url"))
        codes = BASIS_CODE.findall(blob) or CODE_RE.findall(blob)
        if codes:
            found[str(row["container_id"])] = codes[0]
    return found


def _suggest(name: str) -> list[dict]:
    raw = http.get(
        "https://searchapi.eastmoney.com/api/suggest/get",
        {"input": name, "type": "14", "count": "20"},
        headers={"Referer": "https://www.eastmoney.com/"},
        timeout=20,
    )
    payload = json.loads(raw.decode("utf-8", "replace"))
    rows = ((payload.get("QuotationCodeTable") or {}).get("Data") or [])
    return [row for row in rows if isinstance(row, dict)]


def _csi_identity(code: str) -> tuple[str, str]:
    payload = http.get_json(CSI_INFO.format(code=code), headers=CSI_HEADERS, timeout=20)
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return "", ""
    publish = str(data.get("publishDate") or "")[:10]
    full = str(data.get("indexFullNameCn") or data.get("indexNameCn") or "")
    return publish, full


def _rows_on_or_after(rows: list[dict], publish: str) -> list[dict]:
    kept = []
    for row in rows:
        day = str(row.get("date") or "")[:10]
        if day and publish and day >= publish and day <= END.isoformat():
            kept.append(row)
    return kept


def _excel_day(serial: str) -> str:
    from datetime import timedelta
    return (date(1899, 12, 30) + timedelta(days=int(float(serial)))).isoformat()


def _xlsx_table(raw: bytes) -> list[dict]:
    import io
    import zipfile
    from xml.etree import ElementTree as ET
    if not raw.startswith(b"PK"):
        return []
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    tag = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(raw)) as book:
        strings = []
        if "xl/sharedStrings.xml" in book.namelist():
            shared = ET.fromstring(book.read("xl/sharedStrings.xml"))
            for item in shared.findall("m:si", ns):
                strings.append("".join(node.text or "" for node in item.iter(tag + "t")))
        sheet = ET.fromstring(book.read("xl/worksheets/sheet1.xml"))
        table = []
        for row in sheet.findall("m:sheetData/m:row", ns):
            values = []
            for cell in row.findall("m:c", ns):
                node = cell.find("m:v", ns)
                if node is None or node.text is None:
                    values.append("")
                elif cell.attrib.get("t") == "s":
                    values.append(strings[int(node.text)])
                else:
                    values.append(node.text)
            if any(values):
                table.append(values)
    if len(table) < 2:
        return []
    header = [str(item).strip() for item in table[0]]
    parsed = []
    for values in table[1:]:
        record = dict(zip(header, values))
        serial = str(record.get("Trade Date") or "")
        close = record.get("Index Value")
        if not serial or close in {None, ""}:
            continue
        day = _excel_day(serial) if serial.replace(".", "", 1).isdigit() else str(serial)[:10]
        parsed.append({
            "date": day,
            "open": record.get("High") and None,
            "high": record.get("High"),
            "low": record.get("Low"),
            "close": close,
            "volume": None,
            "amount": None,
        })
    parsed.sort(key=lambda item: item["date"])
    return parsed


def _nasdaq_quote(symbol: str, start: date, end: date) -> list[dict]:
    raw = http.get(
        f"https://api.nasdaq.com/api/quote/{symbol}/historical",
        {"assetclass": "index", "fromdate": start.isoformat(), "todate": end.isoformat(), "limit": "9999"},
        headers={"Referer": "https://www.nasdaq.com/", "Accept": "application/json"},
        timeout=40,
    )
    payload = json.loads(raw.decode("utf-8", "replace"))
    rows = (((payload.get("data") or {}).get("tradesTable") or {}).get("rows") or [])
    parsed = []
    for row in rows:
        parts = str(row.get("date") or "").split("/")
        if len(parts) != 3:
            continue
        month, day, year = parts
        def num(key: str):
            text = str(row.get(key) or "").replace(",", "").strip()
            if text in {"", "--", "N/A"}:
                return None
            return text
        parsed.append({
            "date": f"{int(year):04d}-{int(month):02d}-{int(day):02d}",
            "open": num("open"), "high": num("high"), "low": num("low"), "close": num("close"),
            "volume": num("volume"), "amount": None,
        })
    parsed.sort(key=lambda item: item["date"])
    return parsed


def _nasdaq_began(symbol: str) -> tuple[str, str]:
    url = f"https://indexes.nasdaqomx.com/Index/Overview/{symbol}"
    raw = http.get(url, headers={"Referer": "https://indexes.nasdaqomx.com/"}, timeout=30)
    text = raw.decode("utf-8", "replace")
    match = re.search(r"began on ([A-Z][a-z]+ \d{1,2}, \d{4})", text)
    if not match:
        return "", url
    published = datetime.strptime(match.group(1), "%B %d, %Y").date().isoformat()
    return published, url


def _nasdaq_export(symbol: str, start: date, end: date) -> list[dict]:
    rows = []
    for year in range(start.year, end.year + 1):
        began = max(start, date(year, 1, 1))
        stop = min(end, date(year, 12, 31))
        raw = http.get(
            f"https://indexes.nasdaqomx.com/Index/ExportHistory/{symbol}",
            {"startDate": began.isoformat(), "endDate": stop.isoformat(), "timeOfDay": "EOD"},
            headers={"Referer": f"https://indexes.nasdaqomx.com/Index/History/{symbol}"},
            timeout=60,
        )
        rows.extend(_xlsx_table(raw))
        time.sleep(0.2)
    dedup = {row["date"]: row for row in rows}
    return [dedup[day] for day in sorted(dedup)]


def _first_export_year(symbol: str) -> int | None:
    for year in range(2018, END.year + 1):
        raw = http.get(
            f"https://indexes.nasdaqomx.com/Index/ExportHistory/{symbol}",
            {"startDate": f"{year}-01-01", "endDate": f"{year}-01-20", "timeOfDay": "EOD"},
            headers={"Referer": "https://indexes.nasdaqomx.com/"},
            timeout=40,
        )
        if raw.startswith(b"PK"):
            return year
        time.sleep(0.15)
    return None


def _blank(row: dict, status: str, reason: str, tried: list[str]) -> dict:
    row["status"] = status
    row["reason"] = reason
    row["publish_date"] = row.get("publish_date") or ""
    row["bars_code"] = row.get("bars_code") or ""
    row["currency"] = row.get("currency") or ""
    row["tried_urls"] = " | ".join(tried)
    return row


def _resolve_csi(name: str, hinted: str, tried: list[str]) -> tuple[str, str, str]:
    """返回 (代码, 发布日, 官网全称)。对不上全称就当没找到。"""
    candidates = []
    if hinted:
        candidates.append(hinted)
    queries = [name]
    short = name
    for token in ("中证", "上证", "指数", "人民币", "港元", "港币"):
        short = short.replace(token, "")
    short = short.strip()
    if short and short not in queries:
        queries.append(short)
    try:
        for query in queries:
            for item in _suggest(query):
                if str(item.get("SecurityTypeName") or "") != "指数":
                    continue
                code = str(item.get("Code") or "")
                if _name_score(name, str(item.get("Name") or "")) == 0 and _name_score(query, str(item.get("Name") or "")) == 0:
                    continue
                if code and code not in candidates:
                    candidates.append(code)
        tried.append("https://searchapi.eastmoney.com/api/suggest/get?type=14")
    except Exception as exc:
        tried.append(f"suggest失败:{type(exc).__name__}")
    best = ("", "", "")
    best_score = 0
    for code in candidates:
        if not re.fullmatch(r"[0-9A-Za-z]{4,12}", code):
            continue
        url = CSI_INFO.format(code=code)
        tried.append(url)
        try:
            publish, full = _csi_identity(code)
        except Exception:
            continue
        score = _name_score(name, full)
        if hinted and code == hinted and score == 0 and full:
            score = 2
        if publish and score > 0 and (score > best_score or (score == best_score and (not best[0] or code < best[0]))):
            best = (code, publish, full)
            best_score = score
    return best


def _fetch_named(container_id: str, tried: list[str]) -> tuple[str, str, str, str, list[dict], str]:
    """非中证的点名指数。返回 code, publish, currency, route, rows, note。失败时 rows 为空。"""
    if container_id == "theme-PHLX Semiconductor Sector Index":
        publish, url = _nasdaq_began("SOX")
        tried.append(url)
        quote = "https://api.nasdaq.com/api/quote/SOX/historical"
        tried.append(quote)
        if not publish:
            return "", "", "USD", "nasdaq_index", [], "纳斯达克总览页没有 began on 发布日"
        rows = _rows_on_or_after(_nasdaq_quote("SOX", date(2000, 1, 1), END), publish)
        note = "容器基准里费城半导体占 70%。拼接 SOX 价格指数，不是 70/20/10 混合净值。2006 年前没有已登记美元汇率的日子在对齐时自然空掉。"
        return "SOX", publish, "USD", "nasdaq_index", rows, note
    if container_id == "theme-纳斯达克生物科技指数":
        publish, url = _nasdaq_began("NBI")
        tried.append(url)
        tried.append("https://api.nasdaq.com/api/quote/NBI/historical")
        if not publish:
            return "", "", "USD", "nasdaq_index", [], "纳斯达克总览页没有 began on 发布日"
        rows = _rows_on_or_after(_nasdaq_quote("NBI", date(2000, 1, 1), END), publish)
        return "NBI", publish, "USD", "nasdaq_index", rows, "纳斯达克生物科技价格指数。美元点位乘已登记 USDCNY。"
    if container_id == "theme-纳斯达克科技市值加权指数":
        tried.append("https://indexes.nasdaqomx.com/Index/Overview/NDXTMC")
        tried.append("https://indexes.nasdaqomx.com/Index/ExportHistory/NDXTMC")
        year = _first_export_year("NDXTMC")
        if year is None:
            return "", "", "USD", "nasdaq_index", [], "NDXTMC 的 ExportHistory 从 2018 年到检验段结束都是空的"
        publish = f"{year}-01-01"
        rows = _rows_on_or_after(_nasdaq_export("NDXTMC", date(year, 1, 1), END), publish)
        if rows:
            publish = rows[0]["date"]
            rows = _rows_on_or_after(rows, publish)
        note = "ExportHistory 在更早的年份为空，第一根官方点位当作可用起点。价格指数，美元乘 USDCNY。不用纳斯达克 100 科技行业（NDXT），那是另一条指数。"
        return "NDXTMC", publish, "USD", "nasdaq_index", rows, note
    if container_id == "theme-东京日经225指数":
        url = "https://indexes.nikkei.co.jp/nkave/historical/nikkei_stock_average_daily_en.csv"
        tried.append(url)
        tried.append("https://indexes.nikkei.co.jp/nkave/archives/data")
        raw = http.get(url, headers={"Referer": "https://indexes.nikkei.co.jp/"}, timeout=30)
        text = raw.decode("utf-8", "replace")
        days = re.findall(r"(\d{4}/\d{2}/\d{2})", text)
        first = min(day.replace("/", "-") for day in days) if days else ""
        return "", first, "LOCAL", "", [], f"官方日线 CSV 最早 {first or '没有日期'}，晚于或不够覆盖首只基金上市前。库内 N225 来自 yahoo，不用来拼接。"
    probes = {
        "theme-法兰克福DAX指数": [
            "https://www.stoxx.com/index-details?symbol=DAX",
            "https://www.dax-indices.com/",
            "https://api.boerse-frankfurt.de/v1/tradingview/lightweight/history/line?symbol=DE0008469008",
        ],
        "theme-法国CAC40指数": [
            "https://live.euronext.com/en/product/indices/FR0003500008-XPAR",
            "https://live.euronext.com/en/ajax/AwlHistoricalPrice/getChartData/FR0003500008-XPAR",
        ],
        "theme-巴西IBOVESPA指数": [
            "https://www.b3.com.br/en_us/market-data-and-indices/indexes/broad-indexes/ibovespa.htm",
        ],
        "theme-东证指数": [
            "https://www.jpx.co.jp/english/markets/indices/topix/index.html",
        ],
        "theme-道琼斯工业平均指数": [
            "https://api.nasdaq.com/api/quote/DJI/historical?assetclass=index",
            "https://www.spglobal.com/spdji/en/indices/equity/dow-jones-industrial-average/",
        ],
        "soymeal": [
            "https://www.dce.com.cn/",
            "https://www.dce.com.cn/dalianshangpin/xqsj/tjsj26/rtj/index.html",
        ],
    }
    for url in probes.get(container_id, []):
        tried.append(url)
        try:
            http.get(url, headers={"Referer": url}, timeout=20)
        except Exception as exc:
            tried.append(f"{type(exc).__name__}:{str(exc)[:80]}")
    return "", "", "", "", [], ""


def _candidate_rows(con) -> list[dict]:
    from .s1_scope import first_list_date, series_truncated_at_listing

    classes = _class_map()
    urls = _urls()
    hinted = _basis_codes()
    by_id = {str(row.get("id") or ""): row for row in load_containers()}
    rows = []
    seen = set()
    for name, kind in sorted(classes.items()):
        container = by_id.get(name)
        if container is None:
            rows.append({
                "container_id": name, "class": kind, "source_url": urls.get(name, ""),
                "index_code": "", "index_name": "", "first_list": "", "series_first": "",
                "status": "frozen", "publish_date": "", "bars_code": "", "currency": "",
                "reason": "大类表有这一行，冻结 universe 没有这个容器，诊断不新开容器。",
                "tried_urls": "",
            })
            continue
        if name == S1_BOND or str(container.get("asset_class") or "") == "现金":
            continue
        listed = first_list_date(container)
        first_list = "" if listed is None else listed.date().isoformat()
        started = _signal_first(con, container)
        index_name = str((container.get("research") or {}).get("index_name") or name)
        item = {
            "container_id": name, "class": kind,
            "source_url": urls.get(name) or str((container.get("research") or {}).get("source_url") or ""),
            "index_code": hinted.get(name, ""), "index_name": index_name,
            "first_list": first_list, "series_first": started,
            "status": "", "publish_date": "", "bars_code": "", "currency": "CNY",
            "reason": "", "tried_urls": "",
        }
        if not series_truncated_at_listing(started, first_list):
            item["status"] = "already"
            item["reason"] = "研究序列已经早于首只场内基金。发布日之前的回填不接。"
            rows.append(item)
            continue
        if index_name in {"该基金无跟踪标的", "跨境商品"} or name in {"cross-border-commodity", "crude-oil", "theme-中信证券印度ETP指数", "theme-巴克莱资本美国综合债券指数"}:
            item["status"] = "frozen"
            item["reason"] = "没有单一跟踪指数，或基准不是一条期货价格指数，不拼。"
            rows.append(item)
            continue
        rows.append(item)
        seen.add(name)
    return rows


_PROBED: dict[str, str] = {}


def _probe(url: str) -> str:
    if url in _PROBED:
        return _PROBED[url]
    try:
        raw = http.get(url, headers={"Referer": "https://www.google.com/"}, timeout=20)
        _PROBED[url] = f"ok:{len(raw)}"
    except Exception as exc:
        _PROBED[url] = f"{type(exc).__name__}:{str(exc)[:80]}"
    return _PROBED[url]


def _family_probes(index_name: str, tried: list[str]) -> str:
    families = []
    if "恒生" in index_name:
        families.append((
            "恒生公司历史日线仍不可用，不用腾讯替代。",
            [
                "https://www.hsi.com.hk/static/uploads/contents/en/indexes/report/hscei.csv",
                "https://www.hsi.com.hk/data/eng/indexes/hstech/chart.json",
            ],
        ))
    if "富时" in index_name or "FTSE" in index_name.upper():
        families.append((
            "富时罗素事实表没有可入库的日线。",
            ["https://research.ftserussell.com/Analytics/Factsheets/Home/DownloadSingleIssue?issueName=GPCSP006"],
        ))
    if "标普" in index_name or "S&P" in index_name:
        families.append((
            "标普道琼斯指数页面没有匿名日线。",
            ["https://www.spglobal.com/spdji/en/indices/equity/sp-500-information-technology-sector/"],
        ))
    if "iEdge" in index_name or "新交所" in index_name:
        families.append((
            "新交所事实表没有可入库的日线。",
            ["https://api2.sgx.com/sites/default/files/2026-09/iEdge%20EM%20Asia_Factsheet_20260831.pdf"],
        ))
    notes = []
    for sentence, urls in families:
        for url in urls:
            tried.append(f"{url} {_probe(url)}")
        notes.append(sentence)
    return " ".join(notes)


def _fill_candidate(con, row: dict) -> dict:
    if row.get("status") in {"already", "frozen"} and row.get("reason"):
        return row
    tried: list[str] = []
    name = str(row.get("index_name") or "")
    code, publish, full = _resolve_csi(name, str(row.get("index_code") or ""), tried)
    listed = str(row.get("first_list") or "")
    if code and publish and listed and publish < listed:
        existing = store.span(con, code, "raw")
        if existing["rows"] and existing.get("source") in {"", "csindex"}:
            ok, note = _append(con, code, [], "csindex")
        else:
            try:
                fetched = fetch_csindex(code, date.fromisoformat(publish), END, pause=0.2)
            except Exception as exc:
                return _blank(row, "frozen", f"有发布日 {publish}（{full}），中证行情取不到：{type(exc).__name__}: {exc}"[:240], tried)
            kept = _rows_on_or_after(fetched.rows, publish)
            if not kept:
                return _blank(row, "frozen", f"有发布日 {publish}（{full}），发布日之后没有行情", tried)
            ok, note = _append(con, code, kept, "csindex")
        row["index_code"] = code
        row["publish_date"] = publish
        row["bars_code"] = code if ok else ""
        row["currency"] = "CNY"
        row["status"] = "spliced" if ok else "frozen"
        row["reason"] = f"{full}；{note}。只入库发布日 {publish} 及之后的点位。"
        row["tried_urls"] = " | ".join(tried)
        return row
    if code and publish and listed and publish >= listed:
        row["index_code"] = code
        row["publish_date"] = publish
        return _blank(row, "frozen", f"中证 {code}（{full}）发布日 {publish} 不早于首只基金 {listed}", tried)
    named = _fetch_named(str(row["container_id"]), tried)
    ncode, npublish, currency, route, nrows, note = named
    if ncode and npublish and listed and npublish < listed and nrows:
        ok, appended = _append(con, ncode, nrows, route)
        row["index_code"] = ncode
        row["publish_date"] = npublish
        row["bars_code"] = ncode if ok else ""
        row["currency"] = currency
        row["status"] = "spliced" if ok else "frozen"
        row["reason"] = f"{note} {appended}".strip()
        row["tried_urls"] = " | ".join(tried)
        return row
    page = str(row.get("source_url") or "")
    if page:
        tried.append(page)
    extra = _family_probes(str(row.get("index_name") or ""), tried)
    if note:
        return _blank(row, "frozen", note, tried)
    return _blank(row, "frozen", extra or "官网没有取到正式发布日及之后、且早于首只基金的价格指数", tried)


def sync() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    http.RECORD_DIR = OUT / "sources"
    ledger = HashLedger(DB.MARKET_DB)
    before = ledger.before("d37-s1-index")
    if not DB.MARKET_DB.is_file() or DB.MARKET_DB.stat().st_size < 1000:
        raise FileNotFoundError(DB.MARKET_DB)
    blob = DB.MARKET_DB.read_bytes()[:80]
    if blob.startswith(b"version https://git-lfs.github.com/spec/v1"):
        raise RuntimeError("行情库还是 LFS 指针")
    con = sqlite3.connect(str(DB.MARKET_DB))
    written = []
    try:
        targets = _candidate_rows(con)
        for row in targets:
            if row.get("status") in {"already", "frozen"} and row.get("reason"):
                continue
            print(f"splice {row['container_id']}", flush=True)
            _fill_candidate(con, row)
            if row.get("status") == "spliced" and row.get("bars_code"):
                written.append(str(row["bars_code"]))
    finally:
        con.close()
    after = ledger.after("d37-s1-index")
    fieldnames = [
        "container_id", "class", "status", "index_code", "publish_date", "bars_code",
        "currency", "first_list", "series_first", "source_url", "tried_urls", "reason",
    ]
    for row in targets:
        row.setdefault("status", "frozen")
        row.setdefault("publish_date", "")
        row.setdefault("bars_code", "")
        row.setdefault("currency", "")
        row.setdefault("reason", "")
        row.setdefault("tried_urls", "")
    registry = OUT / "s1-index-registry.csv"
    with registry.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(targets)
    (OUT / "s1-splice-roster.csv").write_text(registry.read_text(encoding="utf-8"), encoding="utf-8")
    sha_path = OUT / "db-sha256.txt"
    sha_path.write_text(
        f"SHA256 BEFORE d37-s1-index {before}\nSHA256 AFTER  d37-s1-index {after}\n",
        encoding="utf-8",
    )
    if after != before:
        log = ROOT / "results" / "inventory" / "db-writes.txt"
        with log.open("a", encoding="utf-8") as handle:
            handle.write(f"SHA256 BEFORE d37-s1-index {before}\n")
            handle.write(f"SHA256 AFTER  d37-s1-index {after}\n")
    return {"before": before, "after": after, "spliced": written, "rows": len(targets)}


def main() -> int:
    summary = sync()
    print(f"before={summary['before']} after={summary['after']} spliced={','.join(summary['spliced']) or '-'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
