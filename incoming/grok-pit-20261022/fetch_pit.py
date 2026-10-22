#!/usr/bin/env python3
"""拉取指数发布日、ETF 分红/折算/拆分、QDII 候选。只写本目录。

不计算收益、不排名。金额只作事实字段。可重复运行：已落地的 raw 会复用。
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
UNIVERSE = ROOT.parents[1] / "data" / "universe.csv"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
ASOF = "2026-09-30"
CODE_RE = re.compile(
    r"\^(?:XNDX|SP500TR|HSTECH)|[0-9]{6}(?:CNY010)?|H[0-9]{5}|NDXTMC|NDX|SPX|N225|BRENT"
)
GAPS: list[dict] = []


def gap(section: str, item: str, tried: str, result: str, reason: str) -> None:
    GAPS.append(
        {"section": section, "item": item, "tried": tried, "result": result, "reason": reason}
    )


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def http_get(url: str, headers: dict | None = None, timeout: int = 40, data: bytes | None = None) -> tuple[int, bytes, str]:
    h = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        h.update(headers)
    last = "none"
    for i in range(3):
        req = urllib.request.Request(url, data=data, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                return resp.status, body, resp.headers.get("content-type") or ""
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            time.sleep(1.5 * (i + 1))
    return 0, b"", last


def save_bytes(path: Path, body: bytes, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        path.write_bytes(body)
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    meta = dict(meta)
    meta["sha256"] = sha256_bytes(path.read_bytes())
    meta["bytes"] = path.stat().st_size
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def load_or_get(path: Path, url: str, headers: dict | None = None, timeout: int = 40) -> bytes | None:
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()
    status, body, info = http_get(url, headers=headers, timeout=timeout)
    if status != 200 or not body:
        save_bytes(path.with_suffix(path.suffix + ".error.txt"), f"{status} {info}\n{url}\n".encode(), {"url": url, "status": status, "error": info})
        return None
    save_bytes(path, body, {"url": url, "status": status, "content_type": info})
    return body


def compact(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"(?<=\d)\s+(?=[年月日/])", "", text)
    text = re.sub(r"(?<=[年月日])\s+(?=\d)", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text


def cn_date(s: str | None) -> str:
    if not s:
        return ""
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ""


def pdf_text(body: bytes, max_pages: int = 8) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(body))
    except Exception as e:
        return f"PDF_READ_ERROR {e}"
    parts = []
    for page in reader.pages[:max_pages]:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    return compact("\n".join(parts))


def universe_codes() -> tuple[list[str], list[str]]:
    indexes: list[str] = []
    funds: list[str] = []
    with UNIVERSE.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ric = (row.get("research_index_code") or "").strip()
            if ric and ric.lower() != "none":
                indexes.append(ric)
            for cell in (row.get("tr_code_candidates") or "",):
                indexes.extend(CODE_RE.findall(cell))
            for cell_name in ("execution_fund_code", "execution_alternatives"):
                cell = row.get(cell_name) or ""
                for part in cell.replace("；", ";").split(";"):
                    part = part.strip()
                    if re.fullmatch(r"\d{6}", part):
                        funds.append(part)
    # 中证全指自由现金流及其全收益。
    indexes.extend(["932365", "932365CNY010"])
    # 财富版候选只在接口返回身份时保留；这里先纳入探测名单。
    indexes.append("H11077CNY010")

    def uniq(xs: list[str]) -> list[str]:
        out = []
        seen = set()
        for x in xs:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    return uniq(indexes), uniq(funds)


def is_csi_code(code: str) -> bool:
    return bool(re.fullmatch(r"(?:H[0-9]{5}|[0-9]{6})(?:CNY010)?", code))


def fetch_indexes(codes: list[str]) -> list[dict]:
    rows = []
    for code in codes:
        print("index", code, flush=True)
        if code in {"399006", "399606"}:
            rows.append(fetch_cni(code))
            continue
        if code == "518880":
            rows.append(non_index_row(code, "华安黄金ETF（universe research_index_code，不是指数）"))
            gap("index", code, "未向指数公司查询", "该代码是上市基金", "research_index_code 指向基金本身，没有指数基日/发布日")
            continue
        if code == "BRENT":
            rows.append(fetch_brent())
            continue
        if code in {"NDX", "NDXTMC", "SPX", "^XNDX", "^SP500TR", "^HSTECH", "N225"}:
            rows.append(fetch_overseas(code))
            continue
        if is_csi_code(code):
            rows.append(fetch_csi(code))
            continue
        rows.append(non_index_row(code, "无法归入中证/国证/已列海外源代码"))
        gap("index", code, "代码形态未匹配已知指数公司接口", "未查询", "不猜测代码所属机构")
    return rows


def non_index_row(code: str, note: str) -> dict:
    return {
        "index_code": code,
        "index_name": "",
        "base_date": "",
        "launch_date": "",
        "source_url_1": "",
        "source_url_2": "",
        "note": note,
    }


def fetch_csi(code: str) -> dict:
    api = f"https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info/{code}"
    detail = f"https://www.csindex.com.cn/zh-CN/indices/index-detail/{code}"
    body = load_or_get(
        RAW / "csi" / f"{code}.json",
        api,
        headers={"Referer": "https://www.csindex.com.cn/", "Accept": "application/json"},
    )
    time.sleep(0.4)
    if not body:
        gap("index", code, api, "请求失败", "中证详情接口无响应")
        return non_index_row(code, "中证 index-basic-info 请求失败") | {"source_url_1": detail}
    try:
        payload = json.loads(body.decode())
    except json.JSONDecodeError:
        gap("index", code, api, "不是 JSON", "无法解析")
        return non_index_row(code, "中证接口响应不是 JSON")
    data = payload.get("data") or {}
    name = data.get("indexFullNameCn") or ""
    base = (data.get("basicDate") or "")[:10]
    launch = (data.get("publishDate") or "")[:10]
    if not name and not base and not launch:
        gap("index", code, api, "data 字段为空", "中证接口没有该代码的指数身份")
        note = "中证 index-basic-info 返回空 data。universe 若把该代码列为全收益候选，本次未能证实。"
        if code == "H11077CNY010":
            note = "探测代码 H11077CNY010：中证接口返回空 data，不能把它当成已发布的财富/全收益代码。"
        return {
            "index_code": code,
            "index_name": "",
            "base_date": "",
            "launch_date": "",
            "source_url_1": detail,
            "source_url_2": "",
            "note": note,
        }
    pdf_url = (
        "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/"
        f"indices/detail/files/zh_CN/{code}_Index_Methodology_cn.pdf"
    )
    pdf = load_or_get(RAW / "csi_pdf" / f"{code}.pdf", pdf_url, timeout=60)
    time.sleep(0.3)
    pdf_base, pdf_launch, pdf_note = "", "", ""
    if pdf and pdf[:4] == b"%PDF":
        text = pdf_text(pdf, max_pages=6)
        bases = sorted(set(cn_date(m) for m in re.findall(r"(\d{4}年\d{1,2}月\d{1,2}日)为基日", text)))
        bases = [d for d in bases if d]
        launches = sorted(set(
            cn_date(m) for m in re.findall(r"于(\d{4}年\d{1,2}月\d{1,2}日)(?:正式)?发布", text)
        ))
        launches += [cn_date(m) for m in re.findall(r"发布日期为(\d{4}年\d{1,2}月\d{1,2}日)", text)]
        launches = sorted({d for d in launches if d})
        if len(bases) == 1:
            pdf_base = bases[0]
        elif len(bases) > 1:
            pdf_note += f"编制方案出现多个基日：{'、'.join(bases)}。"
        if len(launches) == 1:
            pdf_launch = launches[0]
        elif len(launches) > 1:
            pdf_note += f"编制方案出现多个发布日：{'、'.join(launches)}。"
        if not pdf_base and not pdf_launch and "PDF_READ_ERROR" not in text:
            pdf_note += "编制方案前 6 页未抽出基日或发布日。"
    else:
        pdf_url = ""
        pdf_note = "编制方案 PDF 未下载到。"
        gap("index", code, pdf_url or "methodology pdf", "无 PDF", "第二个来源缺失")

    notes = []
    if data.get("indexShortNameCn"):
        notes.append(f"简称 {data.get('indexShortNameCn')}")
    if pdf_note:
        notes.append(pdf_note)
    # 两边都有值才对照；缺一边不静默补。
    if pdf_base and base and pdf_base != base:
        notes.append(f"基日不一致：详情接口 {base}；编制方案 {pdf_base}")
        gap("index", code, f"{detail} | {pdf_url}", f"{base} vs {pdf_base}", "两个来源基日不一致，CSV 保留详情接口日期，note 并列")
    elif pdf_base and not base:
        notes.append(f"详情接口无基日，编制方案为 {pdf_base}")
    elif base and not pdf_base:
        notes.append("发布日/基日的编制方案交叉核对未抽出基日，基日仅有中证详情接口")
    if pdf_launch and launch and pdf_launch != launch:
        notes.append(f"发布日不一致：详情接口 {launch}；编制方案 {pdf_launch}")
        gap("index", code, f"{detail} | {pdf_url}", f"{launch} vs {pdf_launch}", "两个来源发布日不一致，CSV 保留详情接口日期，note 并列")
    elif launch and not pdf_launch:
        notes.append("发布日仅见于中证详情接口，编制方案前 6 页未载明")
    if code == "H11077CNY010":
        notes.append("该代码来自 universe 单元格中的示例探测，不是已写死的财富代码；上列为中证接口实际返回的身份")
    return {
        "index_code": code,
        "index_name": name,
        "base_date": base,
        "launch_date": launch,
        "source_url_1": detail,
        "source_url_2": pdf_url,
        "note": "；".join(notes),
    }


def fetch_cni(code: str) -> dict:
    h = {"Referer": "http://www.cnindex.com.cn/", "Accept": "application/json"}
    detail = f"http://www.cnindex.com.cn/module/index-detail.html?act_menu=1&indexCode={code}"
    sel = load_or_get(RAW / "cni" / f"{code}_select.json", f"http://www.cnindex.com.cn/index/selectIndexByCode?codeValue={code}", headers=h)
    intro = load_or_get(RAW / "cni" / f"{code}_intro.json", f"http://www.cnindex.com.cn/index-intro?indexcode={code}", headers=h)
    pdf_url = f"http://www.cnindex.com.cn/docs/gz_{code}.pdf"
    pdf = load_or_get(RAW / "cni_pdf" / f"{code}.pdf", pdf_url, timeout=60)
    name, base, launch = "", "", ""
    if intro:
        try:
            data = json.loads(intro.decode()).get("data") or {}
            base = (data.get("jr") or "")[:10]
            launch = (data.get("fbrq") or "")[:10]
        except json.JSONDecodeError:
            gap("index", code, "cni index-intro", "不是 JSON", "无法解析")
    if sel:
        try:
            data = json.loads(sel.decode()).get("data") or {}
            name = data.get("indexfullcname") or data.get("indexname") or ""
            if not base:
                base = (data.get("jr") or "")[:10]
        except json.JSONDecodeError:
            pass
    notes = ["来源均为国证指数网：详情接口与编制方案 PDF"]
    pdf_base = pdf_launch = ""
    if pdf and pdf[:4] == b"%PDF":
        text = pdf_text(pdf, max_pages=6)
        bases = sorted({cn_date(m) for m in re.findall(r"(\d{4}年\d{1,2}月\d{1,2}日)为基日", text) if cn_date(m)})
        launches = sorted({cn_date(m) for m in re.findall(r"(\d{4}年\d{1,2}月\d{1,2}日)(?:正式)?发布", text) if cn_date(m)})
        if len(bases) == 1:
            pdf_base = bases[0]
        if len(launches) == 1:
            pdf_launch = launches[0]
        if pdf_base and base and pdf_base != base:
            notes.append(f"基日不一致：接口 {base}；编制方案 {pdf_base}")
            gap("index", code, f"{detail} | {pdf_url}", f"{base} vs {pdf_base}", "基日不一致")
        elif not pdf_base:
            notes.append("编制方案前 6 页未抽出基日")
        if pdf_launch and launch and pdf_launch != launch:
            notes.append(f"发布日不一致：接口 {launch}；编制方案 {pdf_launch}")
            gap("index", code, f"{detail} | {pdf_url}", f"{launch} vs {pdf_launch}", "发布日不一致")
        elif launch and not pdf_launch:
            notes.append("发布日仅见于国证 index-intro 的 fbrq，编制方案前 6 页未载明")
    else:
        pdf_url = ""
        notes.append("编制方案 PDF 未下载到")
        gap("index", code, f"http://www.cnindex.com.cn/docs/gz_{code}.pdf", "无 PDF", "第二来源缺失")
    if not name and not base:
        gap("index", code, detail, "接口无名称/基日", "国证未返回该指数")
    return {
        "index_code": code,
        "index_name": name,
        "base_date": base,
        "launch_date": launch,
        "source_url_1": detail,
        "source_url_2": pdf_url,
        "note": "；".join(notes),
    }


OVERSEAS = {
    "NDX": [
        "https://indexes.nasdaqomx.com/docs/Methodology_NDX.pdf",
        "https://indexes.nasdaqomx.com/docs/Index_Versions_NDX.pdf",
        "https://indexes.nasdaqomx.com/docs/NDX_Fundamentals.pdf",
    ],
    "NDXTMC": [
        "https://indexes.nasdaqomx.com/docs/Methodology_NDXTMC.pdf",
        "https://indexes.nasdaq.com/docs/Methodology_NDXTMC.pdf",
    ],
    "^XNDX": [
        "https://indexes.nasdaqomx.com/docs/Index_Versions_NDX.pdf",
        "https://indexes.nasdaqomx.com/docs/Methodology_NDX.pdf",
    ],
    "SPX": [
        "https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-us-indices.pdf",
    ],
    "^SP500TR": [
        "https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-us-indices.pdf",
    ],
    "^HSTECH": [
        "https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/factsheets/hsteche.pdf",
        "https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/methodologies/IM_hsteche.pdf",
    ],
    "N225": [
        "https://indexes.nikkei.co.jp/nkave/archives/file/nikkei_stock_average_factsheet_en.pdf",
        "https://indexes.nikkei.co.jp/en/nkave/index/profile?idx=nk225",
    ],
}


def fetch_overseas(code: str) -> dict:
    saved = []
    text_all = []
    for i, url in enumerate(OVERSEAS.get(code, [])):
        ext = ".pdf" if url.lower().endswith(".pdf") else ".html"
        path = RAW / "overseas" / f"{code.strip('^')}_{i}{ext}"
        body = load_or_get(path, url, timeout=60)
        if not body:
            gap("index", code, url, "下载失败", "海外指数官方链接无响应或被拒绝")
            continue
        saved.append(url)
        if body[:4] == b"%PDF":
            text_all.append(pdf_text(body, max_pages=12))
        else:
            # 去掉标签，保留可见文字
            raw = body.decode("utf-8", "replace")
            raw = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw)
            raw = re.sub(r"(?is)<style.*?>.*?</style>", " ", raw)
            raw = re.sub(r"(?s)<[^>]+>", " ", raw)
            text_all.append(compact(raw)[:20000])
    blob = "\n".join(text_all)
    if not blob.strip():
        return {
            "index_code": code,
            "index_name": "",
            "base_date": "",
            "launch_date": "",
            "source_url_1": OVERSEAS.get(code, [""])[0] if OVERSEAS.get(code) else "",
            "source_url_2": "",
            "note": "官方页面/PDF 均未取到，基日和发布日留空",
        }
    base, launch, name, note = overseas_dates(code, blob)
    if not base:
        gap("index", code, " | ".join(saved) or "overseas urls", "未抽出 base date", "原文没有可机械识别的基日")
    if not launch:
        gap("index", code, " | ".join(saved) or "overseas urls", "未抽出 launch date", "原文没有可机械识别的发布日")
    return {
        "index_code": code,
        "index_name": name,
        "base_date": base,
        "launch_date": launch,
        "source_url_1": saved[0] if saved else "",
        "source_url_2": saved[1] if len(saved) > 1 else "",
        "note": note,
    }


def eng_date(chunk: str) -> str:
    chunk = re.sub(r"(\d+)(?:st|nd|rd|th)\b", r"\1", chunk, flags=re.I)
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
        "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    m = re.search(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})", chunk)
    if m and m.group(1).lower() in months:
        return f"{int(m.group(3)):04d}-{months[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})", chunk)
    if m and m.group(2).lower() in months:
        return f"{int(m.group(3)):04d}-{months[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", chunk)
    if m:
        return f"{int(m.group(3)):04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return ""


def overseas_dates(code: str, blob: str) -> tuple[str, str, str, str]:
    """只从已下载原文抽日期。抽不到就留空。"""
    flat = re.sub(r"\s+", " ", blob)
    name = ""
    m = re.search(r"(Nasdaq-100 Technology Sector[^\n]{0,40}|Nasdaq-100 Index|Hang Seng TECH Index|Nikkei Stock Average|S&P 500)", blob)
    if m:
        name = compact(m.group(1))[:80]
    base = launch = ""
    note = ""
    if code == "N225":
        m1 = re.search(r"commencement date of the calculation was ([A-Za-z0-9, ]{6,40})", flat, re.I)
        m2 = re.search(r"to (May 16(?:th)?, 1949)", flat, re.I)
        launch = eng_date(m1.group(1)) if m1 else ""
        base = eng_date(m2.group(1)) if m2 else ""
        note = "日经事实表小标题是 (Base date etc)。launch_date 取 commencement date of the calculation，base_date 取回溯到的 May 16, 1949。"
        if m1:
            note += " 原文：" + m1.group(0)[:160]
        if m2:
            note += "；" + m2.group(0)
        return base, launch, name or "Nikkei Stock Average", note
    if code in {"NDX", "^XNDX"}:
        if re.search(r"Launched on January 31, 1985", flat, re.I):
            launch = "1985-01-31"
        m = re.search(r"Total Return XNDX .{0,160}?(\d{1,2}/\d{1,2}/\d{4})", flat, re.I)
        tr = eng_date(m.group(1)) if m else ""
        m = re.search(r"Nasdaq-100 NDX .{0,160}?(\d{1,2}/\d{1,2}/\d{4})", flat, re.I)
        px = eng_date(m.group(1)) if m else ""
        if code == "NDX":
            base = px
            note = "base_date 是 Index Versions 表 Nasdaq-100 / NDX / PRICE RETURN 的 Base Value Date。launch_date 来自 NDX Fundamentals 的 “Launched on January 31, 1985”。两份文件若不一致，以各列对应的那一句为准。"
        else:
            base = tr
            launch = ""
            note = "XNDX 的 base_date 是 Index Versions 表 Nasdaq-100 Total Return / XNDX 的 Base Value Date。该行没有单独的 Launch Date，launch_date 留空。"
        return base, launch, name or "Nasdaq-100", note
    if code == "^HSTECH":
        m = re.search(r"Launch Date\s+([0-9]{1,2}\s+[A-Za-z]+\.?\s+[0-9]{4})", blob, re.I)
        if m:
            launch = eng_date(m.group(1))
        m = re.search(r"Base Date\s+([0-9]{1,2}\s+[A-Za-z]+\.?\s+[0-9]{4})", blob, re.I)
        if m:
            base = eng_date(m.group(1))
        note = "恒生科技指数的 Launch Date / Base Date 来自恒生指数公司事实表或编制方法。"
        return base, launch, name or "Hang Seng TECH Index", note
    if code == "NDXTMC":
        m = re.search(r"Launch Date\s+([A-Za-z0-9, /-]+)", blob, re.I)
        if m:
            launch = eng_date(m.group(1))
        m = re.search(r"Base Date\s+([A-Za-z0-9, /-]+)", blob, re.I)
        if m:
            base = eng_date(m.group(1))
        note = "纳斯达克科技市值加权指数只采用其方法论 PDF 里标明的 Launch Date / Base Date。"
        return base, launch, name or "Nasdaq-100 Technology Sector Market-Cap Weighted Index", note
    note = "标普页面本次若被拒绝，日期留空，不用其他网站的转述补数。"
    m = re.search(r"Launch Date[:\s]+([A-Za-z0-9, /-]+)", blob, re.I)
    if m:
        launch = eng_date(m.group(1))
    m = re.search(r"Base Date[:\s]+([A-Za-z0-9, /-]+)", blob, re.I)
    if m and m.group(1).strip().lower() not in {"etc", "the"}:
        base = eng_date(m.group(1))
    return base, launch, name, note


def fetch_brent() -> dict:
    url = "https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=RBRTE&f=D"
    body = load_or_get(RAW / "overseas" / "BRENT_eia.html", url, timeout=60)
    note = "universe 研究代码是 EIA 现货序列 RBRTE 与期货代码 BZ=F，不是指数，故 base_date/launch_date 留空。"
    if not body:
        gap("index", "BRENT", url, "下载失败", "EIA 页面未取到")
        return {
            "index_code": "BRENT",
            "index_name": "Europe Brent Spot Price FOB (EIA RBRTE)",
            "base_date": "",
            "launch_date": "",
            "source_url_1": url,
            "source_url_2": "",
            "note": note + " EIA 页面本次未下载到。",
        }
    text = re.sub(r"(?s)<[^>]+>", " ", body.decode("utf-8", "replace"))
    text = compact(text)
    # 只记录页面标题级事实，不把序列第一天当成发布日。
    m = re.search(r"Europe Brent Spot Price FOB[^.]{0,80}", text)
    name = m.group(0).strip() if m else "Europe Brent Spot Price FOB"
    return {
        "index_code": "BRENT",
        "index_name": name[:80],
        "base_date": "",
        "launch_date": "",
        "source_url_1": url,
        "source_url_2": "https://www.eia.gov/dnav/pet/hist/rbrteD.htm",
        "note": note,
    }


def is_sz(code: str) -> bool:
    return code.startswith(("15", "16"))


def load_cninfo_orgs() -> dict[str, str]:
    url = "https://www.cninfo.com.cn/new/data/fund_stock.json"
    body = load_or_get(RAW / "cninfo" / "fund_stock.json", url, headers={"Referer": "https://www.cninfo.com.cn/"})
    orgs = {}
    if not body:
        gap("etf", "cninfo fund_stock.json", url, "下载失败", "深市基金 orgId 表缺失")
        return orgs
    try:
        data = json.loads(body.decode())
    except json.JSONDecodeError:
        return orgs
    for item in data.get("stockList") or []:
        if item.get("category") in {"ETF", "LOF", "开放式基金"} and re.fullmatch(r"\d{6}", item.get("code") or ""):
            orgs[item["code"]] = item.get("orgId") or ""
    return orgs


def sse_bulletins(code: str) -> list[dict]:
    path = RAW / "sse" / f"{code}_bulletins.json"
    if path.exists() and path.stat().st_size > 0:
        return json.loads(path.read_text(encoding="utf-8"))
    headers = {"Referer": "https://www.sse.com.cn/disclosure/fund/announcement/", "Accept": "application/json"}
    all_rows = []
    total = None
    for page in range(1, 30):
        url = (
            "https://query.sse.com.cn/commonSoaQuery.do?isPagination=true&sqlId=BS_GGLL"
            f"&pageHelp.pageSize=100&pageHelp.pageNo={page}&pageHelp.beginPage={page}"
            f"&pageHelp.cacheSize=1&pageHelp.endPage={page}&siteId=28&channelId=8361&stockcode={code}"
        )
        status, body, info = http_get(url, headers=headers, timeout=40)
        if status != 200 or not body:
            gap("etf", code, url, f"{status} {info}", "上交所基金公告接口失败")
            break
        try:
            payload = json.loads(body.decode())
        except json.JSONDecodeError:
            gap("etf", code, url, "不是 JSON", "上交所公告接口异常")
            break
        ph = payload.get("pageHelp") or {}
        total = ph.get("total")
        chunk = ph.get("data") or []
        all_rows.extend(chunk)
        if not chunk or len(all_rows) >= int(total or 0) or len(chunk) < 100:
            break
        time.sleep(0.25)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(all_rows, ensure_ascii=False), encoding="utf-8")
    (path.with_suffix(".meta.json")).write_text(
        json.dumps({"url": "https://query.sse.com.cn/commonSoaQuery.do", "sqlId": "BS_GGLL", "channelId": "8361", "stockcode": code, "total": total, "saved": len(all_rows)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return all_rows


def cninfo_query(code: str, org: str, key: str) -> list[dict]:
    safe = re.sub(r"\W+", "_", key)[:40]
    path = RAW / "cninfo" / f"{code}_{safe}.json"
    if path.exists() and path.stat().st_size > 0:
        return json.loads(path.read_text(encoding="utf-8"))
    headers = {
        "Referer": "https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
        "Origin": "https://www.cninfo.com.cn",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json",
    }
    found = []
    for page in range(1, 8):
        form = {
            "pageNum": str(page),
            "pageSize": "30",
            "column": "fund",
            "tabName": "fulltext",
            "plate": "",
            "stock": f"{code},{org}" if org else "",
            "searchkey": key,
            "secid": "",
            "category": "",
            "trade": "",
            "seDate": "2000-01-01~2026-10-23",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        status, body, info = http_get(
            "https://www.cninfo.com.cn/new/hisAnnouncement/query",
            headers=headers,
            data=urllib.parse.urlencode(form).encode(),
        )
        if status != 200 or not body:
            gap("etf", f"{code} {key}", "cninfo hisAnnouncement", f"{status} {info}", "巨潮查询失败")
            break
        try:
            payload = json.loads(body.decode())
        except json.JSONDecodeError:
            break
        anns = payload.get("announcements") or []
        for a in anns:
            if a.get("secCode") == code:
                found.append(a)
        total = int(payload.get("totalAnnouncement") or 0)
        if page * 30 >= total or not anns:
            break
        time.sleep(0.2)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(found, ensure_ascii=False), encoding="utf-8")
    return found


def abs_sse(url: str) -> str:
    if not url:
        return ""
    if url.startswith("http"):
        return url
    return "https://" + url.lstrip("/")


def money(s: str) -> str:
    try:
        return format(Decimal(s).normalize(), "f")
    except InvalidOperation:
        return ""


def parse_div_text(text: str) -> dict:
    out = {"record_date": "", "ex_date": "", "cash_per_unit": "", "split_ratio": "", "event_type": ""}
    m = re.search(r"权益登记日[:：]?\s*(\d{4}年\d{1,2}月\d{1,2}日)", text)
    if m:
        out["record_date"] = cn_date(m.group(1))
    m = re.search(r"除息日[:：]?\s*(\d{4}年\d{1,2}月\d{1,2}日)", text)
    if m:
        out["ex_date"] = cn_date(m.group(1))
    if not out["ex_date"]:
        m = re.search(r"除权日[:：]?\s*(\d{4}年\d{1,2}月\d{1,2}日)", text)
        if m:
            out["ex_date"] = cn_date(m.group(1))
    per10 = ""
    m = re.search(r"元\s*/\s*10\s*份基金份额[）)]\s*([0-9]+(?:\.[0-9]+)?)", text)
    if m:
        per10 = m.group(1)
    if not per10:
        m = re.search(r"每\s*10\s*份(?:基金份额)?[^0-9]{0,24}([0-9]+\.[0-9]+)\s*元", text)
        if m:
            per10 = m.group(1)
    if per10:
        per = money(str(Decimal(per10) / Decimal(10)))
        if per:
            out["cash_per_unit"] = per
            out["event_type"] = "现金分红"
    if not out["cash_per_unit"]:
        m = re.search(r"每份基金份额派发(?:现金红利)?(?:人民币)?\s*([0-9]+(?:\.[0-9]+)?)\s*元", text)
        if m:
            out["cash_per_unit"] = money(m.group(1))
            out["event_type"] = "现金分红"
    if "份额折算" in text or "拆分" in text:
        ratio = ""
        m2 = re.search(r"1\s*[:：]\s*([0-9]+(?:\.[0-9]+)?)", text)
        if m2 and "折算" in text:
            ratio = "1:" + m2.group(1)
        if not ratio:
            m = re.search(r"折算比例(?:为|[:：])?\s*([0-9]+\.[0-9]+)", text)
            if m:
                ratio = m.group(1)
        if "份额折算" in text:
            out["event_type"] = "份额折算"
        elif "拆分" in text and not out["event_type"]:
            out["event_type"] = "拆分"
        if ratio:
            out["split_ratio"] = ratio
    return out


def em_events(code: str) -> list[dict]:
    url = f"https://fundf10.eastmoney.com/fhsp_{code}.html"
    body = load_or_get(RAW / "em_fhsp" / f"{code}.html", url, headers={"Referer": "https://fundf10.eastmoney.com/"})
    if not body:
        gap("etf", code, url, "下载失败", "天天基金分红页缺失，无法交叉核对")
        return []
    html = body.decode("utf-8", "replace")
    events = []

    def rows_of(label: str) -> str:
        m = re.search(label + r".*?<tbody>(.*?)</tbody>", html, re.S)
        return m.group(1) if m else ""

    for row in re.findall(r"<tr>(.*?)</tr>", rows_of("分红送配详情"), re.S):
        cells = [re.sub("<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) < 5 or "暂无" in "".join(cells):
            continue
        cash = ""
        cell = cells[3].replace(" ", "")
        m = re.search(r"派(?:现金)?(?:红利)?([0-9]+(?:\.[0-9]+)?)", cell)
        if not m:
            m = re.search(r"([0-9]+\.[0-9]+)", cell)
        if m:
            try:
                val = Decimal(m.group(1))
                if "10份" in cell:
                    val = val / Decimal(10)
                cash = format(val.normalize(), "f")
            except InvalidOperation:
                cash = ""
        events.append({
            "event_type": "现金分红",
            "record_date": cells[1] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[1]) else "",
            "ex_date": cells[2] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[2]) else "",
            "cash_per_unit": cash,
            "split_ratio": "",
            "cross_check_url": url,
            "source": "eastmoney",
        })
    for row in re.findall(r"<tr>(.*?)</tr>", rows_of("拆分详情"), re.S):
        cells = [re.sub("<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) < 4 or "暂无" in "".join(cells):
            continue
        kind = cells[2]
        if "折算" in kind:
            et = "份额折算"
        elif "拆分" in kind:
            et = "拆分"
        else:
            et = ""
            gap("etf", code, url, f"未知拆分类型 {kind}", "不映射到规定的三类")
        if not et:
            continue
        events.append({
            "event_type": et,
            "record_date": "",
            "ex_date": cells[1] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[1]) else "",
            "cash_per_unit": "",
            "split_ratio": cells[3],
            "cross_check_url": url,
            "source": "eastmoney",
            "date_note": "天天基金列名是拆分折算日，写入 ex_date；权益登记日页面未单列",
        })
    return events


def official_events(code: str, orgs: dict[str, str]) -> tuple[list[dict], list[dict]]:
    """返回 (事件公告, 全部公告标题用于上市日/额度说明)。"""
    docs = []
    if is_sz(code):
        org = orgs.get(code, "")
        if not org:
            gap("etf", code, "cninfo fund_stock.json", "无 orgId", "深市基金未出现在巨潮基金列表，改试上交所接口")
            bulletins = sse_bulletins(code)
        else:
            bulletins = []
            seen = set()
            for key in ("分红", "收益分配", "折算", "拆分", "产品资料概要"):
                for a in cninfo_query(code, org, key):
                    aid = a.get("announcementId")
                    if aid in seen:
                        continue
                    seen.add(aid)
                    title = re.sub(r"</?em>", "", a.get("announcementTitle") or "")
                    url = "https://static.cninfo.com.cn/" + (a.get("adjunctUrl") or "").lstrip("/")
                    docs.append({"title": title, "url": url, "id": str(aid), "date": ""})
            return finish_docs(code, docs), docs
    else:
        bulletins = sse_bulletins(code)
    for b in bulletins:
        title = b.get("docTitle") or ""
        url = abs_sse(b.get("docURL") or "")
        docs.append({
            "title": title,
            "url": url,
            "id": (b.get("docId") or title)[:80],
            "date": (b.get("createTime") or "")[:10],
            "gglx": b.get("extGGLX") or "",
        })
    interesting = []
    for d in docs:
        title = d["title"]
        if any(k in title for k in ("分红", "收益分配", "份额折算", "拆分")) and "风险提示" not in title and "多码合一" not in title and "上市首日" not in title:
            interesting.append(d)
    return finish_docs(code, interesting), docs


def finish_docs(code: str, docs: list[dict]) -> list[dict]:
    events = []
    for d in docs:
        if not any(k in d["title"] for k in ("分红", "收益分配", "份额折算", "拆分")):
            continue
        if any(k in d["title"] for k in ("风险提示", "多码合一", "上市首日")):
            continue
        ext = "pdf"
        path = RAW / "event_pdf" / f"{code}_{re.sub(r'[^0-9A-Za-z]+', '_', d['id'])[:60]}.{ext}"
        body = load_or_get(path, d["url"], headers={"Referer": "https://www.sse.com.cn/"}, timeout=60)
        parsed = {"record_date": "", "ex_date": "", "cash_per_unit": "", "split_ratio": "", "event_type": ""}
        if body and body[:4] == b"%PDF":
            parsed = parse_div_text(pdf_text(body, max_pages=4))
        else:
            gap("etf", f"{code} {d['title'][:40]}", d["url"], "PDF 未取到", "有标题无正文")
        if not parsed["event_type"]:
            if "折算" in d["title"]:
                parsed["event_type"] = "份额折算"
            elif "拆分" in d["title"]:
                parsed["event_type"] = "拆分"
            elif "分红" in d["title"] or "收益分配" in d["title"]:
                parsed["event_type"] = "现金分红"
        if not any(parsed.get(k) for k in ("record_date", "ex_date", "cash_per_unit", "split_ratio")):
            gap("etf", f"{code} {d['title'][:40]}", d["url"], "标题命中但未抽出日期、金额或比例", "不写入 etf_events，避免把无关公告当成事件")
            continue
        events.append({
            "event_type": parsed["event_type"],
            "record_date": parsed["record_date"],
            "ex_date": parsed["ex_date"],
            "cash_per_unit": parsed["cash_per_unit"],
            "split_ratio": parsed["split_ratio"],
            "source_url": d["url"],
            "title": d["title"],
            "source": "official",
        })
        time.sleep(0.15)
    return events


def find_listing_in_text(text: str) -> str:
    m = re.search(r"上市日期.{0,40}?(\d{4}年\d{1,2}月\d{1,2}日)", text)
    if m:
        return cn_date(m.group(1))
    m = re.search(r"上市日期.{0,40}?(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    return ""


def listing_date_from_docs(code: str, docs: list[dict]) -> str:
    legacy = RAW / "overview" / f"{code}.pdf"
    if legacy.exists() and legacy.stat().st_size > 1000:
        found = find_listing_in_text(pdf_text(legacy.read_bytes(), max_pages=8))
        if found:
            return found
    ranked = sorted(docs, key=lambda d: d.get("date") or "", reverse=True)
    tried = 0
    for d in ranked:
        if "产品资料概要" not in d["title"]:
            continue
        tried += 1
        if tried > 3:
            break
        path = RAW / "overview" / f"{code}_{tried}.pdf"
        body = load_or_get(path, d["url"], headers={"Referer": "https://www.sse.com.cn/"}, timeout=60)
        if not body or body[:4] != b"%PDF":
            continue
        found = find_listing_in_text(pdf_text(body, max_pages=8))
        if found:
            return found
    if tried:
        gap("etf", code, "最多 3 份产品资料概要", "未抽出上市日期", "不把合同生效日当作上市日")
    return ""


def same_event(a: dict, b: dict) -> bool:
    if a.get("event_type") != b.get("event_type"):
        return False
    da = {a.get("record_date"), a.get("ex_date")} - {None, ""}
    db = {b.get("record_date"), b.get("ex_date")} - {None, ""}
    return bool(da & db)


def merge_events(code: str, official: list[dict], crosses: list[dict], listing: str) -> list[dict]:
    used = set()
    merged = []
    # 同一官方事件多份公告（实施/结果）先折叠。
    folded = []
    for ev in official:
        hit = None
        for i, keep in enumerate(folded):
            if same_event(ev, keep):
                hit = i
                break
        if hit is None:
            folded.append(ev)
        else:
            cur = folded[hit]
            # 结果公告或已抽出数字的优先。
            def score(e: dict) -> tuple:
                return (
                    1 if e.get("cash_per_unit") or e.get("split_ratio") else 0,
                    1 if "结果" in (e.get("title") or "") else 0,
                )
            if score(ev) > score(cur):
                folded[hit] = ev
    for ev in folded:
        match = None
        for i, c in enumerate(crosses):
            if i in used:
                continue
            if same_event(ev, c):
                match = i
                break
        row = {
            "code": code,
            "listing_date": listing,
            "event_type": ev.get("event_type") or "",
            "record_date": ev.get("record_date") or "",
            "ex_date": ev.get("ex_date") or "",
            "cash_per_unit": ev.get("cash_per_unit") or "",
            "split_ratio": ev.get("split_ratio") or "",
            "source_url": ev.get("source_url") or "",
            "cross_check_url": "",
        }
        if match is not None:
            used.add(match)
            c = crosses[match]
            row["cross_check_url"] = c.get("cross_check_url") or ""
            if not row["record_date"]:
                row["record_date"] = c.get("record_date") or ""
            if not row["ex_date"]:
                row["ex_date"] = c.get("ex_date") or ""
            if not row["cash_per_unit"]:
                row["cash_per_unit"] = c.get("cash_per_unit") or ""
                if c.get("cash_per_unit"):
                    gap("etf", f"{code} {row['event_type']} {row['record_date'] or row['ex_date']}", row["source_url"], "金额取自天天基金", "公告原文未抽出每份金额")
            elif c.get("cash_per_unit") and Decimal(row["cash_per_unit"]) != Decimal(c["cash_per_unit"]):
                gap(
                    "etf",
                    f"{code} {row['event_type']} {row['record_date']}",
                    f"{row['source_url']} | {row['cross_check_url']}",
                    f"公告 {row['cash_per_unit']}；天天基金 {c['cash_per_unit']}",
                    "每份金额不一致，CSV 保留公告抽出的数值",
                )
            if not row["split_ratio"]:
                row["split_ratio"] = c.get("split_ratio") or ""
            elif c.get("split_ratio") and row["split_ratio"] != c["split_ratio"]:
                gap(
                    "etf",
                    f"{code} {row['event_type']} {row['ex_date']}",
                    f"{row['source_url']} | {row['cross_check_url']}",
                    f"公告 {row['split_ratio']}；天天基金 {c['split_ratio']}",
                    "折算/拆分比例不一致，CSV 保留公告抽出的写法",
                )
        else:
            gap("etf", f"{code} {row['event_type']} {row['record_date'] or row['ex_date']}", row["source_url"], "天天基金分红页无对应日期", "交叉核对未命中")
        merged.append(row)
    for i, c in enumerate(crosses):
        if i in used:
            continue
        gap("etf", f"{code} {c['event_type']} {c.get('record_date') or c.get('ex_date')}", c.get("cross_check_url") or "", "只有天天基金，没有对上交易所/巨潮标题", "source_url 留空")
        merged.append({
            "code": code,
            "listing_date": listing,
            "event_type": c.get("event_type") or "",
            "record_date": c.get("record_date") or "",
            "ex_date": c.get("ex_date") or "",
            "cash_per_unit": c.get("cash_per_unit") or "",
            "split_ratio": c.get("split_ratio") or "",
            "source_url": "",
            "cross_check_url": c.get("cross_check_url") or "",
        })
    return merged


def fetch_events(funds: list[str]) -> list[dict]:
    orgs = load_cninfo_orgs()
    rows = []
    for code in funds:
        print("fund", code, flush=True)
        try:
            official, docs = official_events(code, orgs)
            listing = listing_date_from_docs(code, docs)
            if not listing:
                gap("etf", code, "产品资料概要 / 公告标题", "未抽出上市日期", "不使用成立日代替上市日")
            crosses = em_events(code)
            part = merge_events(code, official, crosses, listing)
            if not part:
                # 仍写一行占位？不写。在 gap 里记「核查后无事件」不算缺口。
                print("  no events", flush=True)
            rows.extend(part)
            # 把公告目录留给 QDII 额度说明复用
            (RAW / "bulletin_index").mkdir(parents=True, exist_ok=True)
            (RAW / "bulletin_index" / f"{code}.json").write_text(json.dumps(docs, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            gap("etf", code, "fetch_events", f"{type(e).__name__}: {e}", "单只基金处理失败，未写入事件")
            print("  ERR", code, e, flush=True)
    return rows


def exchange_names() -> list[tuple[str, str]]:
    sse_url = "https://www.sse.com.cn/js/common/ssesuggestfunddata.js"
    body = load_or_get(RAW / "sse" / "ssesuggestfunddata.js", sse_url, headers={"Referer": "https://www.sse.com.cn/"})
    names = []
    if body:
        text = body.decode("utf-8", "replace")
        names.extend(re.findall(r'val:"(\d{6})",val2:"([^"]+)"', text))
    else:
        gap("qdii", "sse fund list", sse_url, "下载失败", "上交所基金简称表缺失")
    org_body = load_or_get(
        RAW / "cninfo" / "fund_stock.json",
        "https://www.cninfo.com.cn/new/data/fund_stock.json",
        headers={"Referer": "https://www.cninfo.com.cn/"},
    )
    if org_body:
        try:
            data = json.loads(org_body.decode())
            for item in data.get("stockList") or []:
                if item.get("category") in {"ETF", "LOF"} and re.fullmatch(r"\d{6}", item.get("code") or ""):
                    names.append((item["code"], item.get("zwjc") or ""))
        except json.JSONDecodeError:
            pass
    # 去重，保留先出现的简称
    seen = set()
    out = []
    for code, name in names:
        if code in seen:
            continue
        seen.add(code)
        out.append((code, name))
    return out


def jbgk(code: str) -> dict:
    url = f"https://fundf10.eastmoney.com/jbgk_{code}.html"
    body = load_or_get(RAW / "jbgk" / f"{code}.html", url, headers={"Referer": "https://fundf10.eastmoney.com/"})
    if not body:
        return {}
    html = body.decode("utf-8", "replace")

    def grab(label: str) -> str:
        m = re.search(label + r"</th>\s*<td[^>]*>(.*?)</td>", html, re.S)
        if not m:
            return ""
        return compact(re.sub("<[^>]+>", "", m.group(1))).strip()

    return {
        "name": grab("基金简称"),
        "type": grab("基金类型"),
        "track": grab("跟踪标的"),
        "bench": grab("业绩比较基准"),
        "qdii": ("QDII" in html) or ("海外" in grab("基金类型")),
        "url": url,
    }


def classify_qdii(name: str, info: dict) -> str:
    if not info or not info.get("qdii"):
        return ""
    track = info.get("track") or ""
    bench = info.get("bench") or ""
    text = f"{name}|{track}|{bench}"
    if "海外科技" in name:
        return bench or name
    if "港股通" in track and "恒生科技指数" not in track:
        return ""
    if any(k in text for k in ("纳斯达克科技", "纳指科技", "科技市值加权")):
        return "纳斯达克科技市值加权指数" if "科技市值加权" in text else track or name
    if "生物" not in text and "科技" not in track:
        if any(k in track for k in ("纳斯达克100", "纳指100", "Nasdaq-100", "Nasdaq 100")):
            return track
        if any(k in name for k in ("纳指100", "纳斯达克100", "纳指ETF", "纳斯达克ETF")) and any(
            k in (track + bench) for k in ("纳斯达克100", "纳指100", "纳斯达克指数", "Nasdaq")
        ):
            return track or "纳斯达克100"
    if "标普500信息科技" in text or "标普信息科技" in text:
        return track or "标普500信息科技指数"
    if ("标普500" in text or "标普 500" in text) and not any(k in text for k in ("信息科技", "生物", "油气", "消费", "医疗", "红利")):
        return track or "标普500"
    if "道琼斯工业" in text or "道琼斯" in name:
        return track or "道琼斯工业平均指数"
    if "日经" in text:
        return track or "日经225"
    if "恒生科技指数" in text or ("恒生科技" in name and "港股通" not in name):
        if "恒生科技" in (track or name):
            return track or "恒生科技指数"
    if any(k in text for k in ("费城半导体", "全球芯片", "全球半导体", "中韩半导体")):
        return track if track and "无跟踪" not in track else bench
    if "海外科技" in name or "海外科技" in text:
        return bench or track or name
    return ""


def sohu_amount(code: str) -> str:
    url = f"https://q.stock.sohu.com/hisHq?code=cn_{code}&start=20260301&end=20260930&stat=1&order=D&period=d"
    body = load_or_get(RAW / "sohu" / f"{code}.json", url, headers={"Referer": "https://q.stock.sohu.com/"})
    if not body:
        gap("qdii", code, url, "下载失败", "60 日成交额留空")
        return ""
    try:
        payload = json.loads(body.decode("gbk", "replace"))
        hq = payload[0].get("hq") or []
    except Exception as e:
        gap("qdii", code, url, f"解析失败 {e}", "成交额留空")
        return ""
    days = [r for r in hq if isinstance(r, list) and len(r) > 8 and r[0] <= ASOF]
    days.sort(key=lambda r: r[0])
    if len(days) < 60:
        gap("qdii", code, url, f"截至 {ASOF} 只有 {len(days)} 个交易日", "不足 60 个交易日，不计算平均成交额")
        return ""
    window = days[-60:]
    try:
        # 搜狐 hq[8] 与「成交量(手)×价格」同量级，等于万元。CSV 记人民币元。
        vals = [Decimal(str(r[8])) * Decimal(10000) for r in window]
    except InvalidOperation:
        gap("qdii", code, url, "成交额字段不是数字", "留空")
        return ""
    avg = sum(vals) / Decimal(60)
    return format(avg.quantize(Decimal("0.01")), "f")


def jisilu_snapshot() -> dict[str, dict]:
    headers = {"Referer": "https://www.jisilu.cn/data/qdii/", "X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}
    found = {}
    for cat in ("E", "A", "C"):
        url = f"https://www.jisilu.cn/data/qdii/qdii_list/{cat}?___jsl=LST___t=1&rp=25&page=1"
        body = load_or_get(RAW / "jisilu" / f"{cat}.json", url, headers=headers)
        if not body:
            gap("qdii", f"jisilu {cat}", url, "下载失败", "溢价页缺失")
            continue
        try:
            payload = json.loads(body.decode())
        except json.JSONDecodeError:
            continue
        for row in payload.get("rows") or []:
            cell = row.get("cell") or {}
            fid = str(cell.get("fund_id") or "")
            if fid:
                found[fid] = cell
        # 记录接口没有翻页
        gap(
            "qdii",
            f"jisilu {cat}",
            url,
            f"rows={len(payload.get('rows') or [])} total_field={payload.get('total')} all_field={payload.get('all')}",
            "匿名接口 page=2 仍返回同一页，未取得全表，也没有日频溢价历史接口",
        )
    return found


def quota_note(code: str, cell: dict | None) -> str:
    bits = []
    path = RAW / "bulletin_index" / f"{code}.json"
    docs = []
    if path.exists():
        docs = json.loads(path.read_text(encoding="utf-8"))
    else:
        # QDII 候选可能不在执行基金列表里，补抓标题。
        if is_sz(code):
            orgs = load_cninfo_orgs()
            org = orgs.get(code, "")
            if org:
                anns = []
                for key in ("暂停申购", "溢价", "限额"):
                    anns.extend(cninfo_query(code, org, key))
                docs = [{
                    "title": re.sub(r"</?em>", "", a.get("announcementTitle") or ""),
                    "url": "https://static.cninfo.com.cn/" + (a.get("adjunctUrl") or "").lstrip("/"),
                    "date": "",
                } for a in anns]
        else:
            bulls = sse_bulletins(code)
            docs = [{"title": b.get("docTitle") or "", "url": abs_sse(b.get("docURL") or ""), "date": (b.get("createTime") or "")[:10]} for b in bulls]
        (RAW / "bulletin_index").mkdir(parents=True, exist_ok=True)
        (RAW / "bulletin_index" / f"{code}.json").write_text(json.dumps(docs, ensure_ascii=False), encoding="utf-8")
    def latest(pred):
        hits = [d for d in docs if pred(d.get("title") or "")]
        hits.sort(key=lambda d: d.get("date") or "", reverse=True)
        return hits[0] if hits else None
    sus = latest(lambda t: "暂停申购" in t or "限制申购" in t or "限额申购" in t)
    res = latest(lambda t: "恢复申购" in t)
    prem = latest(lambda t: "溢价" in t)
    if sus:
        bits.append(f"暂停/限额申购公告 {sus.get('date','')} {sus['title']} {sus['url']}")
    if res:
        bits.append(f"恢复申购公告 {res.get('date','')} {res['title']} {res['url']}")
    if prem:
        bits.append(f"最近溢价提示 {prem.get('date','')} {prem['title']} {prem['url']}")
    if cell:
        bits.append(
            "集思录快照 "
            f"price_dt={cell.get('price_dt')} apply_status={cell.get('apply_status')} "
            f"redeem_status={cell.get('redeem_status')} nav_discount_rt={cell.get('nav_discount_rt')} "
            f"notes={cell.get('notes') or ''}"
        )
    else:
        bits.append("集思录本次返回的每类前 20 条中没有该代码，未记当日折溢价")
    return "；".join(bits)[:900]


def fetch_qdii() -> list[dict]:
    pre = []
    for code, name in exchange_names():
        if any(k in name for k in ("纳指", "纳斯达克", "标普500", "标普信息", "道琼", "日经", "恒生科技", "全球芯片", "海外科技", "中韩半导体", "信息科技", "海外")):
            pre.append((code, name))
    print("qdii prefilter", len(pre), flush=True)
    snap = jisilu_snapshot()
    rows = []
    for code, name in pre:
        print("qdii", code, name, flush=True)
        info = jbgk(code)
        tracking = classify_qdii(name, info)
        if not tracking:
            continue
        listing = ""
        idx_path = RAW / "bulletin_index" / f"{code}.json"
        docs = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else []
        if not docs:
            if is_sz(code):
                orgs = load_cninfo_orgs()
                org = orgs.get(code, "")
                anns = cninfo_query(code, org, "产品资料概要") if org else []
                docs = [{
                    "title": re.sub(r"</?em>", "", a.get("announcementTitle") or ""),
                    "url": "https://static.cninfo.com.cn/" + (a.get("adjunctUrl") or "").lstrip("/"),
                    "date": "",
                    "id": str(a.get("announcementId")),
                } for a in anns]
            else:
                bulls = sse_bulletins(code)
                docs = [{"title": b.get("docTitle") or "", "url": abs_sse(b.get("docURL") or ""), "date": (b.get("createTime") or "")[:10], "id": b.get("docId") or ""} for b in bulls]
            (RAW / "bulletin_index").mkdir(parents=True, exist_ok=True)
            (RAW / "bulletin_index" / f"{code}.json").write_text(json.dumps(docs, ensure_ascii=False), encoding="utf-8")
        listing = listing_date_from_docs(code, docs)
        if not listing:
            gap("qdii", code, "产品资料概要", "未抽出上市日期", "留空")
        amount = sohu_amount(code)
        cell = snap.get(code)
        rows.append({
            "code": code,
            "name": (info.get("name") or name),
            "tracking_index": tracking,
            "listing_date": listing,
            "avg_amount_60d": amount,
            "premium_source": "集思录 QDII 页 https://www.jisilu.cn/data/qdii/ （匿名列表接口未提供日频历史；基金公司 IOPV 为盘中估值，不是日频溢价历史）",
            "premium_history_available": "否",
            "quota_or_suspension_notes": quota_note(code, cell),
        })
    # 去重
    uniq = {}
    for r in rows:
        uniq[r["code"]] = r
    return [uniq[k] for k in sorted(uniq)]


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def write_unavailable() -> None:
    lines = [
        "# UNAVAILABLE",
        "",
        "取不到的项留空，不插值、不用近似序列顶替。下面每条写明试过的来源、结果和原因。",
        "",
    ]
    if not GAPS:
        lines.append("本次没有单独登记的缺口。")
    else:
        current = ""
        for g in GAPS:
            if g["section"] != current:
                current = g["section"]
                lines += ["", f"## {current}", ""]
            lines.append(f"- **{g['item']}**")
            lines.append(f"  - 试过：{g['tried']}")
            lines.append(f"  - 结果：{g['result']}")
            lines.append(f"  - 原因：{g['reason']}")
    (ROOT / "UNAVAILABLE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_readme(n_index: int, n_events: int, n_qdii: int, funds: list[str], event_rows: list[dict]) -> None:
    seen = {r["code"] for r in event_rows}
    empty = [c for c in funds if c not in seen]
    text = f"""# point-in-time 资料（2026-10-22）

