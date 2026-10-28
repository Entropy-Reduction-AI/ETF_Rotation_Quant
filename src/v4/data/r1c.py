"""v4-R1c：124 只场内后复权、相近替身、310318 抽查、2016 年以后完整性。

不覆盖已有后复权。不算组合收益，也不把 2016-01-01 以后的涨跌做成汇总。
"""
from __future__ import annotations

import csv
import hashlib
import time
import tomllib
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from src.data import db as DB
from src.data import http
from src.v4.data import catalog as C
from src.v4.data import ingest as IN
from src.v4.data.integrity import (
    ETF_MOVE, FINDING_COLUMNS, OTC_MOVE, WINDOW_END, WINDOW_START, adj_discontinuity,
    count_findings, scan_price_series,
)
from src.v4.data.parse import bar_sha256
from src.v4.data.r1c_parse import (
    NEAR_SUBSTITUTES, ParseError, REJECTED_NOT_SUBSTITUTE, accum_unit_spread,
    assemble_backward, growth_discrepancies, near_substitute_rows, parse_fhsp,
    parse_sina_nav, pingzhong_action_markers, series_daily_growth, sina_daily_growth,
    spot_event,
)

ROOT = Path(__file__).resolve().parents[3]
UNIVERSE = ROOT / "config" / "v3" / "universe.toml"
OUT = ROOT / "results" / "v4" / "inventory"
FHSP = "https://fundf10.eastmoney.com/fhsp_{code}.html"
PING = "https://fund.eastmoney.com/pingzhongdata/{code}.js"
SINA_NAV = "https://stock.finance.sina.com.cn/fundInfo/api/openapi.php/CaihuiFundInfoService.getNav"
SOURCE = "eastmoney_fhsp"
SOURCE_NOTE = "没有把原始收盘当成后复权"
PRIORITY = ("159940", "159944")
SPREAD_LIMIT = 0.02
CLIFF = 0.25
GROWTH_TOLERANCE = 0.0005
US_ETF = {item["code"] for item in C.ETFS}

_ACTION = """
CREATE TABLE IF NOT EXISTS v4_corp_action (
    code        TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('dividend', 'split')),
    ex_date     TEXT NOT NULL,
    amount      REAL,
    ratio_num   REAL,
    ratio_den   REAL,
    ratio_text  TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL,
    source_url  TEXT NOT NULL,
    body_sha256 TEXT NOT NULL,
    note        TEXT NOT NULL DEFAULT '',
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (code, kind, ex_date)
) WITHOUT ROWID
"""
_NEAR = """
CREATE TABLE IF NOT EXISTS v4_near_sub (
    code             TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    instrument       TEXT NOT NULL,
    container_id     TEXT NOT NULL,
    container_name   TEXT NOT NULL,
    tracked_index    TEXT NOT NULL,
    near_index       TEXT NOT NULL,
    near_index_code  TEXT NOT NULL,
    decision         TEXT NOT NULL,
    note             TEXT NOT NULL,
    fetched_at       TEXT NOT NULL
) WITHOUT ROWID
"""
_BLOCK = """
CREATE TABLE IF NOT EXISTS v4_carrier_block (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    reason      TEXT NOT NULL,
    abnormal    INTEGER NOT NULL CHECK (abnormal IN (0, 1)),
    conclusion  TEXT NOT NULL,
    source      TEXT NOT NULL,
    checked_at  TEXT NOT NULL
) WITHOUT ROWID
"""


class R1cError(RuntimeError):
    pass


CARRY_SOURCE = "tencent_etf_hfq_carry"
CARRY_METHOD = "factor_carry"
LIMIT_UP = "limit_up"
# 重叠段末日附近，后复权/原始收盘的比例只应剩三位小数的取整抖动。
RATIO_SPAN_LIMIT = 0.002
# 承接后的后复权收盘，相对「原始收盘 × 前一日比例」允许一个最小价位。
TICK = 0.001

_MOVE = """
CREATE TABLE IF NOT EXISTS v4_move_check (
    code         TEXT NOT NULL,
    series_kind  TEXT NOT NULL,
    date         TEXT NOT NULL,
    close        REAL NOT NULL,
    prev_close   REAL NOT NULL,
    peer_close   REAL NOT NULL,
    peer_source  TEXT NOT NULL,
    peer_url     TEXT NOT NULL,
    limit_close  REAL,
    conclusion   TEXT NOT NULL,
    note         TEXT NOT NULL DEFAULT '',
    fetched_at   TEXT NOT NULL,
    PRIMARY KEY (code, series_kind, date)
) WITHOUT ROWID
"""


def ensure(con) -> None:
    con.execute(_ACTION)
    con.execute(_NEAR)
    con.execute(_BLOCK)
    con.execute(_MOVE)
    con.commit()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unavailable_codes(path: Path = IN.COVERAGE) -> list[str]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    codes = [row["code"] for row in rows if row.get("status") == "unavailable" and SOURCE_NOTE in (row.get("note") or "")]
    if len(codes) != len(set(codes)):
        raise R1cError("覆盖表里缺后复权的代码有重复")
    return codes


