"""持有、漂移、按资产类别扣费。成交在决策日的下一交易日收盘。"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .sessions import next_session

DESIGN_END = pd.Timestamp("2015-12-31")


class RunnerError(RuntimeError):
    pass


@dataclass
class Book:
    net: pd.Series
    gross: pd.Series
    held: pd.DataFrame
    decisions: pd.DataFrame
    targets: pd.DataFrame
    cost: pd.Series
    buy: pd.Series
    sell: pd.Series
    choices: dict = field(default_factory=dict)


def assert_window(index, allow_after: bool) -> None:
    if allow_after or len(index) == 0:
        return
    last = pd.Timestamp(max(pd.Timestamp(day) for day in index))
    if last > DESIGN_END:
        raise RunnerError(f"拒绝计算 {last.date()} 的组合收益：晚于 {DESIGN_END.date()}")


def drift(weights: dict[str, float], rets: dict[str, float]) -> tuple[float, dict[str, float]]:
    port = 0.0
    grown: dict[str, float] = {}
    for name, weight in weights.items():
        value = rets.get(name, 0.0)
        if value is None or value != value:
            value = 0.0
        grown[name] = weight * (1.0 + float(value))
        port += weight * float(value)
    scale = 1.0 + port
    if scale == 0.0:
        return port, dict(weights)
    return port, {name: value / scale for name, value in grown.items()}


def leg_cost(before: dict[str, float], after: dict[str, float], fees: dict[str, float],
             trade_eps: float) -> tuple[float, float, float]:
    """卖出腿和买入腿各自按该腿资产类别扣一次。没有成交则费用为 0。"""
    cost = 0.0
    buy = 0.0
    sell = 0.0
    for name in set(before) | set(after):
        change = float(after.get(name, 0.0)) - float(before.get(name, 0.0))
        if abs(change) <= trade_eps:
            continue
        cost += abs(change) * float(fees[name])
        if change > 0.0:
            buy += change
        else:
            sell -= change
    return cost, buy, sell


def to_execution(decisions: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    rows = []
    index = []
    for day, row in decisions.iterrows():
        nxt = next_session(dates, pd.Timestamp(day))
        if nxt is None:
            continue
        rows.append(row.to_numpy(dtype=float))
        index.append(nxt)
    if not rows:
        return pd.DataFrame(columns=decisions.columns)
    return pd.DataFrame(rows, index=pd.DatetimeIndex(index), columns=decisions.columns)


def simulate(pnl: pd.DataFrame, targets: pd.DataFrame, fees: dict[str, float], cash_id: str, *,
             trade_eps: float = 1e-12, cost_multiplier: float = 1.0,
             allow_after: bool = False) -> Book:
    """当日收益用开盘前权重。执行日先按当日收益漂移，再在收盘换成目标权重并扣费。"""
    assert_window(pnl.index, allow_after)
    columns = list(pnl.columns)
    if cash_id not in columns:
        raise RunnerError("收益里没有现金列")
    weights = {cash_id: 1.0}
    for name in columns:
        weights.setdefault(name, 0.0)
    target_rows = {} if targets is None or targets.empty else {
        pd.Timestamp(day).normalize(): row for day, row in targets.iterrows()
    }
    held_rows = []
    net_rows = []
    gross_rows = []
    cost_rows = []
    buy_rows = []
    sell_rows = []
    index = []
    for day in pnl.index:
        stamp = pd.Timestamp(day).normalize()
        held_rows.append([weights.get(name, 0.0) for name in columns])
        rets = {name: pnl.at[day, name] for name in columns}
        gross, drifted = drift(weights, rets)
        cost = 0.0
        buy = 0.0
        sell = 0.0
        if stamp in target_rows:
            raw = target_rows[stamp]
            target = {name: float(raw[name]) if name in raw.index else 0.0 for name in columns}
            target[cash_id] = float(raw[cash_id]) if cash_id in raw.index else target.get(cash_id, 0.0)
            cost, buy, sell = leg_cost(drifted, target, fees, trade_eps)
            cost *= cost_multiplier
            weights = target
        else:
            weights = drifted
        gross_rows.append(gross)
        net_rows.append(gross - cost)
        cost_rows.append(cost)
        buy_rows.append(buy)
        sell_rows.append(sell)
        index.append(stamp)
    idx = pd.DatetimeIndex(index)
    return Book(
        net=pd.Series(net_rows, index=idx, dtype=float, name="net"),
        gross=pd.Series(gross_rows, index=idx, dtype=float, name="gross"),
        held=pd.DataFrame(held_rows, index=idx, columns=columns),
        decisions=pd.DataFrame(),
        targets=targets if targets is not None else pd.DataFrame(),
        cost=pd.Series(cost_rows, index=idx, dtype=float, name="cost"),
        buy=pd.Series(buy_rows, index=idx, dtype=float, name="buy"),
        sell=pd.Series(sell_rows, index=idx, dtype=float, name="sell"),
    )


def empty_decisions(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)
