"""v4-R1b：场内后复权、场外指数基金、2005 年汇率、R1 质量清单。

不计算组合收益。不覆盖已有 bars 收盘，只把 6 个中证代码在 2013-06-28 的 0 改成空值。
"""
from __future__ import annotations

import csv
import hashlib
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.data import db as DB
from src.data import http
from src.data import universe as U
from src.data.sources import TENCENT_KLINE
from src.v3.engine.prices import dividend_yields, total_return_close

from . import catalog as C
from . import ingest as IN
from .adjust import (
    backward_total_return, cny_per_hkd, compound_adjusted_nav, fill_backward,
    safe_quote_to_cny, split_already_in_close,
)
from .parse import bar_sha256, series_sha256
from .r1b_parse import (
    parse_jbgk, parse_pingzhongdata, parse_rank_index_funds, parse_safe_mid, parse_tencent_kline_rows,
)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results" / "v4" / "inventory"
SAFE_URL = "https://www.safe.gov.cn/safe/2020/1218/17833.html"
SAFE_FILE = "https://www.safe.gov.cn/safe/file/file/20260106/0f147e5357eb4c12a6406fc575cc21e8.xlsx"
RANK_URL = "https://fund.eastmoney.com/data/rankhandler.aspx"
JBGK = "https://fundf10.eastmoney.com/jbgk_{code}.html"
PING = "https://fund.eastmoney.com/pingzhongdata/{code}.js"
OTC_CUTOFF = "2011-12-31"
FX_EXISTING_FROM = "2006-01-04"
ZERO_DAY = "2013-06-28"
ZERO_CODES = ("H20184", "H20187", "H20202", "H30184", "H30187", "H30202")
DIFF_LIMIT = 0.05

# 跟踪标的与 v3 的 14 个 A 股容器。名称来自基金概况页，不是简称猜测。
EXACT_INDEX = {
    "沪深300指数": "csi300",
    "中证500指数": "csi500",
    "中证1000指数": "csi1000",
    "中证红利指数": "csi-dividend",
    "中证全指能源指数": "allshare-energy",
    "中证全指原材料指数": "allshare-materials",
    "中证全指工业指数": "allshare-industrials",
    "中证全指可选消费指数": "allshare-discretionary",
    "中证全指主要消费指数": "allshare-staples",
    "中证全指医药卫生指数": "allshare-healthcare",
    "中证全指金融地产指数": "allshare-financials-re",
    "中证全指信息技术指数": "allshare-it",
    "中证全指通信服务指数": "allshare-communication",
    "中证全指公用事业指数": "allshare-utilities",
}
# 不是同一个指数，但行业篮子接近。必须在 note 里写明实际跟踪的是哪一个。
NEAR_INDEX = {
    "沪深300金融地产指数": (
        "allshare-financials-re",
        "相近指数：跟踪沪深300金融地产指数，不是中证全指金融地产指数。",
    ),
}
# 概况页上见过、但不是这 14 个指数，所以不入库。
REJECTED = {
    "csi1000": " 国证2000指数和中证200指数不是中证1000。",
    "allshare-energy": " 中证上游资源产业指数和上证商品不是中证全指能源。",
    "allshare-materials": " 中证上游资源产业指数不是中证全指原材料。",
    "allshare-discretionary": " 上证消费80同时覆盖主要消费和可选消费，不单独代表可选消费。",
    "allshare-staples": " 上证消费80同时覆盖主要消费和可选消费，不单独代表主要消费。",
    "allshare-financials-re": " 中证银行指数和上证180金融股指数只覆盖银行或金融股，没有地产。",
    "allshare-it": " 深证电子信息传媒产业50指数不是中证全指信息技术。",
    "csi-dividend": " 深证红利指数不是中证红利指数。",
}
CONTAINER_NAME = {
    "csi300": "沪深300",
    "csi500": "中证500",
    "csi1000": "中证1000",
    "csi-dividend": "中证红利",
    "allshare-energy": "中证全指能源",
    "allshare-materials": "中证全指原材料",
    "allshare-industrials": "中证全指工业",
    "allshare-discretionary": "中证全指可选消费",
    "allshare-staples": "中证全指主要消费",
    "allshare-healthcare": "中证全指医药卫生",
    "allshare-financials-re": "中证全指金融地产",
    "allshare-it": "中证全指信息技术",
    "allshare-communication": "中证全指通信服务",
    "allshare-utilities": "中证全指公用事业",
}

_SERIES = """
CREATE TABLE IF NOT EXISTS v4_series (
    code       TEXT NOT NULL,
    kind       TEXT NOT NULL,
    date       TEXT NOT NULL,
    open       REAL,
    high       REAL,
    low        REAL,
    close      REAL,
    volume     REAL,
    unit_nav   REAL,
    accum_nav  REAL,
    filled     INTEGER NOT NULL DEFAULT 0 CHECK (filled IN (0, 1)),
    source     TEXT NOT NULL,
    source_url TEXT NOT NULL,
    method     TEXT NOT NULL DEFAULT '',
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (code, kind, date)
) WITHOUT ROWID
"""
_LISTING = """
CREATE TABLE IF NOT EXISTS v4_listing (
    code           TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    container_id   TEXT NOT NULL,
    maps_to        TEXT NOT NULL,
    tracked_index  TEXT NOT NULL,
    inception      TEXT NOT NULL,
    enhanced       INTEGER NOT NULL DEFAULT 0 CHECK (enhanced IN (0, 1)),
    source_url     TEXT NOT NULL,
    sha256         TEXT NOT NULL,
    note           TEXT NOT NULL DEFAULT '',
    fetched_at     TEXT NOT NULL
) WITHOUT ROWID
"""


class R1bError(RuntimeError):
    pass


def ensure(con) -> None:
    con.execute(_SERIES)
    con.execute(_LISTING)
    con.commit()


