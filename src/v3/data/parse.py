"""纯解析。不出网，不写库。"""
from __future__ import annotations

import re
from html.parser import HTMLParser

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class _Table(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in = False
        self._buf = ""
        self._row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag == "td":
            self._in = True
            self._buf = ""

    def handle_endtag(self, tag):
        if tag == "td" and self._in:
            self._row.append(re.sub(r"\s+", " ", self._buf).strip())
            self._in = False
        elif tag == "tr" and self._row:
            self.rows.append(self._row)

    def handle_data(self, data):
        if self._in:
            self._buf += data


def _num(text: str) -> float | None:
    if text is None:
        return None
    raw = text.replace(",", "").replace("%", "").strip()
    if raw in {"", "-", "--"}:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if value != value:
        return None
    return value


def parse_sge_daily(html: str) -> list[dict]:
    """上金所日行情表。只收下 Au99.99 与 Au9999，不把别的合约并进来。"""
    parser = _Table()
    parser.feed(html)
    out = []
    for row in parser.rows:
        if len(row) < 11 or row[1] not in {"Au99.99", "Au9999"}:
            continue
        if not _DATE.match(row[0]):
            continue
        close = _num(row[5])
        if close is None:
            continue
        out.append({
            "date": row[0],
            "contract": row[1],
            "open": _num(row[2]),
            "high": _num(row[3]),
            "low": _num(row[4]),
            "close": close,
            "volume": _num(row[9]),
            "amount": _num(row[10]),
        })
    return out


def parse_fund_catalog(text: str) -> list[dict]:
    """东财 fundcode_search.js。类型原文保留，不把联接基金算成场内 ETF。"""
    rows = []
    for code, name, kind in re.findall(r'\["(\d{6})","[^"]*","([^"]*)","([^"]*)"', text):
        rows.append({"code": code, "name": name, "fund_type": kind})
    return rows


def on_exchange_qdii(rows: list[dict]) -> list[dict]:
    """场内代码，且类型或名称含 QDII / 海外。联接基金不进名单。"""
    out = []
    seen = set()
    for row in rows:
        code = row["code"]
        blob = f"{row.get('name') or ''} {row.get('fund_type') or ''}"
        if code in seen or "联接" in (row.get("name") or ""):
            continue
        if not exchange_code(code):
            continue
        if "QDII" not in blob and "海外" not in blob:
            continue
        seen.add(code)
        out.append(row)
    return out


def parse_qdii_rank(text: str) -> list[dict]:
    """东财 rankhandler 的 datas 数组。只取代码和名称，其余字段不解释成收益。"""
    codes = []
    for match in re.finditer(r'"(\d{6}),([^,"]*)', text):
        code, name = match.group(1), match.group(2)
        codes.append({"code": code, "name": name})
    # 去重，保留先出现的名称
    seen = set()
    out = []
    for row in codes:
        if row["code"] in seen:
            continue
        seen.add(row["code"])
        out.append(row)
    return out


def parse_szse_fund_row(row: dict) -> dict | None:
    """深交所基金列表一行。上市日来自 ssrq。"""
    code_html = row.get("sys_key") or ""
    name_html = row.get("jjjcurl") or ""
    code = _anchor_text(code_html)
    name = _anchor_text(name_html)
    if not re.fullmatch(r"\d{6}", code or ""):
        return None
    listed = (row.get("ssrq") or "").strip()
    if listed and not _DATE.match(listed):
        listed = ""
    return {
        "code": code,
        "name": name,
        "kind": (row.get("jjlb") or "").strip(),
        "list_date": listed,
    }


def _anchor_text(html: str) -> str:
    match = re.search(r">([^<]+)<", html or "")
    return match.group(1).strip() if match else re.sub(r"<[^>]+>", "", html or "").strip()


def parse_jbgk(html: str) -> dict:
    """基金概况页的可见字段。没有上市日期字段时不编一个。"""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    full = _after(text, "基金全称")
    kind = _after(text, "基金类型")
    track = _after(text, "跟踪标的")
    setup = ""
    match = re.search(r"成立日期/规模\s*(\d{4}年\d{2}月\d{2}日)", text)
    if match:
        y, m, d = re.findall(r"\d+", match.group(1))[:3]
        setup = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    listed = ""
    match = re.search(r"上市日期\s*(\d{4}年\d{2}月\d{2}日|\d{4}-\d{2}-\d{2})", text)
    if match:
        raw = match.group(1)
        if "-" in raw:
            listed = raw
        else:
            y, m, d = re.findall(r"\d+", raw)[:3]
            listed = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    return {
        "full_name": full,
        "fund_type": kind,
        "track": track,
        "setup_date": setup,
        "list_date": listed,
        "single_index": classify_track(track),
    }


def _after(text: str, label: str) -> str:
    match = re.search(re.escape(label) + r"\s+(\S+)", text)
    return match.group(1) if match else ""


def appendix1_decision(name: str, fund_type: str, track: str) -> str:
    """附录 1。返回 include，或 exclude:原因。不猜测合同里没写的跟踪标的。"""
    kind = fund_type or ""
    label = f"{name} {kind} {track}"
    if any(token in kind for token in ("债", "货币", "REIT", "Reit")):
        return "exclude:债券、货币或REITs"
    if "商品" in kind or any(token in label for token in ("黄金", "原油", "豆粕")):
        return "exclude:跨境商品，归入商品大类"
    if classify_track(track) != "single_index":
        return "exclude:跟踪标的不是单一指数"
    if "QDII" not in label and "海外" not in kind:
        return "exclude:代码表类型不含QDII或海外"
    return "include"


def classify_track(track: str) -> str:
    """单一海外指数 / 不是 / 看不出来。百分号和加号视为多基准，不当成一个容器。"""
    text = (track or "").strip()
    if not text or "无跟踪" in text:
        return "not_single_index"
    if any(tok in text for tok in ("+", "＋", "和", "以及", "%", "％")):
        return "not_single_index"
    if "指数" in text:
        return "single_index"
    return "unknown"


def exchange_code(code: str) -> bool:
    """场内 ETF/LOF 的代码形态。场外 000/006 和上证开放式 519 不在这里。"""
    return re.fullmatch(
        r"(159\d{3}|1[56]\d{4}|50[12]\d{3}|51[0-8]\d{3}|52\d{4}|56\d{4}|58\d{4})",
        code or "",
    ) is not None
