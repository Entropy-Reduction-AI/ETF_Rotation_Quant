"""D38 第 4 版补充：U1 底仓美股比例、U2 风险均衡比例、U3 保险换成什么。
规则全部复用 sim.py（K0、K2A）；不按收益挑比例。
用法：python scripts/preflight/us_share.py results/v6-preflight
"""
import sys, json, pathlib, importlib.util
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
OUT = pathlib.Path(sys.argv[1])
import numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location('sim', ROOT / 'scripts/preflight/sim.py')
_argv = sys.argv; sys.argv = ['sim', str(OUT), '1000']
sim = importlib.util.module_from_spec(spec); spec.loader.exec_module(sim); sys.argv = _argv
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets

SHARES = (0.30, 0.40, 0.50, 0.60, 0.70, 0.80)
res = {}

# ---------- U1 ①：合成行情六种 ----------
syn = []
for scen, segs in sim.SCEN.items():
    sim.reseed(); lr = sim.build(segs); a = sim.WARM; b = lr.shape[1]; yrs = (b - a) / sim.D
    navs_bm = sim.run(lr, s_us=0.30, kind='K0')[0]
    bm = navs_bm[:, a - 1:b] / navs_bm[:, a - 1:a]; bm_ann = bm[:, -1] ** (1 / yrs) - 1
    for s in SHARES:
        for k in ('K0', 'K2A'):
            navs = sim.run(lr, s_us=s, kind=k)[0]
            nv = navs[:, a - 1:b] / navs[:, a - 1:a]
            ann = nv[:, -1] ** (1 / yrs) - 1
            syn.append(dict(行情=scen, 结构=k, 美股=f'{s:.0%}', 最低剩_万_中位=round(float(np.median(100 * (1 + sim.mdd(nv)))), 1),
                            最低剩_万_p10=round(float(np.percentile(100 * (1 + sim.mdd(nv)), 10)), 1),
                            比BM年化_p50=round(float(np.median(ann - bm_ann)) * 100, 2)))
pd.DataFrame(syn).to_csv(OUT / 'us-share-synthetic.csv', index=False)

# ---------- U1 ②：两地强弱不同的十年 ----------
spr = []
for spread in (-0.10, 0.0, 0.10, 0.20):
    sim.reseed(); lr = sim.build([sim.warm(0.20), sim.seg(10 * sim.D, 0.06, 0.06 + spread, 0.25, 0.17)])
    a = sim.WARM; b = lr.shape[1]; yrs = (b - a) / sim.D
    navs_bm = sim.run(lr, s_us=0.30, kind='K0')[0]; bm = navs_bm[:, a - 1:b] / navs_bm[:, a - 1:a]; bm_ann = bm[:, -1] ** (1 / yrs) - 1
    for s in SHARES:
        navs = sim.run(lr, s_us=s, kind='K2A')[0]; nv = navs[:, a - 1:b] / navs[:, a - 1:a]; ann = nv[:, -1] ** (1 / yrs) - 1
        spr.append(dict(美股比A股每年多涨=f'{spread:+.0%}', 美股=f'{s:.0%}', 结构='K2A',
                        比BM年化_p50=round(float(np.median(ann - bm_ann)) * 100, 2),
                        最低剩_万_中位=round(float(np.median(100 * (1 + sim.mdd(nv)))), 1)))
pd.DataFrame(spr).to_csv(OUT / 'us-share-spread.csv', index=False)

# ---------- 真实数据（项目池 ≤2015） ----------
m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
R = m.signal.loc[:'2015-12-31', ['csi300', 'ndx100', 'spx', 'cash', 'cgb-5y', 'cgb-10y']]
R = R[R[['csi300', 'ndx100', 'spx']].notna().all(axis=1)]
us = (R['ndx100'] + R['spx']) / 2
lr_real = np.log1p(np.column_stack([R['csi300'].values, us.values]))[None, :, :]
idx = R.index
cash = R['cash'].fillna(0).values
BONDS = {'固定3%': None, '现金': cash,
         '5年国债': np.where(R['cgb-5y'].notna(), R['cgb-5y'].fillna(0), cash),
         '10年国债': np.where(R['cgb-10y'].notna(), R['cgb-10y'].fillna(0), cash)}

def stress(nav):
    out = {}
    for name, a, b in (('2008', '2007-06-01', '2009-06-30'), ('2015', '2015-05-01', '2015-12-31')):
        seg = nav.loc[a:b]; pk = nav.loc[:seg.idxmin()].max()
        out[name] = round(float(seg.min() / pk * 100), 1)
    st = nav.loc['2006-01-01':]; dd = st / st.cummax() - 1; t = dd.idxmin()
    out['全段最差'] = round(float(100 * (1 + dd.min())), 1); out['最差见顶'] = str(st.loc[:t].idxmax().date()); out['最差见底'] = str(t.date())
    out['年化'] = round(float((st.iloc[-1] / st.iloc[0]) ** (252 / len(st)) - 1) * 100, 2)
    return out

bm_nav = pd.Series(sim.run(lr_real, s_us=0.30, kind='K0')[0][0], idx)
bm_ann = stress(bm_nav)['年化']
real = []
for bname, bser in BONDS.items():
    for s in SHARES:
        for k in ('K0', 'K2A'):
            if k == 'K0' and bname != '固定3%': continue
            nav = pd.Series(sim.run(lr_real, s_us=s, kind=k, bond=bser)[0][0], idx)
            x = stress(nav)
            real.append(dict(保险换成=bname if k == 'K2A' else '—', 结构=k, 美股=f'{s:.0%}', 最低剩_2008=x['2008'], 最低剩_2015=x['2015'],
                             全段最差=x['全段最差'], 最差区间=f"{x['最差见顶']}→{x['最差见底']}", 年化=x['年化'], 比BM年化=round(x['年化'] - bm_ann, 2)))
pd.DataFrame(real).to_csv(OUT / 'us-share-real.csv', index=False)

# ---------- U2：风险均衡 ----------
d = pd.DataFrame({'A': R['csi300'], 'US': us}).loc['2006-01-01':]
volA, volU = d.std() * np.sqrt(252)
navA = pd.Series(sim.run(np.log1p(np.column_stack([R['csi300'].values, us.values]))[None], s_us=0.0, kind='K2A')[0][0], idx)
volA2 = float(navA.loc['2006-01-01':].pct_change().std() * np.sqrt(252))
res['U2'] = dict(原始A股腿波动=round(float(volA) * 100, 1), 美股腿波动=round(float(volU) * 100, 1), 相关=round(float(d.corr().iloc[0, 1]), 2),
                 风险均衡美股_原始腿=round(float(volA / (volA + volU)), 3),
                 加K2A后A股腿波动=round(volA2 * 100, 1), 风险均衡美股_加K2A后=round(volA2 / (volA2 + float(volU)), 3),
                 说明='两项资产的风险均衡权重与波动成反比（与相关性无关）；只用 2006–2015 的波动率，不用收益')
res['BM真实年化_2006_2015'] = bm_ann
json.dump(res, open(OUT / 'us-share.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
