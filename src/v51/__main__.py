"""python -m src.v51 design
python -m src.v51 controls
python -m src.v51 gpool
python -m src.v51 r1
python -m src.v51 robustness
python -m src.v51 turnover
python -m src.v51 gate

设计期、R5 对照、G 池、R1、稳健性和换手。gate 只收草稿的最后一行。
不写 LOCK，不打标签。
"""
from __future__ import annotations

import argparse

from src.v51.design import run_design


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v5.1 设计期、对照、稳健性和入围结论")
    parser.add_argument(
        "step",
        choices=["design", "controls", "gpool", "r1", "robustness", "turnover", "gate"],
    )
    args = parser.parse_args(argv)
    if args.step == "design":
        summary = run_design()
        print(f"db={summary['db_sha256']}", flush=True)
    elif args.step == "controls":
        from src.v51.controls import run_controls

        summary = run_controls()
        print(
            f"db={summary['db_sha256']} equal={summary['equal_cagr']:.6f} vol={summary['vol_cagr']:.6f}",
            flush=True,
        )
    elif args.step == "gpool":
        from src.v51.gpool import run_gpool

        summary = run_gpool()
        full = summary["full"]
        print(
            f"cagr={full['cagr']:.6f} calmar={full['calmar']:.6f} bm={full['bm_cagr']:.6f}",
            flush=True,
        )
    elif args.step == "r1":
        from src.v51.structure import run_r1

        summary = run_r1()
        print(f"db={summary['db_sha256']}", flush=True)
    elif args.step == "robustness":
        from src.v51.robustness import run_robustness

        summary = run_robustness()
        print(f"db={summary['db_sha256']} cases={','.join(summary['cases'])}", flush=True)
    elif args.step == "turnover":
        from src.v51.turnover import run_turnover

        summary = run_turnover()
        for pool, row in summary.items():
            print(f"{pool} turnover={row['turnover_one_way']:.6f} cost={row['cost']:.6f}", flush=True)
    else:
        from src.v51.gate import write_gate

        summary = write_gate()
        print(summary["note"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
