"""v4-R1e：上交所、深交所场内 QDII ETF / LOF 普查，并只插入缺的行情和净值。

不算收益，不覆盖已有行。登记表由 r1e_register 机械改写。
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
import ssl
import time
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.data import db as DB
from src.data import fund_nav
from src.data import http
from src.data.sources import EM_KLINE
from src.v3.data import coverage
from src.v3.data import parse
from src.v3.data import universe as U
from src.v4.data.r1b_parse import parse_eastmoney_klines, parse_pingzhongdata

from .r1e_parse import (
    alpha_code,
    commodity_bucket,
    group_funds,
    heaviest_benchmark_index,
    is_qdii_row,
    iso_date,
    management_style,
    split_bilingual,
    szse_code_name,
    table_dicts,
    xlsx_table,
)
from .r1e_register import apply_register, apply_v4

ROOT = Path(__file__).resolve().parents[3]
INCOMING = ROOT / "incoming" / "2026-10-29-v4-r1e"
OUT = ROOT / "results" / "v4" / "inventory" / "r1e"
NAV_END = "2026-09-30"
V3_PATH = ROOT / "config" / "v3" / "universe.toml"
V4_PATH = ROOT / "config" / "v4" / "universe.toml"
SSE_LIST = "https://query.sse.com.cn/commonSoaQuery.do"
SZSE_XLSX = "https://www.szse.cn/api/report/ShowReport"
PING = "https://fund.eastmoney.com/pingzhongdata/{code}.js"
JBGK = "https://fundf10.eastmoney.com/jbgk_{code}.html"
CATALOG = "https://fund.eastmoney.com/js/fundcode_search.js"
HFQ_SOURCE = "eastmoney_etf_hfq"
RAW_SOURCE = "eastmoney_etf"
NAV_SOURCE = "eastmoney_pingzhongdata"

CENSUS_COLUMNS = (
    "exchange", "code", "name", "vehicle", "list_date", "delist_date", "list_status",
    "passive_active", "index_code", "index_name", "english_name", "benchmark",
    "benchmark_index", "benchmark_weight", "commodity", "converted", "include_reason",
    "source_url", "profile_url",
)
DIFF_COLUMNS = (
    "code", "name", "exchange", "v3_status", "v3_container", "v4_status",
    "group_key", "group_name", "group_rule", "target_id", "d19_action",
)
GROUP_COLUMNS = (
    "group_key", "group_name", "group_rule", "target_id", "asset_class", "codes", "names",
)
FILL_COLUMNS = (
    "code", "kind", "status", "inserted", "kept", "first", "last", "source", "source_url",
    "sha256", "reason",
)


def _gz(path: Path, raw: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wb") as handle:
        handle.write(raw)
    return hashlib.sha256(raw).hexdigest()


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def fetch(url: str, params: dict | None = None, *, headers: dict | None = None, timeout: int = 40,
         retries: int = 1) -> bytes:
    """先走项目里的 HTTP。深交所拒 TLS 1.3 时退到 TLS 1.2，仍留下请求记录。"""
    try:
        return http.get(url, params, headers=headers, timeout=timeout, retries=retries)
    except http.FetchError:
        return _fetch_tls12(url, params, headers=headers, timeout=timeout)


def _fetch_tls12(url: str, params: dict | None, *, headers: dict | None, timeout: int) -> bytes:
    if params:
        url = f"{url}{'&' if '?' in url else '?'}{urlencode(params)}"
    context = ssl.create_default_context()
    context.maximum_version = ssl.TLSVersion.TLSv1_2
    request = Request(url, headers={"User-Agent": http.UA, "Accept": "*/*", "Accept-Encoding": "gzip", **(headers or {})})
    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            raw = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        http._record(url, None, f"{type(exc).__name__}: {str(exc)[:160]}")
        raise http.FetchError(f"{type(exc).__name__}: {str(exc)[:160]}  ← {url[:160]}") from exc
    http._record(url, raw, None)
    return raw


def _sse_pages(fund_type: str, sub_class: str) -> list[dict]:
    got: list[dict] = []
    total = None
    for page in range(1, 30):
        params = {
            "isPagination": "true",
            "sqlId": "FUND_LIST",
            "fundType": fund_type,
            "subClass": sub_class,
            "pageHelp.pageSize": "500",
            "pageHelp.pageNo": str(page),
            "pageHelp.beginPage": str(page),
            "pageHelp.cacheSize": "1",
            "pageHelp.endPage": str(page),
        }
        raw = fetch(SSE_LIST, params, headers={"Referer": "https://www.sse.com.cn/assortment/fund/list/"}, timeout=40)
        _gz(INCOMING / "raw" / "sse" / f"fund-list-{fund_type}-{page}.json.gz", raw)
        payload = json.loads(_decode(raw))
        rows = payload.get("result") or []
        page_help = payload.get("pageHelp") or {}
        if page_help.get("total") is not None:
            total = int(page_help["total"])
        if not rows:
            break
        got.extend(rows)
        if (total is not None and len(got) >= total) or len(rows) < 500:
            break
        time.sleep(0.2)
    if total is not None and len(got) < total:
        raise http.FetchError(f"上交所基金列表没收全：{len(got)} / {total} fundType={fund_type}")
    return got


def _sse_row(item: dict) -> dict:
    vehicle = "LOF" if str(item.get("fundType")) == "10" else "ETF"
    return {
        "exchange": "SSE",
        "code": str(item.get("fundCode") or ""),
        "name": item.get("secNameFull") or item.get("fundAbbr") or "",
        "full_name": item.get("secNameFull") or "",
        "vehicle": vehicle,
        "list_date": iso_date(str(item.get("listingDate") or "")),
        "delist_date": "",
        "list_status": "listed",
        "index_code": (item.get("INDEX_CODE") or "").strip(),
        "index_name": (item.get("INDEX_NAME") or "").strip(),
        "english_name": "",
        "benchmark": "",
        "sub_class": str(item.get("subClass") or ""),
        "fund_type": "",
        "converted": "1" if "转型" in (item.get("secNameFull") or "") else "0",
        "source_url": SSE_LIST + "?sqlId=FUND_LIST",
        "profile_url": "",
    }


def _szse_xlsx(catalog: str) -> list[dict]:
    raw = fetch(SZSE_XLSX, {"SHOWTYPE": "xlsx", "CATALOGID": catalog, "TABKEY": "tab1"},
                headers={"Referer": "https://www.szse.cn/"}, timeout=60)
    path = INCOMING / "raw" / "szse" / f"{catalog}.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return table_dicts(xlsx_table(raw))


def _catalog() -> dict[str, str]:
    raw = fetch(CATALOG, headers={"Referer": "https://fund.eastmoney.com/"}, timeout=60)
    _gz(INCOMING / "raw" / "eastmoney" / "fundcode_search.js.gz", raw)
    types = {}
    for row in parse.parse_fund_catalog(_decode(raw)):
        types[row["code"]] = row["fund_type"]
    return types


def _profile(code: str) -> dict:
    path = INCOMING / "raw" / "jbgk" / f"{code}.html.gz"
    if path.exists():
        raw = gzip.open(path, "rb").read()
    else:
        raw = fetch(JBGK.format(code=code), headers={"Referer": "https://fundf10.eastmoney.com/"}, timeout=30)
        _gz(path, raw)
        time.sleep(0.12)
    html = _decode(raw)
    profile = parse.parse_jbgk(html)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    match = re.search(r"终止上市(?:日期|日)?[:：\s]*(\d{4}-\d{2}-\d{2}|\d{4}年\d{1,2}月\d{1,2}日)", text)
    profile["delist_date"] = iso_date(match.group(1)) if match else ""
    profile["converted"] = "1" if ("已转型" in text or "转型为" in text) else "0"
    profile["path"] = str(path.relative_to(ROOT))
    return profile


def _apply_profile(row: dict, profile: dict) -> None:
    row["full_name"] = profile.get("full_name") or row.get("full_name") or row.get("name")
    if row["full_name"] and row["full_name"] != row.get("name"):
        row["name"] = row["full_name"]
    row["fund_type"] = profile.get("fund_type") or row.get("fund_type") or ""
    if not row.get("index_name"):
        row["index_name"] = profile.get("track") or ""
    cell = profile.get("track_cell") or ""
    _chinese, english = split_bilingual(cell) if cell else ("", "")
    if not english and re.search(r"[A-Za-z]{3}", cell):
        english = cell
    if english and not row.get("english_name"):
        row["english_name"] = english
    row["benchmark"] = profile.get("benchmark") or ""
    if not row.get("list_date"):
        row["list_date"] = profile.get("list_date") or ""
    if profile.get("delist_date"):
        row["delist_date"] = profile["delist_date"]
    if profile.get("converted") == "1":
        row["converted"] = "1"
    row["profile_url"] = JBGK.format(code=row["code"])
    row["profile_path"] = profile.get("path") or ""


def _benchmark_fields(row: dict) -> None:
    heavy = heaviest_benchmark_index(row.get("benchmark") or "")
    row["benchmark_index"] = heavy["name"] if heavy else ""
    row["benchmark_english"] = heavy["english"] if heavy else ""
    row["benchmark_weight"] = "" if not heavy or heavy["weight"] is None else heavy["weight"]
    if heavy and heavy["english"]:
        row["english_name"] = heavy["english"]


def _needs_profile(row: dict) -> bool:
    if management_style(row, row.get("fund_type") or "") == "active":
        return True
    if not row.get("index_name") and not alpha_code(row.get("index_code") or ""):
        return True
    if not row.get("list_date"):
        return True
    return False


def load_membership() -> tuple[dict[str, str], dict[str, str], set[str], set[str]]:
    """主臂执行代码 → 容器，上市日，排除注释里的代码，v4 里的六位代码。"""
    doc = U.load(V3_PATH)
    execution: dict[str, str] = {}
    listed: dict[str, str] = {}
    for box in doc.get("container") or []:
        if box.get("arm") not in {None, "main"}:
            continue
        for item in box.get("execution") or []:
            code = str(item.get("code") or "")
            if re.fullmatch(r"\d{6}", code):
                execution[code] = box["id"]
                listed[code] = str(item.get("list_date") or "")
    excluded = set()
    for line in V3_PATH.read_text(encoding="utf-8").splitlines():
        match = re.match(r"# (\d{6}) .*exclude:", line)
        if match:
            excluded.add(match.group(1))
    v4_codes = set(re.findall(r'(?m)^code = "(\d{6})"', V4_PATH.read_text(encoding="utf-8")))
    return execution, listed, excluded, v4_codes


def _known_ids() -> set[str]:
    return {box["id"] for box in U.containers()}


def census() -> list[dict]:
    """交易所现行名单，加上代码表里有上市日、但不在现行名单上的场内 QDII。"""
    types = _catalog()
    sse = _sse_pages("00", "01,02,03,04,06,08,09,31,32,33,34,35,36,37,38")
    sse += _sse_pages("10", "11,12,13,14,15")
    listed_rows = [_sse_row(item) for item in sse if item.get("fundCode")]
    szse_all = _szse_xlsx("1105")
    szse_etf = _szse_xlsx("1945")
    try:
        szse_lof = _szse_xlsx("1945_LOF")
    except (http.FetchError, zipfile.BadZipFile, json.JSONDecodeError):
        szse_lof = []
    index_by_code = {}
    for row in szse_etf:
        code, _name = szse_code_name(row)
        index = ""
        for key, value in row.items():
            if "拟合" in key or "指数" in key:
                index = (value or "").strip()
        if code:
            index_by_code[code] = index
    seen = {row["code"] for row in listed_rows}
    for row in szse_all:
        code, name = szse_code_name(row)
        if not code or code in seen:
            continue
        kind = ""
        list_date = ""
        for key, value in row.items():
            if "类别" in key and "投资" not in key:
                kind = value
            if "上市" in key:
                list_date = iso_date(value)
        vehicle = "LOF" if "LOF" in f"{kind} {name}" else "ETF" if "ETF" in f"{kind} {name}" else (kind or "")
        listed_rows.append({
            "exchange": "SZSE",
            "code": code,
            "name": name,
            "full_name": name,
            "vehicle": vehicle,
            "list_date": list_date,
            "delist_date": "",
            "list_status": "listed",
            "index_code": index_by_code.get(code) or "",
            "index_name": "",
            "english_name": "",
            "benchmark": "",
            "sub_class": "",
            "fund_type": types.get(code) or "",
            "converted": "1" if "转型" in name else "0",
            "source_url": SZSE_XLSX + "?SHOWTYPE=xlsx&CATALOGID=1105&TABKEY=tab1",
            "profile_url": "",
        })
        seen.add(code)
    _ = szse_lof
    included = []
    for row in listed_rows:
        row["fund_type"] = row.get("fund_type") or types.get(row["code"]) or ""
        keep, why = is_qdii_row(row, types.get(row["code"]) or "")
        if not keep:
            continue
        row["include_reason"] = why
        included.append(row)
    listed_codes = {row["code"] for row in included}
    for code, kind in sorted(types.items()):
        if code in seen or not parse.exchange_code(code):
            continue
        stub = {"code": code, "name": "", "full_name": "", "index_name": "", "sub_class": "", "fund_type": kind}
        keep, why = is_qdii_row(stub, kind)
        if not keep:
            continue
        included.append({
            "exchange": "SZSE" if code.startswith(("15", "16")) else "SSE",
            "code": code,
            "name": "",
            "full_name": "",
            "vehicle": "",
            "list_date": "",
            "delist_date": "",
            "list_status": "not_on_exchange_list",
            "index_code": "",
            "index_name": "",
            "english_name": "",
            "benchmark": "",
            "sub_class": "",
            "fund_type": kind,
            "converted": "0",
            "include_reason": why,
            "source_url": CATALOG,
            "profile_url": "",
        })
    confirmed = []
    for row in included:
        if row["code"] in listed_codes and not _needs_profile(row):
            _benchmark_fields(row)
            row["passive_active"] = management_style(row, row.get("fund_type") or "")
            confirmed.append(row)
            continue
        print(f"profile {row['code']} {row.get('list_status')}", flush=True)
        try:
            profile = _profile(row["code"])
        except (http.FetchError, ValueError) as exc:
            row["profile_error"] = str(exc)[:180]
            if row["list_status"] == "listed":
                _benchmark_fields(row)
                row["passive_active"] = management_style(row, row.get("fund_type") or "")
                confirmed.append(row)
            continue
        _apply_profile(row, profile)
        if row["list_status"] != "listed":
            if not row.get("list_date"):
                continue
            row["list_status"] = "delisted" if row.get("delist_date") else "absent_from_exchange_list"
            row["exchange"] = "SZSE" if row["code"].startswith(("15", "16")) else "SSE"
        _benchmark_fields(row)
        keep, why = is_qdii_row(row, row.get("fund_type") or types.get(row["code"]) or "")
        if not keep:
            continue
        row["include_reason"] = row.get("include_reason") or why
        row["passive_active"] = management_style(row, row.get("fund_type") or "")
        if commodity_bucket(row.get("name") or "", row.get("fund_type") or "", row.get("index_name") or ""):
            row["include_reason"] = "cross_border_commodity"
        confirmed.append(row)
    grouped = group_funds(confirmed)
    for row in grouped:
        row["passive_active"] = row.get("passive_active") or management_style(row, row.get("fund_type") or "")
    return grouped


def _targets(rows: list[dict], execution: dict[str, str], known_ids: set[str]) -> dict[str, tuple[str, bool]]:
    members: dict[str, list[dict]] = {}
    for row in rows:
        members.setdefault(row["group_key"], []).append(row)
    planned = {}
    for key, group in members.items():
        if key in {"gold", "crude-oil", "soymeal"}:
            planned[key] = (key, False)
            continue
        if key in {"silver", "cross-border-commodity"}:
            planned[key] = (key, key not in known_ids)
            continue
        holders = [execution[row["code"]] for row in group if row["code"] in execution]
        if holders:
            counts = Counter(holders)
            best_n = max(counts.values())
            target = sorted(cid for cid, count in counts.items() if count == best_n)[0]
            planned[key] = (target, False)
            continue
        target = "theme-" + key.replace('"', "'").replace("/", "-")
        planned[key] = (target, target not in known_ids)
    return planned


def _diff_rows(rows: list[dict], execution, excluded, v4_codes, planned) -> list[dict]:
    out = []
    for row in rows:
        code = row["code"]
        target, _create = planned[row["group_key"]]
        if code in execution and execution[code] == target:
            action = "keep"
            status = "included"
            container = execution[code]
        elif code in execution:
            action = "move"
            status = "included"
            container = execution[code]
        elif code in excluded:
            action = "include_previously_excluded"
            status = "excluded"
            container = ""
        else:
            action = "add"
            status = "absent"
            container = ""
        out.append({
            "code": code,
            "name": row.get("name") or "",
            "exchange": row.get("exchange") or "",
            "v3_status": status,
            "v3_container": container,
            "v4_status": "included" if code in v4_codes else "absent",
            "group_key": row["group_key"],
            "group_name": row["group_name"],
            "group_rule": row["group_rule"],
            "target_id": target,
            "d19_action": action,
        })
    return out


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in columns})


def write_census_tables(rows: list[dict], diff_rows: list[dict]) -> None:
    _write_csv(OUT / "census.csv", CENSUS_COLUMNS, rows)
    _write_csv(OUT / "diff.csv", DIFF_COLUMNS, diff_rows)
    groups: dict[str, dict] = {}
    for row in diff_rows:
        slot = groups.setdefault(row["group_key"], {
            "group_key": row["group_key"],
            "group_name": row["group_name"],
            "group_rule": row["group_rule"],
            "target_id": row["target_id"],
            "asset_class": "",
            "codes": [],
            "names": [],
        })
        slot["codes"].append(row["code"])
        slot["names"].append(row["name"])
    table = []
    for key in sorted(groups):
        slot = groups[key]
        bucket = slot["group_key"] if slot["group_key"] in {"gold", "crude-oil", "soymeal", "silver", "cross-border-commodity"} else ""
        slot["asset_class"] = "商品" if bucket else "美股和全球主题"
        slot["codes"] = " ".join(slot["codes"])
        slot["names"] = " | ".join(slot["names"])
        table.append(slot)
    _write_csv(OUT / "grouping.csv", GROUP_COLUMNS, table)


def _end_for(row: dict) -> str:
    listed = row.get("delist_date") or ""
    if listed and listed < NAV_END:
        return listed
    return NAV_END


def _kline(secid: str, fqt: int, end: str, *, beg: str = "19900101", allow_empty: bool = False):
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": "101",
        "fqt": str(fqt),
        "beg": beg,
        "end": end.replace("-", ""),
        "lmt": "100000",
    }
    raw = fetch(EM_KLINE, params, headers={"Referer": "https://quote.eastmoney.com/"}, timeout=12, retries=0)
    payload = json.loads(_decode(raw))
    rc = (payload or {}).get("rc", 0) if isinstance(payload, dict) else "bad"
    klines = ((payload.get("data") or {}).get("klines") if isinstance(payload, dict) else None)
    if rc not in (0, None):
        raise http.FetchError(f"eastmoney {secid} fqt={fqt} rc={rc}")
    if not klines:
        if allow_empty:
            return [], raw
        raise http.FetchError(f"eastmoney {secid} fqt={fqt} 没有K线")
    _name, rows = parse_eastmoney_klines(payload)
    kept = [row for row in rows if row.get("close") and row["close"] > 0]
    if not kept and not allow_empty:
        raise http.FetchError(f"eastmoney {secid} fqt={fqt} 没有收盘")
    return kept, raw


def _pull_span(secid: str, fqt: int, beg: str, end: str):
    try:
        rows, raw = _kline(secid, fqt, end, beg=beg, allow_empty=True)
        return rows, raw, None
    except http.FetchError as exc:
        return None, b"", exc


def _kline_retry(secid: str, fqt: int, end: str):
    """整段失败时，先确认近端还有行情，再按年往前补。连续两年断连就停。"""
    try:
        return _kline(secid, fqt, end)
    except http.FetchError as exc:
        last = exc
    year = int(end[:4])
    recent_beg = f"{year}0101" if end[5:7] >= "04" else f"{year - 1}1001"
    part, raw, err = _pull_span(secid, fqt, recent_beg, end)
    if part is None:
        raise err or last
    rows = list(part)
    blobs = [raw] if raw else []
    misses = 0
    for prev in range(year - 1, 2009, -1):
        piece, praw, err = _pull_span(secid, fqt, f"{prev}0101", f"{prev}-12-31")
        if piece is None or not piece:
            misses += 1
            last = err or last
            if misses >= 2:
                break
            continue
        misses = 0
        rows.extend(piece)
        if praw:
            blobs.append(praw)
        time.sleep(0.15)
    dedup = {row["date"]: row for row in rows}
    ordered = [dedup[day] for day in sorted(dedup)]
    if not ordered:
        raise last or http.FetchError(f"eastmoney {secid} 没有收盘")
    return ordered, b"\n".join(blobs)


def _secid(code: str) -> str | None:
    if re.fullmatch(r"5\d{5}", code):
        return f"1.{code}"
    if re.fullmatch(r"1[56]\d{4}", code):
        return f"0.{code}"
    return None


def insert_missing_bars(con, code: str, adj: str, source: str, rows: list[dict], fetched_at: str, *,
                        start: str = "", end: str = NAV_END) -> dict:
    """只插入还没有的日期。重叠日收盘对不上则整段不写。已有行不改。"""
    existing = list(con.execute(
        """SELECT date, open, high, low, close, volume, amount, source
           FROM bars WHERE code = ? AND adj = ? ORDER BY date""",
        (code, adj)))
    sources = {row[7] for row in existing}
    if sources and source not in sources:
        return {"status": "skipped_other_source", "inserted": 0, "kept": len(existing),
                "reason": f"已有来源 {' '.join(sorted(sources))}"}
    if len(sources) > 1:
        return {"status": "mixed_source", "inserted": 0, "kept": len(existing), "reason": "库内已有多个来源"}
    by_day = {row[0]: row for row in existing}
    fresh = []
    conflicts = []
    for row in rows:
        day = row["date"]
        if day > end or (start and day < start):
            continue
        old = by_day.get(day)
        if old is None:
            fresh.append(row)
            continue
        if old[4] is None or row.get("close") is None:
            continue
        if abs(float(old[4]) - float(row["close"])) > 1e-4:
            conflicts.append(day)
    if conflicts:
        return {"status": "conflict", "inserted": 0, "kept": len(existing),
                "reason": "重叠日收盘不一致 " + " ".join(conflicts[:6])}
    saved = [(row[0], row[4], row[7]) for row in existing]
    with con:
        con.executemany(
            """INSERT INTO bars (code, adj, date, open, high, low, close, volume, amount, source, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(code, adj, row["date"], row.get("open"), row.get("high"), row.get("low"), row["close"],
              row.get("volume"), row.get("amount"), source, fetched_at) for row in fresh])
        after = {
            day: (close, source_name)
            for day, close, source_name in con.execute(
                "SELECT date, close, source FROM bars WHERE code = ? AND adj = ?",
                (code, adj))
        }
    for day, close, source_name in saved:
        if after.get(day) != (close, source_name):
            raise RuntimeError(f"{code} {adj} 已有行情被改写 {day}")
    span = con.execute(
        "SELECT min(date), max(date), count(*) FROM bars WHERE code = ? AND adj = ? AND date <= ?",
        (code, adj, end)).fetchone()
    return {"status": "in_db", "inserted": len(fresh), "kept": len(existing),
            "first": span[0], "last": span[1], "reason": ""}


