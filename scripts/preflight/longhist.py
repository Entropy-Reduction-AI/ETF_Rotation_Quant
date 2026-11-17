"""D38 预演第 2 项后半：长历史整段回放（单市场版本的 K0、K1、K2）。

数据（已登记，不在任何检验段里）：标普500 1955-01 → 2003-06-30；恒生、日经 1987-01 → 2015-12-31。
国债/现金：美国 3 个月国库券 DTB3（恒生同，港元挂钩美元）；日经用日本银行拆借利率（与 results/v5/diag/design/longhist.py 相同）。
价格指数，不含分红（三种结构同口径，比较的是差）。规则与 sim.py 相同：
  K0 一直持有；K1 月末低于 10 个月末均线换成现金，回到上方换回；K2 = K1 × min(1, 252 日波动 ÷ 20 日波动)，每周看，变化不到 10 个点不动。
成本每腿单边 0.1%。熊市 = 从高点回落 ≥ 20%，到低点后反弹 ≥ 20% 结束（同 v5 longhist 口径）。
用法：python scripts/preflight/longhist.py results/v6-preflight
"""
import sys, json, pathlib
import numpy as np, pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
RAW = ROOT / 'data/research/long-history/raw'
COST = 0.001

dtb = pd.read_csv(ROOT / 'results/v5/other-market/raw/DTB3.csv', parse_dates=['date'], na_values=['.', '']).set_index('date')['DTB3']
dtb = dtb.where(dtb > -100).dropna()
def jp_rate():
    dd = pd.read_csv(RAW / 'FM01-STRDCLUCON.csv', parse_dates=['date']).set_index('date').iloc[:, 0]
    mm = pd.read_csv(RAW / 'FM02-STRACLUCON.csv'); mm.index = pd.to_datetime(mm.iloc[:, 0].astype(str)); mm = mm.iloc[:, 1]
    mm = mm[mm.index < dd.index[0]]
    return pd.concat([mm, dd]).sort_index().astype(float)

SETS = (('标普500', '^GSPC.csv', '1955-01-01', '2003-06-30', None),
        ('恒生', '^HSI.csv', '1987-01-01', '2015-12-31', None),
        ('日经', '^N225.csv', '1987-01-01', '2015-12-31', 'jp'))

def bears(px):
    out, mode, ext, ext_t, peak_t, peak = [], 'up', px.iloc[0], px.index[0], None, None
    for t, p in px.items():
        if mode == 'up':
            if p > ext: ext, ext_t = p, t
            elif p <= ext * 0.8: mode, peak_t, peak, ext, ext_t = 'down', ext_t, ext, p, t
        else:
            if p < ext: ext, ext_t = p, t
            elif p >= ext * 1.2: out.append((peak_t, ext_t, ext / peak - 1)); mode, ext, ext_t = 'up', p, t
    if mode == 'down': out.append((peak_t, ext_t, ext / peak - 1))
    return out

def simulate(px, rate, kind):
    r = px.pct_change().fillna(0).values
    gap = px.index.to_series().diff().dt.days.fillna(1).values
    c = (rate.reindex(px.index, method='ffill').ffill().bfill().values / 100) * gap / 360
    lr = np.log1p(r)
    month = px.index.to_period('M'); me = np.r_[month[1:] != month[:-1], True]
    me_idx = np.where(me)[0]
    week = px.index.to_period('W'); we = np.r_[week[1:] != week[:-1], True]
    n = len(px); w = 1.0; on = 1.0; frac = 1.0; nav = 1.0
    navs = np.empty(n); expo = np.empty(n); turn = 0.0; flips_back = 0; last_flip = -999; last_state = 1.0
    p = px.values
    for t in range(n):
        g = 1 + w * r[t] + (1 - w) * c[t]
        w = w * (1 + r[t]) / g; nav *= g; navs[t] = nav; expo[t] = w
        new_on, new_frac = on, frac
        if kind in ('K1', 'K2') and me[t]:
            k = np.searchsorted(me_idx, t)
            if k >= 9:
                new_on = float(p[t] >= p[me_idx[k - 9:k + 1]].mean())
        if kind == 'K2' and we[t] and t >= 252:
            vl = lr[t - 251:t + 1].std(); vs = lr[t - 19:t + 1].std()
            f = min(1.0, vl / max(vs, 1e-12))
            if abs(f - frac) >= 0.10: new_frac = f
        tgt = new_on * new_frac
        if kind == 'K0': tgt = 1.0
        if abs(tgt - w) > 1e-12 and (new_on != on or new_frac != frac or kind == 'K0'):
            tr = 2 * abs(tgt - w) if kind != 'K0' else 0.0     # 卖股票买现金（或反之），两条腿都算
            nav *= (1 - COST * tr); turn += tr; w = tgt
        if new_on != on:
            if t - last_flip <= 31 and new_on == last_state: flips_back += 1
            last_state, last_flip = on, t
        on, frac = new_on, new_frac
    return pd.Series(navs, px.index), pd.Series(expo, px.index), turn, flips_back

