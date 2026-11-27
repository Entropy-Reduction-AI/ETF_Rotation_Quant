"""D45 第二版的设计期引擎。主日历、T−12、发布后第一笔、两种 TRIN 截尾。"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .d45_french import confidence

CUTOFF = pd.Timestamp("2015-12-31")
US_TRIN = ("XLK", "XLV", "XLE", "XLY", "XLP", "XLF", "XLI", "XLB", "XLU")
INDUSTRY_PUBLISH = pd.Timestamp("2011-08-02")


def _positive(frame: pd.Series) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=float)
    out = frame.astype(float)
    out = out[out > 0]
    return out[~out.index.duplicated(keep="last")].sort_index()


def on_calendar(series: pd.Series, calendar: pd.DatetimeIndex, first: pd.Timestamp | None) -> pd.Series:
    if series.empty or first is None:
        return pd.Series(np.nan, index=calendar)
    aligned = series.reindex(calendar.union(series.index)).ffill().reindex(calendar)
    return aligned.where(aligned.index >= first)


def first_on_or_after(series: pd.Series, day: pd.Timestamp) -> pd.Timestamp | None:
    if series.empty:
        return None
    kept = series[series.index >= day]
    if kept.empty:
        return None
    return pd.Timestamp(kept.index[0])


def month_end_mask(calendar: pd.DatetimeIndex) -> np.ndarray:
    months = calendar.month.to_numpy()
    return np.r_[months[1:] != months[:-1], True]


def trin_from_prices(prices: pd.DataFrame, amounts: pd.DataFrame, *, clip: str) -> pd.Series:
    change = prices.pct_change()
    up = change > 0
    down = change < 0
    up_n = up.sum(axis=1).astype(float)
    down_n = down.sum(axis=1).astype(float).replace(0.0, np.nan)
    up_amt = (amounts * up).sum(axis=1).astype(float)
    down_amt = (amounts * down).sum(axis=1).astype(float).replace(0.0, np.nan)
    ratio = ((up_n / down_n) / (up_amt / down_amt)).replace([np.inf, -np.inf], np.nan)
    ratio = ratio.where(up.sum(axis=1) + down.sum(axis=1) >= 4)
    if clip == "full":
        capped = ratio.clip(upper=ratio.quantile(0.99))
    elif clip == "expanding":
        capped = ratio.clip(upper=ratio.expanding().quantile(0.99))
    else:
        raise ValueError(clip)
    monthly = capped.rolling(10, min_periods=7).mean().resample("ME").last()
    monthly.index = monthly.index.to_period("M")
    return monthly


def votes(levels: pd.DataFrame, parent: str, trin: pd.Series) -> pd.Series:
    mask = month_end_mask(levels.index)
    month = levels.loc[mask].copy()
    month.index = month.index.to_period("M")
    average = month.rolling(10).mean()
    ma_vote = (month[parent] < average[parent]).astype(float)
    breadth = (month > average).where(month.rolling(10).count() == 10).mean(axis=1)
    enough = breadth.expanding(min_periods=24).count() >= 24
    breadth_vote = (breadth <= breadth.expanding(min_periods=24).quantile(1.0 / 3.0)).where(enough).fillna(0.0)
    trin_month = trin.reindex(month.index)
    trin_enough = trin_month.expanding(min_periods=24).count() >= 24
    trin_vote = (trin_month >= trin_month.expanding(min_periods=24).quantile(2.0 / 3.0)).where(trin_enough).fillna(0.0)
    return ma_vote.fillna(0.0) + breadth_vote.astype(float) + trin_vote.astype(float)


def continuity_balance(levels: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """ID 的方向以外部分，以及窗口内有效交易日。窗口是 12 个月前月末之后到上月末。"""
    change = levels.pct_change()
    up = change > 0
    down = change < 0
    known = change.notna()
    ends = list(levels.index[month_end_mask(levels.index)])
    balance_rows = []
    day_rows = []
    for pos, _stamp in enumerate(ends):
        if pos < 12:
            balance_rows.append(np.full(levels.shape[1], np.nan))
            day_rows.append(np.zeros(levels.shape[1]))
            continue
        start, stop = ends[pos - 12], ends[pos - 1]
        window = known.loc[(known.index > start) & (known.index <= stop)]
        days = window.sum(axis=0).to_numpy(dtype=float)
        down_n = down.loc[window.index].sum(axis=0).to_numpy(dtype=float)
        up_n = up.loc[window.index].sum(axis=0).to_numpy(dtype=float)
        balance = np.full(levels.shape[1], np.nan)
        enough = days >= 200
        balance[enough] = (down_n[enough] - up_n[enough]) / days[enough]
        balance_rows.append(balance)
        day_rows.append(days)
    index = pd.DatetimeIndex(ends)
    return (
        pd.DataFrame(balance_rows, index=index, columns=levels.columns),
        pd.DataFrame(day_rows, index=index, columns=levels.columns),
    )


def continuity_pick(score: np.ndarray, ok: np.ndarray, identity: np.ndarray, tag: np.ndarray,
                    names: int = 3) -> list[int]:
    """先在给定池子里按 12−1 去重排名，取前一半（向上取整），再取 ID 最低的 3 个。"""
    ranked: list[int] = []
    used: set[str] = set()
    order = np.argsort(-np.where(ok, score, -np.inf))
    for pos in order:
        if not ok[pos]:
            break
        label = tag[pos]
        if label and label in used:
            continue
        ranked.append(int(pos))
        if label:
            used.add(str(label))
    half = math.ceil(len(ranked) / 2)
    pool = ranked[:half]
    pool.sort(key=lambda pos: (float(identity[pos]), -float(score[pos])))
    return pool[:names]


def run_slot(levels: pd.DataFrame, parent: str, vote: pd.Series, bond: pd.Series, cash: pd.Series,
             tags: dict[str, str], prior: list[float] | None, *, mode: str, cost: float, names: int = 3,
             dedupe: bool = True, exclude: frozenset[str] | None = None):
    calendar = levels.index
    returns = levels.pct_change().fillna(0.0)
    mask = month_end_mask(calendar)
    month_level = levels.loc[mask]
    momentum = month_level.shift(1) / month_level.shift(12) - 1.0
    above = month_level > month_level.rolling(10).mean()
    forward = month_level.pct_change().shift(-1)
    bond_level = np.exp(np.log1p(bond.fillna(0.0)).cumsum()).where(bond.notna().cumsum() > 0)
    bond_month = bond_level.loc[mask]
    bond_above = (bond_month > bond_month.rolling(10).mean()) & bond_month.notna()
    columns = list(levels.columns)
    tag = np.array([tags.get(column, "") for column in columns], dtype=object)
    parent_at = columns.index(parent)
    banned = set(exclude or ())
    held = np.zeros(len(columns))
    bond_weight = 0.0
    cash_weight = 1.0
    out = np.zeros(len(calendar))
    turnover = 0.0
    pending = None
    history: list[float] = []
    queued: float | None = None
    log: dict = {}
    asset = returns.to_numpy(dtype=float)
    bond_ret = bond.fillna(0.0).to_numpy(dtype=float)
    cash_ret = cash.to_numpy(dtype=float)
    continuity = mode in ("cont", "cont_ref")
    balance_at, days_at = continuity_balance(levels) if continuity else (None, None)

    def choose(score: np.ndarray, ok: np.ndarray) -> list[int]:
        picked: list[int] = []
        used: set[str] = set()
        order = np.argsort(-np.where(ok, score, -np.inf))
        for pos in order:
            if not ok[pos] or len(picked) == names:
                break
            if columns[pos] in banned:
                continue
            label = tag[pos]
            if dedupe and label and label in used:
                continue
            picked.append(int(pos))
            if label:
                used.add(str(label))
        return picked

    for today in range(len(calendar)):
        fee = 0.0
        if pending is not None:
            target, target_bond, target_cash = pending
            traded = float(np.abs(target - held).sum() + abs(target_bond - bond_weight))
            turnover += traded
            fee = cost * traded
            held, bond_weight, cash_weight = target, target_bond, target_cash
            pending = None
        gain = float((held * asset[today]).sum() + bond_weight * bond_ret[today] + cash_weight * cash_ret[today])
        out[today] = (1.0 + gain) * (1.0 - fee) - 1.0
        gross = 1.0 + gain
        held = held * (1.0 + asset[today]) / gross
        bond_weight = bond_weight * (1.0 + bond_ret[today]) / gross
        cash_weight = cash_weight * (1.0 + cash_ret[today]) / gross
        if not mask[today]:
            continue
        stamp = calendar[today]
        if queued is not None:
            history.append(queued)
            queued = None
        score = momentum.loc[stamp].to_numpy(dtype=float)
        ok = np.isfinite(score)
        if banned:
            for pos, name in enumerate(columns):
                if name in banned:
                    ok[pos] = False
        target = np.zeros(len(columns))
        belief = confidence(history, prior)
        votes_now = int(vote.get(stamp.to_period("M"), 0))
        stressed = votes_now >= 2
        record = {"票数": votes_now, "紧张": stressed, "p": round(belief, 3), "可参选": int(ok.sum())}
        if not ok.any():
            target[parent_at] = 1.0
            picked: list[int] = [parent_at]
            raw: list[int] = []
            record["股票仓位"] = 1.0
            record["去重改了名单"] = False
            record["母指数跌破均线"] = False
        elif mode == "ew":
            groups: dict[str, list[int]] = {}
            for pos in range(len(columns)):
                if ok[pos]:
                    groups.setdefault(str(tag[pos]) or f"_{pos}", []).append(pos)
            for members in groups.values():
                for pos in members:
                    target[pos] = 1.0 / len(groups) / len(members)
            picked = list(np.where(ok)[0])
            raw = []
        else:
            gate = not bool(above.loc[stamp].iloc[parent_at])
            record["母指数跌破均线"] = gate
            if continuity:
                sign = np.sign(score)
                ident = sign * balance_at.loc[stamp].to_numpy(dtype=float)
                eligible = ok & (days_at.loc[stamp].to_numpy(dtype=float) >= 200) & np.isfinite(ident)
                raw = continuity_pick(score, eligible, ident, tag, names)
                tradable = eligible & (score > 0) if (mode == "cont" and gate) else eligible
                picked = continuity_pick(score, tradable, ident, tag, names)
                record["去重改了名单"] = False
                record["领头者"] = [columns[pos] for pos in raw]
            else:
                raw = choose(score, ok)
                no_dedupe = [int(pos) for pos in np.argsort(-np.where(ok, score, -np.inf))[:names] if ok[pos]]
                record["去重改了名单"] = sorted(raw) != sorted(no_dedupe)
                tradable = ok & (score > 0) if gate else ok
                picked = choose(score, tradable)
            fraction = belief if (stressed and mode in ("v6", "cont", "cont_ref")) else 1.0
            if picked:
                target[picked] = fraction / names
            record["股票仓位"] = round(float(target.sum()), 3)
            nxt = forward.loc[stamp].to_numpy(dtype=float)
            if stressed and raw and np.isfinite(nxt[raw]).all():
                queued = float(np.mean(nxt[raw]))
        left = 1.0 - float(target.sum())
        bond_ok = bool(bond_above.loc[stamp]) if stamp in bond_above.index else False
        record["持有"] = [columns[pos] for pos in picked] if mode != "ew" else []
        record["权重"] = {columns[pos]: float(target[pos]) for pos in picked}
        record["分数"] = {columns[pos]: float(score[pos]) for pos in range(len(columns)) if np.isfinite(score[pos])}
        record["国债"] = round(left if bond_ok else 0.0, 6)
        record["现金"] = round(0.0 if bond_ok else left, 6)
        log[stamp] = record
        pending = (target, left if bond_ok else 0.0, 0.0 if bond_ok else left)
    return pd.Series(out, index=calendar), turnover, log
