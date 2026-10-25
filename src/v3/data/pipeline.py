"""L1 取数。只补缺，不改已有来源，不算组合收益。"""
from __future__ import annotations

import json
import time
from datetime import date, timedelta

from src.data import db as DB
from src.data import fund_nav
from src.data import http
from src.data import sohu_amount
from src.data import sources as S
from src.data import store as bars
from src.data import universe as phase1

from . import artifacts
from . import emit_universe
from . import parse
from . import store
from . import universe as U

END = date(2026, 9, 30)
CSI_URL = "https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info/{code}"
CSI_HEADERS = {"Referer": "https://www.csindex.com.cn/", "Accept": "application/json"}
SGE_URL = "https://www.sge.com.cn/sjzx/quotation_daily_new"
RANK_URL = "https://fund.eastmoney.com/data/rankhandler.aspx"
JBGK = "https://fundf10.eastmoney.com/jbgk_{code}.html"

# 研究序列用全收益代码。价格代码只归档身份，不另下一套行情。
CSI_FETCH = [
    "H00986", "H00987", "H00988", "H00989", "H00990",
    "H00991", "H00992", "H00993", "H00994", "H00995", "H00922",
]
CSI_IDENTITY = CSI_FETCH + [
    "000986", "000987", "000988", "000989", "000990", "000991", "000992", "000993", "000994", "000995",
    "000922", "H00300", "000300", "H00905", "000905", "H00852", "000852", "000688", "H000688", "H00688",
    "932075", "932076",
]
INDUSTRY_SEARCH = {
    "allshare-energy": ("全指能源", "中证全指能源指数"),
    "allshare-materials": ("全指材料", "中证全指原材料指数"),
    "allshare-industrials": ("全指工业", "中证全指工业指数"),
    "allshare-discretionary": ("全指可选", "中证全指可选消费指数"),
    "allshare-staples": ("全指消费", "中证全指主要消费指数"),
    "allshare-healthcare": ("全指医药", "中证全指医药卫生指数"),
    "allshare-financials-re": ("金融地产", "中证全指金融地产指数"),
    "allshare-it": ("全指信息", "中证全指信息技术指数"),
    "allshare-communication": ("全指通信服务", "中证全指通信服务指数"),
    "allshare-utilities": ("全指公用事业", "中证全指公用事业指数"),
}


def _log(log, text: str) -> None:
    log.append(text)
    print(text, flush=True)


def _months(start: date, end: date):
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def _window(y: int, m: int, day: int, span: int, end: date) -> tuple[date, date] | None:
    try:
        beg = date(y, m, day)
    except ValueError:
        return None
    stop = min(beg + timedelta(days=span - 1), end)
    if beg > end:
        return None
    return beg, stop


def archive_csi_identity(log: list[str]) -> None:
    for code in CSI_IDENTITY:
        url = CSI_URL.format(code=code)
        try:
            raw = http.get(url, headers=CSI_HEADERS, timeout=25)
        except http.FetchError as exc:
            _log(log, f"csi identity {code} FAIL {exc}")
            continue
        artifacts.save(f"raw/csi/{code}.json", raw, url=url, note="index-basic-info")
        try:
            data = json.loads(raw).get("data") or {}
        except json.JSONDecodeError:
            data = {}
        _log(log, f"csi identity {code} {data.get('indexFullNameCn') or '空'} "
                  f"base={str(data.get('basicDate') or '')[:10]} publish={str(data.get('publishDate') or '')[:10]}")
        time.sleep(0.15)


