"""D38 第 22、23 行：市场内 Top N 增强（母指数也是候选，可选均线门槛）与整套系统（A 股名额 50% + 美股名额 50%）。
用法：python scripts/preflight/topn_system.py results/v6-preflight
"""
import sys, json, sqlite3, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'scripts/preflight'))
OUT = pathlib.Path(sys.argv[1]); sys.argv = [sys.argv[0], '/tmp/simout']
import numpy as np, pandas as pd, sim
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets
from src.v4.engine.pool import load_mid
from src.v6.guard import DESIGN_END_TEXT, load_end_text
END = load_end_text()

m = Markets(load_spec()).get('index', t4=False, allow_substitute=True, end=END, allow_after=END > DESIGN_END_TEXT)
P = m.signal.loc[:END]; P = P[P[['csi300', 'spx', 'ndx100']].notna().all(axis=1)]; idx = P.index
cash = P['cash'].fillna(0); bond = P['cgb-10y']
A_C = ['csi300'] + [c for c in P.columns if c.startswith('allshare-')] + ['csi500', 'csi1000', 'csi-dividend', 'chinext']
A_LVL = np.exp(np.log1p(P[A_C].fillna(0)).cumsum()).where(P[A_C].notna().cumsum() > 0)

con = sqlite3.connect(ROOT / 'data/market.sqlite')
US_C = {'SPX': '标普500', 'NDX': '纳指100', 'DJIA': '道指', 'SOX': '费城半导体', 'NBI': '纳斯达克生物科技',
        'XLK': '科技', 'XLV': '医疗', 'XLE': '能源', 'XLY': '可选消费', 'XLP': '必需消费', 'XLF': '金融', 'XLI': '工业', 'XLB': '材料', 'XLU': '公用'}
usd = load_mid(con, 'USDCNY', END, filled=True)
def us_level(code, rmb):
    s = pd.read_sql_query("SELECT date, close FROM bars WHERE code=? AND adj='raw' AND close>0 AND date<=? ORDER BY date", con, params=(code, END))
    s = pd.Series(s['close'].values, pd.to_datetime(s['date'])); s = s[~s.index.duplicated(keep='last')]
    if rmb: s = s * usd.reindex(s.index.union(usd.index)).ffill().reindex(s.index)
    return s
def us_frame(rmb, cal):
    return pd.DataFrame({k: us_level(k, rmb).reindex(cal.union(us_level(k, rmb).index)).ffill().reindex(cal) for k in US_C})

def slot(lvl, parent, N, gate, bret, cret, cost=0.001):
    """一个名额：月末按 12−1 取前 N（母指数也是候选），可选门槛；选不满的放国债（国债跌破均线放现金）。返回逐日收益、换手。"""
    cal = lvl.index; r = lvl.pct_change().fillna(0).values; K = lvl.shape[1]
    me_mask = np.r_[cal.month[1:] != cal.month[:-1], True]
    me = lvl[me_mask]; mom = (me.shift(1) / me.shift(12) - 1); above = me > me.rolling(10).mean()
    blvl = np.exp(np.log1p(bret.fillna(0)).cumsum()).where(bret.notna().cumsum() > 0)
    bme = blvl[me_mask]; babove = (bme > bme.rolling(10).mean()) & bme.notna()
    w = np.zeros(K); wb = 0.0; wc = 1.0; out = np.zeros(len(cal)); turn = 0.0; pending = None
    br, cr = bret.fillna(0).values, cret.values
    for t in range(len(cal)):
        if pending is not None:
            tgt, tb, tc = pending; tr = np.abs(tgt - w).sum() + abs(tb - wb)
            turn += tr; cst = cost * tr; w, wb, wc = tgt, tb, tc; pending = None
        else: cst = 0.0
        g = (w * r[t]).sum() + wb * br[t] + wc * cr[t]
        out[t] = (1 + g) * (1 - cst) - 1
        G = 1 + g; w = w * (1 + r[t]) / G; wb = wb * (1 + br[t]) / G; wc = wc * (1 + cr[t]) / G
        if me_mask[t] and cal[t] in mom.index:
            sc = mom.loc[cal[t]].values.astype(float); ok = np.isfinite(sc)
            if gate: ok &= above.loc[cal[t]].values.astype(bool)
            tgt = np.zeros(K)
            if ok.any():
                pick = np.argsort(-np.where(ok, sc, -np.inf))[:N]; pick = [i for i in pick if ok[i]]
                tgt[pick] = 1 / N
            if not np.isfinite(mom.loc[cal[t]].values.astype(float)).any():
                tgt = np.zeros(K); tgt[list(lvl.columns).index(parent)] = 1.0   # 预热期：拿母指数
            left = 1 - tgt.sum(); bok = bool(babove.loc[cal[t]]) if cal[t] in babove.index else False
            pending = (tgt, left if bok else 0.0, 0.0 if bok else left)
    return pd.Series(out, cal), turn

