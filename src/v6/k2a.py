"""K2A 日收益。算法照 scripts/preflight/sim.py 的 run(kind='K2A')，
调用方式照 topn_system.py：A 股为沪深300，美股为纳指与标普的简单平均，国债用项目序列。

不导入 sim.py。那个模块在导入时会读整份 ^GSPC、^HSI。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.v6.guard import IsolationError, assert_not_after

D, M, W = 252, 21, 5
COST = 0.001


def month_end_positions(index: pd.DatetimeIndex, calendar: bool) -> np.ndarray:
    """calendar 为真时用真实月末；否则每 21 个交易日的最后一根。"""
    if calendar:
        months = index.month.to_numpy()
        return np.flatnonzero(np.r_[months[1:] != months[:-1], True])
    return np.arange(M - 1, len(index), M)


def k2a_returns(a_ret: pd.Series, us_ret: pd.Series, bond: pd.Series, cash: pd.Series,
                calendar_month: bool = False) -> pd.Series:
    """日收益。第一天记 0。calendar_month 为真时均线和再平衡用真实月末，波动仍每 5 个交易日。"""
    if not a_ret.index.equals(us_ret.index):
        raise IsolationError("K2A 的两条腿不是同一个日历")
    assert_not_after(a_ret.index, "K2A")
    frame = pd.concat([a_ret.astype(float).rename("a"), us_ret.astype(float).rename("u")], axis=1)
    if frame.isna().any().any():
        raise IsolationError("K2A 的指数收益有空值")
    bond_on = bond.reindex(frame.index)
    cash_on = cash.reindex(frame.index)
    if cash_on.isna().any():
        raise IsolationError("K2A 的现金收益没有盖住日历")
    daily_bond = np.where(bond_on.notna().to_numpy(), bond_on.fillna(0).to_numpy(), cash_on.to_numpy())
    lr = np.log1p(frame.to_numpy())[None, :, :]
    ends = month_end_positions(frame.index, calendar_month)
    nav = _run_k2a(lr, daily_bond[None, :], ends, calendar_month)[0]
    out = pd.Series(nav, index=frame.index).pct_change().fillna(0.0)
    out.name = "K2A" if calendar_month else "K2A-参照"
    assert_not_after(out.index, "K2A")
    return out


def _run_k2a(lr: np.ndarray, bond: np.ndarray, month_ends: np.ndarray, calendar_month: bool) -> np.ndarray:
    """n=1 的 K2A。美股腿始终持有、不调波动；A 股腿用 10 个月均线和 20 日波动带。"""
    n, length, _ = lr.shape
    simple = np.expm1(lr)
    level = np.exp(np.cumsum(lr, axis=1))
    base = np.array([0.5, 0.5])
    on = np.ones((n, 2))
    frac = np.ones((n, 2))
    held = np.zeros((n, 3))
    held[:, :2] = base
    nav = np.ones(n)
    navs = np.empty((n, length))
    month_set = set(int(i) for i in month_ends)
    for t in range(length):
        gain = 1 + held[:, 0] * simple[:, t, 0] + held[:, 1] * simple[:, t, 1] + held[:, 2] * bond[:, t]
        held = np.column_stack([
            held[:, 0] * (1 + simple[:, t, 0]),
            held[:, 1] * (1 + simple[:, t, 1]),
            held[:, 2] * (1 + bond[:, t]),
        ]) / gain[:, None]
        nav = nav * gain
        navs[:, t] = nav
        month_end = t in month_set
        week_end = (t + 1) % W == 0
        new_on, new_frac = on, frac
        if month_end and not calendar_month and t >= 10 * M:
            closes = level[:, t - 9 * M:t + 1:M, :]
            new_on = (level[:, t, :] >= closes.mean(axis=1)).astype(float)
        if month_end and calendar_month:
            prior = month_ends[month_ends <= t]
            if len(prior) >= 10:
                closes = level[:, prior[-10:], :]
                new_on = (level[:, t, :] >= closes.mean(axis=1)).astype(float)
        if week_end and t >= D:
            long = lr[:, t - D + 1:t + 1, :]
            long_vol = long.std(axis=1)
            short_vol = lr[:, t - 20 + 1:t + 1, :].std(axis=1)
            scaled = np.minimum(1.0, long_vol / np.maximum(short_vol, 1e-9))
            new_frac = np.where(np.abs(scaled - frac) >= 0.10, scaled, frac)
        new_on = new_on.copy()
        new_on[:, 1] = 1.0
        new_frac = new_frac.copy()
        new_frac[:, 1] = 1.0
        legs = base * new_on * new_frac
        target = np.column_stack([legs, 1 - legs.sum(axis=1)])
        changed = (
            (new_on != on).any(axis=1)
            | (np.abs(new_frac - frac) > 1e-12).any(axis=1)
            | month_end
        )
        if changed.any():
            traded = np.abs(target - held).sum(axis=1) * changed
            nav = nav * (1 - COST * traded)
            held = np.where(changed[:, None], target, held)
        on, frac = new_on, new_frac
    return navs
