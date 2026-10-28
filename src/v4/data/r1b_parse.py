"""v4-R1b 网页与表格的解析。不计算组合收益。"""
from __future__ import annotations

import json
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from src.data.sources import _f, _row

from .adjust import ms_to_date

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_RANK_ROW = re.compile(r'"([^"]*)"')
_TAG = re.compile(r"<[^>]+>")


def parse_rank_index_funds(text: str, inception_on_or_before: str) -> list[dict]:
    """东财指数型排名。只留下成立日不晚于给定日的行。不读取申购赎回费率。"""
    match = re.search(r"datas:\[(.*)\]\s*,\s*allRecords", text, re.S)
    if not match:
        raise ValueError("rankhandler 没有 datas")
    out = []
    for raw in _RANK_ROW.findall(match.group(1)):
        parts = raw.split(",")
        if len(parts) < 17 or not re.fullmatch(r"\d{6}", parts[0]):
            continue
        inception = parts[16]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", inception):
            continue
        if inception > inception_on_or_before:
            continue
        out.append({"code": parts[0], "name": parts[1], "inception": inception})
    return out


def _cell(html: str, label: str) -> str:
    match = re.search(rf"{re.escape(label)}</th>\s*<td[^>]*>\s*([^<]+)", html)
    if not match:
        return ""
    return _TAG.sub("", match.group(1)).strip()


def parse_jbgk(html: str) -> dict:
    """概况页上的名称、成立日、跟踪标的。不读取费率。"""
    inception = _cell(html, "成立日期/规模")
    day = ""
    matched = re.search(r"(\d{4})年(\d{2})月(\d{2})日", inception)
    if matched:
        day = f"{matched.group(1)}-{matched.group(2)}-{matched.group(3)}"
    return {
        "name": _cell(html, "基金全称") or _cell(html, "基金简称"),
        "short_name": _cell(html, "基金简称"),
        "inception": day,
        "tracked_index": _cell(html, "跟踪标的"),
    }


def _assign_js(text: str, name: str) -> str:
    match = re.search(rf"var\s+{name}\s*=\s*", text)
    if not match:
        raise ValueError(f"pingzhongdata 没有 {name}")
    start = match.end()
    opener = text[start]
    if opener == "[":
        close = "]"
    elif opener == "{":
        close = "}"
    else:
        raise ValueError(f"{name} 不是数组或对象")
    depth = 0
    for i in range(start, len(text)):
        char = text[i]
        if char == opener:
            depth += 1
        elif char == close:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise ValueError(f"{name} 没有收尾")


def parse_pingzhongdata(text: str, end: date) -> list[dict]:
    """单位净值、累计净值、日增长率、分红。截止到 end，不含更晚的日子。"""
    raw = json.loads(_assign_js(text, "Data_netWorthTrend"))
    accum = {}
    if "Data_ACWorthTrend" in text:
        for pair in json.loads(_assign_js(text, "Data_ACWorthTrend")):
            if isinstance(pair, list) and len(pair) >= 2:
                accum[int(pair[0])] = pair[1]
    hi = end.isoformat()
    points = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict) or item.get("x") is None or item.get("y") is None:
            continue
        day = ms_to_date(int(item["x"]))
        if day > hi or day in seen:
            continue
        seen.add(day)
        dividend = item.get("unitMoney")
        points.append({
            "date": day,
            "unit_nav": _f(item.get("y")),
            "accum_nav": _f(accum.get(int(item["x"]))),
            "equity_return": _f(item.get("equityReturn")),
            "dividend": _f(dividend) if dividend not in (None, "") else 0.0,
        })
    points.sort(key=lambda row: row["date"])
    return points


def parse_safe_mid(path: Path) -> list[dict]:
    """外管局人民币汇率中间价工作簿。美元、港元列是 100 外币兑人民币。"""
    with zipfile.ZipFile(path) as book:
        strings = _shared_strings(book)
        sheet = ET.fromstring(book.read("xl/worksheets/sheet1.xml"))
    rows = []
    for row in sheet.findall("m:sheetData/m:row", _NS):
        values = [_cell_value(cell, strings) for cell in row.findall("m:c", _NS)]
        if len(values) < 5 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(values[0])):
            continue
        usd = _quote(values[1])
        hkd = _quote(values[4])
        rows.append({"date": values[0], "usd_per_hundred": usd, "hkd_per_hundred": hkd})
    rows.sort(key=lambda item: item["date"])
    return rows


def _quote(value) -> float | None:
    if value in (None, "", "-"):
        return None
    number = _f(value)
    if number is None or number <= 0:
        return None
    return number


def _shared_strings(book: zipfile.ZipFile) -> list[str]:
    root = ET.fromstring(book.read("xl/sharedStrings.xml"))
    out = []
    for item in root.findall("m:si", _NS):
        out.append("".join(node.text or "" for node in item.iter(f"{{{_NS['m']}}}t")))
    return out


def _cell_value(cell, strings: list[str]) -> str:
    node = cell.find("m:v", _NS)
    if node is None or node.text is None:
        return ""
    if cell.get("t") == "s":
        return strings[int(node.text)]
    return node.text


def parse_tencent_kline_rows(lines: list) -> list[dict]:
    """腾讯行是 [日期, 开, 收, 高, 低, 量]。"""
    rows = []
    for item in lines or []:
        if not isinstance(item, (list, tuple)) or len(item) < 6:
            continue
        row = _row(item[0], item[1], item[3], item[4], item[2], item[5])
        if row and row["close"] and row["close"] > 0:
            rows.append(row)
    dedup = {row["date"]: row for row in rows}
    return [dedup[day] for day in sorted(dedup)]


def parse_eastmoney_klines(payload: dict) -> tuple[str, list[dict]]:
    """fqt=2 的单次 K 线。日期,开,收,高,低,量,额。"""
    data = (payload or {}).get("data") or {}
    name = str(data.get("name") or "")
    rows = []
    for line in data.get("klines") or []:
        parts = line.split(",")
        if len(parts) < 7:
            continue
        row = _row(parts[0], parts[1], parts[3], parts[4], parts[2], parts[5], parts[6])
        if row and row["close"] and row["close"] > 0:
            rows.append(row)
    dedup = {row["date"]: row for row in rows}
    return name, [dedup[day] for day in sorted(dedup)]