def stats(ret, start, segs):
    s = (1 + ret.loc[start:]).cumprod(); yrs = len(s) / 252; o = {}
    o['年化'] = round(float(s.iloc[-1] ** (1 / yrs) - 1) * 100, 2)
    o['最低剩'] = round(float(100 * (s / s.cummax()).min()), 1)
    for k, (a, b) in segs.items():
        x = (1 + ret.loc[a:b]).cumprod(); o[f'年化_{k}'] = round(float(x.iloc[-1] ** (252 / len(x)) - 1) * 100, 2)
    return o

res = {'第22行 名额内': {}, '第23行 整套系统': {}}
# ---- 第 22 行：每个名额单独，和一直持有母指数比 ----
us_usd = us_frame(False, pd.DatetimeIndex(sorted(set(us_level('SPX', False).index))))
us_usd = us_usd.loc['1999-01-01':]
us_cash = pd.Series(0.0, us_usd.index); us_bond = pd.Series(np.nan, us_usd.index)
for name, lvl, parent, start, segs, b, c in (
        ('美股', us_usd, 'SPX', '2001-01-01', {'2001–05': ('2001', '2005'), '2006–10': ('2006', '2010'), '2011–15': ('2011', '2015')}, us_bond, us_cash),
        ('A股', A_LVL, 'csi300', '2006-01-01', {'2006–10': ('2006', '2010'), '2011–15': ('2011', '2015')}, bond, cash)):
    hold = lvl[parent].pct_change().fillna(0); base = stats(hold, start, segs); rows = {'一直持有母指数': base}
    pg, tg = slot(lvl[[parent]], parent, 1, True, b, c); st = stats(pg, start, segs)
    st['每年换手_倍'] = round(tg / (len(pg.loc[start:]) / 252), 2); st['比母指数_年化点'] = round(st['年化'] - base['年化'], 2)
    rows['母指数+门槛（不挑选）'] = st
    if name == 'A股':                                   # 看完结果后加的拆分：去掉规模指数，只留行业和红利
        sub = lvl[[c for c in lvl.columns if c not in ('csi500', 'csi1000', 'chinext')]]
        for N in (2, 3):
            ret, tu = slot(sub, parent, N, True, b, c); st = stats(ret, start, segs)
            st['每年换手_倍'] = round(tu / (len(ret.loc[start:]) / 252), 2); st['比母指数_年化点'] = round(st['年化'] - base['年化'], 2)
            rows[f'前{N}+门槛（去掉中证500/1000/创业板）'] = st
    for gate in (False, True):
        for N in (1, 2, 3):
            for cost in (0.001, 0.002):
                ret, tu = slot(lvl, parent, N, gate, b, c, cost)
                st = stats(ret, start, segs); st['每年换手_倍'] = round(tu / (len(ret.loc[start:]) / 252), 2)
                st['比母指数_年化点'] = round(st['年化'] - base['年化'], 2)
                rows[f'前{N}{"+门槛" if gate else ""}{" 成本0.2%" if cost == 0.002 else ""}'] = st
    res['第22行 名额内'][name] = rows
