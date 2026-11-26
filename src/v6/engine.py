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


def _pick(scores: np.ndarray, ok: np.ndarray, tags: np.ndarray, n: int, dedupe: bool = True) -> list[int]:
    chosen, used = [], set()
    order = np.argsort(-np.where(ok, scores, -np.inf))
    for pos in order:
        if not ok[pos] or len(chosen) == n:
            break
        tag = tags[pos]
        if dedupe and tag and tag in used:
            continue
        chosen.append(int(pos))
        used.add(tag)
    return chosen


def continuity_pick(scores, ident, eligible, tags, n: int, dedupe: bool = True) -> list[int]:
    """去重后按 12−1 取前一半，再按 ID 从低到高取 n 个。同分用 12−1 更高的。"""
    ranked = _pick(scores, eligible, tags, int(np.sum(eligible)), dedupe)
    half = math.ceil(len(ranked) / 2) if ranked else 0
    pool = sorted(ranked[:half], key=lambda i: (float(ident[i]), -float(scores[i])))
    return pool[:n]


def continuity_state(levels, day, month_index, scores, min_days: int = 200):
    """§1.3。窗口是 T−12 月末之后到 T−1 月末。不足 min_days 个有效日的不参选。"""
    width = len(scores)
    blank = np.full(width, np.nan)
    none = np.zeros(width, dtype=bool)
    loc = month_index.get_loc(day)
    if not isinstance(loc, (int, np.integer)) or int(loc) < 12:
        return blank, none
    t12 = month_index[int(loc) - 12]
    t1 = month_index[int(loc) - 1]
    window = levels.pct_change().loc[lambda s: (s.index > t12) & (s.index <= t1)]
    valid = window.notna().sum().to_numpy()
    up = (window > 0).sum().to_numpy()
    down = (window < 0).sum().to_numpy()
    share = np.divide(down - up, valid, out=np.full(width, np.nan), where=valid > 0)
    ident = np.sign(scores) * share
    eligible = np.isfinite(scores) & np.isfinite(ident) & (valid >= min_days)
    return ident, eligible


def slot(levels, parent, n, prior, tags, mode, cost, votes_fn, bond, cash, dedupe: bool = True,
         signal_lag: int = 0, stress_votes: int = 2, exclude=None):
    """一个名额。mode：v6 四步全开；id 是加过滤的连续性版；id_open 是不过滤的参照；top 前 n 不设防守；ew 按标签等权、不设防守。

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
    month_index = pd.DatetimeIndex(calendar[mask])
    month = levels.loc[month_index]
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
    pending_delay = 0
    banned = {name for name in (exclude or ()) if name != parent}
    bond_ret = bond.reindex(calendar).fillna(0).values
    cash_ret = cash.reindex(calendar).values
    if np.isnan(cash_ret).any():
        raise IsolationError("现金收益没有盖住日历")
    history = []
    pending_leader = None
    log = {}
    for t, day in enumerate(calendar):
        if pending_target is not None and pending_delay > 0:
            pending_delay -= 1
            fee = 0.0
        elif pending_target is not None:
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
        if banned:
            ok = ok & np.array([name not in banned for name in columns])
        target = np.zeros(width)
        p_value = confidence(history, prior=prior)
        votes = int(vote_sum.get(day.to_period("M"), 0))
        stress = votes >= stress_votes
        record = {
            "票数": votes,
            "紧张": stress,
            "p": None if mode not in ("v6", "id", "id_open", "id_full", "id_open_full") else round(p_value, 3),
            "可参选": int(ok.sum()),
            "可参选名单": [columns[i] for i in range(width) if ok[i]],
        }
        if not ok.any():
            target[parent_at] = 1.0
            pick = [parent_at]
            raw = []
        else:
            raw = _pick(scores, ok, tag_of, n, dedupe)
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
            elif mode in ("id", "id_open", "id_full", "id_open_full"):
                # D47-3：主结果先限“12−1 为正”，再取前一半、按 ID 取 3 个。
                # 把握 p 的领头者不过这道过滤，与主规则“领头者不做正收益过滤”同一结构。
                gate = not bool(above.loc[day].to_numpy()[parent_at])
                ident, eligible = continuity_state(levels, day, month_index, scores)
                use_filter = mode in ("id", "id_full")
                hold_ok = eligible & (scores > 0) if (use_filter and gate) else eligible
                raw = continuity_pick(scores, ident, eligible, tag_of, n, dedupe)
                pick = continuity_pick(scores, ident, hold_ok, tag_of, n, dedupe)
                frac = p_value if (stress and mode in ("id", "id_open")) else 1.0
                if pick:
                    target[pick] = frac / n
                record["母指数跌破均线"] = gate
                record["股票仓位"] = round(float(target.sum()), 3)
                record["过滤规则"] = use_filter
                record["本月限为正"] = bool(use_filter and gate)
                record["领头者"] = [columns[i] for i in raw]
            else:
                gate = not bool(above.loc[day].to_numpy()[parent_at])
                allowed = ok & (scores > 0) if gate else ok
                frac = p_value if (stress and mode == "v6") else 1.0
                pick = _pick(scores, allowed, tag_of, n, dedupe)
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
        pending_delay = signal_lag
    series = pd.Series(out, index=calendar, name=parent)
    assert_not_after(series.index, "slot")
    return series, turnover, log


def mix_daily(a: pd.Series, u: pd.Series) -> pd.Series:
    return 0.4 * a + 0.6 * u


def mix_monthly(a: pd.Series, u: pd.Series, cost: float, weight_a: float = 0.4) -> pd.Series:
    """月末把两个名额再平衡到目标权重，调拨金额按单边成本计一次。默认 A 股 40%、美股 60%。"""
    calendar = a.index
    mask = np.r_[calendar.month[1:] != calendar.month[:-1], True]
    weight_u = 1.0 - weight_a
    wa, wu = weight_a, weight_u
    out = np.zeros(len(calendar))
    rebalance = False
    for t in range(len(calendar)):
        fee = 0.0
        if rebalance:
            fee = cost * abs(wa - weight_a)
            wa, wu = weight_a, weight_u
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