def fetch_csi_series(con, log: list[str], end: date) -> None:
    start = date(2004, 12, 31)
    http.RECORD_DIR = artifacts.INCOMING / "raw" / "csi-perf"
    for code in CSI_FETCH:
        cid = _container_for_series(code)
        have = bars.span(con, code, "raw")
        if have["rows"] and have["source"] == "csi" and (have["last"] or "") >= end.isoformat():
            _log(log, f"csi perf {code} reused rows={have['rows']} {have['first']} {have['last']}")
            if cid:
                U.patch_field(cid, "series_status", "fetched")
            continue
        mark = len(http.LOG)
        try:
            fetched = S.fetch_csindex(code, start, end, pause=0.2, forbidden_wait=3)
        except http.FetchError as exc:
            _log(log, f"csi perf {code} FAIL {exc}")
            if cid:
                U.patch_field(cid, "series_status", "取不到")
            continue
        for ent in http.LOG[mark:]:
            if ent.get("file") and ent.get("sha256"):
                artifacts._append({
                    "path": f"raw/csi-perf/{ent['file']}",
                    "sha256": ent["sha256"],
                    "file_sha256": ent["sha256"],
                    "bytes": ent.get("bytes") or 0,
                    "file_bytes": ent.get("bytes") or 0,
                    "url": ent.get("url") or "",
                    "fetched_at": ent.get("fetched_at") or "",
                    "note": f"csi perf {code}",
                })
        result = store.write_series(con, code, "csi", fetched.rows, DB.now())
        status = "fetched" if result["status"] in {"fetched", "appended"} else result["status"]
        if result["status"] == "empty":
            status = "取不到"
        if cid and status in {"fetched", "reused", "取不到", "appended"}:
            U.patch_field(cid, "series_status", "fetched" if status == "appended" else status)
        _log(log, f"csi perf {code} {result} name={fetched.name} n={len(fetched.rows)}")
    http.RECORD_DIR = None


def _container_for_series(code: str) -> str | None:
    for box in U.containers():
        if box["research"].get("series_code") == code and box["research"].get("series_status") in {"TBD", "取不到", "fetched"}:
            return box["id"]
    return None


def fetch_tencent_index(con, log: list[str], symbol: str, code: str, route: str, start: date, end: date) -> dict:
    try:
        fetched = S.fetch_tencent(symbol, start, end)
    except http.FetchError as exc:
        _log(log, f"tencent {symbol} FAIL {exc}")
        return {"status": "取不到", "error": str(exc)}
    result = store.write_series(con, code, route, fetched.rows, DB.now())
    _log(log, f"tencent {symbol} -> {code} {result} name={fetched.name} n={len(fetched.rows)}")
    result["name"] = fetched.name
    result["n"] = len(fetched.rows)
    return result


def fetch_hk(con, log: list[str], end: date) -> None:
    hsi = fetch_tencent_index(con, log, "hkHSI", "HSI", "tencent_hk_index", date(2000, 1, 1), end)
    U.patch_field("hsi", "series_status", "fetched" if hsi.get("n") else "取不到")
    tech = fetch_tencent_index(con, log, "hkHSTECH", "HSTECH", "tencent_hk_index", date(2014, 1, 1), end)
    U.patch_field("hstech", "series_status", "fetched" if tech.get("n") else "取不到")
    alt = fetch_tencent_index(con, log, "sz399606", "399606", "tencent_index", date(2010, 1, 1), end)
    if alt.get("n"):
        store.write_instruments(con, 0, [{
            "container_id": "chinext",
            "role": "alt",
            "code": "399606",
            "name": alt.get("name") or "创业板R",
            "return_basis": "unconfirmed",
            "source": "tencent_index",
            "source_url": "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
            "series_status": "fetched",
            "note": "腾讯名称不含全收益。不作为创业板指的研究序列。",
        }], DB.now())


def _sge_page(beg: date, stop: date) -> tuple[list[dict], bytes, str]:
    params = {"start_date": beg.isoformat(), "end_date": stop.isoformat()}
    raw = http.get(SGE_URL, params, headers={"Referer": "https://www.sge.com.cn/"}, timeout=40)
    text = raw.decode("utf-8", "replace")
    return parse.parse_sge_daily(text), raw, f"{SGE_URL}?start_date={beg}&end_date={stop}"


