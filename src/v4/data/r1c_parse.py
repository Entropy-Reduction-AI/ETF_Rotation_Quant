"""v4-R1c 的网页解析、相近替身名单和后复权拼装。不出网，不算组合收益。"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta

from src.data.sources import _f

from .adjust import backward_total_return, ms_to_date, split_already_in_close
from .r1b_parse import _assign_js

# 与 operations/work_logs/2026-10-28-v4-r1c-vehicle-table.md 的「相近替身」表一致。
# 只登记 D15 已经决定的两只。near_index 是容器指数，不是它们实际跟踪的指数。
NEAR_SUBSTITUTES = (
    {
        "code": "161211",
        "name": "国投瑞银沪深300金融地产交易型开放式指数证券投资基金联接基金",
        "instrument": "otc_fund",
        "container_id": "allshare-financials-re",
        "container_name": "中证全指金融地产",
        "tracked_index": "沪深300金融地产指数",
        "near_index": "中证全指金融地产指数",
        "near_index_code": "H00992",
        "decision": "D15-2",
        "note": "相近替身。收益用这只基金自己的复权净值，不冒充中证全指金融地产。非增强，联接。成立日和净值起点 2010-04-09。",
    },
    {
        "code": "510880",
        "name": "上证红利交易型开放式指数证券投资基金",
        "instrument": "etf",
        "container_id": "csi-dividend",
        "container_name": "中证红利",
        "tracked_index": "上证红利指数",
        "near_index": "中证红利指数",
        "near_index_code": "H00922",
        "decision": "D15-3",
        "note": "相近替身。实际跟踪上证红利，不是中证红利。对上证红利容器是同一指数的场内 ETF。",
    },
)

# 载体表写明不入库、也不当替身。这里只留名字，不写进登记表。
REJECTED_NOT_SUBSTITUTE = (
    "国证2000指数",
    "中证200指数",
    "中证上游资源产业指数",
    "上证商品",
    "上证消费80",
    "中证银行指数",
    "上证180金融股指数",
    "深证电子信息传媒产业50指数",
    "深证红利指数",
)

_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_CASH_10 = re.compile(r"每\s*10\s*份派现金\s*([0-9]+(?:\.[0-9]+)?)\s*元")
_CASH_1 = re.compile(r"每\s*份派现金\s*([0-9]+(?:\.[0-9]+)?)\s*元")
_RATIO = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*[:：]\s*([0-9]+(?:\.[0-9]+)?)")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class ParseError(ValueError):
    pass


def near_substitute_rows() -> list[dict]:
    """登记表。每行都写明相近的指数。拒绝名单不在这里。"""
    rows = []
    for item in NEAR_SUBSTITUTES:
        if not item["near_index"] or not item["tracked_index"]:
            raise ParseError(f"{item['code']} 没有写明相近指数或实际跟踪指数")
        if item["near_index"] == item["tracked_index"]:
            raise ParseError(f"{item['code']} 的相近指数和实际跟踪指数相同")
        rows.append(dict(item))
    codes = [row["code"] for row in rows]
    if codes != ["161211", "510880"]:
        raise ParseError(f"相近替身必须是载体表的两只，现在是 {codes}")
    return rows


def _text(fragment: str) -> str:
    return _TAG.sub("", fragment).replace("&nbsp;", " ").strip()


def _table_after(html: str, header: str) -> str:
    """取包含表头的那张表。表头在 th 里面，不在表的后面。"""
    pos = html.find(header)
    if pos < 0:
        return ""
    start = html.rfind("<table", 0, pos)
    end = html.find("</table>", pos)
    if start < 0 or end < 0:
        return ""
    return html[start:end]


def _body_rows(table: str) -> list[list[str]]:
    body = table
    marker = table.lower().find("<tbody")
    if marker >= 0:
        body = table[marker:]
    rows = []
    for raw in _ROW.findall(body):
        cells = [_text(cell) for cell in _CELL.findall(raw)]
        if cells:
            rows.append(cells)
    return rows


def cash_amount(text: str) -> float:
    """分红单元格换成每股金额。每 10 份派现要除以 10。"""
    match = _CASH_10.search(text.replace(",", ""))
    if match:
        return float(match.group(1)) / 10.0
    match = _CASH_1.search(text.replace(",", ""))
    if match:
        return float(match.group(1))
    raise ParseError(f"认不出分红金额：{text}")


def split_ratio(text: str) -> tuple[float, float]:
    """东财「1:2」是 1 份旧份额变成 2 份新份额。返回 (新份额, 旧份额)。"""
    match = _RATIO.search(text.replace(",", ""))
    if not match:
        raise ParseError(f"认不出拆分比例：{text}")
    old = float(match.group(1))
    new = float(match.group(2))
    if old <= 0 or new <= 0:
        raise ParseError(f"拆分比例必须为正：{text}")
    return new, old


def parse_fhsp(html: str) -> dict:
    """天天基金分红送配页。表头在静态 HTML 里，金额没有被拿掉。"""
    dividend_table = _table_after(html, "每10份分红")
    split_table = _table_after(html, "拆分折算比例")
    if not dividend_table or not split_table:
        raise ParseError("分红送配页缺少分红表或拆分表")
    dividends = []
    explicit_empty_div = "暂无分红" in dividend_table
    if not explicit_empty_div:
        for cells in _body_rows(dividend_table):
            if len(cells) < 4:
                continue
            dates = _DATE.findall(" ".join(cells))
            if len(dates) < 2:
                raise ParseError(f"分红行没有除息日：{cells}")
            amount = cash_amount(cells[3])
            if amount <= 0:
                raise ParseError(f"分红必须为正：{cells}")
            dividends.append({
                "record_date": dates[0],
                "date": dates[1],
                "amount": amount,
                "pay_date": dates[2] if len(dates) > 2 else "",
                "text": cells[3],
            })
    splits = []
    explicit_empty_split = "暂无拆分" in split_table
    if not explicit_empty_split:
        for cells in _body_rows(split_table):
            if len(cells) < 4:
                continue
            dates = _DATE.findall(" ".join(cells))
            if not dates:
                raise ParseError(f"拆分行没有日期：{cells}")
            numerator, denominator = split_ratio(cells[3])
            splits.append({
                "date": dates[0],
                "kind_text": cells[2],
                "numerator": numerator,
                "denominator": denominator,
                "text": cells[3],
            })
    return {
        "dividends": dividends,
        "splits": splits,
        "explicit_empty_dividend": explicit_empty_div and not dividends,
        "explicit_empty_split": explicit_empty_split and not splits,
    }


def pingzhong_action_markers(text: str) -> list[str]:
    """净值脚本里的公司行为字样。页面常把金额数字拿掉，这里只看有没有字样。"""
    return [item for item in re.findall(r'"unitMoney":"([^"]*)"', text) if item.strip()]


def accum_unit_spread(text: str, end: date) -> float | None:
    """累计净值减单位净值的极差。没有累计净值时返回 None。"""
    if "Data_netWorthTrend" not in text or "Data_ACWorthTrend" not in text:
        return None
    raw = json.loads(_assign_js(text, "Data_netWorthTrend"))
    accum = {}
    for pair in json.loads(_assign_js(text, "Data_ACWorthTrend")):
        if isinstance(pair, list) and len(pair) >= 2 and pair[1] is not None:
            accum[int(pair[0])] = float(pair[1])
    diffs = []
    hi = end.isoformat()
    for item in raw:
        if not isinstance(item, dict) or item.get("x") is None or item.get("y") is None:
            continue
        day = ms_to_date(int(item["x"]))
        if day > hi:
            continue
        unit = _f(item.get("y"))
        acc = accum.get(int(item["x"]))
        if unit is None or acc is None:
            continue
        diffs.append(acc - unit)
    if len(diffs) < 2:
        return None
    return max(diffs) - min(diffs)


def _shift(day: str, n: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=n)).isoformat()


def align_ex_date(ex_date: str, bar_dates: set[str], limit: int = 5) -> str | None:
    """除息日或折算日没行情时，用其后 limit 个日历日内的第一根 K 线。"""
    for offset in range(limit + 1):
        key = _shift(ex_date, offset)
        if key in bar_dates:
            return key
    return None


def assemble_backward(bars: list[dict], dividends: list[dict], splits: list[dict]) -> dict:
    """用原始收盘和公布的公司行为做后复权。原始列表不被改写。

    腾讯原始收盘含拆分缺口。比例按「新份额 / 旧份额」乘回去。
    缺口已经不在收盘里的拆分不再乘。上市前的行为丢掉。
    """
    usable = [dict(bar) for bar in bars if bar.get("date") and bar.get("close") and float(bar["close"]) > 0]
    if not usable:
        raise ParseError("没有正收盘，不能做后复权")
    dates = {bar["date"] for bar in usable}
    first = usable[0]["date"]
    notes = []
    div_on: dict[str, float] = {}
    for item in dividends:
        if item["date"] < first:
            notes.append({"kind": "dividend", "date": item["date"], "note": "上市前，不参与后复权"})
            continue
        aligned = align_ex_date(item["date"], dates)
        if aligned is None:
            raise ParseError(f"分红除息日 {item['date']} 附近没有 K 线")
        div_on[aligned] = div_on.get(aligned, 0.0) + float(item["amount"])
        if aligned != item["date"]:
            notes.append({"kind": "dividend", "date": item["date"], "note": f"对齐到 {aligned}"})
    split_on = []
    for item in splits:
        if item["date"] < first:
            notes.append({"kind": "split", "date": item["date"], "note": "上市前，不参与后复权"})
            continue
        aligned = align_ex_date(item["date"], dates)
        if aligned is None:
            raise ParseError(f"拆分日 {item['date']} 附近没有 K 线")
        prev = _prev_close(usable, aligned)
        if prev is None:
            notes.append({"kind": "split", "date": item["date"], "note": "没有前收，不参与后复权"})
            continue
        close = _close_on(usable, aligned)
        if split_already_in_close(prev, close, float(item["numerator"]), float(item["denominator"])):
            notes.append({"kind": "split", "date": aligned, "note": "收盘里已经含这次拆分，不再乘"})
            continue
        split_on.append({
            "date": aligned,
            "numerator": float(item["numerator"]),
            "denominator": float(item["denominator"]),
        })
    applied_divs = [{"date": day, "amount": amount} for day, amount in sorted(div_on.items())]
    adjusted = backward_total_return(usable, applied_divs, split_on, splits_in_price=False)
    return {
        "adjusted": adjusted,
        "notes": notes,
        "dividends": applied_divs,
        "splits": split_on,
    }


def _close_on(bars: list[dict], day: str) -> float:
    for bar in bars:
        if bar["date"] == day:
            return float(bar["close"])
    raise KeyError(day)


def _prev_close(bars: list[dict], day: str) -> float | None:
    prev = None
    for bar in bars:
        if bar["date"] == day:
            return prev
        if bar.get("close") and float(bar["close"]) > 0:
            prev = float(bar["close"])
    return None


def spot_event(kind: str, day: str, raw: list[dict], adjusted: list[dict], amount: float, mult: float) -> dict:
    """核对后复权收益是否等于原始收益经分红和拆分修正后的值。只看这一天。"""
    prev_raw = _prev_close(raw, day)
    raw_close = _close_on(raw, day) if any(bar["date"] == day for bar in raw) else None
    prev_adj = _prev_close(adjusted, day)
    adj_close = _close_on(adjusted, day) if any(bar["date"] == day for bar in adjusted) else None
    if not prev_raw or not raw_close or not prev_adj or not adj_close:
        return {"kind": kind, "date": day, "continuous": "0", "note": "缺相邻K线",
                "raw_return": "", "adj_return": ""}
    raw_ret = raw_close / prev_raw - 1.0
    adj_ret = adj_close / prev_adj - 1.0
    expected = (raw_close / prev_raw) * mult - 1.0 + amount / prev_raw
    return {
        "kind": kind,
        "date": day,
        "raw_return": f"{raw_ret:.6f}",
        "adj_return": f"{adj_ret:.6f}",
        "continuous": "1" if abs(adj_ret - expected) < 1e-6 else "0",
        "note": f"expected={expected:.6f}",
    }


def parse_sina_nav(payload: dict) -> list[dict]:
    """新浪基金净值。只要日期、单位净值和累计净值。"""
    data = ((payload or {}).get("result") or {}).get("data") or {}
    rows = data.get("data") or []
    out = []
    for item in rows:
        day = str(item.get("fbrq") or "")[:10]
        unit = _f(item.get("jjjz"))
        accum = _f(item.get("ljjz"))
        if not _DATE.fullmatch(day) or unit is None or unit <= 0:
            continue
        out.append({"date": day, "unit_nav": unit, "accum_nav": accum})
    dedup = {row["date"]: row for row in out}
    return [dedup[day] for day in sorted(dedup)]


def sina_daily_growth(rows: list[dict]) -> list[dict]:
    """单位净值的日增长。累计净值相对单位净值跳升时，把跳升当作每股分红加回去。

    只产生逐日数字，不汇总。
    """
    out = []
    for prev, cur in zip(rows, rows[1:]):
        dividend = 0.0
        if prev.get("accum_nav") is not None and cur.get("accum_nav") is not None:
            dividend = (cur["accum_nav"] - cur["unit_nav"]) - (prev["accum_nav"] - prev["unit_nav"])
            if dividend < 0:
                dividend = 0.0
        growth = (cur["unit_nav"] + dividend) / prev["unit_nav"] - 1.0
        out.append({"date": cur["date"], "growth": growth, "dividend": dividend})
    return out


def series_daily_growth(rows: list[dict]) -> dict[str, float]:
    """复权净值相邻两天的涨跌。调用方只拿来逐日对照，不要再加总。"""
    out = {}
    usable = [row for row in rows if row.get("close") and float(row["close"]) > 0]
    for prev, cur in zip(usable, usable[1:]):
        out[cur["date"]] = float(cur["close"]) / float(prev["close"]) - 1.0
    return out


def growth_discrepancies(left: dict[str, float], right: list[dict], tolerance: float) -> list[dict]:
    """两边都有的日子。差值超过 tolerance 的留下。不算年化、累计或相关。"""
    problems = []
    for row in right:
        if row["date"] not in left:
            continue
        diff = left[row["date"]] - row["growth"]
        if abs(diff) > tolerance:
            problems.append({
                "date": row["date"],
                "stored_growth": left[row["date"]],
                "other_growth": row["growth"],
                "diff": diff,
            })
    return problems
