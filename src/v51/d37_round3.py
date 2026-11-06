"""D37 第三轮：只补第二轮仍冻结、且冻结 universe 里有容器的指数。

官网能下的才入库。登录墙、付费墙、403 记下来，不绕过。
不覆盖已有序列。只保留正式发布日及之后、首只场内基金上市日之前的点位。
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
from src.data.hashlog import HashLedger
from src.data.sources import fetch_csindex

from .d37_data import _append, _csi_identity, _name_score
from .diag_d37 import OUT

ROOT = Path(__file__).resolve().parents[2]
TAIPEI = ZoneInfo("Asia/Taipei")
END_BEFORE = date(2026, 9, 30)
NIKKEI_URL = "https://indexes.nikkei.co.jp/nkave/statistics/dataload"
NIKKEI_PROFILE = "https://indexes.nikkei.co.jp/en/nkave/index/profile?idx=nk225"
NIKKEI_PAGE = "https://indexes.nikkei.co.jp/nkave/archives/data"
CSI_INFO = "https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info/{code}"
ROW_RE = re.compile(
    r"<td>(\d{4}\.\d{2}\.\d{2})</td>\s*<td>([\d,\.]+)</td>\s*<td>([\d,\.]+)</td>\s*"
    r"<td>([\d,\.]+)</td>\s*<td>([\d,\.]+)</td>",
    re.I,
)

# 全称已在中证官网对过。港币字样在比对时去掉。
CSI_CODES = {
    "theme-中证港股通信息技术综合指数": "930967",
    "theme-中证港股通医药卫生综合指数": "930965",
    "theme-中证港股通汽车产业主题指数": "931239",
    "theme-中证香港科技指数指数": "931574",
    "theme-中证香港创新药港币指数": "931787",
}


def now_taipei() -> str:
    return datetime.now(TAIPEI).isoformat(timespec="seconds")


def parse_nikkei_month(html: str) -> list[dict]:
    """日经档案页一个月的表。列是日期、始值、高值、安值、终值。"""
    rows = []
    for stamp, opened, high, low, close in ROW_RE.findall(html):
        rows.append({
            "date": stamp.replace(".", "-"),
            "open": opened.replace(",", ""),
            "high": high.replace(",", ""),
            "low": low.replace(",", ""),
            "close": close.replace(",", ""),
            "volume": None,
            "amount": None,
        })
    rows.sort(key=lambda item: item["date"])
    return rows


def _num(text: str) -> str:
    return str(text or "").replace(",", "").strip()


def _keep(rows: list[dict], publish: str, first_list: str) -> list[dict]:
    kept = []
    for row in rows:
        day = str(row.get("date") or "")[:10]
        if not day or day < publish or day >= first_list or day > END_BEFORE.isoformat():
            continue
        kept.append(row)
    return kept


def _csi_meta(code: str) -> dict:
    payload = http.get_json(
        CSI_INFO.format(code=code),
        headers={"Referer": "https://www.csindex.com.cn/", "Accept": "application/json"},
        timeout=25,
    )
    data = payload.get("data") if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        data = {}
    currency = str(data.get("currencyEn") or data.get("currencyCn") or "")
    if "HK" in currency.upper() or "港" in currency:
        ccy = "HKD"
    elif "USD" in currency.upper() or "美元" in currency:
        ccy = "USD"
    else:
        ccy = "CNY"
    return {
        "publish": str(data.get("publishDate") or "")[:10],
        "name": str(data.get("indexFullNameCn") or ""),
        "currency": ccy,
        "currency_text": currency,
    }


def fetch_nikkei(con, first_list: str, archive: Path) -> dict:
    """日经官方按月表。发布日是概况页的 Commencement date。不用库内 yahoo 的 N225。"""
    tried = [NIKKEI_PAGE, NIKKEI_PROFILE, NIKKEI_URL]
    profile = http.get(NIKKEI_PROFILE, headers={"Referer": "https://indexes.nikkei.co.jp/"}, timeout=30)
    (archive / "nikkei-profile.html").write_bytes(profile)
    text = profile.decode("utf-8", "replace")
    if "September/07/1950" not in text:
        return {"status": "frozen", "reason": "日经概况页没有 Commencement date September/07/1950", "tried": tried}
    publish = "1950-09-07"
    rows: list[dict] = []
    # 设计期从 2006 起要能打分，所以从 2005-01 收到上市前。更早的官方表存在，这一轮用到打分窗口。
    year, month = 2005, 1
    stop = date.fromisoformat(first_list)
    sample_saved = False
    while date(year, month, 1) < stop:
        raw = http.get(
            NIKKEI_URL,
            {"list": "daily", "year": str(year), "month": str(month)},
            headers={"Referer": NIKKEI_PAGE},
            timeout=30,
        )
        if not sample_saved:
            (archive / "nikkei-2019-01.html").write_bytes(raw) if (year, month) == (2019, 1) else None
            if year == 2005 and month == 1:
                (archive / "nikkei-2005-01.html").write_bytes(raw)
        html = raw.decode("utf-8", "replace")
        rows.extend(parse_nikkei_month(html))
        month += 1
        if month == 13:
            month = 1
            year += 1
        time.sleep(0.12)
    (archive / "nikkei-2019-06.html").write_bytes(http.get(
        NIKKEI_URL, {"list": "daily", "year": "2019", "month": "6"},
        headers={"Referer": NIKKEI_PAGE}, timeout=30,
    ))
    kept = _keep(rows, publish, first_list)
    if len(kept) < 1000:
        return {"status": "frozen", "reason": f"日经按月表只解析出 {len(kept)} 行，不入库", "tried": tried, "publish_date": publish}
    ok, note = _append(con, "NK225", kept, "nikkei_official")
    return {
        "status": "spliced" if ok else "frozen",
        "bars_code": "NK225" if ok else "",
        "index_code": "NK225",
        "publish_date": publish,
        "currency": "LOCAL",
        "price_basis": "price",
        "reason": f"日经官方按月表，概况页 Commencement date 1950-09-07。日元价格指数，库内没有日元汇率，不换人民币。{note}",
        "tried": tried,
        "fetched_at": now_taipei(),
        "source_url": NIKKEI_URL,
    }


def fetch_one_csi(con, container_id: str, code: str, index_name: str, first_list: str, archive: Path) -> dict:
    url = CSI_INFO.format(code=code)
    meta = _csi_meta(code)
    publish, full = meta["publish"], meta["name"]
    tried = [url]
    if _name_score(index_name, full) < 2:
        return {"status": "frozen", "reason": f"中证全称「{full}」对不上「{index_name}」", "tried": tried, "publish_date": publish}
    if not publish or not first_list or publish >= first_list:
        return {"status": "frozen", "reason": f"中证 {code}（{full}）发布日 {publish or '无'} 不早于首只基金 {first_list}", "tried": tried, "publish_date": publish}
    listed = date.fromisoformat(first_list)
    last = date.fromordinal(listed.toordinal() - 1)
    fetched = fetch_csindex(code, date.fromisoformat(publish), last, pause=0.15)
    (archive / f"csi-{code}-note.json").write_text(json.dumps({
        "url": url, "publish": publish, "name": full, "currency": meta["currency_text"],
        "rows": len(fetched.rows), "fetched_at": now_taipei(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    kept = _keep(fetched.rows, publish, first_list)
    if not kept:
        return {"status": "frozen", "reason": f"中证 {code} 在发布日与上市日之间没有行情", "tried": tried, "publish_date": publish}
    ok, note = _append(con, code, kept, "csindex")
    return {
        "status": "spliced" if ok else "frozen",
        "bars_code": code if ok else "",
        "index_code": code,
        "publish_date": publish,
        "currency": meta["currency"],
        "price_basis": "price",
        "reason": f"{full}；币种 {meta['currency_text'] or meta['currency']}。{note} 只留 {publish} 至上市前。",
        "tried": tried,
        "fetched_at": now_taipei(),
        "source_url": url,
    }


def _probe(url: str, referer: str | None = None) -> str:
    try:
        raw = http.get(url, headers={"Referer": referer or url, "Accept": "*/*"}, timeout=20)
        return f"ok:{len(raw)}"
    except Exception as exc:
        return f"{type(exc).__name__}:{str(exc)[:140]}"


def blocked_notes(archive: Path) -> dict[str, dict]:
    """这一轮实际打开过、但没有免费日线的站点。每个容器一条原因。"""
    stamp = now_taipei()
    hsi_chart = _probe("https://www.hsi.com.hk/data/eng/indexes/hscei/chart-rebased.json", "https://www.hsi.com.hk/")
    hsi_page = _probe("https://www.hsi.com.hk/eng/indexes/all-indexes/hscei")
    hsi_account = "https://www.hsi.com.hk/en-hk/index360/create-account/"
    hsi_reason = (
        f"恒生指数详情页是前端壳（{hsi_page}）。chart-rebased.json {hsi_chart}。"
        f"历史日线在 Index360，注册页 {hsi_account}。不注册、不绕过，不用腾讯。"
        f" 核对时间 {stamp}。"
    )
    sp_reason = (
        "标普道琼斯指数页 " + _probe("https://www.spglobal.com/spdji/en/indices/equity/sp-500-information-technology-sector/")
        + "。不绕过 403，不用未知导出。"
        f" 核对时间 {stamp}。"
    )
    stoxx = _probe("https://www.stoxx.com/document/Indices/Current/HistoricalData/h_dax.txt", "https://www.stoxx.com/")
    dax_site = _probe("https://www.dax-indices.com/")
    cac = _probe("https://live.euronext.com/en/product/indices/FR0003500008-XPAR")
    cac_ajax = _probe("https://live.euronext.com/en/ajax/getFullDownloadAjax/FR0003500008-XPAR", "https://live.euronext.com/")
    jpx = _probe("https://www.jpx.co.jp/english/markets/indices/topix/tvdivq00000030ne-att/topixyear_e.xls")
    b3 = _probe("https://www.b3.com.br/en_us/market-data-and-indices/indexes/broad-indexes/ibovespa.htm")
    ftse = _probe("https://research.ftserussell.com/Analytics/Factsheets/Home/DownloadSingleIssue?issueName=GPCSP006")
    sgx = _probe("https://api2.sgx.com/sites/default/files/2026-09/iEdge%20EM%20Asia_Factsheet_20260831.pdf")
    msci = _probe("https://www.msci.com/indexes/index/704966")
    dce = _probe("https://www.dce.com.cn/")
    szse = _probe("https://www.szse.cn/api/report/ShowReport?SHOWTYPE=JSON&CATALOGID=1815_stock_index&TABKEY=tab1&txtDMorJC=399006")
    (archive / "blocked-probes.json").write_text(json.dumps({
        "fetched_at": stamp,
        "hsi_chart": hsi_chart, "hsi_page": hsi_page, "sp": sp_reason,
        "stoxx": stoxx, "dax_site": dax_site, "cac": cac, "cac_ajax": cac_ajax,
        "jpx_year_xls": jpx, "b3": b3, "ftse": ftse, "sgx": sgx, "msci": msci,
        "dce": dce, "szse": szse,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    notes = {
        "hangseng": {"reason": hsi_reason, "tried": [
            "https://www.hsi.com.hk/eng/indexes/all-indexes/hscei",
            "https://www.hsi.com.hk/data/eng/indexes/hscei/chart-rebased.json",
            hsi_account,
        ]},
        "sp": {"reason": sp_reason, "tried": [
            "https://www.spglobal.com/spdji/en/indices/equity/sp-500-information-technology-sector/",
            "https://www.spglobal.com/spdji/en/indices/equity/dow-jones-industrial-average/",
        ]},
        "dax": {"reason": f"德交所/STOXX 历史文件 {stoxx}；dax-indices.com {dax_site}。没有免费日线。核对时间 {stamp}。", "tried": [
            "https://www.stoxx.com/document/Indices/Current/HistoricalData/h_dax.txt",
            "https://www.dax-indices.com/",
        ]},
        "cac": {"reason": f"泛欧产品页 {cac}；猜测的下载接口 {cac_ajax}。页面没有匿名日线导出。核对时间 {stamp}。", "tried": [
            "https://live.euronext.com/en/product/indices/FR0003500008-XPAR",
            "https://live.euronext.com/en/ajax/getFullDownloadAjax/FR0003500008-XPAR",
        ]},
        "topix": {"reason": f"JPX 公开的是年度表 topixyear_e.xls（{jpx}）和事实表，不是日线。不把年度表当成日线。核对时间 {stamp}。", "tried": [
            "https://www.jpx.co.jp/english/markets/indices/topix/index.html",
            "https://www.jpx.co.jp/english/markets/indices/topix/tvdivq00000030ne-att/topixyear_e.xls",
        ]},
        "b3": {"reason": f"B3 Ibovespa 介绍页 {b3}。没有匿名日线文件。核对时间 {stamp}。", "tried": [
            "https://www.b3.com.br/en_us/market-data-and-indices/indexes/broad-indexes/ibovespa.htm",
        ]},
        "ftse": {"reason": f"富时罗素事实表 {ftse}。事实表不是日线，历史库要登录。不注册。核对时间 {stamp}。", "tried": [
            "https://www.lseg.com/en/ftse-russell",
            "https://research.ftserussell.com/Analytics/Factsheets/Home/DownloadSingleIssue?issueName=GPCSP006",
        ]},
        "sgx": {"reason": f"新交所事实表 {sgx}。事实表不是日线。核对时间 {stamp}。", "tried": [
            "https://www.sgx.com/",
            "https://api2.sgx.com/sites/default/files/2026-09/iEdge%20EM%20Asia_Factsheet_20260831.pdf",
        ]},
        "msci": {"reason": f"MSCI 指数页 {msci}。历史数据在登录后的终端，不注册、不绕过。核对时间 {stamp}。", "tried": [
            "https://www.msci.com/",
        ]},
        "dce": {"reason": f"大商所首页 {dce}。没有取到豆粕期货价格指数日线。核对时间 {stamp}。", "tried": [
            "https://www.dce.com.cn/",
        ]},
        "szse": {"reason": (
            f"创业板指 399006 的中证基本信息是空的。深交所报表 {szse}。"
            "库内已有序列来自 tencent_index，不用腾讯接上。"
            f" 核对时间 {stamp}。"
        ), "tried": [
            "https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info/399006",
            "https://www.szse.cn/api/report/ShowReport?SHOWTYPE=JSON&CATALOGID=1815_stock_index&TABKEY=tab1&txtDMorJC=399006",
        ]},
    }
    return notes


def _family(container_id: str) -> str:
    if container_id == "chinext":
        return "szse"
    if container_id == "soymeal":
        return "dce"
    if container_id == "theme-东京日经225指数":
        return "nikkei"
    if container_id == "theme-东证指数":
        return "topix"
    if container_id == "theme-法兰克福DAX指数":
        return "dax"
    if container_id == "theme-法国CAC40指数":
        return "cac"
    if container_id == "theme-巴西IBOVESPA指数":
        return "b3"
    if "富时" in container_id:
        return "ftse"
    if "iEdge" in container_id or "新交所" in container_id:
        return "sgx"
    if container_id.startswith("theme-MSCI"):
        return "msci"
    if container_id.startswith("theme-标普") or container_id.startswith("theme-S&P") or container_id.startswith("theme-SP") or "道琼斯" in container_id:
        return "sp"
    if container_id.startswith("theme-HS") or "恒生" in container_id:
        return "hangseng"
    return ""


def load_targets() -> list[dict]:
    frame = pd.read_csv(OUT / "s1-container-effect-检验段.csv")
    frozen = frame[frame["status"] == "frozen"].copy()
    reason = frozen["reason"].fillna("")
    keep = frozen[~reason.str.contains("冻结 universe") & ~reason.str.contains("没有单一跟踪指数")]
    return keep.to_dict(orient="records")


def update_registry(updates: dict[str, dict]) -> None:
    path = OUT / "s1-index-registry.csv"
    frame = pd.read_csv(path, dtype=str).fillna("")
    rows = frame.to_dict(orient="records")
    by_id = {row["container_id"]: row for row in rows}
    for container_id, patch in updates.items():
        row = by_id.get(container_id)
        if row is None:
            continue
        for key in ("status", "index_code", "publish_date", "bars_code", "currency", "reason", "tried_urls", "source_url"):
            if key in patch and patch[key] is not None:
                row[key] = patch[key]
    fieldnames = list(frame.columns)
    for extra in ("currency", "tried_urls"):
        if extra not in fieldnames:
            fieldnames.append(extra)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "s1-splice-roster.csv").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def main() -> int:
    archive = OUT / "round3"
    archive.mkdir(parents=True, exist_ok=True)
    http.RECORD_DIR = archive / "http"
    targets = load_targets()
    print(f"targets {len(targets)}", flush=True)
    ledger = HashLedger(DB.MARKET_DB)
    before = ledger.before("d37-round3")
    con = sqlite3.connect(str(DB.MARKET_DB))
    updates: dict[str, dict] = {}
    try:
        by_id = {row["container_id"]: row for row in targets}
        if "theme-东京日经225指数" in by_id:
            print("nikkei", flush=True)
            result = fetch_nikkei(con, str(by_id["theme-东京日经225指数"].get("first_list") or "2019-06-25"), archive)
            updates["theme-东京日经225指数"] = {
                "status": result["status"],
                "index_code": result.get("index_code") or "",
                "publish_date": result.get("publish_date") or "",
                "bars_code": result.get("bars_code") or "",
                "currency": result.get("currency") or "",
                "reason": result.get("reason") or "",
                "tried_urls": " | ".join(result.get("tried") or []),
                "source_url": result.get("source_url") or NIKKEI_URL,
            }
            print(result["status"], result.get("reason", "")[:160], flush=True)
        for container_id, code in CSI_CODES.items():
            if container_id not in by_id:
                continue
            print("csi", container_id, code, flush=True)
            result = fetch_one_csi(
                con, container_id, code,
                str(by_id[container_id].get("container_id") or container_id),
                str(by_id[container_id].get("first_list") or ""),
                archive,
            )
            # 名称比对用容器跟踪的指数名。效果表没有指数名时用容器 id 去掉 theme-。
            updates[container_id] = {
                "status": result["status"],
                "index_code": result.get("index_code") or "",
                "publish_date": result.get("publish_date") or "",
                "bars_code": result.get("bars_code") or "",
                "currency": result.get("currency") or "",
                "reason": result.get("reason") or "",
                "tried_urls": " | ".join(result.get("tried") or []),
                "source_url": result.get("source_url") or "",
            }
            print(result["status"], (result.get("reason") or "")[:140], flush=True)
        notes = blocked_notes(archive)
        for row in targets:
            container_id = row["container_id"]
            if container_id in updates:
                continue
            family = _family(container_id)
            note = notes.get(family)
            if note is None:
                updates[container_id] = {
                    "status": "frozen",
                    "reason": "第三轮没有对应的官方日线入口",
                    "tried_urls": "",
                }
                continue
            updates[container_id] = {
                "status": "frozen",
                "reason": note["reason"],
                "tried_urls": " | ".join(note["tried"]),
            }
    finally:
        con.close()
    after = ledger.after("d37-round3")
    update_registry(updates)
    sha = OUT / "db-sha256.txt"
    with sha.open("a", encoding="utf-8") as handle:
        handle.write(f"SHA256 BEFORE d37-round3 {before}\n")
        handle.write(f"SHA256 AFTER  d37-round3 {after}\n")
    log = ROOT / "results" / "inventory" / "db-writes.txt"
    with log.open("a", encoding="utf-8") as handle:
        handle.write(f"SHA256 BEFORE d37-round3 {before}\n")
        handle.write(f"SHA256 AFTER  d37-round3 {after}\n")
    spliced = [key for key, value in updates.items() if value.get("status") == "spliced"]
    print(f"before={before} after={after} spliced={','.join(spliced) or '-'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
