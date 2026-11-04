"""把 kind=otc_nav 且最后日期恰为 2015-12-31 的基金净值续到 2026-09-30。

只追加。不改、不删已有行，不换代码，不算组合收益。
来源仍是 eastmoney_pingzhongdata，复权仍是 equity_return_compound。
2015-12-31 的单位净值必须与库内一致；复权净值在这一天对齐后，只写入更晚的日期。
"""
from __future__ import annotations

import csv
import hashlib
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
from src.v3.data.universe import containers as load_containers
from src.v3.engine.universe import is_qdii
from src.v4.data.adjust import compound_adjusted_nav
from src.v4.data.r1b_parse import parse_pingzhongdata
from src.v4.engine.carriers import (
    SUBSTITUTES, build_candidates, choose_path, prints_for, sse_calendar,
)
from src.v4.engine.pool import HK_SECTORS, US_SECTORS

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results" / "data" / "otc-backfill-2016"
SEAM = "2015-12-31"
END = "2026-09-30"
END_DAY = date(2026, 9, 30)
WINDOW_FROM = "2016-01-01"
SOURCE = "eastmoney_pingzhongdata"
METHOD = "equity_return_compound"
PING = "https://fund.eastmoney.com/pingzhongdata/{code}.js"
JBGK = "https://fundf10.eastmoney.com/jbgk_{code}.html"
HOME = "https://fund.eastmoney.com/{code}.html"
LSJZ = "https://api.fund.eastmoney.com/f10/lsjz"
NAV_PAGE = "https://fundf10.eastmoney.com/jjjz_{code}.html"
# 公布净值通常到小数点后 4 位。
NAV_TOL = 1e-4
# 接缝复权净值：相对差不超过这个值就视为同一条链，按 1 倍接上。
EXACT_REL = 1e-8
# 超过这个相对差就拒绝续接，避免把另一条净值链硬接上来。
SCALE_REL = 1e-3
PAUSE = 0.12
SPOT_DATES = ("2016-06-30", "2020-12-31", "2026-09-30")
SPOT_PREFER = ("000942", "001469", "001133", "050025", "160416", "000071", "001180", "160213", "000614", "164906")

# 补数之前，只读载体路径对过 results/v5/report/otc-carrier-use-2016plus.csv。
# 截断日 = 当天没有成交价，且该载体价格序列的最后一天已经早于当天。
# 序列中间单独缺一天、但后面还有行情的，不算截断。
EXPECTED_USE = (
    ("allshare-financials-re", 2611, 2611, "otc:001469", "2016-01-04", "2026-09-30"),
    ("allshare-discretionary", 2611, 2611, "otc:001133", "2016-01-04", "2026-09-30"),
    ("allshare-it", 2611, 2611, "otc:000942", "2016-01-04", "2026-09-30"),
    ("theme-标普全球石油指数", 2410, 2611, "otc:160416", "2016-01-04", "2026-09-30"),
    ("allshare-healthcare", 2611, 2611, "otc:001180", "2016-01-04", "2026-09-30"),
    ("theme-中证海外中国互联网指数", 1924, 2516, "otc:164906", "2016-01-04", "2026-05-18"),
    ("theme-标普石油天然气勘探及生产精选行业指数", 293, 2442, "otc:162411", "2017-01-09", "2024-09-12"),
    ("theme-纳斯达克生物科技指数", 1959, 1959, "otc:001092", "2016-01-04", "2024-06-17"),
    ("theme-法兰克福DAX指数", 1839, 1839, "otc:000614", "2016-01-04", "2023-12-27"),
    ("spx", 764, 764, "otc:050025", "2016-01-04", "2021-11-23"),
    ("ndx100", 671, 671, "otc:160213", "2016-01-04", "2019-12-18"),
    ("hsi", 333, 333, "otc:000071", "2016-01-04", "2019-07-01"),
    ("gold", 14, 14, "otc:000216", "2016-01-04", "2019-07-01"),
    ("chinext", 11, 11, "otc:050021", "2019-01-09", "2019-07-01"),
    ("theme-恒生中国企业指数", 11, 11, "otc:160717", "2019-01-09", "2019-07-01"),
    ("csi300", 11, 0, "otc:050002", "2019-01-09", "2019-07-01"),
    ("csi500", 11, 0, "otc:160119", "2019-01-09", "2019-07-01"),
    ("csi-dividend", 1440, 0, "otc:090010", "2016-01-04", "2022-01-07"),
)

_NAME = re.compile(r'var\s+fS_name\s*=\s*"([^"]*)"')
_CODE = re.compile(r'var\s+fS_code\s*=\s*"([^"]*)"')
_TAG = re.compile(r"<[^>]+>")
_CELL = r"{label}</th>\s*<td[^>]*>\s*([^<]+)"


class BackfillError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds")


def _rel(left: float, right: float) -> float:
    if left == 0:
        return abs(right)
    return abs(left - right) / abs(left)


