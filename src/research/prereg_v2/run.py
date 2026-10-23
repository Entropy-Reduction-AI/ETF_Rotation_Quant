"""预注册 v2 入口。

    python -m src.research.prereg_v2.run --end 2015-12-31

设计期只允许结束日 ≤ 2015-12-31。样本外要同时给出 --oos 和冻结 SHA，
并且 results/v2/oos/LOCK 还不存在。锁先写入（时间、代码 SHA、market.sqlite SHA256），然后才计算。
本模块把样本外计算留在 run_oos；没有 Owner 的单独命令时不要执行那条路径。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from src.research.prereg_v1.panel import PanelError
from src.research.prereg_v2.engine import (
    DESIGN_END,
    FROZEN_SHA,
    OOS_END,
    ROOT,
    RunnerError,
    run_design,
    run_oos,
    sha_matches,
)

DEFAULT_PANEL = ROOT / "outputs" / "panel-2026-09-30.sqlite"
DEFAULT_MARKET = ROOT / "data" / "market.sqlite"
DEFAULT_CONFIG = ROOT / "config" / "portfolio.toml"
DEFAULT_LOCK = ROOT / "results" / "v2" / "oos" / "LOCK"
DESIGN_OUT = ROOT / "results" / "v2" / "design" / "summary.json"
OOS_OUT = ROOT / "results" / "v2" / "oos" / "summary.json"
SHANGHAI = ZoneInfo("Asia/Shanghai")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def write_lock(path: Path, market_db: Path) -> None:
    """样本外锁。调用方已经确认文件不存在。 exclusive create，避免两个人同时写。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "written_at": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
        "code_sha": git_head(),
        "market_sqlite_sha256": sha256_file(market_db) if Path(market_db).exists() else None,
        "prereg_sha": FROZEN_SHA,
    }
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, indent=1) + "\n")


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:+.1%}"


def _share(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1%}"


def _num(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}"


def _print_arms(title: str, arms: dict) -> None:
    print(title)
    print(f"{'臂':<8} {'年化':>8} {'最大回撤':>8} {'在场':>8} {'切换/年':>8}")
    for name in ("B0", "B1", "B2"):
        row = arms[name]
        print(f"{name:<8} {_pct(row['cagr']):>8} {_pct(row['max_drawdown']):>8} "
              f"{_share(row['time_in_market']):>8} {_num(row['switches_per_year']):>8}")


def _print_portfolio(title: str, arms: dict) -> None:
    print(title)
    print(f"{'臂':<8} {'年化':>8} {'最大回撤':>8}")
    for name in ("B0", "B1", "B2"):
        row = arms[name]
        print(f"{name:<8} {_pct(row['cagr']):>8} {_pct(row['max_drawdown']):>8}")


def _print_design(result: dict) -> None:
    real = result["haven_511880"]
    print(f"设计期 → {result['end']}  判定账本 511880 真实收益  切换成本 单边 0.05%×2")
    print(real["rule"])
    _print_arms("A 股腿（判定账本）", real["arms"])
    doubled = real["doubled_cost"]
    _print_arms(f"成本加倍，判定账本（单边 0.10%，一轮 {doubled['round_trip_cost']:.3%}）", doubled["arms"])
    judge = real["criteria"]
    print(judge["label"])
    print(judge["verdict"])
    print("§4 三条："
          f"回撤 {judge['drawdown_shallower_by_10pp']}  "
          f"年化 {judge['cagr_giveup_at_most_2pp']}  "
          f"成本加倍 {judge['still_holds_at_doubled_cost']}  "
          f"同时成立 {judge['pass']}")
    b2 = real["b2_vs_b0"]
    print(f"§5 B2 全面劣于 B0：{b2['both_worse']}  {b2['label']}")
    cash = result["cash_assumption"]
    print(f"{cash['label']}  避风港 {cash['haven']}")
    _print_arms("A 股腿", cash["arms"])
    gate = result["d4_gate"]
    print(f"与 d4 印刷值的差（百分点，门槛 ±{gate['tolerance_pp']}，用上面的 2% 对照复现）")
    for name, row in gate["deltas_pp"].items():
        extra = ""
        if "switches_per_year" in row:
            extra = f"  切换/年 {row['switches_per_year']:+.2f}"
        print(f"  {name}  年化 {row['cagr_pp']:+.3f}  回撤 {row['max_drawdown_pp']:+.3f}{extra}")
    print("复现门槛：" + ("通过" if gate["within"] else "未通过"))
    print("511880 真实账本相对 2% 对照的差（百分点）")
    for name, row in real["vs_cash_assumption_pp"].items():
        print(f"  {name}  年化 {row['cagr_pp']:+.3f}  回撤 {row['max_drawdown_pp']:+.3f}")
    print(result["portfolio"]["description"])
    print(result["portfolio"]["qdii"])
    _print_portfolio("组合，511880 真实收益", result["portfolio"]["haven_511880"])
    _print_portfolio("组合，2% 现金假设（对照，不用于判定）", result["portfolio"]["cash_assumption"]["arms"])


def _refuse_oos(sha: str | None, lock: Path) -> str | None:
    if not sha_matches(sha):
        return f"预注册 SHA 与冻结提交 {FROZEN_SHA} 不符，拒绝样本外。"
    if Path(lock).exists():
        return f"样本外锁已存在：{lock}。拒绝再跑。"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.research.prereg_v2.run")
    parser.add_argument("--end", default=None)
    parser.add_argument("--oos", action="store_true")
    parser.add_argument("--prereg-sha", default=None)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--market-db", type=Path, default=DEFAULT_MARKET)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    args = parser.parse_args(argv)
    try:
        if args.oos:
            reason = _refuse_oos(args.prereg_sha, args.lock)
            if reason:
                print(reason)
                return 2
            if args.end is not None and pd.Timestamp(args.end).normalize() != OOS_END:
                print(f"样本外结束日只能是 {OOS_END.date()}。")
                return 2
            write_lock(args.lock, args.market_db)
            result = run_oos(args.panel, args.market_db, args.config)
            out = args.out or OOS_OUT
        else:
            end = pd.Timestamp(args.end).normalize() if args.end else DESIGN_END
            if end > DESIGN_END:
                print(f"设计期只允许 end ≤ {DESIGN_END.date()}。样本外需要 --oos 和预注册 SHA。")
                return 2
            result = run_design(args.panel, args.market_db, args.config, end)
            result["generated_at"] = datetime.now(SHANGHAI).isoformat(timespec="seconds")
            result["code_sha"] = git_head()
            result["market_sqlite_sha256"] = sha256_file(args.market_db)
            _print_design(result)
            out = args.out or DESIGN_OUT
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"写入 {out}")
        if result.get("window") == "design" and result["d4_gate"]["applies"] and not result["d4_gate"]["within"]:
            return 1
        return 0
    except (RunnerError, PanelError, OSError, ValueError) as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