def fetch_sge(con, log: list[str], end: date) -> None:
    saved_empty = False
    empty = []
    months = []
    for y, m in _months(date(2012, 1, 1), end):
        window = _window(y, m, 1, 10, end)
        if window is None:
            continue
        try:
            rows, raw, url = _sge_page(*window)
        except http.FetchError as exc:
            _log(log, f"sge probe {y}-{m:02d} FAIL {exc}")
            empty.append({"month": f"{y}-{m:02d}", "error": str(exc)[:180]})
            continue
        hits = [r for r in rows if r["contract"] == "Au99.99"]
        if hits:
            months.append((y, m))
            artifacts.save(f"raw/sge/{y}{m:02d}-probe.html", raw, url=url, note="Au99.99 probe hit")
        else:
            digest = artifacts.sha256_bytes(raw)
            empty.append({"month": f"{y}-{m:02d}", "sha256": digest, "bytes": len(raw), "url": url})
            if not saved_empty:
                artifacts.save("raw/sge/empty-sample.html", raw, url=url, note="无 Au99.99 的页面样本")
                saved_empty = True
        time.sleep(0.2)
    by_contract: dict[str, dict[str, dict]] = {"Au99.99": {}, "Au9999": {}}
    for y, m in months:
        day = 1
        while day <= 28:
            window = _window(y, m, day, 7, end)
            day += 7
            if window is None:
                continue
            try:
                rows, raw, url = _sge_page(*window)
            except http.FetchError as exc:
                _log(log, f"sge {y}-{m:02d}-{window[0].day} FAIL {exc}")
                continue
            if rows:
                artifacts.save(f"raw/sge/{window[0].isoformat()}_{window[1].isoformat()}.html", raw, url=url, note="daily")
            for row in rows:
                by_contract[row["contract"]][row["date"]] = row
            time.sleep(0.15)
    body = json.dumps({"empty_months": empty, "hit_months": [f"{y}-{m:02d}" for y, m in months]}, ensure_ascii=False).encode()
    artifacts.save("raw/sge/probe-index.json", body, url=SGE_URL, note="哪些月份的探测页没有 Au99.99")
    for contract, bucket in by_contract.items():
        rows = [bucket[d] for d in sorted(bucket)]
        if not rows:
            continue
        result = store.write_series(con, contract, "sge_daily", rows, DB.now())
        _log(log, f"sge {contract} {result} first={rows[0]['date']} last={rows[-1]['date']} n={len(rows)}")
    au = by_contract["Au99.99"]
    if not au:
        U.patch_field("gold", "series_status", "取不到")
        return
    first = min(au)
    status = "partial" if first > "2013-01-01" else "fetched"
    U.patch_field("gold", "series_status", status)


def probe_gaps(log: list[str]) -> list[dict]:
    """只记录打得开的页面或失败原因，不把别的指数写进原油/豆粕/中债。"""
    targets = [
        ("dce", "https://www.dce.com.cn/", "大商所首页"),
        ("chinabond", "https://www.chinabond.com.cn/", "中国债券信息网首页"),
        ("chinabond-yield", "https://yield.chinabond.com.cn/", "中债收益率页"),
        ("ccidx-basket", "http://www.ccidx.com/zs/zsxx/202412/t20241205_1593.html", "中证商品期货指数（一篮子，不是原油单品种）"),
        ("hsi-factsheet", "https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/factsheets/hsi.pdf", "恒生指数事实表"),
    ]
    failed = []
    for name, url, why in targets:
        try:
            raw = http.get(url, headers={"Referer": url}, timeout=20)
        except http.FetchError as exc:
            failed.append({"name": name, "url": url, "error": str(exc)[:300], "why": why})
            _log(log, f"gap {name} FAIL {exc}")
            continue
        note = why
        if raw[:4] != b"%PDF" and name == "hsi-factsheet":
            note += "；响应不是 PDF"
            failed.append({"name": name, "url": url, "error": "not pdf", "why": note, "bytes": len(raw)})
        artifacts.save(f"raw/gaps/{name}.body", raw, url=url, note=note)
        _log(log, f"gap {name} bytes={len(raw)} {note}")
    return failed