def _bar_span(con, code: str) -> dict[str, dict]:
    found = {}
    for adj, source, first, last, rows in con.execute(
            """SELECT adj, min(source), min(date), max(date), count(*)
               FROM bars WHERE code = ? GROUP BY adj""",
            (code,)):
        found[adj] = {"source": source, "first": first, "last": last, "rows": rows}
    return found


def _nav_span(con, code: str) -> dict:
    row = con.execute(
        "SELECT min(date), max(date), count(*), min(source) FROM fund_nav WHERE code = ?",
        (code,)).fetchone()
    return {"first": row[0], "last": row[1], "rows": row[2] or 0, "source": row[3] or ""}


def fill(con, rows: list[dict]) -> list[dict]:
    """缺的场内行情（东财后复权优先）和净值只插入。已覆盖到截止日的不请求。"""
    report = []
    fetched_at = DB.now()
    run_id = DB.start_run(con, "backfill", end=date.fromisoformat(NAV_END), args={
        "job": "v4-r1e-census-fill",
        "portfolio_returns": False,
        "overwrites_existing_rows": False,
        "nav_end": NAV_END,
    })
    try:
        for index, row in enumerate(rows):
            code = row["code"]
            end = _end_for(row)
            start = row.get("list_date") or ""
            if start == "取不到":
                start = ""
            bars = _bar_span(con, code)
            nav = _nav_span(con, code)
            need_hfq = not bars.get("hfq") or (bars["hfq"]["last"] or "") < end or (
                start and (bars["hfq"]["first"] or "9999") > start)
            need_raw = "raw" not in bars
            need_nav = nav["rows"] == 0 or (nav["last"] or "") < end or (start and (nav["first"] or "9999") > start)
            secid = _secid(code)
            if need_hfq or need_raw:
                if not secid:
                    report.append({"code": code, "kind": "bars", "status": "unfillable", "inserted": 0,
                                   "source": "", "source_url": EM_KLINE, "reason": "代码没有东财 secid"})
                else:
                    for adj, fqt, source, needed in (
                        ("hfq", 2, HFQ_SOURCE, need_hfq),
                        ("raw", 0, RAW_SOURCE, need_raw),
                    ):
                        if not needed:
                            have = bars.get(adj) or {}
                            report.append({"code": code, "kind": adj, "status": "already", "inserted": 0,
                                           "kept": have.get("rows") or 0, "first": have.get("first") or "",
                                           "last": have.get("last") or "", "source": have.get("source") or "",
                                           "source_url": "", "reason": ""})
                            continue
                        url = EM_KLINE + f"?secid={secid}&fqt={fqt}"
                        try:
                            series, raw = _kline(secid, fqt, end)
                        except (http.FetchError, ValueError) as exc:
                            report.append({"code": code, "kind": adj, "status": "unfillable", "inserted": 0,
                                           "source": source, "source_url": url, "reason": str(exc)[:200]})
                            continue
                        digest = _gz(INCOMING / "raw" / "kline" / f"{code}-{adj}.json.gz", raw)
                        result = insert_missing_bars(con, code, adj, source, series, fetched_at, start=start, end=end)
                        report.append({"code": code, "kind": adj, "source": source, "source_url": url,
                                       "sha256": digest, **result})
                        time.sleep(0.15)
            else:
                for adj in ("hfq", "raw"):
                    have = bars.get(adj) or {}
                    if not have:
                        continue
                    report.append({"code": code, "kind": adj, "status": "already", "inserted": 0,
                                   "kept": have.get("rows") or 0, "first": have.get("first") or "",
                                   "last": have.get("last") or "", "source": have.get("source") or "",
                                   "source_url": "", "reason": ""})
            if need_nav:
                url = PING.format(code=code)
                try:
                    raw = fetch(url, headers={"Referer": "https://fund.eastmoney.com/"}, timeout=60)
                    points = parse_pingzhongdata(_decode(raw), date.fromisoformat(end))
                except (http.FetchError, ValueError) as exc:
                    report.append({"code": code, "kind": "nav", "status": "unfillable", "inserted": 0,
                                   "source": NAV_SOURCE, "source_url": url, "reason": str(exc)[:200]})
                else:
                    digest = _gz(INCOMING / "raw" / "pingzhong" / f"{code}.js.gz", raw)
                    nav_rows = [{
                        "code": code, "date": point["date"], "unit_nav": point["unit_nav"],
                        "accum_nav": point["accum_nav"], "subscribe_status": None, "redeem_status": None,
                        "source": NAV_SOURCE,
                    } for point in points if not start or point["date"] >= start]
                    result = fund_nav.store_missing(con, run_id, nav_rows, fetched_at, end=end, source=NAV_SOURCE)
                    status = "conflict" if result["conflicts"] else "in_db"
                    report.append({
                        "code": code, "kind": "nav", "status": status, "inserted": result["inserted"],
                        "kept": result["kept"], "first": result["first"], "last": result["last"],
                        "source": NAV_SOURCE, "source_url": url, "sha256": digest,
                        "reason": "重叠日净值不一致" if result["conflicts"] else "",
                    })
                    time.sleep(0.12)
            else:
                report.append({"code": code, "kind": "nav", "status": "already", "inserted": 0,
                               "kept": nav["rows"], "first": nav["first"] or "", "last": nav["last"] or "",
                               "source": nav["source"], "source_url": "", "reason": ""})
            print(f"fill {index + 1}/{len(rows)} {code}", flush=True)
        DB.write_requests(con, run_id, http.LOG)
        DB.finish_run(con, run_id, "ok")
    except Exception:
        DB.finish_run(con, run_id, "error")
        raise
    return report


