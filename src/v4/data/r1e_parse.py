"""v4-R1e 场内 QDII / LOF 普查的纯解析。不出网，不算收益。

分组按预注册第 2.2 版 §3.1：同一指数用英文正式名称或代码；
主动基金用业绩比较基准里权重最大的指数；跨境商品归入商品大类。
162411 与 159518 / 513350、159100 与 520870 是这条规则点名要合并的两对。
"""
from __future__ import annotations

import io
import re
import zipfile
import xml.etree.ElementTree as ET

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_T = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"

OIL = "S&P Oil & Gas Exploration & Production Select Industry Index"
IBOV = "Ibovespa Index"
SOX = "PHLX Semiconductor Sector Index"

# 预注册点名，以及基准英文名和中文译名不是逐字相同的那几只。不靠模糊相似度。
MANDATED_NAMES = {
    "标普石油天然气勘探及生产精选行业指数": OIL,
    "标普石油天然气上游股票指数": OIL,
    "s&p oil & gas exploration & production select industry index": OIL,
    "s&p oil & gas exploration & production select industry": OIL,
    "巴西伊博维斯帕指数": IBOV,
    "巴西ibovespa指数": IBOV,
    "ibovespa": IBOV,
    "ibovespa index": IBOV,
    "bovespa": IBOV,
    "费城半导体指数": SOX,
    "phlx semiconductor sector index": SOX,
    "phlx semiconductor sector": SOX,
}
MANDATED_CODES = {
    "SPSIOP": OIL,
    "IBOV": IBOV,
    "IBOVESPA": IBOV,
    "SOX": SOX,
    "XSOX": SOX,
}
CROSS_BORDER_SUBCLASS = {"04", "33", "34"}
COMMODITY_NAME = {
    "crude-oil": "原油",
    "gold": "黄金",
    "silver": "白银",
    "soymeal": "豆粕",
    "cross-border-commodity": "跨境商品",
}


def norm_name(text: str) -> str:
    """比较指数名称。去掉空白、标点和「收益率」，不去掉「指数」。"""
    raw = (text or "").lower().replace("\xa0", " ")
    raw = raw.replace("＆", "&")
    raw = re.sub(r"收益率|经估值汇率调整后的", "", raw)
    raw = re.sub(r"[\s\u3000\-_/.,，。;；:：'\"“”]+", "", raw)
    raw = raw.replace("（", "(").replace("）", ")")
    return raw


def alpha_code(text: str) -> str:
    """指数代码。纯数字（深交所拟合指数内部号）不当成代码。"""
    raw = re.sub(r"[^A-Za-z0-9]", "", (text or "").upper())
    if re.fullmatch(r"[A-Z][A-Z0-9]{1,14}", raw or ""):
        return raw
    return ""


def iso_date(text: str) -> str:
    raw = (text or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    if re.fullmatch(r"\d{8}", raw):
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    match = re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw)
    if match:
        y, m, d = (int(part) for part in match.groups())
        return f"{y:04d}-{m:02d}-{d:02d}"
    return ""


def split_bilingual(text: str) -> tuple[str, str]:
    """括号里的英文单独取出。允许英文名自己再套一层括号。没有英文括号时 english 为空。"""
    raw = (text or "").strip()
    matches = re.findall(r"[（(]([A-Za-z][^（）()]*(?:\([^)]*\))?[^（）()]*)[）)]", raw)
    english = ""
    if matches:
        english = re.sub(r"\s+", " ", max(matches, key=len)).strip(" ，,")
    chinese = re.sub(r"[（(][^（）()]*(?:\([^)]*\))?[^（）()]*[）)]", "", raw)
    chinese = re.sub(r"收益率", "", chinese).strip(" ，,")
    return chinese, english


def clean_index_label(text: str) -> str:
    """去掉汇率套话和权重，留下指数名称。"""
    raw = (text or "").strip()
    raw = re.sub(r"^经[^的]{0,24}的", "", raw)
    raw = re.sub(r"^[（(]?人民币计价[）)]?", "", raw)
    raw = re.sub(r"^\d+(?:\.\d+)?\s*[%％]\s*[×*xX]", "", raw)
    raw = re.sub(r"[×*xX]\s*\d+(?:\.\d+)?\s*[%％]\s*$", "", raw)
    raw = raw.replace("收益率", "")
    raw = re.sub(r"[（(]人民币计价[）)]", "", raw)
    return re.sub(r"\s+", " ", raw).strip(" ，,")


