"""把附表 A 的月末目标落到持仓上。

决策在月末收盘之后。成交在下一个上交所交易日收盘，先按当天收益漂移，再换仓、扣费。
费用用 `leg_cost`，和 v4 同一套单边费率。报价存在时，涨停买单、跌停卖单、无价
按 §4.5 顺延；新的常规调仓执行日替换还没做成的顺延单。

不调用离场，不调用溢价，不打开 T1–T4。不读行情库。日期晚于 2015-12-31 直接拒绝。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.v3.engine.book import assert_window, drift, leg_cost
from src.v3.engine.limits import executable_weights, legs_clear, session_tradable
from src.v3.engine.sessions import next_session

from .config import PeerError, PeerRun
from .signals import decision_targets


@dataclass
class PeerResult:
    peer_id: str
    pool: str
    month_end_rule: str
    signal: pd.DataFrame
    held: pd.DataFrame
    close_held: pd.DataFrame
    decisions: pd.DataFrame
    cost: pd.Series
    net: pd.Series


def _sessions(dates) -> pd.DatetimeIndex:
    index = pd.DatetimeIndex(pd.to_datetime(dates)).normalize().sort_values().unique()
    if len(index) == 0:
        raise PeerError("没有交易日")
    return index


def _daily(level: pd.Series) -> pd.Series:
    change = level.pct_change(fill_method=None)
    values = change.to_numpy(dtype=float)
    values = np.where(np.isfinite(values), values, 0.0)
    values[0] = 0.0
    return pd.Series(values, index=level.index, dtype=float)


def _same(left: dict[str, float], right: dict[str, float], eps: float) -> bool:
    names = set(left) | set(right)
    return all(abs(float(left.get(name, 0.0)) - float(right.get(name, 0.0))) <= eps for name in names)


def _aligned(peer: PeerRun, sessions, levels: pd.DataFrame, cash: pd.Series | None) -> tuple[pd.DataFrame, pd.Series]:
    names = [leg.leg_id for leg in peer.legs]
    missing = [name for name in names if name not in levels.columns]
    if missing:
        raise PeerError(f"收盘缺腿 {missing}")
    frame = levels.loc[:, names].reindex(sessions)
    assert_window(levels.index, False)
    assert_window(sessions, False)
    if cash is None:
        series = pd.Series(peer.cash_annual / peer.trading_days, index=sessions, dtype=float)
    else:
        assert_window(cash.index, False)
        series = cash.reindex(sessions).astype(float)
        if not np.isfinite(series.to_numpy(dtype=float)).all():
            raise PeerError("现金日收益有缺日")
    return frame, series


def run_peer(peer: PeerRun, sessions, levels: pd.DataFrame, *,
             cash: pd.Series | None = None,
             carriers: pd.DataFrame | None = None,
             quotes: dict | None = None,
             calendar_closed: bool = False,
             signal_levels: pd.DataFrame | None = None) -> PeerResult:
    """手造或调用方给的序列。`net` 只是这些序列上的费用核对，不是策略成绩。

    `levels` 是持有和日收益。`signal_levels` 只用于月末判断；不传时判断和收益用同一条序列。
    U-可交易传入研究序列做判断、载体水平做收益。没有载体的那一腿仍由 `carriers` 改成现金。
    """
    if peer.exit_module or peer.premium_module or peer.t1_turn or peer.t2_state_weights or peer.t3_refill or peer.t4_pool:
        raise PeerError("附表 A 不接离场、溢价或 T1–T4")
    calendar = _sessions(sessions)
    panel, cash_series = _aligned(peer, calendar, levels, cash)
    if signal_levels is None:
        judged = panel
    else:
        judged, _ignored = _aligned(peer, calendar, signal_levels, cash)
    if carriers is not None:
        assert_window(carriers.index, False)
    decisions = decision_targets(
        peer, calendar, judged, cash_series, carriers=carriers, calendar_closed=calendar_closed)
    execution = {}
    for day in decisions.index:
        nxt = next_session(calendar, pd.Timestamp(day))
        if nxt is not None:
            execution[pd.Timestamp(nxt)] = pd.Timestamp(day)
    columns = list(decisions.columns) if len(decisions.columns) else (
        [leg.leg_id for leg in peer.legs] + [peer.cash_id])
    fees = peer.fees()
    returns = {name: _daily(panel[name]) for name in columns if name != peer.cash_id}
    returns[peer.cash_id] = cash_series
    weights = {name: 0.0 for name in columns}
    weights[peer.cash_id] = 1.0
    signal = dict(weights)
    pending = None
    signal_rows = []
    held_rows = []
    close_rows = []
    cost_rows = []
    net_rows = []
    leg_ids = [name for name in columns if name != peer.cash_id]
    for day in calendar:
        stamp = pd.Timestamp(day)
        held_rows.append([weights[name] for name in columns])
        gross, drifted = drift(weights, {name: float(returns[name].loc[stamp]) for name in columns})
        if stamp in decisions.index:
            signal = {name: float(decisions.at[stamp, name]) for name in columns}
        if stamp in execution:
            pending = {name: float(decisions.at[execution[stamp], name]) for name in columns}
        cost = 0.0
        if pending is not None:
            desired = pending
            if quotes is None:
                executed = desired
                pending = None
            else:
                tradable = session_tradable(quotes, stamp, leg_ids)
                if legs_clear(drifted, desired, tradable, peer.cash_id, peer.trade_eps):
                    executed = desired
                    pending = None
                else:
                    executed = executable_weights(
                        drifted, desired, tradable, peer.cash_id, peer.trade_eps)
                    if _same(executed, desired, peer.trade_eps):
                        pending = None
            cost, _buy, _sell = leg_cost(drifted, executed, fees, peer.trade_eps)
            weights = {name: float(executed[name]) for name in columns}
        else:
            weights = drifted
        signal_rows.append([signal[name] for name in columns])
        close_rows.append([weights[name] for name in columns])
        cost_rows.append(cost)
        net_rows.append(gross - cost)
    index = pd.DatetimeIndex(calendar)
    return PeerResult(
        peer_id=peer.peer_id,
        pool=peer.pool,
        month_end_rule=peer.month_end_rule,
        signal=pd.DataFrame(signal_rows, index=index, columns=columns),
        held=pd.DataFrame(held_rows, index=index, columns=columns),
        close_held=pd.DataFrame(close_rows, index=index, columns=columns),
        decisions=decisions,
        cost=pd.Series(cost_rows, index=index, dtype=float, name="cost"),
        net=pd.Series(net_rows, index=index, dtype=float, name="net"),
    )