def _nav_ok(stored, fresh) -> bool:
    if stored is None or fresh is None:
        return stored is None and fresh is None
    return abs(float(stored) - float(fresh)) <= NAV_TOL


def plan_continuation(stored: list[dict], fresh: list[dict]) -> dict:
    """决定要追加的行。stored 至少含接缝日。fresh 是整段重算，可以长过 END。

    返回的 rows 只有严格晚于接缝、且不晚于 END 的日期。接缝日本身不返回。
    """
    seam = next((row for row in stored if row["date"] == SEAM), None)
    if seam is None or seam.get("close") is None or not (float(seam["close"]) > 0):
        return _empty("seam_missing", "库内没有 2015-12-31 的正复权净值")
    fresh_seam = next((row for row in fresh if row["date"] == SEAM), None)
    if fresh_seam is None or fresh_seam.get("close") is None or not (float(fresh_seam["close"]) > 0):
        return _empty("seam_missing", "新抓到的净值里没有 2015-12-31")
    if fresh_seam.get("unit_nav") is None or not _nav_ok(seam.get("unit_nav"), fresh_seam.get("unit_nav")):
        return _empty(
            "seam_refuse",
            f"接缝单位净值不一致：库内 {seam.get('unit_nav')}，页面 {fresh_seam.get('unit_nav')}",
            seam_close_db=float(seam["close"]), seam_close_fresh=float(fresh_seam["close"]))
    if not _nav_ok(seam.get("accum_nav"), fresh_seam.get("accum_nav")):
        return _empty(
            "seam_refuse",
            f"接缝累计净值不一致：库内 {seam.get('accum_nav')}，页面 {fresh_seam.get('accum_nav')}",
            seam_close_db=float(seam["close"]), seam_close_fresh=float(fresh_seam["close"]))
    stored_close = float(seam["close"])
    fresh_close = float(fresh_seam["close"])
    rel = _rel(stored_close, fresh_close)
    if rel <= EXACT_REL:
        scale = 1.0
        how = "exact"
    elif rel <= SCALE_REL:
        scale = stored_close / fresh_close
        how = "scaled"
    else:
        return _empty(
            "seam_refuse",
            f"接缝复权净值相对差 {rel:.6g}，超过 {SCALE_REL}，不续接",
            seam_close_db=stored_close, seam_close_fresh=fresh_close)
    by_fresh = {row["date"]: row for row in fresh}
    worst = 0.0
    worst_day = ""
    missing = 0
    for row in stored:
        if row["date"] > SEAM or row.get("close") is None or not (float(row["close"]) > 0):
            continue
        got = by_fresh.get(row["date"])
        if got is None or got.get("close") is None or not (float(got["close"]) > 0):
            missing += 1
            continue
        gap = _rel(float(row["close"]), float(got["close"]) * scale)
        if gap > worst:
            worst = gap
            worst_day = row["date"]
    rows = []
    for row in fresh:
        if row["date"] <= SEAM or row["date"] > END:
            continue
        if row.get("close") is None or not (float(row["close"]) > 0):
            continue
        rows.append({
            "date": row["date"],
            "close": float(row["close"]) * scale,
            "unit_nav": None if row.get("unit_nav") is None else float(row["unit_nav"]),
            "accum_nav": None if row.get("accum_nav") is None else float(row["accum_nav"]),
        })
    rows.sort(key=lambda item: item["date"])
    return {
        "status": how,
        "scale": scale,
        "rows": rows,
        "reason": "" if how == "exact" else f"接缝复权净值相对差 {rel:.6g}，后段按 {scale:.10g} 倍对齐到库内收盘",
        "seam_close_db": stored_close,
        "seam_close_fresh": fresh_close,
        "seam_unit_db": None if seam.get("unit_nav") is None else float(seam["unit_nav"]),
        "seam_unit_fresh": float(fresh_seam["unit_nav"]),
        "overlap_max_rel": worst,
        "overlap_worst_day": worst_day,
        "overlap_missing": missing,
    }


def _empty(status: str, reason: str, **extra) -> dict:
    base = {
        "status": status, "scale": None, "rows": [], "reason": reason,
        "seam_close_db": None, "seam_close_fresh": None,
        "seam_unit_db": None, "seam_unit_fresh": None,
        "overlap_max_rel": None, "overlap_worst_day": "", "overlap_missing": None,
    }
    base.update(extra)
    return base


def truncated_codes(con: sqlite3.Connection) -> list[str]:
    rows = con.execute(
        """SELECT code FROM v4_series WHERE kind='otc_nav'
           GROUP BY code HAVING MAX(date)=? ORDER BY code""",
        (SEAM,)).fetchall()
    return [row[0] for row in rows]


def _listing(con: sqlite3.Connection, code: str) -> sqlite3.Row | None:
    return con.execute(
        "SELECT name, maps_to, tracked_index, inception, enhanced, note FROM v4_listing WHERE code=?",
        (code,)).fetchone()


