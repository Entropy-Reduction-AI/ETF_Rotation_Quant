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
    parser.add_argument("--history-mode", choices=["official", "publish_date"], default="official")
    parser.add_argument("--exit-drawdown", type=float, default=0.10)
    parser.add_argument("--premium-window", type=int, default=None)
    parser.add_argument("--premium-theta", type=float, default=None)
    args = parser.parse_args(argv)
    premium_spec = None
    if args.premium_window is not None or args.premium_theta is not None:
        from src.v3.premium.rules import PremiumSpec
        if args.premium_window is None or args.premium_theta is None:
            print("溢价参数要同时给出 W 和 θ。不给则按预注册逐年选择。")
            return 2
        premium_spec = PremiumSpec(args.premium_window, args.premium_theta)
    book = run(
        args.arm, args.pool, args.end, full_period=args.full_period, freeze_sha=args.freeze_sha,
        debug=args.debug, cost_multiplier=args.cost_multiplier, n=args.n, freq=args.freq,
        ledger_path=args.ledger, history_mode=args.history_mode, exit_drawdown=args.exit_drawdown,
        premium_spec=premium_spec)
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
