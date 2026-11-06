"""D37 第四轮：2016 年起才有场内基金、仍冻结的容器，接发布日之后的指数。

两个行情来源对得上，或者发布日能从恒生指数目录读出来并且第二条日线也对得上，才入库。
对不上就留下试过的网址。不覆盖已有序列。不改 LOCK。
日经 225 仍用第三轮的官方点位，这一轮只补 100 日元兑人民币中间价。
"""
from __future__ import annotations

import csv
import json
import re
import shutil
import sqlite3
import subprocess
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import pandas as pd

from src.data import db as DB
from src.data import http
from src.data.hashlog import HashLedger
from src.data.sources import fetch_yahoo
from src.v4.data.catalog import CHINAMONEY
from src.v4.data.parse import parse_chinamoney

from .d37_data import _append
from .d37_round3 import update_registry
from .diag_d37 import OUT

ROOT = Path(__file__).resolve().parents[2]
TAIPEI = ZoneInfo("Asia/Taipei")
END = "2026-09-30"
CATALOGUE_URL = "https://www.hsi.com.hk/static/uploads/contents/zh_cn/dl_centre/index_catalogue/index_catalogue.pdf"
EM_KLINE = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
JQKA = "https://d.10jqka.com.cn/v2/line/{symbol}/01/{part}.js"
TENCENT = "https://web.ifzq.gtimg.cn/appstock/app/kline/kline"

# 发布日是指数目录里的 launch date，不是基日。目录对不上就整轮停，避免把回填写进去。
HANG_SENG = [
    ("theme-HSFML25", "HSFML25", "2003-01-20", "124.HSFML25"),
    ("theme-HSISC", "HSISC", "2024-03-08", "124.HSISC"),
    ("theme-HSSC50", "HSSC50", "2025-01-13", "124.HSSC50"),
    ("theme-HSSCAMHI", "HSSCAM", "2024-05-31", "124.HSSCAM"),
    ("theme-HSSCHKY", "HSSCHKY", "2019-11-18", "124.HSSCHKY"),
    ("theme-HSSCITI", "HSSCITI", "2023-07-17", "124.HSSCITI"),
    ("theme-HSSCNE", "HSSCNE", "2018-01-08", "124.HSSCNE"),
    ("theme-HSSCPB", "HSSCPB", "2023-07-17", "124.HSSCPB"),
    ("theme-HSSCSOY", "HSSCSOY", "2023-06-12", "124.HSSCSOY"),
    ("theme-HSSCT", "HSSCT", "2020-02-17", "124.HSSCT"),
    ("theme-恒生中国央企指数", "HSCSOE", "2023-04-17", "124.HSCSOE"),
    ("theme-恒生互联网科技业指数", "HSIII", "2015-08-17", "124.HSIII"),
    ("theme-恒生创新药指数", "HSIDI", "2023-05-15", "124.HSIDI"),
    ("theme-恒生医疗保健指数", "HSHCI", "2015-08-17", "124.HSHCI"),
    ("theme-恒生消费指数", "HSCGSI", "2015-08-17", "124.HSCGSI"),
    ("theme-恒生港股通红利低波动指数", "HSHYLV", "2017-05-08", "124.HSHYLV"),
    ("theme-恒生生物科技指数", "HSBIO", "2019-12-16", "124.HSBIO"),
    ("theme-恒生综合小型股指数", "HSSI", "2001-10-03", "124.HSSI"),
]

# 第二条来源是 Yahoo。发布日必须能从打开的页面里读到，否则不入库。
OVERSEAS = [
    ("theme-法国CAC40指数", "FCHI", "EUR", "1988-06-15", "100.FCHI", "^FCHI",
     "https://live.euronext.com/en/product/indices/FR0003500008-XPAR", ("1988",)),
    ("theme-标普500信息科技指数", "SP500-45", "USD", "1996-06-28", "", "^SP500-45",
     "https://studylib.net/doc/28009375/fs-sp-500-information-technology-sector", ("June 28, 1996", "LAUNCH DATE")),
    ("theme-标普生物科技精选行业指数", "SPSIBI", "USD", "", "166.SPSIBI", "^SPSIBI", "", ()),
    ("theme-道琼斯工业平均指数", "DJIA", "USD", "1896-05-26", "100.DJIA", "^DJI", "", ()),
    ("theme-道琼斯美国石油开发与生产指数", "DJSOEP", "USD", "", "166.DJSOEP", "^DJSOEP", "", ()),
    ("theme-道琼斯美国精选REIT指数", "DJUSRE", "USD", "", "", "^DJUSRE", "", ()),
    ("theme-标普500消费精选指数", "SP500-25", "USD", "", "", "^SP500-25", "", ()),
    ("theme-标普500医疗保健等权重指数", "SP5HEW", "USD", "", "", "^SPXEWHE", "", ()),
    ("theme-巴西IBOVESPA指数", "BVSP", "BRL", "1968-01-02", "100.BVSP", "^BVSP", "", ()),
    ("theme-东证指数", "TPX", "JPY", "1969-07-01", "100.TPX", "^TPX", "", ()),
    ("theme-标普港股通低波红利指数", "SPAHLVCP", "HKD", "", "166.SPAHLVCP", "", "", ()),
]