def execution_codes(path: Path = UNIVERSE) -> set[str]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    codes = set()
    for container in data["container"]:
        for item in container.get("execution") or []:
            code = str(item.get("code") or "")
            if code:
                codes.add(code)
    return codes


def list_dates(path: Path = UNIVERSE) -> dict[str, str]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    out = {}
    for container in data["container"]:
        for item in container.get("execution") or []:
            code = str(item.get("code") or "")
            listed = str(item.get("list_date") or "")
            if code and code not in out:
                out[code] = listed
    for item in C.ETFS:
        out.setdefault(item["code"], item["inception"])
    return out


def sort_codes(codes: list[str], carriers: set[str]) -> list[str]:
    front = [code for code in PRIORITY if code in codes]
    rest_carriers = sorted(code for code in codes if code in carriers and code not in front)
    others = sorted(code for code in codes if code not in carriers and code not in front)
    return front + rest_carriers + others


def _read_raw(con, code: str, end: str) -> list[dict]:
    return [dict(row) for row in con.execute(
        """SELECT date, open, high, low, close, volume FROM bars
           WHERE code=? AND adj='raw' AND date<=? ORDER BY date""",
        (code, end))]


def _max_abs_move(rows: list[dict]) -> float:
    prev = None
    worst = 0.0
    for row in rows:
        close = row.get("close")
        if close is None or not (float(close) > 0):
            continue
        close = float(close)
        if prev:
            worst = max(worst, abs(close / prev - 1.0))
        prev = close
    return worst


def _same_close(raw: list[dict], adjusted: list[dict]) -> bool:
    left = [(row["date"], float(row["close"])) for row in raw if row.get("close") and float(row["close"]) > 0]
    right = [(row["date"], float(row["close"])) for row in adjusted if row.get("close") and float(row["close"]) > 0]
    if len(left) != len(right):
        return False
    return all(a[0] == b[0] and abs(a[1] - b[1]) < 1e-9 for a, b in zip(left, right))


def build_one(raw: list[dict], fhsp_html: str, ping_text: str | None, end: date) -> dict:
    """决定一只 ETF 的后复权。页面不是明确空表、或空表和净值对不上时，不写入。"""
    parsed = parse_fhsp(fhsp_html)
    markers = pingzhong_action_markers(ping_text) if ping_text else []
    spread = None
    if ping_text:
        try:
            spread = accum_unit_spread(ping_text, end)
        except (ValueError, TypeError) as exc:
            raise R1cError(f"净值文件解析失败：{exc}") from exc
    has_events = bool(parsed["dividends"] or parsed["splits"])
    if not has_events:
        if not (parsed["explicit_empty_dividend"] and parsed["explicit_empty_split"]):
            raise R1cError("分红或拆分表不是明确的空表")
        if any("分红" in item or "拆分" in item or "折算" in item for item in markers):
            raise R1cError("净值文件标了公司行为，分红送配表却是空的")
        if spread is not None and spread > SPREAD_LIMIT:
            raise R1cError(f"累计净值减单位净值的极差为 {spread:.4f}，分红表是空的")
        if _max_abs_move(raw) >= CLIFF:
            raise R1cError("原始收盘有 25% 以上的单日缺口，页面没有对应拆分")
    built = assemble_backward(raw, parsed["dividends"], parsed["splits"])
    if not has_events and not _same_close(raw, built["adjusted"]):
        raise R1cError("没有公司行为时后复权收盘应与原始收盘相同")
    spots = _spots(raw, built)
    if any(row.get("continuous") == "0" for row in spots):
        raise R1cError("抽查不连续，没有入库")
    method = "no_corporate_action_factor_1" if not has_events else "fhsp_dividend_reinvest_split_undone"
    return {
        "adjusted": built["adjusted"],
        "dividends": built["dividends"],
        "splits": built["splits"],
        "parsed": parsed,
        "spots": spots,
        "method": method,
        "spread": spread,
        "notes": built["notes"],
    }


def _spots(raw: list[dict], built: dict) -> list[dict]:
    spots = []
    if built["dividends"]:
        item = max(built["dividends"], key=lambda row: row["amount"])
        spots.append(spot_event("dividend", item["date"], raw, built["adjusted"], item["amount"], 1.0))
    else:
        spots.append({"kind": "dividend", "date": "", "raw_return": "", "adj_return": "",
                      "continuous": "", "note": "无分红日"})
    if built["splits"]:
        item = built["splits"][0]
        mult = float(item["numerator"]) / float(item["denominator"])
        spots.append(spot_event("split", item["date"], raw, built["adjusted"], 0.0, mult))
    else:
        spots.append({"kind": "split", "date": "", "raw_return": "", "adj_return": "",
                      "continuous": "", "note": "无拆分日"})
    return spots


