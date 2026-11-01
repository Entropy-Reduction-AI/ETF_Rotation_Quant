"""python -m src.v5 design

只跑设计期的 S0、P1、P2。没有全期开关，不写 LOCK，不打标签。
复核签收之前不要运行。
"""
from __future__ import annotations

import argparse

from src.v5.campaign import run_design


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v5 设计期：S0 → P1 → P2")
    parser.add_argument("step", choices=["design"])
    args = parser.parse_args(argv)
    if args.step == "design":
        summary = run_design()
        print(f"C1 pass={summary['c1_passed']} P2 base={summary['base_arm']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
