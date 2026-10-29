"""v4-R1f / D21：8 只场内 QDII、LOF 的后复权还原。

东财 fqt=2 取不到时，用已入库的不复权收盘和天天基金分红送配页还原。
没有分红、没有拆分的，后复权等于不复权。有现金分红的，除息日把累计因子乘上
前收盘 ÷（前收盘 − 每份分红）。来源记为还原。

只插入。kind=backward 已有行时不改那些行，还原序列另写 kind=backward_rebuild。
不写 bars.adj=hfq：那一列的检查只接受 eastmoney_etf_hfq。不算组合收益。
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
from datetime import date
from pathlib import Path

from src.data import db as DB
from src.data import http
from src.v4.data.parse import bar_sha256
from src.v4.data.r1c import ensure as ensure_r1c
from src.v4.data.r1c_parse import align_ex_date, parse_fhsp

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results" / "v4" / "inventory" / "r1f"
INCOMING = ROOT / "incoming" / "2026-10-29-v4-r1f-d21"
CACHED_FHSP = ROOT / "incoming" / "2026-10-29-v4-r1e-hfq-followup" / "fhsp"
FHSP = "https://fundf10.eastmoney.com/fhsp_{code}.html"
END = "2026-09-30"
SOURCE = "还原"
KIND_BACKWARD = "backward"
KIND_REBUILD = "backward_rebuild"
METHOD_FLAT = "no_corporate_action_factor_1"
METHOD_DIV = "ex_date_factor_prev_close_over_prev_minus_dps"
CLOSE_TOL = 1e-6
FLAT_CODES = ("513910", "159501", "159687", "159688", "159822")
CASH_CODES = ("513820", "160125", "160644")
CODES = FLAT_CODES + CASH_CODES
# 任务写明的窗口内现金分红次数。少于此数视为页面不完整，不入库。
MIN_DIVIDENDS = {"513820": 27, "160125": 4, "160644": 1}

FILL_COLUMNS = (
    "code", "kind", "status", "inserted", "kept", "first", "last", "source", "source_url",
    "sha256", "method", "reason",
)
GAP_COLUMNS = ("code", "name", "reason", "source")
DIVIDEND_COLUMNS = (
    "code", "ex_date", "record_date", "amount_per_share", "text", "aligned_date",
    "prev_close", "factor_step", "factor", "used", "note",
)
CROSS_COLUMNS = (
    "code", "year", "hfq_start", "hfq_end", "hfq_growth", "nav_start", "nav_end",
    "nav_source", "accum_growth", "diff", "note",
)


class R1fError(RuntimeError):
    pass


def window_dividends(parsed: dict, end: str = END) -> list[dict]:
    """留下除息日不晚于 end 的现金分红。每份金额按页面精度收到 6 位小数。有拆分则拒绝。"""
    if parsed.get("splits"):
        raise R1fError("有拆分或折算，本轮只处理现金分红")
    kept = []
    for item in parsed.get("dividends") or []:
        if item["date"] > end:
            continue
        amount = round(float(item["amount"]), 6)
        if not (amount > 0):
            raise R1fError(f"分红必须为正：{item}")
        kept.append({**item, "amount": amount})
    kept.sort(key=lambda row: (row["date"], row["amount"]))
    return kept


def choose_method(parsed: dict, dividends: list[dict]) -> str:
    """无事件且两张表都明确为空时，因子恒为 1。页面写了分红（含截止日之后）则用除息因子。"""
    if parsed.get("splits"):
        raise R1fError("有拆分或折算")
    if dividends or parsed.get("dividends"):
        return METHOD_DIV
    if parsed.get("explicit_empty_dividend") and parsed.get("explicit_empty_split"):
        return METHOD_FLAT
    raise R1fError("分红或拆分表不是明确的空表")


def rebuild_bars(bars: list[dict], dividends: list[dict]) -> dict:
    """用原始收盘做后复权。不改传入的列表。

    除息日（或其后 5 个日历日内的第一根 K 线）把累计因子乘上
    前收盘 ÷（前收盘 − 每份分红）。后复权 OHLC = 不复权 OHLC × 累计因子。
    因子从 1 起，首日不复权收盘就是后复权收盘。
    """
    usable = [dict(bar) for bar in bars if bar.get("date") and bar.get("close") and float(bar["close"]) > 0]
    if not usable:
        raise R1fError("没有正收盘，不能做后复权")
    dates = {bar["date"] for bar in usable}
    first = usable[0]["date"]
    div_on: dict[str, float] = {}
    notes = []
    for item in dividends:
        if item["date"] < first:
            notes.append({"date": item["date"], "note": "上市前，不参与后复权"})
            continue
        aligned = align_ex_date(item["date"], dates)
        if aligned is None:
            raise R1fError(f"分红除息日 {item['date']} 附近没有 K 线")
        div_on[aligned] = round(div_on.get(aligned, 0.0) + float(item["amount"]), 6)
        if aligned != item["date"]:
            notes.append({"date": item["date"], "note": f"对齐到 {aligned}"})
    factor = 1.0
    prev_raw = None
    adjusted = []
    applied = []
    for bar in usable:
        raw = float(bar["close"])
        day = bar["date"]
        step = 1.0
        dps = div_on.get(day)
        if dps:
            if prev_raw is None:
                raise R1fError(f"{day} 没有前收，不能除息")
            if not (0 < dps < prev_raw):
                raise R1fError(f"{day} 每份分红 {dps} 不低于前收 {prev_raw}")
            step = prev_raw / (prev_raw - dps)
            factor *= step
            applied.append({
                "date": day,
                "amount": dps,
                "prev_close": prev_raw,
                "factor_step": step,
                "factor": factor,
            })
        adjusted.append(_scaled(bar, factor))
        prev_raw = raw
    return {"adjusted": adjusted, "applied": applied, "notes": notes, "dividends_on": div_on}


def _scaled(bar: dict, factor: float) -> dict:
    def px(name):
        value = bar.get(name)
        if value is None or value == "":
            return None
        value = float(value)
        if factor == 1.0:
            return value
        return value * factor

    return {
        "date": bar["date"],
        "open": px("open"),
        "high": px("high"),
        "low": px("low"),
        "close": px("close"),
        "volume": bar.get("volume"),
    }


def same_closes(left: list[dict], right: list[dict], tol: float = CLOSE_TOL) -> bool:
    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        if a["date"] != b["date"] or abs(float(a["close"]) - float(b["close"])) > tol:
            return False
    return True


def year_crosscheck(code: str, hfq: list[dict], nav: list[dict]) -> list[dict]:
    """逐年对照后复权收盘和累计净值的增长。只出每年一行，不加总。

    有上一年末日时，增长 = 本年末日 / 上一年末日 − 1。
    序列从这一年中间开始时，用这一年自己的首尾，并在 note 里标明。
    """
    hfq_years = _year_ends(hfq, "close")
    nav_years = _year_ends([row for row in nav if row.get("accum_nav")], "accum_nav")
    years = sorted(set(hfq_years) | set(nav_years))
    prev_h = None
    prev_n = None
    rows = []
    for year in years:
        h = hfq_years.get(year)
        n = nav_years.get(year)
        notes = []
        h_growth = _growth(prev_h, h, "close", "后复权当年内从首日到末日", notes)
        n_growth = _growth(prev_n, n, "accum_nav", "累计净值当年内从首日到末日", notes)
        diff = ""
        if h_growth != "" and n_growth != "":
            diff = f"{h_growth - n_growth:.8f}"
        rows.append({
            "code": code,
            "year": year,
            "hfq_start": h["first_date"] if h else "",
            "hfq_end": h["last_date"] if h else "",
            "hfq_growth": "" if h_growth == "" else f"{h_growth:.8f}",
            "nav_start": n["first_date"] if n else "",
            "nav_end": n["last_date"] if n else "",
            "nav_source": n["source"] if n else "",
            "accum_growth": "" if n_growth == "" else f"{n_growth:.8f}",
            "diff": diff,
            "note": " ".join(notes),
        })
        if h:
            prev_h = h
        if n:
            prev_n = n
    return rows


def _year_ends(rows: list[dict], key: str) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for row in rows:
        value = row.get(key)
        if value is None or not (float(value) > 0):
            continue
        year = row["date"][:4]
        slot = found.get(year)
        if slot is None:
            found[year] = {
                "first_date": row["date"],
                "first_value": float(value),
                "last_date": row["date"],
                "last_value": float(value),
                "source": row.get("source") or "",
            }
            continue
        slot["last_date"] = row["date"]
        slot["last_value"] = float(value)
        if row.get("source"):
            slot["source"] = row["source"]
    return found


def _growth(prev: dict | None, cur: dict | None, _key: str, partial_note: str, notes: list[str]) -> float | str:
    if cur is None:
        return ""
    if prev is not None:
        return cur["last_value"] / prev["last_value"] - 1.0
    if cur["first_date"] == cur["last_date"]:
        return ""
    notes.append(partial_note)
    return cur["last_value"] / cur["first_value"] - 1.0


def _series(con, code: str, kind: str) -> list[dict]:
    return [dict(row) for row in con.execute(
        """SELECT date, open, high, low, close, volume, source, method
           FROM v4_series WHERE code=? AND kind=? ORDER BY date""",
        (code, kind))]


def _raw_bars(con, code: str, end: str = END) -> list[dict]:
    return [dict(row) for row in con.execute(
        """SELECT date, open, high, low, close, volume
           FROM bars WHERE code=? AND adj='raw' AND date<=? ORDER BY date""",
        (code, end))]


def _nav_rows(con, code: str, end: str = END) -> list[dict]:
    return [dict(row) for row in con.execute(
        """SELECT date, accum_nav, source FROM fund_nav
           WHERE code=? AND date<=? AND accum_nav IS NOT NULL
           ORDER BY date""",
        (code, end))]


def destination(con, code: str, adjusted: list[dict], method: str) -> tuple[str, str]:
    """决定写入哪一种 kind。已有行收盘对得上就跳过，对不上也不覆盖。"""
    backward = _series(con, code, KIND_BACKWARD)
    if not backward:
        return KIND_BACKWARD, "insert"
    if _same_stored(backward, adjusted) and _one_source(backward, SOURCE, method):
        return KIND_BACKWARD, "already"
    rebuild = _series(con, code, KIND_REBUILD)
    if not rebuild:
        return KIND_REBUILD, "insert"
    if _same_stored(rebuild, adjusted):
        return KIND_REBUILD, "already"
    return KIND_REBUILD, "conflict"


def _one_source(rows: list[dict], source: str, method: str) -> bool:
    return all(row.get("source") == source and row.get("method") == method for row in rows)


def _same_stored(stored: list[dict], adjusted: list[dict]) -> bool:
    left = [{"date": row["date"], "close": row["close"]} for row in stored if row.get("close") is not None]
    return same_closes(left, adjusted)


def insert_series(con, code: str, kind: str, rows: list[dict], source_url: str, method: str,
                  fetched_at: str) -> int:
    """只插入一种还没有的 kind。调用方负责不把已有 kind 传进来。"""
    have = con.execute(
        "SELECT COUNT(*) FROM v4_series WHERE code=? AND kind=?", (code, kind)).fetchone()[0]
    if have:
        raise R1fError(f"{code} {kind} 已有 {have} 行，不覆盖")
    if any(row["date"] > END for row in rows):
        raise R1fError(f"{code} 含有 {END} 之后的日期")
    con.executemany(
        """INSERT INTO v4_series
           (code, kind, date, open, high, low, close, volume, unit_nav, accum_nav, filled,
            source, source_url, method, fetched_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, 0, ?, ?, ?, ?)""",
        [(code, kind, row["date"], row.get("open"), row.get("high"), row.get("low"), row["close"],
          row.get("volume"), SOURCE, source_url, method, fetched_at) for row in rows])
    return len(rows)


def insert_dividends(con, code: str, parsed_rows: list[dict], source_url: str, body_sha: str,
                     fetched_at: str) -> int:
    """只给这次写入 kind=backward 的现金分红补登记。已有除息日不改。"""
    existing = {
        row[0]: row[1]
        for row in con.execute(
            "SELECT ex_date, amount FROM v4_corp_action WHERE code=? AND kind='dividend'", (code,))
    }
    fresh = []
    for item in parsed_rows:
        old = existing.get(item["date"])
        if old is not None:
            if abs(float(old) - float(item["amount"])) > 1e-8:
                raise R1fError(f"{code} {item['date']} 已有分红 {old}，与 {item['amount']} 不一致")
            continue
        fresh.append(item)
    con.executemany(
        """INSERT INTO v4_corp_action
           (code, kind, ex_date, amount, ratio_num, ratio_den, ratio_text, source, source_url,
            body_sha256, note, fetched_at)
           VALUES (?, 'dividend', ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?)""",
        [(code, item["date"], item["amount"], item.get("text") or "", SOURCE, source_url, body_sha,
          "", fetched_at) for item in fresh])
    return len(fresh)


def _gz(path: Path, raw: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wb") as handle:
        handle.write(raw)
    return hashlib.sha256(raw).hexdigest()


def _load_fhsp(code: str) -> dict:
    url = FHSP.format(code=code)
    try:
        raw = http.get(url, headers={"Referer": "https://fundf10.eastmoney.com/"}, timeout=25, retries=0)
        origin = "live"
    except http.FetchError as exc:
        cached = CACHED_FHSP / f"{code}.html.gz"
        if not cached.exists():
            raise R1fError(f"{code} 分红送配页取不到，也没有已保存的页面：{exc}") from exc
        with gzip.open(cached, "rb") as handle:
            raw = handle.read()
        origin = f"cached:{cached.relative_to(ROOT)} ({exc})"
    digest = _gz(INCOMING / "fhsp" / f"{code}.html.gz", raw)
    html = raw.decode("utf-8", "replace")
    return {"code": code, "raw": raw, "html": html, "sha256": digest, "url": url, "origin": origin}


def _plan(code: str, bars: list[dict], page: dict) -> dict:
    parsed = parse_fhsp(page["html"])
    dividends = window_dividends(parsed, END)
    later = [item for item in parsed.get("dividends") or [] if item["date"] > END]
    if code in CASH_CODES and len(dividends) < MIN_DIVIDENDS[code]:
        raise R1fError(
            f"{code} 窗口内现金分红 {len(dividends)} 次，少于已登记的 {MIN_DIVIDENDS[code]} 次")
    if code in FLAT_CODES and (dividends or parsed.get("splits") or later):
        raise R1fError(f"{code} 分红送配页不再是空表")
    method = choose_method(parsed, dividends)
    if code in FLAT_CODES and method != METHOD_FLAT:
        raise R1fError(f"{code} 应是无公司行为，方法却是 {method}")
    if code in CASH_CODES and method != METHOD_DIV:
        raise R1fError(f"{code} 应有现金分红，方法却是 {method}")
    built = rebuild_bars(bars, dividends)
    if method == METHOD_FLAT and not same_closes(bars, built["adjusted"]):
        raise R1fError(f"{code} 没有公司行为时后复权应与原始收盘相同")
    _check_factor_days(bars, built)
    return {
        "code": code,
        "parsed": parsed,
        "dividends": dividends,
        "later": later,
        "method": method,
        "built": built,
        "page": page,
    }


def _check_factor_days(bars: list[dict], built: dict) -> None:
    """除息日的后复权收益应等于 收盘 ÷（前收 − 每份分红） − 1。"""
    raw = {row["date"]: float(row["close"]) for row in bars}
    adj = {row["date"]: float(row["close"]) for row in built["adjusted"]}
    order = [row["date"] for row in built["adjusted"]]
    prev = {day: order[i - 1] for i, day in enumerate(order) if i}
    for item in built["applied"]:
        day = item["date"]
        before = prev.get(day)
        if before is None:
            raise R1fError(f"{day} 没有前一根后复权")
        expected = raw[day] / (item["prev_close"] - item["amount"]) - 1.0
        actual = adj[day] / adj[before] - 1.0
        if abs(actual - expected) > 1e-8:
            raise R1fError(f"{day} 后复权收益 {actual} 与因子 {expected} 不一致")


def _positive_raw(bars: list[dict]) -> list[dict]:
    return [row for row in bars if row.get("close") and float(row["close"]) > 0]


def _fingerprint(rows: list[tuple]) -> str:
    blob = "\n".join(",".join("" if item is None else str(item) for item in row) for row in rows)
    return hashlib.sha256(blob.encode()).hexdigest()


def _bar_fingerprint(con, code: str) -> str:
    rows = [tuple(row) for row in con.execute(
        """SELECT adj, date, open, high, low, close, volume, amount, source
           FROM bars WHERE code=? ORDER BY adj, date""",
        (code,))]
    return _fingerprint(rows)


def _kind_fingerprint(con, code: str, kind: str) -> str:
    rows = [tuple(row) for row in con.execute(
        """SELECT date, close, source, method FROM v4_series
           WHERE code=? AND kind=? ORDER BY date""",
        (code, kind))]
    return _fingerprint(rows)


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gap_row(code: str, method: str, inserted: int, source_url: str, backward: list[dict],
            adjusted: list[dict]) -> dict:
    """原 kind=backward 没被盖掉时，记下它的来源，以及和还原收盘差多少。"""
    sources = "、".join(dict.fromkeys(row["source"] for row in backward if row.get("source")))
    left = [{"date": row["date"], "close": row["close"]} for row in backward if row.get("close") is not None]
    if same_closes(left, adjusted):
        match = "收盘与还原逐行相同（容差 1e-6）"
    else:
        by_day = {row["date"]: float(row["close"]) for row in adjusted}
        worst = max(
            (abs(float(row["close"]) - by_day[row["date"]]) for row in left if row["date"] in by_day),
            default=0.0)
        match = f"收盘与还原不同，重叠日最大绝对差 {worst:.6f}"
    return {
        "code": code,
        "name": "kind=backward 仍是原序列",
        "reason": (
            f"还原已写入 backward_rebuild（{inserted} 行，方法 {method}）。"
            f"原 kind=backward 来源 {sources}，{len(backward)} 行未改，{match}。"
            "研究读取仍用 kind=backward。"
        ),
        "source": source_url,
    }


def _dividend_sheet(plan: dict) -> list[dict]:
    built = plan["built"]
    applied = {item["date"]: item for item in built["applied"]}
    dates = {row["date"] for row in built["adjusted"]}
    rows = []
    if plan["method"] == METHOD_FLAT:
        rows.append({
            "code": plan["code"], "ex_date": "", "record_date": "", "amount_per_share": "",
            "text": "暂无分红、暂无拆分", "aligned_date": "", "prev_close": "", "factor_step": "",
            "factor": "1", "used": "0", "note": "页面写明没有分红、没有拆分。后复权因子为 1。",
        })
        return rows
    for item in plan["dividends"]:
        aligned = align_ex_date(item["date"], dates)
        hit = applied.get(aligned) if aligned else None
        rows.append({
            "code": plan["code"],
            "ex_date": item["date"],
            "record_date": item.get("record_date") or "",
            "amount_per_share": f"{item['amount']:.6f}",
            "text": item.get("text") or "",
            "aligned_date": hit["date"] if hit else "",
            "prev_close": f"{hit['prev_close']:.6f}" if hit else "",
            "factor_step": f"{hit['factor_step']:.8f}" if hit else "",
            "factor": f"{hit['factor']:.8f}" if hit else "",
            "used": "1" if hit else "0",
            "note": "" if hit else "没有用到这次除息",
        })
    for item in plan["later"]:
        rows.append({
            "code": plan["code"],
            "ex_date": item["date"],
            "record_date": item.get("record_date") or "",
            "amount_per_share": f"{round(float(item['amount']), 6):.6f}",
            "text": item.get("text") or "",
            "aligned_date": "",
            "prev_close": "",
            "factor_step": "",
            "factor": "",
            "used": "0",
            "note": f"除息日晚于 {END}，不参与本次还原",
        })
    return rows


def run() -> dict:
    con = DB.connect(DB.MARKET_DB)
    before_sha = DB.sha256_file(DB.MARKET_DB)
    before_bytes = DB.MARKET_DB.stat().st_size
    before_bars = con.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
    before_series = con.execute("SELECT COUNT(*) FROM v4_series").fetchone()[0]
    bar_fp = {code: _bar_fingerprint(con, code) for code in CODES}
    kind_fp = {
        (code, kind): _kind_fingerprint(con, code, kind)
        for code in CODES for kind in (KIND_BACKWARD, KIND_REBUILD)
    }
    reports = []
    try:
        ensure_r1c(con)
        pages = [_load_fhsp(code) for code in CODES]
        plans = []
        for code, page in zip(CODES, pages):
            bars = _positive_raw(_raw_bars(con, code))
            if not bars:
                raise R1fError(f"{code} 没有不复权正收盘")
            plans.append(_plan(code, bars, page))
        fetched_at = DB.now()
        run_id = DB.start_run(con, "backfill", end=date.fromisoformat(END), args={
            "job": "v4-r1f-d21-hfq-rebuild",
            "portfolio_returns": False,
            "overwrites_existing_rows": False,
            "nav_end": END,
            "source": SOURCE,
        })
        with con:
            for plan in plans:
                code = plan["code"]
                adjusted = plan["built"]["adjusted"]
                kind, action = destination(con, code, adjusted, plan["method"])
                page = plan["page"]
                digest = bar_sha256(adjusted)
                base = {
                    "code": code, "kind": kind, "source": SOURCE, "source_url": page["url"],
                    "sha256": digest, "method": plan["method"],
                    "first": adjusted[0]["date"], "last": adjusted[-1]["date"],
                }
                if action == "conflict":
                    raise R1fError(f"{code} {kind} 已有还原行，但收盘与这次计算不一致")
                if action == "already":
                    kept = con.execute(
                        "SELECT COUNT(*) FROM v4_series WHERE code=? AND kind=?",
                        (code, kind)).fetchone()[0]
                    reports.append({**base, "status": "already", "inserted": 0, "kept": kept, "reason": ""})
                    continue
                inserted = insert_series(
                    con, code, kind, adjusted, page["url"], plan["method"], fetched_at)
                reason = ""
                if kind == KIND_REBUILD:
                    reason = "kind=backward 已有行，不覆盖。还原序列写入 backward_rebuild。"
                if kind == KIND_BACKWARD and plan["dividends"]:
                    insert_dividends(
                        con, code, plan["dividends"], page["url"], page["sha256"], fetched_at)
                reports.append({
                    **base, "status": "in_db", "inserted": inserted, "kept": 0, "reason": reason,
                })
        for code in CODES:
            if _bar_fingerprint(con, code) != bar_fp[code]:
                raise R1fError(f"{code} 的 bars 被改动")
            for kind in (KIND_BACKWARD, KIND_REBUILD):
                inserted_this = any(
                    row["code"] == code and row["kind"] == kind and int(row["inserted"]) > 0
                    for row in reports)
                if not inserted_this and _kind_fingerprint(con, code, kind) != kind_fp[(code, kind)]:
                    raise R1fError(f"{code} {kind} 已有行被改动")
        after_bars = con.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
        if after_bars != before_bars:
            raise R1fError(f"bars 行数从 {before_bars} 变成 {after_bars}")
        hfq_bars = con.execute(
            f"SELECT COUNT(*) FROM bars WHERE adj='hfq' AND code IN ({','.join('?' * len(CODES))})",
            CODES).fetchone()[0]
        if hfq_bars:
            raise R1fError("不应写入 bars.adj=hfq")
        cross = []
        dividends = []
        for plan in plans:
            code = plan["code"]
            dividends.extend(_dividend_sheet(plan))
            if code not in CASH_CODES:
                continue
            cross.extend(year_crosscheck(code, plan["built"]["adjusted"], _nav_rows(con, code)))
        gaps = []
        for plan, report in zip(plans, reports):
            if report["kind"] != KIND_REBUILD or report["status"] != "in_db":
                continue
            backward = _series(con, plan["code"], KIND_BACKWARD)
            gaps.append(gap_row(
                plan["code"], plan["method"], int(report["inserted"]), report["source_url"],
                backward, plan["built"]["adjusted"]))
        fill_sha = _write_csv(OUT / "fill.csv", FILL_COLUMNS, reports)
        gap_sha = _write_csv(OUT / "gaps.csv", GAP_COLUMNS, gaps)
        div_sha = _write_csv(OUT / "dividends.csv", DIVIDEND_COLUMNS, dividends)
        cross_sha = _write_csv(OUT / "crosscheck-year.csv", CROSS_COLUMNS, cross)
        DB.write_requests(con, run_id, http.LOG)
        DB.finish_run(con, run_id, "ok")
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        after_sha = DB.sha256_file(DB.MARKET_DB)
        summary = {
            "job": "v4-r1f-d21-hfq-rebuild",
            "end": END,
            "source": SOURCE,
            "before_sha256": before_sha,
            "before_bytes": before_bytes,
            "sha256": after_sha,
            "bytes": DB.MARKET_DB.stat().st_size,
            "bars_rows": after_bars,
            "v4_series_before": before_series,
            "v4_series_after": con.execute("SELECT COUNT(*) FROM v4_series").fetchone()[0],
            "inserted_rows": sum(int(row["inserted"]) for row in reports),
            "integrity": integrity,
            "fill_sha256": fill_sha,
            "gaps_sha256": gap_sha,
            "dividends_sha256": div_sha,
            "crosscheck_sha256": cross_sha,
            "pages": [
                {"code": page["code"], "sha256": page["sha256"], "origin": page["origin"], "url": page["url"]}
                for page in pages
            ],
            "reports": reports,
        }
        (OUT / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (INCOMING / "attempts.json").write_text(
            json.dumps({"pages": summary["pages"], "reports": reports}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    except Exception:
        con.close()
        raise
    else:
        con.close()
    for suffix in ("-wal", "-shm"):
        leftover = Path(str(DB.MARKET_DB) + suffix)
        if leftover.exists():
            raise R1fError(f"库文件旁还有 {leftover.name}")
    print(json.dumps({
        "integrity": summary["integrity"],
        "sha256": summary["sha256"],
        "inserted_rows": summary["inserted_rows"],
        "v4_series_after": summary["v4_series_after"],
    }, ensure_ascii=False, indent=2))
    return summary
