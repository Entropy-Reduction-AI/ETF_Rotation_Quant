"""现金分红。

qfq 推导（sync_qfq）只追加，不改已有行。一手公告替换（replace_from_events）是另一次写入：
先摘掉只追加触发器，删掉对不上公告的旧行，再把触发器装回去。


腾讯 qfq 是减法复权：diff(t) = 不复权收盘 − qfq 收盘 = 除息日晚于 t 的现金分红之和。
相邻两个都有两边收盘的交易日，diff 下降的幅度就是这一天的每股现金分红。
后来的分红会把更早的 diff 两边一起抬高，阶跃大小不变，所以重复推导是幂等的。
同一代码、同一除息日只保留第一次写入。
"""
from __future__ import annotations

import csv
import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from src.data import db as DB
from src.data import http
from src.data import store
from src.data import universe as U
from src.data.hashlog import HashLedger
from src.data.sources import fetch_tencent

# 511880 这三行 Grok 把权益登记日写成了除息日。库内除息日与价格跳空日一致，替换时保留库内日期。
EX_DATE_CORRECTIONS = {
    ("511880", "2014-01-16"): "2014-01-17",
    ("511880", "2014-12-30"): "2014-12-31",
    ("511880", "2015-12-30"): "2015-12-31",
}
# 评审里逐条对过、可以当现金分红日历的 10 只。替换后必须与一手公告逐行一致。
TRUSTED_FUNDS = (
    "510300", "510880", "511020", "512400", "515210", "588080",
    "510330", "511010", "511260", "515100",
)
_AMOUNT = Decimal("0.0001")
_CODE = re.compile(r"\d{6}")

# 与 compare() 的 tol 相同：1.5 个最小价位。更小的阶跃是四舍五入，不是分红。
STEP_TOL = 0.0015
# A 股 ETF 单日涨跌幅限制多数 ±10%，创业板、科创板相关 ±20%。
# 阈值高于这个上限，限制以内的跳空走正常止损。
# 25% 仍会把回放里黄金次日开盘 200、前收 308（约 −35%）判成份额折算，
# 作废理由从「开盘已在失效位下方」变成「数据断档」。取 40%，高于 20% 限制，也高于这次构造。
GAP_LIMIT = 0.40

_TABLE = """
CREATE TABLE IF NOT EXISTS cash_dividends (
    code        TEXT NOT NULL,
    ex_date     TEXT NOT NULL CHECK (date(ex_date) = ex_date),
    amount      REAL NOT NULL CHECK (amount > 0),
    prev_close  REAL NOT NULL CHECK (prev_close > amount),
    run_id      INTEGER NOT NULL,
    request_seq INTEGER NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (code, ex_date)
) WITHOUT ROWID
"""
_NO_UPDATE = """
CREATE TRIGGER IF NOT EXISTS cash_dividends_no_update BEFORE UPDATE ON cash_dividends
BEGIN
    SELECT RAISE(ABORT, 'cash_dividends 只追加');
END
"""
_NO_DELETE = """
CREATE TRIGGER IF NOT EXISTS cash_dividends_no_delete BEFORE DELETE ON cash_dividends
BEGIN
    SELECT RAISE(ABORT, 'cash_dividends 只追加');
END
"""


def ensure(con) -> None:
    con.execute(_TABLE)
    con.execute(_NO_UPDATE)
    con.execute(_NO_DELETE)


def derive_cash_dividends(raw_rows: list[dict], qfq_rows: list[dict]) -> list[dict]:
    """返回 [{ex_date, amount, prev_close}]。只认相邻交易日上的向下阶跃。"""
    raw = {r["date"]: r for r in raw_rows if r.get("date") and r.get("close") is not None}
    qfq = {r["date"]: r["close"] for r in qfq_rows if r.get("date") and r.get("close") is not None}
    days = [d for d in sorted(raw) if d in qfq]
    out, prev = [], None
    for d in days:
        diff = float(raw[d]["close"]) - float(qfq[d])
        if prev is not None:
            step = prev["diff"] - diff
            if step > STEP_TOL and prev["close"] > step:
                out.append({"ex_date": d, "amount": round(step, 6), "prev_close": prev["close"]})
        prev = {"date": d, "diff": diff, "close": float(raw[d]["close"])}
    return out


