"""§3.2 合成行情。只跑 msim_v6_n3 的「防守资产不帮忙」。

路径噪声来自 2013-01 至 2015-12 的设计期残差。美股名额的把握 p 用起点经验；
没有经过两份逐格比较的起点，调用方必须把结果标成未完成验收。
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from src.v6.engine import slot
from src.v6.guard import DESIGN_END_TEXT, assert_not_after, install_readers, restore_readers
from src.v6.trin import clip_expanding, clip_full_sample, month_end_mean, raw_ratio

ROOT_DB = None
D = 252
M = 21
WARM2 = 504
SEED = 20261117
BOND = 0.03
BENCH_COST = 0.001
US_CODES = ["SPX", "NDX", "DJIA", "SOX", "NBI", "XLK", "XLV", "XLE", "XLY", "XLP", "XLF", "XLI", "XLB", "XLU"]


def _seg(days, mu_a, mu_u, vol_a, vol_u):
    return (days, mu_a, mu_u, vol_a, vol_u)


def _total(rate, days):
    return (1 + rate) ** (D / days) - 1


def scenarios():
    warm = _seg(D, 0.08, 0.08, 0.15, 0.15)
    return {
        "慢牛": [ _seg(D, 0.08, 0.08, 0.15, 0.15), _seg(3 * D, 0.15, 0.15, 0.15, 0.15)],
        "急跌": [warm, _seg(D, 0.15, 0.15, 0.15, 0.15), _seg(20, _total(-0.30, 20), _total(-0.30, 20), 0.40, 0.40),
               _seg(120, 0.0, 0.0, 0.25, 0.25)],
        "慢熊": [_seg(D, 0.08, 0.08, 0.18, 0.18), _seg(378, _total(-0.45, 378), _total(-0.45, 378), 0.25, 0.25)],
        "V型反转": [_seg(D, 0.08, 0.08, 0.18, 0.18), _seg(20, _total(-0.30, 20), _total(-0.30, 20), 0.40, 0.40),
                  _seg(60, _total(1 / 0.7 - 1, 60), _total(1 / 0.7 - 1, 60), 0.35, 0.35), _seg(120, 0.10, 0.10, 0.20, 0.20)],
        "震荡": [_seg(D, 0.08, 0.08, 0.22, 0.22), _seg(3 * D, 0.0, 0.0, 0.22, 0.22)],
        "市场接力": [_seg(D, 0.08, 0.08, 0.20, 0.20), _seg(378, 0.25, 0.0, 0.20, 0.20), _seg(378, 0.0, 0.25, 0.20, 0.20)],
    }


def _residuals(panels):
    from pathlib import Path
    window = panels["A_pub"].loc["2013-01-01":"2015-12-31"]
    names = [c for c in window.columns if window[c].notna().all()]
    prices = window[names]
    amount = pd.DataFrame({c: panels["amt"][c].reindex(window.index) for c in names if c in panels["amt"]})
    originals = install_readers(pd)
    root = Path(__file__).resolve().parents[2]
    con = sqlite3.connect(root / "data/market.sqlite")
    try:
        frames = {}
        for code in US_CODES:
            frame = pd.read_sql_query(
                "select date, close, volume from bars where code=? and adj='raw' and close>0 "
                "and date>=? and date<=? order by date",
                con, params=(code, "2012-12-01", "2015-12-31"))
            frame = frame.drop_duplicates("date", keep="last")
            frame.index = pd.to_datetime(frame["date"])
            assert_not_after(frame.index, code)
            frames[code] = frame
    finally:
        con.close()
        restore_readers(pd, originals)
    calendar = prices.index
    us_px = pd.DataFrame({
        c: frames[c]["close"].reindex(calendar.union(frames[c].index)).ffill().reindex(calendar)
        for c in US_CODES
    })
    us_amt = pd.DataFrame({
        c: (frames[c]["close"] * frames[c]["volume"]).reindex(calendar)
        for c in US_CODES if c.startswith("X")
    })
    ra = np.log(prices).diff().iloc[1:]
    ru = np.log(us_px).diff().iloc[1:]
    ra = ra - ra.mean()
    ru = ru - ru.mean()
    ra = ra / ra["csi300"].std()
    ru = ru / ru["SPX"].std()
    return {
        "a_cols": names,
        "RA": ra.to_numpy(),
        "RU": ru.to_numpy(),
        "AA": amount.iloc[1:].fillna(amount.median()).to_numpy(),
        "UA": us_amt.iloc[1:].fillna(us_amt.median()).to_numpy(),
        "aa_cols": list(amount.columns),
        "ua_cols": list(us_amt.columns),
    }


def _path(pack, segs, rng):
    k = int(np.ceil(sum(s[0] for s in segs) / 20)) + 1
    start = rng.integers(0, len(pack["RA"]) - 20, size=k)
    index = (start[:, None] + np.arange(20)).ravel()
    out_a, out_u, amt_a, amt_u, bond = [], [], [], [], []
    pos = 0
    for days, ma, mu, va, vu in segs:
        j = index[pos:pos + days]
        pos += days
        out_a.append(np.log1p(ma) / D + pack["RA"][j] * va / np.sqrt(D))
        out_u.append(np.log1p(mu) / D + pack["RU"][j] * vu / np.sqrt(D))
        amt_a.append(pack["AA"][j])
        amt_u.append(pack["UA"][j])
        # 不帮忙：下跌段国债收益为 0，其余 2.5%。与 msim_v6_n3.path 的 helps=False 相同。
        rate = 0.0 if (ma + mu) / 2 < 0 else 0.025
        bond.append(np.full(days, (1 + rate) ** (1 / D) - 1))
    return (np.vstack(out_a), np.vstack(out_u), np.vstack(amt_a), np.vstack(amt_u), np.concatenate(bond))


def _clip_month(prices, amount, new: bool) -> pd.Series:
    daily = raw_ratio(prices, amount, min_movers=None)
    clipped = clip_expanding(daily) if new else clip_full_sample(daily)
    return month_end_mean(clipped)


def _k0(log_ret):
    simple = np.expm1(log_ret)
    bond = (1 + BOND) ** (1 / D) - 1
    weight = np.array([0.70, 0.30, 0.0])
    nav = 1.0
    out = np.empty(len(log_ret))
    for t in range(len(log_ret)):
        growth = 1 + weight[0] * simple[t, 0] + weight[1] * simple[t, 1] + weight[2] * bond
        weight = np.array([
            weight[0] * (1 + simple[t, 0]),
            weight[1] * (1 + simple[t, 1]),
            weight[2] * (1 + bond),
        ]) / growth
        nav *= growth
        if (t + 1) % M == 0:
            target = np.array([0.70, 0.30, 0.0])
            traded = float(np.abs(target - weight).sum())
            nav *= 1 - BENCH_COST * traded
            weight = target
        out[t] = nav
    return out


def _stats(nav):
    seg = nav[WARM2 - 1:] / nav[WARM2 - 1]
    years = (len(nav) - WARM2) / D
    low = 100 * (seg / np.maximum.accumulate(seg)).min()
    ann = seg[-1] ** (1 / years) - 1
    return float(low), float(ann)


def no_help(panels, prior, *, new_trin: bool, paths: int = 200) -> pd.DataFrame:
    pack = _residuals(panels)
    rows = []
    for name, segs in scenarios().items():
        segs = [_seg(WARM2 - D, *segs[0][1:])] + list(segs)
        rng = np.random.default_rng(SEED)
        system, bench = [], []
        for _ in range(paths):
            la, lu, aa, au, bond = _path(pack, segs, rng)
            dates = pd.bdate_range("2000-01-03", periods=len(la))
            a_level = pd.DataFrame(np.exp(np.cumsum(la, axis=0)), index=dates, columns=pack["a_cols"])
            u_level = pd.DataFrame(np.exp(np.cumsum(lu, axis=0)), index=dates, columns=US_CODES)
            a_amt = pd.DataFrame(aa, index=dates, columns=pack["aa_cols"])
            u_amt = pd.DataFrame(au, index=dates, columns=pack["ua_cols"])
            panels["trin"]["csi300"] = _clip_month(a_level[pack["aa_cols"]], a_amt, new_trin)
            panels["trin"]["SPX"] = _clip_month(u_level[pack["ua_cols"]], u_amt, new_trin)
            cash = pd.Series((1.02) ** (1 / D) - 1, index=dates)
            bond_s = pd.Series(bond, index=dates)
            a_ret, _, _ = slot(a_level, "csi300", 3, None, {}, "v6", 0.002, panels["votes"], bond_s, cash, dedupe=False)
            u_ret, _, _ = slot(u_level, "SPX", 3, prior, {}, "v6", 0.002, panels["votes"], bond_s, cash, dedupe=False)
            nav = (1 + (0.4 * a_ret + 0.6 * u_ret)).cumprod().to_numpy()
            parent = np.column_stack([la[:, pack["a_cols"].index("csi300")], lu[:, US_CODES.index("SPX")]])
            system.append(_stats(nav))
            bench.append(_stats(_k0(parent)))
        sys_a = np.array(system)
        ben_a = np.array(bench)
        rows.append({
            "行情": name,
            "口径": "扩展99%" if new_trin else "全样本99%（仅本条合成路径）",
            "最低剩_中位": round(float(np.median(sys_a[:, 0])), 1),
            "最低剩_p10": round(float(np.percentile(sys_a[:, 0], 10)), 1),
            "比基准年化_中位": round(float(np.median(sys_a[:, 1] - ben_a[:, 1])) * 100, 2),
        })
    return pd.DataFrame(rows)
