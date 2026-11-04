"""python -m src.v51 design
python -m src.v51 controls
python -m src.v51 gpool

设计期只跑两个池。controls 跑 R0、C-等权和 C-波动比。
gpool 跑 §7.2 的 G 池一次。不写 LOCK，不打标签。
"""
from __future__ import annotations

import argparse

from src.v51.design import run_design


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v5.1 设计期、R5 对照和 G 池")
    parser.add_argument("step", choices=["design", "controls", "gpool"])
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
    else:
        from src.v51.gpool import run_gpool

        summary = run_gpool()
        full = summary["full"]
        print(
            f"cagr={full['cagr']:.6f} calmar={full['calmar']:.6f} bm={full['bm_cagr']:.6f}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