def _stored(con: sqlite3.Connection, code: str) -> list[dict]:
    rows = con.execute(
        """SELECT date, close, unit_nav, accum_nav FROM v4_series
           WHERE code=? AND kind='otc_nav' ORDER BY date""",
        (code,)).fetchall()
    return [{"date": row[0], "close": row[1], "unit_nav": row[2], "accum_nav": row[3]} for row in rows]


def fetch_ping(code: str) -> dict:
    url = PING.format(code=code)
    body = http.get(url, headers={"Referer": HOME.format(code=code)}, timeout=60)
    text = body.decode("utf-8-sig", "replace")
    name = _NAME.search(text)
    page_code = _CODE.search(text)
    points = parse_pingzhongdata(text, END_DAY)
    nav = compound_adjusted_nav(points)
    return {
        "url": url,
        "sha256": hashlib.sha256(body).hexdigest(),
        "page_name": name.group(1).strip() if name else "",
        "page_code": page_code.group(1).strip() if page_code else "",
        "nav": nav,
    }


def _cell(html: str, label: str) -> str:
    match = re.search(_CELL.format(label=re.escape(label)), html)
    if not match:
        return ""
    return _TAG.sub("", match.group(1)).strip()


def explain_short(code: str, last: str) -> str:
    """净值没有接到 END 时，只记录页面上的原因，不另找一只基金代替。"""
    bits = [f"公布净值停在 {last}，没有接到 {END}"]
    try:
        page = JBGK.format(code=code)
        html = http.get(page, headers={"Referer": "https://fundf10.eastmoney.com/"}, timeout=30).decode("utf-8", "replace")
        status = _cell(html, "基金状态") or _cell(html, "运作方式")
        full = _cell(html, "基金全称") or _cell(html, "基金简称")
        if status:
            bits.append(f"概况页状态：{status}")
        if full:
            bits.append(f"概况页名称：{full}")
        bits.append(page)
    except (http.FetchError, ValueError) as exc:
        bits.append(f"概况页读取失败：{exc}")
    try:
        home = HOME.format(code=code)
        text = http.get(home, headers={"Referer": "https://fund.eastmoney.com/"}, timeout=30).decode("utf-8", "replace")
        if any(word in text for word in ("已终止", "终止", "清盘", "已清盘")):
            bits.append("主页出现终止或清盘字样")
        bits.append(home)
    except (http.FetchError, ValueError) as exc:
        bits.append(f"主页读取失败：{exc}")
    bits.append("不更换代码，不用其他基金填这段缺口")
    return "；".join(bits)


def _guard(con: sqlite3.Connection, codes: list[str]) -> dict:
    marks = ",".join("?" * len(codes))
    pre = con.execute(
        f"""SELECT code, date, close, unit_nav, accum_nav, source, method
            FROM v4_series WHERE kind='otc_nav' AND date<=? ORDER BY code, date""",
        (SEAM,)).fetchall()
    digest = hashlib.sha256()
    for row in pre:
        digest.update(repr(tuple(row)).encode())
        digest.update(b"\n")
    return {
        "pre_rows": len(pre),
        "pre_sha256": digest.hexdigest(),
        "other_kinds": con.execute("SELECT COUNT(*) FROM v4_series WHERE kind!='otc_nav'").fetchone()[0],
        "other_otc": con.execute(
            f"SELECT COUNT(*) FROM v4_series WHERE kind='otc_nav' AND code NOT IN ({marks})",
            codes).fetchone()[0],
        "target_pre": con.execute(
            f"SELECT COUNT(*) FROM v4_series WHERE kind='otc_nav' AND date<=? AND code IN ({marks})",
            (SEAM, *codes)).fetchone()[0],
        "bars": con.execute("SELECT COUNT(*) FROM bars").fetchone()[0],
        "fund_nav": con.execute("SELECT COUNT(*) FROM fund_nav").fetchone()[0],
        "listing": con.execute("SELECT COUNT(*) FROM v4_listing").fetchone()[0],
    }


def _insert(con: sqlite3.Connection, code: str, rows: list[dict], url: str, fetched_at: str) -> int:
    con.executemany(
        """INSERT INTO v4_series
           (code, kind, date, open, high, low, close, volume, unit_nav, accum_nav, filled,
            source, source_url, method, fetched_at)
           VALUES (?, 'otc_nav', ?, NULL, NULL, NULL, ?, NULL, ?, ?, 0, ?, ?, ?, ?)""",
        [(code, row["date"], row["close"], row["unit_nav"], row["accum_nav"],
          SOURCE, url, METHOD, fetched_at) for row in rows])
    return len(rows)


def _main_containers() -> list[dict]:
    return [
        row for row in load_containers()
        if row.get("arm") in {None, "main"} and row.get("asset_class") != "现金"
    ]


