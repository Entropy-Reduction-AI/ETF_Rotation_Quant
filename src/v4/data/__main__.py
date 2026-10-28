"""python -m src.v4.data ingest|hash CODE

不提供回测或组合收益命令。
"""
from __future__ import annotations

import sys

from src.data import db as DB

from .ingest import COVERAGE, _read_bars, _read_events, run
from .parse import bar_sha256, series_sha256


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if any(token in {"backtest", "returns", "pnl", "timing"} for token in argv):
        print("v4-R1 只取数和登记，不计算组合收益。")
        return 2
    if not argv or argv[0] not in {"ingest", "hash"}:
        print("用法: python -m src.v4.data ingest|hash CODE")
        return 2
    if argv[0] == "hash":
        if len(argv) != 2:
            print("用法: python -m src.v4.data hash CODE")
            return 2
        return _hash(argv[1])
    con = DB.connect(DB.MARKET_DB)
    try:
        for line in run(con):
            print(line, flush=True)
    finally:
        con.close()
    print(COVERAGE)
    return 0


def _hash(code: str) -> int:
    con = DB.connect(DB.MARKET_DB, readonly=True)
    try:
        ensure_ro = _table(con, "v4_event")
        bars = _read_bars(con, code)
        print(f"bars {len(bars)} {bar_sha256(bars) if bars else '-'}")
        if not ensure_ro:
            return 0
        for kind, cols in (("dividend", ("date", "amount")), ("split", ("date", "numerator", "denominator"))):
            rows = _read_events(con, code, kind)
            digest = series_sha256(rows, cols) if rows else "-"
            print(f"{kind} {len(rows)} {digest}")
    finally:
        con.close()
    return 0


def _table(con, name: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


if __name__ == "__main__":
    sys.exit(main())
