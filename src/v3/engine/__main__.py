"""python -m src.v3.engine --arm A --pool index --debug

debug 不写 trial-ledger。非 debug 的配置运行会追加一行。本入口不创建 LOCK。
"""
from __future__ import annotations

import argparse

from src.report.metrics import cagr, max_drawdown

from .runner import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v3 §4 回测")
    parser.add_argument("--arm", required=True, choices=["A", "B", "S1", "S2"])
    parser.add_argument("--pool", required=True, choices=["index", "tradable"])
    parser.add_argument("--end", default=None)
    parser.add_argument("--full-period", action="store_true")
    parser.add_argument("--freeze-sha", default=None)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--cost-multiplier", type=float, default=1.0)
    parser.add_argument("--n", type=int, default=None)
    parser.add_argument("--freq", choices=["week", "month"], default=None)
    parser.add_argument("--ledger", default=None)
    args = parser.parse_args(argv)
    book = run(
        args.arm, args.pool, args.end, full_period=args.full_period, freeze_sha=args.freeze_sha,
        debug=args.debug, cost_multiplier=args.cost_multiplier, n=args.n, freq=args.freq,
        ledger_path=args.ledger)
    if book.net.empty:
        print("没有收益")
        return 0
    depth = max_drawdown(book.net)
    print(
        f"arm={args.arm} pool={args.pool} {book.net.index[0].date()}→{book.net.index[-1].date()} "
        f"n={len(book.net)} cagr={cagr(book.net):.6f} max_drawdown={depth['max_drawdown']:.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
