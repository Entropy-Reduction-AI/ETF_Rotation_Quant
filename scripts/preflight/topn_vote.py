"""D38 第 33 行 M2：市场状态分（均线、宽度、TRIN 等权投票）调股票仓位，仓位内拿前 N 领头者。
用法：python scripts/preflight/topn_vote.py <49_Industry_Portfolios.csv> <DTB3.csv>
"""
import sys, json, pathlib, warnings
warnings.filterwarnings('ignore')
HERE = pathlib.Path(__file__).resolve().parent
FFP, DTBP = sys.argv[1], sys.argv[2]
sys.argv = [sys.argv[0], 'results/v6-preflight']
g = {'__file__': str(HERE / 'topn_system2.py'), '__name__': 'x'}; exec(open(HERE / 'topn_system2.py').read().split("res = {}")[0], g)
vs = {'__file__': str(HERE / 'volume_signals.py')}; exec(open(HERE / 'volume_signals.py').read().split("def analyse")[0], vs)
import numpy as np, pandas as pd
A_LVL, US_RMB, bond, cash, stats = g['A_LVL'], g['US_RMB'], g['bond'], g['cash'], g['stats']

def trin_t2(codes, amt, pc, pa, start):
    PX, AM, _ = vs['universe'](codes, amt, pc, pa, start); dr = PX.pct_change(); up, dn = dr > 0, dr < 0
    d = ((up.sum(axis=1) / dn.sum(axis=1).replace(0, np.nan)) / ((AM * up).sum(axis=1) / (AM * dn).sum(axis=1).replace(0, np.nan))).replace([np.inf, -np.inf], np.nan)
    d = d.clip(upper=d.quantile(0.99)).rolling(10, min_periods=7).mean().resample('ME').last()
    d.index = d.index.to_period('M'); return d
TRIN = {'csi300': trin_t2(vs['AS'], True, 'H00300', True, '2005-01-01'), 'SPX': trin_t2(vs['US'], False, 'SPX', False, '1999-01-01')}

def votes(lvl, parent, which):
    cal = lvl.index; me_mask = np.r_[cal.month[1:] != cal.month[:-1], True]; me = lvl[me_mask]; me.index = me.index.to_period('M')
    v = pd.DataFrame(index=me.index)
    v['均线'] = (me[parent] < me[parent].rolling(10).mean()).astype(float)
    b1 = (me > me.rolling(10).mean()).where(me.rolling(10).count() == 10).mean(axis=1)
    v['宽度'] = (b1 <= b1.expanding(min_periods=24).quantile(1 / 3)).where(b1.expanding(min_periods=24).count() >= 24).fillna(0).astype(float)
    t = TRIN[parent].reindex(me.index)
    v['TRIN'] = (t >= t.expanding(min_periods=24).quantile(2 / 3)).where(t.expanding(min_periods=24).count() >= 24).fillna(0).astype(float)
    return v[which].sum(axis=1), len(which)