def _rank() -> tuple[list[dict], bytes]:
    raw = http.get(RANK_URL, {
        "op": "ph", "dt": "kf", "ft": "qdii", "sc": "dm", "st": "asc", "pi": "1", "pn": "500", "dx": "1",
    }, headers={"Referer": "https://fund.eastmoney.com/"}, timeout=40)
    text = raw.decode("utf-8", "replace")
    return parse.parse_qdii_rank(text), raw


def _szse_funds(log: list[str]) -> dict[str, dict]:
    out = {}
    page = 1
    pages = 1
    while page <= pages:
        url = "https://www.szse.cn/api/report/ShowReport/data"
        params = {"SHOWTYPE": "JSON", "CATALOGID": "1105", "TABKEY": "tab1", "PAGENO": str(page)}
        raw = None
        err = None
        for _ in range(3):
            try:
                raw = http.get(url, params, headers={"Referer": "https://www.szse.cn/"}, timeout=40)
                break
            except http.FetchError as exc:
                err = exc
                time.sleep(1)
        if raw is None:
            _log(log, f"szse page {page} FAIL {err}")
            page += 1
            continue
        artifacts.save(f"raw/szse/funds-{page}.json", raw, url=url, note="基金列表")
        payload = json.loads(raw)
        tab = payload[0]
        pages = int(tab["metadata"].get("pagecount") or page)
        for item in tab.get("data") or []:
            parsed = parse.parse_szse_fund_row(item)
            if parsed:
                out[parsed["code"]] = parsed
        page += 1
        time.sleep(0.2)
    _log(log, f"szse funds {len(out)}")
    return out


def _jbgk(code: str) -> dict:
    url = JBGK.format(code=code)
    raw = http.get(url, headers={"Referer": "https://fundf10.eastmoney.com/"}, timeout=30)
    artifacts.save(f"raw/jbgk/{code}.html", raw, url=url, note="基金概况")
    return parse.parse_jbgk(raw.decode("utf-8", "replace"))


def _nav_stale(con, code: str) -> bool:
    row = con.execute("SELECT count(*), max(date) FROM fund_nav WHERE code = ?", (code,)).fetchone()
    if not row or not row[0]:
        return True
    return (row[1] or "") < "2026-09-01"


def fetch_nav_from_2021(code: str) -> list[dict]:
    """东财 lsjz 从新到旧。翻到 2021-01-01 之前就停。"""
    first = fund_nav._page(code, 1)
    total = int(first.get("TotalCount") or 0)
    if total <= 0:
        return []
    pages = (total + fund_nav.PAGE_SIZE - 1) // fund_nav.PAGE_SIZE
    by_date: dict[str, dict] = {}

    def take(payload) -> str | None:
        oldest = None
        for item in ((payload.get("Data") or {}).get("LSJZList")) or []:
            parsed = fund_nav.parse_lsjz_row(code, item)
            if parsed is None:
                continue
            by_date.setdefault(parsed["date"], parsed)
            oldest = parsed["date"] if oldest is None else min(oldest, parsed["date"])
        return oldest

    oldest = take(first)
    if oldest and oldest < "2021-01-01":
        return [by_date[d] for d in sorted(by_date) if d >= "2021-01-01"]
    for page in range(2, pages + 1):
        time.sleep(0.05)
        oldest = take(fund_nav._page(code, page))
        if not oldest or oldest < "2021-01-01":
            break
    return [by_date[d] for d in sorted(by_date) if d >= "2021-01-01"]


def _toml_quote(text: str) -> str:
    return (text or "").replace('"', "'").replace("\n", " ")


