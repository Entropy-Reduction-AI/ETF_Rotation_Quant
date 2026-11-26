"""§3.2 六种「不帮忙」合成路径。两种 TRIN 截尾各跑 200 条。"""

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
sys.argv = ["x", "/tmp/simout"]

import scripts.preflight.sim as sim
from run_d45 import A_SPEC, TRIN_A, US_TRIN, bars_frame, build_levels, market_legs
from v6ind.d45_engine import run_slot, trin_from_prices, votes
from v6ind.d45_french import us_prior, value_weighted_market
from v6ind.load import connect_readonly

OUT = Path(__file__).resolve().parent / "output"
D = 252
SEED = 20261117
WARM2 = 504
NP = 200
US_C = ["SPX", "NDX", "DJIA", "SOX", "NBI", "XLK", "XLV", "XLE", "XLY", "XLP", "XLF", "XLI", "XLB", "XLU"]


def path(segs, rng, noise_a, noise_u, amt_a, amt_u):
    days_total = sum(item[0] for item in segs)
    draws = int(np.ceil(days_total / 20)) + 1
    start = rng.integers(0, len(noise_a) - 20, size=draws)
    index = (start[:, None] + np.arange(20)).ravel()
    blocks_a, blocks_u, blocks_aa, blocks_ua, bond = [], [], [], [], []
    pos = 0
    for days, drift_a, drift_u, vol_a, vol_u in segs:
        chosen = index[pos:pos + days]
        pos += days
        blocks_a.append(np.log1p(drift_a) / D + noise_a[chosen] * vol_a / np.sqrt(D))
        blocks_u.append(np.log1p(drift_u) / D + noise_u[chosen] * vol_u / np.sqrt(D))
        blocks_aa.append(amt_a[chosen])
        blocks_ua.append(amt_u[chosen])
        down = (drift_a + drift_u) / 2 < 0
        rate = 0.0 if down else 0.025
        bond.append(np.full(days, (1 + rate) ** (1 / D) - 1))
    return (np.vstack(blocks_a), np.vstack(blocks_u), np.vstack(blocks_aa), np.vstack(blocks_ua), np.concatenate(bond))


def scenario_segments(name: str):
    base = sim.SCEN[name]
    return [sim.seg(WARM2 - sim.WARM, *base[0][1:])] + list(base)


def summarize(nav_end, low, benchmark_ann):
    return {
        "最低剩_万_中位": round(float(np.median(low)), 1),
        "最低剩_万_p10": round(float(np.percentile(low, 10)), 1),
        "比基准年化_中位": round(float(np.median(nav_end - benchmark_ann)) * 100, 2),
    }


