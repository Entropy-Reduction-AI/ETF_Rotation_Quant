"""§5.2 同结构随机，以及体检第 2–4 节。不覆盖已锁定的 d48-health.json。

随机：准入和去重与 v6 相同，去重后的名单里随机取 3 只。把握 p 仍用 12−1 去重后的前 3，不随随机持仓改变。
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_d45 import OFFICIAL, mix_monthly  # noqa: E402
from run_d47_health import (  # noqa: E402
    A_SPEC,
    US_SPEC,
    bars_frame,
    build_levels,
    current_allocation,
    k2a_book,
    load_fx,
    load_market,
    require_cutoff,
    signed_peer,
    sleeve_books,
    total_return_benchmarks,
)
from src.report.metrics import ann_vol, cagr, max_drawdown  # noqa: E402
from src.v4.scorecard.core import (  # noqa: E402
    any_start,
    any_start_summary,
    capture_ratios,
    classify_months,
    growth_nav,
    load_h00300,
)
from v6ind.d45_engine import month_end_mask, trin_from_prices, votes  # noqa: E402
from v6ind.d45_french import confidence, us_prior, value_weighted_market  # noqa: E402
from v6ind.load import connect_readonly  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
SEED = 20261122
RUNS = 1000
COST = 0.002
PERIODS = {
    "2006–10": ("2006-01-01", "2010-12-31"),
    "2011–15": ("2011-01-01", "2015-12-31"),
    "2006–15": ("2006-01-01", "2015-12-31"),
}
CRASHES = (
    ("2008", "2007-10-01", "2009-06-30"),
    ("2015", "2015-05-01", "2015-12-31"),
)


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def deduped(score: np.ndarray, ok: np.ndarray, tag: np.ndarray) -> list[int]:
    ranked: list[int] = []
    used: set[str] = set()
    order = np.argsort(-np.where(ok, score, -np.inf))
    for pos in order:
        if not ok[int(pos)]:
            break
        label = tag[int(pos)]
        if label and label in used:
            continue
        ranked.append(int(pos))
        if label:
            used.add(str(label))
    return ranked


def prepare(levels: pd.DataFrame, parent: str, vote: pd.Series, bond: pd.Series, cash: pd.Series,
            tags: dict[str, str], prior: list[float] | None) -> list[dict]:
    """与 run_slot 同一套月末决定。持仓名单留空，由调用方填。"""
    calendar = levels.index
    mask = month_end_mask(calendar)
    month_level = levels.loc[mask]
    momentum = month_level.shift(1) / month_level.shift(12) - 1.0
    above = month_level > month_level.rolling(10).mean()
    forward = month_level.pct_change().shift(-1)
    bond_level = np.exp(np.log1p(bond.fillna(0.0)).cumsum()).where(bond.notna().cumsum() > 0)
    bond_month = bond_level.loc[mask]
    bond_above = (bond_month > bond_month.rolling(10).mean()) & bond_month.notna()
    tag = np.array([tags.get(column, "") for column in levels.columns], dtype=object)
    parent_at = list(levels.columns).index(parent)
    history: list[float] = []
    queued: float | None = None
    plans = []
    for today, stamp in enumerate(calendar):
        if not mask[today]:
            continue
        if queued is not None:
            history.append(queued)
            queued = None
        score = momentum.loc[stamp].to_numpy(dtype=float)
        ok = np.isfinite(score)
        belief = confidence(history, prior)
        stressed = int(vote.get(stamp.to_period("M"), 0)) >= 2
        gate = not bool(above.loc[stamp].iloc[parent_at])
        leaders = deduped(score, ok, tag)[:3]
        nxt = forward.loc[stamp].to_numpy(dtype=float)
        if stressed and leaders and np.isfinite(nxt[leaders]).all():
            queued = float(np.mean(nxt[leaders]))
        tradable = ok & (score > 0) if gate else ok
        pool = deduped(score, tradable, tag) if ok.any() else []
        bond_ok = bool(bond_above.loc[stamp]) if stamp in bond_above.index else False
        plans.append({
            "today": today,
            "stamp": stamp,
            "parent": not ok.any(),
            "parent_at": parent_at,
            "pool": pool,
            "share": (belief if stressed else 1.0) / 3.0,
            "bond_ok": bond_ok,
        })
    return plans


def simulate(levels: pd.DataFrame, bond: pd.Series, cash: pd.Series, plans: list[dict],
             picks: dict[pd.Timestamp, np.ndarray], cost: float) -> np.ndarray:
    """picks[stamp] 形状 (路径数, 3)，不足用 -1。返回 (路径数, 天数) 日收益。"""
    calendar = levels.index
    asset = levels.pct_change().fillna(0.0).to_numpy(dtype=float)
    bond_ret = bond.reindex(calendar).fillna(0.0).to_numpy(dtype=float)
    cash_ret = cash.reindex(calendar).fillna(0.0).to_numpy(dtype=float)
    sample = next(iter(picks.values()))
    n_runs, _width = sample.shape
    names = asset.shape[1]
    held = np.zeros((n_runs, names))
    bond_weight = np.zeros(n_runs)
    cash_weight = np.ones(n_runs)
    out = np.zeros((n_runs, len(calendar)))
    pending = None
    plan_at = {plan["today"]: plan for plan in plans}
    for today in range(len(calendar)):
        fee = np.zeros(n_runs)
        if pending is not None:
            target, target_bond, target_cash = pending
            traded = np.abs(target - held).sum(axis=1) + np.abs(target_bond - bond_weight)
            fee = cost * traded
            held = target
            bond_weight = target_bond
            cash_weight = target_cash
            pending = None
        gain = held @ asset[today] + bond_weight * bond_ret[today] + cash_weight * cash_ret[today]
        out[:, today] = (1.0 + gain) * (1.0 - fee) - 1.0
        gross = 1.0 + gain
        held = held * (1.0 + asset[today]) / gross[:, None]
        bond_weight = bond_weight * (1.0 + bond_ret[today]) / gross
        cash_weight = cash_weight * (1.0 + cash_ret[today]) / gross
        plan = plan_at.get(today)
        if plan is None:
            continue
        if plan["parent"]:
            target = np.zeros((n_runs, names))
            target[:, plan["parent_at"]] = 1.0
        else:
            chosen = picks[plan["stamp"]]
            target = np.zeros((n_runs, names))
            for slot in range(chosen.shape[1]):
                column = chosen[:, slot]
                valid = column >= 0
                target[np.flatnonzero(valid), column[valid]] = plan["share"]
        left = 1.0 - target.sum(axis=1)
        if plan["bond_ok"]:
            pending = (target, left, np.zeros(n_runs))
        else:
            pending = (target, np.zeros(n_runs), left)
    return out


def top_picks(plans: list[dict], n_runs: int) -> dict[pd.Timestamp, np.ndarray]:
    picks = {}
    for plan in plans:
        chosen = np.full((n_runs, 3), -1, dtype=int)
        for slot, name in enumerate(plan["pool"][:3]):
            chosen[:, slot] = name
        picks[plan["stamp"]] = chosen
    return picks


def random_picks(plans: list[dict], n_runs: int, rng: np.random.Generator) -> dict[pd.Timestamp, np.ndarray]:
    """每个月末、每条路径，对去重后的池子做一次 permutation，取前 3 个。池子为空则不抽。"""
    picks = {}
    for plan in plans:
        pool = plan["pool"]
        chosen = np.full((n_runs, 3), -1, dtype=int)
        if pool:
            order = np.vstack([rng.permutation(len(pool)) for _ in range(n_runs)])
            take = min(3, len(pool))
            for slot in range(take):
                chosen[:, slot] = np.asarray(pool, dtype=int)[order[:, slot]]
        picks[plan["stamp"]] = chosen
    return picks


def annual_block(daily: np.ndarray, index: pd.DatetimeIndex, start: str, end: str) -> np.ndarray:
    mask = (index >= start) & (index <= end)
    block = daily[:, mask]
    nav = np.prod(1.0 + block, axis=1)
    years = int(mask.sum()) / 252.0
    return nav ** (1.0 / years) - 1.0


def month_frame(daily: np.ndarray, index: pd.DatetimeIndex) -> pd.DataFrame:
    frame = pd.DataFrame(daily.T, index=index)
    return (1.0 + frame).groupby(index.to_period("M")).prod() - 1.0


def percentile(random_annual: np.ndarray, rule_annual: float) -> float:
    """100 次里有多少次年化小于等于规则。规则最好时是 100。"""
    return round(100.0 * float(np.mean(random_annual <= rule_annual)), 4)


def win_share(rule_month: pd.Series, random_month: pd.DataFrame, start: str, end: str) -> dict:
    left = pd.Timestamp(start).to_period("M")
    right = pd.Timestamp(end).to_period("M")
    keep = (random_month.index >= left) & (random_month.index <= right)
    block = random_month.loc[keep]
    rule = rule_month.reindex(block.index)
    median = block.median(axis=1)
    compared = rule.notna()
    beats = rule[compared] > median[compared]
    return {
        "months": int(compared.sum()),
        "win_share": round(float(beats.mean()), 6) if len(beats) else None,
    }


def series_stats(rets: pd.Series, benchmark: pd.Series) -> dict:
    block = rets.dropna()
    bench = benchmark.reindex(block.index).fillna(0.0)
    capture = capture_ratios(block, bench)
    return {
        "annual_pct": round(cagr(block) * 100.0, 6),
        "maxdd_pct": round(max_drawdown(block)["max_drawdown"] * 100.0, 6),
        "vol_pct": round(ann_vol(block) * 100.0, 6),
        "up_capture": capture["up_capture"],
        "down_capture": capture["down_capture"],
        "up_months": capture["up_months"],
        "down_months": capture["down_months"],
        "days": int(len(block)),
    }


def crash_from_peak(rets: pd.Series, levels: pd.Series, start: str, end: str) -> dict:
    window = levels.loc[start:end].dropna()
    if window.empty:
        raise SystemExit(f"沪深300 在 {start} 至 {end} 没有收盘")
    peak = pd.Timestamp(window.idxmax())
    after = rets.loc[(rets.index > peak) & (rets.index <= end)].dropna()
    path = (1.0 + after).cumprod()
    if path.empty:
        lowest, trough = 0.0, str(peak.date())
    else:
        trough_at = path.idxmin()
        lowest = float(path.min() - 1.0)
        if lowest > 0:
            lowest, trough = 0.0, str(peak.date())
        else:
            trough = str(pd.Timestamp(trough_at).date())
    return {
        "window": [start, end],
        "h00300_peak": str(peak.date()),
        "h00300_peak_close_is_window_max": True,
        "lowest_pct": round(lowest * 100.0, 6),
        "trough": trough,
    }


def regime_table(rets: pd.Series, benchmark: pd.Series, states: pd.Series) -> list[dict]:
    strategy_month = (1.0 + rets).resample("ME").prod() - 1.0
    bench_month = (1.0 + benchmark.reindex(rets.index).fillna(0.0)).resample("ME").prod() - 1.0
    daily_excess = (rets - benchmark.reindex(rets.index).fillna(0.0))
    rows = []
    for name in ("牛市", "回调", "熊市", "反弹"):
        marked = states[states == name]
        months = strategy_month.reindex(marked.index).dropna()
        bench = bench_month.reindex(months.index)
        wins = int((months > bench).sum())
        total = float(daily_excess[daily_excess.index.to_period("M").isin(months.index.to_period("M"))].sum())
        rows.append({
            "state": name,
            "months": int(len(months)),
            "win_months": wins,
            "excess_sum_pp": round(total * 100.0, 6),
        })
    return rows


def anystart_vs_benchmark(rets: pd.Series, benchmark: pd.Series) -> list[dict]:
    index = rets.dropna().index
    navs = {
        "v6": growth_nav(rets, index),
        "基准": growth_nav(benchmark.reindex(index).fillna(0.0), index),
    }
    tables = any_start(navs, strategy="v6", horizons=(1, 3, 5))
    summary = any_start_summary(tables, strategy="v6")
    rows = []
    for _, row in summary.iterrows():
        rows.append({
            "years": int(row["years"]),
            "n": int(row["n"]),
            "win_pct": None if pd.isna(row["win_pct"]) else int(row["win_pct"]),
            "median_excess_pp": row["median_excess_pp"],
            "worst_excess_pp": row["worst_excess_pp"],
            "worst_start": row["worst_start"],
        })
    return rows


def main() -> None:
    if not OFFICIAL.exists():
        raise SystemExit(f"缺少已允许的 French 文件 {OFFICIAL}")
    con = connect_readonly(ROOT / "data" / "market.sqlite")
    codes = sorted({row[1] for row in A_SPEC} | {row[0] for row in US_SPEC})
    raw = bars_frame(con, codes)
    fx_rows = load_fx(con)
    con.close()
    fx = pd.Series([value for _day, value in fx_rows], index=pd.to_datetime([day for day, _value in fx_rows]))
    fx = fx[~fx.index.duplicated(keep="last")].sort_index()
    require_cutoff(fx.index, "汇率")
    frame = load_market()
    bond = frame["cgb-10y"].reindex(frame.index)
    cash = frame["cash"].reindex(frame.index)
    levels_a, amounts_a = build_levels(raw, A_SPEC, frame.index, None)
    levels_u, _amounts_u = build_levels(raw, US_SPEC, frame.index, fx)
    tags_a = {row[0]: row[3] for row in A_SPEC}
    tags_u = {row[0]: row[3] for row in US_SPEC}
    prior = us_prior(value_weighted_market(OFFICIAL.read_text(errors="replace")))
    us_prices, us_amounts = [], []
    for code in ("XLK", "XLV", "XLE", "XLY", "XLP", "XLF", "XLI", "XLB", "XLU"):
        close = raw[code]["close"]
        close = close[close > 0]
        close = close[~close.index.duplicated(keep="last")].sort_index()
        volume = raw[code]["volume"].reindex(close.index)
        us_prices.append(close.rename(code))
        us_amounts.append((close * volume).where(lambda values: values > 0).rename(code))
    us_px = pd.concat(us_prices, axis=1).sort_index()
    us_am = pd.concat(us_amounts, axis=1).reindex(us_px.index)
    books, _logs = sleeve_books(
        levels_a, amounts_a, levels_u, us_px, us_am, bond, cash, tags_a, tags_u, prior, "full")
    vote_note = "full 与 expanding 在已锁定的 d48 闸门上相同；随机沿用 full 这一套票。"
    trin_columns = [name for name in levels_a.columns if name.startswith("allshare-") or name.startswith("theme-")
                    or name in {"csi500", "csi1000", "chinext"}]
    vote_a = votes(levels_a, "csi300", trin_from_prices(levels_a[trin_columns], amounts_a[trin_columns], clip="full"))
    vote_u = votes(levels_u, "SPX", trin_from_prices(us_px, us_am, clip="full"))
    plans_a = prepare(levels_a, "csi300", vote_a, bond, cash, tags_a, None)
    plans_u = prepare(levels_u, "SPX", vote_u, bond, cash, tags_u, prior)
    check_a = simulate(levels_a, bond, cash, plans_a, top_picks(plans_a, 1), COST)[0]
    check_u = simulate(levels_u, bond, cash, plans_u, top_picks(plans_u, 1), COST)[0]
    v6_a = books["v6"]["a"].to_numpy(dtype=float)
    v6_u = books["v6"]["us"].to_numpy(dtype=float)
    if not np.allclose(check_a, v6_a, atol=1e-10) or not np.allclose(check_u, v6_u, atol=1e-10):
        raise SystemExit(
            f"随机引擎在固定取前 3 时与 v6 不一致：A {np.max(np.abs(check_a - v6_a))} 美 {np.max(np.abs(check_u - v6_u))}")
    rng = np.random.default_rng(SEED)
    random_a = simulate(levels_a, bond, cash, plans_a, random_picks(plans_a, RUNS, rng), COST)
    random_u = simulate(levels_u, bond, cash, plans_u, random_picks(plans_u, RUNS, rng), COST)
    # 每月末 60/40。两条名额的日收益按路径配对后逐路径再平衡。
    mixed = np.vstack([
        mix_monthly(pd.Series(random_a[i], index=frame.index), pd.Series(random_u[i], index=frame.index), COST).to_numpy()
        for i in range(RUNS)
    ])
    v6 = mix_monthly(books["v6"]["a"], books["v6"]["us"], COST)
    index = frame.index
    summary = {}
    annual_rows = []
    sleeves = {
        "组合": (mixed, v6.to_numpy(dtype=float)),
        "A股": (random_a, v6_a),
        "美股": (random_u, v6_u),
    }
    for label, (start, end) in PERIODS.items():
        block = {}
        for name, (sample, rule) in sleeves.items():
            sample_annual = annual_block(sample, index, start, end)
            rule_annual = float(annual_block(rule.reshape(1, -1), index, start, end)[0])
            sample_month = month_frame(sample, index)
            rule_month = month_frame(rule.reshape(1, -1), index).iloc[:, 0]
            block[name] = {
                "v6_annual_pct": round(rule_annual * 100.0, 6),
                "percentile": percentile(sample_annual, rule_annual),
                "monthly": win_share(rule_month, sample_month, start, end),
                "random_annual_median_pct": round(float(np.median(sample_annual)) * 100.0, 6),
            }
            for run, value in enumerate(sample_annual):
                annual_rows.append({
                    "run": run,
                    "sleeve": name,
                    "period": label,
                    "annual_pct": round(float(value) * 100.0, 6),
                })
        summary[label] = block
    benchmarks = total_return_benchmarks()
    continuity = mix_monthly(books["cont"]["a"], books["v6"]["us"], COST)
    k2a = k2a_book(frame)
    peers = {
        "A1": signed_peer(ROOT / "results/v4/r5/design/A1/index/net.csv"),
        "A2": signed_peer(ROOT / "results/v4/r5/design/A2/index/net.csv"),
    }
    try:
        current = current_allocation()
    except Exception as exc:  # noqa: BLE001
        current = {"status": "stopped", "reason": str(exc)}
    h00300 = load_h00300(ROOT / "data" / "market.sqlite", "2015-12-31")
    require_cutoff(h00300.index, "沪深300")
    states = classify_months(h00300)
    bench = benchmarks["BM-主"]
    series_map = {
        "v6": v6,
        "连续性版": continuity,
        "A1": peers["A1"],
        "A2": peers["A2"],
        "K2A真实月末": k2a,
        "BM-主": bench,
        "BM-同仓位": benchmarks["BM-同仓位"],
    }
    if current.get("status") == "ok":
        from src.portfolio.config import load_config
        from src.portfolio.replicate import _haven_returns, daily_book, load_haven_closes
        # current_allocation already returned stats, not the daily series. Recompute the book
        # only if the function stored lines. The daily series is not returned. Call the same
        # path by reading the panel already built under /tmp.
        panel = Path("/tmp/v6-d47-pkg/panel-2015-12-31.sqlite")
        if panel.exists():
            import sqlite3
            uri = f"{panel.resolve().as_uri()}?mode=ro"
            con = sqlite3.connect(uri, uri=True)
            try:
                prices = pd.read_sql_query(
                    "SELECT date, container, close, data_hole FROM panel WHERE date <= '2015-12-31'", con)
            finally:
                con.close()
            prices["date"] = pd.to_datetime(prices["date"])
            prices = prices.loc[prices["data_hole"] == 0]
            wide = prices.pivot(index="date", columns="container", values="close").sort_index()
            require_cutoff(wide.index, "现行配置")
            cfg = load_config()
            state = pd.Series(1, index=wide.groupby(wide.index.to_period("M")).tail(1).index)
            haven = load_haven_closes(ROOT / "data" / "market.sqlite", cfg.haven_code, pd.Timestamp("2015-12-31"))
            series_map["现行配置"] = daily_book(wide, state, cfg, _haven_returns(wide.index, haven, cfg.cash_daily))
    windowed = {name: series.loc["2006-01-01":"2015-12-31"].dropna() for name, series in series_map.items()}
    character = {name: series_stats(series, bench.reindex(series.index).fillna(0.0)) for name, series in windowed.items()}
    crashes = {
        name: [crash_from_peak(series, h00300, start, end) for _label, start, end in CRASHES]
        for name, series in windowed.items()
    }
    regimes = {name: regime_table(series, bench, states) for name, series in windowed.items()}
    starts = {name: anystart_vs_benchmark(series, bench) for name, series in windowed.items()}
    payload = {
        "seed": SEED,
        "runs": RUNS,
        "code_sha256": {
            "run_d48_random.py": file_sha(Path(__file__)),
            "d45_engine.py": file_sha(HERE / "v6ind" / "d45_engine.py"),
        },
        "rule": "去重后随机取 3；准入与 v6 相同；p 用 12−1 去重前 3；每月末 60/40；单边 0.2%",
        "vote_note": vote_note,
        "top3_matches_v6": True,
        "random": summary,
        "character": character,
        "crash": crashes,
        "regimes": regimes,
        "anystart": starts,
        "current_allocation": {key: value for key, value in current.items() if key != "lines"},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    random_path = OUT / "d48-random.json"
    extra_path = OUT / "d48-health-extra.json"
    csv_path = OUT / "d48-random-annuals.csv"
    random_path.write_text(json.dumps(
        {key: payload[key] for key in ("seed", "runs", "code_sha256", "rule", "vote_note", "top3_matches_v6", "random")},
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    extra_path.write_text(json.dumps(
        {key: payload[key] for key in ("character", "crash", "regimes", "anystart", "current_allocation")},
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    pd.DataFrame(annual_rows).to_csv(csv_path, index=False)
    print(random_path)
    print(extra_path)
    print(csv_path)


if __name__ == "__main__":
    main()
