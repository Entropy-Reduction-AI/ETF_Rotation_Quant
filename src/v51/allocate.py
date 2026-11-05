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

# 诊断开关。默认 frozen 就是冻结规则（V0）。其余四个不改周度选市场。
CADENCES = ("frozen", "weekly", "resonance", "daily", "resonance_daily")


@dataclass(frozen=True)
class Allocation:
    """`state` 是每个交易日收盘后的目标。`decisions` 只含要成交的决策日。

    `legs` 是每个市场两条腿的逐日读数，给诊断拆尺子。冻结路径也记，不参与配权。
    """

    state: pd.DataFrame
    decisions: pd.DataFrame
    exits: pd.DataFrame
    legs: pd.DataFrame | None = None


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


def leg_flags(name: str, day, level: pd.DataFrame, frontier_share: pd.DataFrame,
             easing: pd.DataFrame, width: float, frontier: float) -> tuple[bool, bool] | None:
    """两条腿各自通不通。读数缺了就是没有腿。"""
    height = _cell(level, day, name)
    share = _cell(frontier_share, day, name)
    slow = _cell(easing, day, name)
    if pd.isna(height) or pd.isna(share) or pd.isna(slow):
        return None
    leg1 = (share < frontier) and not (pd.notna(width) and width >= frontier)
    leg2 = (height > 0.0) or bool(slow)
    return bool(leg1), bool(leg2)


