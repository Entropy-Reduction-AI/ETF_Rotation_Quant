#!/usr/bin/env python3
"""v5.1 R3：§2 H/F/E/B 与 §3 持仓独立复算（Reviewer，不 import 引擎读数/配权作真值）。

用法（仓库根）：
  .venv/bin/python operations/reviews/diag/v51/v51-r3-recalc.py

只读 data/market.sqlite 的 ≤2015-12-31 信号收益；不算组合 PnL。
"""
from __future__ import annotations

import bisect
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.v3.engine.exit import triggered, valid_mark
from src.v3.engine.sessions import decision_dates
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets
from src.v51.allocate import breadth as engine_breadth
from src.v51.allocate import target_weights as engine_target_weights
from src.v51.params import RULERS, Params
from src.v51.readings import read_panel
from src.v51.universe import class_lookup, universe_from_names
from src.v5.campaign import classes_for, class_map

OUT = ROOT / "operations" / "reviews" / "diag" / "v51" / "v51-r3-recalc.json"
ARTIFACT = Path("/opt/cursor/artifacts/v51-r3-recalc.json")

# §9：5 序列 × 5 日期。序列固定为三层代表 + 防守；日期 seed 可复现。
SEQUENCES = ("csi300", "hsi", "spx", "cgb-10y", "gold")
DATE_SEED = 20261104
BROAD = {"A股": "csi300", "港股": "hsi", "美股": "spx"}
RISK_REPS = tuple(BROAD.values())
RTOL = 0.0
ATOL = 1e-12


def _percentile_past(values: np.ndarray, minimum: int) -> np.ndarray:
    out = np.full(len(values), np.nan)
    history: list[float] = []
    for i, value in enumerate(values):
        if np.isnan(value):
            continue
        if len(history) >= minimum:
            out[i] = bisect.bisect_left(history, float(value)) / len(history)
        bisect.insort(history, float(value))
    return out


