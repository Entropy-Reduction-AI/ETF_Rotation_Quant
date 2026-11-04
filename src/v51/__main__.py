"""python -m src.v51 design

只跑 v5.1 设计期的两个池。没有全期开关，不写 LOCK，不打标签。
"""
from __future__ import annotations

import argparse

from src.v51.design import run_design


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v5.1 设计期：U-指数和 U-可交易")
    parser.add_argument("step", choices=["design"])
    args = parser.parse_args(argv)
    if args.step == "design":
        summary = run_design()
        print(f"db={summary['db_sha256']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
