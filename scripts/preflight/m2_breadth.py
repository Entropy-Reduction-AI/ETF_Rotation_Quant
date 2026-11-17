"""D38 第 17、19 行 M2：候选扩容。≤2015，口径同 a2_vs_k2a.py（月末 10 个月均线门槛，次日调仓，单边 0.1%，单个名额 ≤ 2/5）。
名额 = 一组同类风险（组内过门槛的成员等分该名额）。
用法：python scripts/preflight/m2_breadth.py results/v6-preflight
"""
import sys, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
OUT = pathlib.Path(sys.argv[1])
import numpy as np, pandas as pd
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets
COST = 0.001
m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
ALL = ['csi300', 'csi-dividend', 'csi500', 'spx', 'ndx100', 'hsi', 'cgb-10y', 'gold']
R = m.signal.loc[:'2015-12-31', ALL + ['cash']]; R = R[R[['csi300', 'spx', 'ndx100']].notna().all(axis=1)]
idx = R.index; cash = R['cash'].fillna(0).values

def run(groups, mode):
    """groups：[(名称, [成员], 角色)]，角色 risk / def。mode：realloc（所有名额同台）或 r3（防守名额只接剩下的钱，国债优先）。"""
    legs = [c for _, mem, _ in groups for c in mem]; r = R[legs]; avail = r.notna().values; rv = r.fillna(0).values
    me = np.exp(np.log1p(r.fillna(0)).cumsum()).resample('ME').last()
    above = (me > me.rolling(10).mean()).reindex(idx, method='ffill').shift(1).fillna(False).values
    month = idx.to_period('M'); first = np.r_[True, month[1:] != month[:-1]]
    K = len(legs); w = np.zeros(K); wc = 1.0; v = 1.0; nav = np.empty(len(idx)); turn = 0.0; expo = np.empty(len(idx))
    pos = {c: i for i, c in enumerate(legs)}; eq = np.array([c not in ('cgb-10y', 'gold') for c in legs])
    for t in range(len(idx)):
        g = 1 + (w * rv[t]).sum() + wc * cash[t]; v *= g; w = w * (1 + rv[t]) / g; wc = wc * (1 + cash[t]) / g
        if first[t]:
            ok = above[t] & avail[t]; tgt = np.zeros(K)
            live = [(n, [pos[c] for c in mem if ok[pos[c]]], role) for n, mem, role in groups]
            slots = [x for x in live if x[1] and (mode == 'realloc' or x[2] == 'risk')]
            if slots:
                share = min(0.4, 1 / len(slots))
                for _, ids, _ in slots: tgt[ids] = share / len(ids)
            if mode == 'r3':
                left = 1 - tgt.sum()
                for n, ids, role in live:
                    if role == 'def' and n == '国债' and ids: tgt[ids] += left
            tr = np.abs(tgt - w).sum(); v *= 1 - COST * tr; turn += tr; w = tgt; wc = 1 - tgt.sum()
        nav[t] = v; expo[t] = w[eq].sum()
    s = pd.Series(nav, idx).loc['2006-01-01':]; s = s / s.iloc[0]; out = {}
    for k, (a, b) in {'2008': ('2007-06-01', '2009-12-31'), '2015': ('2015-01-01', '2015-12-31'), '全程': (None, None)}.items():
        x = s.loc[a:b]; pk = s.loc[:x.index[-1]].cummax().loc[x.index]; out[f'最低剩_{k}'] = round(float(100 * (x / pk).min()), 1)
    yrs = len(s) / 252; out['年化'] = round(float(s.iloc[-1] ** (1 / yrs) - 1) * 100, 2)
    yr = s.resample('YE').last().pct_change(); yr.iloc[0] = s.resample('YE').last().iloc[0] - 1
    out['最差一年'] = round(float(yr.min()) * 100, 1); out['平均股票仓位'] = round(float(expo[idx >= '2006-01-01'].mean()), 2)
    out['每年换手_倍'] = round(turn / yrs, 2); return out

G5 = [('A股', ['csi300'], 'risk'), ('美股', ['spx'], 'risk'), ('港股', ['hsi'], 'risk'), ('国债', ['cgb-10y'], 'def'), ('黄金', ['gold'], 'def')]
G8flat = [(c, [c], 'def' if c in ('cgb-10y', 'gold') else 'risk') for c in ALL]; G8flat = [(('国债' if n == 'cgb-10y' else n), m_, r_) for n, m_, r_ in G8flat]
G8 = [('A股', ['csi300', 'csi-dividend', 'csi500'], 'risk'), ('美股', ['spx', 'ndx100'], 'risk'), ('港股', ['hsi'], 'risk'), ('国债', ['cgb-10y'], 'def'), ('黄金', ['gold'], 'def')]
G8b = [g if g[0] != '黄金' else ('黄金', ['gold'], 'risk') for g in G8]
G5b = [g if g[0] != '黄金' else ('黄金', ['gold'], 'risk') for g in G5]
res = {'R1 5 腿': run(G5, 'realloc'), 'R1 8 腿平铺': run(G8flat, 'realloc'), 'R1 8 腿按风险归组': run(G8, 'realloc'),
       'R3a 5 腿': run(G5, 'r3'), 'R3a 8 腿按风险归组': run(G8, 'r3'), 'R3b 5 腿': run(G5b, 'r3'), 'R3b 8 腿按风险归组': run(G8b, 'r3')}
json.dump(res, open(OUT / 'm2-breadth.json', 'w'), ensure_ascii=False, indent=1)
print(pd.DataFrame(res).T.to_string())
