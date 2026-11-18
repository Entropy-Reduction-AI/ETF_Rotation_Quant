"""D38 第 35 行 M4：分级要求。平时满仓前 N；母指数跌破均线 → 入选者 12−1 为正；确认紧张（≥2 票）→ 还须站上自己均线。
用法：python scripts/preflight/topn_tiered.py <49_Industry_Portfolios.csv> <DTB3.csv>
"""
import sys, json, pathlib
HERE = pathlib.Path(__file__).resolve().parent
src = open(HERE / 'topn_vote.py').read().split("res = {'设计期")[0]
g = {'__file__': str(HERE / 'topn_vote.py'), '__name__': 'x'}; exec(src, g)
import numpy as np, pandas as pd
A_LVL, US_RMB, bond, cash, stats, votes = g['A_LVL'], g['US_RMB'], g['bond'], g['cash'], g['stats'], g['votes']

def slot_tier(lvl, parent, N, bret, cret, cost=0.002):
    cal = lvl.index; r = lvl.pct_change().fillna(0).values; K = lvl.shape[1]; pi = list(lvl.columns).index(parent)
    me_mask = np.r_[cal.month[1:] != cal.month[:-1], True]; me = lvl[me_mask]; mom = me.shift(1) / me.shift(12) - 1
    above = me > me.rolling(10).mean()
    blvl = np.exp(np.log1p(bret.fillna(0)).cumsum()).where(bret.notna().cumsum() > 0)
    bme = blvl[me_mask]; babove = (bme > bme.rolling(10).mean()) & bme.notna()
    V, _ = votes(lvl, parent, ['均线', '宽度', 'TRIN'])
    w = np.zeros(K); wb = 0.0; wc = 1.0; out = np.zeros(len(cal)); turn = 0.0; pending = None; br, cr = bret.fillna(0).values, cret.values; nstress = 0
    for t in range(len(cal)):
        if pending is not None:
            tgt, tb, tc = pending; tr = np.abs(tgt - w).sum() + abs(tb - wb); turn += tr; cst = cost * tr; w, wb, wc = tgt, tb, tc; pending = None
        else: cst = 0.0
        gg = (w * r[t]).sum() + wb * br[t] + wc * cr[t]; out[t] = (1 + gg) * (1 - cst) - 1
        G = 1 + gg; w = w * (1 + r[t]) / G; wb = wb * (1 + br[t]) / G; wc = wc * (1 + cr[t]) / G
        if me_mask[t]:
            d = cal[t]; sc = mom.loc[d].values.astype(float); ok = np.isfinite(sc); tgt = np.zeros(K)
            if not ok.any(): tgt[pi] = 1.0
            else:
                if not bool(above.loc[d].values[pi]): ok &= sc > 0
                if int(V.get(d.to_period('M'), 0)) >= 2: ok &= above.loc[d].values.astype(bool); nstress += 1
                pick = [i for i in np.argsort(-np.where(ok, sc, -np.inf))[:N] if ok[i]]; tgt[pick] = 1 / N
            left = 1 - tgt.sum(); bok = bool(babove.loc[d]) if d in babove.index else False
            pending = (tgt, left if bok else 0.0, 0.0 if bok else left)
    return pd.Series(out, cal), turn, nstress

res = {'设计期': {}}
for N in (2, 3):
    a, ta, sa = slot_tier(A_LVL, 'csi300', N, bond, cash); u, tu, su = slot_tier(US_RMB, 'SPX', N, bond, cash)
    ret = 0.5 * a + 0.5 * u; st = stats(ret, '2006-01-01', {'2006–10': ('2006', '2010'), '2011–15': ('2011', '2015')})
    s = (1 + ret.loc['2006':]).cumprod()
    for k, (x0, x1) in {'2008': ('2007-06-01', '2009-12-31'), '2015': ('2015-01-01', '2015-12-31')}.items():
        x = s.loc[x0:x1]; pk = s.loc[:x.index[-1]].cummax().loc[x.index]; st[f'最低剩_{k}'] = round(float(100 * (x / pk).min()), 1)
    yr = s.resample('YE').last().pct_change(); yr.iloc[0] = s.resample('YE').last().iloc[0] - 1
    st['最差一年'] = round(float(yr.min()) * 100, 1); st['每年换手_倍'] = round((ta + tu) / 2 / (len(s) / 252), 2); st['紧张月数_A/美'] = f'{sa}/{su}'
    res['设计期'][f'前{N} 分级要求'] = st
old = json.load(open('results/v6-preflight/topn-vote2.json'))
for k, v in old['设计期'].items():
    if k.startswith('前2') or k.startswith('参照'): res['设计期'][k] = v
# 长历史
lt = "\n".join(open(HERE / "topn_vote.py").read().split("# 长历史")[1].split("dfn = json.load")[0].split("\n")[1:])
f = dict(g); exec(lt, f)
X, mom, above, rf, COST, blow = f['X'], f['mom'], f['above'], f['rf'], f['COST'], f['blow']; ALL = list(X.columns)
def run_tier(N):
    wp = pd.Series(0.0, index=ALL); out = []
    for i in range(12, len(X) - 1):
        t, nx = X.index[i], X.index[i + 1]; sc = mom.loc[t, ALL]; ok = sc.notna()
        if not above.loc[t, 'MKT']:
            ok &= sc > 0
            if blow.loc[t]: ok &= above.loc[t, ALL]
        pick = sc[ok].nlargest(N).index; w = pd.Series(0.0, index=ALL); w[pick] = 1 / N
        wf = 1 - w.sum(); tr = (w - wp).abs().sum(); wp = w
        out.append((nx, float((w * X.loc[nx].fillna(0)).sum() + wf * rf.loc[nx] - COST * tr), tr))
    return pd.DataFrame(out, columns=['t', 'r', 'tr']).set_index('t')
L = {f'前{N} 分级要求': f['lst'](run_tier(N)) for N in (3, 5)}
d3 = run_tier(3).loc['2016':]; L['前3 分级要求 2016–2026 逐年'] = ((1 + d3['r']).groupby(d3.index.year).prod() - 1).round(3).to_dict()
for k, v in old['长历史'].items(): L[k] = v
res['长历史'] = L
json.dump(res, open('results/v6-preflight/topn-tiered.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(pd.DataFrame(res['设计期']).T.to_string())
print(pd.DataFrame({k: v for k, v in L.items() if '逐年' not in k}).T.to_string()); print(L['前3 分级要求 2016–2026 逐年'])