def slot_vote(lvl, parent, N, which, bret, cret, cost=0.002, confirm=False):
    cal = lvl.index; r = lvl.pct_change().fillna(0).values; K = lvl.shape[1]; pi = list(lvl.columns).index(parent)
    me_mask = np.r_[cal.month[1:] != cal.month[:-1], True]; me = lvl[me_mask]; mom = me.shift(1) / me.shift(12) - 1
    blvl = np.exp(np.log1p(bret.fillna(0)).cumsum()).where(bret.notna().cumsum() > 0)
    bme = blvl[me_mask]; babove = (bme > bme.rolling(10).mean()) & bme.notna()
    V, n = votes(lvl, parent, which) if which else (None, 1)
    w = np.zeros(K); wb = 0.0; wc = 1.0; out = np.zeros(len(cal)); turn = 0.0; pending = None; br, cr = bret.fillna(0).values, cret.values
    log = []
    for t in range(len(cal)):
        if pending is not None:
            tgt, tb, tc = pending; tr = np.abs(tgt - w).sum() + abs(tb - wb); turn += tr; cst = cost * tr; w, wb, wc = tgt, tb, tc; pending = None
        else: cst = 0.0
        gg = (w * r[t]).sum() + wb * br[t] + wc * cr[t]; out[t] = (1 + gg) * (1 - cst) - 1
        G = 1 + gg; w = w * (1 + r[t]) / G; wb = wb * (1 + br[t]) / G; wc = wc * (1 + cr[t]) / G
        if me_mask[t]:
            d = cal[t]; sc = mom.loc[d].values.astype(float); ok = np.isfinite(sc); tgt = np.zeros(K)
            if not ok.any(): tgt[pi] = 1.0; k = 0
            else:
                pick = [i for i in np.argsort(-np.where(ok, sc, -np.inf))[:N] if ok[i]]
                k = int(V.get(d.to_period('M'), 0)) if V is not None else 0
                frac = (1.0 if k < 2 else 1 - k / n) if confirm else 1 - k / n
                tgt[pick] = frac / N
            left = 1 - tgt.sum(); bok = bool(babove.loc[d]) if d in babove.index else False
            pending = (tgt, left if bok else 0.0, 0.0 if bok else left); log.append((d, k))
    return pd.Series(out, cal), turn, pd.Series(dict(log))

def system(N, which, confirm=False):
    a, ta, la = slot_vote(A_LVL, 'csi300', N, which, bond, cash, confirm=confirm); u, tu, lu = slot_vote(US_RMB, 'SPX', N, which, bond, cash, confirm=confirm)
    ret = 0.5 * a + 0.5 * u; st = stats(ret, '2006-01-01', {'2006–10': ('2006', '2010'), '2011–15': ('2011', '2015')})
    s = (1 + ret.loc['2006':]).cumprod()
    for k, (x0, x1) in {'2008': ('2007-06-01', '2009-12-31'), '2015': ('2015-01-01', '2015-12-31')}.items():
        x = s.loc[x0:x1]; pk = s.loc[:x.index[-1]].cummax().loc[x.index]; st[f'最低剩_{k}'] = round(float(100 * (x / pk).min()), 1)
    yr = s.resample('YE').last().pct_change(); yr.iloc[0] = s.resample('YE').last().iloc[0] - 1
    st['最差一年'] = round(float(yr.min()) * 100, 1); st['每年换手_倍'] = round((ta + tu) / 2 / (len(s) / 252), 2)
    if which:
        n = len(which); exp = 1 - (la.loc['2006':] + lu.loc['2006':]) / 2 / n; st['平均股票仓位'] = round(float(exp.mean()), 2)
    return st, (la, lu, a, u)

res = {'设计期 2006–2015（美股 + A 股各半，单边 0.2%）': {}}
D = res['设计期 2006–2015（美股 + A 股各半，单边 0.2%）']; keep = {}
for N in (2, 3):
    for which, name in ((['均线', '宽度', 'TRIN'], '三票'), (['均线', '宽度'], '两票：均线+宽度'), (['均线', 'TRIN'], '两票：均线+TRIN'), ([], '不设防守')):
        st, aux = system(N, which); D[f'前{N} {name}'] = st; keep[(N, name)] = aux
old = json.load(open('results/v6-preflight/topn-system2.json'))
for k in ('前2 ③只在母指数层面', '前3 ③只在母指数层面', '参照 基准（美股30%）', '参照 增强基准（K2A 美股50%）'): D[k] = old[k]
# 每个票数下：下月母指数收益（三票版，按名额）
la, lu, a, u = keep[(2, '三票')]
by = {}
for nm, lg, lvl, par in (('A 股名额', la, A_LVL, 'csi300'), ('美股名额', lu, US_RMB, 'SPX')):
    pm = lvl[par].resample('ME').last().pct_change().shift(-1); pm.index = pm.index.to_period('M')
    x = pd.DataFrame({'k': lg.loc['2006':].values}, index=pd.DatetimeIndex(lg.loc['2006':].index).to_period('M')).join(pm.rename('nx')).dropna()
    by[nm] = {int(k): dict(月数=int(len(gg)), 下月母指数_年化=round(float(gg['nx'].mean() * 1200), 1), 下月跌超5pct概率=round(float((gg['nx'] < -0.05).mean()), 2)) for k, gg in x.groupby('k')}
