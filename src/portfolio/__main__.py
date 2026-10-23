"""命令行：python -m src.portfolio replicate|target …"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.portfolio.config import ROOT, FallbackError, load_config
from src.portfolio.execution import schedule_execution
from src.portfolio.replicate import replicate
from src.portfolio.target import (
    decision_state,
    load_calendar,
    load_closes,
    load_fund_nav,
    plan_targets,
)

def _fmt_pct(value: float) -> str:
    return f"{value:+.1%}"


def _print_replicate(result: dict) -> None:
    a = result["monthly"]["a_valve"]
    b = result["monthly"]["blend"]
    d = result["daily"]
    print(f"设计期 {result['monthly']['first']} → {result['monthly']['last']}")
    print(f"月频 A股等权+阀25/10  {_fmt_pct(a['cagr'])}  {_fmt_pct(a['max_drawdown'])}  切换 {a['switches']}")
    print(f"月频 A股70%(阀25/10)+海外30%  {_fmt_pct(b['cagr'])}  {_fmt_pct(b['max_drawdown'])}")
    print(f"与 d2 的差（百分点） {json.dumps(result['d2_delta_pp'], ensure_ascii=False)}")
    print(f"日频 {d['first']} → {d['last']}  {_fmt_pct(d['cagr'])}  {_fmt_pct(d['max_drawdown'])}  切换 {d['switches']}")


def _print_target(result: dict) -> None:
    drawdown = result["a_share_drawdown_from_high"]
    dd = "—" if drawdown is None else _fmt_pct(drawdown)
    print(f"{result['date']}  信号日 {result['signal_date']}  阀 {result['valve']}  "
          f"A股距高点 {dd}  QDII {result['qdii_premium']}")
    print(f"{'容器':<12} {'代码':<8} {'权重':>10}  QDII")
    for row in result["weights"]:
        print(f"{row['container']:<12} {row['execution_code']:<8} {row['weight']:10.6f}  {row['qdii_premium']}")


def _print_holdings(result: dict) -> None:
    print(f"决策 {result['decision_date']}  执行 {result['execution_date']}  信号日 {result['signal_date']}  "
          f"阀 {result['valve']}  海外偏离前权重 {result['overseas_weight_before']:.4f}")
    print(f"净值截止 {result['nav_cutoff']}  滞后 {result['nav_lag_trading_days']}  来源 {result['nav_source']}")
    print("规则 " + ", ".join(result["rules"]))
    print(f"{'池':<8} {'代码':<8} {'净值日':<12} {'溢价':>10}  买入")
    for row in result["premiums"]:
        mark = "是" if row["chosen"] else ""
        print(f"{row['pool']:<8} {row['code']:<8} {row['nav_date']:<12} {row['premium']:10.4%}  {mark}")
    print(f"{'代码':<8} {'名称':<10} {'腿':<10} {'股数':>10} {'价格':>10}")
    for row in result["targets"]:
        print(f"{row['code']:<8} {row['name']:<10} {row['sleeve']:<10} {row['shares']:10d} {row['price']:10.4f}")
    print(f"剩余现金 {result['residual_cash']:.2f}")


def _read_json_map(path: Path | None) -> dict:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FallbackError(f"{path} 必须是对象")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.portfolio")
    parser.add_argument("--config", type=Path, default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)
    rep = sub.add_parser("replicate")
    rep.add_argument("--panel", type=Path, required=True)
    rep.add_argument("--end", default=None)
    rep.add_argument("--haven-db", type=Path, default=None)
    rep.add_argument("--out", type=Path, default=None)
    tgt = sub.add_parser("target")
    tgt.add_argument("--panel", type=Path, required=True)
    tgt.add_argument("--date", required=True)
    tgt.add_argument("--equity", type=float, required=True)
    tgt.add_argument("--holdings", type=Path, default=None)
    tgt.add_argument("--nav-db", type=Path, required=True)
    tgt.add_argument("--price-db", type=Path, default=None)
    tgt.add_argument("--status", type=Path, default=None)
    tgt.add_argument("--nav-source", default="fund_nav")
    tgt.add_argument("--nav-note", default="")
    tgt.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    try:
        if args.cmd == "replicate":
            end = args.end or cfg.design_end.date().isoformat()
            haven = args.haven_db
            if haven is None:
                default_db = ROOT / "data" / "market.sqlite"
                haven = default_db if default_db.exists() else None
            result = replicate(args.panel, end, cfg, haven_db=haven)
            _print_replicate(result)
            if args.out:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            return 0 if result["matches_d2"] else 1
        holdings = {str(code): value for code, value in _read_json_map(args.holdings).items()}
        statuses = {str(code): str(value) for code, value in _read_json_map(args.status).items()}
        price_db = args.price_db or (ROOT / "data" / "market.sqlite")
        codes = [cfg.haven_code, *holdings]
        for book in cfg.funds:
            codes.append(book.primary)
            codes.extend(alt.code for alt in book.alternates)
        for pool in cfg.pools:
            codes.extend(pool.codes)
        trading_days = load_calendar(price_db)
        schedule = schedule_execution(args.date, trading_days)
        # 阀和 A 股目标用决策日（上月最后一个交易日的收盘）。溢价和带宽也用这一天的收盘：
        # 执行日的收盘当时还没有。海外带宽和 A 股对齐写在同一张执行单上。
        # D7 关掉慢阀后不再读阀状态，A 股腿按在场出目标。
        if cfg.valve_enabled:
            state = decision_state(args.panel, schedule["decision_date"], cfg)
            in_market = state["in_market"]
            signal_date = state["signal_date"]
        else:
            in_market = True
            signal_date = schedule["decision_date"]
        nav_rows = load_fund_nav(args.nav_db)
        sources = sorted({row.source for row in nav_rows if row.source})
        nav_source = sources[0] if args.nav_source == "fund_nav" and len(sources) == 1 else args.nav_source
        result = plan_targets(
            cfg, as_of=schedule["decision_date"], equity=args.equity, holdings=holdings,
            prices=load_closes(price_db, sorted(set(codes)), schedule["decision_date"].date().isoformat()),
            nav_rows=nav_rows, trading_days=trading_days, statuses=statuses,
            in_market=in_market, a_share_due=schedule["a_share_due"],
            signal_date=signal_date, decision_date=schedule["decision_date"],
            execution_date=schedule["execution_date"], nav_source=nav_source, nav_note=args.nav_note)
        _print_holdings(result)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return 0
    except FallbackError as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