def _record(con, run_id: int, seq: int, code: str, items: list[dict], now: str) -> int:
    wrote = 0
    with con:
        for item in items:
            cur = con.execute(
                """INSERT OR IGNORE INTO cash_dividends
                   (code, ex_date, amount, prev_close, run_id, request_seq, recorded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (code, item["ex_date"], item["amount"], item["prev_close"], run_id, seq, now))
            wrote += cur.rowcount
    return wrote


def sync_qfq(con, run_id: int, windows: dict, end: date, *, log=print) -> None:
    """为给出的代码再拉一次 qfq。失败只记日志，不让这次 mvp 更新失败。"""
    if not windows:
        return
    ensure(con)
    own_record = http.RECORD_DIR is None
    if own_record:
        http.RECORD_DIR = DB.ROOT / "outputs" / "data" / "dividends"
    try:
        for code, start in sorted(windows.items()):
            sym = U.fund_tencent(code)
            if not sym:
                log(f"  qfq {code}: 没有腾讯代码，跳过")
                continue
            before = len(http.LOG)
            try:
                got = fetch_tencent(sym, start, end, adjust="qfq")
            except Exception as exc:  # noqa: BLE001 — 分红取数失败不阻断行情更新
                log(f"  qfq {code}: {str(exc)[:120]}")
                continue
            seq = len(http.LOG) - 1
            if seq < before or not got.rows:
                log(f"  qfq {code}: 没有前复权收盘，不推导分红")
                continue
            raw = [r for r in store.read(con, code, "raw") if r.get("date") and r["date"] >= start.isoformat()]
            items = derive_cash_dividends(raw, got.rows)
            wrote = _record(con, run_id, seq, code, items, DB.now())
            log(f"  qfq {code}: 推导 {len(items)} 笔现金分红，新写入 {wrote} 笔")
    finally:
        if own_record:
            http.RECORD_DIR = None


def _amount_4(text: str) -> float:
    amount = Decimal(str(text).strip()).quantize(_AMOUNT, rounding=ROUND_HALF_UP)
    if amount <= 0:
        raise ValueError(f"现金分红金额必须大于 0：{text}")
    return float(amount)


def _same_amount(stored, wanted: float) -> bool:
    return round(float(stored), 4) == round(float(wanted), 4)


def verified_no_dividend_codes(readme: str) -> list[str]:
    """README「核查后没有分红、折算、拆分记录」那一段的 6 位代码。找不到就拒绝替换。"""
    lines = readme.splitlines()
    for index, line in enumerate(lines):
        if "核查后没有分红" not in line and "核查后无分红" not in line:
            continue
        for nxt in lines[index + 1:]:
            if not nxt.strip():
                continue
            return _CODE.findall(nxt)
    raise ValueError("README 里没有「核查后无分红」名单")


def announcement_rows(events_path: Path, readme_path: Path) -> tuple[list[dict], set[str]]:
    """现金分红行（金额 4 位小数）和核查后无分红的代码。份额折算、拆分不进 cash_dividends。"""
    verified = set(verified_no_dividend_codes(readme_path.read_text(encoding="utf-8")))
    by_key: dict[tuple[str, str], dict] = {}
    with open(events_path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("event_type") != "现金分红":
                continue
            code = (row.get("code") or "").strip()
            ex_date = (row.get("ex_date") or "").strip()
            if not code or not ex_date:
                raise ValueError(f"现金分红缺代码或除息日：{row}")
            ex_date = EX_DATE_CORRECTIONS.get((code, ex_date), ex_date)
            item = {"code": code, "ex_date": ex_date, "amount": _amount_4(row.get("cash_per_unit") or "")}
            key = (code, ex_date)
            if key in by_key and not _same_amount(by_key[key]["amount"], item["amount"]):
                raise ValueError(f"同一除息日两条金额：{code} {ex_date}")
            by_key[key] = item
    overlap = {code for code, _ in by_key} & verified
    if overlap:
        raise ValueError(f"同一代码既有现金分红又在核查后无分红：{sorted(overlap)}")
    rows = [by_key[key] for key in sorted(by_key)]
    return rows, verified


def unknown_dividend_codes(universe_rows: list[dict], announcement: set[str], verified: set[str]) -> dict[str, list[str]]:
    """执行基金里，一手公告没有现金分红、也没有「核查后无分红」的代码。按 theme_id 分组。不写 0。"""
    grouped: dict[str, list[str]] = {}
    for row in universe_rows:
        codes = sorted(c for c in U.listed_codes(row) if c not in announcement and c not in verified)
        if codes:
            grouped[row["theme_id"]] = codes
    return grouped


def _coverage_mark(con, run_id: int, unknown_by_theme: dict[str, list[str]]) -> list[str]:
    """在 coverage 备注里写「分红未知: 代码」。已经有同一句的主题不再写一行。"""
    latest = {r["theme_id"]: r for r in DB.read_coverage(con)}
    writing = []
    marked = []
    for theme, codes in unknown_by_theme.items():
        base = latest.get(theme)
        if not base:
            continue
        marker = "分红未知: " + ",".join(codes)
        notes = base.get("notes") or ""
        if marker in notes:
            continue
        base = dict(base)
        base["notes"] = " | ".join(part for part in (notes, marker) if part)
        base["checked_at"] = DB.now()
        writing.append(base)
        marked.append(theme)
    if writing:
        cols = DB.COVERAGE_COLUMNS
        con.executemany(
            f"INSERT OR REPLACE INTO coverage (run_id, {', '.join(cols)}) VALUES (?, {', '.join('?' * len(cols))})",
            [(run_id, *[str(r.get(c, "") if r.get(c) is not None else "") for c in cols]) for r in writing])
    return marked


def _assert_replaced(con, wanted_rows: list[dict]) -> None:
    """提交前核对：10 只可信基金逐行对齐，511880 三个除息日是价格日，没有 0 金额，噪声代码不留行。"""
    by_code: dict[str, list[dict]] = {}
    for row in wanted_rows:
        by_code.setdefault(row["code"], []).append(row)
    for code in TRUSTED_FUNDS:
        got = list(con.execute("SELECT ex_date, amount FROM cash_dividends WHERE code = ? ORDER BY ex_date", (code,)))
        expect = sorted(by_code.get(code, []), key=lambda r: r["ex_date"])
        if len(got) != len(expect):
            raise ValueError(f"{code} 替换后 {len(got)} 行，公告 {len(expect)} 行")
        for have, want in zip(got, expect):
            if have["ex_date"] != want["ex_date"] or not _same_amount(have["amount"], want["amount"]):
                raise ValueError(f"{code} {have['ex_date']}={have['amount']} 对不上公告 {want['ex_date']}={want['amount']}")
    dates = [row[0] for row in con.execute(
        """SELECT ex_date FROM cash_dividends
            WHERE code = '511880' AND ex_date IN ('2014-01-16','2014-01-17','2014-12-30','2014-12-31','2015-12-30','2015-12-31')
            ORDER BY ex_date""")]
    if dates != ["2014-01-17", "2014-12-31", "2015-12-31"]:
        raise ValueError(f"511880 除息日应为价格日，实际 {dates}")
    zeros = con.execute("SELECT count(*) FROM cash_dividends WHERE amount <= 0").fetchone()[0]
    if zeros:
        raise ValueError(f"写入了 {zeros} 行非正金额")
    announcement = set(by_code)
    stray = [row[0] for row in con.execute(
        f"SELECT DISTINCT code FROM cash_dividends WHERE code NOT IN ({','.join('?' * len(announcement))})",
        tuple(sorted(announcement)))]
    if stray:
        raise ValueError(f"替换后仍有公告以外的代码：{stray[:12]}")


def _prev_close(con, code: str, ex_date: str, amount: float) -> float:
    row = con.execute(
        "SELECT close FROM bars WHERE code = ? AND adj = 'raw' AND date < ? AND close IS NOT NULL ORDER BY date DESC LIMIT 1",
        (code, ex_date)).fetchone()
    if row is None or row[0] <= amount:
        have = None if row is None else row[0]
        raise ValueError(f"{code} {ex_date} 没有大于分红 {amount} 的前收（前收={have}）")
    return float(row[0])


def _write_removed(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["code", "ex_date", "amount", "prev_close", "run_id", "request_seq", "recorded_at"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in fields})


def replace_from_events(con, run_id: int, events_path: Path, readme_path: Path, removed_path: Path) -> dict:
    """用一手现金分红替换 cash_dividends。

    表里只留下公告行（511880 三天用库内除息日）。核查后无分红的代码删掉 qfq 噪声，不写 0。
    其余执行基金没有任一侧的分红记录，coverage 记「分红未知」，也不写 0。
    删掉的旧行全部导出。
    """
    ensure(con)
    wanted_rows, verified = announcement_rows(events_path, readme_path)
    wanted = {(r["code"], r["ex_date"]): r for r in wanted_rows}
    announcement = {code for code, _ in wanted}
    existing = [dict(row) for row in con.execute(
        "SELECT code, ex_date, amount, prev_close, run_id, request_seq, recorded_at FROM cash_dividends ORDER BY code, ex_date")]
    before = {}
    for row in existing:
        before[row["code"]] = before.get(row["code"], 0) + 1
    removing = []
    for row in existing:
        key = (row["code"], row["ex_date"])
        fresh = wanted.get(key)
        if fresh is None or not _same_amount(row["amount"], fresh["amount"]):
            removing.append(row)
    removing_keys = {(row["code"], row["ex_date"]) for row in removing}
    unknown = unknown_dividend_codes(U.load(), announcement, verified)
    now = DB.now()
    with con:
        con.execute("DROP TRIGGER IF EXISTS cash_dividends_no_update")
        con.execute("DROP TRIGGER IF EXISTS cash_dividends_no_delete")
        con.executemany("DELETE FROM cash_dividends WHERE code = ? AND ex_date = ?",
                        [(row["code"], row["ex_date"]) for row in removing])
        inserting = []
        for key, item in wanted.items():
            if key in removing_keys or key not in {(row["code"], row["ex_date"]) for row in existing}:
                prev = _prev_close(con, item["code"], item["ex_date"], item["amount"])
                inserting.append((item["code"], item["ex_date"], item["amount"], prev, run_id, 0, now))
        con.executemany(
            """INSERT INTO cash_dividends (code, ex_date, amount, prev_close, run_id, request_seq, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""", inserting)
        con.execute(_NO_UPDATE)
        con.execute(_NO_DELETE)
        marked = _coverage_mark(con, run_id, unknown)
        _assert_replaced(con, wanted_rows)
    _write_removed(removed_path, removing)
    after_rows = [dict(row) for row in con.execute(
        "SELECT code, ex_date, amount FROM cash_dividends ORDER BY code, ex_date")]
    after: dict[str, int] = {}
    for row in after_rows:
        after[row["code"]] = after.get(row["code"], 0) + 1
    return {
        "announcement_rows": len(wanted_rows),
        "announcement_codes": sorted(announcement),
        "verified_none": sorted(verified),
        "unknown_by_theme": unknown,
        "themes_marked": marked,
        "deleted": len(removing),
        "inserted": len(inserting),
        "before": before,
        "after": after,
        "removed_csv": str(removed_path),
    }


def apply_replace(db: Path = DB.MARKET_DB, *, events_path: Path | None = None, readme_path: Path | None = None,
                  apply: bool = False, log=print) -> dict:
    events_path = events_path or (DB.ROOT / "incoming/grok-pit-20261022/etf_events.csv")
    readme_path = readme_path or (DB.ROOT / "incoming/grok-pit-20261022/README.md")
    wanted, verified = announcement_rows(events_path, readme_path)
    report: dict = {
        "apply": apply,
        "announcement_rows": len(wanted),
        "verified_none": sorted(verified),
        "unknown_by_theme": unknown_dividend_codes(U.load(), {r["code"] for r in wanted}, verified),
    }
    if not apply:
        log(f"将写入现金分红 {len(wanted)} 行；核查后无分红 {len(verified)} 只。未写库。")
        return report
    ledger = HashLedger(db)
    con = DB.connect(db)
    try:
        ledger.before("replace_dividends start_run")
        run_id = DB.start_run(con, "update", args={
            "job": "replace_cash_dividends",
            "events": str(events_path.relative_to(DB.ROOT)) if events_path.is_relative_to(DB.ROOT) else str(events_path),
            "ex_date_corrections": [list(k) + [v] for k, v in EX_DATE_CORRECTIONS.items()],
        })
        ledger.after("replace_dividends start_run")
        removed = DB.ROOT / "results" / "inventory" / f"cash_dividends_removed-{run_id}.csv"
        ledger.before("replace_dividends write")
        detail = replace_from_events(con, run_id, events_path, readme_path, removed)
        ledger.after("replace_dividends write")
        ledger.before("replace_dividends finish_run")
        DB.finish_run(con, run_id, "ok")
        ledger.after("replace_dividends finish_run")
        report.update(detail)
        report["run_id"] = run_id
        report["integrity"] = con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()
    report["hashes"] = ledger.lines
    report["status"] = "ok"
    log(f"  分红替换 run_id={report['run_id']} 删除 {report['deleted']} 行，写入 {report['inserted']} 行")
    return report


def load_dividends(db, codes) -> dict[str, list[dict]]:
    """只读。表还不存在时返回空，调用方按不复权价继续。"""
    wanted = [c for c in dict.fromkeys(codes or []) if c]
    if not wanted or not Path(db).exists():
        return {}
    con = DB.connect(db, readonly=True)
    try:
        have = con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'cash_dividends'").fetchone()
        if not have:
            return {}
        marks = ",".join("?" * len(wanted))
        out: dict[str, list[dict]] = {}
        for row in con.execute(
                f"""SELECT code, ex_date, amount, prev_close FROM cash_dividends
                    WHERE code IN ({marks}) ORDER BY code, ex_date""", tuple(wanted)):
            out.setdefault(row["code"], []).append(
                {"ex_date": row["ex_date"], "amount": row["amount"], "prev_close": row["prev_close"]})
        return out
    finally:
        con.close()