def _ended(series: pd.Series | None, day: pd.Timestamp, vehicle: str) -> bool:
    """当天没有用到的价格，并且序列最后一天已经早于当天。"""
    if series is None or len(series) == 0:
        return True
    ordered = series.dropna().sort_index()
    if ordered.empty:
        return True
    stamp = pd.Timestamp(day)
    last = pd.Timestamp(ordered.index.max())
    if vehicle == "spdr":
        known = ordered[ordered.index < stamp]
        return known.empty and last < stamp
    if stamp in ordered.index:
        return False
    return last < stamp


def carrier_use(con: sqlite3.Connection) -> list[dict]:
    """2016 年起每个容器用场外载体的天数。只读选择路径，不算组合收益。"""
    containers = _main_containers()
    calendar = sse_calendar(con, END)
    if len(calendar) == 0 or str(calendar[calendar >= WINDOW_FROM][0].date()) != "2016-01-04":
        raise BackfillError("上交所日历的 2016 首个交易日不是 2016-01-04")
    window = calendar[calendar >= WINDOW_FROM]
    if len(window) != 2611:
        raise BackfillError(f"2016-01-01 至 {END} 的交易日应是 2611，实际 {len(window)}")
    grouped = build_candidates(con, containers, calendar, END)
    prints = prints_for(con, grouped, END)
    found = []
    for container in containers:
        identity = str(container.get("id") or "")
        path = choose_path(grouped.get(identity) or [], calendar)
        otc_days = []
        trunc = 0
        for day, choice in zip(calendar, path):
            if day < pd.Timestamp(WINDOW_FROM):
                continue
            if choice is not None and _ended(prints.get(choice.code), day, choice.vehicle):
                trunc += 1
            if choice is not None and choice.vehicle == "otc":
                otc_days.append((str(day.date()), choice.label, choice.code))
        if not otc_days:
            continue
        labels: dict[str, list[str]] = {}
        for day, label, code in otc_days:
            labels.setdefault(label, []).append(day)
        label = max(labels, key=lambda key: (len(labels[key]), key))
        days = labels[label]
        found.append({
            "container": identity,
            "otc_days": len(otc_days),
            "trunc_days": trunc,
            "otc_carrier": label,
            "from": days[0],
            "to": days[-1],
        })
    found.sort(key=lambda row: (-row["otc_days"], -row["trunc_days"], row["container"]))
    return found


def use_matches_expected(rows: list[dict]) -> list[str]:
    got = {
        row["container"]: (
            row["container"], row["otc_days"], row["trunc_days"], row["otc_carrier"], row["from"], row["to"])
        for row in rows
    }
    problems = []
    for item in EXPECTED_USE:
        if got.get(item[0]) != item:
            problems.append(f"{item[0]} 期望 {item} 实际 {got.get(item[0])}")
    extra = sorted(set(got) - {item[0] for item in EXPECTED_USE})
    for name in extra:
        problems.append(f"多出容器 {name} {got[name]}")
    return problems


def _names(con: sqlite3.Connection) -> dict[str, str]:
    found = {row[0]: row[1] for row in con.execute("SELECT code, name FROM v4_listing")}
    for container in load_containers():
        for row in container.get("execution") or []:
            code = str(row.get("code") or "")
            if code and code not in found:
                found[code] = str(row.get("name") or "")
    return found


def _carrier_sets() -> tuple[set[str], set[str], dict[str, str]]:
    listed: set[str] = set()
    qdii: set[str] = set()
    home: dict[str, str] = {}
    for container in load_containers():
        if container.get("asset_class") == "现金":
            continue
        identity = str(container.get("id") or "")
        flag = is_qdii(container)
        for row in container.get("execution") or []:
            code = str(row.get("code") or "")
            if code in {"", "取不到", "TBD"}:
                continue
            listed.add(code)
            home.setdefault(code, identity)
            if flag:
                qdii.add(code)
    for identity, code in (*US_SECTORS, *HK_SECTORS):
        listed.add(code)
        home.setdefault(code, identity)
    for row in SUBSTITUTES:
        if row["vehicle"] == "etf":
            listed.add(row["code"])
            home.setdefault(row["code"], row["container"])
    return listed, qdii, home


