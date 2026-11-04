"""v5.1 体检报告的统计（读已签收的设计期结果，不重跑策略；只用 ≤2015-12-31）。输出 results/v5.1/report/health.json 和 anystart.csv。
用法：python results/v5.1/report/health.py
"""
import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets
R = ROOT / 'results'; OUT = R / 'v5.1/report'
m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
idx_ser = m.signal[['csi300', 'spx', 'ndx100']].loc['2006':'2015']
bm = pd.read_csv(R / 'v5.1/design/benchmark.csv', parse_dates=['date']).set_index('date').benchmark.loc['2006':'2015']
def rd(f, col=None):
    d = pd.read_csv(f, parse_dates=[0], index_col=0); return (d[col] if col else d.iloc[:, 0]).loc['2006':'2015']
S = {}
for pool in ('index', 'tradable'):
    S[pool] = pd.DataFrame({'v5.1': rd(R / f'v5.1/design/{pool}/daily.csv', 'net'), 'E2 新口径': rd(R / f'v4/r5/design/B0/{pool}/net.csv'),
                            'A1': rd(R / f'v4/r5/design/A1/{pool}/net.csv'), '基准': bm, '沪深300': idx_ser.csi300, '标普500': idx_ser.spx, '纳指100': idx_ser.ndx100}).dropna(subset=['v5.1']).fillna(0)
res = {}
def cagr(r): return float((1 + r).prod() ** (252 / len(r)) - 1)
def mdd(r): n = (1 + r).cumprod(); return float((n / n.cummax() - 1).min())
for pool, d in S.items():
    mo = (1 + d).resample('ME').prod() - 1
    up, dn = mo['基准'] > 0, mo['基准'] < 0
    res[pool] = {k: dict(年化=round(cagr(d[k]) * 100, 1), 回撤=round(mdd(d[k]) * 100, 1), 波动=round(float(d[k].std() * np.sqrt(252) * 100), 1),
                         上涨月跟到=round(float(mo.loc[up, k].mean() / mo.loc[up, '基准'].mean() * 100), 0), 下跌月只跟=round(float(mo.loc[dn, k].mean() / mo.loc[dn, '基准'].mean() * 100), 0),
                         S1=round(cagr(d[k].loc['2006':'2010']) * 100, 1), S2=round(cagr(d[k].loc['2011':'2015']) * 100, 1)) for k in ('v5.1', 'E2 新口径', 'A1', '基准')}
    # 四种行情
    st = pd.read_csv(R / 'v5.1/design/month-states.csv', parse_dates=['month_end']).set_index('month_end').state
    ex = (d['v5.1'] - d['基准']); exm = mo['v5.1'] - mo['基准']
    lab = st.reindex(exm.index)
    dl = pd.Series(lab.reindex(d.index, method='bfill').values, index=d.index)
    res[pool]['四种行情'] = {s: dict(月数=int((lab == s).sum()), 合计=round(float(ex[dl == s].sum() * 100), 1), 跑赢月份=round(float((exm[lab == s] > 0).mean() * 100), 0),
                                 E2=round(float((d['E2 新口径'] - d['基准'])[dl == s].sum() * 100), 1)) for s in ('牛市', '回调', '熊市', '反弹')}
    # 任意起点
    starts = d.groupby(d.index.to_period('M')).head(1).index
    rows = []
    for yrs in (1, 3, 5):
        n = 252 * yrs
        for t in starts:
            i = d.index.get_loc(t)
            if i + n > len(d): continue
            w = d.iloc[i:i + n]; a = (1 + w).prod() ** (1 / yrs) - 1
            for c in ('基准', '沪深300', '标普500', '纳指100', 'E2 新口径', 'A1'):
                rows.append(dict(pool=pool, yrs=yrs, start=t.date(), vs=c, diff=(a['v5.1'] - a[c]) * 100))
    A = pd.DataFrame(rows); A.to_csv(OUT / f'anystart-{pool}.csv', index=False)
    res[pool]['任意起点'] = {f'{y}年': {c: dict(跑赢=round(float((g['diff'] > 0).mean() * 100), 0), 中位=round(float(g['diff'].median()), 1), 最差=round(float(g['diff'].min()), 1), 最差起点=str(g.loc[g['diff'].idxmin(), 'start']), 起点数=len(g))
                                    for c, g in A[A.yrs == y].groupby('vs')} for y in (1, 3, 5)}
    # 同行自己相对基准的任意起点（同一套起点）
    pe = {}
    for k in ('v5.1', 'E2 新口径', 'A1'):
        for yrs in (1, 3, 5):
            n = 252 * yrs; ds = []
            for t in starts:
                i = d.index.get_loc(t)
                if i + n > len(d): continue
                w = d.iloc[i:i + n]; a = (1 + w).prod() ** (1 / yrs) - 1; ds.append((a[k] - a['基准']) * 100)
            ds = pd.Series(ds); pe[f'{k}|{yrs}年'] = dict(跑赢=round(float((ds > 0).mean() * 100), 0), 中位=round(float(ds.median()), 1), 最差=round(float(ds.min()), 1))
    res[pool]['同行任意起点'] = pe
# 两次急跌
d = S['index']; dd = pd.read_csv(R / 'v5.1/design/index/daily.csv', parse_dates=['date']).set_index('date')
for name, a, b in (('2008', '2007-10-16', '2008-11-04'), ('2015', '2015-06-12', '2015-09-15')):
    w = d.loc[a:b]; res.setdefault('急跌', {})[name] = {k: round(float((1 + w[k]).prod() - 1) * 100, 1) for k in ('v5.1', 'E2 新口径', 'A1', '沪深300')}
    res['急跌'][name]['v5.1 平均风险仓位'] = round(float(dd.risk.loc[a:b].mean() * 100), 0)
(OUT / 'health.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
print(json.dumps({p: res[p]['同行任意起点'] for p in ('index', 'tradable')}, ensure_ascii=False, indent=0))
