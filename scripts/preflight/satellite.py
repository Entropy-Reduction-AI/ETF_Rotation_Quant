"""D38 第 12 行 S1：卫星仓压力测试。底仓 A 股 40%（K2A）+ 美股 50% + 机动 10%。
机动仓 = 项目池 ≤2015 里 2008 或 2015 回撤最深的 A 股行业/宽基，全程持有（最坏代理，不是挑选）；有无 K2A 两种。
三部分按日收益固定权重合成（近似月度再平衡），只看最低剩。
用法：python scripts/preflight/satellite.py results/v6-preflight
"""
import sys, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'scripts/preflight'))
OUT = pathlib.Path(sys.argv[1]); sys.argv = [sys.argv[0], '/tmp/simout']
import numpy as np, pandas as pd, sim
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets
m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
SAT = ['csi500', 'csi1000', 'chinext'] + [c for c in m.signal.columns if c.startswith('allshare-')]
R = m.signal.loc[:'2015-12-31', ['csi300', 'ndx100', 'spx', 'cash', 'cgb-10y'] + SAT]
R = R[R[['csi300', 'ndx100', 'spx']].notna().all(axis=1)]
us = (R['ndx100'] + R['spx']) / 2; cash = R['cash'].fillna(0).values
bond = np.where(R['cgb-10y'].notna(), R['cgb-10y'].fillna(0), cash)
def path(a, u, s, kind):
    lr = np.log1p(np.column_stack([a, u]))[None]
    return sim.run(lr, s_us=s, kind=kind, bond=bond)[0][0]
def lows(nav):
    nav = pd.Series(nav, R.index); out = {}
    for y, (a, b) in {'2008': ('2007-06-01', '2009-12-31'), '2015': ('2015-01-01', '2015-12-31'), '全程': (None, None)}.items():
        x = nav.loc[a:b]; out[y] = round(float(100 * (x / x.cummax()).min()), 1)
    return out
# 底仓 90% 内：A 40/90，美股 50/90
core = pd.Series(path(R['csi300'].values, us.values, 50 / 90, 'K2A'), R.index).pct_change().fillna(0)
dd = {c: lows(np.cumprod(1 + R[c].fillna(0).values)) for c in SAT if R[c].notna().mean() > 0.9}
worst = {y: min(dd, key=lambda c: dd[c][y]) for y in ('2008', '2015')}
res = dict(机动仓候选单独最低剩=dd, 最坏代理=worst, 组合={})
res['组合']['A50+美50（无机动，参照）'] = lows(path(R['csi300'].values, us.values, 0.5, 'K2A'))
for y, c in worst.items():
    x = R[c].fillna(0).values
    for kind in ('K0', 'K2A'):
        sat = pd.Series(path(x, x, 0.0, kind), R.index).pct_change().fillna(0)
        res['组合'][f'机动={c}（{y}最深）{"有保险" if kind == "K2A" else "无保险"}'] = lows(np.cumprod(1 + 0.9 * core.values + 0.1 * sat.values))
json.dump(res, open(OUT / 'satellite.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(res['最坏代理'], ensure_ascii=False)); [print(k, v) for k, v in res['组合'].items()]
