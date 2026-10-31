"""D25-8：510880 在 2008-01-02 的错价只插入一条修正收盘。

不覆盖 `bars` 里的不复权，也不覆盖 `v4_series` 里的腾讯后复权。
统一后复权入口在选中腾讯之后读这条修正。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from src.v4.data.hfq import CORRECTION_KIND
from src.v4.data.r1b import ensure

CODE = "510880"
DAY = "2008-01-02"
PREV_DAY = "2007-12-28"
NEXT_DAY = "2008-01-03"
BAD_RAW = 1.467
BAD_HFQ = 0.961
PREV_RAW = 4.637
PREV_HFQ = 3.039
NEXT_RAW = 4.794
# 东财日 K（fqt=0）2008-01-02 收盘。新浪、搜狐同一天收盘也是 4.649。
EASTMONEY_CLOSE = Decimal("4.649")
EASTMONEY_OPEN = Decimal("4.640")
EASTMONEY_HIGH = Decimal("4.692")
EASTMONEY_LOW = Decimal("4.581")
# 天天基金 / 东财 f10/lsjz 单位净值。相对 2007-12-28 的 4.6390，涨跌 +0.56%，无分红标记。
UNIT_NAV = Decimal("4.6650")
SOURCE = "d25-8-eastmoney-kline"
SOURCE_URL = (
    "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    "?secid=1.510880&klt=101&fqt=0&beg=20071228&end=20080104"
    "&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
)
NAV_URL = (
    "https://api.fund.eastmoney.com/f10/lsjz?fundCode=510880"
    "&pageIndex=1&pageSize=20&startDate=2007-12-20&endDate=2008-01-15"
)
REASON = (
    "D25-8。2008-01-02 腾讯不复权收盘 1.467、腾讯后复权 0.961 为错价；"
    "前一日不复权 4.637，后一日 4.794。东财日 K 不复权收盘 4.649"
    "（开 4.640 高 4.692 低 4.581，涨跌 +0.26%）。"
    "天天基金单位净值 4.6650，相对 2007-12-28 的 4.6390 上涨 0.56%，无分红标记。"
    "修正后复权 = 2007-12-28 腾讯后复权 3.039 × 4.649/4.637，仍用腾讯刻度。"
    "不覆盖 bars，不覆盖 tencent_etf_hfq。"
)


class CorrectionError(RuntimeError):
    pass


def corrected_hfq_close() -> float:
    """前一日腾讯后复权乘以东财不复权的当日涨跌。不用错价那一天的比例。"""
    value = Decimal(str(PREV_HFQ)) * EASTMONEY_CLOSE / Decimal(str(PREV_RAW))
    return float(value)


def _close(con: sqlite3.Connection, sql: str, params: tuple) -> float | None:
    row = con.execute(sql, params).fetchone()
    if row is None or row[0] is None:
        return None
    return float(row[0])


def _same(left: float | None, right: float) -> bool:
    return left is not None and abs(left - right) <= 1e-9


def insert_correction(con: sqlite3.Connection, *, fetched_at: str | None = None) -> dict:
    """插入一条修正收盘。原行还在，且数值必须仍是错价，否则拒绝。"""
    ensure(con)
    raw = _close(
        con,
        "SELECT close FROM bars WHERE code = ? AND adj = 'raw' AND date = ?",
        (CODE, DAY),
    )
    hfq = _close(
        con,
        """SELECT close FROM v4_series
           WHERE code = ? AND kind = 'backward' AND source = 'tencent_etf_hfq' AND date = ?""",
        (CODE, DAY),
    )
    prev_raw = _close(
        con,
        "SELECT close FROM bars WHERE code = ? AND adj = 'raw' AND date = ?",
        (CODE, PREV_DAY),
    )
    prev_hfq = _close(
        con,
        """SELECT close FROM v4_series
           WHERE code = ? AND kind = 'backward' AND source = 'tencent_etf_hfq' AND date = ?""",
        (CODE, PREV_DAY),
    )
    if not _same(raw, BAD_RAW) or not _same(hfq, BAD_HFQ):
        raise CorrectionError(f"{CODE} {DAY} 原收盘不是登记的错价，拒绝插入")
    if not _same(prev_raw, PREV_RAW) or not _same(prev_hfq, PREV_HFQ):
        raise CorrectionError(f"{CODE} {PREV_DAY} 与修正公式用的前收不一致，拒绝插入")
    close = corrected_hfq_close()
    existing = con.execute(
        """SELECT close, source, method FROM v4_series
           WHERE code = ? AND kind = ? AND date = ?""",
        (CODE, CORRECTION_KIND, DAY),
    ).fetchone()
    if existing is not None:
        if not _same(float(existing[0]), close) or str(existing[1]) != SOURCE:
            raise CorrectionError(f"{CODE} {DAY} 已有不同的修正行，不覆盖")
        _assert_originals(con)
        return {"status": "already", "close": close, "kind": CORRECTION_KIND}
    when = fetched_at or datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds")
    with con:
        con.execute(
            """INSERT INTO v4_series
               (code, kind, date, open, high, low, close, volume, unit_nav, accum_nav, filled,
                source, source_url, method, fetched_at)
               VALUES (?, ?, ?, NULL, NULL, NULL, ?, NULL, NULL, NULL, 0, ?, ?, ?, ?)""",
            (CODE, CORRECTION_KIND, DAY, close, SOURCE, SOURCE_URL, REASON, when),
        )
    _assert_originals(con)
    return {"status": "inserted", "close": close, "kind": CORRECTION_KIND, "fetched_at": when}


def _assert_originals(con: sqlite3.Connection) -> None:
    raw = _close(
        con,
        "SELECT close FROM bars WHERE code = ? AND adj = 'raw' AND date = ?",
        (CODE, DAY),
    )
    hfq = _close(
        con,
        """SELECT close FROM v4_series
           WHERE code = ? AND kind = 'backward' AND source = 'tencent_etf_hfq' AND date = ?""",
        (CODE, DAY),
    )
    if not _same(raw, BAD_RAW) or not _same(hfq, BAD_HFQ):
        raise CorrectionError("插入之后原错价行变了")


def crosscheck_rows(corrected: float) -> list[dict]:
    """核对表。数字来自已经对照过的东财日 K 和天天基金单位净值。"""
    return [
        {
            "source": "bars.raw tencent_etf",
            "date": DAY,
            "field": "close",
            "value": f"{BAD_RAW:.3f}",
            "kept": "yes",
            "note": "错价，不覆盖",
        },
        {
            "source": "v4_series tencent_etf_hfq",
            "date": DAY,
            "field": "close",
            "value": f"{BAD_HFQ:.3f}",
            "kept": "yes",
            "note": "错价，不覆盖",
        },
        {
            "source": "eastmoney kline fqt=0",
            "date": DAY,
            "field": "close",
            "value": f"{EASTMONEY_CLOSE:.3f}",
            "kept": "",
            "note": (
                f"开 {EASTMONEY_OPEN:.3f} 高 {EASTMONEY_HIGH:.3f} 低 {EASTMONEY_LOW:.3f}；"
                f"前一日 {PREV_RAW:.3f}，后一日 {NEXT_RAW:.3f}；{SOURCE_URL}"
            ),
        },
        {
            "source": "tiantian lsjz unit_nav",
            "date": DAY,
            "field": "unit_nav",
            "value": f"{UNIT_NAV:.4f}",
            "kept": "",
            "note": f"相对 2007-12-28 单位净值 4.6390 上涨 0.56%，无分红标记；{NAV_URL}",
        },
        {
            "source": SOURCE,
            "date": DAY,
            "field": "hfq_close",
            "value": f"{corrected:.12g}",
            "kept": "inserted",
            "note": REASON,
        },
    ]


def main() -> int:
    import csv
    import os
    from pathlib import Path

    from src.data import db as DB

    if os.environ.get("ETF_LEDGER_TESTING"):
        print("测试环境拒绝写默认库")
        return 2
    con = DB.connect(DB.MARKET_DB)
    try:
        result = insert_correction(con)
    finally:
        con.close()
    digest = DB.sha256_file(DB.MARKET_DB)
    out = Path("results/v4/inventory/r5c/510880-2008-01-02-crosscheck.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = crosscheck_rows(float(result["close"]))
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("source", "date", "field", "value", "kept", "note"),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"status={result['status']} close={result['close']:.12g}")
    print(f"sha256={digest}")
    print(f"bytes={DB.MARKET_DB.stat().st_size}")
    print(f"crosscheck={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
