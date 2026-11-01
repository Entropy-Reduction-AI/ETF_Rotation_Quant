"""v5 的周、月两路成交。

目标权重用 `path_decisions`。成交走 v4 B0 的 `_run_path`：同一组
`fill_limits` / `fill_quotes`、`premium`、`code_levels` / `code_returns`、
`cross_border`、`dividend_yield`、`trade_eps`、`weight_eps`、`cost_multiplier`。
不走 v3 的六路。延后 1 天沿用 `src/v4/r5/design.py` 的 `_execute`。
不补位。行情须已经按 B0 装好（汇率、载体、成交报价）。
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

import pandas as pd

from src.v3.engine.arms import _run_path, _schedule
from src.v3.engine.costs import names_for
from src.v3.engine.limits import quotes_from_market
from src.v3.engine.score import lookback_panel
from src.v3.engine.switches import EngineSwitches

from .allocate import STRUCTURE_S0, EngineError, path_decisions
from .paths import PATHS, arm_return, delay_book, resolve_exit


def b0_switches(*, allow_substitute: bool = True) -> EngineSwitches:
    """与 v4 B0 的 `Job.switches()` 相同。T1–T4 关着。"""
    return EngineSwitches(
        fill_limits=True,
        fx_v4=True,
        carriers=True,
        allow_substitute=allow_substitute,
    )


@dataclass
class ArmRun:
    net: pd.Series
    paths: dict


def run_arm(market, spec, class_of: dict[str, str], *, enable_c2: bool, enable_c1: bool = False,
            structure: str = STRUCTURE_S0, switches: EngineSwitches | None = None,
            decision_delay: int = 0, exit_drawdown: float | None = None,
            cost_multiplier: float = 1.0, lookbacks: tuple[int, ...] | None = None) -> ArmRun:
    """S0、P1、P2、稳健性和结构对照都从这里进。只跑周、月两路。"""
    if decision_delay not in {0, 1}:
        raise EngineError("决策日只延后 0 天或 1 天")
    running = copy.copy(market)
    running.cost_multiplier = float(cost_multiplier)
    chosen = switches if switches is not None else b0_switches()
    lengths = tuple(int(item) for item in (spec.lookbacks if lookbacks is None else lookbacks))
    panels = {
        length: lookback_panel(running.signal, running.cash_id, length) for length in lengths
    }
    premium = _schedule(running, spec, panels, None)
    quotes = quotes_from_market(running) if chosen.fill_limits else None
    border = None
    dividend = None
    if chosen.cross_border is not None:
        border = names_for(getattr(running, "asset_classes", None))
        dividend = getattr(running, "dividend_yield", None)
    drawdown = resolve_exit(enable_c2, exit_drawdown)
    names = [*list(running.names), running.cash_id]
    c1 = running.signal if enable_c1 else None
    books = {}
    for freq in PATHS:
        decisions = path_decisions(
            panels, running.dates, freq, names, class_of, running.cash_id,
            liquidity=running.liquidity, structure=structure, returns=c1, lookbacks=lengths,
        )
        books[freq] = _run_path(
            running, spec, decisions, allow_after=False, exit_drawdown=drawdown, premium=premium,
            switches=chosen, fill_quotes=quotes, refill_targets=None,
            cross_border_names=border, dividend_yield=dividend,
        )
    if decision_delay == 1:
        books = {
            freq: delay_book(running, spec, book, drawdown, chosen, quotes)
            for freq, book in books.items()
        }
    return ArmRun(net=arm_return(books["week"].net, books["month"].net), paths=books)
