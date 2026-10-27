"""纯解析。不出网，不写库。"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SGE_ARTICLE = re.compile(
    r'href="(/sjzx/mrhqsj/\d+)"[\s\S]{0,500}?'
    r"上海黄金交易所(\d{4})年(\d{1,2})月(\d{1,2})日交易行情"
)


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
        elif tag in {"td", "th"}:
            self._in = True
            self._buf = ""

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self._in:
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


def _label(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def contract_key(text: str) -> str:
    """Au99.99 与 Au9999 都收成 AU9999。带前缀的 iAu99.99 不会并进来。"""
    return re.sub(r"[^A-Za-z0-9]", "", text or "").upper()


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


def _header_index(header: list[str], name: str) -> int | None:
    if name in header:
        return header.index(name)
    for i, label in enumerate(header):
        if label.startswith(name):
            return i
    return None


def _cell(row: list[str], index: int | None):
    if index is None or index >= len(row):
        return None
    return _num(row[index])


def parse_sge_index_page(html: str) -> list[dict]:
    """历史行情列表页。返回文章路径和标题里的交易日。"""
    out = []
    seen = set()
    for path, year, month, day in _SGE_ARTICLE.findall(html):
        date = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        if path in seen:
            continue
        seen.add(path)
        out.append({"path": path, "date": date})
    return out


def parse_sge_history(html: str) -> list[dict]:
    """历史行情文章里的表。按表头取列，不按列号。只留 Au99.99 / Au9999。"""
    parser = _Table()
    parser.feed(html)
    header_at = None
    header: list[str] = []
    for i, row in enumerate(parser.rows):
        labels = [_label(cell) for cell in row]
        if "收盘价" in labels:
            header_at = i
            header = labels
            break
    if header_at is None:
        return []
    i_open = _header_index(header, "开盘价")
    i_high = _header_index(header, "最高价")
    i_low = _header_index(header, "最低价")
    i_close = _header_index(header, "收盘价")
    i_volume = _header_index(header, "成交量")
    i_amount = _header_index(header, "成交金额")
    out = []
    for row in parser.rows[header_at + 1:]:
        if not row or contract_key(row[0]) != "AU9999":
            continue
        close = _cell(row, i_close)
        if close is None or close <= 0:
            continue
        out.append({
            "contract": re.sub(r"\s+", "", row[0]),
            "open": _cell(row, i_open),
            "high": _cell(row, i_high),
            "low": _cell(row, i_low),
            "close": close,
            "volume": _cell(row, i_volume),
            "amount": _cell(row, i_amount),
        })
    return out


def parse_sge_dailyhq(payload: dict) -> list[dict]:
    """/graph/Dailyhq?instid=Au99.99。数组是开盘、收盘、最低、最高。"""
    out = []
    for rec in payload.get("time") or []:
        if not isinstance(rec, (list, tuple)) or len(rec) < 5:
            continue
        if not _DATE.match(str(rec[0])):
            continue
        close = _num(str(rec[2]))
        if close is None or close <= 0:
            continue
        out.append({
            "date": str(rec[0]),
            "contract": "Au99.99",
            "open": _num(str(rec[1])),
            "close": close,
            "low": _num(str(rec[3])),
            "high": _num(str(rec[4])),
        })
    return out


def chinabond_day(millis: int | str) -> str:
    """查询结果的键是 UTC 毫秒。页面按台北时间的日期展示，16:00Z 是次日。"""
    stamp = datetime.fromtimestamp(int(millis) / 1000, timezone.utc)
    return stamp.astimezone(ZoneInfo("Asia/Taipei")).date().isoformat()


def parse_chinabond_wealth(payload: dict) -> list[dict]:
    """单指数查询的财富（总值）序列。同一天留最后一笔。"""
    series = payload.get("CFZS_00") or {}
    by_date = {}
    for key, value in series.items():
        close = _num(str(value) if value is not None else "")
        if close is None or close <= 0:
            continue
        by_date[chinabond_day(key)] = close
    return [{"date": day, "close": by_date[day]} for day in sorted(by_date)]


def parse_chinabond_method(text: str) -> dict:
    """编制说明正文。去掉空白后再取名称、财富代码和基准日。没有首次发布日就不填。"""
    compact = re.sub(r"\s+", "", text or "")
    name = ""
    found = re.search(r"中文名称[:：](.+?)英文名称", compact)
    if found:
        name = found.group(1)
    code = ""
    found = re.search(r"财富指数代码[:：](CBA\d{5})", compact)
    if found:
        code = found.group(1)
    base = ""
    found = re.search(r"基准日(?:为)?(\d{4})年(\d{1,2})月(\d{1,2})日", compact)
    if found:
        base = f"{int(found.group(1)):04d}-{int(found.group(2)):02d}-{int(found.group(3)):02d}"
    return {"index_name": name, "wealth_code": code, "base_date": base}


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
