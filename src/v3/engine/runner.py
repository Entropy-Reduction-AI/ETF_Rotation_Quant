"""运行器。默认结束日不晚于 2015-12-31。全期要冻结 SHA，且 LOCK 已存在时拒绝。"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from src.data import db as DB
from src.v3.data.universe import containers as load_containers

from .arms import execute
from .book import DESIGN_END, RunnerError
from .ledger import append_ledger
from .market import load_market
from .spec import LEDGER, LOCK, Spec, load_spec, sha_matches

__all__ = ["RunnerError", "execute", "resolve_end", "run"]


def resolve_end(end, spec: Spec, *, full_period: bool = False, freeze_sha: str | None = None,
                lock_path: Path = LOCK, debug: bool = False) -> pd.Timestamp:
    design = pd.Timestamp(spec.design_end)
    chosen = design if end is None else pd.Timestamp(end)
    if chosen <= design:
        return chosen
    if debug:
        raise RunnerError("debug 只允许结束日不晚于 2015-12-31")
    if Path(lock_path).exists():
        raise RunnerError("已有 results/v3/LOCK，拒绝再跑 2016 年及之后")
    if not full_period:
        raise RunnerError("默认只允许结束日不晚于 2015-12-31；全期要显式打开并带冻结 SHA")
    if not sha_matches(freeze_sha, spec.freeze_sha):
        raise RunnerError("全期运行必须带预注册冻结 SHA")
    return chosen


def run(arm: str, pool: str, end=None, *, full_period: bool = False, freeze_sha: str | None = None,
        debug: bool = False, cost_multiplier: float = 1.0, n: int | None = None, freq: str | None = None,
        ledger_path: Path | None = None, lock_path: Path = LOCK, db_path: Path = DB.MARKET_DB,
        spec: Spec | None = None, market=None, runner: str | None = None):
    """先检查结束日，再读不超过该日的行情。debug 不写尝试记录。本函数不创建 LOCK。"""
    spec = load_spec() if spec is None else spec
    if pool not in {"index", "tradable"}:
        raise RunnerError(f"未知的池 {pool}")
    chosen = resolve_end(end, spec, full_period=full_period, freeze_sha=freeze_sha,
                         lock_path=lock_path, debug=debug)
    allow_after = chosen > DESIGN_END
    if market is None:
        market = load_market(db_path, load_containers(), arm, pool, chosen, spec,
                             cost_multiplier=cost_multiplier, allow_after=allow_after)
    else:
        market.cost_multiplier = cost_multiplier
    if len(market.dates) and pd.Timestamp(market.dates.max()) > chosen:
        raise RunnerError("行情越过结束日，拒绝计算")
    book = execute(market, spec, arm, n=n, freq=freq, allow_after=allow_after)
    if len(book.net) and pd.Timestamp(book.net.index.max()) > chosen:
        raise RunnerError("组合收益越过结束日")
    if not debug:
        payload = {
            "pool": pool,
            "end": str(chosen.date()),
            "cost_multiplier": cost_multiplier,
        }
        if n is not None:
            payload["n"] = n
            payload["freq"] = freq
        label = "group" if n is not None else arm
        segment = "full" if allow_after else "design"
        append_ledger(
            LEDGER if ledger_path is None else Path(ledger_path),
            arm=label,
            params=payload,
            segment=segment,
            runner=runner or os.environ.get("ETF_V3_RUNNER") or "dev",
        )
    return book
