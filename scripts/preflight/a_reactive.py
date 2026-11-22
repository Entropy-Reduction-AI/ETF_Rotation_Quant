"""D38 第 54 行：A 股名额的反应式处理（B0 现规则 / B1 快速出场 / B2 结构市才挑选），三条反对意见的量，与 v2 的相关。
用法：python -I scripts/preflight/a_reactive.py <49_Industry_Portfolios.csv> <DTB3.csv>
"""
import sys, json, math, tomllib, pathlib, warnings
warnings.filterwarnings('ignore')
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parents[1]
FFP, DTBP = sys.argv[1], sys.argv[2]
import numpy as np, pandas as pd

G = {'__file__': str(HERE / 'a_official.py'), '__name__': 'x'}; sys.argv = ['x', FFP, DTBP]
exec(open(HERE / 'a_official.py').read().split("res = {'每年末")[0], G)
A_OLD, A, bond = G['A_OLD'], G['A'], G['bond']
TAGS = tomllib.load(open(ROOT / 'config/v6-preflight/sector-tags.toml', 'rb'))['a']
COST = 0.002; N = 3

def run(L, a, b):
    """L: 日点位（列 = 候选，含 csi300）。返回各规则的日收益、成本、出场记录。"""
    L = L.loc[:b]; cal = L.index; r = L.pct_change().fillna(0.0); br = bond.reindex(cal).fillna(0.0).values
    cols = list(L.columns); K = len(cols); pi = cols.index('csi300')
    grp = {}
    for j, c in enumerate(cols):
        g = TAGS.get(c, '') or f'_{c}'; grp.setdefault(g, []).append(j)
    mm = np.r_[cal.month[1:] != cal.month[:-1], True]; me_idx = np.where(mm)[0]
    me = L.iloc[me_idx]; s12 = (me.shift(1) / me.shift(12) - 1); ab = (me > me.rolling(10).mean()).where(me.rolling(10).count() == 10)
    breadth = ab.mean(axis=1); q = breadth.expanding(min_periods=24).quantile(1 / 3)
    low = (breadth <= q).astype(float).where(q.notna() & breadth.notna())
    R = r.values; Lv = L.values

    def ew_target(ok):
        t = np.zeros(K); gs = [[j for j in js if ok[j]] for js in grp.values()]; gs = [g for g in gs if g]
        for g in gs:
            for j in g: t[j] = 1 / len(gs) / len(g)
        return t

    out = {}
    for rule in ('B0', 'B1', 'B2', 'EW'):
        w = np.zeros(K); wb = 1.0; nav_r = np.zeros(len(cal)); cost = np.zeros(len(cal)); exits = []; pend = None; mstart = None; mode = {}
        for t in range(len(cal)):
            if pend is not None:
                tgt, tb = pend; tr = np.abs(tgt - w).sum() + abs(tb - wb); cost[t] = COST * tr; w, wb = tgt.copy(), tb; pend = None
            g = (w * R[t]).sum() + wb * br[t]; nav_r[t] = (1 + g) * (1 - cost[t]) - 1
            Gx = 1 + g; w = w * (1 + R[t]) / Gx; wb = wb * (1 + br[t]) / Gx
            if mm[t]:
                d = cal[t]; sc = s12.loc[d].values.astype(float); ok = np.isfinite(sc)
                if ok.sum() < 5: pend = (np.zeros(K), 1.0); mstart = None; continue
                top = [j for j in np.argsort(-np.where(ok, sc, -np.inf))[:N]]
                if rule == 'EW' or (rule == 'B2' and low.get(d) == 0.0):
                    tgt = ew_target(ok); mode[d] = 'EW'
                else:
                    tgt = np.zeros(K); tgt[top] = 1 / N; mode[d] = 'select'
                pend = (tgt, 1 - tgt.sum()); mstart = t; held = set(np.where(tgt > 0)[0]) if rule == 'B1' else set()
            elif rule == 'B1' and mstart is not None and (t - mstart) % 5 == 0 and t - mstart >= 5 and t >= 20:
                r20 = Lv[t] / Lv[t - 20] - 1; okp = np.isfinite(r20) & np.isfinite(s12.iloc[min(np.searchsorted(me_idx, mstart), len(me_idx) - 1)].values.astype(float))
                if okp.sum() < 5: continue
                med = np.nanmedian(np.where(okp, r20, np.nan)); sell = [j for j in held if np.isfinite(r20[j]) and r20[j] < med and w[j] > 1e-9]
                if sell:
                    tgt = w.copy(); tb = wb
                    for j in sell: tb += tgt[j]; tgt[j] = 0.0; held.discard(j)
                    nxt_me = me_idx[me_idx > t]; e = nxt_me[0] if len(nxt_me) else len(cal) - 1
                    for j in sell:
                        rj = Lv[e, j] / Lv[t, j] - 1; rp = np.nanmedian(np.where(okp, Lv[e] / Lv[t] - 1, np.nan))
                        exits.append((cal[t], cols[j], float(rj - rp)))
                    pend = (tgt, tb)
        out[rule] = dict(r=pd.Series(nav_r, cal), cost=pd.Series(cost, cal), exits=exits, mode=mode)
    # v2 近似：同一篮子（等权全部）做 EMA10/20 进出
    bk = out['EW']['r']; nav = (1 + bk).cumprod(); e10 = nav.ewm(span=10, adjust=False).mean(); e20 = nav.ewm(span=20, adjust=False).mean()
    inn = ((e10 > e20) & (e10.diff() > 0) & (e20.diff() > 0)).shift(1).fillna(False)      # T 日定，T+1 收盘成交 → T+2 起生效
    pos = inn.shift(1).fillna(False).astype(float); sw = pos.diff().abs().fillna(0)
    v2 = pos * bk + (1 - pos) * pd.Series(br, cal) - sw * 0.0005 * 2
    out['v2'] = dict(r=v2, pos=pos)
    out['_c300'] = r['csi300']
    return out