def insert_backward(con, code: str, rows: list[dict], source_url: str, method: str, fetched_at: str) -> None:
    have = con.execute(
        "SELECT COUNT(*) FROM v4_series WHERE code=? AND kind='backward'", (code,)).fetchone()[0]
    if have:
        raise R1cError(f"{code} 已有后复权 {have} 行，不覆盖")
    con.executemany(
        """INSERT INTO v4_series
           (code, kind, date, open, high, low, close, volume, unit_nav, accum_nav, filled,
            source, source_url, method, fetched_at)
           VALUES (?, 'backward', ?, ?, ?, ?, ?, ?, NULL, NULL, 0, ?, ?, ?, ?)""",
        [(code, row["date"], row.get("open"), row.get("high"), row.get("low"), row.get("close"),
          row.get("volume"), SOURCE, source_url, method, fetched_at) for row in rows])


def _insert_actions(con, code: str, parsed: dict, source_url: str, body_sha: str, fetched_at: str) -> None:
    rows = []
    for item in parsed["dividends"]:
        rows.append((code, "dividend", item["date"], item["amount"], None, None, item["text"],
                     SOURCE, source_url, body_sha, "", fetched_at))
    for item in parsed["splits"]:
        rows.append((code, "split", item["date"], None, item["numerator"], item["denominator"], item["text"],
                     SOURCE, source_url, body_sha, item.get("kind_text") or "", fetched_at))
    con.executemany(
        """INSERT INTO v4_corp_action
           (code, kind, ex_date, amount, ratio_num, ratio_den, ratio_text, source, source_url,
            body_sha256, note, fetched_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows)


def _coverage_for(code: str, name: str, bars: list[dict], digest: str, source_url: str, note: str, status: str) -> dict:
    return IN._coverage_row(
        market="CN", container_id=f"etf-{code}", code=code, name=name or code,
        series_kind="bar", return_basis="total_return", currency="CNY",
        source=SOURCE, source_url=source_url,
        first_date=bars[0]["date"] if bars else "", last_date=bars[-1]["date"] if bars else "",
        rows=len(bars), sha256=digest, status=status, note=note,
    )


def _name_of(con, code: str) -> str:
    row = con.execute(
        "SELECT name FROM v4_listing WHERE code=?", (code,)).fetchone()
    if row and row[0]:
        return row[0]
    for item in NEAR_SUBSTITUTES:
        if item["code"] == code:
            return item["name"]
    return code


def fill_hfq(con, codes: list[str], end: date, fetched_at: str, log: list[str]) -> tuple[list[dict], list[dict]]:
    coverage = []
    spots = []
    carriers = execution_codes()
    ordered = sort_codes(codes, carriers)
    log.append(f"hfq order front={','.join(ordered[:2])} carriers={sum(code in carriers for code in ordered)} total={len(ordered)}")
    for index, code in enumerate(ordered, 1):
        source_url = FHSP.format(code=code)
        raw = [row for row in _read_raw(con, code, end.isoformat()) if row.get("close") and float(row["close"]) > 0]
        if not raw:
            coverage.append(_coverage_for(code, code, [], "", source_url, "v4-R1c 没有原始正收盘，不能做后复权。", "unavailable"))
            log.append(f"hfq {code} no raw")
            continue
        if con.execute("SELECT 1 FROM v4_series WHERE code=? AND kind='backward' LIMIT 1", (code,)).fetchone():
            raise R1cError(f"{code} 在补齐前已经有后复权，拒绝覆盖")
        try:
            fhsp_raw = http.get(source_url, headers={"Referer": "https://fundf10.eastmoney.com/"}, timeout=25)
            fhsp_html = fhsp_raw.decode("utf-8", "replace")
            body_sha = hashlib.sha256(fhsp_raw).hexdigest()
            ping_text = _ping(code)
        except (http.FetchError, UnicodeError) as exc:
            coverage.append(_coverage_for(
                code, _name_of(con, code), [], "", source_url,
                f"v4-R1c 分红送配页取不到：{exc}"[:240], "unavailable"))
            log.append(f"hfq {code} FETCH {exc}")
            time.sleep(0.2)
            continue
        try:
            built = build_one(raw, fhsp_html, ping_text, end)
        except (R1cError, ParseError, ValueError) as exc:
            coverage.append(_coverage_for(
                code, _name_of(con, code), [], "", source_url,
                f"v4-R1c 未写入后复权：{exc}"[:240], "unavailable"))
            log.append(f"hfq {code} BLOCK {exc}")
            time.sleep(0.15)
            continue
        digest = bar_sha256(built["adjusted"])
        note = _hfq_note(built, body_sha)
        with con:
            _insert_actions(con, code, built["parsed"], source_url, body_sha, fetched_at)
            insert_backward(con, code, built["adjusted"], source_url, built["method"], fetched_at)
        coverage.append(_coverage_for(code, _name_of(con, code), built["adjusted"], digest, source_url, note, "in_db"))
        for spot in built["spots"]:
            spots.append({"code": code, **spot})
        if index % 10 == 0 or index == len(ordered):
            log.append(f"hfq progress {index}/{len(ordered)} last={code} method={built['method']} rows={len(built['adjusted'])}")
        time.sleep(0.15)
    return coverage, spots


def _ping(code: str) -> str | None:
    try:
        raw = http.get(PING.format(code=code), headers={"Referer": f"https://fund.eastmoney.com/{code}.html"}, timeout=40)
    except http.FetchError:
        return None
    return raw.decode("utf-8", "replace")


def _hfq_note(built: dict, body_sha: str) -> str:
    div_n = len(built["parsed"]["dividends"])
    split_n = len(built["parsed"]["splits"])
    if built["method"] == "no_corporate_action_factor_1":
        spread = built["spread"]
        spread_text = "净值文件没有累计净值可对。" if spread is None else f"累计净值减单位净值的极差 {spread:.4f}。"
        return ("v4-R1c 天天基金分红送配页写明没有分红、没有拆分。"
                f"{spread_text}后复权因子为 1，收盘与原始收盘相同，不是把原始收盘改名。"
                f"页面 SHA256 {body_sha}。不是东财 fqt=2：本次 push2his 对 159940 被断开。"
                "腾讯 fqkline 在 R1b 没有这批代码的 hfqday，本次复测 159940 仍没有。")
    return ("v4-R1c 用天天基金分红送配页的现金分红和拆分比例，对腾讯原始收盘做后复权。"
            f"分红 {div_n} 次，拆分或折算 {split_n} 次。不覆盖原始收盘。"
            f"页面 SHA256 {body_sha}。")


def replace_coverage(extra: list[dict], codes: set[str]) -> None:
    rows = []
    if IN.COVERAGE.exists():
        with IN.COVERAGE.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("code") in codes and SOURCE_NOTE in (row.get("note") or ""):
                    continue
                rows.append(row)
    IN.write_coverage(rows + extra)


def register_near_substitutes(con, fetched_at: str) -> list[dict]:
    rows = near_substitute_rows()
    rejected = set(REJECTED_NOT_SUBSTITUTE)
    with con:
        con.execute("DELETE FROM v4_near_sub")
        for row in rows:
            if row["tracked_index"] in rejected or row["near_index"] in rejected:
                raise R1cError(f"{row['code']} 用了载体表拒绝的指数")
            con.execute(
                """INSERT INTO v4_near_sub
                   (code, name, instrument, container_id, container_name, tracked_index,
                    near_index, near_index_code, decision, note, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["code"], row["name"], row["instrument"], row["container_id"], row["container_name"],
                 row["tracked_index"], row["near_index"], row["near_index_code"], row["decision"],
                 row["note"], fetched_at))
    _write(OUT / "near-substitute.csv", (
        "code", "name", "instrument", "container_id", "container_name", "tracked_index",
        "near_index", "near_index_code", "decision", "note",
    ), rows)
    return rows


