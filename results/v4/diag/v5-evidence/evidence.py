# v5 换架构的证据（D26）。只做描述性统计，不跑任何新策略；收益只到 2015-12-31。
# 用法：python results/v4/diag/v5-evidence/evidence.py results/v4/diag/v5-evidence/evidence.json
import sys, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd
from src.v4.r5 import design as D
from src.v3.engine.spec import load_spec
R = ROOT / 'results/v4/r5'
grp = pd.read_csv(ROOT / 'results/v4/diag/data-board/out/containers.csv').set_index('id')['group'].to_dict()
m = D.prepare_market('index', t4=False, allow_substitute=True, spec=load_spec())
lv = m.levels.loc[:'2015-12-31']
out = {}
# 1) 相关性与等效独立赌注数（月收益，2006–2015）
mr = lv.resample('ME').last().pct_change().loc['2006':'2015']
A = [k for k in mr.columns if grp.get(k) == 'A 股' and mr[k].notna().sum() > 100]
allk = [k for k in mr.columns if k != 'cash' and mr[k].notna().sum() > 80]
def eff(c):
    ev = np.linalg.eigvalsh(c); ev = ev[ev > 0]; return float(ev.sum() ** 2 / (ev ** 2).sum())
ca = mr[A].corr().values
out['breadth'] = {'a_share_n': len(A), 'a_share_avg_pair_corr': round(float(ca[np.triu_indices(len(A), 1)].mean()), 3),
                  'a_share_effective': round(eff(ca), 2), 'all_n': len(allk), 'all_effective': round(eff(mr[allk].corr().fillna(0).values), 2)}
# 2) 横截面排名 IC（E2 的四回看期平均打分 → 下月收益），A 股内部 vs 大类代表
me = lv.resample('ME').last(); fwd = me.shift(-1) / me - 1
def score(d):
    i = lv.index.get_indexer([d], method='pad')[0]; out = {}
    for L in (20, 60, 120, 250):
        if i - L < 0: continue
        w = lv.iloc[i - L:i + 1]; out[L] = (w.iloc[-1] / w.iloc[0] - 1) / (w.pct_change().std() * np.sqrt(L))
    return pd.DataFrame(out).mean(axis=1)
REP = ['csi300', 'spx', 'hsi', 'cgb-10y', 'gold']
ics = {'within_a_share': [], 'across_classes': []}; ts = []
for d in me.index:
    if d < pd.Timestamp('2006-01-31') or d > pd.Timestamp('2015-11-30'): continue
    s = score(d); f = fwd.loc[d]
    for name, keys in (('within_a_share', A), ('across_classes', REP)):
        k = [x for x in keys if pd.notna(s.get(x)) and pd.notna(f.get(x))]
        if len(k) >= 4: ics[name].append(s[k].rank().corr(f[k].rank()))
    for k in REP + A:
        if pd.notna(s.get(k)) and pd.notna(f.get(k)): ts.append((k in REP, bool(s[k] > 0), float(f[k] - 0.02 / 12)))
out['cross_sectional_ic'] = {k: {'months': len(v), 'mean': round(float(np.mean(v)), 3), 't': round(float(np.mean(v) / np.std(v, ddof=1) * np.sqrt(len(v))), 2)} for k, v in ics.items()}
t = pd.DataFrame(ts, columns=['rep', 'up', 'fx']); out['time_series_trend'] = {}
for r, name in ((True, 'class_reps'), (False, 'a_share_pooled')):
    x = t[t.rep == r]; a, b = x[x.up].fx, x[~x.up].fx
    out['time_series_trend'][name] = {'up_next_month_excess_pct': round(a.mean() * 100, 2), 'down_next_month_excess_pct': round(b.mean() * 100, 2),
        't_naive': round(float((a.mean() - b.mean()) / np.sqrt(a.var() / len(a) + b.var() / len(b))), 2), 'n_up': len(a), 'n_down': len(b)}
# 3) 显著性：月度超额的 t 值
g = pd.read_csv(R / 'gate-inputs.csv', index_col=0, parse_dates=True)
rd = lambda c, p: pd.read_csv(R / f'design/{c}/{p}/net.csv', index_col=0, parse_dates=True)['net'].loc['2006':]
S = {'E2_index': rd('B0', 'index'), 'E2_tradable': rd('B0', 'tradable'), 'A1_index': rd('A1', 'index'), 'A1_tradable': rd('A1', 'tradable'), 'A2_index': rd('A2', 'index'), 'BM': g.benchmark.fillna(0).loc['2006':]}
M = {k: (1 + v).resample('ME').prod() - 1 for k, v in S.items()}
out['sharpe'] = {k: round(float((v - 0.02 / 12).mean() / (v - 0.02 / 12).std() * np.sqrt(12)), 2) for k, v in M.items()}
def tt(a, b, lo='2006', hi='2015'):
    dd = (M[a] - M[b]).loc[lo:hi]; return {'excess_pct_yr': round(float(dd.mean() * 1200), 1), 't': round(float(dd.mean() / dd.std() * np.sqrt(len(dd))), 2)}
out['t_stats'] = {'E2_index_vs_BM': tt('E2_index', 'BM'), 'E2_index_vs_BM_2009_2015': tt('E2_index', 'BM', '2009', '2015'),
                  'E2_tradable_vs_BM': tt('E2_tradable', 'BM'), 'E2_index_vs_A1_index': tt('E2_index', 'A1_index'),
                  'E2_tradable_vs_A1_tradable': tt('E2_tradable', 'A1_tradable'), 'E2_index_vs_A2_index': tt('E2_index', 'A2_index')}
json.dump(out, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False))