def stale_carriers(con: sqlite3.Connection) -> list[dict]:
    """场内、场外、QDII 载体序列里，最后一天早于 2026-09-30 的全部列出来。"""
    names = _names(con)
    listed, qdii, home = _carrier_sets()
    otc_home = {
        row[0]: row[1]
        for row in con.execute("SELECT code, maps_to FROM v4_listing")
    }
    rows = []

    def add(vehicle: str, code: str, store: str, kind: str, first, last, count: int) -> None:
        if last is None or last >= END:
            return
        rows.append({
            "vehicle_class": vehicle,
            "code": code,
            "name": names.get(code, ""),
            "container": otc_home.get(code, "") if vehicle == "OTC" else home.get(code, ""),
            "store": store,
            "kind": kind,
            "first_date": first or "",
            "last_date": last,
            "rows": count,
            "note": f"最后日期早于 {END}",
        })

    for code, first, last, count in con.execute(
            """SELECT code, MIN(date), MAX(date), COUNT(*) FROM v4_series
               WHERE kind='otc_nav' GROUP BY code"""):
        add("OTC", code, "v4_series", "otc_nav", first, last, count)
    listed_codes = listed
    for code, kind, first, last, count in con.execute(
            """SELECT code, kind, MIN(date), MAX(date), COUNT(*) FROM v4_series
               WHERE kind IN ('backward', 'backward_rebuild') GROUP BY code, kind"""):
        if code not in listed_codes:
            continue
        add("listed", code, "v4_series", kind, first, last, count)
    for code, first, last, count in con.execute(
            """SELECT code, MIN(date), MAX(date), COUNT(*) FROM bars
               WHERE adj='raw' AND close>0 GROUP BY code"""):
        if code not in listed_codes:
            continue
        add("listed", code, "bars", "raw", first, last, count)
    for code, first, last, count in con.execute(
            """SELECT code, MIN(date), MAX(date), COUNT(*) FROM fund_nav
               WHERE unit_nav>0 GROUP BY code"""):
        if code not in qdii:
            continue
        add("QDII", code, "fund_nav", "unit_nav", first, last, count)
    covered = {row["code"] for row in rows}
    present = set()
    for code, in con.execute("SELECT DISTINCT code FROM bars"):
        present.add(code)
    for code, in con.execute("SELECT DISTINCT code FROM v4_series"):
        present.add(code)
    for code, in con.execute("SELECT DISTINCT code FROM fund_nav"):
        present.add(code)
    for code in sorted(listed | qdii):
        if code in covered or code in present:
            continue
        vehicle = "QDII" if code in qdii else "listed"
        rows.append({
            "vehicle_class": vehicle,
            "code": code,
            "name": names.get(code, ""),
            "container": home.get(code, ""),
            "store": "",
            "kind": "",
            "first_date": "",
            "last_date": "",
            "rows": 0,
            "note": "登记为载体，库内没有行情，所以没有最后日期",
        })
    rows.sort(key=lambda row: (row["vehicle_class"], row["last_date"], row["code"], row["kind"]))
    return rows


def _on_or_before(days: list[str], target: str) -> str:
    earlier = [day for day in days if day <= target]
    if not earlier:
        return ""
    return earlier[-1]


def _num(value):
    if value in (None, "", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _lsjz_one(code: str, day: str) -> dict | None:
    """天天基金历史净值表的一天。pageSize 实际最大 20，按单日查询。"""
    raw = http.get(LSJZ, {
        "fundCode": code, "pageIndex": "1", "pageSize": "20",
        "startDate": day, "endDate": day,
    }, headers={"Referer": "https://fundf10.eastmoney.com/"}, timeout=40)
    payload = json.loads(raw.decode("utf-8", "replace"))
    if payload.get("ErrCode") not in (0, "0", None):
        raise http.FetchError(f"lsjz {code} {day}: {payload.get('ErrMsg')}")
    for item in ((payload.get("Data") or {}).get("LSJZList") or []):
        if str(item.get("FSRQ") or "") != day:
            continue
        growth = item.get("JZZZL")
        return {
            "date": day,
            "unit_nav": _num(item.get("DWJZ")),
            "accum_nav": _num(item.get("LJJZ")),
            "equity_return": _num(growth) if growth not in (None, "", "--") else None,
        }
    return None


def spotcheck_rows(con: sqlite3.Connection, codes: list[str] | None = None) -> list[dict]:
    """5 只基金、各 3 个日子。页面复权净值 = 库内前一公布日复权净值 ×（1 + 页面日增长率）。

    日增长率来自天天基金历史净值表，不是 pingzhongdata 再读一遍。
    """
    if codes is None:
        reached = [
            row[0] for row in con.execute(
                """SELECT code FROM v4_series WHERE kind='otc_nav'
                   GROUP BY code HAVING MAX(date)=? ORDER BY code""",
                (END,))
        ]
        codes = [code for code in SPOT_PREFER if code in set(reached)][:5]
    if len(codes) < 5:
        raise BackfillError(f"接到 {END} 的基金不足 5 只，无法抽查")
    rows = []
    for code in codes:
        stored = {row["date"]: row for row in _stored(con, code)}
        order = sorted(stored)
        home = HOME.format(code=code)
        nav_page = NAV_PAGE.format(code=code)
        for target in SPOT_DATES:
            day = target if target in stored else _on_or_before(order, target)
            pub = _lsjz_one(code, day) if day else None
            pub = pub or {}
            db_close = None if day not in stored else stored[day]["close"]
            prev_close = None
            db_return = None
            if day in order:
                pos = order.index(day)
                if pos > 0 and stored[order[pos - 1]].get("close"):
                    prev_close = float(stored[order[pos - 1]]["close"])
                    if db_close not in (None, 0):
                        db_return = float(db_close) / prev_close - 1.0
            page_close = None
            growth = pub.get("equity_return")
            if prev_close is not None and growth is not None:
                page_close = prev_close * (1.0 + float(growth) / 100.0)
            rel = None
            if db_close not in (None, 0) and page_close not in (None, 0):
                rel = _rel(float(db_close), float(page_close))
            rows.append({
                "code": code,
                "target_date": target,
                "date": day,
                "db_adjusted_nav": db_close,
                "page_adjusted_nav": page_close,
                "adjusted_rel_diff": rel,
                "db_daily_return": db_return,
                "db_unit_nav": None if day not in stored else stored[day]["unit_nav"],
                "page_unit_nav": pub.get("unit_nav"),
                "db_accum_nav": None if day not in stored else stored[day]["accum_nav"],
                "page_accum_nav": pub.get("accum_nav"),
                "page_daily_growth_pct": growth,
                "fund_url": home,
                "nav_url": nav_page,
                "lsjz_url": f"{LSJZ}?fundCode={code}&pageIndex=1&pageSize=20&startDate={day}&endDate={day}",
            })
            time.sleep(0.05)
        time.sleep(PAUSE)
    return rows


def _write_csv(path: Path, rows: list[dict], columns: list[str]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in columns})
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fmt(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, float):
        return format(value, ".10g")
    return str(value)