def leg_score(name: str, day, level: pd.DataFrame, frontier_share: pd.DataFrame,
             easing: pd.DataFrame, width: float, frontier: float) -> float | None:
    """一个代表在这一天的风险仓位。读数缺了就是没有这条腿。"""
    flags = leg_flags(name, day, level, frontier_share, easing, width, frontier)
    if flags is None:
        return None
    return 0.5 * float(flags[0]) + 0.5 * float(flags[1])


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
             allow_after: bool = False, mode: str = "legs",
             strength: pd.DataFrame | None = None, noise: pd.DataFrame | None = None,
             selection: str = "market", daily_look: bool = True,
             cadence: str = "frozen") -> Allocation:
    """按交易日走到收盘。不算组合收益。

    `selection="all"` 只给 §7.1 S12：不先锁定一个市场，三个市场里够格的 ETF 按 H 一起取前 3。
    `daily_look=False` 只给 S13：减仓、单只离场和换防守都只在周度决策日做。
    `cadence="frozen"` 是冻结规则。其余值只给 D37 诊断，并且只改非周度日的档位。
    默认参数走冻结规则。
    """
    frozen = Params() if params is None else params
    if selection not in {"market", "all"}:
        raise V51Error(f"没有这种挑选：{selection}")
    if selection == "all" and mode != "legs":
        raise V51Error("全部一起排只用于两条腿")
    if not daily_look and mode != "legs":
        raise V51Error("只在周度决策日减仓只用于两条腿")
    if cadence not in CADENCES:
        raise V51Error(f"没有这种节奏：{cadence}")
    if cadence != "frozen" and (mode != "legs" or selection != "market" or not daily_look):
        raise V51Error("诊断节奏只打开在两条腿、按市场挑选、每天看的默认路径上")
    days = pd.DatetimeIndex(pd.to_datetime(index))
    if days.tz is not None:
        raise V51Error("交易日不带时区")
    days = pd.DatetimeIndex(days.normalize())
    if days.has_duplicates or not days.is_monotonic_increasing:
        raise V51Error("交易日要按时间唯一排好")
    assert_window(days, allow_after)
    if mode not in {"legs", "vol_ratio"}:
        raise V51Error(f"没有这种持仓模式：{mode}")
    if mode == "vol_ratio" and (strength is None or noise is None):
        raise V51Error("波动比对照要带强度和噪音")
    if weekly is None:
        weekly = decision_dates(days, "week")
    week_set = {pd.Timestamp(day).normalize() for day in weekly}
    by_rep = {market.representative: market for market in universe.markets}
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
        return leg_score(name, day, level, frontier_share, easing, width, frozen.frontier)

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
    name_market = {name: market for market in universe.markets for name in market.members}
    state_rows = []
    exit_rows = []
    decision_rows = []
    decision_index = []
    leg_rows = []
    week_picks: list[str] = []
    left_market: Market | None = None

    def _abandon(market: Market) -> None:
        nonlocal held, risk, picks, left_market
        for name in list(picks):
            exit_rows.append((stamp, name, "市场退出"))
            peak.pop(name, None)
        left_market = market
        held = None
        risk = 0.0
        picks = []

    def _refill(market: Market) -> None:
        nonlocal held, risk, picks, left_market
        while len(picks) < frozen.top_n:
            if len(picks) >= previous_count:
                break
            ranked = [name for name in qualified(held, stamp, blocked) if name not in picks]
            if not ranked:
                break
            picks.append(ranked[0])
        if picks:
            return
        stand = fallback(held, stamp, blocked, check_frontier=True)
        if stand:
            picks = [stand]
            return
        left_market = market
        held = None
        risk = 0.0

    def _reenter(market: Market, new_risk: float) -> None:
        nonlocal held, risk, picks, left_market
        if new_risk <= 0.0:
            return
        held = market
        risk = min(1.0, float(new_risk))
        allowed = set(qualified(market, stamp, blocked))
        restored = [name for name in week_picks if name in allowed]
        if not restored:
            stand = fallback(market, stamp, blocked, check_frontier=True)
            restored = [stand] if stand else []
        picks = restored[:frozen.top_n]
        if not picks:
            left_market = market
            held = None
            risk = 0.0
            return
        left_market = None

    def _step_cadence() -> None:
        """非周度日。单只离场已经在上面做过。这里只改档位和整体离场后的买回。"""
        nonlocal held, risk, defense, left_market
        adds = cadence in {"daily", "resonance_daily"}
        market = held if held is not None else (left_market if adds else None)
        if market is None:
            return
        updated = market_legs(market, stamp)
        if cadence == "weekly":
            if held is None:
                return
            if risk == 0.0:
                _abandon(market)
            else:
                _refill(market)
        elif cadence == "resonance":
            if held is None:
                return
            if updated is not None and updated <= 0.0:
                _abandon(market)
            elif risk <= 0.0:
                _abandon(market)
            else:
                _refill(market)
        elif cadence == "daily":
            if updated is None:
                if held is not None and risk > 0.0:
                    _refill(market)
                elif held is not None:
                    _abandon(market)
            elif updated <= 0.0:
                if held is not None:
                    _abandon(market)
            elif held is None:
                _reenter(market, float(updated))
            else:
                risk = float(updated)
                if risk <= 0.0:
                    _abandon(market)
                else:
                    _refill(market)
        elif cadence == "resonance_daily":
            if updated is None:
                if held is not None and risk > 0.0:
                    _refill(market)
                elif held is not None:
                    _abandon(market)
            elif updated <= 0.0:
                if held is not None:
                    _abandon(market)
            elif held is None:
                _reenter(market, float(updated))
            else:
                if float(updated) > risk:
                    risk = min(1.0, float(updated))
                if risk <= 0.0:
                    _abandon(market)
                else:
                    _refill(market)
        else:
            raise V51Error(f"没有这种节奏：{cadence}")
        defense = defense_of(stamp, defense)

    for day in days:
        stamp = pd.Timestamp(day).normalize()
        sold_today: set[str] = set()
        if daily_look or stamp in week_set:
            for name in list(picks):
                px = price_of(stamp, name)
                if valid_mark(px):
                    peak[name] = px if name not in peak else max(peak[name], px)
                why = None
                share = _cell(frontier_share, stamp, name)
                if pd.notna(share) and share >= frozen.frontier:
                    why = "F"
                elif (frozen.hard_stop is not None and name in peak and valid_mark(px)
                      and triggered(px, peak[name], frozen.hard_stop)):
                    why = "硬闸门"
                if why is None:
                    continue
                picks.remove(name)
                blocked.add(name)
                sold_today.add(name)
                peak.pop(name, None)
                exit_rows.append((stamp, name, why))

        if stamp in week_set:
            if mode == "vol_ratio":
                held_id, defense = select_vol_market(
                    None if held is None else held.representative, defense, stamp,
                    universe.markets, universe.bond, universe.gold, universe.cash,
                    strength, noise, frozen.noise_band,
                )
                held = None if held_id is None else by_rep[held_id]
                risk = 1.0 if held is not None else 0.0
            else:
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
                defense = defense_of(stamp, defense)
            if selection == "all" and mode != "vol_ratio":
                scores = {market.representative: market_legs(market, stamp) for market in universe.markets}
                open_markets = [
                    market for market in universe.markets
                    if scores[market.representative] and any(buyable(name, stamp) for name in market.members)
                ]
                pool: list[str] = []
                for market in open_markets:
                    pool.extend(qualified(market, stamp, blocked))
                chosen = _rank(list(dict.fromkeys(pool)), stamp, level)[:frozen.top_n]
                if not chosen and open_markets:
                    best = _best(open_markets, stamp, level)
                    stand = fallback(best, stamp, blocked, check_frontier=False) if best is not None else None
                    chosen = [stand] if stand else []
                new = chosen
                parts = [float(scores[name_market[name].representative] or 0.0) for name in new]
                held = None if not new else name_market[new[0]]
                risk = 0.0 if not parts else float(sum(parts) / len(parts))
            elif held is None:
                new = []
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
            week_picks = list(picks)
            left_market = None
        elif selection == "all" and held is not None and daily_look:
            kept: list[str] = []
            for name in list(picks):
                updated = market_legs(name_market[name], stamp)
                if updated == 0.0:
                    exit_rows.append((stamp, name, "市场退出"))
                    peak.pop(name, None)
                    continue
                kept.append(name)
            picks = kept
            if picks:
                parts = []
                for name in picks:
                    updated = market_legs(name_market[name], stamp)
                    if updated is not None:
                        parts.append(float(updated))
                if parts:
                    proposed = float(sum(parts) / len(parts))
                    if proposed < risk:
                        risk = proposed
                while len(picks) < frozen.top_n and len(picks) < previous_count:
                    pool = []
                    for market in universe.markets:
                        score = market_legs(market, stamp)
                        if not score or not any(buyable(name, stamp) for name in market.members):
                            continue
                        pool.extend(name for name in qualified(market, stamp, blocked) if name not in picks)
                    ranked = [name for name in _rank(list(dict.fromkeys(pool)), stamp, level) if name not in picks]
                    if not ranked:
                        break
                    picks.append(ranked[0])
            if not picks:
                open_markets = [
                    market for market in universe.markets
                    if market_legs(market, stamp) and any(buyable(name, stamp) for name in market.members)
                ]
                best = _best(open_markets, stamp, level)
                stand = fallback(best, stamp, blocked, check_frontier=True) if best is not None else None
                if stand:
                    picks = [stand]
                    held = name_market[stand]
                else:
                    held = None
                    risk = 0.0
            else:
                held = name_market[picks[0]]
            defense = defense_of(stamp, defense)
        elif held is not None and daily_look and mode == "vol_ratio":
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
        elif held is not None and daily_look and cadence == "frozen":
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
        elif daily_look and cadence != "frozen":
            _step_cadence()

        previous_count = len(picks)
        weights = _weights(picks, risk if held is not None else 0.0, defense, universe.cash)
        if stamp in week_set or _weight_key(weights, universe.cash) != _weight_key(previous_weights, universe.cash):
            decision_rows.append(weights)
            decision_index.append(stamp)
        previous_weights = weights
        if selection == "all":
            reps: list[str] = []
            labels: list[str] = []
            for name in picks:
                market = name_market.get(name)
                if market is None or market.representative in reps:
                    continue
                reps.append(market.representative)
                labels.append(market.name)
            market_id = "|".join(reps)
            market_label = "|".join(labels)
        else:
            market_id = "" if held is None else held.representative
            market_label = "" if held is None else held.name
        row = {
            "market": market_id,
            "market_name": market_label,
            "risk": 0.0 if held is None else risk,
            "defense": defense,
            "picks": "|".join(picks),
            "blocked": "|".join(sorted(blocked)),
        }
        if mode == "vol_ratio":
            focus = held.representative if held is not None else defense
            row["strength"] = _cell(strength, stamp, focus)
            row["noise"] = _cell(noise, stamp, focus)
        state_rows.append(row)
        for market in universe.markets:
            band = bands[market.representative]
            width = float(band.at[stamp]) if stamp in band.index else float("nan")
            flags = leg_flags(
                market.representative, stamp, level, frontier_share, easing, width, frozen.frontier,
            )
            if flags is None:
                leg1 = leg2 = score = float("nan")
            else:
                leg1 = float(flags[0])
                leg2 = float(flags[1])
                score = 0.5 * leg1 + 0.5 * leg2
            leg_rows.append((stamp, market.representative, market.name, leg1, leg2, score, width))

    state = pd.DataFrame(state_rows, index=days)
    exits = pd.DataFrame(exit_rows, columns=["t", "id", "why"])
    decisions = _decision_frame(decision_rows, decision_index, universe.cash)
    legs = pd.DataFrame(leg_rows, columns=["date", "market", "market_name", "leg1", "leg2", "score", "width"])
    return Allocation(state=state, decisions=decisions, exits=exits, legs=legs)