def crosscheck_310318(con, log: list[str]) -> dict:
    """用新浪 2008 年净值对照库内复权净值的逐日涨跌。不对照指数，不算跟踪差。"""
    stored = [dict(row) for row in con.execute(
        """SELECT date, close FROM v4_series
           WHERE code='310318' AND kind='otc_nav' AND date>='2008-01-01' AND date<='2008-12-31'
           ORDER BY date""")]
    if len(stored) < 200:
        raise R1cError(f"310318 在 2008 年只有 {len(stored)} 行复权净值")
    sina = []
    for page in range(1, 16):
        raw = http.get(SINA_NAV, {
            "symbol": "310318", "datefrom": "2008-01-01", "dateto": "2008-12-31", "page": str(page),
        }, timeout=20)
        batch = parse_sina_nav(_json(raw))
        if not batch:
            break
        sina.extend(batch)
        time.sleep(0.15)
    dedup = {row["date"]: row for row in sina}
    sina_rows = [dedup[day] for day in sorted(dedup)]
    left = series_daily_growth(stored)
    right = sina_daily_growth(sina_rows)
    paired = [row for row in right if row["date"] in left]
    problems = growth_discrepancies(left, right, GROWTH_TOLERANCE)
    worst = max((abs(row["diff"]) for row in problems), default=0.0)
    over_50bp = sum(1 for row in problems if abs(row["diff"]) > 0.005)
    agrees = len(paired) >= 200 and over_50bp == 0 and worst <= 0.003
    conclusion = (
        f"2008 年重叠 {len(paired)} 天。绝对差超过 5bp 的 {len(problems)} 天，超过 50bp 的 {over_50bp} 天，"
        f"最大绝对差 {worst:.6f}。"
        + ("新浪单位净值加分红后的日增长与库内复权净值一致，不是抓取错误。"
           if agrees else "两个来源的日增长对不上，310318 仍标为异常，序列没有改。")
        + "增强型基金不作载体。"
    )
    detail = []
    for row in right:
        if row["date"] not in left:
            continue
        detail.append({
            "date": row["date"],
            "stored_growth": f"{left[row['date']]:.8f}",
            "sina_growth": f"{row['growth']:.8f}",
            "diff": f"{left[row['date']] - row['growth']:.8f}",
        })
    _write(OUT / "r1c-310318-crosscheck.csv", ("date", "stored_growth", "sina_growth", "diff"), detail)
    log.append(f"310318 {conclusion}")
    return {"agrees": agrees, "conclusion": conclusion, "overlap": len(paired), "over_5bp": len(problems),
            "over_50bp": over_50bp, "max_abs": worst}


def _json(raw: bytes) -> dict:
    import json
    return json.loads(raw.decode("utf-8", "replace"))


