"""python -m src.v4.data ingest|r1b|r1c|hash CODE

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
        print("v4 只取数和登记，不计算组合收益。")
        return 2
    if not argv or argv[0] not in {"ingest", "r1b", "r1c", "r1e", "hash"}:
        print("用法: python -m src.v4.data ingest|r1b|r1c|r1e|hash CODE")
        return 2
    if argv[0] == "r1e":
        return _r1e(argv[1] if len(argv) > 1 else "all")
    if argv[0] == "r1b":
        return _r1b()
    if argv[0] == "r1c":
        return _r1c()
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


def _r1b() -> int:
    from .r1b import run as run_r1b
    con = DB.connect(DB.MARKET_DB)
    try:
        for line in run_r1b(con):
            print(line, flush=True)
    finally:
        con.close()
    print(COVERAGE)
    return 0


def _r1c() -> int:
    from .r1c import run as run_r1c
    con = DB.connect(DB.MARKET_DB)
    try:
        for line in run_r1c(con):
            print(line, flush=True)
    finally:
        con.close()
    print(COVERAGE)
    return 0


def _r1e(stage: str) -> int:
    from .r1e import run
    if stage == "followup":
        from .r1e_followup import run as run_followup
        run_followup()
        return 0
    if stage not in {"all", "census", "fill", "register", "regroup", "retry"}:
        print("用法: python -m src.v4.data r1e [all|census|fill|register|regroup|retry|followup]")
        return 2
    run(stage)
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
