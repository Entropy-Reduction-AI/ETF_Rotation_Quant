"""python -m src.v4.scorecard reference

`reference` 复现 v3.1 P1 的参考数。`score` 对另一份设计期 paths/held 出同一张卡。
两条命令都不跑组合，也不接受 2015-12-31 之后的收益。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import DESIGN_END, DESIGN_START, ScorecardError, payload, reference_scorecard, score_book

REPO = Path(__file__).resolve().parents[3]


def _print_report(report: dict) -> None:
    summary = report["summary"]
    show = summary.rename(columns={
        "years": "持有年",
        "comparator": "对照",
        "n": "起点数",
        "win_pct": "跑赢%",
        "median_excess_pp": "中位差",
        "worst_excess_pp": "最差",
        "worst_start": "最差起点",
    })
    columns = ["持有年", "对照", "起点数", "跑赢%", "中位差", "最差", "最差起点"]
    print(f"{report['name']}  {report['start']} → {report['end']}  {report['n_days']} 个交易日")
    print("任意起点：跑赢占比为四舍五入后的整数；中位差和最差是年化超额的百分点。")
    print(show[columns].to_string(index=False))
    print()
    states = report["states"].rename(columns={
        "months": "月数",
        "win_month_pct": "跑赢月份%",
        "cash_pp": "拿现金",
        "selection_pp": "选标的",
        "excess_pp": "合计",
        "excess_pp_board": "看板整数",
    })
    print("四种状态：合计是日超额相加后的百分点（1 位小数）。看板整数是对这一位小数再四舍五入。")
    print(states.to_string())
    capture = report["capture"]
    print()
    print(f"跟涨 {capture['up_capture']:.2f}（{capture['up_months']} 个月）")
    print(f"跟跌 {capture['down_capture']:.2f}（{capture['down_months']} 个月）")
    if "acceptance" in report:
        print()
        print("验收通过" if report["acceptance"]["ok"] else "验收未通过")
        for item in report["acceptance"]["checks"]:
            mark = "ok" if item["ok"] else "DIFF"
            print(f"  {mark}  {item['name']}: {item['got']}  期望 {item['want']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v4 打分卡：任意起点与四种市场状态")
    sub = parser.add_subparsers(dest="command", required=True)

    reference = sub.add_parser("reference", help="用 v3.1 P1 复现参考数字")
    reference.add_argument("--db", default=None)
    reference.add_argument("--json", action="store_true", help="只打印 JSON")

    score = sub.add_parser("score", help="对一份设计期 paths.csv / held.csv 出打分卡")
    score.add_argument("--paths", required=True)
    score.add_argument("--held", required=True)
    score.add_argument("--db", default=None)
    score.add_argument("--start", default=DESIGN_START)
    score.add_argument("--end", default=str(DESIGN_END.date()))
    score.add_argument("--name", default="strategy")
    score.add_argument("--json", action="store_true", help="只打印 JSON")

    args = parser.parse_args(argv)
    database = Path(args.db) if args.db else REPO / "data" / "market.sqlite"
    try:
        if args.command == "reference":
            report = reference_scorecard(REPO, database)
        else:
            report = score_book(
                Path(args.paths), Path(args.held), database,
                start=args.start, end=args.end, name=args.name,
            )
    except ScorecardError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(payload(report), ensure_ascii=False, indent=2))
    else:
        _print_report(report)
    if report.get("acceptance", {}).get("ok") is False:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
