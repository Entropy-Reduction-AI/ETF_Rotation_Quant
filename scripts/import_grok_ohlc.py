"""把 incoming/grok-ohlc-20261021 的价格指数开高低导入 ohlc_supplement。

不改 bars，不把补充行混进已有序列。开=高=低=收的平盘行不导入。
tr_closes.csv 不导入：offline-supplement 只接受 H00300 三个年末日的中证原件，
现有机制不改代码不能接收这些全收益年末收盘；那些缺日按 I-29 第 (2) 条当零星缺口。
可重跑：算出的目标行与表内一致时不写库。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data import db as DB  # noqa: E402
from src.data.date_constraints import date_rule  # noqa: E402

DIR_NAME = "incoming/grok-ohlc-20261021"
REL_TOL = 0.0005          # 0.05%
MIN_SHARE = 0.99
DDL = f"""
CREATE TABLE IF NOT EXISTS ohlc_supplement (
    code        TEXT NOT NULL CHECK (length(code) > 0),
    date        TEXT NOT NULL CHECK ({date_rule('ohlc_supplement', 'date')}),
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    volume      REAL,
    source      TEXT NOT NULL CHECK (length(source) > 0),
    file_sha256 TEXT NOT NULL CHECK (length(file_sha256) = 64),
    PRIMARY KEY (code, date)
) WITHOUT ROWID;
"""
TR_CLOSES_NOTE = (
    "不导入 tr_closes.csv：offline-supplement 只接受 H00300 的 2008-12-31、2009-12-31、2010-12-31"
    "（FORMAT h00300-year-end-v1，indexCode 必须是 H00300）。现有机制不改代码不能接收这些全收益年末收盘。"
    "按 I-29 第 (2) 条当零星缺口，不写入 bars，也不写入 ohlc_supplement。"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _num(text) -> float | None:
    if text is None or str(text).strip() == "":
        return None
    return float(text)


def parse_price_csv(path: Path) -> tuple[list[dict], int]:
    """返回 (可导入行, 跳过的平盘行数)。不平、非正或日期重复时抛 ValueError，整份文件拒收。"""
    rows, seen, flats = [], set(), 0
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            day = (raw.get("date") or "").strip()
            open_, high, low, close = _num(raw.get("open")), _num(raw.get("high")), _num(raw.get("low")), _num(raw.get("close"))
            values = (open_, high, low, close)
            if day in seen:
                raise ValueError(f"重复日期 {day}")
            seen.add(day)
            if any(v is None or not (v > 0) or v != v or v in (float("inf"), float("-inf")) for v in values):
                raise ValueError(f"{day or '空日期'} 开高低收不是正数")
            if not (low <= min(open_, close) <= max(open_, close) <= high):
                raise ValueError(f"{day} 不满足 low ≤ 开收 ≤ high")
            if open_ == high == low == close:
                flats += 1
                continue
            rows.append({"date": day, "open": open_, "high": high, "low": low, "close": close, "volume": _num(raw.get("volume"))})
    return rows, flats


def bar_closes(con, code: str) -> dict[str, float]:
    return {row[0]: row[1] for row in con.execute(
        "SELECT date, close FROM bars WHERE code = ? AND adj = 'raw' AND close > 0", (code,))}


def tr_codes(con, price_code: str) -> list[str]:
    """价格指数配对的全收益代码：tr_code_used，否则与价格代码不同的 series_code。"""
    found = []
    for series, tr in con.execute(
            "SELECT series_code, tr_code_used FROM coverage_latest WHERE code = ?", (price_code,)):
        for cand in (tr, series):
            if cand and cand != price_code and cand not in found:
                found.append(cand)
    return found


def close_check(supplement: dict[str, float], bars: dict[str, float]) -> tuple[bool, str]:
    overlap = [day for day in supplement if day in bars and bars[day] > 0 and supplement[day] > 0]
    if not overlap:
        return True, f"与 bars 无重叠日（补充 {len(supplement)} 行），收盘对照跳过"
    passed = sum(abs(supplement[day] - bars[day]) / bars[day] <= REL_TOL for day in overlap)
    share = passed / len(overlap)
    if share < MIN_SHARE:
        return False, f"收盘相对差 ≤ 0.05% 的重叠日 {passed}/{len(overlap)} = {share:.2%}，低于 99%"
    return True, f"收盘对照通过 {passed}/{len(overlap)}"


def k_check(supplement: dict[str, float], total_return: dict[str, float], tr_code: str) -> tuple[bool, str]:
    """k = 全收益收盘 / 补充收盘。至少 99% 的相邻重叠日 k 的变化 ≥ −0.05%。"""
    if not total_return:
        return False, f"配对全收益 {tr_code} 不在 bars，无法做 k 日变化检验"
    days = sorted(day for day in supplement if day in total_return and total_return[day] > 0 and supplement[day] > 0)
    if len(days) < 2:
        return False, f"配对全收益 {tr_code} 重叠不足 2 日，无法做 k 日变化检验"
    ks = [total_return[day] / supplement[day] for day in days]
    changes = [ks[i] / ks[i - 1] - 1 for i in range(1, len(ks))]
    passed = sum(change >= -REL_TOL for change in changes)
    share = passed / len(changes)
    if share < MIN_SHARE:
        worst = min(changes)
        return False, (f"k 日变化 ≥ −0.05% 的日子 {passed}/{len(changes)} = {share:.2%}，低于 99%"
                       f"（{tr_code}，最差 {worst:.4%}）")
    return True, f"k 对照通过 {tr_code} {passed}/{len(changes)}"


def load_manifest(path: Path) -> dict:
    import json
    return json.loads(path.read_text(encoding="utf-8"))


def collect(con, incoming: Path, manifest: dict, log) -> tuple[list[tuple], list[str]]:
    wanted, rejected = [], []
    for entry in manifest["files"]:
        name = entry["file"]
        if "index_code" not in entry:
            continue
        code = entry["index_code"]
        path = incoming / name
        digest = sha256_file(path)
        if digest != entry["sha256"]:
            rejected.append(f"{code}: sha256 与 MANIFEST 不一致（文件 {digest}，清单 {entry['sha256']}）")
            continue
        try:
            parsed, flats = parse_price_csv(path)
        except (ValueError, OSError, csv.Error) as exc:
            rejected.append(f"{code}: {exc}")
            continue
        if not parsed:
            log(f"  跳过 {code}: 没有可导入的非平盘行（平盘 {flats}）")
            continue
        supplement = {row["date"]: row["close"] for row in parsed}
        ok, detail = close_check(supplement, bar_closes(con, code))
        notes = [detail, f"平盘跳过 {flats}"]
        if ok:
            for tr_code in tr_codes(con, code):
                passed, k_detail = k_check(supplement, bar_closes(con, tr_code), tr_code)
                notes.append(k_detail)
                if not passed:
                    ok = False
                    break
        if not ok:
            rejected.append(f"{code}: " + "；".join(notes))
            continue
        log(f"  接收 {code}: {len(parsed)} 行；" + "；".join(notes))
        source = entry["source"]
        for row in parsed:
            wanted.append((code, row["date"], row["open"], row["high"], row["low"], row["close"],
                           row["volume"], source, digest))
    wanted.sort(key=lambda row: (row[0], row[1]))
    return wanted, rejected


def existing_rows(path: Path):
    con = DB.connect(path, readonly=True)
    try:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'ohlc_supplement'").fetchone():
            return None
        return [tuple(row) for row in con.execute(
            "SELECT code, date, open, high, low, close, volume, source, file_sha256 "
            "FROM ohlc_supplement ORDER BY code, date")]
    finally:
        con.close()


def write_rows(path: Path, rows: list[tuple]) -> None:
    con = DB.connect(path)
    try:
        con.execute(DDL)
        with con:
            con.execute("DELETE FROM ohlc_supplement")
            con.executemany("INSERT INTO ohlc_supplement VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    finally:
        con.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="导入价格指数开高低到 ohlc_supplement")
    parser.add_argument("--db", type=Path, default=DB.MARKET_DB)
    parser.add_argument("--incoming", type=Path, default=ROOT / DIR_NAME)
    args = parser.parse_args(argv)
    db, incoming = Path(args.db), Path(args.incoming)
    log = print
    before = sha256_file(db)
    log(f"market.sqlite SHA256 before: {before}")
    log(TR_CLOSES_NOTE)
    manifest = load_manifest(incoming / "MANIFEST.json")
    con = DB.connect(db, readonly=True)
    try:
        wanted, rejected = collect(con, incoming, manifest, log)
    finally:
        con.close()
    for item in rejected:
        log(f"拒收 {item}")
    current = existing_rows(db)
    if current == wanted:
        after = sha256_file(db)
        log(f"目标行与 ohlc_supplement 一致（{len(wanted)} 行），不写库")
        log(f"market.sqlite SHA256 after: {after}")
        return 0
    write_rows(db, wanted)
    after = sha256_file(db)
    log(f"写入 ohlc_supplement {len(wanted)} 行，拒收 {len(rejected)} 个代码")
    log(f"market.sqlite SHA256 after: {after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
