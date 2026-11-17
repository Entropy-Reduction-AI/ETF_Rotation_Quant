"""Reviewer 独立实现 D38 合成行情 K0–K2（不引用 scripts/preflight）。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[4]
RAW_HISTORY = REPO / "data/research/long-history/raw"

TRADING_DAYS = 252
MONTH_DAYS = 21
WEEK_DAYS = 5
WARMUP = TRADING_DAYS
BOND_ANNUAL = 0.03
LEG_COST = 0.001
DEFAULT_SEED = 20261117
US_WEIGHT = 0.30


@dataclass(frozen=True)
class Segment:
    days: int
    drift_a: float
    drift_us: float
    vol_a: float
    vol_us: float


def _annual_to_daily_log(mu: float) -> float:
    return np.log1p(mu) / TRADING_DAYS


def _total_return_to_annual(r: float, days: int) -> float:
    return (1 + r) ** (TRADING_DAYS / days) - 1


def load_paired_noise() -> Tuple[np.ndarray, float]:
    frames = {}
    for key, fname in (("A", "^HSI.csv"), ("US", "^GSPC.csv")):
        px = pd.read_csv(RAW_HISTORY / fname, parse_dates=["date"]).set_index("date")["close"]
        frames[key] = px[(px.index >= "1987-01-01") & (px.index <= "2003-06-30")]
    paired = pd.DataFrame(frames).dropna()
    log_ret = np.log(paired).diff().dropna()
    z = (log_ret - log_ret.mean()) / log_ret.std()
    return z[["A", "US"]].to_numpy(), float(log_ret.corr().iloc[0, 1])


class NoiseSampler:
    def __init__(self, z: np.ndarray, seed: int):
        self._z = z
        self._rng = np.random.default_rng(seed)

    def sample(self, n_paths: int, n_days: int) -> np.ndarray:
        blocks = int(np.ceil(n_days / 20))
        starts = self._rng.integers(0, len(self._z) - 20, size=(n_paths, blocks))
        idx = (starts[:, :, None] + np.arange(20)).reshape(n_paths, -1)[:, :n_days]
        return self._z[idx]


def compose_paths(segments: Sequence[Segment], sampler: NoiseSampler, n_paths: int) -> np.ndarray:
    chunks: List[np.ndarray] = []
    for seg in segments:
        noise = sampler.sample(n_paths, seg.days)
        noise = noise - noise.mean(axis=1, keepdims=True)
        sig = np.array([seg.vol_a, seg.vol_us]) / np.sqrt(TRADING_DAYS)
        drift = np.array([_annual_to_daily_log(seg.drift_a), _annual_to_daily_log(seg.drift_us)])
        chunks.append(drift + noise * sig)
    return np.concatenate(chunks, axis=1)


def warmup(vol: float = 0.18) -> Segment:
    return Segment(WARMUP, 0.08, 0.08, vol, vol)


SCENARIOS: Dict[str, List[Segment]] = {
    "慢牛": [warmup(0.15), Segment(3 * TRADING_DAYS, 0.15, 0.15, 0.15, 0.15)],
    "急跌": [
        warmup(0.15),
        Segment(TRADING_DAYS, 0.15, 0.15, 0.15, 0.15),
        Segment(20, _total_return_to_annual(-0.30, 20), _total_return_to_annual(-0.30, 20), 0.40, 0.40),
        Segment(120, 0.0, 0.0, 0.25, 0.25),
    ],
    "V型反转": [
        warmup(0.18),
        Segment(20, _total_return_to_annual(-0.30, 20), _total_return_to_annual(-0.30, 20), 0.40, 0.40),
        Segment(60, _total_return_to_annual(1 / 0.7 - 1, 60), _total_return_to_annual(1 / 0.7 - 1, 60), 0.35, 0.35),
        Segment(120, 0.10, 0.10, 0.20, 0.20),
    ],
}


def simulate_structure(
    log_returns: np.ndarray,
    structure: str,
    us_weight: float = US_WEIGHT,
    vol_short: int = 20,
    vol_band: float = 0.10,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, np.ndarray], np.ndarray]:
    """log_returns: (paths, days, 2). 返回净值、股票敞口、换手字典、一月内保险翻回次数。"""
    n_paths, horizon, _ = log_returns.shape
    simple = np.expm1(log_returns)
    bond_daily = (1 + BOND_ANNUAL) ** (1 / TRADING_DAYS) - 1
    prices = np.exp(np.cumsum(log_returns, axis=1))
    base = np.array([1 - us_weight, us_weight])

    leg_on = np.ones((n_paths, 2))
    leg_frac = np.ones((n_paths, 2))
    weights = np.zeros((n_paths, 3))
    weights[:, :2] = base
    nav = np.ones(n_paths)
    nav_series = np.empty((n_paths, horizon))
    exposure = np.empty((n_paths, horizon))
    turns = {k: np.zeros(n_paths) for k in ("再平衡", "保险切换", "波动调仓")}
    flip_count = np.zeros(n_paths)
    last_flip = np.full((n_paths, 2), -10**6)
    prev_on = leg_on.copy()

    for t in range(horizon):
        gross = 1 + weights[:, 0] * simple[:, t, 0] + weights[:, 1] * simple[:, t, 1] + weights[:, 2] * bond_daily
        weights = np.column_stack(
            [
                weights[:, 0] * (1 + simple[:, t, 0]),
                weights[:, 1] * (1 + simple[:, t, 1]),
                weights[:, 2] * (1 + bond_daily),
            ]
        ) / gross[:, None]
        nav *= gross
        nav_series[:, t] = nav
        exposure[:, t] = weights[:, 0] + weights[:, 1]

        month_end = (t + 1) % MONTH_DAYS == 0
        week_end = (t + 1) % WEEK_DAYS == 0
        new_on, new_frac = leg_on, leg_frac

        if structure in ("K1", "K2") and month_end and t >= 10 * MONTH_DAYS:
            month_closes = prices[:, t - 9 * MONTH_DAYS : t + 1 : MONTH_DAYS, :]
            new_on = (prices[:, t, :] >= month_closes.mean(axis=1)).astype(float)

        if structure == "K2" and week_end and t >= TRADING_DAYS:
            long_vol = log_returns[:, t - TRADING_DAYS + 1 : t + 1, :].std(axis=1)
            short_vol = log_returns[:, t - vol_short + 1 : t + 1, :].std(axis=1)
            target_frac = np.minimum(1.0, long_vol / np.maximum(short_vol, 1e-9))
            move = np.abs(target_frac - leg_frac) >= vol_band
            new_frac = np.where(move, target_frac, leg_frac)

        stock_legs = base * new_on * new_frac
        target = np.column_stack([stock_legs, 1 - stock_legs.sum(axis=1)])

        state_change = (new_on != leg_on).any(axis=1)
        frac_change = (np.abs(new_frac - leg_frac) > 1e-12).any(axis=1)
        rebalance = month_end
        trade = state_change | frac_change | rebalance

        if trade.any():
            turnover = np.abs(target - weights).sum(axis=1) * trade
            vol_only = frac_change & ~state_change
            state_only = state_change
            plain = trade & ~state_only & ~vol_only
            for key, mask in (
                ("保险切换", state_only),
                ("波动调仓", vol_only),
                ("再平衡", plain),
            ):
                turns[key] += turnover * mask
            nav *= 1 - LEG_COST * turnover
            weights = np.where(trade[:, None], target, weights)
            flips = new_on != leg_on
            revert = flips & (t - last_flip <= MONTH_DAYS) & (new_on == prev_on)
            flip_count += revert.sum(axis=1)
            prev_on = np.where(flips, leg_on, prev_on)
            last_flip = np.where(flips, t, last_flip)

        leg_on, leg_frac = new_on, new_frac

    scaled_turns = {k: v / (horizon / TRADING_DAYS) for k, v in turns.items()}
    flips_per_year = flip_count / (horizon / TRADING_DAYS)
    return nav_series, exposure, scaled_turns, flips_per_year


def path_stats(nav: np.ndarray, exposure: np.ndarray, warmup: int = WARMUP) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    segment = nav[:, warmup - 1 :] / nav[:, warmup - 1 : warmup]
    years = (nav.shape[1] - warmup) / TRADING_DAYS
    annualized = segment[:, -1] ** (1 / years) - 1
    peaks = np.maximum.accumulate(segment, axis=1)
    drawdown = (segment / peaks - 1).min(axis=1)
    avg_exposure = exposure[:, warmup:].mean(axis=1)
    return annualized, drawdown, avg_exposure


def percentile_band(x: np.ndarray, ps: Iterable[int] = (10, 50, 90)) -> List[float]:
    return [float(np.percentile(x, p)) for p in ps]


def run_scenario(name: str, segments: List[Segment], n_paths: int, seed: int) -> dict:
    z, corr = load_paired_noise()
    sampler = NoiseSampler(z, seed)
    lr = compose_paths(segments, sampler, n_paths)
    out = {}
    k0_ann, k0_mdd, k0_exp = None, None, None
    for struct in ("K0", "K1", "K2"):
        nav, expo, turns, flips = simulate_structure(lr, struct)
        ann, mdd, exp = path_stats(nav, expo)
        if struct == "K0":
            k0_ann, k0_mdd, k0_exp = ann, mdd, exp
        total_turn = sum(turns.values())
        out[struct] = {
            "ann_median_pct": round(float(np.median(ann)) * 100, 2),
            "vs_k0_ann_pctiles": [round(v * 100, 4) for v in percentile_band(ann - k0_ann)],
            "mdd_median_pct": round(float(np.median(mdd)) * 100, 1),
            "vs_k0_mdd_p50_pct": round(float(np.median(mdd - k0_mdd)) * 100, 1),
            "stock_exposure_ratio_p50": round(float(np.median(exp / k0_exp)), 3),
            "flips_per_year_p50": round(float(np.median(flips)), 2),
            "turnover_annual_p50": {k: round(float(np.median(v)), 2) for k, v in turns.items()},
            "total_turn_p50": round(float(np.median(total_turn)), 2),
            "cost_annual_pct_p50": round(float(np.median(total_turn)) * LEG_COST * 100, 3),
        }
    return {"scenario": name, "structures": out, "meta": {"paths": n_paths, "seed": seed, "noise_corr": round(corr, 3)}}


def main_review_r1(out_dir: Path, n_paths: int = 1000) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, segs in SCENARIOS.items():
        rows.append(run_scenario(name, segs, n_paths, DEFAULT_SEED))
    target = out_dir / "r1_synthetic.json"
    target.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


if __name__ == "__main__":
    main_review_r1(Path(__file__).parent / "out")