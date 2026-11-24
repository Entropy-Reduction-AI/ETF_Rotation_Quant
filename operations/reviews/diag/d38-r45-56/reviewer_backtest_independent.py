"""Reviewer 独立回测：信号、持仓、成本、EW、月收益与 t。不导入/不 exec 作者 prep/pick/run/report。"""
from __future__ import annotations

import math
from typing import Callable

import numpy as np
import pandas as pd

COST = 0.002
N_PICK = 3
MIN_WINDOW_DAYS = 200

P1_PHASES = {
    "2006-01 → 2007-10 大牛": ("2006-01", "2007-10"),
    "2007-11 → 2008-10 崩盘": ("2007-11", "2008-10"),
    "2008-11 → 2009-07 反弹": ("2008-11", "2009-07"),
    "2009-08 → 2014-06 结构与震荡": ("2009-08", "2014-06"),
    "2014-07 → 2015-11 大牛与崩盘": ("2014-07", "2015-11"),
}
P2_PHASES = {
    "2011-08 → 2013-12": ("2011-08", "2013-12"),
    "2014-01 → 2015-11": ("2014-01", "2015-11"),
}


def month_ends(cal: pd.DatetimeIndex) -> np.ndarray:
    mm = np.r_[cal.month[1:] != cal.month[:-1], True]
    return np.where(mm)[0]


def build_month_state(
    L: pd.DataFrame, overnight: dict[str, pd.Series] | None
) -> dict[pd.Timestamp, dict]:
    """月末信号：12−1、ID、隔夜窗口和（登记口径）。"""
    cal = L.index
    me_idx = month_ends(cal)
    r = L.pct_change()
    out: dict[pd.Timestamp, dict] = {}
    for k in range(12, len(me_idx)):
        a, b = me_idx[k - 12] + 1, me_idx[k - 1] + 1
        dts = cal[a:b]
        d = cal[me_idx[k]]
        R = r.iloc[a:b]
        nval = R.notna().sum(axis=0)
        mom = L.iloc[me_idx[k - 1]] / L.iloc[me_idx[k - 12]] - 1
        pos = (R > 0).sum() / nval.replace(0, np.nan)
        neg = (R < 0).sum() / nval.replace(0, np.nan)
        id_s = np.sign(mom) * (neg - pos)
        mom = mom.where(nval >= MIN_WINDOW_DAYS)
        id_s = id_s.where(nval >= MIN_WINDOW_DAYS)
        on_sum = None
        if overnight:
            rows = []
            for c in L.columns:
                if c not in overnight:
                    rows.append(np.nan)
                    continue
                s = overnight[c].reindex(dts)
                rows.append(s.sum(min_count=MIN_WINDOW_DAYS))
            on_sum = pd.Series(rows, index=L.columns)
        out[d] = {"mom": mom, "id": id_s, "on": on_sum}
    return out


def eligibility(row: dict, need_on: bool) -> pd.Series:
    m = row["mom"].notna()
    if need_on:
        return m & row["on"].notna()
    return m


def select_b0(row: dict, elig: pd.Series) -> list[str] | None:
    m = row["mom"].where(elig).dropna()
    if len(m) < 5:
        return None
    return list(m.nlargest(N_PICK).index)


def select_c1(row: dict, elig: pd.Series) -> list[str] | None:
    m = row["mom"].where(elig).dropna()
    if len(m) < 5:
        return None
    top = m.nlargest(math.ceil(len(m) / 2)).index
    tab = pd.DataFrame({"id": row["id"][top], "m": m[top]}).dropna()
    if len(tab) < N_PICK:
        return None
    tab = tab.sort_values(["id", "m"], ascending=[True, False])
    return list(tab.index[:N_PICK])


def select_c2(row: dict, elig: pd.Series) -> list[str] | None:
    o = row["on"].where(elig).dropna()
    if len(o) < N_PICK:
        return None
    return list(o.nlargest(N_PICK).index)


SELECTORS: dict[str, Callable] = {"B0": select_b0, "C1": select_c1, "C2": select_c2}


def ew_weights(elig: pd.Series, cols: list[str], tag_lookup: dict[str, str]) -> np.ndarray:
    K = len(cols)
    grp: dict[str, list[int]] = {}
    for j, c in enumerate(cols):
        g = tag_lookup.get(c, "") or f"_{c}"
        grp.setdefault(g, []).append(j)
    tgt = np.zeros(K)
    gs = [[j for j in js if elig.iloc[j]] for js in grp.values()]
    gs = [x for x in gs if x]
    if not gs:
        return tgt
    for members in gs:
        for j in members:
            tgt[j] = 1.0 / len(gs) / len(members)
    return tgt