def _finite_number(value: float) -> bool:
    return value == value and np.isfinite(value)


def _best_id(names: list[str], day, score: pd.DataFrame) -> str:
    """强度高的在前。同分按容器 id 升序。"""
    return sorted(names, key=lambda name: (-_cell(score, day, name), name))[0]


def select_vol_market(held: str | None, defense: str, day, markets: tuple[Market, ...],
                      bond: str, gold: str, cash: str, strength: pd.DataFrame,
                      noise: pd.DataFrame, band: float) -> tuple[str | None, str]:
    """C-波动比的第一层。返回（市场代表或空，防守容器）。

    强度 M 高的才算最强。资格和离场看 M 的正负。换市场、换防守才看噪音 z 的差，
    要大于 `band`（冻稿的噪音带 1）。已经持有的市场，M 还没转负时不因为噪音不够而离场。
    """
    risk_ids = [market.representative for market in markets]
    held_id = held if held in risk_ids else None
    if held_id is not None:
        height = _cell(strength, day, held_id)
        if _finite_number(height) and height < 0.0:
            held_id = None
        else:
            base = _cell(noise, day, held_id)
            challengers = []
            for name in risk_ids:
                if name == held_id:
                    continue
                score = _cell(noise, day, name)
                if not _finite_number(score) or not (score > 0.0):
                    continue
                if not _finite_number(_cell(strength, day, name)):
                    continue
                if _finite_number(base) and not (score - base > band):
                    continue
                challengers.append(name)
            if challengers:
                held_id = _best_id(challengers, day, strength)
    if held_id is not None:
        return held_id, defense
    entrants = []
    for name in risk_ids:
        height = _cell(strength, day, name)
        score = _cell(noise, day, name)
        if _finite_number(height) and height > 0.0 and _finite_number(score):
            entrants.append(name)
    if entrants:
        return _best_id(entrants, day, strength), defense
    sleeves = []
    for name in (bond, gold):
        height = _cell(strength, day, name)
        score = _cell(noise, day, name)
        if _finite_number(height) and height > 0.0 and _finite_number(score):
            sleeves.append(name)
    if not sleeves:
        return None, cash
    if defense in sleeves:
        best = _best_id(sleeves, day, strength)
        if best != defense and _cell(noise, day, best) - _cell(noise, day, defense) > band:
            defense = best
        return None, defense
    return None, _best_id(sleeves, day, strength)


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
                   allow_after: bool = False, equal_weight: bool = False,
                   cadence: str = "frozen") -> Allocation:
    """先算 §2 的读数，再走 §3。不成交。`equal_weight` 只给 C-等权。"""
    frozen = Params() if params is None else params
    panel = read_panel(
        returns, universe.cash, allow_after=allow_after, params=frozen, equal_weight=equal_weight,
    )
    return allocate(
        panel.H.index, panel.H, panel.F, panel.E, universe,
        prices=level_index(returns), returns=returns, eligible=eligible,
        params=frozen, allow_after=allow_after, cadence=cadence,
    )