def _actions(rows: list[dict], diff_rows: list[dict], execution: dict[str, str], listed: dict[str, str], con) -> list[dict]:
    by_code = {row["code"]: row for row in rows}
    actions = []
    for item in diff_rows:
        code = item["code"]
        row = by_code[code]
        current_list = listed.get(code) or ""
        refresh = current_list in {"", "取不到"} and row.get("list_date")
        if item["d19_action"] == "keep" and not refresh:
            continue
        target = item["target_id"]
        create = item["d19_action"] == "add" and target not in execution.values() and target not in {
            "gold", "crude-oil", "soymeal",
        }
        # 同组里只要已有容器，就不要新建。上面的 planned 已经决定 create。
        create = item["d19_action"] in {"add", "include_previously_excluded"} and _group_is_new(item, diff_rows, execution)
        nav = _nav_span(con, code)
        bars = _bar_span(con, code)
        bar = bars.get("hfq") or bars.get("raw") or {}
        track = row.get("index_name") or row.get("group_name") or "取不到"
        note = (
            f"D19-4 纳入。分组 {row.get('group_key')}（{row.get('group_rule')}）。"
            f"净值 {nav['rows']} 行。行情 {bar.get('rows') or 0} 行，来源 {bar.get('source') or '无'}。"
        )
        action = {
            "code": code,
            "name": row.get("name") or code,
            "list_date": row.get("list_date") or "取不到",
            "list_date_source": row.get("source_url") or "",
            "bars_status": "in_db" if bar.get("rows") else "取不到",
            "track": track,
            "track_source": row.get("profile_url") or row.get("source_url") or "",
            "note": note,
            "target_id": target,
            "target_name": row.get("group_name") or target,
            "group_key": row.get("group_key") or "",
            "group_rule": row.get("group_rule") or "",
            "asset_class": "商品" if row.get("commodity") else ("债券" if "债" in (row.get("fund_type") or "") else "美股和全球主题"),
            "create": create,
        }
        if create:
            rep = _representative(code, diff_rows, by_code)
            rep_nav = _nav_span(con, rep["code"])
            action["research"] = {
                "index_code": row.get("group_key") or "",
                "index_name": row.get("group_name") or "",
                "return_basis": "unit_nav",
                "publish_date": rep.get("list_date") or "取不到",
                "publish_date_source": rep.get("source_url") or "",
                "base_date": "取不到",
                "base_date_source": "",
                "series_code": rep["code"] if rep_nav["rows"] else "",
                "series_source": rep_nav["source"],
                "series_status": "in_db" if rep_nav["rows"] else "取不到",
                "source_url": rep.get("profile_url") or rep.get("source_url") or "",
                "note": (
                    f"D19 §3.1：{row.get('group_name')}。"
                    f"研究序列用上市最早的 {rep['code']} 的单位净值，从上市日起。"
                    "没有把上市前的海外指数接进来。不计算收益。"
                ),
            }
        actions.append(action)
    actions.sort(key=lambda action: (action["target_id"], not action["create"], action["code"]))
    return actions


