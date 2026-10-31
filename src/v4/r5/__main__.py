"""python -m src.v4.r5 all

只跑设计期。没有全期开关，不写 results/v4/LOCK。
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import pandas as pd

from src.v3.engine.book import RunnerError
from src.v4.scorecard.core import ScorecardError
from src.v3.engine.spec import load_spec
from src.v4.r5.design import (
    DESIGN_END,
    OUT,
    budget_jobs,
    final_jobs,
    ledger_rows,
    load_gate_table,
    month_states,
    passed_from_table,
    read_net,
    require_frozen_db,
    robustness_jobs,
    run_job,
    single_jobs,
    benchmark_returns,
    write_gate,
    Markets,
)
from src.v4.r5.peers import run_peers
from src.v4.scorecard.gate import RUN_ORDER


def _print_net(case: str, pool: str, net, started: float) -> None:
    print(
        f"{case} {pool} {net.index[0].date()}→{net.index[-1].date()} "
        f"n={len(net)} {time.perf_counter() - started:.1f}s",
        flush=True,
    )


def _pool_jobs(jobs, pool: str | None):
    if not pool:
        return list(jobs)
    return [job for job in jobs if job.pool == pool]


def step2(markets: Markets, *, resume: bool, pool: str | None = None) -> None:
    for job in _pool_jobs(single_jobs(), pool):
        started = time.perf_counter()
        net = run_job(job, markets, resume=resume)
        _print_net(job.case, job.pool, net, started)


def step3() -> list[str]:
    columns = {}
    for name in RUN_ORDER:
        columns[name] = read_net(name, "index")
    returns = pd.DataFrame(columns)
    benchmark = benchmark_returns()
    states = month_states()
    table = write_gate(returns, benchmark, states)
    passed = passed_from_table(table)
    print(table.to_string(index=False), flush=True)
    print(f"过关: {passed or '无'}", flush=True)
    return passed


def step4(markets: Markets, passed: list[str], *, resume: bool, pool: str | None = None) -> None:
    finals = _pool_jobs(final_jobs(passed), pool)
    expected = len(budget_jobs(passed)) + 4
    if expected > 60:
        raise RunnerError(f"ledger 预计 {expected} 行，超过 60")
    for job in finals:
        started = time.perf_counter()
        net = run_job(job, markets, resume=resume)
        _print_net(job.case, job.pool, net, started)
    print("公开同行", flush=True)
    peer_pools = (pool,) if pool else ("index", "tradable")
    run_peers(markets.spec, resume=resume, pools=peer_pools)
    anchor = final_jobs(passed)[0]
    for job in _pool_jobs(robustness_jobs(anchor), pool):
        started = time.perf_counter()
        net = run_job(job, markets, resume=resume)
        _print_net(job.case, job.pool, net, started)
    rows = ledger_rows()
    if len(rows) > 60:
        raise RunnerError(f"ledger 已有 {len(rows)} 行，超过预算 60")
    manifest = {
        "end": DESIGN_END,
        "passed": passed,
        "ledger_rows": len(rows),
        "db_sha256": require_frozen_db(),
        "gate": str(OUT / "candidate-gate.csv"),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ledger {len(rows)} 行", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v4-R5 设计期运行")
    parser.add_argument("step", choices=["step2", "step3", "step4", "all"])
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--pool", choices=["index", "tradable"], default=None)
    args = parser.parse_args(argv)
    try:
        digest = require_frozen_db()
        print(f"db {digest[:12]} end={DESIGN_END}", flush=True)
        markets = Markets(load_spec())
        resume = not args.no_resume
        pool = args.pool
        if args.step == "step2":
            step2(markets, resume=resume, pool=pool)
        elif args.step == "step3":
            step3()
        elif args.step == "step4":
            step4(markets, passed_from_table(load_gate_table()), resume=resume, pool=pool)
        else:
            step2(markets, resume=resume, pool=pool)
            if pool == "tradable":
                passed = passed_from_table(load_gate_table())
                print("U-指数未重跑，过关表不重写", flush=True)
            else:
                passed = step3()
            step4(markets, passed, resume=resume, pool=pool)
        require_frozen_db()
    except (RunnerError, ScorecardError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
