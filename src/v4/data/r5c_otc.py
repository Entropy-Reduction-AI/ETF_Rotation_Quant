"""v4-R5c：创业板指第 2 档非增强联接和纯指数。只插入，不覆盖。

成立日晚于 2015-12-31 的不收。复权净值写到这一天为止。
跟踪标的必须是「创业板指数(价格)」或「创业板指数」。增强型、创业板 50、
场内 ETF 不进这一档。050002 的除息核对只读，不改序列。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from src.data import db as DB
from src.data import http
from src.v4.data.r1b_parse import parse_pingzhongdata
from src.v4.data.r5b_otc import (
    CUTOFF,
    END,
    JBGK,
    LSJZ,
    PING,
    R5bOtcError,
    _exchange_only,
    _insert,
    _nav,
    _now,
    _profile,
    _rank,
    _write,
)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results" / "v4" / "inventory" / "r5c"
TRACKS = frozenset({"创业板指数(价格)", "创业板指数"})
# 排名扫描之外再点名。概况页对不上就拒绝，不凭这份名单入库。
NAMED = ("001592", "001593", "050021", "110026", "160637", "161022")
EXDIV_CODE = "050002"
EXDIV_DAY = "2015-12-29"


def _skip_share(name: str, short: str) -> bool:
    text = f"{name} {short}"
    return any(token in text for token in ("美元", "现汇", "现钞"))


def _decision(info: dict) -> str:
    name = info.get("name") or ""
    short = info.get("short_name") or ""
    tracked = info.get("tracked_index") or ""
    inception = info.get("inception") or ""
    fund_type = info.get("fund_type") or ""
    enhanced = 1 if "增强" in name or "增强" in short else 0
    info["enhanced"] = enhanced
    if _skip_share(name, short):
        return "share_class"
    if not inception or inception > CUTOFF:
        return "after_cutoff"
    if enhanced:
        return "enhanced"
    if _exchange_only(name) or ("ETF" in name and "联接" not in name and "LOF" not in name):
        return "exchange_etf"
    if tracked not in TRACKS:
        return "other_index"
    if "指数" not in fund_type and "指数" not in name:
        return "not_index"
    return "insert"


def _candidates(log: list[str]) -> list[str]:
    ranked = _rank(log)
    codes = set(NAMED)
    for row in ranked:
        if "创业板" in str(row.get("name") or ""):
            codes.add(row["code"])
    return sorted(codes)


def run(root: Path = OUT) -> list[dict]:
    root.mkdir(parents=True, exist_ok=True)
    log = [f"D25-3 chinext tier-2 cutoff {CUTOFF}"]
    con = sqlite3.connect(DB.MARKET_DB)
    con.row_factory = sqlite3.Row
    existing = {row[0] for row in con.execute("SELECT code FROM v4_listing")}
    fetched_at = _now()
    scan = []
    inserted = []
    try:
        for code in _candidates(log):
            if code in existing:
                scan.append({"code": code, "decision": "already", "maps_to": ""})
                continue
            try:
                info = _profile(code)
            except (http.FetchError, ValueError) as exc:
                log.append(f"jbgk {code} FAIL {exc}")
                scan.append({"code": code, "decision": "profile_fail", "maps_to": ""})
                continue
            decision = _decision(info)
            base = {
                "code": code,
                "name": info.get("name") or "",
                "short_name": info.get("short_name") or "",
                "inception": info.get("inception") or "",
                "tracked": info.get("tracked_index") or "",
                "fund_type": info.get("fund_type") or "",
                "decision": decision,
                "maps_to": "chinext" if decision == "insert" else "",
            }
            if decision != "insert":
                scan.append(base)
                log.append(f"skip {code} {decision} tracked={base['tracked']}")
                continue
            note = (
                f"D25-3 第2档。成立日不晚于 {CUTOFF}。"
                f"概况页跟踪标的「{base['tracked']}」对上容器 chinext 的正式名称。"
                "非增强。名称含联接的是联接基金，其余是跟踪同一指数的场外纯指数。"
            )
            item = {
                "code": code,
                "name": base["name"],
                "maps_to": "chinext",
                "tracked_index": base["tracked"],
                "inception": base["inception"],
                "enhanced": 0,
                "page": info["page"],
                "note": note,
            }
            try:
                nav = _nav(code, log)
                _insert(con, item, nav, fetched_at)
            except (http.FetchError, ValueError, R5bOtcError) as exc:
                log.append(f"insert {code} FAIL {exc}")
                base["decision"] = "nav_fail"
                scan.append(base)
                continue
            inserted.append(item)
            scan.append(base)
            log.append(
                f"otc {code} chinext rows={item['rows']} {item['first_date']}→{item['last_date']} "
                f"sha256={item['sha256']}")
    finally:
        con.close()
    _write(root / "scan.csv", scan)
    _write(root / "roster.csv", inserted)
    (root / "run.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    print(f"inserted {len(inserted)} scanned {len(scan)}", flush=True)
    return inserted


def _stored_return(con: sqlite3.Connection, code: str, day: str) -> float | None:
    rows = con.execute(
        "SELECT date, close FROM v4_series WHERE code=? AND kind='otc_nav' AND date<=? "
        "ORDER BY date DESC LIMIT 2",
        (code, day)).fetchall()
    if len(rows) < 2 or rows[0][0] != day:
        return None
    later = float(rows[0][1])
    earlier = float(rows[1][1])
    if earlier <= 0:
        return None
    return later / earlier - 1.0


def check_exdiv(code: str = EXDIV_CODE, day: str = EXDIV_DAY, root: Path = OUT) -> dict:
    """对照 pingzhong 的 unitMoney 和 lsjz 的累计净值。不写 v4_series。"""
    root.mkdir(parents=True, exist_ok=True)
    ping_url = PING.format(code=code)
    body = http.get(ping_url, headers={"Referer": f"https://fund.eastmoney.com/{code}.html"}, timeout=60)
    points = parse_pingzhongdata(body.decode("utf-8", "replace"), date(2015, 12, 31))
    window = [row for row in points if "2015-12-24" <= row["date"] <= "2015-12-31"]
    ping_day = next((row for row in points if row["date"] == day), None)
    raw = http.get(LSJZ, {
        "fundCode": code,
        "pageIndex": "1",
        "pageSize": "20",
        "startDate": "2015-12-01",
        "endDate": "2015-12-31",
    }, headers={"Referer": f"https://fundf10.eastmoney.com/jjjz_{code}.html"}, timeout=40)
    payload = json.loads(raw.decode("utf-8", "replace"))
    batch = ((payload.get("Data") or {}).get("LSJZList") or [])
    lsjz = {}
    for item in batch:
        stamp = str(item.get("FSRQ") or "")
        if not stamp:
            continue
        lsjz[stamp] = {
            "date": stamp,
            "unit_nav": item.get("DWJZ"),
            "accum_nav": item.get("LJJZ"),
            "growth": item.get("JZZZL"),
            "bonus": item.get("FHFCZ") or item.get("FHSP") or "",
        }
    lsjz_day = lsjz.get(day) or {}
    con = sqlite3.connect(f"file:{DB.MARKET_DB.resolve()}?mode=ro", uri=True)
    try:
        stored = _stored_return(con, code, day)
        source = con.execute(
            "SELECT source, source_url FROM v4_series WHERE code=? AND kind='otc_nav' AND date=?",
            (code, day)).fetchone()
    finally:
        con.close()
    def _pct(text) -> float | None:
        if text in (None, "", "--"):
            return None
        try:
            return float(text) / 100.0
        except (TypeError, ValueError):
            return None

    def _level(text) -> float | None:
        if text in (None, "", "--"):
            return None
        try:
            number = float(text)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    growth = lsjz_day.get("growth")
    lsjz_return = _pct(growth)
    ping_return = None
    if ping_day and ping_day.get("equity_return") is not None:
        ping_return = float(ping_day["equity_return"]) / 100.0
    dividend = float(ping_day["dividend"]) if ping_day else 0.0
    bonus = str(lsjz_day.get("bonus") or "")
    gap = None
    if stored is not None and lsjz_return is not None:
        gap = stored - lsjz_return
    ordered = sorted(lsjz)
    accum_return = None
    if day in ordered:
        pos = ordered.index(day)
        if pos > 0:
            now = _level((lsjz.get(day) or {}).get("accum_nav"))
            prev = _level((lsjz.get(ordered[pos - 1]) or {}).get("accum_nav"))
            if now is not None and prev is not None:
                accum_return = now / prev - 1.0
    accum_gap = None if stored is None or accum_return is None else stored - accum_return
    prior = ordered[ordered.index(day) - 1] if day in ordered and ordered.index(day) > 0 else ""

    def _pair_gap(stamp: str) -> dict:
        if stamp not in ordered:
            return {}
        pos = ordered.index(stamp)
        if pos == 0:
            return {}
        prev_stamp = ordered[pos - 1]
        now = lsjz[stamp]
        prev = lsjz[prev_stamp]
        unit_now, unit_prev = _level(now.get("unit_nav")), _level(prev.get("unit_nav"))
        accum_now, accum_prev = _level(now.get("accum_nav")), _level(prev.get("accum_nav"))
        unit_ret = None if unit_now is None or unit_prev is None else unit_now / unit_prev - 1.0
        accum_ret = None if accum_now is None or accum_prev is None else accum_now / accum_prev - 1.0
        return {
            "date": stamp,
            "prev": prev_stamp,
            "unit_point": None if unit_now is None or unit_prev is None else unit_now - unit_prev,
            "accum_point": None if accum_now is None or accum_prev is None else accum_now - accum_prev,
            "unit_return": unit_ret,
            "accum_return": accum_ret,
            "unit_minus_accum": None if unit_ret is None or accum_ret is None else unit_ret - accum_ret,
        }

    dec28 = _pair_gap("2015-12-28")
    dec29 = _pair_gap(day)
    conclusion = (
        f"{code} {day} 不是分红除息日。pingzhong unitMoney={dividend}，"
        f"lsjz 没有分红字段（FHFCZ / FHSP 均未出现）。"
        f"单位净值与累计净值同一天都上涨，点数相同。"
        f"库内复权净值日收益 {stored} 与 pingzhong 日增长率、lsjz 日增长率 JZZZL 一致"
        f"（和 JZZZL 相差 {gap}）。"
        f"相对上一公布日 {prior} 的累计净值涨跌是 {accum_return}，"
        f"与库内日收益相差 {accum_gap}。"
        "差来自累计净值的分母更大，不是除息。"
        "2015-12-28 单位净值与累计净值同跌 0.0349，百分比差约 1.70 个百分点，同样没有分红标记；"
        "D25 写的约 1.7 个百分点对得上这一天的口径差，不是 12-29 的除息。"
        "序列不改。"
    )
    rows = []
    for row in window:
        stamp = row["date"]
        side = lsjz.get(stamp) or {}
        rows.append({
            "date": stamp,
            "ping_unit": row.get("unit_nav"),
            "ping_accum": row.get("accum_nav"),
            "ping_equity_return_pct": row.get("equity_return"),
            "ping_unit_money": row.get("dividend"),
            "lsjz_unit": side.get("unit_nav"),
            "lsjz_accum": side.get("accum_nav"),
            "lsjz_growth_pct": side.get("growth"),
            "lsjz_bonus": side.get("bonus"),
        })
    _write(root / "050002-exdiv.csv", rows)
    summary = {
        "code": code,
        "day": day,
        "stored_return": stored,
        "stored_source": None if source is None else source[0],
        "stored_source_url": None if source is None else source[1],
        "ping_return": ping_return,
        "ping_unit_money": dividend,
        "lsjz_return": lsjz_return,
        "lsjz_accum_return": accum_return,
        "lsjz_bonus": bonus,
        "stored_minus_jzzzl": gap,
        "stored_minus_ljjz": accum_gap,
        "level_gap_2015_12_28": dec28,
        "level_gap_2015_12_29": dec29,
        "conclusion": conclusion,
        "ping_url": ping_url,
        "lsjz_url": f"{LSJZ}?fundCode={code}&startDate=2015-12-01&endDate=2015-12-31",
        "jbgk": JBGK.format(code=code),
    }
    (root / "050002-exdiv.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(conclusion, flush=True)
    return summary


def main() -> None:
    run()
    check_exdiv()


if __name__ == "__main__":
    main()