res['三票版：每个票数下母指数的下月表现（设计期）'] = by

# 长历史：French 49 行业，两票（全市场均线 + 宽度）
src = open(HERE / 'topn_longhist.py').read().split("ALL = list")[0]; f = {}; sys.argv = ['x', FFP, DTBP, 'results/v6-preflight']; exec(src, f)
X, mom, above, rf, COST = f['X'], f['mom'], f['above'], f['rf'], f['COST']; ALL = list(X.columns); INDS = [c for c in ALL if c != 'MKT']
b1 = above[INDS].where(f['lvl'][INDS].rolling(10).count() == 10).mean(axis=1)
blow = (b1 <= b1.expanding(min_periods=24).quantile(1 / 3)).astype(float)
def run_vote(N, use):
    wp = pd.Series(0.0, index=ALL); out = []
    for i in range(12, len(X) - 1):
        t, nx = X.index[i], X.index[i + 1]; sc = mom.loc[t, ALL].dropna(); pick = sc.nlargest(N).index
        k = (0 if 'none' in use else (float(not above.loc[t, 'MKT']) + (float(blow.loc[t]) if '宽度' in use else 0)))
        n = 2 if '宽度' in use else 1
        if 'confirm' in use: k, n = (1, 1) if k >= 2 else (0, 1)
        w = pd.Series(0.0, index=ALL); w[pick] = (1 - k / n) / N; wf = 1 - w.sum(); tr = (w - wp).abs().sum(); wp = w
        out.append((nx, float((w * X.loc[nx].fillna(0)).sum() + wf * rf.loc[nx] - COST * tr), tr))
    return pd.DataFrame(out, columns=['t', 'r', 'tr']).set_index('t')
SEGS = {'全程': ('1955', '2026'), '1955–1979': ('1955', '1979'), '1980–1999': ('1980', '1999'), '2000–2015': ('2000', '2015'), '2016–2026': ('2016', '2026')}
def lst(d):
    o = {}
    for k, (a_, b_) in SEGS.items():
        x = d.loc[a_:b_, 'r']; nav = (1 + x).cumprod(); o[k] = f"{round(float(nav.iloc[-1] ** (12 / len(x)) - 1) * 100, 2)}% / {round(float(100 * (nav / nav.cummax()).min()), 1)}"
    o['换手'] = round(float(d['tr'].mean() * 12), 2); return o
L = {}
for N in (3, 5):
    L[f'前{N} 两票：均线+宽度'] = lst(run_vote(N, ['均线', '宽度'])); L[f'前{N} 一票：只看全市场均线（按仓位减半）'] = lst(run_vote(N, ['均线']))
dfn = json.load(open('results/v6-preflight/topn-defense.json'))
for k in ('一直持有全市场', '前3 不设防守', '前3 ③只在全市场层面', '前5 ③只在全市场层面'):
    v = dfn[k]; L[k] = {s: f"{v[s]['年化']}% / {v[s]['最低剩']}" for s in SEGS if s in v} | {'全程': f"{v['全程']['年化']}% / {v['全程']['最低剩']}", '换手': v['每年换手_倍']}
res['长历史 French 49 行业 1955–2026（年化 / 最低剩，单边 0.2%）'] = L
json.dump(res, open('results/v6-preflight/topn-vote.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(pd.DataFrame(D).T.to_string()); print(json.dumps(by, ensure_ascii=False)); print(pd.DataFrame(L).T.to_string())
