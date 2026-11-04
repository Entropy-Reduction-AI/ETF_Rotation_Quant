"""R0：每月末抽一只，下一交易日收盘满仓。成交口径对齐 A 臂的单名满仓。

涨跌停沿用 `session_tradable`。卖不出就继续持有并改日再试；卖得出但买不进，
先落到现金，下一个交易日再买。新的月末决定会换掉还没完成的重试。
随机数是一条流：先跑完一次模拟的各月，再跑下一次。空月份拿现金，不抽数。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.v3.engine.book import assert_window
from src.v3.engine.limits import session_tradable
from src.v3.engine.sessions import next_session

from .params import V51Error

SEED = 20261101
N_SIMS = 2000


def draw_names(eligible: list[list[str]], *, n: int = N_SIMS, seed: int = SEED,
               cash_id: str = "cash") -> list[list[str]]:
    """候选先按 id 排序，无放回抽 1 只。`n` 次共用同一个 Generator。"""
    pools = [sorted(set(names)) for names in eligible]
    rng = np.random.default_rng(seed)
    drawn: list[list[str]] = []
    for _ in range(n):
        picks = []
        for names in pools:
            if not names:
                picks.append(cash_id)
                continue
            choice = rng.choice(np.asarray(names, dtype=object), size=1, replace=False)[0]
            picks.append(str(choice))
        drawn.append(picks)
    return drawn


def execution_positions(dates: pd.DatetimeIndex, decisions: pd.DatetimeIndex) -> np.ndarray:
    """决策日对应的成交日在 `dates` 里的位置。没有下一交易日时记 −1。"""
    index = pd.DatetimeIndex(pd.to_datetime(dates)).normalize()
    out = np.empty(len(decisions), dtype=int)
    for i, day in enumerate(decisions):
        nxt = next_session(index, pd.Timestamp(day))
        out[i] = -1 if nxt is None else int(index.get_loc(pd.Timestamp(nxt).normalize()))
    return out


def trade_masks(quotes, dates: pd.DatetimeIndex, columns: list[str], cash_id: str) -> tuple[np.ndarray, np.ndarray]:
    """(能买, 能卖)，列顺序与收益表一致。现金两边都视为可成交。"""
    names = [name for name in columns if name != cash_id]
    buy = np.zeros((len(dates), len(columns)), dtype=bool)
    sell = np.zeros((len(dates), len(columns)), dtype=bool)
    locate = {name: i for i, name in enumerate(columns)}
    buy[:, locate[cash_id]] = True
    sell[:, locate[cash_id]] = True
    for i, day in enumerate(dates):
        flags = session_tradable(quotes, day, names)
        for name in names:
            can_buy, can_sell = flags.get(name, (False, False))
            buy[i, locate[name]] = bool(can_buy)
            sell[i, locate[name]] = bool(can_sell)
    return buy, sell


def single_name_nets(returns: pd.DataFrame, cash_id: str, decisions: pd.DatetimeIndex,
                     picks: list[list[str]], fees: dict[str, float], can_buy: np.ndarray,
                     can_sell: np.ndarray, *, cost_multiplier: float = 1.0) -> np.ndarray:
    """每行一次模拟的日净收益。开盘前的持仓拿当天收益，收盘才换仓。"""
    frame = returns.copy()
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index)).normalize()
    assert_window(frame.index, False)
    if cash_id not in frame.columns:
        raise V51Error("收益里没有现金列")
    columns = list(frame.columns)
    if can_buy.shape != (len(frame), len(columns)) or can_sell.shape != can_buy.shape:
        raise V51Error("涨跌停掩码和收益表对不齐")
    if any(len(row) != len(decisions) for row in picks):
        raise V51Error("每次模拟的决定个数要和决策日一致")
    for name in columns:
        if name not in fees:
            raise V51Error(f"费用表缺 {name}")
    positions = execution_positions(frame.index, decisions)
    keep = positions >= 0
    if len(positions[keep]) != len(set(positions[keep].tolist())):
        raise V51Error("两个决策日落到了同一个成交日")
    exec_pos = positions[keep]
    codes = {name: i for i, name in enumerate(columns)}
    unknown = sorted({name for row in picks for name in row if name not in codes})
    if unknown:
        raise V51Error(f"随机抽到了收益里没有的容器：{unknown[:5]}")
    n_sims = len(picks)
    desired = np.empty((n_sims, int(keep.sum())), dtype=np.int16)
    for i, row in enumerate(picks):
        kept = [name for name, use in zip(row, keep) if use]
        desired[i] = [codes[name] for name in kept]
    values = frame.to_numpy(dtype=float)
    values = np.where(np.isfinite(values), values, 0.0)
    fee = np.array([float(fees[name]) for name in columns], dtype=float)
    cash_i = np.int16(codes[cash_id])
    multiplier = float(cost_multiplier)
    hold = np.full(n_sims, cash_i, dtype=np.int16)
    retry = np.full(n_sims, -1, dtype=np.int16)
    gross = np.zeros((n_sims, len(frame)), dtype=float)
    cost = np.zeros((n_sims, len(frame)), dtype=float)
    exec_at = {int(pos): i for i, pos in enumerate(exec_pos)}
    for t in range(len(frame)):
        gross[:, t] = values[t, hold]
        if t in exec_at:
            retry[:] = -1
            target = desired[:, exec_at[t]]
            has = np.ones(n_sims, dtype=bool)
        else:
            has = retry >= 0
            target = retry.copy()
            retry[:] = -1
        attempt = has & (target != hold)
        if not attempt.any():
            continue
        safe_target = np.where(attempt, target, 0)
        blocked_sell = attempt & (hold != cash_i) & ~can_sell[t, hold]
        blocked_buy = attempt & ~blocked_sell & (safe_target != cash_i) & ~can_buy[t, safe_target]
        retry[blocked_sell | blocked_buy] = target[blocked_sell | blocked_buy]
        go_cash = blocked_buy & (hold != cash_i)
        if go_cash.any():
            cost[go_cash, t] = (fee[hold[go_cash]] + fee[cash_i]) * multiplier
            hold[go_cash] = cash_i
        clear = attempt & ~blocked_sell & ~blocked_buy
        if clear.any():
            cost[clear, t] = (fee[hold[clear]] + fee[target[clear]]) * multiplier
            hold[clear] = target[clear]
    return gross - cost


def decision_frame(columns: list[str], cash_id: str, decisions: pd.DatetimeIndex,
                   picks: list[str]) -> pd.DataFrame:
    """一条模拟的目标权重。被抽中的那只为 1，其余为 0。"""
    rows = []
    for name in picks:
        if name not in columns:
            raise V51Error(f"决定里没有这个容器：{name}")
        row = {column: 0.0 for column in columns}
        row[name] = 1.0
        rows.append(row)
    frame = pd.DataFrame(rows, index=pd.DatetimeIndex(decisions), columns=columns)
    if cash_id not in frame.columns:
        raise V51Error("决定里没有现金列")
    return frame