def _group_is_new(item: dict, diff_rows: list[dict], execution: dict[str, str]) -> bool:
    if item["target_id"] in {"gold", "crude-oil", "soymeal"}:
        return False
    mates = [row for row in diff_rows if row["group_key"] == item["group_key"]]
    if any(row["code"] in execution and execution[row["code"]] == item["target_id"] for row in mates):
        return False
    if item["target_id"] in execution.values():
        return False
    return item["code"] == min(row["code"] for row in mates)


def _representative(code: str, diff_rows: list[dict], by_code: dict[str, dict]) -> dict:
    item = next(row for row in diff_rows if row["code"] == code)
    mates = [by_code[row["code"]] for row in diff_rows if row["group_key"] == item["group_key"]]
    dated = [row for row in mates if row.get("list_date")]
    if not dated:
        return by_code[code]
    return min(dated, key=lambda row: row["list_date"])


def _v4_records(rows: list[dict], diff_rows: list[dict], con) -> list[dict]:
    target = {row["code"]: row["target_id"] for row in diff_rows}
    records = []
    for row in rows:
        code = row["code"]
        nav = _nav_span(con, code)
        digest = hashlib.sha256()
        if nav["rows"]:
            for day, unit, accum in con.execute(
                    """SELECT date, unit_nav, accum_nav FROM fund_nav
                       WHERE code = ? AND date <= ? ORDER BY date""",
                    (code, NAV_END)):
                digest.update(f"{day},{unit},{accum}\n".encode())
        records.append({
            "code": code,
            "name": row.get("name") or "",
            "maps_to": target.get(code) or "",
            "tracked_index": row.get("group_name") or "",
            "source": nav["source"] or NAV_SOURCE,
            "source_url": row.get("profile_url") or JBGK.format(code=code),
            "status": "in_db" if nav["rows"] else "取不到",
            "official_launch": row.get("list_date") or "取不到",
            "first_date": nav["first"] or "",
            "last_date": nav["last"] or "",
            "rows": nav["rows"],
            "sha256": digest.hexdigest() if nav["rows"] else "",
        })
    return records