def null_zero_closes(con, codes: tuple[str, ...] = ZERO_CODES, day: str = ZERO_DAY) -> list[str]:
    """把指定日子上的收盘 0 改成空值。别的价格不动。"""
    notes = []
    with con:
        for code in codes:
            row = con.execute(
                "SELECT adj, open, high, low, close, volume, amount, source, fetched_at "
                "FROM bars WHERE code=? AND date=?",
                (code, day)).fetchone()
            if row is None:
                raise R1bError(f"{code} {day} 没有 K 线，拒绝改别的日子")
            close = row["close"]
            if close is None:
                notes.append(f"{code} {day} 收盘已是空值")
                continue
            if float(close) != 0.0:
                raise R1bError(f"{code} {day} 收盘是 {close}，不是 0，拒绝改成空值")
            con.execute("DELETE FROM bars WHERE code=? AND adj=? AND date=?", (code, row["adj"], day))
            con.execute(
                """INSERT INTO bars
                   (code, adj, date, open, high, low, close, volume, amount, source, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)""",
                (code, row["adj"], day, row["open"], row["high"], row["low"],
                 row["volume"], row["amount"], row["source"], row["fetched_at"]))
            notes.append(f"{code} {day} close 0 -> null source={row['source']}")
    return notes


def bars_except_fingerprint(con, skip: set[tuple[str, str]]) -> str:
    """除若干 (code, date) 外，bars 内容的哈希。用来证明没有改到别的收盘。"""
    digest = hashlib.sha256()
    sql = ("SELECT code, adj, date, open, high, low, close, volume, amount, source "
           "FROM bars ORDER BY code, adj, date")
    for row in con.execute(sql):
        if (row["code"], row["date"]) in skip:
            continue
        digest.update(repr(tuple(row)).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def _replace_series(con, code: str, kind: str, rows: list[dict], fetched_at: str) -> None:
    with con:
        con.execute("DELETE FROM v4_series WHERE code=? AND kind=?", (code, kind))
        con.executemany(
            """INSERT INTO v4_series
               (code, kind, date, open, high, low, close, volume, unit_nav, accum_nav, filled,
                source, source_url, method, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(code, kind, r["date"], r.get("open"), r.get("high"), r.get("low"), r.get("close"),
              r.get("volume"), r.get("unit_nav"), r.get("accum_nav"), int(r.get("filled") or 0),
              r["source"], r["source_url"], r.get("method") or "", fetched_at) for r in rows])


def _read_raw(con, code: str) -> list[dict]:
    return [dict(r) for r in con.execute(
        "SELECT date, open, high, low, close, volume FROM bars WHERE code=? AND adj='raw' ORDER BY date",
        (code,))]


def _events(con, code: str) -> tuple[list[dict], list[dict]]:
    divs = [dict(r) for r in con.execute(
        "SELECT ex_date AS date, amount FROM v4_event WHERE code=? AND kind='dividend' ORDER BY ex_date",
        (code,))]
    splits = [dict(r) for r in con.execute(
        "SELECT ex_date AS date, ratio_num AS numerator, ratio_den AS denominator, ratio "
        "FROM v4_event WHERE code=? AND kind='split' ORDER BY ex_date",
        (code,))]
    return divs, splits


def _neighbor(bars: list[dict], day: str) -> tuple[dict | None, dict | None]:
    prev = None
    for row in bars:
        if row["date"] == day:
            return prev, row
        if row["date"] < day:
            prev = row
        else:
            break
    return prev, None


def classify_splits(bars: list[dict], splits: list[dict]) -> tuple[bool, list[dict]]:
    """每笔拆分看相邻收盘。全部已在价格里才返回 True。没有拆分也是 True。"""
    reports = []
    if not splits:
        return True, reports
    flags = []
    for split in splits:
        prev, row = _neighbor(bars, split["date"])
        if prev is None or row is None or not prev.get("close") or not row.get("close"):
            raise R1bError(f"拆分日 {split['date']} 没有相邻收盘，不能判断是否已经复权")
        already = split_already_in_close(
            float(prev["close"]), float(row["close"]), float(split["numerator"]), float(split["denominator"]))
        flags.append(already)
        reports.append({
            "date": split["date"],
            "ratio": split.get("ratio") or f"{split['numerator']}:{split['denominator']}",
            "prev_close": prev["close"],
            "close": row["close"],
            "actual_ratio": float(row["close"]) / float(prev["close"]),
            "already_in_close": already,
        })
    if any(flags) and not all(flags):
        raise R1bError(f"同一代码的拆分日口径不一致：{reports}")
    return all(flags), reports


def build_us_adjusted(con, end: date, fetched_at: str, log: list[str]) -> list[dict]:
    rows = []
    basis_path = OUT / "us-split-basis.csv"
    basis = []
    for item in C.ETFS:
        code = item["code"]
        bars = [r for r in _read_raw(con, code) if r["date"] <= end.isoformat()]
        divs, splits = _events(con, code)
        divs = [r for r in divs if r["date"] <= end.isoformat()]
        splits = [r for r in splits if r["date"] <= end.isoformat()]
        in_price, reports = classify_splits(bars, splits)
        for report in reports:
            report["code"] = code
            basis.append(report)
        if not in_price:
            raise R1bError(f"{code} 的收盘没有包含拆分，本轮不按未复权公式重做，先停下来核对")
        adjusted = backward_total_return(bars, divs, splits, splits_in_price=True)
        stored = [{
            **bar, "source": "yahoo", "source_url": C.YAHOO.format(symbol=code),
            "method": "dividend_reinvest_splits_already_in_close", "filled": 0,
        } for bar in adjusted]
        _replace_series(con, code, "backward", stored, fetched_at)
        digest = bar_sha256(adjusted)
        log.append(f"us {code} backward rows={len(adjusted)} splits_in_price=yes div={len(divs)} sha={digest[:12]}")
        rows.append(_cov(
            market="US", container_id=item["container_id"], code=code,
            name=item["name"] + " 后复权", series_kind="bar", return_basis="total_return",
            currency="USD", source="yahoo", source_url=C.YAHOO.format(symbol=code),
            official_launch=item["inception"], gics_sector=item["sector"],
            gics_effective=item["gics_effective"], bars=adjusted, sha=digest, status="in_db",
            note=("Yahoo 收盘在拆分日没有缺口，拆分已在价格里，后复权只做分红再投资，不再乘拆分比。"
                  "原始收盘仍在 bars.adj=raw。")))
    _write_dicts(basis_path, ("code", "date", "ratio", "prev_close", "close", "actual_ratio", "already_in_close"), basis)
    log.append(f"us split basis {basis_path}")
    return rows


def _write_dicts(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _progress(log: list[str], message: str) -> None:
    log.append(message)
    path = Path("/tmp/r1b/progress.log")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def _chunks(start: date, end: date, days: int = 450):
    cur = start
    while cur <= end:
        stop = min(end, cur + timedelta(days=days - 1))
        yield cur, stop
        cur = stop + timedelta(days=1)


def _fetch_tencent_hfq(symbol: str, start: date, end: date) -> tuple[str, list[dict]]:
    """腾讯 hfqday。东财 fqt=2 这次被断开，后复权改走这条。一次最多约 400 根。"""
    rows = []
    name = ""
    for begin, stop in _chunks(start, end):
        param = f"{symbol},day,{begin.isoformat()},{stop.isoformat()},400,hfq"
        payload = None
        last = ""
        for attempt in range(2):
            try:
                payload = http.get_json(TENCENT_KLINE, {"param": param}, timeout=25)
                break
            except http.FetchError as exc:
                last = str(exc)
                time.sleep(1.0 + attempt)
        if payload is None:
            raise http.FetchError(last)
        if not isinstance(payload, dict) or payload.get("code") not in (0, "0"):
            raise http.FetchError(f"tencent {symbol} {begin} {str(payload)[:80]}")
        node = ((payload.get("data") or {}).get(symbol)) or {}
        if not isinstance(node, dict):
            node = {}
        qt = (node.get("qt") or {}).get(symbol)
        if isinstance(qt, list) and len(qt) > 1 and qt[1]:
            name = name or str(qt[1])
        rows.extend(parse_tencent_kline_rows(node.get("hfqday") or []))
        time.sleep(0.2)
    dedup = {row["date"]: row for row in rows if row["date"] <= end.isoformat()}
    return name, [dedup[day] for day in sorted(dedup)]


def fetch_hfq_all(con, end: date, fetched_at: str, log: list[str]) -> tuple[list[dict], dict[str, list[dict]]]:
    codes = [r[0] for r in con.execute(
        "SELECT DISTINCT code FROM bars WHERE source='tencent_etf' ORDER BY code")]
    coverage = []
    stored = {}
    for i, code in enumerate(codes, 1):
        symbol = U.fund_tencent(code)
        if not symbol:
            _progress(log, f"hfq {code} skip 不是场内基金代码")
            continue
        raw = _read_raw(con, code)
        raw = [r for r in raw if r.get("date") and r["date"] <= end.isoformat() and r.get("close")]
        if not raw:
            continue
        already = con.execute(
            "SELECT source FROM v4_series WHERE code=? AND kind='backward' LIMIT 1", (code,)).fetchone()
        if already and already[0] == "tencent_etf_hfq":
            bars = _read_series(con, code, "backward")
            stored[code] = bars
            coverage.append(_hfq_coverage(code, code, bars, bar_sha256(bars)))
            continue
        try:
            name, bars = _fetch_tencent_hfq(symbol, date.fromisoformat(raw[0]["date"]), end)
        except http.FetchError as exc:
            _progress(log, f"hfq {code} FAIL {exc}")
            coverage.append(_cov(
                market="CN", container_id=f"etf-{code}", code=code, name=code, series_kind="bar",
                return_basis="total_return", currency="CNY", source="tencent_etf_hfq",
                source_url=TENCENT_KLINE, bars=[], sha="", status="unavailable",
                note=f"v4-R1b 后复权取数失败：{exc}"[:240]))
            continue
        if not bars:
            _progress(log, f"hfq {code} empty")
            coverage.append(_kept_or_missing(con, code))
            continue
        batch = [{
            **bar, "source": "tencent_etf_hfq", "source_url": TENCENT_KLINE,
            "method": "tencent_hfq", "filled": 0,
        } for bar in bars]
        _replace_series(con, code, "backward", batch, fetched_at)
        stored[code] = bars
        digest = bar_sha256(bars)
        coverage.append(_hfq_coverage(code, name or code, bars, digest))
        if i % 10 == 0 or i == len(codes):
            _progress(log, f"hfq progress {i}/{len(codes)} last={code} rows={len(bars)} name={name}")
    return coverage, stored


def _kept_or_missing(con, code: str) -> dict:
    """腾讯没有 hfqday 时，保留已经入库的东财后复权；否则登记为取不到。"""
    row = con.execute(
        "SELECT source, source_url FROM v4_series WHERE code=? AND kind='backward' LIMIT 1",
        (code,)).fetchone()
    if row:
        bars = _read_series(con, code, "backward")
        return _cov(
            market="CN", container_id=f"etf-{code}", code=code, name=code, series_kind="bar",
            return_basis="total_return", currency="CNY", source=row["source"],
            source_url=row["source_url"] or TENCENT_KLINE, bars=bars, sha=bar_sha256(bars),
            status="in_db",
            note="腾讯没有 hfqday。这条是限流前拿到的东财 fqt=2，不覆盖原始收盘。")
    return _cov(
        market="CN", container_id=f"etf-{code}", code=code, name=code, series_kind="bar",
        return_basis="total_return", currency="CNY", source="tencent_etf_hfq",
        source_url=TENCENT_KLINE, bars=[], sha="", status="unavailable",
        note="腾讯没有返回 hfqday。东财 K 线接口本次连接被断开。没有把原始收盘当成后复权。")


def finalize_gaps(con, log: list[str] | None = None) -> list[str]:
    """补覆盖表里腾讯没有后复权、但东财序列还在的代码，以及完全取不到的代码。"""
    log = log if log is not None else []
    codes = [r[0] for r in con.execute(
        "SELECT DISTINCT code FROM bars WHERE source='tencent_etf' ORDER BY code")]
    extra = []
    audit_bars = {}
    for code in codes:
        have = con.execute(
            "SELECT source FROM v4_series WHERE code=? AND kind='backward' LIMIT 1", (code,)).fetchone()
        if have and have[0] == "tencent_etf_hfq":
            continue
        extra.append(_kept_or_missing(con, code))
        if have:
            audit_bars[code] = _read_series(con, code, "backward")
    if audit_bars:
        before = OUT / "adjust-audit.csv"
        detail_old = list(csv.DictReader(before.open(encoding="utf-8"))) if before.exists() else []
        summary_old = []
        summary_path = OUT / "adjust-audit-summary.csv"
        if summary_path.exists():
            summary_old = list(csv.DictReader(summary_path.open(encoding="utf-8")))
        detail, summary = [], []
        seen = {row["code"] for row in summary_old}
        audit_bars = {code: bars for code, bars in audit_bars.items() if code not in seen}
        for code, bars in audit_bars.items():
            raw = _read_raw(con, code)
            div_rows = [dict(r) for r in con.execute(
                "SELECT ex_date, amount, prev_close FROM cash_dividends WHERE code=? ORDER BY ex_date",
                (code,))]
            flagged, counts = _audit_one(raw, bars, div_rows)
            for row in flagged:
                row["code"] = code
                detail.append(row)
            summary.append({"code": code, **counts})
            log.append(f"audit kept {code} missed={counts['missed_action']} removed={counts['gap_removed_real']}")
        _write_dicts(before, ("code", "date", "kind", "raw_return", "hfq_return", "tr_return"), detail_old + detail)
        _write_dicts(summary_path,
                     ("code", "days", "gap_zeroed", "gap_matches_action", "gap_removed_real", "missed_action"),
                     summary_old + summary)
        spot_path = OUT / "adjust-spotcheck.csv"
        spots = list(csv.DictReader(spot_path.open(encoding="utf-8"))) if spot_path.exists() else []
        spotted = {row["code"] for row in spots}
        for code, bars in audit_bars.items():
            if code in spotted:
                continue
            spots.extend(_cn_spots(code, _read_raw(con, code), bars))
        _write_dicts(spot_path, ("code", "kind", "date", "raw_return", "adj_return", "continuous", "note"), spots)
    kept = sum(1 for row in extra if row["status"] == "in_db")
    missing = sum(1 for row in extra if row["status"] != "in_db")
    log.append(f"gaps kept_eastmoney={kept} unavailable={missing}")
    if extra:
        _append_coverage(extra)
    return log


def _append_coverage(extra: list[dict]) -> None:
    rows = []
    if IN.COVERAGE.exists():
        with IN.COVERAGE.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    drop = ("没有把原始收盘当成后复权", "限流前拿到的东财")
    rows = [row for row in rows if not any(token in (row.get("note") or "") for token in drop)]
    stamped = []
    for row in extra:
        row = dict(row)
        if not str(row.get("note") or "").startswith("v4-R1b"):
            row["note"] = ("v4-R1b " + (row.get("note") or "")).strip()
        stamped.append(row)
    IN.write_coverage(rows + stamped)


def _hfq_coverage(code: str, name: str, bars: list[dict], digest: str) -> dict:
    return _cov(
        market="CN", container_id=f"etf-{code}", code=code, name=name, series_kind="bar",
        return_basis="total_return", currency="CNY", source="tencent_etf_hfq",
        source_url=TENCENT_KLINE, bars=bars, sha=digest, status="in_db",
        note="腾讯 hfqday 后复权。分红再投资，拆分和份额折算在这条序列里处理。不覆盖原始收盘。")


def audit_adjusted(con, hfq: dict[str, list[dict]], log: list[str]) -> None:
    """对照 v3 total_return_close。只记单标的价格路径差，不汇总成组合。"""
    detail = []
    summary = []
    for code, bars in hfq.items():
        raw = _read_raw(con, code)
        div_rows = [dict(r) for r in con.execute(
            "SELECT ex_date, amount, prev_close FROM cash_dividends WHERE code=? ORDER BY ex_date",
            (code,))]
        flagged, counts = _audit_one(raw, bars, div_rows)
        for row in flagged:
            row["code"] = code
            detail.append(row)
        summary.append({"code": code, **counts})
    _write_dicts(OUT / "adjust-audit.csv",
                 ("code", "date", "kind", "raw_return", "hfq_return", "tr_return"), detail)
    missed = sum(r["missed_action"] for r in summary)
    removed = sum(r["gap_removed_real"] for r in summary)
    matched = sum(r["gap_matches_action"] for r in summary)
    log.append(f"audit etf={len(summary)} missed_action_days={missed} "
               f"gap_removed_real={removed} gap_matches_action={matched} "
               f"detail={OUT / 'adjust-audit.csv'}")
    _write_dicts(OUT / "adjust-audit-summary.csv",
                 ("code", "days", "gap_zeroed", "gap_matches_action", "gap_removed_real", "missed_action"),
                 summary)


def _audit_one(raw: list[dict], hfq: list[dict], div_rows: list[dict]) -> tuple[list[dict], dict]:
    hfq_close = {r["date"]: float(r["close"]) for r in hfq if r.get("close")}
    frame = pd.DataFrame(raw)
    if frame.empty:
        return [], {"days": 0, "gap_zeroed": 0, "gap_matches_action": 0,
                    "gap_removed_real": 0, "missed_action": 0}
    yields = dividend_yields(pd.DataFrame(div_rows)) if div_rows else {}
    level, gaps = total_return_close(frame, yields)
    gap_days = {ts.strftime("%Y-%m-%d") for ts in gaps}
    level_by = {ts.strftime("%Y-%m-%d"): float(val) for ts, val in level.items()}
    days = [r["date"] for r in raw if r.get("close") and float(r["close"]) > 0 and r["date"] in hfq_close]
    flagged = []
    counts = {"days": max(len(days) - 1, 0), "gap_zeroed": 0, "gap_matches_action": 0,
              "gap_removed_real": 0, "missed_action": 0}
    for prev_day, day in zip(days, days[1:]):
        raw_ret = float(_close_on(raw, day)) / float(_close_on(raw, prev_day)) - 1.0
        hfq_ret = hfq_close[day] / hfq_close[prev_day] - 1.0
        if prev_day not in level_by or day not in level_by or level_by[prev_day] == 0:
            continue
        tr_ret = level_by[day] / level_by[prev_day] - 1.0
        kind = ""
        if day in gap_days:
            counts["gap_zeroed"] += 1
            if abs(hfq_ret) < DIFF_LIMIT:
                kind = "gap_matches_action"
                counts["gap_matches_action"] += 1
            else:
                kind = "gap_removed_real"
                counts["gap_removed_real"] += 1
        elif abs(tr_ret - hfq_ret) >= DIFF_LIMIT:
            kind = "missed_action"
            counts["missed_action"] += 1
        if kind:
            flagged.append({
                "date": day, "kind": kind,
                "raw_return": f"{raw_ret:.6f}", "hfq_return": f"{hfq_ret:.6f}",
                "tr_return": f"{tr_ret:.6f}",
            })
    return flagged, counts


def _close_on(rows: list[dict], day: str) -> float:
    for row in rows:
        if row["date"] == day:
            return float(row["close"])
    raise KeyError(day)


def spot_checks(con, hfq: dict[str, list[dict]], log: list[str]) -> None:
    rows = []
    for item in C.ETFS:
        code = item["code"]
        raw = _read_raw(con, code)
        divs, splits = _events(con, code)
        adjusted = _read_series(con, code, "backward")
        if divs:
            rows.append(_us_spot(code, "dividend", divs[len(divs) // 2]["date"], raw, adjusted, divs))
        else:
            rows.append({"code": code, "kind": "dividend", "date": "", "note": "无分红日"})
        if splits:
            rows.append(_us_spot(code, "split", splits[0]["date"], raw, adjusted, divs))
        else:
            rows.append({"code": code, "kind": "split", "date": "", "note": "无拆分日"})
    for code, bars in sorted(hfq.items()):
        raw = _read_raw(con, code)
        rows.extend(_cn_spots(code, raw, bars))
    _write_dicts(OUT / "adjust-spotcheck.csv",
                 ("code", "kind", "date", "raw_return", "adj_return", "continuous", "note"), rows)
    bad = [r for r in rows if r.get("continuous") == "0"]
    log.append(f"spot {len(rows)} discontinuous={len(bad)} file={OUT / 'adjust-spotcheck.csv'}")


def _read_series(con, code: str, kind: str) -> list[dict]:
    return [dict(r) for r in con.execute(
        "SELECT date, open, high, low, close, volume FROM v4_series WHERE code=? AND kind=? ORDER BY date",
        (code, kind))]


def _us_spot(code, kind, day, raw, adjusted, divs) -> dict:
    prev_r, row_r = _neighbor(raw, day)
    prev_a, row_a = _neighbor(adjusted, day)
    if not prev_r or not row_r or not prev_a or not row_a:
        return {"code": code, "kind": kind, "date": day, "continuous": "0", "note": "缺相邻K线"}
    raw_ret = float(row_r["close"]) / float(prev_r["close"]) - 1.0
    adj_ret = float(row_a["close"]) / float(prev_a["close"]) - 1.0
    dividend = 0.0
    for item in divs:
        if item["date"] == day:
            dividend = float(item["amount"])
    expected = raw_ret + (dividend / float(prev_r["close"]) if prev_r["close"] else 0.0)
    # 拆分已在收盘里：后复权收益应等于原始收益加分红率，拆分日不应再出现拆分缺口。
    # 只核对有没有把拆分再乘一次。当天行情本身可以大。
    continuous = abs(adj_ret - expected) < 1e-6
    return {
        "code": code, "kind": kind, "date": day,
        "raw_return": f"{raw_ret:.6f}", "adj_return": f"{adj_ret:.6f}",
        "continuous": "1" if continuous else "0",
        "note": f"expected={expected:.6f}",
    }


def _cn_spots(code: str, raw: list[dict], hfq: list[dict]) -> list[dict]:
    hfq_close = {r["date"]: float(r["close"]) for r in hfq if r.get("close")}
    raw_close = {r["date"]: float(r["close"]) for r in raw if r.get("close") and float(r["close"]) > 0}
    days = [d for d in raw_close if d in hfq_close]
    wedges = []
    cliffs = []
    for prev_day, day in zip(days, days[1:]):
        raw_ret = raw_close[day] / raw_close[prev_day] - 1.0
        hfq_ret = hfq_close[day] / hfq_close[prev_day] - 1.0
        wedge = hfq_ret - raw_ret
        if 0.001 < wedge < 0.08 and abs(raw_ret) < 0.12:
            wedges.append((wedge, day, raw_ret, hfq_ret))
        if abs(raw_ret) >= 0.25 and abs(hfq_ret) < 0.15:
            cliffs.append((abs(raw_ret), day, raw_ret, hfq_ret))
    out = []
    if wedges:
        _, day, raw_ret, hfq_ret = max(wedges)
        out.append({"code": code, "kind": "dividend", "date": day,
                    "raw_return": f"{raw_ret:.6f}", "adj_return": f"{hfq_ret:.6f}",
                    "continuous": "1" if abs(hfq_ret) < 0.25 else "0",
                    "note": "后复权相对原始收盘多出的收益，当作分红日"})
    else:
        out.append({"code": code, "kind": "dividend", "date": "", "continuous": "", "note": "无分红日",
                    "raw_return": "", "adj_return": ""})
    if cliffs:
        _, day, raw_ret, hfq_ret = max(cliffs)
        out.append({"code": code, "kind": "split", "date": day,
                    "raw_return": f"{raw_ret:.6f}", "adj_return": f"{hfq_ret:.6f}",
                    "continuous": "1" if abs(hfq_ret) < 0.15 else "0",
                    "note": "原始收盘有折算缺口，后复权收益连续"})
    else:
        out.append({"code": code, "kind": "split", "date": "", "continuous": "", "note": "无拆分日",
                    "raw_return": "", "adj_return": ""})
    return out


def build_fx(con, end: date, fetched_at: str, log: list[str]) -> list[dict]:
    folder = ROOT / "outputs" / "data" / "v4-r1b"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "safe-rmb-mid.xlsx"
    raw = http.get(SAFE_FILE, headers={"Referer": SAFE_URL}, timeout=60)
    target.write_bytes(raw)
    file_sha = hashlib.sha256(raw).hexdigest()
    log.append(f"safe xlsx sha256={file_sha} bytes={len(raw)}")
    table = parse_safe_mid(target)
    safe_2005 = [r for r in table if r["date"].startswith("2005-")]
    missing_hkd = [r["date"] for r in safe_2005 if r["hkd_per_hundred"] is None and r["usd_per_hundred"] is not None]
    if missing_hkd:
        log.append(f"safe 2005 港元空缺 {len(missing_hkd)} 天，没有另找港币兑美元，留给 20 日均值补齐")
    else:
        log.append("safe 2005 美元和港元都有中间价，不用港币兑美元换算")
    sse = [r[0] for r in con.execute(
        "SELECT date FROM calendar WHERE date>='2005-01-01' AND date<'2006-01-04' ORDER BY date")]
    hk = [r[0] for r in con.execute(
        "SELECT date FROM bars WHERE code='HSI' AND adj='raw' AND date>='2005-01-01' AND date<'2006-01-04' ORDER BY date")]
    coverage = []
    for code, column, pair in (("USDCNY", "usd_per_hundred", "USD/CNY"), ("HKDCNY", "hkd_per_hundred", "HKD/CNY")):
        official = []
        for row in safe_2005:
            quote = row[column]
            if quote is None:
                continue
            official.append((row["date"], safe_quote_to_cny(quote)))
        copied = [(r["date"], float(r["close"])) for r in con.execute(
            "SELECT date, close FROM bars WHERE code=? AND adj='raw' AND date>=? AND date<=? ORDER BY date",
            (code, FX_EXISTING_FROM, end.isoformat()))]
        # 用 2006 年初的官方点给 2005 年的缺口做参照，本身不重复写入。
        anchor = copied[:20]
        filled = fill_backward(official + anchor, sse + hk, 20)
        extra = [r for r in filled if r["filled"] == 1 and r["date"] < FX_EXISTING_FROM]
        series = []
        for day, close in official:
            series.append({"date": day, "close": close, "filled": 0, "source": "safe",
                           "source_url": SAFE_URL, "method": "official_mid_per_100_div_100"})
        for row in extra:
            series.append({"date": row["date"], "close": row["close"], "filled": 1, "source": "v4_fill",
                           "source_url": SAFE_URL, "method": "fill_mean_next_20"})
        for day, close in copied:
            series.append({"date": day, "close": close, "filled": 0, "source": "chinamoney",
                           "source_url": C.CHINAMONEY, "method": "copied_existing_bar"})
        series.sort(key=lambda item: item["date"])
        _replace_series(con, code, "fx", series, fetched_at)
        digest = series_sha256(
            [{"date": r["date"], "close": r["close"], "filled": r["filled"]} for r in series],
            ("date", "close", "filled"))
        log.append(f"fx {code} official_2005={len(official)} filled={len(extra)} "
                   f"copied={len(copied)} sha={digest[:12]}")
        coverage.append(_cov(
            market="FX", container_id=f"fx-{code.lower()}-ext", code=code,
            name=f"{pair} 中间价（含 2005）", series_kind="fx", return_basis="fx",
            currency="CNY", source="safe", source_url=SAFE_URL,
            first_override=series[0]["date"], last_override=series[-1]["date"],
            n_override=len(series), sha=digest, status="in_db",
            note=(f"2005 年来自外管局历史中间价工作簿（100 外币兑人民币，已除以 100），文件 SHA256 {file_sha}。"
                  f"2006-01-04 起复制库内 chinamoney，不改 bars。补齐 {len(extra)} 天。"
                  "中国货币网 CcprHisNew 的 2005 年仍是空的。")))
    _write_dicts(OUT / "fx-fill.csv", ("code", "date", "close", "method"), [
        {"code": code, "date": r["date"], "close": r["close"], "method": r["method"]}
        for code in ("USDCNY", "HKDCNY")
        for r in _read_fx_filled(con, code)
    ])
    return coverage


def _read_fx_filled(con, code: str) -> list[dict]:
    return [dict(r) for r in con.execute(
        "SELECT date, close, method FROM v4_series WHERE code=? AND kind='fx' AND filled=1 ORDER BY date",
        (code,))]


def build_otc(con, end: date, fetched_at: str, log: list[str]) -> tuple[list[dict], list[dict]]:
    raw = http.get(RANK_URL, {
        "op": "ph", "dt": "kf", "ft": "zs", "rs": "", "gs": "0", "sc": "clrq", "st": "asc",
        "pi": "1", "pn": "5000", "dx": "1",
    }, headers={"Referer": "https://fund.eastmoney.com/data/fundranking.html"}, timeout=40)
    candidates = parse_rank_index_funds(raw.decode("utf-8", "replace"), OTC_CUTOFF)
    log.append(f"otc rank inception<={OTC_CUTOFF} n={len(candidates)}")
    chosen = []
    seen_track = {}
    for cand in candidates:
        page = JBGK.format(code=cand["code"])
        try:
            html = http.get(page, headers={"Referer": "https://fundf10.eastmoney.com/"}, timeout=20)
            info = parse_jbgk(html.decode("utf-8", "replace"))
        except (http.FetchError, ValueError) as exc:
            log.append(f"otc jbgk {cand['code']} FAIL {exc}")
            time.sleep(0.1)
            continue
        tracked = info["tracked_index"]
        seen_track.setdefault(tracked, []).append(cand["code"])
        if tracked in EXACT_INDEX:
            chosen.append({**cand, **info, "maps_to": EXACT_INDEX[tracked], "near": "", "page": page})
        elif tracked in NEAR_INDEX:
            maps, note = NEAR_INDEX[tracked]
            chosen.append({**cand, **info, "maps_to": maps, "near": note, "page": page})
        time.sleep(0.1)
    log.append("otc tracked indexes: " + "; ".join(f"{k}={','.join(v)}" for k, v in sorted(seen_track.items())))
    coverage = []
    listings = []
    found = {item["maps_to"] for item in chosen}
    for item in chosen:
        nav_url = PING.format(code=item["code"])
        try:
            body = http.get(nav_url, headers={"Referer": f"https://fund.eastmoney.com/{item['code']}.html"}, timeout=40)
            points = parse_pingzhongdata(body.decode("utf-8", "replace"), end)
            log.append(f"otc nav check {item['code']} {_nav_check(points)}")
            nav = compound_adjusted_nav(points)
        except (http.FetchError, ValueError) as exc:
            log.append(f"otc nav {item['code']} FAIL {exc}")
            time.sleep(0.1)
            continue
        if not nav:
            log.append(f"otc nav {item['code']} empty")
            continue
        enhanced = 1 if "增强" in (item.get("name") or "") or "增强" in (item.get("short_name") or "") else 0
        note = item["near"]
        if enhanced:
            note = (note + " " if note else "") + "指数增强，跟踪误差不是纯指数基金。"
        if "联接" in (item.get("name") or "") or "联接" in (item.get("short_name") or ""):
            note = (note + " " if note else "") + "名称含联接，概况页跟踪标的仍是上面写的指数。"
        batch = [{
            "date": r["date"], "close": r["close"], "unit_nav": r["unit_nav"], "accum_nav": r["accum_nav"],
            "filled": 0, "source": "eastmoney_pingzhongdata", "source_url": nav_url,
            "method": "equity_return_compound",
        } for r in nav]
        _replace_series(con, item["code"], "otc_nav", batch, fetched_at)
        digest = series_sha256(
            [{"date": r["date"], "unit_nav": r["unit_nav"], "accum_nav": r["accum_nav"], "close": r["close"]}
             for r in nav],
            ("date", "unit_nav", "accum_nav", "close"))
        with con:
            con.execute("DELETE FROM v4_listing WHERE code=?", (item["code"],))
            con.execute(
                """INSERT INTO v4_listing
                   (code, name, container_id, maps_to, tracked_index, inception, enhanced,
                    source_url, sha256, note, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item["code"], item.get("name") or item["name"], f"otc-{item['code']}", item["maps_to"],
                 item["tracked_index"], item.get("inception") or item["inception"], enhanced,
                 item["page"], digest, note.strip(), fetched_at))
        listings.append({
            "code": item["code"], "name": item.get("name") or item["short_name"],
            "container_id": f"otc-{item['code']}", "maps_to": item["maps_to"],
            "tracked_index": item["tracked_index"], "inception": item.get("inception") or item["inception"],
            "source_url": item["page"], "sha256": digest, "note": note.strip(),
            "first_date": nav[0]["date"], "last_date": nav[-1]["date"], "rows": len(nav),
        })
        coverage.append(_cov(
            market="CN", container_id=f"otc-{item['code']}", code=item["code"],
            name=item.get("name") or item["short_name"], series_kind="nav", return_basis="total_return",
            currency="CNY", source="eastmoney_pingzhongdata", source_url=nav_url,
            official_launch=item.get("inception") or item["inception"],
            bars=[{"date": r["date"], "open": None, "high": None, "low": None, "close": r["close"], "volume": None}
                  for r in nav],
            sha=digest, status="in_db",
            note=(f"场外基金。跟踪「{item['tracked_index']}」，对应容器 {item['maps_to']}。"
                  f"复权净值由日增长率连乘。{note} 不登记申赎费和到账天数。").strip()))
        log.append(f"otc {item['code']} {item['maps_to']} {item['tracked_index']} rows={len(nav)}")
        time.sleep(0.1)
    for container, name in CONTAINER_NAME.items():
        if container in found:
            continue
        coverage.append(_cov(
            market="CN", container_id=f"otc-missing-{container}", code="",
            name=f"{name} 场外指数基金", series_kind="nav", return_basis="total_return",
            currency="CNY", source="eastmoney", source_url=RANK_URL,
            bars=[], sha="", status="unavailable",
            note=("2006–2011 已成立的开放式指数基金里，没有跟踪该指数的产品。没有用别的指数代替。"
                  + REJECTED.get(container, ""))))
        log.append(f"otc missing {container}")
    return coverage, listings


def _nav_check(points: list[dict]) -> str:
    """分红日的日增长率应更接近「单位净值变动加分红」，而不是只看单位净值。"""
    for prev, cur in zip(points, points[1:]):
        dividend = float(cur.get("dividend") or 0.0)
        if dividend <= 0 or not prev.get("unit_nav") or cur.get("equity_return") is None:
            continue
        prev_unit = float(prev["unit_nav"])
        if prev_unit <= 0 or cur.get("unit_nav") is None:
            continue
        crude = (float(cur["unit_nav"]) - prev_unit) / prev_unit * 100.0
        gross = (float(cur["unit_nav"]) + dividend - prev_unit) / prev_unit * 100.0
        got = float(cur["equity_return"])
        closer = "unit+div" if abs(got - gross) <= abs(got - crude) else "unit_only"
        return f"{cur['date']} equity={got:.4f} crude={crude:.4f} gross={gross:.4f} closer={closer}"
    return "no published dividend in the nav file"


def append_universe(listings: list[dict]) -> None:
    text = IN.UNIVERSE.read_text(encoding="utf-8") if IN.UNIVERSE.exists() else ""
    marker = "# v4-R1b 场外基金。"
    if marker in text:
        text = text[:text.index(marker)].rstrip() + "\n"
    lines = [text.rstrip(), "", marker, "# python -m src.v4.data r1b 写出。类型是场外基金。不登记申赎费。", ""]
    for item in listings:
        lines.extend([
            "[[container]]",
            f'id = "{item["container_id"]}"',
            'market = "CN"',
            'instrument_type = "otc_fund"',
            f'name = "{IN._toml_escape(item["name"])}"',
            f'code = "{item["code"]}"',
            f'maps_to = "{item["maps_to"]}"',
            f'tracked_index = "{IN._toml_escape(item["tracked_index"])}"',
            'return_basis = "total_return"',
            'currency = "CNY"',
            'source = "eastmoney_pingzhongdata"',
            f'source_url = "{item["source_url"]}"',
            'status = "in_db"',
            f'official_launch = "{item["inception"]}"',
            f'first_date = "{item["first_date"]}"',
            f'last_date = "{item["last_date"]}"',
            f'rows = "{item["rows"]}"',
            f'sha256 = "{item["sha256"]}"',
            f'note = "{IN._toml_escape(item["note"])}"',
            "",
        ])
    IN.UNIVERSE.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def merge_coverage(extra: list[dict]) -> None:
    existing = []
    if IN.COVERAGE.exists():
        with IN.COVERAGE.open(encoding="utf-8", newline="") as handle:
            existing = [row for row in csv.DictReader(handle) if not str(row.get("note", "")).startswith("v4-R1b")]
    # 本轮行都带 v4-R1b 前缀，重复运行时换掉旧的一轮。
    stamped = []
    for row in extra:
        row = dict(row)
        note = row.get("note") or ""
        if not note.startswith("v4-R1b"):
            row["note"] = ("v4-R1b " + note).strip()
        stamped.append(row)
    IN.write_coverage(existing + stamped)


def _cov(**kwargs) -> dict:
    bars = kwargs.pop("bars", None)
    sha = kwargs.pop("sha", "")
    status = kwargs.pop("status", "")
    first = kwargs.pop("first_override", None)
    last = kwargs.pop("last_override", None)
    n_override = kwargs.pop("n_override", None)
    if bars is not None and n_override is None:
        n_override = len(bars)
        first = bars[0]["date"] if bars else ""
        last = bars[-1]["date"] if bars else ""
        if not sha and bars:
            sha = bar_sha256(bars)
        if not status:
            status = "in_db" if bars else "unavailable"
    row = IN._coverage_row(
        first_date=first or "", last_date=last or "", rows=n_override or 0,
        sha256=sha, status=status, **kwargs)
    return row


def check_hsf(con, log: list[str]) -> None:
    """恒生公司历史日线是付费订阅。页面 404 时，用 Yahoo 的恒生金融指数做对照，不改库内 HSF。"""
    targets = ("1997-10-28", "2013-12-30")
    local = {r["date"]: dict(r) for r in con.execute(
        """SELECT date, open, high, low, close FROM bars
           WHERE code='HSF' AND adj='raw' AND date IN
           ('1997-10-27','1997-10-28','1997-10-29','2013-12-27','2013-12-30','2013-12-31')""")}
    probes = []
    for url in (
        "https://www.hsi.com.hk/static/uploads/contents/en/indexes/report/hsf.csv",
        "https://www.hsi.com.hk/data/eng/indexes/hsf/chart.json",
        "https://www.hsi.com.hk/eng/indexes/all-indexes/hsf",
        "https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/factsheets/hsf.pdf",
    ):
        try:
            body = http.get(url, headers={"Referer": "https://www.hsi.com.hk/"}, timeout=20)
            probes.append({"url": url, "bytes": len(body), "error": "", "head": repr(body[:120])})
        except http.FetchError as exc:
            probes.append({"url": url, "bytes": 0, "error": str(exc)[:180], "head": ""})
    yahoo = {}
    try:
        from .ingest import _yahoo
        for start, stop in ((date(1997, 10, 20), date(1997, 11, 5)), (date(2013, 12, 20), date(2014, 1, 6))):
            parsed = _yahoo("%5EHSNF", start, stop)
            for row in parsed["bars"]:
                yahoo[row["date"]] = row["close"]
        log.append(f"hsf yahoo ^HSNF name=HANG SENG FINANCE INDEX points={len(yahoo)}")
    except Exception as exc:  # noqa: BLE001 — 对照失败也留下，不改 HSF
        log.append(f"hsf yahoo probe FAIL {exc}")
    rows = []
    for day in targets:
        got = local.get(day)
        other = yahoo.get(day)
        same = ""
        if got and other:
            same = "1" if abs(float(got["close"]) - float(other)) < 0.02 else "0"
        note = ("恒生公司日线网址返回 404，历史日线仍是付费订阅，没有官方收盘可写入。"
                "Yahoo ^HSNF 名称是 HANG SENG FINANCE INDEX，用来对照腾讯，不覆盖 bars。")
        if day == "2013-12-30":
            note += " 这一天收盘相对前后交易日是连续的；HSU、HSC 缺的是它们自己的日子。"
        if day == "1997-10-28":
            note += " 腾讯与 Yahoo 同一跳空和次日回升，不是腾讯单方坏点。亚洲金融危机那一周，不把收盘改成空值。"
        rows.append({
            "date": day,
            "tencent_close": "" if not got else got["close"],
            "yahoo_hsnf_close": "" if other is None else other,
            "abs_diff_under_0.02": same,
            "official_close": "",
            "note": note,
        })
    _write_dicts(OUT / "hsf-check.csv",
                 ("date", "tencent_close", "yahoo_hsnf_close", "abs_diff_under_0.02", "official_close", "note"),
                 rows)
    _write_dicts(OUT / "hsf-probes.csv", ("url", "bytes", "error", "head"), probes)
    hsi = con.execute(
        "SELECT close FROM bars WHERE code='HSI' AND adj='raw' AND date='2013-12-30'").fetchone()
    log.append(f"hsf 2013-12-30 HSI close={None if hsi is None else hsi['close']} "
               "（恒生指数开市，不是金融分类的官方收盘）")


def run(con, end: date = C.END) -> list[str]:
    if end > C.END:
        raise R1bError(f"截止日 {end} 晚于登记上限 {C.END}")
    ensure(con)
    fetched_at = DB.now()
    log: list[str] = []
    skip = {(code, ZERO_DAY) for code in ZERO_CODES}
    before_fp = bars_except_fingerprint(con, skip)
    before_n = con.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
    http.LOG.clear()
    run_id = DB.start_run(con, "backfill", end=end, args={
        "job": "v4-r1b-ingest",
        "portfolio_returns": False,
        "overwrites_existing_bars": False,
        "nulls_zero_close": list(ZERO_CODES),
    })
    try:
        log.extend(null_zero_closes(con))
        after_fp = bars_except_fingerprint(con, skip)
        after_n = con.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
        if before_fp != after_fp or before_n != after_n:
            raise R1bError("除 6 个 0 收盘以外，bars 发生了变化，停止")
        log.append(f"bars unchanged except {ZERO_DAY} zeros rows={after_n}")
        extra = []
        extra.extend(build_us_adjusted(con, end, fetched_at, log))
        hfq_rows, hfq = fetch_hfq_all(con, end, fetched_at, log)
        extra.extend(hfq_rows)
        audit_adjusted(con, hfq, log)
        spot_checks(con, hfq, log)
        extra.extend(build_fx(con, end, fetched_at, log))
        otc_rows, listings = build_otc(con, end, fetched_at, log)
        extra.extend(otc_rows)
        append_universe(listings)
        merge_coverage(extra)
        check_hsf(con, log)
        if bars_except_fingerprint(con, skip) != before_fp:
            raise R1bError("写入新序列之后 bars 被改动")
        DB.write_requests(con, run_id, list(http.LOG))
        DB.finish_run(con, run_id, "ok")
    except Exception:
        DB.finish_run(con, run_id, "error")
        raise
    log.append(f"run_id {run_id}")
    return log


# 港币换算留在模块里，供测试确认公式没有写进取数主路径以外的隐式常数。
def hkd_from_peg(usd_cny: float, hkd_per_usd: float) -> float:
    return cny_per_hkd(usd_cny, hkd_per_usd)