def commodity_bucket(name: str, fund_type: str = "", track: str = "") -> str:
    """跨境商品大类。石油天然气股票指数不是原油商品。"""
    blob = f"{name} {fund_type} {track}"
    equity_oil = any(tok in blob for tok in ("上游股票", "勘探及生产", "精选行业"))
    if any(tok in blob for tok in ("原油", "布伦特", "WTI", "Brent")) and "股票指数" not in blob:
        return "crude-oil"
    if equity_oil and "原油" not in blob:
        return ""
    if "黄金" in blob or "贵金属" in blob:
        return "gold"
    if "白银" in blob:
        return "silver"
    if "豆粕" in blob:
        return "soymeal"
    if any(tok in blob for tok in ("商品", "抗通胀")):
        return "cross-border-commodity"
    return ""


def heaviest_benchmark_index(text: str) -> dict | None:
    """业绩比较基准里权重最大的那只指数。没有权重就只有一只指数时用那一只。"""
    raw = (text or "").strip()
    if not raw:
        return None
    scored = []
    for order, part in enumerate(re.split(r"\+|＋", raw)):
        if "指数" not in part and not re.search(r"\bIndex\b", part, re.I):
            continue
        weights = [float(item) for item in re.findall(r"(\d+(?:\.\d+)?)\s*[%％]", part)]
        weight = weights[-1] if weights else None
        chinese, english = split_bilingual(part)
        label = clean_index_label(english or chinese)
        chinese = clean_index_label(chinese)
        english = clean_index_label(english)
        if not label:
            continue
        scored.append((weight if weight is not None else -1.0, -order, label, english, chinese, weight))
    if not scored:
        return None
    scored.sort(reverse=True)
    _rank, _order, label, english, chinese, weight = scored[0]
    return {"name": label, "english": english, "chinese": chinese, "weight": weight}


def xlsx_table(raw: bytes) -> list[list[str]]:
    """深交所导出的 xlsx。单元格是 inlineStr。"""
    book = zipfile.ZipFile(io.BytesIO(raw))
    root = ET.fromstring(book.read("xl/worksheets/sheet1.xml"))
    table = []
    for row in root.findall("m:sheetData/m:row", _NS):
        vals: list[str] = []
        for cell in row.findall("m:c", _NS):
            ref = cell.get("r") or "A"
            col = "".join(ch for ch in ref if ch.isalpha())
            idx = 0
            for ch in col:
                idx = idx * 26 + (ord(ch.upper()) - 64)
            while len(vals) < idx:
                vals.append("")
            if cell.get("t") == "inlineStr":
                text = "".join(node.text or "" for node in cell.iter(_T))
            else:
                node = cell.find("m:v", _NS)
                text = node.text if node is not None and node.text else ""
            vals[idx - 1] = text.strip()
        if any(vals):
            table.append(vals)
    return table


def table_dicts(table: list[list[str]]) -> list[dict]:
    if not table:
        return []
    header = [re.sub(r"\s+", "", cell) for cell in table[0]]
    out = []
    for row in table[1:]:
        item = {}
        for key, value in zip(header, row):
            if key:
                item[key] = value
        if item:
            out.append(item)
    return out


def szse_code_name(row: dict) -> tuple[str, str]:
    code = ""
    name = ""
    for key, value in row.items():
        if "代码" in key and re.search(r"\d{6}", value or ""):
            code = re.search(r"\d{6}", value).group(0)
        if not name and any(tok in key for tok in ("简称", "名称")):
            name = re.sub(r"<[^>]+>", "", value or "").strip()
    return code, name


def is_qdii_row(row: dict, em_type: str = "") -> tuple[bool, str]:
    """这只是否进入场内 QDII ETF / LOF 普查。联接基金不进。"""
    name = f"{row.get('name') or ''} {row.get('full_name') or ''}"
    kind = f"{em_type} {row.get('fund_type') or ''}"
    if "联接" in name:
        return False, "联接基金"
    subclass = str(row.get("sub_class") or "")
    if subclass in CROSS_BORDER_SUBCLASS:
        return True, "sse_cross_border_subclass"
    if "QDII" in name or "QDII" in kind or "海外" in kind:
        return True, "qdii_or_overseas"
    blob = f"{name} {kind} {row.get('index_name') or ''}"
    if any(tok in blob for tok in ("原油", "布伦特", "WTI", "Brent")):
        return True, "cross_border_commodity"
    bucket = commodity_bucket(name, kind, row.get("index_name") or "")
    if bucket and ("QDII" in kind or "海外" in kind):
        return True, "cross_border_commodity"
    return False, ""