# ---- 第 23 行：整套系统（人民币，A 股日历） ----
US_RMB = us_frame(True, idx)
SEGS = {'2006–10': ('2006', '2010'), '2011–15': ('2011', '2015')}
def system(N, gate, cost, parent_only=False):
    AL, UL = (A_LVL[['csi300']], US_RMB[['SPX']]) if parent_only else (A_LVL, US_RMB)
    a, ta = slot(AL, 'csi300', N, gate, bond, cash, cost); u, tu = slot(UL, 'SPX', N, gate, bond, cash, cost)
    ret = 0.5 * a + 0.5 * u; st = stats(ret, '2006-01-01', SEGS)
    s = (1 + ret.loc['2006':]).cumprod()
    for k, (x0, x1) in {'2008': ('2007-06-01', '2009-12-31'), '2015': ('2015-01-01', '2015-12-31')}.items():
        x = s.loc[x0:x1]; pk = s.loc[:x.index[-1]].cummax().loc[x.index]; st[f'最低剩_{k}'] = round(float(100 * (x / pk).min()), 1)
    yr = s.resample('YE').last().pct_change(); yr.iloc[0] = s.resample('YE').last().iloc[0] - 1
    st['最差一年'] = round(float(yr.min()) * 100, 1); st['每年换手_倍'] = round((ta + tu) / 2 / (len(s) / 252), 2)
    return st
us2 = (P['ndx100'] + P['spx']) / 2; lr2 = np.log1p(np.column_stack([P['csi300'].values, us2.values]))[None]
bnd = np.where(bond.notna(), bond.fillna(0), cash)
for k, kw in (('基准（美股30%）', dict(s_us=0.30, kind='K0')), ('增强基准（K2A 美股50%）', dict(s_us=0.50, kind='K2A', bond=bnd))):
    ret = pd.Series(sim.run(lr2, **kw)[0][0], idx).pct_change().fillna(0); st = stats(ret, '2006-01-01', SEGS)
    s = (1 + ret.loc['2006':]).cumprod()
    for kk, (x0, x1) in {'2008': ('2007-06-01', '2009-12-31'), '2015': ('2015-01-01', '2015-12-31')}.items():
        x = s.loc[x0:x1]; pk = s.loc[:x.index[-1]].cummax().loc[x.index]; st[f'最低剩_{kk}'] = round(float(100 * (x / pk).min()), 1)
    yr = s.resample('YE').last().pct_change(); yr.iloc[0] = s.resample('YE').last().iloc[0] - 1; st['最差一年'] = round(float(yr.min()) * 100, 1)
    res['第23行 整套系统'][k] = st
res['第23行 整套系统']['两个母指数各半+门槛（不挑选）'] = system(1, True, 0.001, parent_only=True)
for gate in (False, True):
    for N in (1, 2, 3):
        res['第23行 整套系统'][f'前{N}{"+门槛" if gate else ""}'] = system(N, gate, 0.001)
res['第23行 整套系统']['前2+门槛 成本0.2%'] = system(2, True, 0.002)
res['第23行 整套系统']['前3+门槛 成本0.2%'] = system(3, True, 0.002)
res['第23行 整套系统'] = {k: v for k, v in res['第23行 整套系统'].items() if v is not None}
json.dump(res, open(OUT / 'topn-slot.json', 'w'), ensure_ascii=False, indent=1)
json.dump(res['第23行 整套系统'], open(OUT / 'topn-system.json', 'w'), ensure_ascii=False, indent=1)
for k, v in res['第22行 名额内'].items():
    print('==', k); print(pd.DataFrame(v).T.to_string())
print('== 整套系统'); print(pd.DataFrame(res['第23行 整套系统']).T.to_string())
