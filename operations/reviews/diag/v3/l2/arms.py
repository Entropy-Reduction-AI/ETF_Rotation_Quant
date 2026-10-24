"""§4.3 合成与 §4.4 的 A、B、S1、S2。S1/S2 的差别在标的和信号，合成与 A 相同。"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from operations.reviews.diag.v3.l2.book import Book, RunnerError, simulate, to_execution
from operations.reviews.diag.v3.l2.score import Lookback, average_weights, lookback_panel, pick_row
from operations.reviews.diag.v3.l2.sessions import decision_dates
from operations.reviews.diag.v3.l2.spec_loader import Spec


def _columns(names: list[str], cash_id: str) -> list[str]:
    return [*names, cash_id]


def group_decisions(prepared: dict[int, Lookback], dates: pd.DatetimeIndex, freq: str, n: int,
                    names: list[str], cash_id: str, sort_ids: dict[str, str],
                    liquidity: pd.DataFrame | None, lookbacks: tuple[int, ...]) -> pd.DataFrame:
    columns = _columns(names, cash_id)
    days = decision_dates(dates, freq)
    rows = []
    for day in days:
        parts = [
            pick_row(prepared[length], day, n, names, cash_id, sort_ids, liquidity)
            for length in lookbacks
        ]
        averaged = average_weights(parts, names, cash_id)
        rows.append([averaged.get(name, 0.0) for name in columns])
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, index=pd.DatetimeIndex(days), columns=columns)


def blend_decisions(frames: list[pd.DataFrame], cash_id: str) -> pd.DataFrame:
    """六组目标的算术平均。还没有决策的组视为全现金，始终除以组数。"""
    columns = list(frames[0].columns)
    cash = np.zeros(len(columns))
    cash[columns.index(cash_id)] = 1.0
    latest: list[np.ndarray | None] = [None] * len(frames)
    days = sorted(set().union(*[set(frame.index) for frame in frames]))
    rows = []
    lookups = [{pd.Timestamp(day): i for i, day in enumerate(frame.index)} for frame in frames]
    arrays = [frame.to_numpy(dtype=float) for frame in frames]
    for day in days:
        acc = np.zeros(len(columns))
        for i, found in enumerate(lookups):
            pos = found.get(pd.Timestamp(day))
            if pos is not None:
                latest[i] = arrays[i][pos]
            acc += cash if latest[i] is None else latest[i]
        rows.append(acc / len(frames))
    return pd.DataFrame(rows, index=pd.DatetimeIndex(days), columns=columns)


def daily_ir(strategy: pd.Series, benchmark: pd.Series) -> float:
    """§7.1：IR = mean(excess) / std(excess) × √252，标准差 ddof=1。"""
    both = pd.concat([
        pd.Series(strategy, dtype=float).rename("strategy"),
        pd.Series(benchmark, dtype=float).rename("benchmark"),
    ], axis=1).dropna()
    if len(both) < 2:
        return -math.inf
    excess = both["strategy"] - both["benchmark"]
    scale = float(excess.std(ddof=1))
    if not math.isfinite(scale) or scale == 0.0:
        return -math.inf
    return float(excess.mean() / scale * math.sqrt(252))


def select_b(books: dict[tuple[int, str], Book], benchmark: pd.Series, spec: Spec,
             dates: pd.DatetimeIndex) -> tuple[pd.DataFrame, dict[int, tuple[int, str] | None]]:
    """每年初用此前全部数据选 IR 最高的一组，用到下一年初。2011 年前没有选择，保持现金。"""
    columns = list(next(iter(books.values())).targets.columns)
    start_year = int(pd.Timestamp(dates.min()).year)
    end_year = int(pd.Timestamp(dates.max()).year)
    train_start = pd.Timestamp(spec.b_train_start)
    choices: dict[int, tuple[int, str] | None] = {}
    parts = []
    for year in range(start_year, end_year + 1):
        if year < spec.b_first_year:
            choices[year] = None
            continue
        train_end = pd.Timestamp(year=year - 1, month=12, day=31)
        best_key = None
        best_ir = -math.inf
        for key in spec.candidates():
            window = books[key].net
            window = window[(window.index >= train_start) & (window.index <= train_end)]
            score = daily_ir(window, benchmark)
            if score > best_ir:
                best_ir = score
                best_key = key
        if best_key is None or best_ir == -math.inf:
            choices[year] = None
            continue
        choices[year] = best_key
        targets = books[best_key].targets
        part = targets[targets.index.year == year]
        if len(part):
            parts.append(part)
    if not parts:
        return pd.DataFrame(columns=columns), choices
    out = pd.concat(parts).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out, choices


def execute(market, spec: Spec, arm: str, *, n: int | None = None, freq: str | None = None,
            allow_after: bool = False) -> Book:
    """在已经准备好的行情上跑一条臂。行情的日期不得晚于调用方允许的结束日。"""
    if arm not in {"A", "B", "S1", "S2"}:
        raise RunnerError(f"未知的臂 {arm}")
    if (n is None) != (freq is None):
        raise RunnerError("子组合要同时给出 N 和频率")
    if n is not None and (n not in spec.ns or freq not in spec.frequencies):
        raise RunnerError(f"子组合不在候选集里：N={n} {freq}")
    names = list(market.names)
    cash_id = market.cash_id
    prepared = {length: lookback_panel(market.signal, cash_id, length) for length in spec.lookbacks}
    keys = ((n, freq),) if n is not None else spec.candidates()
    frames = []
    books: dict[tuple[int, str], Book] = {}
    for key in keys:
        decisions = group_decisions(
            prepared, market.dates, key[1], key[0], names, cash_id, market.sort_ids,
            market.liquidity, spec.lookbacks)
        targets = to_execution(decisions, market.dates)
        if arm == "B" or n is not None:
            book = simulate(
                market.pnl, targets, market.fees, cash_id, trade_eps=spec.trade_eps,
                cost_multiplier=market.cost_multiplier, allow_after=allow_after)
            book.decisions = decisions
            books[key] = book
        frames.append(decisions)
    if n is not None:
        return books[(n, freq)]
    if arm == "B":
        if market.benchmark is None:
            raise RunnerError("B 臂需要 BM-主 日收益")
        targets, choices = select_b(books, market.benchmark, spec, market.dates)
        book = simulate(
            market.pnl, targets, market.fees, cash_id, trade_eps=spec.trade_eps,
            cost_multiplier=market.cost_multiplier, allow_after=allow_after)
        book.choices = choices
        book.targets = targets
        return book
    blended = blend_decisions(frames, cash_id)
    targets = to_execution(blended, market.dates)
    book = simulate(
        market.pnl, targets, market.fees, cash_id, trade_eps=spec.trade_eps,
        cost_multiplier=market.cost_multiplier, allow_after=allow_after)
    book.decisions = blended
    book.targets = targets
    return book
