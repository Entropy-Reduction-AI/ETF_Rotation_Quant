"""python -m src.v3.data validate|coverage|fetch

不提供回测、择时或组合收益命令。
"""
from __future__ import annotations

import sys
from datetime import date

from src.data import db as DB

from . import coverage
from . import emit_universe
from . import pipeline
from . import store
from . import universe as U


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if any(token in {"backtest", "returns", "timing"} for token in argv):
        print("L1 只做数据登记，不跑回测或组合收益。")
        return 2
    if not argv or argv[0] not in {"validate", "coverage", "fetch", "fetch-qdii", "fetch-defensive", "emit"}:
        print("用法: python -m src.v3.data validate|coverage|fetch|fetch-qdii|fetch-defensive|emit")
        return 2
    errors = U.validate()
    if argv[0] == "validate":
        if errors:
            print("\n".join(errors))
            return 1
        print(f"universe ok containers={len(U.containers())}")
        return 0
    if errors and argv[0] == "coverage":
        print("\n".join(errors))
        return 1
    if argv[0] == "emit":
        con = store.connect(DB.MARKET_DB)
        try:
            summary = emit_universe.emit(con)
            errors = U.validate()
            coverage_summary = coverage.write(con)
        finally:
            con.close()
        print("EMIT", summary)
        print("COVERAGE", coverage_summary)
        if errors:
            print("\n".join(errors[:30]))
            return 1
        return 0
    if argv[0] == "coverage":
        con = store.connect(DB.MARKET_DB)
        try:
            summary = coverage.write(con)
        finally:
            con.close()
        print(summary)
        return 0
    if argv[0] == "fetch-defensive":
        from . import defensive
        log: list[str] = []
        report = defensive.run(date(2026, 9, 30), log)
        print("SHA256", report["before"], report["after"])
        print("INTEGRITY", report.get("integrity"))
        print("REMOVED", len(report.get("removed") or []))
        print("AUDIT", len(report.get("audit") or []))
        return 0 if report.get("integrity") == "ok" else 1
    if argv[0] == "fetch-qdii":
        log = []
        report = pipeline.supplement_exchange_qdii(date(2026, 9, 30), log)
        errors = U.validate()
        con = store.connect(DB.MARKET_DB)
        try:
            summary = coverage.write(con)
        finally:
            con.close()
        print("COVERAGE", summary)
        print("SHA256", report["before"], report["after"])
        print("INTEGRITY", report.get("integrity"))
        if errors:
            print("登记表不完整", len(errors))
            print("\n".join(errors[:20]))
            return 1
        return 0
    log: list[str] = []
    report = pipeline.run(date(2026, 9, 30), log=log)
    errors = U.validate()
    if errors:
        print("登记表在取数后不完整:")
        print("\n".join(errors[:40]))
        report["validate_errors"] = len(errors)
    con = store.connect(DB.MARKET_DB)
    try:
        summary = coverage.write(con)
    finally:
        con.close()
    print("COVERAGE", summary)
    print("SHA256", report["before"], report["after"])
    print("INTEGRITY", report.get("integrity"))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