def register(con, rows: list[dict], diff_rows: list[dict], execution: dict[str, str], listed: dict[str, str]) -> dict:
    actions = _actions(rows, diff_rows, execution, listed, con)
    text = apply_register(V3_PATH.read_text(encoding="utf-8"), actions)
    V3_PATH.write_text(text, encoding="utf-8")
    errors = U.validate()
    if errors:
        raise RuntimeError("登记表不完整\n" + "\n".join(errors[:30]))
    records = _v4_records(rows, diff_rows, con)
    V4_PATH.write_text(apply_v4(V4_PATH.read_text(encoding="utf-8"), records), encoding="utf-8")
    summary = coverage.write(con)
    return {"actions": len(actions), "coverage": summary, "validate_errors": errors}


def summarize(rows: list[dict], diff_rows: list[dict], fill_rows: list[dict] | None = None) -> dict:
    fill_rows = fill_rows or []
    def count(status: str) -> int:
        return sum(1 for row in diff_rows if row["d19_action"] == status)
    filled = {}
    unfillable = []
    for row in fill_rows:
        if row.get("status") == "in_db" and row.get("inserted"):
            filled[row["kind"]] = filled.get(row["kind"], 0) + 1
        if row.get("status") == "unfillable":
            unfillable.append({"code": row["code"], "kind": row["kind"], "reason": row.get("reason") or ""})
    return {
        "exchange_total": len(rows),
        "listed": sum(1 for row in rows if row.get("list_status") == "listed"),
        "delisted_or_absent": sum(1 for row in rows if row.get("list_status") != "listed"),
        "previously_included": count("keep") + count("move"),
        "missing": count("add"),
        "previously_excluded_now_include": count("include_previously_excluded"),
        "moved": count("move"),
        "groups": len({row["group_key"] for row in diff_rows}),
        "filled_codes": filled,
        "unfillable": unfillable,
        "inserted_rows": sum(int(row.get("inserted") or 0) for row in fill_rows),
    }


