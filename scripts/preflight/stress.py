"""D38 预演：真实历史压力测试（第 3 版登记后追加，2026-11-17）。
用项目池 index 口径（≤2015-12-31，设计期，只作压力测试，不用来选规则）：
A 股腿 = 沪深300；美股腿 = 纳指100 与标普500 各半（人民币口径，每日再平衡）。
K0、K2、K2A 规则与 sim.py 完全相同（直接复用 sim.run），国债 3%。
输出：2008、2015 两次大跌里，100 万最低剩多少；全段最大回撤。
用法：python scripts/preflight/stress.py results/v6-preflight
"""
import sys, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
OUT = pathlib.Path(sys.argv[1])
import numpy as np, pandas as pd, importlib.util
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets
spec = importlib.util.spec_from_file_location('sim', ROOT / 'scripts/preflight/sim.py')
sys_argv = sys.argv; sys.argv = ['sim', str(OUT), '1']
sim = importlib.util.module_from_spec(spec); spec.loader.exec_module(sim); sys.argv = sys_argv

m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
R = m.signal.loc[:'2015-12-31', ['csi300', 'ndx100', 'spx']].dropna()
us = (R['ndx100'] + R['spx']) / 2
lr = np.log1p(np.column_stack([R['csi300'].values, us.values]))[None, :, :]
idx = R.index
res = {}
for k in ('K0', 'K2', 'K2A'):
    navs, expo, turn, flips = sim.run(lr, s_us=0.30, kind=k)
    nav = pd.Series(navs[0], idx)
    out = {}
    for name, a, b in (('2008', '2007-06-01', '2009-06-30'), ('2015', '2015-05-01', '2015-12-31')):
        seg = nav.loc[a:b]; pk = nav.loc[:b].loc[:seg.idxmin()].max()
        out[name] = dict(最低剩_万=round(float(seg.min() / pk * 100), 1), 回撤=round(float(seg.min() / pk - 1) * 100, 1),
                         见顶=str(nav.loc[:seg.idxmin()].idxmax().date()), 见底=str(seg.idxmin().date()))
    st = nav.loc['2006-01-01':]
    out['2006–2015 最大回撤'] = round(float((st / st.cummax() - 1).min()) * 100, 1)
    out['2006–2015 年化'] = round(float((st.iloc[-1] / st.iloc[0]) ** (252 / len(st)) - 1) * 100, 2)
    res[k] = out
json.dump(res, open(OUT / 'stress.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