def management_style(row: dict, em_type: str = "") -> str:
    """passive / active / unknown。有跟踪指数或指数代码视为被动。"""
    kind = f"{em_type} {row.get('fund_type') or ''}"
    track = row.get("index_name") or ""
    if alpha_code(row.get("index_code") or "") or ("指数" in track and "无跟踪" not in track):
        return "passive"
    if any(tok in kind for tok in ("普通股票", "混合", "FOF", "主动")):
        return "active"
    if "无跟踪" in track or "无跟踪" in (row.get("benchmark") or ""):
        return "active"
    if "指数" in kind:
        return "passive"
    if row.get("vehicle") == "ETF" and track:
        return "passive"
    return "unknown"


def _learned_names(rows: list[dict]) -> dict[str, str]:
    """交易所自己把指数代码和中文名称写在同一行时，用这个对照。点名合并覆盖它。"""
    learned: dict[str, str] = {}
    for row in rows:
        code = alpha_code(row.get("index_code") or "")
        if not code:
            continue
        key = MANDATED_CODES.get(code, code)
        for text in (row.get("index_name") or "", row.get("english_name") or ""):
            folded = norm_name(text)
            if len(folded) >= 4:
                learned.setdefault(folded, key)
    for name, key in MANDATED_NAMES.items():
        learned[norm_name(name)] = key
    return learned


def _lookup_name(text: str, learned: dict[str, str]) -> str:
    folded = norm_name(text)
    if not folded:
        return ""
    if folded in learned:
        return learned[folded]
    chinese, english = split_bilingual(text)
    for piece in (english, chinese):
        folded_piece = norm_name(piece)
        if folded_piece in learned:
            return learned[folded_piece]
    return ""


def group_funds(rows: list[dict]) -> list[dict]:
    """给每只基金写上 group_key、group_name、group_rule。不改容器。"""
    learned = _learned_names(rows)
    grouped = []
    for row in rows:
        item = dict(row)
        bucket = commodity_bucket(
            f"{item.get('name') or ''} {item.get('full_name') or ''}",
            item.get("fund_type") or "",
            item.get("index_name") or "",
        )
        if bucket:
            item["group_key"] = bucket
            item["group_name"] = COMMODITY_NAME[bucket]
            item["group_rule"] = "cross_border_commodity"
            item["commodity"] = bucket
            grouped.append(item)
            continue
        item["commodity"] = ""
        code = alpha_code(item.get("index_code") or "")
        if code and code in MANDATED_CODES:
            item["group_key"] = MANDATED_CODES[code]
            item["group_rule"] = "mandated_code"
        else:
            hit = ""
            rule = ""
            for field, why in (
                ("english_name", "english_name"),
                ("index_name", "index_name"),
                ("benchmark_index", "benchmark"),
                ("benchmark_english", "benchmark"),
            ):
                hit = _lookup_name(item.get(field) or "", learned)
                if hit:
                    rule = "mandated" if hit in {OIL, IBOV, SOX} else f"learned_{why}"
                    break
            if hit:
                item["group_key"] = hit
                item["group_rule"] = rule
            elif code:
                item["group_key"] = code
                item["group_rule"] = "index_code"
            elif item.get("benchmark_index"):
                item["group_key"] = item["benchmark_index"]
                item["group_rule"] = "benchmark_max_weight"
            elif item.get("index_name"):
                item["group_key"] = item["index_name"]
                item["group_rule"] = "index_name"
            else:
                item["group_key"] = f"fund:{item.get('code')}"
                item["group_rule"] = "singleton"
        key = item["group_key"]
        if key == OIL:
            item["group_name"] = OIL
        elif key == IBOV:
            item["group_name"] = IBOV
        elif key == SOX:
            item["group_name"] = SOX
        else:
            item["group_name"] = item.get("english_name") or item.get("index_name") or item.get("benchmark_index") or key
        grouped.append(item)
    names: dict[str, str] = {}
    for item in grouped:
        key = item["group_key"]
        if key in {OIL, IBOV, SOX} or key in COMMODITY_NAME:
            names[key] = item["group_name"]
            continue
        current = names.get(key) or ""
        candidate = item.get("english_name") or ""
        if not candidate and item.get("group_rule") == "index_code":
            candidate = item.get("index_name") or ""
        if candidate and (not current or len(candidate) > len(current)):
            names[key] = candidate
        elif key not in names:
            names[key] = item["group_name"]
    for item in grouped:
        item["group_name"] = names.get(item["group_key"]) or item["group_name"]
    return grouped
