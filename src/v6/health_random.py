"""同结构随机。只写 health-random.csv 和 health-random-summary.json。

冻结 §5.2：四步不变，第 ① 步改为去重后随机取 3 只，同样受准入限制。
1000 次，种子 20261122。百分位和每月跑赢随机中位数的比例沿用
`a_decompose.py` 里对这个种子写出的比较式：路径月均收益、当月中位数，严格大于才算跑赢。
不改已经交付的体检文件。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.report.metrics import monthly_returns
from src.v6.engine import _pick, confidence, mix_monthly, slot
from src.v6.guard import IsolationError, assert_not_after
from src.v6.health import COST, OUT, SEGMENTS
from src.v6.load import load_panels
from src.v6.prior import us_prior
from src.v6.run_design import FRENCH_SHA, PANEL, TAGS, _a_daily, _sha_file, _us_daily
from src.v6.trin import clip_expanding, month_end_mean

SEED = 20261122
TRIALS = 1000
N = 3


def rank_percentile(rule_months: np.ndarray, random_months: np.ndarray) -> float:
    """1000 条路径的月均收益里，严格低于规则月均的比例，单位是百分位。"""
    path_means = random_months.mean(axis=1)
    return float((path_means < float(rule_months.mean())).mean() * 100.0)


def beat_median_share(rule_months: np.ndarray, random_months: np.ndarray) -> float:
    """规则月收益严格高于当月 1000 条中位数的月份比例。"""
    median = np.median(random_months, axis=0)
    return float((rule_months > median).mean())


def _plans(levels, parent, prior, tags, votes_fn, bond, cash):
    """每个月末的去重池、v6 选中的 3 只、股票总仓位、国债或现金。把握 p 用 12−1 领头者。"""
    assert_not_after(levels.index, parent)
    calendar = levels.index
    columns = list(levels.columns)
    tag_of = np.array([tags.get(c, "") for c in columns], dtype=object)
    parent_at = columns.index(parent)
    mask = np.r_[calendar.month[1:] != calendar.month[:-1], True]
    month = levels.loc[calendar[mask]]
    score_frame = month.shift(1) / month.shift(12) - 1
    forward = month.pct_change().shift(-1)
    bond_level = np.exp(np.log1p(bond.fillna(0)).cumsum()).where(bond.notna().cumsum() > 0)
    bond_month = bond_level.loc[calendar[mask]]
    bond_above = (bond_month > bond_month.rolling(10).mean()) & bond_month.notna()
    vote_sum, _n = votes_fn(levels, parent, ["均线", "宽度", "TRIN"])
    above = month > month.rolling(10).mean()
    history = []
    pending_leader = None
    plans = []
    for t, day in enumerate(calendar):
        if not mask[t]:
            continue
        if pending_leader is not None:
            history.append(pending_leader)
            pending_leader = None
        scores = score_frame.loc[day].to_numpy(dtype=float)
        ok = np.isfinite(scores)
        p_value = confidence(history, prior=prior)
        stress = int(vote_sum.get(day.to_period("M"), 0)) >= 2
        held_bond = bool(bond_above.loc[day]) if day in bond_above.index else False
        if not ok.any():
            plans.append({
                "t": t, "pool": np.array([parent_at], dtype=int),
                "v6": np.array([parent_at], dtype=int), "frac": 1.0,
                "bond": held_bond, "fallback": True,
            })
            continue
        raw = _pick(scores, ok, tag_of, N, True)
        pool = np.array(_pick(scores, ok, tag_of, int(ok.sum()), True), dtype=int)
        gate = not bool(above.loc[day].to_numpy()[columns.index(parent)])
        allowed = ok & (scores > 0) if gate else ok
        v6 = np.array(_pick(scores, allowed, tag_of, N, True), dtype=int)
        frac = p_value if stress else 1.0
        nxt = forward.loc[day].to_numpy(dtype=float)
        if stress and raw and np.isfinite(nxt[raw]).all():
            pending_leader = float(np.mean(nxt[raw]))
        plans.append({
            "t": t, "pool": pool, "v6": v6, "frac": float(frac),
            "bond": held_bond, "fallback": False,
        })
    return plans


def _targets(plans, picks, width: int) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """picks[m] 形状 (路径数, 选中个数)，不足的位置是 -1。fallback 时忽略 picks。"""
    out = []
    for plan, chosen in zip(plans, picks):
        n_paths = chosen.shape[0]
        target = np.zeros((n_paths, width))
        if plan["fallback"]:
            target[:, plan["pool"][0]] = 1.0
        else:
            for k in range(chosen.shape[1]):
                idx = chosen[:, k]
                valid = idx >= 0
                rows = np.flatnonzero(valid)
                target[rows, idx[valid]] = plan["frac"] / N
        left = 1.0 - target.sum(axis=1)
        if plan["bond"]:
            bond_w, cash_w = left, np.zeros(n_paths)
        else:
            bond_w, cash_w = np.zeros(n_paths), left
        out.append((target, bond_w, cash_w))
    return out


def _simulate(levels, bond, cash, plans, picks, cost: float) -> np.ndarray:
    calendar = levels.index
    returns = levels.pct_change().fillna(0).to_numpy()
    bond_ret = bond.reindex(calendar).fillna(0).to_numpy()
    cash_ret = cash.reindex(calendar).to_numpy()
    if np.isnan(cash_ret).any():
        raise IsolationError("现金收益没有盖住日历")
    width = returns.shape[1]
    n_paths = picks[0].shape[0]
    weight = np.zeros((n_paths, width))
    bond_w = np.zeros(n_paths)
    cash_w = np.ones(n_paths)
    out = np.zeros((n_paths, len(calendar)))
    pending = None
    plan_at = {plan["t"]: i for i, plan in enumerate(plans)}
    targets = _targets(plans, picks, width)
    mask = np.r_[calendar.month[1:] != calendar.month[:-1], True]
    for t in range(len(calendar)):
        if pending is not None:
            target, target_bond, target_cash = pending
            traded = np.abs(target - weight).sum(axis=1) + np.abs(target_bond - bond_w)
            fee = cost * traded
            weight, bond_w, cash_w = target, target_bond, target_cash
            pending = None
        else:
            fee = 0.0
        gross = (weight * returns[t]).sum(axis=1) + bond_w * bond_ret[t] + cash_w * cash_ret[t]
        out[:, t] = (1.0 + gross) * (1.0 - fee) - 1.0
        growth = 1.0 + gross
        weight = weight * (1.0 + returns[t]) / growth[:, None]
        bond_w = bond_w * (1.0 + bond_ret[t]) / growth
        cash_w = cash_w * (1.0 + cash_ret[t]) / growth
        if mask[t]:
            pending = targets[plan_at[t]]
    assert_not_after(calendar, "随机")
    return out


def _draw(plans, rng: np.random.Generator, trials: int) -> list[np.ndarray]:
    picks = []
    for plan in plans:
        chosen = np.full((trials, N), -1, dtype=int)
        if plan["fallback"]:
            picks.append(chosen)
            continue
        pool = plan["pool"]
        if len(pool) <= N:
            chosen[:, :len(pool)] = pool
        else:
            for i in range(trials):
                chosen[i] = rng.choice(pool, size=N, replace=False)
        picks.append(chosen)
    return picks


def _v6_picks(plans) -> list[np.ndarray]:
    picks = []
    for plan in plans:
        chosen = np.full((1, N), -1, dtype=int)
        if not plan["fallback"]:
            chosen[0, :len(plan["v6"])] = plan["v6"]
        picks.append(chosen)
    return picks


def _month_matrix(daily: np.ndarray, index: pd.DatetimeIndex) -> tuple[pd.PeriodIndex, np.ndarray]:
    periods = index.to_period("M")
    labels = pd.PeriodIndex(periods.unique(), freq="M")
    matrix = np.empty((daily.shape[0], len(labels)))
    for i, period in enumerate(labels):
        block = daily[:, periods == period]
        matrix[:, i] = np.prod(1.0 + block, axis=1) - 1.0
    return labels, matrix


def _rows(rule: pd.Series, random_daily: np.ndarray) -> list[dict]:
    labels, matrix = _month_matrix(random_daily, rule.index)
    rule_months = monthly_returns(rule).reindex(labels)
    if rule_months.isna().any():
        raise IsolationError("规则的月收益没有盖住随机路径")
    rows = []
    for name, start, end in SEGMENTS:
        start_p, end_p = pd.Period(start, "M"), pd.Period(end, "M")
        keep = np.array([(start_p <= period <= end_p) for period in labels])
        if not keep.any():
            raise IsolationError(f"{name} 没有月份")
        rule_block = rule_months.to_numpy()[keep]
        random_block = matrix[:, keep]
        rows.append({
            "segment": name,
            "seed": SEED,
            "trials": TRIALS,
            "n_months": int(keep.sum()),
            "percentile": rank_percentile(rule_block, random_block),
            "beat_random_median_share": beat_median_share(rule_block, random_block),
        })
    return rows


def run() -> dict:
    panels = load_panels()
    opaque = Path("/opt/cursor/artifacts/french-49/49_Industry_Portfolios.csv")
    csv_sha = _sha_file(opaque) if opaque.exists() else None
    if csv_sha != FRENCH_SHA or not PANEL.exists():
        raise IsolationError("美股起点经验不在已登记的面板上，随机停")
    prior = us_prior(PANEL)
    bond, cash = panels["bond"], panels["cash"]
    votes = panels["votes"]
    saved = {key: panels["trin"][key].copy() for key in ("csi300", "SPX")}
    panels["trin"]["csi300"] = month_end_mean(clip_expanding(_a_daily(panels)))
    panels["trin"]["SPX"] = month_end_mean(clip_expanding(_us_daily(panels)))
    try:
        a_plans = _plans(panels["A"], "csi300", None, TAGS["a"], votes, bond, cash)
        u_plans = _plans(panels["US"], "SPX", prior, TAGS["us"], votes, bond, cash)
        a_check = _simulate(panels["A"], bond, cash, a_plans, _v6_picks(a_plans), COST)[0]
        u_check = _simulate(panels["US"], bond, cash, u_plans, _v6_picks(u_plans), COST)[0]
        a_slot, _, _ = slot(panels["A"], "csi300", N, None, TAGS["a"], "v6", COST, votes, bond, cash)
        u_slot, _, _ = slot(panels["US"], "SPX", N, prior, TAGS["us"], "v6", COST, votes, bond, cash)
        gap_a = float(np.max(np.abs(a_check - a_slot.to_numpy())))
        gap_u = float(np.max(np.abs(u_check - u_slot.to_numpy())))
        if gap_a > 1e-8 or gap_u > 1e-8:
            raise IsolationError(f"随机引擎和 v6 引擎不一致：A {gap_a}，美股 {gap_u}")
        rng = np.random.default_rng(SEED)
        a_draw = _draw(a_plans, rng, TRIALS)
        u_draw = _draw(u_plans, rng, TRIALS)
        a_paths = _simulate(panels["A"], bond, cash, a_plans, a_draw, COST)
        u_paths = _simulate(panels["US"], bond, cash, u_plans, u_draw, COST)
        mixed = np.empty_like(a_paths)
        for i in range(TRIALS):
            mixed[i] = mix_monthly(
                pd.Series(a_paths[i], index=panels["A"].index),
                pd.Series(u_paths[i], index=panels["US"].index),
                COST,
            ).to_numpy()
        rule = mix_monthly(a_slot, u_slot, COST)
        assert_not_after(rule.index, "随机规则")
        if rule.index.max() > pd.Timestamp("2015-12-31"):
            raise IsolationError("随机结果晚于 2015-12-31")
        rows = _rows(rule, mixed)
    finally:
        panels["trin"]["csi300"] = saved["csi300"]
        panels["trin"]["SPX"] = saved["SPX"]
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / "health-random.csv", index=False)
    summary = {
        "seed": SEED,
        "trials": TRIALS,
        "segments": rows,
        "first": rule.index.min().date().isoformat(),
        "last": rule.index.max().date().isoformat(),
        "engine_gap": {"A": gap_a, "US": gap_u},
        "formula": {
            "percentile": "100 ×（1000 条路径的月均收益严格低于规则月均收益的比例）。月收益是该自然月日收益连乘减 1，函数 src/report/metrics.py monthly_returns。",
            "beat_random_median_share": "规则月收益严格高于当月 1000 条中位数的月份比例。",
            "source": "比较式与 scripts/preflight/a_decompose.py 对种子 20261122 的写法相同。结构按冻结 §5.2，不是那份只看挑选层的脚本。",
        },
        "structure": "两个名额都把第①步换成去重后的随机 3 只。准入是 12−1 有限。去重沿用 _pick：非空标签只留 12−1 最高的一个。把握 p 仍用 12−1 领头者，与主规则同一条。每月末 60/40，单边 0.2%。",
        "draw_order": "一个 Generator(20261122)。按月末先后，先抽 A 股池，再抽美股池。池子不超过 3 只时全持有，不消耗随机数。",
        "positive_filter": "§5.2 写的是同样受准入限制。正收益过滤写在第①步的排序里，本随机不套用。母指数跌破均线时，随机池仍是全部已准入且去重后的候选。",
        "inputs": {
            "french_sha256": csv_sha,
            "french_panel": str(PANEL.relative_to(OUT.parents[1])),
            "loader_sha256": panels["loader_sha256"],
            "date_cap": "2015-12-31",
            "trin": "expanding99",
        },
        "command": ".venv/bin/python -m src.v6.health_random",
    }
    (OUT / "health-random-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"rows": len(rows), "last": summary["last"]}


def main() -> None:
    print(json.dumps(run(), ensure_ascii=False))


if __name__ == "__main__":
    main()
