"""python -m src.v51 design
python -m src.v51 controls

设计期只跑两个池。controls 跑 R0、C-等权和 C-波动比。不写 LOCK，不打标签。
"""
from __future__ import annotations

import argparse

from src.v51.design import run_design


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v5.1 设计期与 R5 对照")
    parser.add_argument("step", choices=["design", "controls"])
    args = parser.parse_args(argv)
    if args.step == "design":
        summary = run_design()
        print(f"db={summary['db_sha256']}", flush=True)
    else:
        from src.v51.controls import run_controls

        summary = run_controls()
        print(
            f"db={summary['db_sha256']} equal={summary['equal_cagr']:.6f} vol={summary['vol_cagr']:.6f}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