只登记事实和来源。没有策略、时点、组合收益、排名或业绩数字。

## 文件

- `index_launch.csv`：{n_index} 行。中证代码来自 `https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info/{{code}}`，详情页作 `source_url_1`，编制方案 PDF 作 `source_url_2`。两边日期不一致时，CSV 保留详情接口的日期，并在 `note` 并列 PDF 的日期。
- `etf_events.csv`：{n_events} 行。`source_url` 是上交所基金公告或巨潮 PDF；`cross_check_url` 是天天基金分红送配页。`cash_per_unit` 单位是人民币元/份。公告写「元/10 份」时已除以 10。天天基金「拆分折算日」在抽不到权益登记日时写入 `ex_date`。
- `qdii_candidates.csv`：{n_qdii} 行。候选来自上交所基金简称表和巨潮深市 ETF/LOF 列表，再用天天基金档案的跟踪标的/业绩比较基准确认，并要求页面出现 QDII 或基金类型含「海外」。`avg_amount_60d` 是截至 2026-09-30 的 60 个交易日搜狐日行情 `hq[8]` 的算术平均，换算成人民币元（源字段与成交量×价格对照后按万元理解，原始响应在 `raw/sohu/`）。不足 60 个交易日则留空。
- 集思录 QDII 列表可以打开，但匿名接口不翻页，也没有日频溢价历史，所以 `premium_history_available` 全部为「否」，`raw/` 下不存放溢价历史。

