"""D38 第 13 行：A2 和 K2A 谁控回撤更好、能否合用（只拆机制，不选规则）。
三种控回撤机制：分散（多样资产）、慢趋势（10 个月均线）、快缩仓（252 日 ÷ 20 日波动，每周查，0.10 档）。
第 14 行加 R1 再分配、R2 排名：只改被门槛刷下的钱去哪。
用法：python scripts/preflight/a2_vs_k2a.py results/v6-preflight
"""
import sys, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'scripts/preflight'))
OUT = pathlib.Path(sys.argv[1]); sys.argv = [sys.argv[0], '/tmp/simout']
import numpy as np, pandas as pd, sim
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets
COST = 0.001
m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
R = m.signal.loc[:'2015-12-31', ['csi300', 'spx', 'ndx100', 'hsi', 'cgb-10y', 'gold', 'cash']]
R = R[R[['csi300', 'spx', 'ndx100']].notna().all(axis=1)]
idx = R.index; cash = R['cash'].fillna(0).values
LEGS = ['csi300', 'spx', 'hsi', 'cgb-10y', 'gold']

def five(gate=True, vol=False, mode='fixed'):
    """A2 族：五腿各 1/5；没数据的腿放现金；月末信号次日调仓；可选每周波动缩仓。"""
    r = R[LEGS]; avail = r.notna().values; rv = r.fillna(0).values
    lvl = np.exp(np.log1p(r.fillna(0)).cumsum()); me = lvl.resample('ME').last()
    above = (me > me.rolling(10).mean()).reindex(idx, method='ffill').shift(1).fillna(False).values
    lr = np.log1p(r.fillna(0))
    s20 = lr.rolling(20).std().values; s252 = lr.rolling(252).std().values
    month = idx.to_period('M'); first = np.r_[True, month[1:] != month[:-1]]
    fri = idx.dayofweek == 4
    T = len(idx); w = np.zeros(5); wc = 1.0; frac = np.ones(5); on = np.ones(5, bool)
    nav = np.empty(T); v = 1.0; turn = 0.0; expo = np.empty(T)
    for t in range(T):
        g = 1 + (w * rv[t]).sum() + wc * cash[t]
        v *= g; w = w * (1 + rv[t]) / g; wc = wc * (1 + cash[t]) / g
        trade = False
        if first[t]:
            on = above[t] if gate else np.ones(5, bool); trade = True
        if vol and fri[t] and t >= 252:
            nf = np.minimum(1, s252[t] / s20[t]); nf = np.where(np.isfinite(nf), nf, 1)
            chg = np.abs(nf - frac) > 0.10
            if chg.any(): frac = np.where(chg, nf, frac); trade = True
        if trade:
            ok = on & avail[t]
            if mode == 'fixed':
                tgt = 0.2 * ok * (frac if vol else 1)
            elif mode in ('r3a', 'r3b'):                          # 第 19 行：防守资产只接刷下来的钱
                risk = np.zeros(5, bool); risk[[0, 1, 2] + ([4] if mode == 'r3b' else [])] = True
                okr = ok & risk; cnt = max(okr.sum(), 1)
                tgt = np.where(okr, min(0.4, 1 / cnt), 0.0)
                if ok[3]: tgt[3] = 1 - tgt.sum()
            else:
                if mode == 'top3' and ok.sum() > 3:
                    mom = me.shift(1) / me.shift(12) - 1          # 12−1，按上月末
                    sc = mom.reindex(idx, method='ffill').shift(1).values[t]
                    sc = np.where(ok & np.isfinite(sc), sc, -np.inf)
                    keep = np.zeros(5, bool); keep[np.argsort(-sc)[:3]] = True; ok = ok & keep
                tgt = np.where(ok, min(0.4, 1 / max(ok.sum(), 1)), 0.0)
            v *= 1 - COST * np.abs(tgt - w).sum()   # 只对买卖的基金计成本；现金不计
            turn += np.abs(tgt - w).sum(); w = tgt.copy(); wc = 1 - tgt.sum()
        nav[t] = v; expo[t] = w[0] + w[1] + w[2]
    return nav, expo, turn

def stats(nav, expo=None, turn=None):
    s = pd.Series(nav, idx).loc['2006-01-01':]; s = s / s.iloc[0]; out = {}
    for k, (a, b) in {'2008': ('2007-06-01', '2009-12-31'), '2010–13': ('2010-01-01', '2013-12-31'),
                      '2015': ('2015-01-01', '2015-12-31'), '全程': (None, None)}.items():
        x = s.loc[a:b]; pk = s.loc[:x.index[-1]].cummax().loc[x.index]
        out[f'最低剩_{k}'] = round(float(100 * (x / pk).min()), 1)
    yrs = len(s) / 252
    out['年化'] = round(float(s.iloc[-1] ** (1 / yrs) - 1) * 100, 2)
    yr = s.resample('YE').last().pct_change(); yr.iloc[0] = s.resample('YE').last().iloc[0] - 1
    out['最差一年'] = round(float(yr.min()) * 100, 1)
    if expo is not None: out['平均股票仓位'] = round(float(pd.Series(expo, idx).loc['2006':].mean()), 2)
    if turn is not None: out['每年换手_倍'] = round(turn / yrs, 2)
    return out

us = (R['ndx100'] + R['spx']) / 2
lr2 = np.log1p(np.column_stack([R['csi300'].values, us.values]))[None]
bond = np.where(R['cgb-10y'].notna(), R['cgb-10y'].fillna(0), cash)
res = {}
n, e, *_ = sim.run(lr2, s_us=0.30, kind='K0'); res['K0 基准式（美股30%）'] = stats(n[0], e[0])
n, e, *_ = sim.run(lr2, s_us=0.50, kind='K2A', bond=bond); res['K2A（美股50%，10年国债）'] = stats(n[0], e[0])
for name, kw in (('A2 去掉均线（只有分散）', dict(gate=False)), ('A2（分散+慢趋势）', dict(gate=True)),
                 ('A2+快缩仓（三种都有）', dict(gate=True, vol=True)),
                 ('R1 再分配（过门槛的等分）', dict(gate=True, mode='realloc')),
                 ('R2 排名（过门槛里取前3）', dict(gate=True, mode='top3')),
                 ('R3a 防守只接刷下来的钱', dict(gate=True, mode='r3a')),
                 ('R3b 同上，黄金算风险腿', dict(gate=True, mode='r3b'))):
    n, e, tu = five(**kw); res[name] = stats(n, e, tu)
json.dump(res, open(OUT / 'a2-vs-k2a.json', 'w'), ensure_ascii=False, indent=1)
print(pd.DataFrame(res).T.to_string())