_SPOT_COLUMNS = [
    "code", "target_date", "date", "db_adjusted_nav", "page_adjusted_nav", "adjusted_rel_diff",
    "db_daily_return", "db_unit_nav", "page_unit_nav", "db_accum_nav", "page_accum_nav",
    "page_daily_growth_pct", "fund_url", "nav_url", "lsjz_url",
]
_SPOT_NUMS = (
    "db_adjusted_nav", "page_adjusted_nav", "adjusted_rel_diff", "db_daily_return",
    "db_unit_nav", "page_unit_nav", "db_accum_nav", "page_accum_nav", "page_daily_growth_pct",
)


def _format_spots(rows: list[dict]) -> None:
    for row in rows:
        for key in _SPOT_NUMS:
            row[key] = _fmt(row.get(key))


def refresh_spotcheck() -> str:
    """只重写抽查表。不打开写库。"""
    con = DB.connect(DB.MARKET_DB, readonly=True)
    try:
        spots = spotcheck_rows(con)
    finally:
        con.close()
    _format_spots(spots)
    digest = _write_csv(OUT / "spotcheck.csv", spots, _SPOT_COLUMNS)
    path = OUT / "summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary["spotcheck_sha256"] = digest
    summary["spot_codes"] = list(dict.fromkeys(row["code"] for row in spots))
    summary["spot_error"] = ""
    summary["spot_method"] = (
        "天天基金历史净值表按单日查询。页面复权净值 = 库内上一公布日复权净值 × (1 + 日增长率/100)。"
        "单位净值、累计净值直接对照表内数字。"
    )
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"spotcheck_sha256": digest, "rows": len(spots)}, ensure_ascii=False), flush=True)
    return digest


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    http.LOG.clear()
    con = DB.connect(DB.MARKET_DB)
    try:
        before_sha = DB.sha256_file(DB.MARKET_DB)
        before_bytes = DB.MARKET_DB.stat().st_size
        before_use = carrier_use(con)
        problems = use_matches_expected(before_use)
        if problems:
            raise BackfillError("补数前的场外使用天数与已公布清单不一致：\n" + "\n".join(problems))
        codes = truncated_codes(con)
        if not codes:
            raise BackfillError("没有 kind=otc_nav 且最后日期为 2015-12-31 的基金")
        before_guard = _guard(con, codes)
        plans = []
        for index, code in enumerate(codes, start=1):
            listing = _listing(con, code)
            stored = _stored(con, code)
            base = {
                "code": code,
                "name": "" if listing is None else listing["name"],
                "maps_to": "" if listing is None else listing["maps_to"],
                "tracked_index": "" if listing is None else listing["tracked_index"],
                "enhanced": "" if listing is None else int(listing["enhanced"] or 0),
                "first_date": stored[0]["date"] if stored else "",
                "page_name": "",
                "page_code": "",
                "source": SOURCE,
                "source_url": PING.format(code=code),
                "method": METHOD,
                "response_sha256": "",
            }
            try:
                fetched = fetch_ping(code)
            except (http.FetchError, ValueError) as exc:
                plans.append({**base, **_empty("fetch_fail", f"pingzhongdata 读取失败：{exc}") , "inserted": 0})
                print(f"[{index}/{len(codes)}] {code} FETCH FAIL", flush=True)
                time.sleep(PAUSE)
                continue
            base["page_name"] = fetched["page_name"]
            base["page_code"] = fetched["page_code"]
            base["response_sha256"] = fetched["sha256"]
            if fetched["page_code"] and fetched["page_code"] != code:
                plans.append({
                    **base,
                    **_empty("seam_refuse", f"页面代码是 {fetched['page_code']}，不是 {code}，不改用别的代码"),
                    "inserted": 0,
                })
                print(f"[{index}/{len(codes)}] {code} CODE MISMATCH", flush=True)
                time.sleep(PAUSE)
                continue
            plan = plan_continuation(stored, fetched["nav"])
            plan["inserted"] = 0
            plans.append({**base, **plan, "nav_last": fetched["nav"][-1]["date"] if fetched["nav"] else ""})
            print(f"[{index}/{len(codes)}] {code} {plan['status']} rows={len(plan['rows'])}", flush=True)
            time.sleep(PAUSE)
        for plan in plans:
            if plan["status"] in {"exact", "scaled"} and not plan["rows"]:
                last = plan.get("nav_last") or SEAM
                plan["status"] = "short"
                plan["reason"] = explain_short(plan["code"], last)
            elif plan["status"] in {"exact", "scaled"} and plan["rows"][-1]["date"] < END:
                plan["reason"] = "；".join(
                    bit for bit in (plan["reason"], explain_short(plan["code"], plan["rows"][-1]["date"])) if bit)
                if any(word in plan["reason"] for word in ("终止", "清盘")):
                    plan["status"] = "liquidated"
                else:
                    plan["status"] = "short"
            elif plan["status"] in {"exact", "scaled"} and plan["rows"][-1]["date"] == END:
                how = "接缝复权净值与库内一致" if plan["status"] == "exact" else plan["reason"]
                plan["status"] = "extended"
                plan["reason"] = (
                    f"{how}。净值接到 {END}。页面简称「{plan.get('page_name') or ''}」。"
                    "同一代码续接，不更换基金。"
                )
        spot_error = ""
        fetched_at = _now()
        inserted_total = 0
        with con:
            cur = con.execute(
                """INSERT INTO runs (kind, started_at, end_date, args, git_commit, universe_sha256, status)
                   VALUES ('backfill', ?, ?, ?, ?, ?, 'running')""",
                (_now(), END, json.dumps({
                    "job": "otc-nav-backfill-2016",
                    "portfolio_returns": False,
                    "append_only": True,
                    "source": SOURCE,
                    "method": METHOD,
                    "seam": SEAM,
                }, ensure_ascii=False), DB.git_head(), None))
            run_id = cur.lastrowid
            for plan in plans:
                if plan["status"] not in {"extended", "short", "liquidated"} or not plan["rows"]:
                    continue
                have = con.execute(
                    "SELECT MAX(date) FROM v4_series WHERE code=? AND kind='otc_nav'",
                    (plan["code"],)).fetchone()[0]
                if have != SEAM:
                    raise BackfillError(f"{plan['code']} 最后日期已是 {have}，拒绝再写")
                plan["inserted"] = _insert(con, plan["code"], plan["rows"], plan["source_url"], fetched_at)
                inserted_total += plan["inserted"]
            after_guard = _guard(con, codes)
            for key in ("pre_rows", "pre_sha256", "other_kinds", "other_otc", "target_pre", "bars", "fund_nav", "listing"):
                if after_guard[key] != before_guard[key]:
                    raise BackfillError(f"已有数据被改动：{key} {before_guard[key]} -> {after_guard[key]}")
            series_after = con.execute("SELECT COUNT(*) FROM v4_series").fetchone()[0]
            series_before = series_after - inserted_total
            if con.execute(
                    "SELECT COUNT(*) FROM v4_series WHERE kind='otc_nav' AND date>? AND code IN ({})".format(
                        ",".join("?" * len(codes))),
                    (SEAM, *codes)).fetchone()[0] != inserted_total:
                raise BackfillError("追加行数与目标基金的新日期行数不一致")
            con.executemany(
                """INSERT INTO requests (run_id, seq, url, fetched_at, bytes, sha256, error, file)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [(run_id, i, item.get("url"), item.get("fetched_at"), item.get("bytes"),
                  item.get("sha256"), item.get("error"), item.get("file"))
                 for i, item in enumerate(http.LOG)])
            con.execute(
                "UPDATE runs SET finished_at=?, status='ok' WHERE run_id=?",
                (_now(), run_id))
        for plan in plans:
            span = con.execute(
                "SELECT MIN(date), MAX(date), COUNT(*) FROM v4_series WHERE code=? AND kind='otc_nav'",
                (plan["code"],)).fetchone()
            plan["final_date"] = span[1]
            plan["final_rows"] = span[2]
            seam_close = con.execute(
                "SELECT close FROM v4_series WHERE code=? AND kind='otc_nav' AND date=?",
                (plan["code"], SEAM)).fetchone()
            plan["seam_close_after"] = None if seam_close is None else seam_close[0]
            if plan.get("seam_close_db") is not None and plan["seam_close_after"] != plan["seam_close_db"]:
                raise BackfillError(f"{plan['code']} 接缝收盘被改写")
        try:
            spots = spotcheck_rows(con)
        except (http.FetchError, ValueError, BackfillError, json.JSONDecodeError) as exc:
            spots = []
            spot_error = str(exc)
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        after_use = carrier_use(con)
        stale = stale_carriers(con)
    finally:
        con.close()
    for suffix in ("-wal", "-shm", "-journal"):
        leftover = Path(str(DB.MARKET_DB) + suffix)
        if leftover.exists():
            raise BackfillError(f"库文件旁还有 {leftover.name}")
    after_sha = DB.sha256_file(DB.MARKET_DB)
    after_bytes = DB.MARKET_DB.stat().st_size
    roster_columns = [
        "code", "name", "page_name", "maps_to", "tracked_index", "enhanced", "first_date",
        "status", "inserted", "final_date", "final_rows", "reaches_end", "reason",
        "seam_close_db", "seam_close_fresh", "seam_close_after", "scale",
        "seam_unit_db", "seam_unit_fresh", "overlap_max_rel", "overlap_worst_day", "overlap_missing",
        "source", "source_url", "method", "response_sha256",
    ]
    roster = []
    for plan in plans:
        roster.append({
            **plan,
            "reaches_end": "yes" if plan.get("final_date") == END else "no",
            "seam_close_db": _fmt(plan.get("seam_close_db")),
            "seam_close_fresh": _fmt(plan.get("seam_close_fresh")),
            "seam_close_after": _fmt(plan.get("seam_close_after")),
            "scale": _fmt(plan.get("scale")),
            "seam_unit_db": _fmt(plan.get("seam_unit_db")),
            "seam_unit_fresh": _fmt(plan.get("seam_unit_fresh")),
            "overlap_max_rel": _fmt(plan.get("overlap_max_rel")),
            "overlap_missing": "" if plan.get("overlap_missing") is None else plan.get("overlap_missing"),
        })
    use_columns = ["container", "otc_days", "trunc_days", "otc_carrier", "from", "to"]
    stale_columns = [
        "vehicle_class", "code", "name", "container", "store", "kind",
        "first_date", "last_date", "rows", "note",
    ]
    _format_spots(spots)
    roster_sha = _write_csv(OUT / "roster.csv", roster, roster_columns)
    _write_csv(OUT / "otc-carrier-use-2016plus-before.csv", before_use, use_columns)
    _write_csv(OUT / "otc-carrier-use-2016plus.csv", after_use, use_columns)
    stale_sha = _write_csv(OUT / "stale-carriers.csv", stale, stale_columns)
    spot_sha = _write_csv(OUT / "spotcheck.csv", spots, _SPOT_COLUMNS)
    by_status: dict[str, int] = {}
    for plan in plans:
        by_status[plan["status"]] = by_status.get(plan["status"], 0) + 1
    summary = {
        "job": "otc-nav-backfill-2016",
        "seam": SEAM,
        "end": END,
        "source": SOURCE,
        "method": METHOD,
        "portfolio_returns": False,
        "append_only": True,
        "funds": len(codes),
        "expected_about": 57,
        "count_note": (
            "kind=otc_nav 且 MAX(date)=2015-12-31 的代码是 "
            f"{len(codes)} 只。其中 6 只 LOF 同时有场内 bars 接到 {END}："
            "160416、160717、161831、162411、164705、164906。"
            "这 6 只的场外净值序列仍然停在接缝日，所以一并续接。63-6=57。"
        ),
        "by_status": by_status,
        "reached_end": sum(1 for plan in plans if plan.get("final_date") == END),
        "inserted_rows": inserted_total,
        "v4_series_before": series_before,
        "v4_series_after": series_after,
        "before_sha256": before_sha,
        "before_bytes": before_bytes,
        "sha256": after_sha,
        "bytes": after_bytes,
        "integrity": integrity,
        "pre_otc_sha256": before_guard["pre_sha256"],
        "pre_otc_rows": before_guard["pre_rows"],
        "run_id": run_id,
        "roster_sha256": roster_sha,
        "stale_sha256": stale_sha,
        "spotcheck_sha256": spot_sha,
        "stale_rows": len(stale),
        "carrier_use_before": before_use,
        "carrier_use_after": after_use,
        "spot_codes": list(dict.fromkeys(row["code"] for row in spots)),
        "spot_error": spot_error,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "SHA256.txt").write_text(
        f"before {before_sha} {before_bytes}\nafter  {after_sha} {after_bytes}\nintegrity {integrity}\n",
        encoding="utf-8")
    print(json.dumps({
        "funds": len(codes),
        "inserted_rows": inserted_total,
        "reached_end": summary["reached_end"],
        "by_status": by_status,
        "sha256": after_sha,
        "integrity": integrity,
    }, ensure_ascii=False, indent=2), flush=True)
    return summary


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "spotcheck":
        refresh_spotcheck()
    else:
        run()