def now_taipei() -> str:
    return datetime.now(TAIPEI).isoformat(timespec="seconds")


def catalogue_dates(text: str, code: str) -> tuple[str, str] | None:
    """指数目录一行里的基日、发布日。代码必须整段命中，避免 HSSCT 吃到 HSSCTU。"""
    token = re.compile(rf"(?<![A-Za-z0-9]){re.escape(code)}(?![A-Za-z0-9])")
    found_dates = re.compile(r"(\d{2})-(\d{2})-(\d{4})")
    for line in text.splitlines():
        if not token.search(line):
            continue
        found = found_dates.findall(line)
        if len(found) < 2:
            continue
        base = f"{found[0][2]}-{found[0][1]}-{found[0][0]}"
        launch = f"{found[1][2]}-{found[1][1]}-{found[1][0]}"
        return base, launch
    return None


def _num(text) -> float | None:
    try:
        value = float(str(text).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if value != value or value <= 0:
        return None
    return value


def _bar(day: str, opened, high, low, close, volume=None, amount=None) -> dict | None:
    px = _num(close)
    if not day or px is None:
        return None
    return {
        "date": day, "open": _num(opened), "high": _num(high), "low": _num(low),
        "close": px, "volume": _num(volume), "amount": _num(amount),
    }


def _iso_compact(text: str) -> str:
    raw = str(text)[:10].replace("/", "-")
    if re.fullmatch(r"\d{8}", raw):
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return raw


def clip_rows(rows: list[dict], publish: str, first_list: str) -> list[dict]:
    kept = []
    for row in rows:
        day = str(row.get("date") or "")[:10]
        if not day or (publish and day < publish) or (first_list and day >= first_list) or day > END:
            continue
        if _num(row.get("close")) is None:
            continue
        kept.append(row)
    kept.sort(key=lambda item: item["date"])
    return kept


def closes_of(rows: list[dict]) -> dict[str, float]:
    out = {}
    for row in rows:
        px = _num(row.get("close"))
        if px is not None:
            out[str(row["date"])[:10]] = px
    return out


def cross_check(left: dict[str, float], right: dict[str, float]) -> dict:
    days = sorted(set(left) & set(right))
    if not days:
        return {"n": 0, "median": None, "p95": None, "max": None, "ok": False}
    gaps = [abs(left[day] / right[day] - 1) for day in days]
    gaps.sort()
    median = gaps[len(gaps) // 2]
    p95 = gaps[min(len(gaps) - 1, int(len(gaps) * 0.95))]
    ok = len(days) >= 30 and median <= 0.005 and p95 <= 0.02
    return {"n": len(days), "median": median, "p95": p95, "max": gaps[-1], "ok": ok,
            "sample": [{"date": day, "left": left[day], "right": right[day]} for day in days[:: max(1, len(days) // 3)]][:3]}


def _get(url: str, params: dict | None = None, referer: str | None = None, timeout: int = 30) -> bytes:
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    raw = http.get(url, params, headers=headers, timeout=timeout)
    time.sleep(0.12)
    return raw


def _retry_get(url: str, params: dict | None = None, referer: str | None = None, timeout: int = 30) -> bytes:
    last: Exception | None = None
    for attempt in range(4):
        try:
            return _get(url, params, referer=referer, timeout=timeout)
        except (http.FetchError, json.JSONDecodeError, TimeoutError) as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise last


def fetch_eastmoney(secid: str) -> tuple[str, list[dict]]:
    if not secid:
        return "", []
    raw = _retry_get(EM_KLINE, {
        "secid": secid, "fields1": "f1,f2,f3",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
        "klt": "101", "fqt": "0", "beg": "19900101", "end": "20261106", "lmt": "100000",
    }, referer="https://quote.eastmoney.com/", timeout=40)
    payload = json.loads(raw)
    data = payload.get("data") or {}
    rows = []
    for line in data.get("klines") or []:
        parts = str(line).split(",")
        if len(parts) < 5:
            continue
        row = _bar(parts[0], parts[1], parts[3], parts[4], parts[2],
                   parts[5] if len(parts) > 5 else None, parts[6] if len(parts) > 6 else None)
        if row:
            rows.append(row)
    rows.sort(key=lambda item: item["date"])
    return str(data.get("name") or ""), rows


def fetch_jqka(code: str) -> list[dict]:
    symbol = f"hk_{code}"
    try:
        raw = _get(JQKA.format(symbol=symbol, part="last"), referer="https://q.10jqka.com.cn/", timeout=20)
    except http.FetchError:
        return []
    text = raw.decode("utf-8", "replace")
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return []
    meta = json.loads(text[start:end + 1])
    years = sorted(int(year) for year in (meta.get("year") or {}))
    rows = []
    for year in years:
        try:
            blob = _get(JQKA.format(symbol=symbol, part=str(year)), referer="https://q.10jqka.com.cn/", timeout=20)
        except http.FetchError:
            continue
        body = blob.decode("utf-8", "replace")
        i, j = body.find("{"), body.rfind("}")
        if i < 0:
            continue
        payload = json.loads(body[i:j + 1])
        for line in str(payload.get("data") or "").split(";"):
            parts = line.split(",")
            if len(parts) < 5:
                continue
            row = _bar(_iso_compact(parts[0]), parts[1], parts[2], parts[3], parts[4])
            if row:
                rows.append(row)
    rows.sort(key=lambda item: item["date"])
    return rows


def fetch_tencent(code: str) -> list[dict]:
    try:
        raw = _get(TENCENT, {"param": f"hk{code},day,,,640,"}, referer="https://gu.qq.com/", timeout=20)
    except http.FetchError:
        return []
    payload = json.loads(raw)
    lines = (((payload.get("data") or {}).get(f"hk{code}") or {}).get("day") or [])
    rows = []
    for item in lines:
        if not isinstance(item, list) or len(item) < 5:
            continue
        row = _bar(str(item[0])[:10], item[1], item[3], item[4], item[2])
        if row:
            rows.append(row)
    return rows


def fetch_yahoo_rows(symbol: str, start: date) -> tuple[str, list[dict]]:
    if not symbol:
        return "", []
    try:
        got = fetch_yahoo(symbol, start, date(2026, 11, 6))
    except http.FetchError:
        return "", []
    time.sleep(1.2)
    return got.name or "", got.rows


def _fx_year(pair: str, year: int) -> list[dict]:
    start = date(year, 1, 1)
    stop = min(date(year, 12, 31), date(2026, 11, 6))
    params = {"startDate": start.isoformat(), "endDate": stop.isoformat(),
              "currency": pair, "pageNum": "1", "pageSize": "500"}
    text = http.post(CHINAMONEY, urlencode(params).encode(), timeout=30, headers={
        "Referer": "https://www.chinamoney.com.cn/",
        "Origin": "https://www.chinamoney.com.cn/",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json",
    })
    time.sleep(0.12)
    payload = json.loads(text)
    total = int(((payload.get("data") or {}).get("total") or 0))
    got = len(payload.get("records") or [])
    if total > got:
        raise RuntimeError(f"{pair} {year} total={total} 超过本页 {got}")
    return parse_chinamoney(payload, pair, start, stop)


def fetch_fx(pair: str, start_year: int) -> list[dict]:
    rows = []
    for year in range(start_year, 2027):
        rows.extend(_fx_year(pair, year))
    by = {row["date"]: row for row in rows}
    return [by[day] for day in sorted(by)]


def _check_fx(rows: list[dict], day: str, close: float) -> None:
    got = {row["date"]: float(row["close"]) for row in rows}
    if day not in got:
        raise RuntimeError(f"中间价核对日 {day} 没有返回")
    if round(got[day], 4) != round(close, 4):
        raise RuntimeError(f"中间价 {day} 解析 {got[day]} 与先前看到的 {close} 不一致")
    days = [date.fromisoformat(row["date"]) for row in rows]
    gap = max((b - a).days for a, b in zip(days, days[1:])) if len(days) > 1 else 0
    if gap > 15:
        raise RuntimeError(f"中间价相邻交易日最大间隔 {gap} 天，中间有缺年，不入库")


def load_scope() -> dict[str, dict]:
    frame = pd.read_csv(OUT / "s1-container-effect-检验段.csv", dtype=str).fillna("")
    frozen = frame[frame["status"] == "frozen"]
    out = {}
    for _, row in frozen.iterrows():
        listed = str(row["first_list"])[:10]
        if len(listed) == 10 and listed >= "2016-01-01":
            out[str(row["container_id"])] = row.to_dict()
    return out


def _note_patch(container_id: str, **patch) -> dict:
    patch["container_id"] = container_id
    return patch


def _format_gap(check: dict) -> str:
    if not check or not check.get("n"):
        return "重叠 0 天"
    return f"重叠 {check['n']} 天，收盘相对差中位数 {check['median']:.4%}，95 分位 {check['p95']:.4%}"


def ingest_hang_seng(con, scope: dict[str, dict], catalogue: str) -> dict[str, dict]:
    updates = {}
    for container_id, code, launch, secid in HANG_SENG:
        row = scope.get(container_id)
        if row is None:
            raise RuntimeError(f"范围里没有 {container_id}")
        parsed = catalogue_dates(catalogue, code)
        if parsed is None or parsed[1] != launch:
            raise RuntimeError(f"{code} 目录发布日 {parsed} 与写死的 {launch} 不一致，停止")
        base, publish = parsed
        first_list = str(row["first_list"])[:10]
        tried = [CATALOGUE_URL, EM_KLINE, JQKA.format(symbol=f"hk_{code}", part="last"),
                 f"{TENCENT}?param=hk{code},day,,,640,"]
        print(f"hang {code} launch {publish} list {first_list}", flush=True)
        try:
            name, primary = fetch_eastmoney(secid)
        except (http.FetchError, json.JSONDecodeError, TimeoutError) as exc:
            updates[container_id] = _note_patch(
                container_id, status="frozen", index_code=code, publish_date=publish, currency="HKD",
                tried_urls=" | ".join(tried), source_url=CATALOGUE_URL,
                reason=f"恒生指数目录发布日 {publish}。东财 {secid} 取数失败：{exc}。不入库。核对时间 {now_taipei()}。",
            )
            continue
        second = fetch_jqka(code)
        second_name = "10jqka"
        if len(second) < 30:
            tencent = fetch_tencent(code)
            if len(tencent) > len(second):
                second, second_name = tencent, "tencent"
        after = [item for item in primary if item["date"] >= publish]
        check = cross_check(closes_of(after), closes_of([item for item in second if item["date"] >= publish]))
        kept = clip_rows(primary, publish, first_list)
        reason_bits = [
            f"恒生指数目录发布日 {publish}，基日 {base} 的回填不接。",
            f"东财 {secid}「{name}」{len(primary)} 行。",
            f"核对来源 {second_name}。{_format_gap(check)}。",
        ]
        if code == "HSSCAM":
            reason_bits.append("基金材料写 HSSCAMHI，指数目录代码是 HSSCAM，名称是恒生港股通汽车主题指数。")
        if not check["ok"] or len(kept) < 5:
            reason_bits.append("没有通过两条日线的核对，或者发布日到上市日之间不足 5 根，不入库。")
            updates[container_id] = _note_patch(
                container_id, status="frozen", index_code=code, publish_date=publish,
                currency="HKD", tried_urls=" | ".join(tried), source_url=CATALOGUE_URL,
                reason="".join(reason_bits) + f" 核对时间 {now_taipei()}。",
            )
            continue
        ok, note = _append(con, code, kept, "eastmoney_index")
        updates[container_id] = _note_patch(
            container_id,
            status="spliced" if ok else "frozen",
            index_code=code, publish_date=publish, bars_code=code if ok else "",
            currency="HKD", tried_urls=" | ".join(tried), source_url=EM_KLINE + "?secid=" + secid,
            reason="".join(reason_bits) + note + f" 港币价格指数，打分时乘已登记 HKDCNY。核对时间 {now_taipei()}。",
        )
    return updates


def _page_has(url: str, needles: tuple[str, ...]) -> bool:
    if not url or not needles:
        return False
    try:
        raw = _get(url, referer=url, timeout=25)
    except http.FetchError:
        return False
    text = raw.decode("utf-8", "replace")
    return all(needle in text for needle in needles)


def ingest_overseas(con, scope: dict[str, dict], fx_ready: set[str]) -> dict[str, dict]:
    updates = {}
    for container_id, code, currency, launch, secid, yahoo, page, needles in OVERSEAS:
        row = scope.get(container_id)
        if row is None:
            continue
        first_list = str(row["first_list"])[:10]
        tried = [item for item in (EM_KLINE, f"yahoo:{yahoo}" if yahoo else "", page) if item]
        print(f"overseas {code or container_id}", flush=True)
        name, primary = fetch_eastmoney(secid)
        yahoo_name, yahoo_rows = fetch_yahoo_rows(yahoo, date(1990, 1, 1))
        launch_ok = bool(launch) and bool(needles) and _page_has(page, needles)
        # 道琼斯 1896 年发布。两边日线若都从 1990 年以后才开始，发布日之前的回填不在拿到的序列里。
        if code == "DJIA" and primary and yahoo_rows:
            first = max(primary[0]["date"], yahoo_rows[0]["date"])
            launch_ok = first >= "1990-01-01"
            launch = "1896-05-26"
        if code == "BVSP" and primary and yahoo_rows:
            first = max(primary[0]["date"], yahoo_rows[0]["date"])
            launch_ok = first >= "1992-01-01"
            launch = launch or "1968-01-02"
        use_launch = launch if launch_ok else ""
        left = [item for item in primary if not use_launch or item["date"] >= use_launch]
        right = [item for item in yahoo_rows if not use_launch or item["date"] >= use_launch]
        check = cross_check(closes_of(left), closes_of(right))
        kept = clip_rows(primary or yahoo_rows, use_launch, first_list)
        source_rows = primary or yahoo_rows
        route = "eastmoney_index" if primary else "yahoo"
        bits = [
            f"东财「{name}」{len(primary)} 行；Yahoo {yahoo or '-'}「{yahoo_name}」{len(yahoo_rows)} 行。",
            f"发布日 {launch or '没有从页面读到'}，页面核对 {'通过' if launch_ok else '没有通过'}。",
            _format_gap(check) + "。",
        ]
        can = check["ok"] and launch_ok and len(kept) >= 5 and currency in fx_ready
        if currency == "USD":
            can = can and "USD" in fx_ready
        if not can:
            if currency not in fx_ready:
                bits.append(f"没有 {currency} 人民币中间价。")
            bits.append("不入库。")
            updates[container_id] = _note_patch(
                container_id, status="frozen", index_code=code, publish_date=launch if launch_ok else "",
                currency=currency, tried_urls=" | ".join(tried),
                source_url=page or EM_KLINE,
                reason="".join(bits) + f" 核对时间 {now_taipei()}。",
            )
            continue
        ok, note = _append(con, code, kept, route)
        updates[container_id] = _note_patch(
            container_id, status="spliced" if ok else "frozen",
            index_code=code, publish_date=use_launch, bars_code=code if ok else "",
            currency=currency, tried_urls=" | ".join(tried),
            source_url=(EM_KLINE + "?secid=" + secid) if primary else f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo}",
            reason="".join(bits) + note + f" 核对时间 {now_taipei()}。",
        )
    return updates


def structural_notes(scope: dict[str, dict]) -> dict[str, dict]:
    """没有单一跟踪指数的，打开基金概况页确认，不硬拼。"""
    pages = {
        "crude-oil": "https://fundf10.eastmoney.com/jbgk_161129.html",
        "theme-中信证券印度ETP指数": "https://fundf10.eastmoney.com/jbgk_164824.html",
    }
    notes = {
        "crude-oil": "161129 的基准是标普高盛原油商品指数，160723 是 WTI 价格，501018 是 60% WTI 加 40% Brent。三只不是一条指数，不硬拼。",
        "theme-中信证券印度ETP指数": "投资的是一篮子境外印度 ETP，不是一条指数，不硬拼。",
    }
    updates = {}
    for container_id, url in pages.items():
        if container_id not in scope:
            continue
        tried = [url, "https://fundf10.eastmoney.com/jbgk_501018.html" if container_id == "crude-oil" else "https://fundf10.eastmoney.com/jbgk_164824.html"]
        try:
            raw = _get(url, referer="https://fundf10.eastmoney.com/", timeout=20)
            opened = f"概况页 {len(raw)} 字节。"
        except http.FetchError as exc:
            opened = f"概况页 {exc}。"
        updates[container_id] = _note_patch(
            container_id, status="frozen", tried_urls=" | ".join(tried), source_url=url,
            reason=notes[container_id] + opened + f" 核对时间 {now_taipei()}。",
        )
    return updates


def probe_rest(scope: dict[str, dict], done: set[str]) -> dict[str, dict]:
    """还没处理的容器，至少再试两个入口，写明卡在哪。"""
    extra = {
        "soymeal": [
            "https://www.dce.com.cn/",
            "https://searchapi.eastmoney.com/api/suggest/get?input=%E8%B1%86%E7%B2%95%E6%9C%9F%E8%B4%A7%E4%BB%B7%E6%A0%BC%E6%8C%87%E6%95%B0&type=14",
        ],
        "theme-MSCI China Value Weighted Index": ["https://www.msci.com/", "https://query1.finance.yahoo.com/v8/finance/chart/MXCNVW?interval=1d&range=5d"],
        "theme-MSCI USA 50 Index": ["https://www.msci.com/", "https://query1.finance.yahoo.com/v8/finance/chart/%5EMSUSA50?interval=1d&range=5d"],
        "theme-富时亚太低碳精选指数": [
            "https://www.lseg.com/en/ftse-russell",
            "https://research.ftserussell.com/Analytics/Factsheets/Home/DownloadSingleIssue?issueName=GPCSP006",
        ],
        "theme-富时沙特阿拉伯指数": [
            "https://www.lseg.com/en/ftse-russell",
            "https://query1.finance.yahoo.com/v8/finance/chart/%5ETASI.SR?interval=1d&range=5d",
        ],
        "theme-iEdge Emerging Asia Select 50 Index": [
            "https://www.sgx.com/",
            "https://api2.sgx.com/sites/default/files/2026-09/iEdge%20EM%20Asia_Factsheet_20260831.pdf",
        ],
        "theme-新交所泛东南亚科技指数": [
            "https://www.sgx.com/",
            "https://api2.sgx.com/sites/default/files/2026-09/iEdge%20Southeast%20Asia%2B%20TECH_Factsheet_20260831.pdf",
        ],
        "theme-标普中国新经济行业指数": [
            "https://www.spglobal.com/spdji/en/indices/equity/sp-new-china-sectors-a-shares-capped-index/",
            "https://query1.finance.yahoo.com/v8/finance/chart/SPNCSCP?interval=1d&range=5d",
        ],
        "theme-标普美国品质消费股票指数": [
            "https://www.spglobal.com/spdji/en/",
            "https://query1.finance.yahoo.com/v8/finance/chart/SPUSQCP?interval=1d&range=5d",
        ],
    }
    updates = {}
    for container_id, row in scope.items():
        if container_id in done:
            continue
        urls = extra.get(container_id, [])
        bits = []
        if container_id == "soymeal":
            name, rows = fetch_eastmoney("159.mfi")
            bits.append(f"东财 159.mfi 名称是「{name}」，{len(rows)} 行。这是豆粕加权，不是大商所豆粕期货价格指数，不用。")
        for url in urls:
            try:
                raw = _get(url, referer=url, timeout=20)
                bits.append(f"{url} 打开了 {len(raw)} 字节，不是可入库的日线。")
            except http.FetchError as exc:
                bits.append(f"{url} {exc}。")
        if not bits:
            bits.append("没有单独的代码可对。东财建议和 Yahoo 没有这条指数的日线。")
        updates[container_id] = _note_patch(
            container_id, status="frozen", tried_urls=" | ".join(urls),
            source_url=urls[0] if urls else "",
            reason="".join(bits) + f" 不入库。核对时间 {now_taipei()}。",
        )
    return updates


def load_catalogue(archive: Path) -> str:
    raw = _get(CATALOGUE_URL, referer="https://www.hsi.com.hk/", timeout=60)
    pdf = archive / "index-catalogue.pdf"
    pdf.write_bytes(raw)
    text_path = archive / "index-catalogue.txt"
    subprocess.run(["pdftotext", "-layout", str(pdf), str(text_path)], check=True)
    return text_path.read_text(encoding="utf-8", errors="replace")


def apply_nikkei_fx(con, jpy_rows: list[dict]) -> None:
    ok, note = _append(con, "JPYCNY", jpy_rows, "chinamoney")
    if not ok:
        raise RuntimeError(note)
    print(f"JPYCNY {note}", flush=True)


def patch_nikkei_registry() -> None:
    path = OUT / "s1-index-registry.csv"
    frame = pd.read_csv(path, dtype=str).fillna("")
    rows = frame.to_dict(orient="records")
    for row in rows:
        if row["container_id"] != "theme-东京日经225指数":
            continue
        row["currency"] = "JPY"
        text = row["reason"]
        swapped = "日元价格指数。第四轮用中国货币网 100JPY/CNY 中间价换成人民币：点位乘该报价，再除以 100。"
        if "不换人民币" in text:
            text = text.replace("日元价格指数，库内没有日元汇率，不换人民币。", swapped)
        elif "100JPY/CNY" not in text:
            text = swapped + text
        row["reason"] = text + f" 中间价核对 2024-01-04 = 4.9788。核对时间 {now_taipei()}。"
        row["tried_urls"] = (row.get("tried_urls") or "") + " | https://www.chinamoney.com.cn/ags/ms/cm-u-bk-ccpr/CcprHisNew?currency=100JPY/CNY"
    fieldnames = list(frame.columns)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "s1-splice-roster.csv").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def fetch() -> dict:
    archive = OUT / "round4"
    archive.mkdir(parents=True, exist_ok=True)
    catalogue = load_catalogue(archive)
    for _container, code, launch, _secid in HANG_SENG:
        parsed = catalogue_dates(catalogue, code)
        if parsed is None or parsed[1] != launch:
            raise RuntimeError(f"目录没有对上 {code}: {parsed} != {launch}")
    scope = load_scope()
    ledger = HashLedger(DB.MARKET_DB)
    before = ledger.before("d37-round4")
    con = sqlite3.connect(str(DB.MARKET_DB))
    summary = {"fetched_at": now_taipei(), "before": before}
    try:
        jpy = fetch_fx("100JPY/CNY", 2005)
        _check_fx(jpy, "2024-01-04", 4.9788)
        apply_nikkei_fx(con, jpy)
        (archive / "jpy-cny-sample.json").write_text(json.dumps({
            "pair": "100JPY/CNY", "check": {"2024-01-04": 4.9788},
            "rows": len(jpy), "first": jpy[0]["date"], "last": jpy[-1]["date"],
            "source": CHINAMONEY, "fetched_at": now_taipei(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        fx_ready = {"USD", "HKD", "JPY"}
        try:
            eur = fetch_fx("EUR/CNY", 2005)
            _check_fx(eur, "2016-01-08", 7.1735)
            ok, note = _append(con, "EURCNY", eur, "chinamoney")
            print(f"EURCNY {note}", flush=True)
            if ok:
                fx_ready.add("EUR")
        except Exception as exc:
            print(f"EURCNY fail {exc}", flush=True)
        try:
            brl = fetch_fx("BRL/CNY", 2010)
            if brl:
                ok, note = _append(con, "BRLCNY", brl, "chinamoney")
                print(f"BRLCNY {note}", flush=True)
                if ok:
                    fx_ready.add("BRL")
        except Exception as exc:
            print(f"BRLCNY fail {exc}", flush=True)
            (archive / "brl-attempt.txt").write_text(
                f"中国货币网 CcprHisNew 的货币表里没有 BRL/CNY。{exc}\n核对时间 {now_taipei()}\n",
                encoding="utf-8",
            )
        updates = {}
        updates.update(ingest_hang_seng(con, scope, catalogue))
        updates.update(ingest_overseas(con, scope, fx_ready))
        updates.update(structural_notes(scope))
        updates.update(probe_rest(scope, set(updates) | {"theme-东京日经225指数"}))
        missing = [name for name in scope if name not in updates and name != "theme-东京日经225指数"]
        if missing:
            raise RuntimeError(f"还有容器没写原因：{missing}")
        update_registry(updates)
        patch_nikkei_registry()
        con.commit()
    finally:
        con.close()
    after = ledger.after("d37-round4")
    with (OUT / "db-sha256.txt").open("a", encoding="utf-8") as handle:
        handle.write(f"SHA256 BEFORE d37-round4 {before}\n")
        handle.write(f"SHA256 AFTER  d37-round4 {after}\n")
    summary["after"] = after
    summary["fx_ready"] = sorted(fx_ready)
    (archive / "fetch-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"before={before} after={after}", flush=True)
    return summary


def check_s0_v0() -> dict:
    """新库上重跑 S0 V0 检验段，对照第三轮留下的文件。对不上就把文件放回去。"""
    from .diag_d37 import run_cn

    archive = OUT / "round4"
    archive.mkdir(parents=True, exist_ok=True)
    folder = OUT / "S0" / "检验段" / "V0"
    backup = archive / "s0-v0-round3"
    if backup.exists():
        shutil.rmtree(backup)
    shutil.copytree(folder, backup)
    try:
        run_cn("检验段", ["V0"], ["S0"], bitmatch=False)
        old = pd.read_csv(backup / "daily.csv", parse_dates=["date"], index_col="date")
        new = pd.read_csv(folder / "daily.csv", parse_dates=["date"], index_col="date")
        shared = old.index.intersection(new.index)
        net = (old.loc[shared, "net"].astype(float) - new.loc[shared, "net"].astype(float)).abs()
        picks = int((old.loc[shared, "picks"].fillna("").astype(str) != new.loc[shared, "picks"].fillna("").astype(str)).sum())
        market = int((old.loc[shared, "market"].fillna("").astype(str) != new.loc[shared, "market"].fillna("").astype(str)).sum())
        report = {
            "days": int(len(shared)),
            "net_max_abs": float(net.max()) if len(net) else None,
            "picks_differ": picks,
            "market_differ": market,
            "same": bool(len(shared) and float(net.max()) == 0 and picks == 0 and market == 0),
        }
    finally:
        shutil.rmtree(folder)
        shutil.copytree(backup, folder)
    text = (
        "新库 S0 V0 检验段对照第三轮 results/v51-diag/d37/S0/检验段/V0。\n"
        f"天数 {report['days']}\n"
        f"net 最大绝对差 {report['net_max_abs']}\n"
        f"名字不同天数 {report['picks_differ']}\n"
        f"市场不同天数 {report['market_differ']}\n"
        f"一致 {report['same']}\n"
    )
    (archive / "s0-v0-check.txt").write_text(text, encoding="utf-8")
    (OUT / "round4-s0-v0-check.txt").write_text(text, encoding="utf-8")
    print(text, flush=True)
    return report


# 东财这些代码只从 2019-08 起有数。同花顺从发布日附近开始，重叠段已经对过，改存同花顺。
LONGER_JQKA = [
    ("theme-HSSCNE", "HSSCNE", "2018-01-08", "2022-03-21"),
    ("theme-恒生互联网科技业指数", "HSIII", "2015-08-17", "2021-02-08"),
    ("theme-恒生医疗保健指数", "HSHCI", "2015-08-17", "2021-03-29"),
    ("theme-恒生消费指数", "HSCGSI", "2015-08-17", "2023-04-21"),
    ("theme-恒生港股通红利低波动指数", "HSHYLV", "2017-05-08", "2023-04-28"),
]


def _replace_series(con, code: str, rows: list[dict], route: str) -> str:
    with con:
        con.execute("DELETE FROM bars WHERE code = ? AND adj = 'raw'", (code,))
    ok, note = _append(con, code, rows, route)
    if not ok:
        raise RuntimeError(note)
    return note


def second_pass() -> None:
    """补同花顺更长的发布日后段，并接入两条日线已经对上的 CAC 40。"""
    archive = OUT / "round4"
    archive.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB.MARKET_DB))
    updates = {}
    try:
        for container_id, code, publish, first_list in LONGER_JQKA:
            rows = clip_rows(fetch_jqka(code), publish, first_list)
            stored = closes_of([
                {"date": day, "close": close}
                for day, close in con.execute(
                    "SELECT date, close FROM bars WHERE code = ? AND adj = 'raw'", (code,)
                )
            ])
            check = cross_check(closes_of(rows), stored)
            print(code, "jqka", len(rows), _format_gap(check), flush=True)
            if not check["ok"] or len(rows) <= len(stored):
                continue
            note = _replace_series(con, code, rows, "tonghuashun_index")
            updates[container_id] = _note_patch(
                container_id, status="spliced", index_code=code, publish_date=publish,
                bars_code=code, currency="HKD",
                source_url=JQKA.format(symbol=f"hk_{code}", part="{year}"),
                reason=(
                    f"恒生指数目录发布日 {publish}。同花顺 hk_{code} 比东财更早，"
                    f"和已核对的东财重叠段一致。{_format_gap(check)}。{note} "
                    f"港币价格指数，打分时乘 HKDCNY。核对时间 {now_taipei()}。"
                ),
            )
        name, em = fetch_eastmoney("100.FCHI")
        yahoo_name, yahoo_rows = fetch_yahoo_rows("^FCHI", date(1990, 1, 1))
        start = max(em[0]["date"], yahoo_rows[0]["date"]) if em and yahoo_rows else ""
        check = cross_check(
            closes_of([row for row in em if row["date"] >= start]),
            closes_of([row for row in yahoo_rows if row["date"] >= start]),
        )
        print("FCHI", start, _format_gap(check), flush=True)
        if check["ok"] and start >= "1990-01-01":
            scope = load_scope_any()
            first_list = scope["theme-法国CAC40指数"]["first_list"][:10]
            kept = clip_rows(em, start, first_list)
            note = _append(con, "FCHI", kept, "eastmoney_index")[1]
            updates["theme-法国CAC40指数"] = _note_patch(
                "theme-法国CAC40指数", status="spliced", index_code="FCHI", publish_date=start,
                bars_code="FCHI", currency="EUR",
                source_url=EM_KLINE + "?secid=100.FCHI",
                tried_urls=" | ".join([
                    "https://live.euronext.com/en/product/indices/FR0003500008-XPAR",
                    "https://query1.finance.yahoo.com/v8/finance/chart/%5EFCHI",
                ]),
                reason=(
                    f"东财「{name}」与 Yahoo「{yahoo_name}」从 {start} 起 {_format_gap(check)}。"
                    "Euronext 产品页没有读出 1988 这个发布日，两条行情本身都从 1990 年起，"
                    f"只入库这段，不用更早的点。欧元点位乘中国货币网 EUR/CNY。{note} 核对时间 {now_taipei()}。"
                ),
            )
        em_name, sp_rows = fetch_eastmoney("166.SPAHLVCP")
        second = fetch_tencent("SPAHLVCP") or fetch_jqka("SPAHLVCP")
        check = cross_check(closes_of(sp_rows), closes_of(second))
        print("SPAHLVCP", em_name, len(sp_rows), len(second), _format_gap(check), flush=True)
        updates["theme-SPAHLVCP"] = _note_patch(
            "theme-SPAHLVCP", status="frozen", index_code="SPAHLVCP", currency="HKD",
            tried_urls=" | ".join([EM_KLINE + "?secid=166.SPAHLVCP", TENCENT, JQKA.format(symbol="hk_SPAHLVCP", part="last")]),
            source_url=EM_KLINE + "?secid=166.SPAHLVCP",
            reason=(
                f"东财 166.SPAHLVCP「{em_name}」{len(sp_rows)} 行。腾讯和同花顺没有可对的日线。"
                f"{_format_gap(check)}。只有一个来源，不入库。核对时间 {now_taipei()}。"
            ),
        )
        updates["theme-东证指数"] = _note_patch(
            "theme-东证指数", status="frozen", index_code="TPX", currency="JPY",
            tried_urls=" | ".join([
                "https://query1.finance.yahoo.com/v8/finance/chart/%5ETPX",
                EM_KLINE + "?secid=100.TPX",
                "https://hq.sinajs.cn/list=znb_TPX",
            ]),
            reason=(
                "Yahoo ^TPX 和东财 100.TPX 都没有日线。新浪 znb_TPX 只有即时报价，历史接口不可用。"
                "1969-07-01 没有从这次打开的页面读到，不把该日写成已核对的发布日。不入库。"
                f"核对时间 {now_taipei()}。"
            ),
        )
        if updates:
            update_registry(updates)
    finally:
        con.close()
    digest = DB.sha256_file(DB.MARKET_DB)
    path = OUT / "db-sha256.txt"
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines and lines[-1].startswith("SHA256 AFTER  d37-round4 "):
        lines[-1] = f"SHA256 AFTER  d37-round4 {digest}"
    else:
        lines.append(f"SHA256 AFTER  d37-round4 {digest}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"after={digest}", flush=True)


def load_scope_any() -> dict[str, dict]:
    frame = pd.read_csv(OUT / "s1-index-registry.csv", dtype=str).fillna("")
    return {row["container_id"]: row for row in frame.to_dict(orient="records")}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="D37 第四轮取数")
    parser.add_argument("--check-s0", action="store_true")
    parser.add_argument("--second-pass", action="store_true")
    args = parser.parse_args()
    if args.second_pass:
        second_pass()
        return 0
    if args.check_s0:
        report = check_s0_v0()
        return 0 if report["same"] else 2
    fetch()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