def flag_enhanced(con, check: dict, fetched_at: str) -> None:
    rows = [dict(row) for row in con.execute(
        "SELECT code, name, enhanced FROM v4_listing ORDER BY code")]
    with con:
        con.execute("DELETE FROM v4_carrier_block")
        for row in rows:
            if not row["enhanced"]:
                continue
            abnormal = 1 if row["code"] == "310318" and not check["agrees"] else 0
            conclusion = check["conclusion"] if row["code"] == "310318" else "增强型不作载体。本次没有另做净值抽查。"
            if row["code"] == "310318" and check["agrees"]:
                abnormal = 0
            con.execute(
                """INSERT INTO v4_carrier_block
                   (code, name, reason, abnormal, conclusion, source, checked_at)
                   VALUES (?, ?, 'enhanced_never_carrier', ?, ?, ?, ?)""",
                (row["code"], row["name"], abnormal, conclusion,
                 "sina_caihui" if row["code"] == "310318" else "v4_listing", fetched_at))
    saved = [dict(row) for row in con.execute(
        "SELECT code, name, reason, abnormal, conclusion FROM v4_carrier_block ORDER BY code")]
    _write(OUT / "r1c-enhanced-block.csv", ("code", "name", "reason", "abnormal", "conclusion"), saved)


def _events_for(con, code: str) -> tuple[set[str], list[dict]]:
    days = set()
    detailed = []
    for ex_date, amount in con.execute(
            "SELECT ex_date, amount FROM cash_dividends WHERE code=?", (code,)):
        days.add(ex_date)
        detailed.append({"date": ex_date, "kind": "dividend", "amount": amount})
    if _table(con, "v4_event"):
        for ex_date, kind, amount, num, den in con.execute(
                "SELECT ex_date, kind, amount, ratio_num, ratio_den FROM v4_event WHERE code=?", (code,)):
            days.add(ex_date)
            detailed.append({"date": ex_date, "kind": kind, "amount": amount,
                             "numerator": num, "denominator": den})
    if _table(con, "v4_corp_action"):
        for ex_date, kind, amount, num, den in con.execute(
                """SELECT ex_date, kind, amount, ratio_num, ratio_den
                   FROM v4_corp_action WHERE code=?""", (code,)):
            days.add(ex_date)
            detailed.append({"date": ex_date, "kind": kind, "amount": amount,
                             "numerator": num, "denominator": den})
    return days, detailed


def _table(con, name: str) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _calendar(con, code: str, source: str) -> list[str] | None:
    if source in {"tencent_etf", "csi", "tencent_index", "tencent_price_index_offline", "chinabond"}:
        return _dates(con, "SELECT date FROM calendar WHERE date>=? AND date<=? ORDER BY date",
                      (WINDOW_START, WINDOW_END))
    if source == "tencent_hk_index":
        return _dates(con, """SELECT date FROM bars WHERE code='HSI' AND adj='raw'
                              AND date>=? AND date<=? ORDER BY date""", (WINDOW_START, WINDOW_END))
    if source in {"yahoo", "nasdaq"} and code != "N225" and code != "BRENT":
        return _dates(con, """SELECT date FROM bars WHERE code='SPX' AND adj='raw'
                              AND date>=? AND date<=? ORDER BY date""", (WINDOW_START, WINDOW_END))
    return None


def _dates(con, sql: str, params: tuple) -> list[str]:
    return [row[0] for row in con.execute(sql, params)]


def _group(source: str, code: str) -> str | None:
    if source == "chinamoney" or code in {"USDCNY", "HKDCNY"}:
        return None
    if source == "tencent_etf" or code in US_ETF:
        return "etf"
    return "research"