def simulate_rules(
    L: pd.DataFrame,
    bond: pd.Series,
    month_state: dict[pd.Timestamp, dict],
    rules: list[str],
    need_on: bool,
    tag_lookup: dict[str, str],
    end_trade: str,
) -> dict[str, pd.Series]:
    L = L.loc[:end_trade]
    cal = L.index
    r = L.pct_change().fillna(0.0).values
    br = bond.reindex(cal).fillna(0.0).values
    cols = list(L.columns)
    K = len(cols)
    pos_of = {cal[i]: i for i in range(len(cal))}
    dec: dict[int, tuple[dict, pd.Series]] = {}
    for d, row in month_state.items():
        if d > pd.Timestamp(end_trade):
            continue
        if d not in pos_of:
            continue
        dec[pos_of[d]] = (row, eligibility(row, need_on))

    out: dict[str, pd.Series] = {}
    for rule in rules + ["EW"]:
        w = np.zeros(K)
        wb = 1.0
        nav = np.zeros(len(cal))
        cost = np.zeros(len(cal))
        pend = None
        for t in range(len(cal)):
            if pend is not None:
                tgt, tb = pend
                tr = float(np.abs(tgt - w).sum() + abs(tb - wb))
                cost[t] = COST * tr
                w, wb = tgt.copy(), tb
                pend = None
            g = float((w * r[t]).sum() + wb * br[t])
            nav[t] = (1 + g) * (1 - cost[t]) - 1
            gx = 1 + g
            if gx != 0:
                w = w * (1 + r[t]) / gx
                wb = wb * (1 + br[t]) / gx
            if t in dec:
                row, el = dec[t]
                if el.sum() < 5:
                    pend = (np.zeros(K), 1.0)
                    continue
                if rule == "EW":
                    tgt = ew_weights(el, cols, tag_lookup)
                else:
                    picks = SELECTORS[rule](row, el)
                    if picks is None:
                        pend = (np.zeros(K), 1.0)
                        continue
                    tgt = np.zeros(K)
                    for c in picks:
                        tgt[cols.index(c)] = 1.0 / N_PICK
                pend = (tgt, 1.0 - float(tgt.sum()))
        out[rule] = pd.Series(nav, cal)
    return out


def monthly_returns(daily_nav: pd.Series, a: str, b: str) -> pd.Series:
    s = daily_nav.loc[a:b]
    return (1 + s).groupby([s.index.year, s.index.month]).prod() - 1


def monthly_t_stat(diff: pd.Series) -> float | None:
    x = diff.dropna()
    if len(x) <= 2:
        return None
    return float(x.mean() / x.std(ddof=1) * math.sqrt(len(x)))


def annualized_pts(diff: pd.Series) -> float:
    return float(diff.mean() * 1200)


def summarize_vs_ew(
    sim: dict[str, pd.Series], rules: list[str], a: str, b: str
) -> dict[str, dict]:
    m = {k: monthly_returns(sim[k], a, b) for k in rules + ["EW"]}
    idx = m["EW"].index
    rep = {}
    for rule in rules:
        dx = m[rule] - m["EW"]
        rep[rule] = {
            "对等权_每月差_未四舍五入均值": float(dx.mean()),
            "对等权_每年点": round(annualized_pts(dx), 1),
            "对等权_t": round(monthly_t_stat(dx), 2) if monthly_t_stat(dx) is not None else None,
            "对B0_每年点": round(annualized_pts(m[rule] - m["B0"]), 1) if rule != "B0" else None,
            "对B0_t": round(monthly_t_stat(m[rule] - m["B0"]), 2) if rule != "B0" else None,
            "月数": int(len(dx)),
        }
    return rep


def phase_b0_minus(
    sim: dict[str, pd.Series], rule: str, phases: dict[str, tuple[str, str]]
) -> dict[str, float]:
    m_r = monthly_returns(sim[rule], "2006-01", "2015-11")
    m_b = monthly_returns(sim["B0"], "2006-01", "2015-11")
    idx = pd.Index([pd.Timestamp(y, m, 1) for y, m in m_r.index])
    m_r = pd.Series(m_r.values, idx)
    m_b = pd.Series(m_b.values, idx)
    out = {}
    for name, (pa, pb) in phases.items():
        sl = slice(pd.Timestamp(pa + "-01"), pd.Timestamp(pb + "-01"))
        out[name] = round(float((m_r.loc[sl] - m_b.loc[sl]).mean()) * 1200, 1)
    return out


def count_phases_beat(rule_pts_by_phase: dict[str, float]) -> int:
    return sum(1 for v in rule_pts_by_phase.values() if v > 0)