## 核查后没有分红、折算、拆分记录的基金

{', '.join(empty) if empty else '（无）'}

这些代码的交易所/巨潮标题和天天基金分红页都查过。没有事件就没有行，不算缺口。
"""
    (ROOT / "README.md").write_text(text, encoding="utf-8")


def write_manifest() -> None:
    files = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        if path.name == "MANIFEST.json":
            continue
        rel = path.relative_to(ROOT).as_posix()
        files.append({"path": rel, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    payload = {
        "generated_for": "incoming/grok-pit-20261022",
        "file_count": len(files),
        "files": files,
        "note": "MANIFEST.json 自身不计入列表，避免自引用。",
    }
    (ROOT / "MANIFEST.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    indexes, funds = universe_codes()
    (RAW / "code_lists.json").write_text(json.dumps({"indexes": indexes, "funds": funds}, ensure_ascii=False, indent=2), encoding="utf-8")
    index_rows = fetch_indexes(indexes)
    write_csv(
        ROOT / "index_launch.csv",
        ["index_code", "index_name", "base_date", "launch_date", "source_url_1", "source_url_2", "note"],
        index_rows,
    )
    event_rows = fetch_events(funds)
    write_csv(
        ROOT / "etf_events.csv",
        ["code", "listing_date", "event_type", "record_date", "ex_date", "cash_per_unit", "split_ratio", "source_url", "cross_check_url"],
        event_rows,
    )
    qdii_rows = fetch_qdii()
    write_csv(
        ROOT / "qdii_candidates.csv",
        ["code", "name", "tracking_index", "listing_date", "avg_amount_60d", "premium_source", "premium_history_available", "quota_or_suspension_notes"],
        qdii_rows,
    )
    write_unavailable()
    write_readme(len(index_rows), len(event_rows), len(qdii_rows), funds, event_rows)
    write_manifest()
    print("DONE", len(index_rows), len(event_rows), len(qdii_rows), "gaps", len(GAPS), flush=True)


if __name__ == "__main__":
    main()
