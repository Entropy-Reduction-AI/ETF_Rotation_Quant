"""python -m src.report evidence"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.report.evidence import ROOT, write_evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.report")
    sub = parser.add_subparsers(dest="cmd", required=True)
    evidence = sub.add_parser("evidence")
    evidence.add_argument("--panel", type=Path, default=ROOT / "outputs" / "panel-2026-09-30.sqlite")
    evidence.add_argument("--market-db", type=Path, default=ROOT / "data" / "market.sqlite")
    evidence.add_argument("--out", type=Path, default=ROOT / "results" / "report")
    evidence.add_argument("--assets", type=Path, default=ROOT / "docs" / "assets")
    args = parser.parse_args(argv)
    if args.cmd == "evidence":
        write_evidence(args.panel, args.market_db, args.out, args.assets)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
