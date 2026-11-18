"""D38 第 27 行：整套系统换防守位置（②绝对动量、③只在母指数层面、④按名额波动缩放），设计期 2006–2015。
用法：python scripts/preflight/topn_system2.py results/v6-preflight
"""
import sys, json, pathlib
HERE = pathlib.Path(__file__).resolve().parent
src = open(HERE / 'topn_system.py').read().split("res = {'第22行")[0]
sys.argv = [sys.argv[0], 'results/v6-preflight']
g = {'__file__': str(HERE / 'topn_system.py'), '__name__': 'x'}; exec(src, g)
import numpy as np, pandas as pd
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith('/tmp') else pathlib.Path('results/v6-preflight')
A_LVL, bond, cash, idx, stats, sim, P = (g[k] for k in ('A_LVL', 'bond', 'cash', 'idx', 'stats', 'sim', 'P'))
US_RMB = g['us_frame'](True, idx)

def slot2(lvl, parent, N, mode, bret, cret, cost=0.002):
    cal = lvl.index; r = lvl.pct_change().fillna(0).values; K = lvl.shape[1]; cols = list(lvl.columns); pi = cols.index(parent)
    me_mask = np.r_[cal.month[1:] != cal.month[:-1], True]
    me = lvl[me_mask]; mom = me.shift(1) / me.shift(12) - 1; above = me > me.rolling(10).mean()
    cme = np.exp(np.log1p(cret).cumsum())[me_mask]; c12 = cme / cme.shift(12) - 1
    blvl = np.exp(np.log1p(bret.fillna(0)).cumsum()).where(bret.notna().cumsum() > 0)
    bme = blvl[me_mask]; babove = (bme > bme.rolling(10).mean()) & bme.notna()
    pr = lvl[parent].pct_change()
    w = np.zeros(K); wb = 0.0; wc = 1.0; out = np.zeros(len(cal)); turn = 0.0; pending = None
    br, cr = bret.fillna(0).values, cret.values; hist = []
    for t in range(len(cal)):
        if pending is not None:
            tgt, tb, tc = pending; tr = np.abs(tgt - w).sum() + abs(tb - wb); turn += tr; cst = cost * tr
            w, wb, wc = tgt, tb, tc; pending = None
        else: cst = 0.0
        gg = (w * r[t]).sum() + wb * br[t] + wc * cr[t]; out[t] = (1 + gg) * (1 - cst) - 1
        G = 1 + gg; w = w * (1 + r[t]) / G; wb = wb * (1 + br[t]) / G; wc = wc * (1 + cr[t]) / G
        if me_mask[t]:
            d = cal[t]; sc = mom.loc[d].values.astype(float); ok = np.isfinite(sc); tgt = np.zeros(K)
            if not ok.any(): tgt[pi] = 1.0
            else:
                if mode == 'absmom': ok &= sc > (c12.loc[d] if np.isfinite(c12.loc[d]) else 0)
                if mode == 'mktgate' and not bool(above.loc[d].values[pi]): ok &= sc > 0
                pick = [i for i in np.argsort(-np.where(ok, sc, -np.inf))[:N] if ok[i]]; tgt[pick] = 1 / N
                if mode == 'volscale' and t > 126:
                    real = np.std(out[t - 126:t]) * np.sqrt(252); target = pr.iloc[:t].std() * np.sqrt(252)
                    if real > 0: tgt = tgt * min(1.0, target / real)
            left = 1 - tgt.sum(); bok = bool(babove.loc[d]) if d in babove.index else False
            pending = (tgt, left if bok else 0.0, 0.0 if bok else left)
    return pd.Series(out, cal), turn

def system(N, mode):
    a, ta = slot2(A_LVL, 'csi300', N, mode, bond, cash); u, tu = slot2(US_RMB, 'SPX', N, mode, bond, cash)
    ret = 0.5 * a + 0.5 * u; st = stats(ret, '2006-01-01', {'2006–10': ('2006', '2010'), '2011–15': ('2011', '2015')})
    s = (1 + ret.loc['2006':]).cumprod()
    for k, (x0, x1) in {'2008': ('2007-06-01', '2009-12-31'), '2015': ('2015-01-01', '2015-12-31')}.items():
        x = s.loc[x0:x1]; pk = s.loc[:x.index[-1]].cummax().loc[x.index]; st[f'最低剩_{k}'] = round(float(100 * (x / pk).min()), 1)
    yr = s.resample('YE').last().pct_change(); yr.iloc[0] = s.resample('YE').last().iloc[0] - 1
    st['最差一年'] = round(float(yr.min()) * 100, 1); st['每年换手_倍'] = round((ta + tu) / 2 / (len(s) / 252), 2)
    return st
res = {}
for N in (2, 3):
    for mode, name in (('none', '不设防守'), ('absmom', '②绝对动量'), ('mktgate', '③只在母指数层面'), ('volscale', '④按名额波动缩放')):
        res[f'前{N} {name}'] = system(N, mode)
old = json.load(open('results/v6-preflight/topn-system.json'))
for k in ('基准（美股30%）', '增强基准（K2A 美股50%）', '前2+门槛 成本0.2%', '前3+门槛 成本0.2%'): res[f'参照 {k}'] = old[k]
json.dump(res, open('results/v6-preflight/topn-system2.json', 'w'), ensure_ascii=False, indent=1)
print(pd.DataFrame(res).T.to_string())