def ann(s):
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    return (s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1

def mdd(s):
    return float((s / s.cummax() - 1).min())

rows, bear_rows = [], []
for name, f, a, b, cash in SETS:
    d = pd.read_csv(RAW / f, parse_dates=['date']).set_index('date')['close']
    px = d[(d.index >= a) & (d.index <= b)]
    px = px[px > 0]
    rate = jp_rate() if cash == 'jp' else dtb
    res = {k: simulate(px, rate, k) for k in ('K0', 'K1', 'K2')}
    st = px.index[0] + pd.Timedelta(days=366)                        # 跳过第一年预热
    bs = bears(px[px.index >= st])
    in_bear = pd.Series(False, px.index)
    for p0, p1, _ in bs: in_bear[(in_bear.index > p0) & (in_bear.index <= p1)] = True
    yrs = (px.index[-1] - st).days / 365.25
    for k, (nav, expo, turn, fb) in res.items():
        nv = nav[nav.index >= st]
        dr = nv.pct_change().fillna(0); k0 = res['K0'][0][res['K0'][0].index >= st].pct_change().fillna(0)
        bull_years = (~in_bear[in_bear.index >= st]).sum() / 252; bear_years = in_bear[in_bear.index >= st].sum() / 252
        bull_ex = np.expm1(np.log1p(dr[~in_bear]).sum() - np.log1p(k0[~in_bear]).sum()) if k != 'K0' else 0.0
        bear_ex = np.expm1(np.log1p(dr[in_bear]).sum() - np.log1p(k0[in_bear]).sum()) if k != 'K0' else 0.0
        rows.append(dict(市场=name, 区间=f'{st.date()}→{px.index[-1].date()}', 结构=k,
                         年化=round(ann(nv) * 100, 2), 比K0年化=round((ann(nv) - ann(res['K0'][0][res['K0'][0].index >= st])) * 100, 2),
                         最大回撤=round(mdd(nv) * 100, 1),
                         牛市段每年比K0=round((np.log1p(dr[~in_bear]).sum() - np.log1p(k0[~in_bear]).sum()) / bull_years * 100, 2),
                         熊市段每年比K0=round((np.log1p(dr[in_bear]).sum() - np.log1p(k0[in_bear]).sum()) / bear_years * 100, 2),
                         平均仓位=round(float(expo[expo.index >= st].mean()), 3),
                         双边换手_每年=round(turn / yrs, 2), 成本_每年_百分点=round(turn / yrs * COST * 100, 3),
                         一月内翻回_每年=round(fb / yrs, 2), 熊市段数=len(bs), 熊市占时间=round(bear_years / (bull_years + bear_years), 3)))
    for p0, p1, dd in bs:
        row = dict(市场=name, 见顶=str(p0.date()), 见底=str(p1.date()), 跌幅=round(dd * 100, 1),
                   跌的天数=int(((px.index > p0) & (px.index <= p1)).sum()))
        for k in ('K1', 'K2'):
            nav = res[k][0]; k0n = res['K0'][0]
            seg = (nav.index >= p0) & (nav.index <= p1)
            row[f'{k}_这段少亏'] = round((nav[seg].iloc[-1] / nav[seg].iloc[0] - k0n[seg].iloc[-1] / k0n[seg].iloc[0]) * 100, 1)
            e = res[k][1]; after = e[(e.index > p1)].iloc[:252]
            hit = np.where(after.values >= 0.5)[0]
            row[f'{k}_见底后回到半仓天数'] = int(hit[0]) if len(hit) else None
            if len(hit):
                row[f'{k}_回来时已离底涨'] = round((px[after.index[hit[0]]] / px[p1] - 1) * 100, 1)
        bear_rows.append(row)

pd.DataFrame(rows).to_csv(OUT / 'longhist.csv', index=False)
pd.DataFrame(bear_rows).to_csv(OUT / 'longhist-bears.csv', index=False)
print(pd.DataFrame(rows).to_string()); print(pd.DataFrame(bear_rows).to_string())