def retry_unfillable(con) -> list[dict]:
    """只重取 fill.csv 里断连的行情。已写入的日期仍然不覆盖。"""
    with (OUT / "fill.csv").open(encoding="utf-8", newline="") as handle:
        previous = list(csv.DictReader(handle))
    census_rows = {row["code"]: row for row in csv.DictReader((OUT / "census.csv").open(encoding="utf-8"))}
    pending = [row for row in previous if row.get("status") == "unfillable" and row.get("kind") in {"hfq", "raw"}]
    fresh_reports = []
    fetched_at = DB.now()
    for index, item in enumerate(pending):
        code = item["code"]
        kind = item["kind"]
        source = HFQ_SOURCE if kind == "hfq" else RAW_SOURCE
        fqt = 2 if kind == "hfq" else 0
        secid = _secid(code)
        meta = census_rows.get(code) or {}
        end = _end_for(meta)
        start = meta.get("list_date") or ""
        if not secid:
            fresh_reports.append({**item, "status": "unfillable", "reason": "代码没有东财 secid"})
            continue
        try:
            series, raw = _kline_retry(secid, fqt, end)
        except (http.FetchError, ValueError) as exc:
            fresh_reports.append({
                "code": code, "kind": kind, "status": "unfillable", "inserted": 0,
                "source": source, "source_url": EM_KLINE, "reason": str(exc)[:200],
            })
            print(f"retry {index + 1}/{len(pending)} {code} {kind} FAIL", flush=True)
            continue
        digest = _gz(INCOMING / "raw" / "kline" / f"{code}-{kind}.json.gz", raw)
        result = insert_missing_bars(con, code, kind, source, series, fetched_at, start=start, end=end)
        fresh_reports.append({
            "code": code, "kind": kind, "source": source, "source_url": EM_KLINE, "sha256": digest, **result,
        })
        print(f"retry {index + 1}/{len(pending)} {code} {kind} {result['status']} +{result['inserted']}", flush=True)
        time.sleep(0.4)
    replaced = {(row["code"], row["kind"]) for row in fresh_reports}
    merged = [row for row in previous if (row.get("code"), row.get("kind")) not in replaced]
    merged.extend(fresh_reports)
    _write_csv(OUT / "fill.csv", FILL_COLUMNS, merged)
    return merged