def discover_industry_etfs(log: list[str]) -> None:
    for cid, (key, must) in INDUSTRY_SEARCH.items():
        try:
            raw = http.get(
                "https://fundsuggest.eastmoney.com/FundSearch/api/FundSearchAPI.ashx",
                {"m": "1", "key": key + "ETF"},
                headers={"Referer": "https://fund.eastmoney.com/"}, timeout=20)
        except http.FetchError as exc:
            _log(log, f"industry search {cid} FAIL {exc}")
            continue
        artifacts.save(f"raw/search/{cid}.json", raw, url="https://fundsuggest.eastmoney.com/FundSearch/api/FundSearchAPI.ashx", note=key)
        try:
            datas = json.loads(raw).get("Datas") or []
        except json.JSONDecodeError:
            continue
        added = 0
        for item in datas:
            code = str(item.get("CODE") or "")
            name = str(item.get("NAME") or "")
            if "ETF" not in name or "联接" in name or not parse.exchange_code(code):
                continue
            try:
                profile = _jbgk(code)
            except http.FetchError as exc:
                _log(log, f"industry jbgk {code} FAIL {exc}")
                continue
            track = profile.get("track") or ""
            if track != must:
                continue
            if f'code = "{code}"' in U.UNIVERSE.read_text(encoding="utf-8"):
                continue
            block = (
                "[[container.execution]]\n"
                f'code = "{code}"\n'
                f'name = "{_toml_quote(name)}"\n'
                'list_date = "TBD"\n'
                'list_date_source = ""\n'
                'bars_status = "TBD"\n'
                f'track = "{_toml_quote(track)}"\n'
                f'track_source = "https://fundf10.eastmoney.com/jbgk_{code}.html"\n'
                'note = "东财搜索加 jbgk 跟踪标的含全指与行业名。上市日未在概况页出现。"\n\n'
            )
            U.insert_execution(cid, block)
            added += 1
            if added >= 3:
                break
            time.sleep(0.1)
        _log(log, f"industry {cid} etf added {added}")


def fetch_qdii(con, run_id: int, log: list[str], end: date) -> None:
    ranked, raw = _rank()
    artifacts.save("raw/qdii/rank.js", raw, url=RANK_URL, note="东财 QDII 排名")
    szse = _szse_funds(log)
    ranked_codes = {row["code"]: row for row in ranked}
    chosen = []
    for code, row in ranked_codes.items():
        on_szse = code in szse
        if not on_szse and not parse.exchange_code(code):
            continue
        chosen.append(row)
    _log(log, f"qdii rank {len(ranked)} on-exchange candidates {len(chosen)}")
    members = []
    for row in chosen:
        code = row["code"]
        try:
            profile = _jbgk(code)
        except http.FetchError as exc:
            _log(log, f"jbgk {code} FAIL {exc}")
            profile = {"track": "", "full_name": row["name"], "single_index": "unknown", "fund_type": "", "setup_date": "", "list_date": ""}
        list_date = ""
        list_src = ""
        if code in szse and szse[code].get("list_date"):
            list_date = szse[code]["list_date"]
            list_src = "https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1105&TABKEY=tab1"
        elif profile.get("list_date"):
            list_date = profile["list_date"]
            list_src = JBGK.format(code=code)
        else:
            list_date = "TBD"
            list_src = ""
        nav_rows = 0
        if _nav_stale(con, code):
            try:
                nav = fetch_nav_from_2021(code)
            except http.FetchError as exc:
                _log(log, f"nav {code} FAIL {exc}")
                nav = []
            if nav:
                fund_nav.store_code(con, run_id, nav, DB.now())
                nav_rows = len(nav)
                _log(log, f"nav {code} {nav_rows} {nav[0]['date']} {nav[-1]['date']}")
        else:
            nav_rows = con.execute("SELECT count(*) FROM fund_nav WHERE code = ?", (code,)).fetchone()[0]
            _log(log, f"nav {code} reused {nav_rows}")
        sym = phase1.fund_tencent(code)
        bars_status = "TBD"
        if sym:
            span_rows = con.execute("SELECT count(*) FROM bars WHERE code = ? AND adj = 'raw'", (code,)).fetchone()[0]
            if not span_rows:
                try:
                    fetched = S.fetch_tencent(sym, date(2005, 1, 1), end)
                except http.FetchError as exc:
                    _log(log, f"bars {code} FAIL {exc}")
                    fetched = None
                if fetched and fetched.rows:
                    result = store.write_series(con, code, "tencent_etf", fetched.rows, DB.now())
                    bars_status = "fetched" if result["status"] in {"fetched", "appended"} else result["status"]
                    _log(log, f"bars {code} {result}")
                else:
                    bars_status = "取不到"
            else:
                bars_status = "reused"
        else:
            bars_status = "取不到"
        note = (
            f"基金类型 {profile.get('fund_type') or 'TBD'}；跟踪标的分类 {profile.get('single_index')}；"
            f"成立日期栏 {profile.get('setup_date') or 'TBD'}。上交所上市日本次没有单独的列表接口，深交所以外的上市日记 TBD。"
            "单一指数成员从上市日起进入 U-指数，不使用更早的海外指数。"
        )
        members.append({
            "code": code,
            "name": profile.get("full_name") or row["name"],
            "track": profile.get("track") or "",
            "single_index": profile.get("single_index") or "unknown",
            "list_date": list_date,
            "list_date_source": list_src,
            "nav_rows": nav_rows,
            "bars_status": bars_status,
            "note": note,
        })
        time.sleep(0.05)
    summary = emit_universe.emit(con)
    _log(log, f"qdii members fetched {len(members)} single={sum(1 for r in members if r['single_index']=='single_index')}")
    _log(log, f"emit {summary}")


