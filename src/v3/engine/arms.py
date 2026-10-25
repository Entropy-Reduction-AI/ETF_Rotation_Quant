"""§4.3 合成与 §4.4 的 A、B、S1、S2。

v3.1 起，A / S1 / S2 不再把六组权重合成一条路径。各路独立持仓、独立离场，
臂的日收益是六路日收益的算术平均。账户层权重只作展示。
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .book import Book, RunnerError, to_execution
from .exit import EXIT_DRAWDOWN, simulate_path
from .score import Lookback, average_weights, lookback_panel, pick_row
from .sessions import decision_dates, next_session
from .spec import Spec


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


def _eligible(prepared: dict[int, Lookback], names: list[str], liquidity: pd.DataFrame | None) -> pd.DataFrame:
    ok = None
    for panel in prepared.values():
        flag = panel.ok[names]
        if liquidity is not None:
            flag = flag & liquidity[names].astype(bool)
        ok = flag if ok is None else (ok | flag)
    return ok if ok is not None else pd.DataFrame(False, index=next(iter(prepared.values())).ok.index, columns=names)


def _levels(market) -> pd.DataFrame:
    levels = getattr(market, "levels", None)
    if levels is not None:
        return levels.reindex(market.dates)
    from .market import levels_from_returns
    return levels_from_returns(market.pnl, market.cash_id)


def _static_premium(market, prepared, premium_spec):
    from src.v3.premium.rules import PremiumSpec
    from .premium_wire import panels_for, premium_ids_of
    if getattr(market, "premium_panels", None):
        panels = market.premium_panels
    elif premium_spec is not None and getattr(market, "premium_inputs", None):
        spec_obj = premium_spec if isinstance(premium_spec, PremiumSpec) else PremiumSpec()
        panels = panels_for(market, spec_obj)
    else:
        return None
    if not panels:
        return None
    return {
        "panels": panels,
        "ids": premium_ids_of(market) or set(panels),
        "eligible_on": _eligible(prepared, list(market.names), market.liquidity),
    }


class PremiumGate:
    """决策日取一张溢价上下文。同一年不换表，成交日不会再次进入。"""

    def __init__(self, *, static=None, choices=None, inputs=None, market=None, prepared=None):
        self.static = static
        self.choices = choices or {}
        self.inputs = inputs or {}
        self.market = market
        self.prepared = prepared
        self._cache = {}

    def on(self, day):
        if self.static is not None:
            return self.static
        choice = self.choices.get(int(pd.Timestamp(day).year))
        if choice is None:
            return None
        from src.v3.premium.rules import PremiumSpec
        from .premium_wire import frames_for, premium_ids_of
        key = (int(choice[0]), float(choice[1]))
        if key not in self._cache:
            self._cache[key] = frames_for(self.inputs, PremiumSpec(*key), self.market.dates)
        return {
            "panels": self._cache[key],
            "ids": premium_ids_of(self.market) or set(self.inputs),
            "eligible_on": _eligible(self.prepared, list(self.market.names), self.market.liquidity),
        }


def _schedule(market, spec: Spec, prepared, premium_spec):
    """显式 (W, θ) 或测试用的状态表直接用。否则在 A 臂上按 §7.1 逐年选择。"""
    static = _static_premium(market, prepared, premium_spec)
    if premium_spec is not None or getattr(market, "premium_panels", None):
        return PremiumGate(static=static) if static is not None else None
    inputs = getattr(market, "premium_inputs", None)
    if not inputs:
        return None
    from src.v3.eval.selection import premium_keys, walk_forward
    from src.v3.premium.rules import PremiumSpec
    series = {}
    for window, theta in premium_keys():
        chosen = PremiumSpec(window, theta)
        book = execute(
            market, spec, "A", allow_after=False, premium_spec=chosen,
            exit_drawdown=EXIT_DRAWDOWN, _selecting=True)
        series[(window, theta)] = book.net
    benchmark = market.benchmark if market.benchmark is not None else pd.Series(0.0, index=market.dates)
    picked = walk_forward(
        series, benchmark, train_start=spec.b_train_start, first_apply_year=spec.b_first_year,
        dates=market.dates, keys=list(premium_keys()))
    return PremiumGate(
        choices=picked["choices"], inputs=inputs, market=market, prepared=prepared)


def _run_path(market, spec: Spec, decisions: pd.DataFrame, *, allow_after: bool,
              exit_drawdown: float, premium) -> Book:
    use_premium = premium is not None
    book = simulate_path(
        market.pnl, _levels(market), market.fees, market.cash_id,
        targets=None if use_premium else to_execution(decisions, market.dates),
        decisions=decisions if use_premium else None,
        premium=premium,
        code_levels=getattr(market, "code_levels", None),
        code_returns=getattr(market, "code_returns", None),
        exit_drawdown=exit_drawdown,
        trade_eps=spec.trade_eps,
        cost_multiplier=market.cost_multiplier,
        allow_after=allow_after,
        weight_eps=spec.weight_eps,
    )
    book.decisions = decisions
    if not use_premium:
        book.targets = to_execution(decisions, market.dates)
    return book


def _average_paths(paths: dict[tuple[int, str], Book], frames: list[pd.DataFrame], cash_id: str,
                   dates: pd.DatetimeIndex) -> Book:
    if not paths:
        raise RunnerError("没有路径")
    ordered = list(paths.values())
    index = ordered[0].net.index
    for book in ordered[1:]:
        if not book.net.index.equals(index):
            raise RunnerError("六路没有对齐到同一交易日历")
    count = float(len(ordered))
    net = sum(book.net for book in ordered) / count
    gross = sum(book.gross for book in ordered) / count
    cost = sum(book.cost for book in ordered) / count
    buy = sum(book.buy for book in ordered) / count
    sell = sum(book.sell for book in ordered) / count
    held = sum(book.held for book in ordered) / count
    display = blend_decisions(frames, cash_id)
    exits = []
    codes = []
    for key, book in paths.items():
        label = f"{key[0]}-{key[1]}"
        if book.exits is not None and not book.exits.empty:
            frame = book.exits.copy()
            frame.insert(0, "path", label)
            exits.append(frame)
        if book.code_audit is not None and not book.code_audit.empty:
            frame = book.code_audit.copy()
            frame.insert(0, "path", label)
            codes.append(frame)
    return Book(
        net=net, gross=gross, held=held, decisions=display,
        targets=to_execution(display, dates),
        cost=cost, buy=buy, sell=sell,
        paths=paths,
        exits=pd.concat(exits, ignore_index=True) if exits else pd.DataFrame(),
        code_audit=pd.concat(codes, ignore_index=True) if codes else pd.DataFrame(),
    )


def _stitch_decisions(frames: dict[tuple[int, str], pd.DataFrame], choices: dict, dates: pd.DatetimeIndex,
                      cash_id: str) -> pd.DataFrame:
    """决策日并入其成交日所在的公历年，和原来按成交日拼接目标的方式一致。"""
    columns = None
    parts = []
    for year in sorted(choices):
        key = choices[year]
        if key is None or key not in frames:
            continue
        frame = frames[key]
        columns = list(frame.columns)
        keep = []
        for day in frame.index:
            nxt = next_session(dates, pd.Timestamp(day))
            if nxt is not None and int(nxt.year) == int(year):
                keep.append(day)
        if keep:
            parts.append(frame.loc[keep])
    if not parts:
        return pd.DataFrame(columns=columns or [cash_id])
    out = pd.concat(parts).sort_index()
    return out[~out.index.duplicated(keep="last")]


def execute(market, spec: Spec, arm: str, *, n: int | None = None, freq: str | None = None,
            allow_after: bool = False, exit_drawdown: float = EXIT_DRAWDOWN,
            premium_spec=None, _selecting: bool = False) -> Book:
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
    frames = {}
    for key in keys:
        frames[key] = group_decisions(
            prepared, market.dates, key[1], key[0], names, cash_id, market.sort_ids,
            market.liquidity, spec.lookbacks)
    premium = None if _selecting else _schedule(market, spec, prepared, premium_spec)

    def one(key) -> Book:
        return _run_path(
            market, spec, frames[key], allow_after=allow_after,
            exit_drawdown=exit_drawdown, premium=premium)

    if n is not None:
        return one((n, freq))
    if arm == "B":
        if market.benchmark is None:
            raise RunnerError("B 臂需要 BM-主 日收益")
        books = {key: one(key) for key in keys}
        _targets, choices = select_b(books, market.benchmark, spec, market.dates)
        if premium is None:
            book = _run_path(
                market, spec, _stitch_decisions(frames, choices, market.dates, cash_id),
                allow_after=allow_after, exit_drawdown=exit_drawdown, premium=None)
            book.targets = _targets
        else:
            book = _run_path(
                market, spec, _stitch_decisions(frames, choices, market.dates, cash_id),
                allow_after=allow_after, exit_drawdown=exit_drawdown, premium=premium)
        book.choices = choices
        book.paths = books
        return book
    paths = {key: one(key) for key in keys}
    return _average_paths(paths, [frames[key] for key in keys], cash_id, market.dates)
