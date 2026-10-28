"""把 v4-R1 新序列写入 market.sqlite。

只插入库里还没有的 code。已有 code 原样留下，不更新、不删除。
不计算收益率，不复权。
"""
from __future__ import annotations

import csv
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from src.data import db as DB
from src.data import http
from src.data import sources as S
from src.data import store
from src.data.date_constraints import date_rule

from . import catalog as C
from .parse import bar_sha256, parse_chinamoney, parse_yahoo_chart, series_sha256

ROOT = Path(__file__).resolve().parents[3]
COVERAGE = ROOT / "results" / "v4" / "inventory" / "coverage.csv"
SPOT = ROOT / "results" / "v4" / "inventory" / "spotcheck.csv"
CROSS = ROOT / "results" / "v4" / "inventory" / "crosscheck.csv"
UNIVERSE = ROOT / "config" / "v4" / "universe.toml"
START = date(1990, 1, 1)
HK_START = date(1984, 1, 13)
FX_START = date(2005, 1, 1)

COLUMNS = (
    "market", "container_id", "code", "name", "series_kind", "return_basis", "currency",
    "source", "source_url", "official_launch", "base_date", "gics_sector", "gics_effective",
    "first_date", "last_date", "rows", "sha256", "status", "note",
)
SPOT_DATES = ("2000-01-04", "2008-01-02", "2015-01-05", "2020-01-02", "2026-09-30")
FX_SPOT_DATES = ("2006-01-04", "2008-01-02", "2015-01-05", "2020-01-02", "2026-09-30")
CROSS_DATES = ("2026-01-05", "2026-03-31", "2026-06-30", "2026-08-31", "2026-09-30")
CROSS_CODES = ("XLB", "XLK", "XLF")

_EVENT = f"""
CREATE TABLE IF NOT EXISTS v4_event (
    code        TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('dividend', 'split')),
    ex_date     TEXT NOT NULL CHECK ({date_rule('v4_event', 'ex_date')}),
    amount      REAL,
    ratio_num   REAL,
    ratio_den   REAL,
    ratio       TEXT NOT NULL DEFAULT '',
    currency    TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL,
    source_url  TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (code, kind, ex_date)
) WITHOUT ROWID
"""


class IngestError(RuntimeError):
    pass


def ensure(con) -> None:
    con.execute(_EVENT)
    con.commit()


def _guard(con) -> dict:
    out = {
        "universe": con.execute("SELECT COUNT(*) FROM universe").fetchone()[0],
        "coverage": con.execute("SELECT COUNT(*) FROM coverage").fetchone()[0],
    }
    if _table(con, "cash_dividends"):
        out["cash_dividends"] = con.execute("SELECT COUNT(*) FROM cash_dividends").fetchone()[0]
    for code in C.SENTINELS:
        row = con.execute(
            "SELECT COUNT(*), MIN(date), MAX(date), MIN(source) FROM bars WHERE code=? AND adj='raw'",
            (code,)).fetchone()
        out[code] = tuple(row)
    return out