def fill_amounts(con, log: list[str]) -> None:
    """只补 v3 执行基金里 amount 为空的日子。连续失败 3 只就停。"""
    codes = []
    for box in U.containers():
        for ex in box.get("execution") or []:
            code = ex.get("code")
            if code and code not in codes:
                codes.append(code)
    streak = 0
    for code in codes:
        span = con.execute(
            "SELECT min(date), max(date), sum(amount IS NULL), count(*) FROM bars WHERE code = ? AND adj = 'raw'",
            (code,)).fetchone()
        if not span or not span[3] or not span[2]:
            continue
        if span[0] is None:
            continue
        source = con.execute(
            "SELECT min(source) FROM bars WHERE code = ? AND adj = 'raw'", (code,)).fetchone()[0]
        if source != "tencent_etf":
            continue
        try:
            amounts = sohu_amount.fetch_code(code, date.fromisoformat(span[0]), date.fromisoformat(span[1]))
        except http.FetchError as exc:
            streak += 1
            _log(log, f"sohu {code} FAIL {exc}")
            if streak >= 3:
                _log(log, "sohu 连续失败 3 只，停止补成交额")
                return
            continue
        streak = 0
        detail = sohu_amount.apply_amounts(con, code, amounts)
        _log(log, f"sohu {code} {detail}")
        time.sleep(0.2)


def apply_szse_list_dates(log: list[str]) -> None:
    """静态容器里、深交所给了 ssrq 的执行基金，补上市日。"""
    # 上市日已在 fetch_qdii 里抓过的页面不再请求。这里读 incoming json。
    import gzip
    folder = artifacts.INCOMING / "raw" / "szse"
    if not folder.exists():
        return
    listing = {}
    for path in sorted(folder.glob("funds-*.json*")):
        raw = gzip.open(path, "rb").read() if path.suffix == ".gz" else path.read_bytes()
        # artifacts.save 对大于 32KB 的文件写成 .gz，path 列是 .gz，磁盘上没有未压缩副本。
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for item in (payload[0].get("data") or []):
            parsed = parse.parse_szse_fund_row(item)
            if parsed and parsed.get("list_date"):
                listing[parsed["code"]] = parsed["list_date"]
    for box in U.containers():
        if str(box.get("generated") or "") == "qdii":
            continue
        for ex in box.get("execution") or []:
            listed = listing.get(ex.get("code") or "")
            if listed and ex.get("list_date") in {"", "TBD"}:
                U.patch_exec(box["id"], ex["code"], "list_date", listed)
                U.patch_exec(box["id"], ex["code"], "list_date_source",
                             "https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1105&TABKEY=tab1")
                _log(log, f"list date {ex['code']} {listed}")


