"""§3.1–§3.3：回撤面、两条腿、每天只减不加、第二层、单只替换。

卖出名单到下一个周度决策日的挑选为止，调仓完成后才清空。
周度决策日先做单只检查，再做周度挑选。同分按容器 id 升序。
硬闸门的触发边界复用 `src.v3.engine.exit.triggered`（等于 90% 不卖）。
持有期高点是这一次持有以来的最高收盘，从进入持仓后的第一个检查日算起；
名字还在手里时，周度留仓不重置高点（和画像 `profile33.py` 一致）。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.v3.engine.book import assert_window
from src.v3.engine.exit import triggered, valid_mark
from src.v3.engine.sessions import decision_dates

from .params import Params, V51Error
from .readings import level_index, read_panel
from .universe import Market, Universe


@dataclass(frozen=True)
class Allocation:
    """`state` 是每个交易日收盘后的目标。`decisions` 只含要成交的决策日。"""

    state: pd.DataFrame
    decisions: pd.DataFrame
    exits: pd.DataFrame


def breadth(frontier_share: pd.DataFrame, members: tuple[str, ...] | list[str], *,
            eligible: pd.DataFrame | None = None, minimum: int = 3,
            frontier: float = 0.5) -> pd.Series:
    """读数有定义的容器不足 `minimum` 个时没有宽度。"""
    index = frontier_share.index
    out = np.full(len(index), np.nan)
    for i, day in enumerate(index):
        count = 0
        hot = 0
        for name in members:
            if eligible is not None and not _flag_on(eligible, day, name):
                continue
            if name not in frontier_share.columns:
                continue
            value = frontier_share.at[day, name]
            if pd.isna(value):
                continue
            count += 1
            if float(value) >= frontier:
                hot += 1
        if count >= minimum:
            out[i] = hot / count
    return pd.Series(out, index=index, dtype=float)


def _flag_on(frame: pd.DataFrame, day, name: str) -> bool:
    if name not in frame.columns or day not in frame.index:
        return False
    value = frame.at[day, name]
    if pd.isna(value):
        return False
    return bool(value)


def _cell(frame: pd.DataFrame | None, day, name: str) -> float:
    if frame is None or name not in frame.columns or day not in frame.index:
        return float("nan")
    value = frame.at[day, name]
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return number


def _priced(returns: pd.DataFrame | None, day, name: str) -> bool:
    """没给收益表时，视作这条序列有价格。给了表，只有有限收益才算有价格。"""
    if returns is None:
        return True
    value = _cell(returns, day, name)
    return value == value and np.isfinite(value)


def _rank(names: list[str], day, level: pd.DataFrame) -> list[str]:
    rows = []
    for name in names:
        height = _cell(level, day, name)
        key = float("-inf") if pd.isna(height) else height
        rows.append((-key, name))
    rows.sort()
    return [name for _, name in rows]


def _weights(picks: list[str], risk: float, defense: str, cash: str) -> dict[str, float]:
    out: dict[str, float] = {}
    if picks and risk > 0.0:
        share = float(risk) / len(picks)
        for name in picks:
            out[name] = out.get(name, 0.0) + share
    rest = 1.0 - sum(out.values())
    if abs(rest) < 1e-15:
        rest = 0.0
    slot = cash if defense == cash else defense
    out[slot] = out.get(slot, 0.0) + rest
    out.setdefault(cash, 0.0)
    return out


def _weight_key(weights: dict[str, float], cash: str) -> tuple:
    return tuple(sorted((name, round(value, 10)) for name, value in weights.items() if abs(value) > 1e-15 or name == cash))


def allocate(index, level: pd.DataFrame, frontier_share: pd.DataFrame, easing: pd.DataFrame,
             universe: Universe, *, prices: pd.DataFrame | None = None,
             returns: pd.DataFrame | None = None, weekly: pd.DatetimeIndex | None = None,
             eligible: pd.DataFrame | None = None, params: Params | None = None,
             allow_after: bool = False) -> Allocation:
    """按交易日走到收盘。不算组合收益。"""
    frozen = Params() if params is None else params
    days = pd.DatetimeIndex(pd.to_datetime(index))
    if days.tz is not None:
        raise V51Error("交易日不带时区")
    days = pd.DatetimeIndex(days.normalize())
    if days.has_duplicates or not days.is_monotonic_increasing:
        raise V51Error("交易日要按时间唯一排好")
    assert_window(days, allow_after)
    if weekly is None:
        weekly = decision_dates(days, "week")
    week_set = {pd.Timestamp(day).normalize() for day in weekly}
    bands = {
        market.representative: breadth(
            frontier_share, market.members, eligible=eligible,
            minimum=frozen.breadth_min, frontier=frozen.frontier,
        )
        for market in universe.markets
    }

    def buyable(name: str, day) -> bool:
        if eligible is None:
            return True
        return _flag_on(eligible, day, name)

    def market_legs(market: Market, day) -> float | None:
        band = bands[market.representative]
        width = float(band.at[day]) if day in band.index else float("nan")
        return _legs(market.representative, day, width)

    def _legs(name: str, day, width: float) -> float | None:
        height = _cell(level, day, name)
        share = _cell(frontier_share, day, name)
        slow = _cell(easing, day, name)
        if pd.isna(height) or pd.isna(share) or pd.isna(slow):
            return None
        leg1 = (share < frozen.frontier) and not (pd.notna(width) and width >= frozen.frontier)
        leg2 = (height > 0.0) or bool(slow)
        return 0.5 * float(leg1) + 0.5 * float(leg2)

    def defense_of(day, current: str) -> str:
        bond = universe.bond
        gold = universe.gold
        bond_h = _cell(level, day, bond)
        gold_h = _cell(level, day, gold)
        if not _priced(returns, day, bond) and pd.isna(bond_h):
            return universe.cash
        bond_legs = _legs(bond, day, float("nan"))
        base = bond if (bond_legs is None or bond_legs > 0.0) else universe.cash
        bond_ref = bond_h if (base == bond and pd.notna(bond_h)) else 0.0
        if pd.notna(gold_h) and gold_h > 0.0 and gold_h - bond_ref > frozen.noise_band:
            return gold
        if (current == gold and pd.notna(gold_h) and gold_h > 0.0 and base == bond
                and pd.notna(bond_h) and gold_h >= bond_h):
            return gold
        return base

    def qualified(market: Market, day, blocked: set[str]) -> list[str]:
        found = []
        for name in market.members:
            if name in blocked or not buyable(name, day):
                continue
            height = _cell(level, day, name)
            share = _cell(frontier_share, day, name)
            if pd.isna(height) or pd.isna(share):
                continue
            if height > 0.0 and share < frozen.frontier:
                found.append(name)
        return _rank(found, day, level)

    def fallback(market: Market, day, blocked: set[str], *, check_frontier: bool) -> str | None:
        rep = market.representative
        if buyable(rep, day) and rep not in blocked and _hold_ok(rep, day, check_frontier):
            return rep
        if buyable(rep, day):
            return None
        pool = []
        for name in market.members:
            if name in blocked or not buyable(name, day):
                continue
            if check_frontier and not _hold_ok(name, day, True):
                continue
            pool.append(name)
        ranked = _rank(pool, day, level)
        return ranked[0] if ranked else None

    def _hold_ok(name: str, day, check_frontier: bool) -> bool:
        if not check_frontier:
            return True
        share = _cell(frontier_share, day, name)
        return pd.notna(share) and share < frozen.frontier

    def price_of(day, name: str) -> float:
        return _cell(prices, day, name)

    held: Market | None = None
    risk = 0.0
    defense = universe.cash
    picks: list[str] = []
    blocked: set[str] = set()
    peak: dict[str, float] = {}
    previous_count = 0
    previous_weights = {universe.cash: 1.0}
    state_rows = []
    exit_rows = []
    decision_rows = []
    decision_index = []

    for day in days:
        stamp = pd.Timestamp(day).normalize()
        sold_today: set[str] = set()
        for name in list(picks):
            px = price_of(stamp, name)
            if valid_mark(px):
                peak[name] = px if name not in peak else max(peak[name], px)
            why = None
            share = _cell(frontier_share, stamp, name)
            if pd.notna(share) and share >= frozen.frontier:
                why = "F"
            elif name in peak and valid_mark(px) and triggered(px, peak[name], frozen.hard_stop):
                why = "硬闸门"
            if why is None:
                continue
            picks.remove(name)
            blocked.add(name)
            sold_today.add(name)
            peak.pop(name, None)
            exit_rows.append((stamp, name, why))

        if stamp in week_set:
            scores = {market.representative: market_legs(market, stamp) for market in universe.markets}
            open_markets = [
                market for market in universe.markets
                if scores[market.representative] and any(buyable(name, stamp) for name in market.members)
            ]
            if held not in open_markets:
                held = _best(open_markets, stamp, level)
            else:
                challenger = _best(open_markets, stamp, level)
                if challenger is not None and challenger != held:
                    gap = _cell(level, stamp, challenger.representative) - _cell(level, stamp, held.representative)
                    if gap > frozen.noise_band:
                        held = challenger
            risk = float(scores[held.representative]) if held is not None else 0.0
            if held is None:
                new: list[str] = []
            else:
                ranked = qualified(held, stamp, blocked)
                chosen = ranked[:frozen.top_n]
                if not chosen:
                    stand = fallback(held, stamp, blocked, check_frontier=False)
                    chosen = [stand] if stand else []
                new = chosen
            for name in list(picks):
                if name not in new:
                    exit_rows.append((stamp, name, "周度换掉"))
                    peak.pop(name, None)
            picks = list(new)
            if not picks:
                held = None
                risk = 0.0
            blocked = set(sold_today)
            defense = defense_of(stamp, defense)
        elif held is not None:
            updated = market_legs(held, stamp)
            if updated is not None and updated < risk:
                risk = float(updated)
            if risk == 0.0:
                for name in list(picks):
                    exit_rows.append((stamp, name, "市场退出"))
                    peak.pop(name, None)
                held = None
                picks = []
            else:
                while len(picks) < frozen.top_n:
                    if len(picks) >= previous_count:
                        break
                    ranked = [name for name in qualified(held, stamp, blocked) if name not in picks]
                    if not ranked:
                        break
                    picks.append(ranked[0])
                if not picks:
                    stand = fallback(held, stamp, blocked, check_frontier=True)
                    if stand:
                        picks = [stand]
                    else:
                        held = None
                        risk = 0.0
            defense = defense_of(stamp, defense)

        previous_count = len(picks)
        weights = _weights(picks, risk if held is not None else 0.0, defense, universe.cash)
        if stamp in week_set or _weight_key(weights, universe.cash) != _weight_key(previous_weights, universe.cash):
            decision_rows.append(weights)
            decision_index.append(stamp)
        previous_weights = weights
        state_rows.append({
            "market": "" if held is None else held.representative,
            "market_name": "" if held is None else held.name,
            "risk": 0.0 if held is None else risk,
            "defense": defense,
            "picks": "|".join(picks),
            "blocked": "|".join(sorted(blocked)),
        })

    state = pd.DataFrame(state_rows, index=days)
    exits = pd.DataFrame(exit_rows, columns=["t", "id", "why"])
    decisions = _decision_frame(decision_rows, decision_index, universe.cash)
    return Allocation(state=state, decisions=decisions, exits=exits)


def _best(markets: list[Market], day, level: pd.DataFrame) -> Market | None:
    if not markets:
        return None
    return sorted(markets, key=lambda market: (-_cell(level, day, market.representative), market.representative))[0]


def _decision_frame(rows: list[dict[str, float]], index: list, cash: str) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=[cash])
    names: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for name in row:
            if name != cash and name not in seen:
                seen.add(name)
                names.append(name)
    names.append(cash)
    data = [[float(row.get(name, 0.0)) for name in names] for row in rows]
    return pd.DataFrame(data, index=pd.DatetimeIndex(index), columns=names)


def target_weights(returns: pd.DataFrame, universe: Universe, *,
                   eligible: pd.DataFrame | None = None, params: Params | None = None,
                   allow_after: bool = False) -> Allocation:
    """先算 §2 的读数，再走 §3。不成交。"""
    frozen = Params() if params is None else params
    panel = read_panel(returns, universe.cash, allow_after=allow_after, params=frozen)
    return allocate(
        panel.H.index, panel.H, panel.F, panel.E, universe,
        prices=level_index(returns), returns=returns, eligible=eligible,
        params=frozen, allow_after=allow_after,
    )