def _table(con, name: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _source_of(con, code: str) -> str | None:
    rows = [r[0] for r in con.execute("SELECT DISTINCT source FROM bars WHERE code=?", (code,))]
    if not rows:
        return None
    if len(rows) != 1:
        raise IngestError(f"{code} 已有多个来源 {rows}")
    return rows[0]


def put_bars(con, code: str, route: str, rows: list[dict], fetched_at: str) -> str:
    """新 code 整段写入。已有同一来源则不改字节。别的来源拒绝。"""
    if code in C.SENTINELS or code in {"USDCNY"}:
        raise IngestError(f"拒绝改写已有序列 {code}")
    src = _source_of(con, code)
    if src is None:
        if not rows:
            return "empty"
        store.replace(con, code, route, rows, fetched_at)
        return "inserted"
    if src != route:
        raise IngestError(f"{code} 已有来源 {src}，拒绝写成 {route}")
    return "reused"


def put_events(con, code: str, kind: str, rows: list[dict], *, currency: str, source: str,
               source_url: str, fetched_at: str) -> str:
    have = con.execute("SELECT COUNT(*) FROM v4_event WHERE code=? AND kind=?", (code, kind)).fetchone()[0]
    if have:
        return "reused"
    if not rows:
        return "empty"
    with con:
        con.executemany(
            """INSERT INTO v4_event
               (code, kind, ex_date, amount, ratio_num, ratio_den, ratio, currency, source, source_url, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(code, kind, r["date"], r.get("amount"), r.get("numerator"), r.get("denominator"),
              r.get("ratio") or "", currency, source, source_url, fetched_at) for r in rows])
    return "inserted"


def _yahoo(symbol: str, start: date, end: date) -> dict:
    p1 = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    p2 = int(datetime(end.year, end.month, end.day, tzinfo=timezone.utc).timestamp()) + 86400
    payload = http.get_json(
        C.YAHOO.format(symbol=symbol),
        {"period1": p1, "period2": p2, "interval": "1d", "events": "div,splits"})
    return parse_yahoo_chart(payload, start, end)


def _drop_before(parsed: dict, not_before: str) -> int:
    dropped = sum(1 for r in parsed["bars"] if r["date"] < not_before)
    parsed["bars"] = [r for r in parsed["bars"] if r["date"] >= not_before]
    parsed["dividends"] = [r for r in parsed["dividends"] if r["date"] >= not_before]
    parsed["splits"] = [r for r in parsed["splits"] if r["date"] >= not_before]
    return dropped


def fetch_etf(con, item: dict, end: date, fetched_at: str, log: list[str]) -> None:
    code = item["code"]
    if _source_of(con, code) == "yahoo":
        log.append(f"etf {code} reused")
        return
    url = C.YAHOO.format(symbol=code)
    try:
        parsed = _yahoo(code, START, end)
    except (http.FetchError, ValueError) as exc:
        log.append(f"etf {code} FAIL {exc}")
        return
    dropped = _drop_before(parsed, item["inception"])
    status = put_bars(con, code, "yahoo", parsed["bars"], fetched_at)
    put_events(con, code, "dividend", parsed["dividends"], currency=parsed["currency"] or "USD",
               source="yahoo", source_url=url, fetched_at=fetched_at)
    put_events(con, code, "split", parsed["splits"], currency="", source="yahoo",
               source_url=url, fetched_at=fetched_at)
    log.append(f"etf {code} {status} bars={len(parsed['bars'])} div={len(parsed['dividends'])} "
               f"split={len(parsed['splits'])} dropped_before_inception={dropped} name={parsed['name']}")
    time.sleep(0.15)


def fetch_sp_price(con, end: date, fetched_at: str, log: list[str]) -> None:
    item = C.SP_PRICE_AVAILABLE
    if _source_of(con, item["code"]) == "yahoo":
        log.append(f"sp {item['code']} reused")
        return
    url = C.YAHOO.format(symbol=item["yahoo"])
    try:
        parsed = _yahoo(item["yahoo"], START, end)
    except (http.FetchError, ValueError) as exc:
        log.append(f"sp {item['code']} FAIL {exc}")
        return
    # 指数没有分红事件。Yahoo 若附带空 events，不写入。
    status = put_bars(con, item["code"], "yahoo", parsed["bars"], fetched_at)
    log.append(f"sp {item['code']} {status} bars={len(parsed['bars'])} name={parsed['name']} basis=price")


def fetch_hk(con, end: date, fetched_at: str, log: list[str]) -> None:
    for item in C.HSI_SUB:
        for code, symbol, basis in (
            (item["code"], item["tencent"], "price"),
            (item["tr_code"], item["tr_tencent"], "total_return"),
        ):
            if _source_of(con, code) == "tencent_hk_index":
                log.append(f"hk {code} reused")
                continue
            try:
                got = S.fetch_tencent(symbol, HK_START, end)
            except http.FetchError as exc:
                log.append(f"hk {code} FAIL {exc}")
                continue
            rows = [r for r in got.rows if r["close"] and r["close"] > 0]
            status = put_bars(con, code, "tencent_hk_index", rows, fetched_at)
            log.append(f"hk {code} {status} bars={len(rows)} name={got.name} basis={basis}")


def _fx_year(pair: str, year: int, end: date) -> list[dict]:
    start = date(year, 1, 1)
    stop = min(date(year, 12, 31), end)
    params = {"startDate": start.isoformat(), "endDate": stop.isoformat(),
              "currency": pair, "pageNum": "1", "pageSize": "500"}
    # 参数放在正文里。写进 URL 时这个接口返回 403。
    text = http.post(C.CHINAMONEY, urlencode(params).encode(), timeout=30, headers={
        "Referer": "https://www.chinamoney.com.cn/",
        "Origin": "https://www.chinamoney.com.cn/",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json",
    })
    payload = json.loads(text)
    total = int(((payload.get("data") or {}).get("total") or 0))
    got = len(payload.get("records") or [])
    if total > got:
        raise IngestError(f"{pair} {year} total={total} 超过本页 {got}，没有翻页")
    return parse_chinamoney(payload, pair, start, stop)


def fetch_fx(con, end: date, fetched_at: str, log: list[str]) -> None:
    check = _fx_year("USD/CNY", 2006, date(2006, 1, 4))
    known = con.execute(
        "SELECT close FROM bars WHERE code='USDCNY' AND adj='raw' AND date='2006-01-04'").fetchone()
    if not known:
        raise IngestError("库里没有 USDCNY 2006-01-04，无法核对解析")
    got = {r["date"]: r["close"] for r in check}
    if "2006-01-04" not in got:
        raise IngestError(f"USD/CNY 核对日没返回 2006-01-04：{sorted(got)}")
    if round(got["2006-01-04"], 4) != round(float(known[0]), 4):
        raise IngestError(f"USD/CNY 解析 {got['2006-01-04']} 与库内 {known[0]} 不一致，停止写入 HKD")
    log.append(f"fx parser check USDCNY 2006-01-04 {known[0]} ok")
    rows = []
    for year in range(FX_START.year, end.year + 1):
        part = _fx_year("HKD/CNY", year, end)
        rows.extend(part)
        time.sleep(0.15)
    by = {}
    for row in rows:
        by[row["date"]] = row
    ordered = [by[day] for day in sorted(by)]
    status = put_bars(con, "HKDCNY", "chinamoney", ordered, fetched_at)
    log.append(f"fx HKDCNY {status} bars={len(ordered)} "
               f"{ordered[0]['date'] if ordered else '-'} {ordered[-1]['date'] if ordered else '-'}")


def _read_bars(con, code: str) -> list[dict]:
    return [dict(r) for r in con.execute(
        "SELECT date, open, high, low, close, volume FROM bars WHERE code=? AND adj='raw' ORDER BY date",
        (code,))]


def _read_events(con, code: str, kind: str) -> list[dict]:
    cols = "ex_date AS date, amount, ratio_num AS numerator, ratio_den AS denominator, ratio"
    return [dict(r) for r in con.execute(
        f"SELECT {cols} FROM v4_event WHERE code=? AND kind=? ORDER BY ex_date", (code, kind))]


def _on_or_after(rows: list[dict], day: str) -> dict | None:
    for row in rows:
        if row["date"] >= day:
            return row
    return None


def _coverage_row(**kwargs) -> dict:
    row = {key: "" for key in COLUMNS}
    row.update({k: "" if v is None else str(v) for k, v in kwargs.items()})
    return row


def build_coverage(con) -> list[dict]:
    rows = []
    for item in C.ETFS:
        code = item["code"]
        bars = _read_bars(con, code)
        divs = _read_events(con, code, "dividend")
        splits = _read_events(con, code, "split")
        url = C.YAHOO.format(symbol=code)
        note = (f"未复权收盘。跟踪有上限的 Select Sector 指数，不是无上限的标普500行业指数。"
                f"GICS {item['sector']}（{item['gics']}）。上市日按 {item['inception']} 截断。")
        if item["gics_effective"] == C.RE_EFFECTIVE:
            note += " 房地产于 2016-08-31 美东收盘后从金融业拆出。"
        if item["gics_effective"] == C.COMM_EFFECTIVE:
            note += " 通信服务于 2018-09-28 美东收盘后在 GICS Direct 生效；标普指数在 2018-09-24 开盘调整。"
        if splits:
            note += " 拆分 " + ",".join(f"{s['date']} {s['ratio'] or s['numerator']}" for s in splits) + "。"
        rows.append(_bar_record("US", item["container_id"], code, item["name"], "price", "USD", "yahoo", url,
                                item["inception"], "", item["sector"], item["gics_effective"], bars, note))
        rows.append(_event_record("US", item["container_id"], code, item["name"] + " 现金分红", "dividend",
                                  "cash_dividend", "USD", "yahoo", url, item["inception"], item["sector"],
                                  item["gics_effective"], divs, ("date", "amount"), "除息日与每股金额，未计入复权价。"))
        rows.append(_event_record("US", item["container_id"], code, item["name"] + " 拆分", "split",
                                  "split", "", "yahoo", url, item["inception"], item["sector"],
                                  item["gics_effective"], splits, ("date", "numerator", "denominator"),
                                  "ratio_num/ratio_den。价格序列仍是拆分前的未复权收盘。"))
    for item in C.SP_TR:
        rows.append(_coverage_row(
            market="US", container_id=item["container_id"], code=item["code"],
            name=f"S&P 500 {item['sector']} (TR)", series_kind="bar", return_basis="total_return",
            currency="USD", source="yahoo", source_url=C.YAHOO.format(symbol=item["yahoo"]),
            gics_sector=item["sector"], gics_effective=item["gics_effective"], rows="0",
            status="unavailable",
            note=("Yahoo chart 能解析到指数名称，validRanges 只有 1d/5d，按 period1/period2 拉取日线为空。"
                  "没有写入 bars。Stooq 返回脚本挑战页，标普官网 403。")))
    item = C.SP_PRICE_AVAILABLE
    bars = _read_bars(con, item["code"])
    rows.append(_bar_record(
        "US", item["container_id"], item["code"], item["name"], "price", "USD", "yahoo",
        C.YAHOO.format(symbol=item["yahoo"]), "", "", item["sector"], item["gics_effective"], bars,
        "这是价格指数，不是全收益。全收益符号 ^SP500-60TR 没有日线。2016-08-31 之前不是拆分后的房地产行业。"))
    for item in C.HSI_SUB:
        for code, basis, label in (
            (item["code"], "price", item["name"]),
            (item["tr_code"], "total_return", item["tr_name"]),
        ):
            bars = _read_bars(con, code)
            launch = C.HSI_LAUNCH if basis == "price" else ""
            base = C.HSI_FIRST_VALUE if basis == "price" else ""
            note = ("腾讯日线。volume 沿用源字段，指数上通常是成交额不是股数。"
                    "四个分类指数是恒生指数子指数，不是恒生综合行业分类的 12 个行业。")
            if basis == "total_return":
                note += " 总收益代码来自腾讯检索，不在 2026-03-31 指数目录摘录里，发布日记空。"
            rows.append(_bar_record("HK", item["container_id"], code, label, basis, "HKD", "tencent_hk_index",
                                    C.TENCENT, launch, base, "", "", bars, note))
    for item in C.HSCI:
        rows.append(_coverage_row(
            market="HK", container_id=f"hk-{item['code'].lower()}", code=item["code"], name=item["name"],
            series_kind="bar", return_basis="price", currency="HKD", source="",
            source_url=C.CATALOGUE, official_launch=item["launch"], base_date=C.HSCI_BASE,
            rows="0", status="unavailable",
            note=("指数目录 2026-03-31 有代码、发布日和首个点日 2000-01-03。事实表称行业指数回溯至基日，"
                  "发布前是回测。Yahoo 404，腾讯无代码，恒生公司日线为付费订阅。未写入 bars。")))
    bars = _read_bars(con, "HKDCNY")
    rows.append(_bar_record(
        "FX", "fx-hkdcny", "HKDCNY", "HKD/CNY 中间价", "fx", "CNY per HKD", "chinamoney", C.CHINAMONEY,
        "", "2006-01-04", "", "", bars,
        "与 USDCNY 同一 CcprHisNew。1 港元兑人民币。2005 年该接口 total=0。只写 close。"))
    return rows


def _bar_record(market, container, code, name, basis, currency, source, url, launch, base, sector,
                effective, bars, note) -> dict:
    status = "in_db" if bars else "unavailable"
    return _coverage_row(
        market=market, container_id=container, code=code, name=name, series_kind="bar",
        return_basis=basis, currency=currency, source=source if bars else source,
        source_url=url, official_launch=launch, base_date=base, gics_sector=sector,
        gics_effective=effective, first_date=bars[0]["date"] if bars else "",
        last_date=bars[-1]["date"] if bars else "", rows=len(bars),
        sha256=bar_sha256(bars) if bars else "", status=status, note=note)


def _event_record(market, container, code, name, kind, basis, currency, source, url, launch, sector,
                  effective, rows, columns, note) -> dict:
    status = "in_db" if rows else "empty"
    return _coverage_row(
        market=market, container_id=container, code=code, name=name, series_kind=kind,
        return_basis=basis, currency=currency, source=source, source_url=url,
        official_launch=launch, gics_sector=sector, gics_effective=effective,
        first_date=rows[0]["date"] if rows else "", last_date=rows[-1]["date"] if rows else "",
        rows=len(rows), sha256=series_sha256(rows, columns) if rows else "", status=status, note=note)


def write_coverage(rows: list[dict]) -> None:
    COVERAGE.parent.mkdir(parents=True, exist_ok=True)
    with COVERAGE.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_spot(con) -> None:
    with SPOT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=("code", "target", "date", "close", "source"))
        writer.writeheader()
        plan = [("XLB", SPOT_DATES), ("HSF", SPOT_DATES), ("HKDCNY", FX_SPOT_DATES)]
        for code, targets in plan:
            bars = _read_bars(con, code)
            src = _source_of(con, code) or ""
            for target in targets:
                hit = _on_or_after(bars, target)
                writer.writerow({
                    "code": code, "target": target,
                    "date": "" if hit is None else hit["date"],
                    "close": "" if hit is None else hit["close"],
                    "source": src,
                })


def cross_check(con, log: list[str]) -> None:
    """收盘价对收盘价。不计算收益。CNBC 只有近两年日线，用来核对 2026 年五个日期。"""
    with CROSS.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=("code", "date", "yahoo_close", "cnbc_close", "abs_diff", "note"))
        writer.writeheader()
        for code in CROSS_CODES:
            local = {r["date"]: r["close"] for r in _read_bars(con, code)}
            try:
                other = _cnbc(code)
            except (http.FetchError, ValueError, KeyError) as exc:
                log.append(f"cross {code} FAIL {exc}")
                writer.writerow({"code": code, "date": "", "yahoo_close": "", "cnbc_close": "",
                                 "abs_diff": "", "note": str(exc)[:160]})
                continue
            for day in CROSS_DATES:
                y = local.get(day)
                c = other.get(day)
                diff = "" if y is None or c is None else f"{abs(float(y) - float(c)):.6g}"
                writer.writerow({"code": code, "date": day, "yahoo_close": "" if y is None else y,
                                 "cnbc_close": "" if c is None else c, "abs_diff": diff, "note": ""})
            time.sleep(0.15)
    log.append(f"cross wrote {CROSS}")


def _cnbc(symbol: str) -> dict[str, float]:
    raw = http.get("https://ts-api.cnbc.com/harmony/app/charts/1Y.json", {"symbol": symbol},
                   timeout=25, headers={"Accept": "application/json", "Referer": "https://www.cnbc.com/"})
    bars = json.loads(raw)["barData"]["priceBars"]
    out = {}
    for bar in bars:
        day = str(bar["tradeTime"])[:8]
        iso = f"{day[:4]}-{day[4:6]}-{day[6:8]}"
        out[iso] = float(bar["close"])
    return out


def _toml_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', "'")


def write_universe(rows: list[dict]) -> None:
    lines = [
        "# v4-R1 新增容器。python -m src.v4.data ingest 写出。",
        "# 不读取、不修改 config/v3/universe.toml 和 data/universe.csv。",
        "# 不接入 v3 引擎。这里没有组合收益。",
        "",
    ]
    seen = set()
    for row in rows:
        if row["series_kind"] != "bar":
            continue
        key = (row["container_id"], row["code"])
        if key in seen:
            continue
        seen.add(key)
        lines.extend([
            "[[container]]",
            f'id = "{row["container_id"]}"',
            f'market = "{row["market"]}"',
            f'name = "{_toml_escape(row["name"])}"',
            f'code = "{row["code"]}"',
            f'return_basis = "{row["return_basis"]}"',
            f'currency = "{_toml_escape(row["currency"])}"',
            f'source = "{row["source"]}"',
            f'source_url = "{row["source_url"]}"',
            f'status = "{row["status"]}"',
            f'official_launch = "{row["official_launch"]}"',
            f'base_date = "{row["base_date"]}"',
            f'gics_sector = "{_toml_escape(row["gics_sector"])}"',
            f'gics_effective = "{row["gics_effective"]}"',
            f'first_date = "{row["first_date"]}"',
            f'last_date = "{row["last_date"]}"',
            f'rows = "{row["rows"]}"',
            f'sha256 = "{row["sha256"]}"',
            f'note = "{_toml_escape(row["note"])}"',
            "",
        ])
    UNIVERSE.parent.mkdir(parents=True, exist_ok=True)
    UNIVERSE.write_text("\n".join(lines), encoding="utf-8")


def run(con, end: date = C.END) -> list[str]:
    if end > C.END:
        raise IngestError(f"截止日 {end} 晚于登记上限 {C.END}")
    ensure(con)
    before = _guard(con)
    fetched_at = DB.now()
    log: list[str] = []
    log.append(f"guard before {before}")
    http.LOG.clear()
    run_id = DB.start_run(con, "backfill", end=end, args={
        "job": "v4-r1-data-ingest",
        "portfolio_returns": False,
        "alters_existing_codes": False,
    })
    try:
        for item in C.ETFS:
            fetch_etf(con, item, end, fetched_at, log)
        fetch_sp_price(con, end, fetched_at, log)
        fetch_hk(con, end, fetched_at, log)
        fetch_fx(con, end, fetched_at, log)
        after = _guard(con)
        if after != before:
            raise IngestError(f"哨兵序列被改动 before={before} after={after}")
        rows = build_coverage(con)
        write_coverage(rows)
        write_universe(rows)
        write_spot(con)
        cross_check(con, log)
        DB.write_requests(con, run_id, list(http.LOG))
        DB.finish_run(con, run_id, "ok")
    except Exception:
        DB.finish_run(con, run_id, "error")
        raise
    log.append(f"run_id {run_id} coverage {COVERAGE}")
    return log