def sync_bar_status(con, log: list[str]) -> None:
    for box in U.containers():
        if str(box.get("generated") or "") == "qdii":
            continue
        for ex in box.get("execution") or []:
            if ex.get("bars_status") != "TBD":
                continue
            n = con.execute("SELECT count(*) FROM bars WHERE code = ? AND adj = 'raw'", (ex["code"],)).fetchone()[0]
            U.patch_exec(box["id"], ex["code"], "bars_status", "fetched" if n else "取不到")
            _log(log, f"bars status {ex['code']} {'fetched' if n else '取不到'} rows={n}")


def supplement_exchange_qdii(end: date = END, log: list[str] | None = None) -> dict:
    """用东财基金代码表补场内 QDII/海外 ETF、LOF。跳过已有净值且已有日线的代码。"""
    if log is None:
        log = []
    url = "https://fund.eastmoney.com/js/fundcode_search.js"
    raw = http.get(url, headers={"Referer": "https://fund.eastmoney.com/"}, timeout=60)
    artifacts.save("raw/qdii/fundcode_search.js", raw, url=url, note="全市场基金代码表，用来筛场内 QDII")
    chosen = parse.on_exchange_qdii(parse.parse_fund_catalog(raw.decode("utf-8", "replace")))
    _log(log, f"catalog on-exchange qdii/overseas {len(chosen)}")
    szse = {}
    folder = artifacts.INCOMING / "raw" / "szse"
    if folder.exists():
        import gzip
        for path in sorted(folder.glob("funds-*.json*")):
            blob = gzip.open(path, "rb").read() if path.suffix == ".gz" else path.read_bytes()
            try:
                payload = json.loads(blob)
            except json.JSONDecodeError:
                continue
            for item in (payload[0].get("data") or []):
                parsed = parse.parse_szse_fund_row(item)
                if parsed:
                    szse[parsed["code"]] = parsed
    path = DB.MARKET_DB
    book = store.ledger(path)
    before = book.before("v3-L1-qdii")
    con = store.connect(path)
    store.ensure_nav(con)
    try:
        run_id = DB.start_run(con, "backfill", end=end, args={"job": "v3-L1-qdii", "n": len(chosen)})
        members = []
        for row in chosen:
            code = row["code"]
            try:
                profile = _jbgk(code)
            except http.FetchError as exc:
                _log(log, f"jbgk {code} FAIL {exc}")
                profile = {"track": "", "full_name": row["name"], "single_index": "unknown",
                           "fund_type": row.get("fund_type") or "", "setup_date": "", "list_date": ""}
            if code in szse and szse[code].get("list_date"):
                list_date = szse[code]["list_date"]
                list_src = "https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1105&TABKEY=tab1"
            elif profile.get("list_date"):
                list_date = profile["list_date"]
                list_src = JBGK.format(code=code)
            else:
                list_date, list_src = "TBD", ""
            if _nav_stale(con, code):
                try:
                    nav = fetch_nav_from_2021(code)
                except http.FetchError as exc:
                    _log(log, f"nav {code} FAIL {exc}")
                    nav = []
                if nav:
                    fund_nav.store_code(con, run_id, nav, DB.now())
                    nav_rows = len(nav)
                    _log(log, f"nav {code} {nav_rows} {nav[0]['date']} {nav[-1]['date']}")
                else:
                    nav_rows = 0
            else:
                nav_rows = con.execute("SELECT count(*) FROM fund_nav WHERE code = ?", (code,)).fetchone()[0]
            sym = phase1.fund_tencent(code)
            have = con.execute("SELECT count(*) FROM bars WHERE code = ? AND adj = 'raw'", (code,)).fetchone()[0]
            if have:
                bars_status = "reused"
            elif not sym:
                bars_status = "取不到"
            else:
                try:
                    fetched = S.fetch_tencent(sym, date(2005, 1, 1), end)
                except http.FetchError as exc:
                    _log(log, f"bars {code} FAIL {exc}")
                    fetched = None
                if fetched and fetched.rows:
                    result = store.write_series(con, code, "tencent_etf", fetched.rows, DB.now())
                    bars_status = "fetched" if result["status"] in {"fetched", "appended"} else result["status"]
                    _log(log, f"bars {code} {result}")
                else:
                    bars_status = "取不到"
            note = (
                f"来自东财基金代码表，类型 {profile.get('fund_type') or row.get('fund_type') or 'TBD'}；"
                f"跟踪标的分类 {profile.get('single_index')}；成立日期栏 {profile.get('setup_date') or 'TBD'}。"
                "上交所上市日没有列表接口时记 TBD。联接基金未纳入。单一指数从上市日起进入 U-指数。"
            )
            members.append({
                "code": code, "name": profile.get("full_name") or row["name"], "track": profile.get("track") or "",
                "single_index": profile.get("single_index") or "unknown", "list_date": list_date,
                "list_date_source": list_src, "nav_rows": nav_rows, "bars_status": bars_status, "note": note,
            })
            time.sleep(0.05)
        summary = emit_universe.emit(con)
        _log(log, f"qdii members fetched {len(members)} single={sum(1 for r in members if r['single_index']=='single_index')}")
        _log(log, f"emit {summary}")
        fill_amounts(con, log)
        DB.write_requests(con, run_id, http.LOG)
        DB.finish_run(con, run_id, "ok")
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()
    after = book.after("v3-L1-qdii")
    return {"before": before, "after": after, "hashes": book.lines, "log": log, "integrity": integrity, "members": len(chosen)}