def mon(x): return (1 + x).groupby([x.index.year, x.index.month]).prod() - 1
def tt(x): x = pd.Series(x).dropna(); return round(float(x.mean() / x.std(ddof=1) * math.sqrt(len(x))), 2) if len(x) > 2 else None
def report(O, a, b, phases):
    M = {k: mon(O[k]['r'].loc[a:b]) for k in ('B0', 'B1', 'B2', 'EW', 'v2')}; c3 = mon(O['_c300'].loc[a:b])
    idx = pd.Index([pd.Timestamp(y, m, 1) for y, m in M['B0'].index]); M = {k: pd.Series(v.values, idx) for k, v in M.items()}; c3 = pd.Series(c3.values, idx)
    res = {}
    for k in ('B0', 'B1', 'B2', 'EW'):
        cst = O[k]['cost'].loc[a:b]
        res[k] = {'对沪深300 每年点': round(float((M[k] - c3).mean()) * 1200, 1), '对等权全部 每年点': round(float((M[k] - M['EW']).mean()) * 1200, 1),
                  '对等权 t': tt(M[k] - M['EW']), '每年成本点': round(float(cst.sum()) / ((cal_years := len(M[k]) / 12)) * 100, 2)}
    res['分阶段：对 B0 的差（每年点）'] = {}
    for ph, (pa, pb) in phases.items():
        s = slice(pd.Timestamp(pa + '-01'), pd.Timestamp(pb + '-01'))
        res['分阶段：对 B0 的差（每年点）'][ph] = {'B0 对等权': round(float((M['B0'] - M['EW']).loc[s].mean()) * 1200, 1),
                                           'B1 − B0': round(float((M['B1'] - M['B0']).loc[s].mean()) * 1200, 1), 'B2 − B0': round(float((M['B2'] - M['B0']).loc[s].mean()) * 1200, 1),
                                           '月数': int(len(M['B0'].loc[s]))}
    ex = [e for e in O['B1']['exits'] if pd.Timestamp(a) <= e[0] <= pd.Timestamp(b) + pd.offsets.MonthEnd(0)]
    yrs = len(M['B0']) / 12
    res['反对意见 ① 反复进出：B1 每年出场次数'] = round(len(ex) / yrs, 1)
    res['反对意见 ③ 卖飞：卖掉后当月剩余时间仍跑赢池中位数的比例'] = round(float(np.mean([e[2] > 0 for e in ex])), 2) if ex else None
    res['反对意见 ③ 卖飞：被卖持仓对池中位数的平均差%（负 = 卖对）'] = round(float(np.mean([e[2] for e in ex])) * 100, 2) if ex else None
    d1, d2 = (M['B1'] - M['B0']), (M['v2'] - M['EW'])
    pos = O['v2']['pos']; exd = [e[0] for e in ex]
    res['与 v2 的相关'] = {'B1−B0 与 v2−篮子 的月度相关': round(float(d1.corr(d2)), 2),
                        'B1 出场当天 v2 也在场外的比例': round(float(np.mean([pos.get(d, np.nan) == 0 for d in exd])), 2) if exd else None,
                        'v2 在场外的时间比例': round(float((pos.loc[a:b] == 0).mean()), 2),
                        'v2 − 篮子 每年点': round(float(d2.mean()) * 1200, 1)}
    res['B2 处在“挑选”模式的月份比例'] = round(float(np.mean([v == 'select' for d, v in O['B2']['mode'].items() if pd.Timestamp(a) <= d <= pd.Timestamp(b) + pd.offsets.MonthEnd(0)])), 2)
    return res

L1 = A_OLD[['csi300'] + [c for c in A_OLD.columns if c.startswith('allshare-')]]
O1 = run(L1, '2006-01', '2015-12-31')
P1 = {'2006-01 → 2007-10 大牛': ('2006-01', '2007-10'), '2007-11 → 2008-10 崩盘': ('2007-11', '2008-10'), '2008-11 → 2009-07 反弹': ('2008-11', '2009-07'),
      '2009-08 → 2014-06 结构与震荡': ('2009-08', '2014-06'), '2014-07 → 2015-11 大牛与崩盘': ('2014-07', '2015-11')}
res = {'说明': '只看挑选层（不加防守），单边 0.2%；EW = 按行业标签等权全部可参选候选；v2 = 同一篮子上的 EMA10/20 进出（近似）',
       'A 股 10 个一级行业 2006-01 → 2015-11': report(O1, '2006-01', '2015-11', P1)}
O2 = run(A, '2011-08', '2015-12-31')
P2 = {'2011-08 → 2013-12': ('2011-08', '2013-12'), '2014-01 → 2015-11': ('2014-01', '2015-11')}
res['主题池（按发布日截断）2011-08 → 2015-11'] = report(O2, '2011-08', '2015-11', P2)
json.dump(res, open(ROOT / 'results/v6-preflight/a-reactive.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
