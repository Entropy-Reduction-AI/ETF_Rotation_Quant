"""v6 名额引擎。算法与冻结的 v6_appendix_b.slot 相同。"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.v6.guard import IsolationError, assert_not_after


def phi(t: float) -> float:
    return 0.5 * (1.0 + math.erf(t / math.sqrt(2.0)))


def confidence(hist, prior=None, min_n: int = 12) -> float:
    """D45-5。样本不足或标准差为 0 时为 0.5。"""
    sample = list(prior or []) + list(hist)
    if len(sample) < min_n:
        return 0.5
    values = np.asarray(sample, dtype=float)
    scale = float(values.std(ddof=1))
    if scale == 0.0 or not np.isfinite(scale):
        return 0.5
    return phi(float(values.mean()) / scale * math.sqrt(len(values)))


def _pick(scores: np.ndarray, ok: np.ndarray, tags: np.ndarray, n: int) -> list[int]:
    chosen, used = [], set()
    order = np.argsort(-np.where(ok, scores, -np.inf))
    for pos in order:
        if not ok[pos] or len(chosen) == n:
            break
        tag = tags[pos]
        if tag and tag in used:
            continue
        chosen.append(int(pos))
        used.add(tag)
    return chosen


def slot(levels, parent, n, prior, tags, mode, cost, votes_fn, bond, cash):
    """一个名额。mode：v6 四步全开；top 前 n 不设防守；ew 按标签等权、不设防守。

    prior 为 None 表示没有起点经验（A 股）。美股必须传入 French 列表；
    调用方在文件缺失时不要用空列表冒充。
    """
    assert_not_after(levels.index, parent)
    calendar = levels.index
    returns = levels.pct_change().fillna(0).values
    columns = list(levels.columns)
    width = len(columns)
    tag_of = np.array([tags.get(c, "") for c in columns], dtype=object)
    parent_at = columns.index(parent)
    mask = np.r_[calendar.month[1:] != calendar.month[:-1], True]
    month = levels.loc[calendar[mask]]
    score_frame = month.shift(1) / month.shift(12) - 1
    above = month > month.rolling(10).mean()
    forward = month.pct_change().shift(-1)
    bond_level = np.exp(np.log1p(bond.fillna(0)).cumsum()).where(bond.notna().cumsum() > 0)
    bond_month = bond_level.loc[calendar[mask]]
    bond_above = (bond_month > bond_month.rolling(10).mean()) & bond_month.notna()
    vote_sum, _n_votes = votes_fn(levels, parent, ["均线", "宽度", "TRIN"])
    weight = np.zeros(width)
    bond_w = 0.0
    cash_w = 1.0
    out = np.zeros(len(calendar))
    turnover = 0.0
    pending_target = None
    bond_ret = bond.reindex(calendar).fillna(0).values
    cash_ret = cash.reindex(calendar).values
    if np.isnan(cash_ret).any():
        raise IsolationError("现金收益没有盖住日历")
    history = []
    pending_leader = None
    log = {}
    for t, day in enumerate(calendar):
        if pending_target is not None:
            target, target_bond, target_cash = pending_target
            traded = float(np.abs(target - weight).sum() + abs(target_bond - bond_w))
            turnover += traded
            fee = cost * traded
            weight, bond_w, cash_w = target, target_bond, target_cash
            pending_target = None
        else:
            fee = 0.0
        gross = float((weight * returns[t]).sum() + bond_w * bond_ret[t] + cash_w * cash_ret[t])
        out[t] = (1.0 + gross) * (1.0 - fee) - 1.0
        growth = 1.0 + gross
        weight = weight * (1.0 + returns[t]) / growth
        bond_w = bond_w * (1.0 + bond_ret[t]) / growth
        cash_w = cash_w * (1.0 + cash_ret[t]) / growth
        if not mask[t]:
            continue
        if pending_leader is not None:
            history.append(pending_leader)
            pending_leader = None
        scores = score_frame.loc[day].to_numpy(dtype=float)
        ok = np.isfinite(scores)
        target = np.zeros(width)
        p_value = confidence(history, prior=prior)
        votes = int(vote_sum.get(day.to_period("M"), 0))
        stress = votes >= 2
        record = {
            "票数": votes,
            "紧张": stress,
            "p": None if mode != "v6" else round(p_value, 3),
            "可参选": int(ok.sum()),
            "可参选名单": [columns[i] for i in range(width) if ok[i]],
        }
        if not ok.any():
            target[parent_at] = 1.0
            pick = [parent_at]
            raw = []
        else:
            raw = _pick(scores, ok, tag_of, n)
            no_dedupe = [i for i in np.argsort(-np.where(ok, scores, -np.inf))[:n] if ok[i]]
            record["去重改了名单"] = sorted(raw) != sorted(no_dedupe)
            if mode == "ew":
                groups = {}
                for i in range(width):
                    if not ok[i]:
                        continue
                    key = tag_of[i] or f"_{i}"
                    groups.setdefault(key, []).append(i)
                for members in groups.values():
                    for i in members:
                        target[i] = 1.0 / len(groups) / len(members)
                pick = list(np.where(ok)[0])
            else:
                gate = not bool(above.loc[day].to_numpy()[parent_at])
                allowed = ok & (scores > 0) if gate else ok
                frac = p_value if (stress and mode == "v6") else 1.0
                pick = _pick(scores, allowed, tag_of, n)
                target[pick] = frac / n
                record["母指数跌破均线"] = gate
                record["股票仓位"] = round(float(target.sum()), 3)
            nxt = forward.loc[day].to_numpy(dtype=float)
            if stress and raw and np.isfinite(nxt[raw]).all():
                pending_leader = float(np.mean(nxt[raw]))
        record["持有"] = [columns[i] for i in pick] if mode != "ew" else []
        record["分数"] = {
            columns[i]: float(scores[i]) for i in range(width) if ok[i]
        }
        held_bond = bool(bond_above.loc[day]) if day in bond_above.index else False
        record["国债在均线上方"] = held_bond
        log[day] = record
        left = 1.0 - float(target.sum())
        pending_target = (target, left if held_bond else 0.0, 0.0 if held_bond else left)
    series = pd.Series(out, index=calendar, name=parent)
    assert_not_after(series.index, "slot")
    return series, turnover, log


def mix_daily(a: pd.Series, u: pd.Series) -> pd.Series:
    return 0.4 * a + 0.6 * u


def mix_monthly(a: pd.Series, u: pd.Series, cost: float) -> pd.Series:
    """月末把两个名额再平衡到 40/60，调拨金额按单边成本计一次。"""
    calendar = a.index
    mask = np.r_[calendar.month[1:] != calendar.month[:-1], True]
    wa, wu = 0.4, 0.6
    out = np.zeros(len(calendar))
    rebalance = False
    for t in range(len(calendar)):
        fee = 0.0
        if rebalance:
            fee = cost * abs(wa - 0.4)
            wa, wu = 0.4, 0.6
            rebalance = False
        gross = wa * float(a.iloc[t]) + wu * float(u.iloc[t])
        out[t] = (1.0 + gross) * (1.0 - fee) - 1.0
        wa = wa * (1.0 + float(a.iloc[t])) / (1.0 + gross)
        wu = wu * (1.0 + float(u.iloc[t])) / (1.0 + gross)
        if mask[t]:
            rebalance = True
    return pd.Series(out, index=calendar)


def benchmark(a_level, us_level, weights) -> pd.Series:
    """每月最后一个交易日收盘后回到目标权重，下一交易日开始生效。美股用价格指数。"""
    parts = pd.DataFrame({
        "c": a_level["csi300"].pct_change(),
        "n": us_level["NDX"].pct_change(),
        "s": us_level["SPX"].pct_change(),
    }).fillna(0)
    calendar = parts.index
    mask = np.r_[calendar.month[1:] != calendar.month[:-1], True]
    target = np.array(weights, dtype=float)
    held = target.copy()
    out = np.zeros(len(calendar))
    for t in range(len(calendar)):
        day = parts.iloc[t].to_numpy(dtype=float)
        gross = float((held * day).sum())
        out[t] = gross
        held = held * (1.0 + day) / (1.0 + gross)
        if mask[t]:
            held = target.copy()
    return pd.Series(out, index=calendar)


def cagr_pct(returns: pd.Series, start: str, end: str) -> float:
    window = returns.loc[start:end]
    assert_not_after(window.index, "cagr")
    growth = float((1.0 + window).prod())
    return (growth ** (252 / len(window)) - 1.0) * 100.0


def signal_month(index: pd.DatetimeIndex, year: int, month: int) -> pd.Timestamp:
    hits = index[(index.year == year) & (index.month == month)]
    if len(hits) != 1:
        raise IsolationError(f"{year}-{month:02d} 信号日不是唯一月末：{list(hits)}")
    return pd.Timestamp(hits[0])