def regroup_saved() -> tuple[list[dict], list[dict]]:
    """用已经落地的普查表重算分组。不重新请求交易所。"""
    with (OUT / "census.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        _benchmark_fields(row)
    rows = group_funds(rows)
    execution, _listed, excluded, v4_codes = load_membership()
    planned = _targets(rows, execution, _known_ids())
    diff_rows = _diff_rows(rows, execution, excluded, v4_codes, planned)
    write_census_tables(rows, diff_rows)
    return rows, diff_rows


def run(stage: str = "all") -> dict:
    execution, listed, excluded, v4_codes = load_membership()
    if stage == "regroup":
        rows, diff_rows = regroup_saved()
        summary = summarize(rows, diff_rows)
        (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return summary
    if stage in {"retry", "register"}:
        rows, diff_rows = regroup_saved()
        fill_rows: list[dict] = []
        con = DB.connect(DB.MARKET_DB)
        try:
            if stage == "retry":
                fill_rows = retry_unfillable(con)
            if stage == "register":
                register(con, rows, diff_rows, execution, listed)
                with (OUT / "fill.csv").open(encoding="utf-8", newline="") as handle:
                    fill_rows = list(csv.DictReader(handle))
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            con.close()
        for suffix in ("-wal", "-shm"):
            leftover = Path(str(DB.MARKET_DB) + suffix)
            if leftover.exists():
                raise RuntimeError(f"库文件旁还有 {leftover.name}")
        summary = summarize(rows, diff_rows, fill_rows)
        summary["integrity"] = integrity
        summary["sha256"] = DB.sha256_file(DB.MARKET_DB)
        summary["bytes"] = DB.MARKET_DB.stat().st_size
        (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: summary[key] for key in summary if key != "unfillable"}, ensure_ascii=False, indent=2))
        print("unfillable", len(summary["unfillable"]))
        return summary
    rows = census()
    planned = _targets(rows, execution, _known_ids())
    diff_rows = _diff_rows(rows, execution, excluded, v4_codes, planned)
    for row in diff_rows:
        groups = [item for item in diff_rows if item["group_key"] == row["group_key"]]
        bond = False
        row["asset_class"] = "商品" if row["group_key"] in {
            "gold", "crude-oil", "soymeal", "silver", "cross-border-commodity"} else "美股和全球主题"
        _ = bond, groups
    write_census_tables(rows, diff_rows)
    fill_rows: list[dict] = []
    if stage in {"all", "fill", "register"}:
        con = DB.connect(DB.MARKET_DB)
        try:
            if stage in {"all", "fill"}:
                fill_rows = fill(con, rows)
                _write_csv(OUT / "fill.csv", FILL_COLUMNS, fill_rows)
            if stage in {"all", "register"}:
                register(con, rows, diff_rows, execution, listed)
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            con.close()
        for suffix in ("-wal", "-shm"):
            leftover = Path(str(DB.MARKET_DB) + suffix)
            if leftover.exists():
                raise RuntimeError(f"库文件旁还有 {leftover.name}")
    else:
        integrity = ""
    summary = summarize(rows, diff_rows, fill_rows)
    summary["integrity"] = integrity
    if stage in {"all", "fill", "register"}:
        summary["sha256"] = DB.sha256_file(DB.MARKET_DB)
        summary["bytes"] = DB.MARKET_DB.stat().st_size
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in summary if key != "unfillable"}, ensure_ascii=False, indent=2))
    print("unfillable", len(summary["unfillable"]))
    return summary
