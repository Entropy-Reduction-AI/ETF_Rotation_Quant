"""python -m src.v5 design
python -m src.v5 robustness

design 只跑设计期的 S0、P1、P2，并把 P2 的上一版写进账本。
robustness 读过关表；§6.1 能确定 F 才跑 §7.1。
没有全期开关，不写 LOCK，不打标签，不跑 §7.2。
"""
from __future__ import annotations

import argparse

from src.v5.campaign import run_design
from src.v5.robustness import run_robustness


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v5 设计期")
    parser.add_argument("step", choices=["design", "robustness"])
    args = parser.parse_args(argv)
    if args.step == "design":
        summary = run_design()
        print(f"C1 pass={summary['c1_passed']} P2 base={summary['base_arm']}", flush=True)
    if args.step == "robustness":
        summary = run_robustness()
        print(
            f"F={summary['final_arm']} C1={summary['enable_c1']} C2={summary['enable_c2']} "
            f"base={summary['base_arm']} rows={summary['n_jobs']} ledger={summary['ledger_rows']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