def run(end: date = END, *, log: list[str] | None = None) -> dict:
    if log is None:
        log = []
    http.LOG.clear()
    archive_csi_identity(log)
    path = DB.MARKET_DB
    book = store.ledger(path)
    before = book.before("v3-L1")
    con = store.connect(path)
    store.ensure_nav(con)
    failed = []
    try:
        book.before("v3-L1 start_run")
        run_id = DB.start_run(con, "backfill", end=end, args={"job": "v3-L1", "end": end.isoformat()})
        book.after("v3-L1 start_run")
        fetch_csi_series(con, log, end)
        fetch_hk(con, log, end)
        fetch_sge(con, log, end)
        failed = probe_gaps(log)
        discover_industry_etfs(log)
        fetch_qdii(con, run_id, log, end)
        apply_szse_list_dates(log)
        # 行业 ETF 可能刚写入登记表，补它们的日线。
        for box in U.containers():
            if str(box.get("generated") or "") == "qdii":
                continue
            for ex in box.get("execution") or []:
                if ex.get("bars_status") != "TBD":
                    continue
                code = ex["code"]
                sym = phase1.fund_tencent(code)
                if not sym:
                    continue
                have = con.execute("SELECT count(*) FROM bars WHERE code = ? AND adj = 'raw'", (code,)).fetchone()[0]
                if have:
                    continue
                try:
                    fetched = S.fetch_tencent(sym, date(2005, 1, 1), end)
                except http.FetchError as exc:
                    _log(log, f"bars {code} FAIL {exc}")
                    continue
                if fetched.rows:
                    result = store.write_series(con, code, "tencent_etf", fetched.rows, DB.now())
                    _log(log, f"bars {code} {result}")
        sync_bar_status(con, log)
        fill_amounts(con, log)
        DB.write_requests(con, run_id, http.LOG)
        DB.finish_run(con, run_id, "ok" if not failed else "partial")
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()
    after = book.after("v3-L1")
    return {"before": before, "after": after, "hashes": book.lines, "log": log, "failed": failed, "integrity": integrity}
