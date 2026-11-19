"""D38 第 40 行 M5：新系统在带行业的合成行情里，查 D39 两条线（慢牛落后 ≤ 4 点、最低剩 ≥ 60 万）。
用法：python scripts/preflight/msim_v6.py <49_Industry_Portfolios.csv> <DTB3.csv> [路径数]
"""
import sys, json, sqlite3, pathlib, warnings
warnings.filterwarnings('ignore')
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parents[1]
FFP, DTBP = sys.argv[1], sys.argv[2]; NP = int(sys.argv[3]) if len(sys.argv) > 3 else 200
import numpy as np, pandas as pd
G = {'__file__': str(HERE / 'a_official.py'), '__name__': 'x'}; sys.argv = ['x', FFP, DTBP]
exec(open(HERE / 'a_official.py').read().split("res = {'每年末")[0], G)
A, AMT, slot_phi, V, US_PRIOR = G['A'], G['AMT'], G['slot_phi'], G['V'], G['US_PRIOR']
sys.path.insert(0, str(HERE)); sys.argv = ['x', '/tmp/simout']; import sim
D, SEED, COST, WARM2 = 252, 20261117, 0.002, 504

# ---------- 噪声：2013-01 → 2015-12 两个市场全部候选 ----------
W0, W1 = '2013-01-01', '2015-12-31'
Aw = A.loc[W0:W1]; Acols = [c for c in Aw.columns if Aw[c].notna().all()]
con = sqlite3.connect(ROOT / 'data/market.sqlite')
US_C = ['SPX', 'NDX', 'DJIA', 'SOX', 'NBI', 'XLK', 'XLV', 'XLE', 'XLY', 'XLP', 'XLF', 'XLI', 'XLB', 'XLU']
def ubar(code):
    d = pd.read_sql_query("select date, close, volume from bars where code=? and adj='raw' and close>0 and date between ? and ? order by date", con, params=(code, '2012-12-01', W1))
    d = d.drop_duplicates('date', keep='last'); d.index = pd.to_datetime(d['date']); return d
cal = Aw.index
U = {c: ubar(c) for c in US_C}
UP = pd.DataFrame({c: U[c]['close'].reindex(cal.union(U[c].index)).ffill().reindex(cal) for c in US_C})
UA = pd.DataFrame({c: (U[c]['close'] * U[c]['volume']).reindex(cal) for c in US_C if c.startswith('X')})   # 成交额：行业 SPDR
AP = Aw[Acols]; AA = pd.DataFrame({c: AMT[c].reindex(cal) for c in Acols if c in AMT})
ra = np.log(AP).diff().iloc[1:]; ru = np.log(UP).diff().iloc[1:]
ra = ra - ra.mean(); ru = ru - ru.mean()                                   # 去掉每个候选自己的平均收益
sa = ra['csi300'].std(); su = ru['SPX'].std()
RA, RU = ra.values / sa, ru.values / su                                     # 母指数日波动 = 1
AAv, UAv = AA.iloc[1:].fillna(AA.median()).values, UA.iloc[1:].fillna(UA.median()).values
n0 = len(RA)

def path(segs, helps, rng):
    k = int(np.ceil(sum(s[0] for s in segs) / 20)) + 1
    st = rng.integers(0, n0 - 20, size=k); ix = (st[:, None] + np.arange(20)).ravel()
    out_a, out_u, amt_a, amt_u, b = [], [], [], [], []; pos = 0
    for days, ma, mu, va, vu in segs:
        j = ix[pos:pos + days]; pos += days
        out_a.append(np.log1p(ma) / D + RA[j] * va / np.sqrt(D)); out_u.append(np.log1p(mu) / D + RU[j] * vu / np.sqrt(D))
        amt_a.append(AAv[j]); amt_u.append(UAv[j])
        down = (ma + mu) / 2 < 0
        by = (0.04 if down else 0.03) if helps else (0.0 if down else 0.025)
        b.append(np.full(days, (1 + by) ** (1 / D) - 1))
    return np.vstack(out_a), np.vstack(out_u), np.vstack(amt_a), np.vstack(amt_u), np.concatenate(b)

def t2(px, am):
    dr = px.pct_change(); up, dn = dr > 0, dr < 0
    d_ = ((up.sum(axis=1) / dn.sum(axis=1).replace(0, np.nan)) / ((am * up).sum(axis=1) / (am * dn).sum(axis=1).replace(0, np.nan))).replace([np.inf, -np.inf], np.nan)
    d_ = d_.clip(upper=d_.quantile(0.99)).rolling(10, min_periods=7).mean().resample('ME').last(); d_.index = d_.index.to_period('M'); return d_

rows = []
for helps in (False, True):
    for name, segs in sim.SCEN.items():
        segs = [sim.seg(WARM2 - sim.WARM, *segs[0][1:])] + segs        # 预热延长到两年（宽度、TRIN 的分位要 24 个月）
        rng = np.random.default_rng(SEED); res = {'新系统': [], '基准': [], '增强基准': []}
        for p in range(NP):
            la, lu, aa, au, b = path(segs, helps, rng); T = len(la)
            dates = pd.bdate_range('2000-01-03', periods=T)
            LA = pd.DataFrame(np.exp(np.cumsum(la, axis=0)), index=dates, columns=Acols)
            LU = pd.DataFrame(np.exp(np.cumsum(lu, axis=0)), index=dates, columns=US_C)
            V['TRIN']['csi300'] = t2(LA[[c for c in Acols if c in AA.columns]], pd.DataFrame(aa, index=dates, columns=AA.columns))
            V['TRIN']['SPX'] = t2(LU[UA.columns], pd.DataFrame(au, index=dates, columns=UA.columns))
            bret = pd.Series(b, dates); cret = pd.Series((1.02) ** (1 / D) - 1, index=dates)
            ra_, _, _ = slot_phi(LA, 'csi300', 2, bret, cret, None); ru_, _, _ = slot_phi(LU, 'SPX', 2, bret, cret, US_PRIOR)
            new = (1 + (0.4 * ra_ + 0.6 * ru_)).cumprod().values
            lr2 = np.column_stack([la[:, Acols.index('csi300')], lu[:, US_C.index('SPX')]])[None]
            bm = sim.run(lr2, s_us=0.30, kind='K0')[0][0]; ek = sim.run(lr2, s_us=0.50, kind='K2A', bond=b)[0][0]
            for k, nv in (('新系统', new), ('基准', bm), ('增强基准', ek)):
                seg_ = nv[WARM2 - 1:] / nv[WARM2 - 1]; yrs = (T - WARM2) / D
                res[k].append((100 * (seg_ / np.maximum.accumulate(seg_)).min(), seg_[-1] ** (1 / yrs) - 1))
        bma = np.array([x[1] for x in res['基准']])
        for k, v in res.items():
            low = np.array([x[0] for x in v]); ann = np.array([x[1] for x in v])
            rows.append(dict(防守资产='帮忙' if helps else '不帮忙', 行情=name, 结构=k, 最低剩_万_中位=round(float(np.median(low)), 1),
                             最低剩_万_p10=round(float(np.percentile(low, 10)), 1), 比基准年化_中位=round(float(np.median(ann - bma)) * 100, 2),
                             比基准年化_p10=round(float(np.percentile(ann - bma, 10)) * 100, 2)))
        print(name, helps, [r for r in rows[-3:]], flush=True)
d = pd.DataFrame(rows); d.to_csv(ROOT / 'results/v6-preflight/msim-v6.csv', index=False)
print(d.to_string(index=False))