def main() -> None:
    con = connect_readonly(ROOT / "data" / "market.sqlite")
    codes = sorted({row[1] for row in A_SPEC} | set(US_C))
    raw = bars_frame(con, codes)
    con.close()
    calendar, _bond, _cash = market_legs()
    levels_a, amounts_a = build_levels(raw, A_SPEC, calendar, None)
    window = levels_a.loc["2013-01-01":"2015-12-31"]
    complete = [column for column in window.columns if window[column].notna().all()]
    prices = window[complete]
    amount_names = [name for name in complete if name in TRIN_A]
    amounts = amounts_a[amount_names].loc[prices.index]
    us_close = {}
    us_dollar = {}
    for code in US_C:
        close = raw[code]["close"]
        close = close[close > 0]
        close = close[~close.index.duplicated(keep="last")]
        us_close[code] = close.reindex(prices.index.union(close.index)).ffill().reindex(prices.index)
        if code in US_TRIN:
            volume = raw[code]["volume"].reindex(close.index)
            us_dollar[code] = (close * volume).where(lambda values: values > 0).reindex(prices.index)
    us_prices = pd.DataFrame(us_close)
    us_amounts = pd.DataFrame(us_dollar)
    residual_a = np.log(prices).diff().iloc[1:]
    residual_u = np.log(us_prices).diff().iloc[1:]
    residual_a = residual_a - residual_a.mean()
    residual_u = residual_u - residual_u.mean()
    noise_a = (residual_a / residual_a["csi300"].std()).to_numpy(dtype=float)
    noise_u = (residual_u / residual_u["SPX"].std()).to_numpy(dtype=float)
    amount_a = amounts.iloc[1:].fillna(amounts.median()).to_numpy(dtype=float)
    amount_u = us_amounts.iloc[1:].fillna(us_amounts.median()).to_numpy(dtype=float)
    prior = us_prior(value_weighted_market(Path("/tmp/49_Industry_Portfolios.csv").read_text(errors="replace")))
    tags = {name: "" for name in [*complete, *US_C]}
    rows = []
    diffs = []
    for clip in ("full", "expanding"):
        saved = {}
        for name in sim.SCEN:
            segments = scenario_segments(name)
            rng = np.random.default_rng(SEED)
            new_low, new_ann, base_low, base_ann = [], [], [], []
            for _path in range(NP):
                left, right, amt_left, amt_right, bond = path(segments, rng, noise_a, noise_u, amount_a, amount_u)
                dates = pd.bdate_range("2000-01-03", periods=len(left))
                level_a = pd.DataFrame(np.exp(np.cumsum(left, axis=0)), index=dates, columns=complete)
                level_u = pd.DataFrame(np.exp(np.cumsum(right, axis=0)), index=dates, columns=US_C)
                trin_a = trin_from_prices(level_a[[c for c in complete if c in amounts.columns]],
                                          pd.DataFrame(amt_left, index=dates, columns=amounts.columns), clip=clip)
                trin_u = trin_from_prices(level_u[list(us_amounts.columns)],
                                          pd.DataFrame(amt_right, index=dates, columns=us_amounts.columns), clip=clip)
                bond_ret = pd.Series(bond, index=dates)
                cash_ret = pd.Series((1.02) ** (1 / D) - 1, index=dates)
                ret_a, _t, _log = run_slot(level_a, "csi300", votes(level_a, "csi300", trin_a), bond_ret, cash_ret,
                                           tags, None, mode="v6", cost=0.002, dedupe=False)
                ret_u, _t, _log = run_slot(level_u, "SPX", votes(level_u, "SPX", trin_u), bond_ret, cash_ret,
                                           tags, prior, mode="v6", cost=0.002, dedupe=False)
                nav = (1 + (0.4 * ret_a + 0.6 * ret_u)).cumprod().to_numpy()
                paired = np.column_stack([left[:, complete.index("csi300")], right[:, US_C.index("SPX")]])[None]
                base = sim.run(paired, s_us=0.30, kind="K0")[0][0]
                segment = nav[WARM2 - 1:] / nav[WARM2 - 1]
                years = (len(nav) - WARM2) / D
                new_low.append(100 * (segment / np.maximum.accumulate(segment)).min())
                new_ann.append(segment[-1] ** (1 / years) - 1)
                base_segment = base[WARM2 - 1:] / base[WARM2 - 1]
                base_low.append(100 * (base_segment / np.maximum.accumulate(base_segment)).min())
                base_ann.append(base_segment[-1] ** (1 / years) - 1)
            new_low, new_ann = np.array(new_low), np.array(new_ann)
            base_low, base_ann = np.array(base_low), np.array(base_ann)
            saved[name] = {
                "新系统": summarize(new_ann, new_low, base_ann) | {"最低剩_万_中位": round(float(np.median(new_low)), 1),
                                                              "最低剩_万_p10": round(float(np.percentile(new_low, 10)), 1)},
                "基准": {"最低剩_万_中位": round(float(np.median(base_low)), 1),
                       "最低剩_万_p10": round(float(np.percentile(base_low, 10)), 1)},
            }
            # summarize() already subtracts benchmark; keep the low points explicit
            saved[name]["新系统"]["比基准年化_中位"] = round(float(np.median(new_ann - base_ann)) * 100, 2)
            print(clip, name, saved[name], flush=True)
        rows.append({"clip": clip, "scenarios": saved})
    if len(rows) == 2:
        for name in sim.SCEN:
            left = rows[0]["scenarios"][name]
            right = rows[1]["scenarios"][name]
            diffs.append({"行情": name, "差为0": left == right, "full": left, "expanding": right})
    payload = {"paths": NP, "seed": SEED, "help": "不帮忙", "clips": rows, "clip_diff": diffs,
               "diff_scenarios": sum(not item["差为0"] for item in diffs)}
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "d45-synthetic.json"
    target.write_bytes(raw)
    print(json.dumps({"synthetic_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                      "scenarios_that_differ": payload["diff_scenarios"]}))


if __name__ == "__main__":
    main()