def limit_close(prev: float) -> float:
    """涨跌幅 20% 的限价。按最小价位 0.001 四舍五入。"""
    return float((Decimal(str(prev)) * Decimal("1.2")).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def _positive(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row.get("date") and row.get("close") not in (None, "") and float(row["close"]) > 0]


def ratio_span(raw: list[dict], backward: list[dict], last: str, n: int = 20) -> float:
    """末日及之前 n 个重叠日的后复权/原始比例极差。"""
    raw_close = {row["date"]: float(row["close"]) for row in _positive(raw) if row["date"] <= last}
    ratios = []
    for row in _positive(backward):
        if row["date"] > last or row["date"] not in raw_close or raw_close[row["date"]] <= 0:
            continue
        ratios.append(float(row["close"]) / raw_close[row["date"]])
    if len(ratios) < 2:
        raise R1cError("重叠段不足以看后复权比例")
    tail = ratios[-n:]
    return max(tail) - min(tail)


def carried_tail(raw: list[dict], backward: list[dict], end: str) -> dict:
    """腾讯后复权停更之后，用末日比例承接原始收盘。不改重叠段。"""
    back = _positive(backward)
    if not back:
        raise R1cError("没有后复权，不能承接")
    last = back[-1]["date"]
    raw_rows = [row for row in _positive(raw) if row["date"] <= end]
    raw_on = {row["date"]: row for row in raw_rows}
    if last not in raw_on:
        raise R1cError(f"后复权末日 {last} 没有原始收盘")
    ratio = float(back[-1]["close"]) / float(raw_on[last]["close"])
    span = ratio_span(raw_rows, back, last)
    if span > RATIO_SPAN_LIMIT:
        raise R1cError(f"末日附近后复权比例极差 {span:.6f}，不承接")
    tail = []
    for row in raw_rows:
        if row["date"] <= last:
            continue
        scale = ratio
        tail.append({
            "date": row["date"],
            "open": None if row.get("open") in (None, "") else float(row["open"]) * scale,
            "high": None if row.get("high") in (None, "") else float(row["high"]) * scale,
            "low": None if row.get("low") in (None, "") else float(row["low"]) * scale,
            "close": float(row["close"]) * scale,
            "volume": row.get("volume"),
        })
    if not tail:
        raise R1cError(f"{last} 之后没有原始正收盘")
    if tail[-1]["date"] != end:
        raise R1cError(f"承接后最后一日是 {tail[-1]['date']}，不是 {end}")
    anchor = float(back[-1]["close"])
    linked = tail[0]["close"] / anchor - 1.0
    raw_linked = float(raw_on[tail[0]["date"]]["close"]) / float(raw_on[last]["close"]) - 1.0
    if abs(linked - raw_linked) > 1e-9:
        raise R1cError("承接的第一天和原始收盘收益不一致")
    return {"last": last, "ratio": ratio, "span": span, "tail": tail}


def overlap_mismatches(stored: dict[str, float], fresh: dict[str, float], tol: float = 1e-6) -> list[tuple]:
    """新抓到的重叠段必须落在库内，且收盘一致。"""
    bad = []
    for day, close in sorted(fresh.items()):
        if day not in stored:
            bad.append((day, None, close))
        elif abs(stored[day] - close) > tol:
            bad.append((day, stored[day], close))
    return bad


def actions_after(parsed: dict, last: str) -> list[dict]:
    later = []
    for item in parsed.get("dividends") or []:
        if item["date"] > last:
            later.append({"kind": "dividend", "date": item["date"]})
    for item in parsed.get("splits") or []:
        if item["date"] > last:
            later.append({"kind": "split", "date": item["date"]})
    return later


def append_carried_tail(con, code: str, tail: list[dict], source_url: str, fetched_at: str) -> int:
    """只插入库里还没有的日期。重叠段不覆盖。"""
    have = {row[0] for row in con.execute(
        "SELECT date FROM v4_series WHERE code=? AND kind='backward'", (code,))}
    fresh = [row for row in tail if row["date"] not in have]
    if not fresh:
        return 0
    con.executemany(
        """INSERT INTO v4_series
           (code, kind, date, open, high, low, close, volume, unit_nav, accum_nav, filled,
            source, source_url, method, fetched_at)
           VALUES (?, 'backward', ?, ?, ?, ?, ?, ?, NULL, NULL, 0, ?, ?, ?, ?)""",
        [(code, row["date"], row.get("open"), row.get("high"), row.get("low"), row["close"],
          row.get("volume"), CARRY_SOURCE, source_url, CARRY_METHOD, fetched_at) for row in fresh])
    return len(fresh)


def limit_up_checks(code: str, day: str, raw: list[dict], backward: list[dict],
                    peer_close: float, peer_source: str, peer_url: str, note: str) -> list[dict]:
    """原始收盘等于涨停价、且与对照价一致时，记下原始和后复权两行。"""
    raw_pos = _positive(raw)
    back_pos = _positive(backward)
    raw_i = {row["date"]: i for i, row in enumerate(raw_pos)}
    back_i = {row["date"]: i for i, row in enumerate(back_pos)}
    if day not in raw_i or raw_i[day] == 0 or day not in back_i or back_i[day] == 0:
        raise R1cError(f"{code} {day} 缺少相邻收盘")
    prev_raw = raw_pos[raw_i[day] - 1]
    raw_row = raw_pos[raw_i[day]]
    prev_back = back_pos[back_i[day] - 1]
    back_row = back_pos[back_i[day]]
    capped = limit_close(float(prev_raw["close"]))
    if abs(float(raw_row["close"]) - capped) > 1e-9 or abs(float(raw_row["close"]) - peer_close) > 1e-9:
        raise R1cError(f"{code} {day} 原始收盘不是涨停价或与对照价不一致")
    scaled = float(raw_row["close"]) * float(prev_back["close"]) / float(prev_raw["close"])
    if abs(float(back_row["close"]) - scaled) > TICK:
        raise R1cError(f"{code} {day} 后复权偏离原始涨停一个价位以上")
    shared = {
        "code": code, "date": day, "peer_source": peer_source, "peer_url": peer_url,
        "conclusion": LIMIT_UP, "note": note,
    }
    return [
        {**shared, "series_kind": "raw", "close": float(raw_row["close"]),
         "prev_close": float(prev_raw["close"]), "peer_close": peer_close, "limit_close": capped},
        {**shared, "series_kind": "backward", "close": float(back_row["close"]),
         "prev_close": float(prev_back["close"]), "peer_close": peer_close, "limit_close": capped},
    ]


def record_limit_ups(con, rows: list[dict], fetched_at: str) -> None:
    ensure(con)
    with con:
        for row in rows:
            con.execute("DELETE FROM v4_move_check WHERE code=? AND series_kind=? AND date=?",
                        (row["code"], row["series_kind"], row["date"]))
            con.execute(
                """INSERT INTO v4_move_check
                   (code, series_kind, date, close, prev_close, peer_close, peer_source, peer_url,
                    limit_close, conclusion, note, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["code"], row["series_kind"], row["date"], row["close"], row["prev_close"],
                 row["peer_close"], row["peer_source"], row["peer_url"], row["limit_close"],
                 row["conclusion"], row["note"], fetched_at))


def record_split(con, code: str, ex_date: str, numerator: float, denominator: float,
                 ratio_text: str, source_url: str, body_sha: str, note: str, fetched_at: str) -> None:
    ensure(con)
    with con:
        con.execute(
            """INSERT OR REPLACE INTO v4_corp_action
               (code, kind, ex_date, amount, ratio_num, ratio_den, ratio_text, source, source_url,
                body_sha256, note, fetched_at)
               VALUES (?, 'split', ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (code, ex_date, numerator, denominator, ratio_text, SOURCE, source_url, body_sha, note, fetched_at))


def _limit_up_days(con, code: str, kind: str, rows: list[dict]) -> set[str]:
    if not _table(con, "v4_move_check"):
        return set()
    recorded = {}
    for day, close, conclusion in con.execute(
            """SELECT date, close, conclusion FROM v4_move_check
               WHERE code=? AND series_kind=?""", (code, kind)):
        if conclusion == LIMIT_UP:
            recorded[day] = float(close)
    found = set()
    for row in rows:
        close = row.get("close")
        if row.get("date") in recorded and close not in (None, "") and abs(float(close) - recorded[row["date"]]) <= 1e-4:
            found.add(row["date"])
    return found


def merge_manager_class(findings: list[dict], previous: list[dict]) -> list[dict]:
    """未改动的问题行保留 Manager 分类。新行留空。"""
    kept = {}
    for row in previous:
        key = (row["code"], row["series_kind"], row["source"], row["check"],
               row["date"], row["end_date"], row["detail"])
        kept[key] = row.get("manager_class") or ""
    merged = []
    for row in findings:
        item = dict(row)
        key = (item["code"], item["series_kind"], item["source"], item["check"],
               item["date"], item["end_date"], item["detail"])
        item["manager_class"] = kept.get(key, "")
        merged.append(item)
    return merged


def run_integrity(con, list_date_map: dict[str, str]) -> tuple[list[dict], list[dict]]:
    inventory = []
    findings = []
    hfq = {}
    for code, day, close in con.execute(
            """SELECT code, date, close FROM v4_series
               WHERE kind='backward' AND date>=? AND date<=?""", (WINDOW_START, WINDOW_END)):
        if close is None or not (float(close) > 0):
            continue
        hfq.setdefault(code, {})[day] = float(close)
    seen = set()
    for source, code in con.execute("SELECT DISTINCT source, code FROM bars ORDER BY source, code"):
        group = _group(source, code)
        if group is None:
            continue
        rows = [dict(row) for row in con.execute(
            "SELECT date, close FROM bars WHERE code=? AND adj='raw' AND date<=? ORDER BY date",
            (code, WINDOW_END))]
        calendar = _calendar(con, code, source)
        if code == "HSI" or code == "SPX":
            calendar = None
        threshold = ETF_MOVE if group == "etf" else None
        events, detailed = _events_for(con, code) if group == "etf" else (set(), [])
        other = hfq.get(code) if group == "etf" else None
        listed = list_date_map.get(code) if group == "etf" else None
        explained = _limit_up_days(con, code, "raw", rows) if group == "etf" else set()
        info, found = scan_price_series(
            code, group, "raw", source, rows, calendar, threshold, events, other, listed, explained)
        inventory.append(info)
        findings.extend(found)
        if group == "etf" and code in hfq and detailed:
            adjusted = [{"date": day, "close": close} for day, close in sorted(hfq[code].items())]
            for item in adj_discontinuity(rows, adjusted, detailed):
                if WINDOW_START <= item["date"] <= WINDOW_END:
                    findings.append({
                        "code": code, "group": group, "series_kind": "backward", "source": "v4_series",
                        "check": item["check"], "date": item["date"], "end_date": item["date"],
                        "n_days": "1", "detail": item["detail"], "manager_class": "",
                    })
        seen.add(code)
    for code, source in con.execute(
            "SELECT code, MIN(source) FROM v4_series WHERE kind='backward' GROUP BY code"):
        rows = [dict(row) for row in con.execute(
            """SELECT date, close FROM v4_series WHERE code=? AND kind='backward' AND date<=?
               ORDER BY date""", (code, WINDOW_END))]
        group = "etf"
        calendar = _calendar(con, code, "tencent_etf" if code not in US_ETF else "yahoo")
        events, _detailed = _events_for(con, code)
        explained = _limit_up_days(con, code, "backward", rows)
        info, found = scan_price_series(
            code, group, "backward", source, rows, calendar, ETF_MOVE, events, None, None, explained)
        inventory.append(info)
        findings.extend(found)
    for code, source in con.execute(
            "SELECT code, MIN(source) FROM v4_series WHERE kind='otc_nav' GROUP BY code"):
        rows = [dict(row) for row in con.execute(
            """SELECT date, close FROM v4_series WHERE code=? AND kind='otc_nav' AND date<=?
               ORDER BY date""", (code, WINDOW_END))]
        calendar = _calendar(con, code, "csi")
        info, found = scan_price_series(
            code, "otc", "otc_nav", source, rows, calendar, OTC_MOVE, set(), None, None)
        inventory.append(info)
        findings.extend(found)
    return inventory, findings


def write_integrity(inventory: list[dict], findings: list[dict]) -> dict[str, int]:
    _write(OUT / "integrity-series.csv",
           ("code", "group", "series_kind", "source", "first_date", "last_date", "rows"), inventory)
    _write(OUT / "integrity-findings.csv", FINDING_COLUMNS, findings)
    counts = count_findings(findings)
    lines = [
        "# 2016-01 至 2026-09 数据完整性",
        "",
        "Dev 只列出问题。`manager_class` 由调用方填入；没有分类的行留空，留给 Manager。",
        "",
        "没有计算年化、累计、排名或 IC。单日涨跌只出现在坏点行上，没有加总。",
        "",
        f"窗口 {WINDOW_START} → {WINDOW_END}。序列 {len(inventory)} 条，问题行 {len(findings)}。",
        "",
        "| 检查项 | 行数 |",
        "| --- | --- |",
    ]
    for key in sorted(counts):
        lines.append(f"| {key} | {counts[key]} |")
    if not counts:
        lines.append("| （无） | 0 |")
    lines.extend([
        "",
        "场内 ETF 单日阈值是 ±20%，场外基金是 ±30%。研究序列不做这个阈值。",
        "A 股和场外对照上交所日历，港股对照恒生指数的交易日，美股对照标普500的交易日。",
        "恒生指数、标普500，以及没有外部日历的序列，只标内部间隔不少于 12 个日历日的洞。",
        "上市日来自 v3 execution；登记为取不到的记 `list_date_unknown`。",
        "没有代码变更登记，本次没有旧代码到新代码的对照行。",
        "汇率中间价不在这三类序列里。",
        "",
    ])
    (OUT / "integrity-2016-2026.md").write_text("\n".join(lines), encoding="utf-8")
    return counts


def _write(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def bars_fingerprint(con) -> str:
    digest = hashlib.sha256()
    for row in con.execute("SELECT code, adj, date, close FROM bars ORDER BY code, adj, date"):
        digest.update(repr(tuple(row)).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def run(con, end: date = C.END) -> list[str]:
    if end > C.END:
        raise R1cError(f"截止日 {end} 晚于登记上限 {C.END}")
    ensure(con)
    fetched_at = DB.now()
    log = []
    codes = unavailable_codes()
    if PRIORITY[0] not in codes or PRIORITY[1] not in codes:
        raise R1cError("159940 或 159944 不在缺后复权名单里")
    db_path = Path(con.execute("PRAGMA database_list").fetchone()[2])
    before_sha = file_sha256(db_path)
    before_bytes = db_path.stat().st_size
    before_bars = bars_fingerprint(con)
    before_n = con.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
    log.append(f"sqlite before sha256={before_sha} bytes={before_bytes} bars={before_n}")
    run_id = DB.start_run(con, "backfill", end=end, args={
        "job": "v4-r1c-ingest",
        "portfolio_returns": False,
        "return_summaries_from_2016": False,
        "overwrites_existing_series": False,
    })
    try:
        coverage, spots = fill_hfq(con, codes, end, fetched_at, log)
        replace_coverage(coverage, set(codes))
        _write(OUT / "r1c-spotcheck.csv",
               ("code", "kind", "date", "raw_return", "adj_return", "continuous", "note"), spots)
        near = register_near_substitutes(con, fetched_at)
        log.append("near " + ", ".join(f"{row['code']}→{row['near_index']}" for row in near))
        check = crosscheck_310318(con, log)
        flag_enhanced(con, check, fetched_at)
        inventory, findings = run_integrity(con, list_dates())
        counts = write_integrity(inventory, findings)
        log.append("integrity " + " ".join(f"{key}={counts[key]}" for key in sorted(counts)))
        after_bars = bars_fingerprint(con)
        after_n = con.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
        if after_bars != before_bars or after_n != before_n:
            raise R1cError("bars 被改动，拒绝把这次运行标成完成")
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise R1cError(f"integrity_check={integrity}")
        con.commit()
        DB.finish_run(con, run_id, "ok")
    except Exception:
        DB.finish_run(con, run_id, "error")
        raise
    after_sha = file_sha256(db_path)
    log.append(f"sqlite after sha256={after_sha} bytes={db_path.stat().st_size}")
    log.append(f"filled={sum(1 for row in coverage if row['status']=='in_db')} "
               f"unavailable={sum(1 for row in coverage if row['status']!='in_db')}")
    return log
