"""附表 A 的月末目标权重。只看调用方给的收盘和现金日收益，不读行情库。

价格必须已经对齐到上交所交易日。美股用严格早于决策日的收盘，港股用决策日当天收盘，
这一步由调用方按 §3.1 做完。这里不再改时点。
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.v4.peers.calendar import month_end_sessions
from src.v4.peers.config import PeerError, PeerRun


def prior_month_end(month_ends, day, months: int) -> pd.Timestamp | None:
    """往前数 `months` 个自然月的那一个月末。中间缺月就没有。"""
    want = pd.Timestamp(day).to_period("M") - int(months)
    hits = [pd.Timestamp(item) for item in month_ends if pd.Timestamp(item).to_period("M") == want]
    if len(hits) != 1:
        return None
    return hits[0]


def _level(series: pd.Series, day) -> float | None:
    stamp = pd.Timestamp(day)
    if stamp not in series.index:
        return None
    value = series.loc[stamp]
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0.0:
        return None
    return number


def trailing_price_return(level: pd.Series, month_ends, day, months: int) -> float | None:
    """月末收盘相对 `months` 个自然月之前那个月末收盘的收益。算不出来就是 None。"""
    prior = prior_month_end(month_ends, day, months)
    if prior is None:
        return None
    now = _level(level, day)
    then = _level(level, prior)
    if now is None or then is None:
        return None
    return now / then - 1.0


def trailing_cash_return(cash: pd.Series, month_ends, day, months: int) -> float | None:
    """从上一个比较月末的下一交易日到本月末（含）的现金连乘收益。"""
    prior = prior_month_end(month_ends, day, months)
    if prior is None:
        return None
    window = cash.loc[(cash.index > pd.Timestamp(prior)) & (cash.index <= pd.Timestamp(day))]
    values = window.to_numpy(dtype=float)
    if len(values) == 0 or not np.isfinite(values).all():
        return None
    return float(np.expm1(np.log1p(values).sum()))


def above_moving_average(level: pd.Series, month_ends, day, window: int) -> bool:
    """当月月末收盘严格高于含当月在内的 `window` 个月末收盘的简单平均。"""
    closes = []
    stamp = pd.Timestamp(day)
    for age in range(window - 1, -1, -1):
        point = stamp if age == 0 else prior_month_end(month_ends, stamp, age)
        if point is None:
            return False
        value = _level(level, point)
        if value is None:
            return False
        closes.append(value)
    return closes[-1] > float(np.mean(closes))


def _cash_book(peer: PeerRun) -> dict[str, float]:
    weights = {leg.leg_id: 0.0 for leg in peer.legs}
    weights[peer.cash_id] = 1.0
    return weights


def _carrier_ok(peer: PeerRun, carriers: pd.DataFrame | None, day, leg_id: str) -> bool:
    if peer.pool == "index":
        return True
    if carriers is None:
        return False
    stamp = pd.Timestamp(day)
    if leg_id not in carriers.columns or stamp not in carriers.index:
        return False
    value = carriers.at[stamp, leg_id]
    if value != value:
        return False
    return bool(value)


def dual_momentum(peer: PeerRun, day, month_ends, levels: pd.DataFrame, cash: pd.Series,
                  carriers: pd.DataFrame | None) -> dict[str, float]:
    """A1。标普500 的 12 个月收益不高于现金则全仓国债；否则全仓两条股票里更高的那条。"""
    months = peer.lookback_months
    equity = trailing_price_return(levels[peer.absolute_leg], month_ends, day, months)
    hurdle = trailing_cash_return(cash, month_ends, day, months)
    if equity is None or hurdle is None:
        return _cash_book(peer)
    if not equity > hurdle:
        defense = peer.defense_leg
        if _level(levels[defense], day) is None or not _carrier_ok(peer, carriers, day, defense):
            return _cash_book(peer)
        weights = _cash_book(peer)
        weights[defense] = 1.0
        weights[peer.cash_id] = 0.0
        return weights
    other = "csi300"
    relative = trailing_price_return(levels[other], month_ends, day, months)
    if relative is None:
        return _cash_book(peer)
    if relative > equity:
        chosen = other
    else:
        # 更高，或两条相等。相等时持有规则里先写到的标普500。
        chosen = peer.absolute_leg
    if not _carrier_ok(peer, carriers, day, chosen):
        return _cash_book(peer)
    weights = _cash_book(peer)
    weights[chosen] = 1.0
    weights[peer.cash_id] = 0.0
    return weights


def ten_month_average(peer: PeerRun, day, month_ends, levels: pd.DataFrame,
                      carriers: pd.DataFrame | None) -> dict[str, float]:
    """A2。五份各自 20%。没过均线、历史不够或没有载体的那一份留在现金。"""
    weights = _cash_book(peer)
    held = 0.0
    share = float(peer.sleeve_weight)
    for leg in peer.legs:
        if not above_moving_average(levels[leg.leg_id], month_ends, day, peer.lookback_months):
            continue
        if not _carrier_ok(peer, carriers, day, leg.leg_id):
            continue
        weights[leg.leg_id] = share
        held += share
    weights[peer.cash_id] = 1.0 - held
    return weights


def decision_targets(peer: PeerRun, sessions, levels: pd.DataFrame, cash: pd.Series, *,
                     carriers: pd.DataFrame | None = None,
                     calendar_closed: bool = False) -> pd.DataFrame:
    """每个月末一行目标权重。还没有决策的日子不在表里。"""
    if peer.pool == "index" and carriers is not None:
        raise PeerError("U-指数用研究序列，不接收载体掩码")
    if peer.pool == "tradable" and carriers is None:
        raise PeerError("U-可交易必须给出每一腿当天有没有载体")
    if carriers is not None:
        carriers = carriers.copy()
        carriers.index = pd.DatetimeIndex(pd.to_datetime(carriers.index)).normalize()
    ends = month_end_sessions(sessions, calendar_closed=calendar_closed)
    columns = [leg.leg_id for leg in peer.legs] + [peer.cash_id]
    rows = []
    for day in ends:
        if peer.peer_id == "A1":
            weights = dual_momentum(peer, day, ends, levels, cash, carriers)
        elif peer.peer_id == "A2":
            weights = ten_month_average(peer, day, ends, levels, carriers)
        else:
            raise PeerError(peer.peer_id)
        rows.append([weights[name] for name in columns])
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, index=pd.DatetimeIndex(ends), columns=columns)
