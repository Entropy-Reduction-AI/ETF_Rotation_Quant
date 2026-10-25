"""§7.2 稳健性。七种情形都重算，只报告 ①，不改判。

成本加倍会重跑整条臂，因为 B 臂的选择用到扣成本后的收益。
决策日延后 1 天：原决策的权重不变，成交再晚一个交易日。
去掉美股主题、去掉商品、去掉最好的 1/2/3 只，都是改池子后重跑。
「最好」按评价窗里该容器自己的累计收益排序，高的在前，累计相同则名字较小的在前。
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.v3.engine.arms import execute
from src.v3.engine.book import simulate
from src.v3.engine.market import market_from_returns
from src.v3.engine.sessions import next_session

from .common import EvalError, compound_return, require_design_period
from .windows import criterion_1

CASES = (
    "base",
    "cost_double",
    "delay_1d",
    "drop_us_theme",
    "drop_commodity",
    "drop_best_1",
    "drop_best_2",
    "drop_best_3",
)
US_THEME = "美股和全球主题"
COMMODITY = "商品"


def best_containers(pnl: pd.DataFrame, names: list[str], k: int) -> list[str]:
    require_design_period(pnl.index)
    scored = []
    for name in names:
        values = pnl[name].to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        if len(finite) == 0 or np.any(finite <= -1.0):
            total = -math.inf
        else:
            total = compound_return(finite)
        scored.append((total, name))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [name for _, name in scored[:k]]


def delay_targets(targets: pd.DataFrame, dates) -> pd.DataFrame:
    """每个成交日改到下一个交易日。没有下一日，或下一日晚于设计期，就丢掉这一笔。"""
    require_design_period(dates)
    require_design_period(targets.index)
    sessions = pd.DatetimeIndex(pd.to_datetime(dates)).sort_values()
    rows = []
    index = []
    for day, row in targets.sort_index().iterrows():
        nxt = next_session(sessions, pd.Timestamp(day))
        if nxt is None:
            continue
        require_design_period([nxt])
        rows.append(row.to_numpy(dtype=float))
        index.append(pd.Timestamp(nxt))
    if not rows:
        return pd.DataFrame(columns=targets.columns)
    frame = pd.DataFrame(rows, index=pd.DatetimeIndex(index), columns=targets.columns)
    return frame[~frame.index.duplicated(keep="last")].sort_index()


def _subset(market, keep: list[str], cost_multiplier: float | None = None):
    columns = [*keep, market.cash_id]
    liquidity = None if market.liquidity is None else market.liquidity.loc[:, columns]
    return market_from_returns(
        market.signal.loc[:, columns],
        {name: market.fees[name] for name in columns},
        pnl=market.pnl.loc[:, columns],
        cash_id=market.cash_id,
        sort_ids={name: market.sort_ids[name] for name in keep},
        liquidity=liquidity,
        benchmark=market.benchmark,
        cost_multiplier=market.cost_multiplier if cost_multiplier is None else cost_multiplier,
    )


def _without(market, drop: list[str]):
    banned = set(drop)
    keep = [name for name in market.names if name not in banned]
    return _subset(market, keep)


def robustness_books(market, spec, arm: str, classes: dict[str, str]) -> dict:
    """八条账：原来的，加上 §7.2 的七种情形。不写尝试记录。"""
    require_design_period(market.dates)
    if market.benchmark is not None:
        require_design_period(pd.Series(market.benchmark).dropna().index)
    base = execute(market, spec, arm, allow_after=False)
    books = {"base": base}
    books["cost_double"] = execute(_subset(market, list(market.names), 2.0), spec, arm, allow_after=False)
    delayed = delay_targets(base.targets, market.dates)
    books["delay_1d"] = simulate(
        market.pnl, delayed, market.fees, market.cash_id,
        trade_eps=spec.trade_eps, cost_multiplier=market.cost_multiplier, allow_after=False)
    us = [name for name in market.names if classes.get(name) == US_THEME]
    commodity = [name for name in market.names if classes.get(name) == COMMODITY]
    books["drop_us_theme"] = execute(_without(market, us), spec, arm, allow_after=False)
    books["drop_commodity"] = execute(_without(market, commodity), spec, arm, allow_after=False)
    ranked = best_containers(market.pnl, list(market.names), 3)
    for k in (1, 2, 3):
        books[f"drop_best_{k}"] = execute(_without(market, ranked[:k]), spec, arm, allow_after=False)
    missing = [name for name in CASES if name not in books]
    if missing:
        raise EvalError(f"稳健性缺了 {missing[0]}")
    return books


def robustness_table(books: dict, benchmark, calendar) -> dict:
    """每种情形只放 ① 的中位数和占比。没有通过与否。"""
    rows = []
    for name in CASES:
        if name not in books:
            raise EvalError(f"稳健性缺了 {name}")
        report = criterion_1(books[name].net, benchmark, calendar)
        rows.append({
            "case": name,
            "n_36": report["n_36"],
            "n_60": report["n_60"],
            "median_36": report["median_36"],
            "median_60": report["median_60"],
            "fraction_positive_60": report["fraction_positive_60"],
        })
    return {"cases": rows}