def independent_readings(
    returns: pd.DataFrame,
    cash_id: str,
    *,
    rulers: tuple[int, ...] = RULERS,
    sigma_window: int = 250,
    quantile_min: int = 250,
    slow_gap: int = 20,
    long_min: int = 60,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """冻结 §2  prose，与 tests/v51/test_readings._portrait 同构，不调用 src.v51.readings。"""
    long = [n for n in rulers if n >= long_min]
    cash_log = np.log1p(returns[cash_id].fillna(0.0))
    level: dict[str, pd.Series] = {}
    turned: dict[str, pd.Series] = {}
    easing: dict[str, pd.Series] = {}
    for name in returns.columns:
        if name == cash_id:
            continue
        logged = np.log1p(returns[name].astype(float))
        ready = logged.notna().rolling(sigma_window, min_periods=1).sum().ge(sigma_window)
        filled = logged.fillna(0.0)
        excess = filled - cash_log.reindex(filled.index)
        sigma = filled.rolling(sigma_window).std().shift(1)
        velocity = pd.DataFrame(
            {n: excess.rolling(n).sum() / (sigma * np.sqrt(n)) for n in rulers},
            index=filled.index,
        ).where(ready, axis=0)
        loudness = pd.DataFrame(
            {
                n: _percentile_past(
                    velocity[n].abs().rolling(n).mean().to_numpy(dtype=float),
                    quantile_min,
                )
                for n in rulers
            },
            index=velocity.index,
        )
        weight = loudness.div(loudness.sum(axis=1), axis=0)
        warmup = loudness.isna().any(axis=1) & velocity.notna().all(axis=1)
        weight.loc[warmup] = 1.0 / len(rulers)
        level[name] = (weight * velocity).sum(axis=1, min_count=len(rulers))
        turned[name] = (velocity < 0).mean(axis=1).where(velocity.notna().all(axis=1))
        slow = velocity[long].mean(axis=1, skipna=False)
        easing[name] = (
            (slow > slow.shift(slow_gap)) & (slow.shift(slow_gap) > slow.shift(slow_gap * 2))
        ).where(slow.notna() & slow.shift(slow_gap * 2).notna()).astype(float)
    idx = returns.index
    return (
        pd.DataFrame(level, index=idx),
        pd.DataFrame(turned, index=idx),
        pd.DataFrame(easing, index=idx),
    )


def independent_breadth(
    frontier: pd.DataFrame,
    uni: dict[str, list[str]],
    *,
    frontier_cut: float = 0.5,
    minimum: int = 3,
) -> pd.DataFrame:
    """§3.1 回撤面：按市场成员 F≥0.5 的比例。"""
    out = {}
    for _kind, rep in BROAD.items():
        members = uni.get(_kind, [])
        if not members:
            continue
        f = frontier.reindex(columns=members)
        n = f.notna().sum(axis=1)
        out[rep] = ((f >= frontier_cut).sum(axis=1) / n).where(n >= minimum)
    return pd.DataFrame(out)


def _legs(
    rep: str,
    day,
    hd: pd.DataFrame,
    fd: pd.DataFrame,
    ed: pd.DataFrame,
    b: pd.DataFrame,
    *,
    frontier: float = 0.5,
) -> float | None:
    h, f, e = hd.at[day, rep], fd.at[day, rep], ed.at[day, rep]
    if pd.isna(h) or pd.isna(f) or pd.isna(e):
        return None
    width = float(b.at[day, rep]) if rep in b.columns and day in b.index else float("nan")
    leg1 = (f < frontier) and not (pd.notna(width) and width >= frontier)
    leg2 = (h > 0.0) or bool(e)
    return 0.5 * float(leg1) + 0.5 * float(leg2)


def independent_allocate(
    idx: pd.DatetimeIndex,
    hd: pd.DataFrame,
    fd: pd.DataFrame,
    ed: pd.DataFrame,
    b: pd.DataFrame,
    ret: pd.DataFrame,
    uni: dict[str, list[str]],
    *,
    cash: str = "cash",
    bond: str = "cgb-10y",
    gold: str = "gold",
    frontier: float = 0.5,
    noise: float = 1.0,
    top_n: int = 3,
    hard_stop: float = 0.10,
) -> pd.DataFrame:
    """§3 主循环（独立实现；硬闸门用 v3 triggered，与引擎一致）。"""
    weeks = {pd.Timestamp(d).normalize() for d in decision_dates(idx, "week")}
    px = {c: np.exp(np.log1p(ret[c].fillna(0)).cumsum()).reindex(idx) for c in hd.columns}

    def defense_of(day, cur: str) -> str:
        hb, hg = hd.at[day, bond], hd.at[day, gold]
        if pd.isna(ret.at[day, bond]) and pd.isna(hb):
            return cash
        bond_legs = _legs(bond, day, hd, fd, ed, b, frontier=frontier)
        base = bond if (bond_legs is None or bond_legs > 0.0) else cash
        bond_ref = hb if (base == bond and pd.notna(hb)) else 0.0
        if pd.notna(hg) and hg > 0.0 and hg - bond_ref > noise:
            return gold
        if (
            cur == gold
            and pd.notna(hg)
            and hg > 0.0
            and base == bond
            and pd.notna(hb)
            and hg >= hb
        ):
            return gold
        return base

    def rank(day, cands: list[str]) -> list[str]:
        return sorted(cands, key=lambda c: (-float(hd.at[day, c]) if pd.notna(hd.at[day, c]) else float("-inf"), c))

    mk = {v: k for k, v in BROAD.items()}
    held_rep: str | None = None
    risk = 0.0
    defense = cash
    picks: list[str] = []
    blocked: set[str] = set()
    peak: dict[str, float] = {}
    prev_n = 0
    rows = []

    for day in idx:
        stamp = pd.Timestamp(day).normalize()
        sold_today: set[str] = set()
        for name in list(picks):
            price = float(px[name].at[stamp]) if stamp in px[name].index else float("nan")
            if valid_mark(price):
                peak[name] = price if name not in peak else max(peak[name], price)
            share = fd.at[stamp, name]
            why = None
            if pd.notna(share) and share >= frontier:
                why = "F"
            elif name in peak and valid_mark(price) and triggered(price, peak[name], hard_stop):
                why = "硬闸门"
            if why is None:
                continue
            picks.remove(name)
            blocked.add(name)
            sold_today.add(name)
            peak.pop(name, None)

        if stamp in weeks:
            scores = {rep: _legs(rep, stamp, hd, fd, ed, b, frontier=frontier) for rep in RISK_REPS}
            open_reps = [rep for rep in RISK_REPS if scores[rep] and scores[rep] > 0]
            if held_rep not in open_reps:
                held_rep = max(open_reps, key=lambda c: hd.at[stamp, c]) if open_reps else None
            elif held_rep is not None:
                challenger = max(open_reps, key=lambda c: hd.at[stamp, c])
                if challenger != held_rep and hd.at[stamp, challenger] - hd.at[stamp, held_rep] > noise:
                    held_rep = challenger
            risk = float(scores[held_rep]) if held_rep else 0.0
            if held_rep is None:
                new: list[str] = []
            else:
                kind = mk[held_rep]
                el = [
                    c
                    for c in uni[kind]
                    if c not in blocked
                    and pd.notna(hd.at[stamp, c])
                    and hd.at[stamp, c] > 0
                    and fd.at[stamp, c] < frontier
                ]
                new = rank(stamp, el)[:top_n]
                if not new:
                    if held_rep not in blocked:
                        new = [held_rep]
                    else:
                        new = []
            for name in list(picks):
                if name not in new:
                    peak.pop(name, None)
            picks = list(new)
            if not picks:
                held_rep, risk = None, 0.0
            blocked = set(sold_today)
            defense = defense_of(stamp, defense)
        elif held_rep is not None:
            updated = _legs(held_rep, stamp, hd, fd, ed, b, frontier=frontier)
            if updated is not None and updated < risk:
                risk = float(updated)
            if risk == 0.0:
                for name in list(picks):
                    peak.pop(name, None)
                held_rep, picks = None, []
            else:
                kind = mk[held_rep]
                while len(picks) < top_n:
                    if len(picks) >= prev_n:
                        break
                    el = [
                        c
                        for c in uni[kind]
                        if c not in picks
                        and c not in blocked
                        and pd.notna(hd.at[stamp, c])
                        and hd.at[stamp, c] > 0
                        and fd.at[stamp, c] < frontier
                    ]
                    ranked = rank(stamp, el)
                    if not ranked:
                        break
                    picks.append(ranked[0])
                if not picks:
                    if held_rep not in blocked and pd.notna(fd.at[stamp, held_rep]) and fd.at[stamp, held_rep] < frontier:
                        picks = [held_rep]
                    else:
                        held_rep, risk = None, 0.0
            defense = defense_of(stamp, defense)
        prev_n = len(picks)
        rows.append(
            {
                "t": stamp,
                "market": held_rep or "",
                "risk": risk if held_rep else 0.0,
                "defense": defense,
                "picks": "|".join(picks),
                "blocked": "|".join(sorted(blocked)),
            }
        )
    return pd.DataFrame(rows)


def _same(a, b) -> bool:
    if pd.isna(a) and pd.isna(b):
        return True
    if pd.isna(a) or pd.isna(b):
        return False
    return bool(np.isclose(float(a), float(b), rtol=RTOL, atol=ATOL))


def _pick_dates(index: pd.DatetimeIndex, hd: pd.DataFrame, n: int = 5) -> list[pd.Timestamp]:
    eligible = index[(index >= "2006-01-01") & (index <= "2015-12-31")]
    mask = np.ones(len(eligible), dtype=bool)
    for seq in SEQUENCES:
        if seq not in hd.columns:
            raise KeyError(seq)
        mask &= hd[seq].notna().to_numpy()
    pool = eligible[mask]
    rng = np.random.default_rng(DATE_SEED)
    chosen = sorted(rng.choice(pool.to_numpy(), size=n, replace=False))
    return [pd.Timestamp(d).normalize() for d in chosen]


def main() -> int:
    params = Params()
    m = Markets(load_spec()).get("index", t4=False, allow_substitute=True)
    ret = m.signal.loc["2006-01-01":"2015-12-31"].copy()
    cash_id = m.cash_id
    if cash_id not in ret.columns:
        ret[cash_id] = m.cash.reindex(ret.index).fillna(0.0)

    cls = classes_for(list(m.names), cash_id, class_map())
    uni = {k: sorted(c for c in m.names if cls.get(c) == k and ret[c].notna().any()) for k in BROAD}

    ind_h, ind_f, ind_e = independent_readings(ret, cash_id)
    eng = read_panel(ret, cash_id, params=params)

    spot_dates = _pick_dates(ret.index, ind_h, 5)

    grid = {"H": 0, "F": 0, "E": 0, "miss": []}
    for seq in SEQUENCES:
        for day in spot_dates:
            for key, ind_df, eng_df in (
                ("H", ind_h, eng.H),
                ("F", ind_f, eng.F),
                ("E", ind_e, eng.E),
            ):
                a, b = ind_df.at[day, seq], eng_df.at[day, seq]
                if _same(a, b):
                    grid[key] += 1
                else:
                    grid["miss"].append({"metric": key, "seq": seq, "day": str(day.date()), "ind": a, "eng": b})

    ind_b = independent_breadth(ind_f, uni)
    eng_b = {}
    universe = universe_from_names(list(ret.columns), class_lookup(list(ret.columns), cash_id), params=params)
    for market in universe.markets:
        eng_b[market.representative] = engine_breadth(
            eng.F, market.members, minimum=params.breadth_min, frontier=params.frontier
        )
    eng_b_df = pd.DataFrame(eng_b)

    b_grid = {"match": 0, "miss": []}
    for rep in RISK_REPS:
        for day in spot_dates:
            a = ind_b.at[day, rep] if rep in ind_b.columns else float("nan")
            b = eng_b_df.at[day, rep] if rep in eng_b_df.columns else float("nan")
            if _same(a, b):
                b_grid["match"] += 1
            else:
                b_grid["miss"].append({"rep": rep, "day": str(day.date()), "ind": a, "eng": b})

    ind_state = independent_allocate(ret.index, ind_h, ind_f, ind_e, ind_b, ret, uni)
    eng_alloc = engine_target_weights(ret, universe, params=params)
    eng_state = eng_alloc.state

    hold = {"match": 0, "miss": []}
    for day in spot_dates:
        ir = ind_state[ind_state["t"] == day].iloc[0]
        er = eng_state.loc[day]
        fields = ("market", "risk", "defense", "picks", "blocked")
        ok = True
        detail = {}
        for field in fields:
            iv, ev = ir[field], er[field]
            if field == "risk":
                same = _same(iv, ev)
            else:
                same = str(iv) == str(ev)
            if not same:
                ok = False
                detail[field] = {"ind": iv, "eng": ev}
        if ok:
            hold["match"] += 1
        else:
            hold["miss"].append({"day": str(day.date()), **detail})

    # profile33 边界：硬闸门 <= vs triggered strict
    profile33_boundary_note = (
        "profile33.py 用 PX/hi-1<=-0.10；引擎与独立复算用 triggered(strict<90%)。"
    )

    sold_list_spot = _sold_list_synthetic()

    report = {
        "tip": "6c958d3d70dd0e7d8a0a77d1f404c03ac3827aad",
        "sequences": list(SEQUENCES),
        "dates": [str(d.date()) for d in spot_dates],
        "readings_5x5": {
            "cells_per_metric": 25,
            "H_match": grid["H"],
            "F_match": grid["F"],
            "E_match": grid["E"],
            "total_match": grid["H"] + grid["F"] + grid["E"],
            "total_cells": 75,
            "misses": grid["miss"],
        },
        "breadth_3x5": {
            "match": b_grid["match"],
            "total": 15,
            "misses": b_grid["miss"],
        },
        "holdings_5_dates": hold,
        "sold_list_synthetic": sold_list_spot,
        "notes": {"profile33_hard_gate": profile33_boundary_note},
    }

    text = json.dumps(report, indent=2, ensure_ascii=False)
    OUT.write_text(text + "\n", encoding="utf-8")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(text + "\n", encoding="utf-8")
    print(text)
    ok = not grid["miss"] and not b_grid["miss"] and not hold["miss"] and sold_list_spot["section_3_3_spot_pass"]
    return 0 if ok else 1


def _sold_list_synthetic() -> dict:
    """复刻 test_allocate.test_names_sold_this_week_are_not_bought_back：§3.3 卖后不买回 + 周度清空。"""
    from src.v51.allocate import allocate as eng_allocate
    from src.v51.universe import Market, Universe

    index = pd.bdate_range("2015-06-01", periods=20)
    weeks = list(decision_dates(index, "week"))
    w0, w1, w2, w3 = weeks[:4]
    names = ["m", "a", "b", "c", "d"]
    level = pd.DataFrame(0.2, index=index, columns=names, dtype=float)
    level["a"], level["b"], level["c"], level["d"] = 4.0, 3.0, 2.0, 1.0
    share = pd.DataFrame(0.1, index=index, columns=names, dtype=float)
    slow = pd.DataFrame(0.0, index=index, columns=names, dtype=float)
    sell_a = index[index.get_loc(w0) + 1]
    share.loc[sell_a, "a"] = 0.5
    share.loc[w1, "b"] = 0.5
    prices = pd.DataFrame(100.0, index=index, columns=names, dtype=float)
    universe = Universe((Market("A股", "m", tuple(names)),), bond="cgb-10y", gold="gold", cash="cash")
    eng = eng_allocate(index, level, share, slow, universe, prices=prices)

    def picks(day) -> list[str]:
        text = eng.state.at[day, "picks"]
        return [] if not text else str(text).split("|")

    def blocked(day) -> set[str]:
        text = eng.state.at[day, "blocked"]
        return set() if not text else set(str(text).split("|"))

    rules = {
        "a_sold_on_F_day": "a" not in picks(sell_a),
        "a_on_sold_list_same_day": "a" in blocked(sell_a),
        "a_not_rebought_before_next_weekly_after_w1": "a" not in picks(w1),
        "sold_list_cleared_for_a_by_w2": "a" not in blocked(w2),
        "a_back_in_picks_w2": "a" in picks(w2),
        "weekly_normal_swap_w3": picks(w3) == ["a", "b", "c"],
        "exit_reason_a_is_F": eng.exits[(eng.exits["t"] == sell_a) & (eng.exits["id"] == "a")]["why"].tolist() == ["F"],
    }
    return {
        "section_3_3_spot_pass": all(rules.values()),
        "rules": rules,
    }


if __name__ == "__main__":
    raise SystemExit(main())
