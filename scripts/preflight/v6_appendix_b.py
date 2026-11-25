"""v6 预注册附表 B：设计期（2006–2015，只用 ≤ 2015）的信号画像与收益拆分。
用法：python -I scripts/preflight/v6_appendix_b.py <49_Industry_Portfolios.csv> <DTB3.csv>
规则与 topn_dedupe.py 第 47 行一致（美股 = 旧 14 个 + REIT、A 股按发布日、前 3、去重、按把握调节、单边 0.2%）。
拆分链：BM-主 →（仓位差）BM-同仓位 →（等权倾斜）同结构等权、不设防守 →（挑选）前 3、不设防守 →（防守）v6 毛 →（成本）v6 净。
"""
import sys, json, math, pathlib, warnings
warnings.filterwarnings('ignore')
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parents[1]
FFP, DTBP = sys.argv[1], sys.argv[2]
import numpy as np, pandas as pd

G = {'__file__': str(HERE / 'topn_dedupe.py'), '__name__': 'x'}; sys.argv = ['x', FFP, DTBP]
exec(open(HERE / 'topn_dedupe.py').read().split('def slot(')[0], G)
A, US_RMB, US_NEW, TAGS, bond, cash, votes, conf, US_PRIOR = (G[k] for k in ('A', 'US_RMB', 'US_NEW', 'TAGS', 'bond', 'cash', 'votes', 'conf', 'US_PRIOR'))
US = US_RMB.copy(); US['DWRTF'] = US_NEW['DWRTF']                                   # 第 47 行：旧 14 个 + REIT
# 预注册 §1.1：10 个中证全指一级行业允许用 2011-08-02 之前的回填点位（D38 第 48 行）；主题指数仍从发布日起。
# 第 47 行（13.3%）的 A 股候选是按发布日截断的，这里两种都算：A_BF 为预注册口径（主），A 为第 47 行口径（参照）。
A_OLD = G['G']['A_OLD']; A_BF = A.copy()
for c in [c for c in A.columns if c.startswith('allshare-')]:
    A_BF[c] = A_OLD[c] / A_OLD[c].dropna().iloc[0]
END = '2015-12-31'

def slot(L, parent, N, prior, tags, mode, cost):
    """mode: v6 = 四步全；top = 前 3、不设防守；ew = 按标签等权全部可参选、不设防守。返回逐日收益、换手、逐月记录。"""
    cal = L.index; r = L.pct_change().fillna(0).values; K = L.shape[1]; cols = list(L.columns); pi = cols.index(parent)
    tg = np.array([tags.get(c, '') for c in cols], dtype=object)
    mm = np.r_[cal.month[1:] != cal.month[:-1], True]; me = L[mm]; m12 = me.shift(1) / me.shift(12) - 1; above = me > me.rolling(10).mean(); mnx = me.pct_change().shift(-1)
    blvl = np.exp(np.log1p(bond.fillna(0)).cumsum()).where(bond.notna().cumsum() > 0); bme = blvl[mm]; bab = (bme > bme.rolling(10).mean()) & bme.notna()
    V, _ = votes(L, parent, ['均线', '宽度', 'TRIN'])
    def top(sc, ok):
        out, used = [], set()
        for i in np.argsort(-np.where(ok, sc, -np.inf)):
            if not ok[i] or len(out) == N: break
            if tg[i] and tg[i] in used: continue
            out.append(i); used.add(tg[i])
        return out
    w = np.zeros(K); wb = 0.0; wc = 1.0; out = np.zeros(len(cal)); turn = 0.0; pend_t = None; br, cr = bond.fillna(0).values, cash.values
    hist = []; pend = None; log = {}
    for t in range(len(cal)):
        if pend_t is not None:
            tgt, tb, tc = pend_t; tr = np.abs(tgt - w).sum() + abs(tb - wb); turn += tr; cst = cost * tr; w, wb, wc = tgt, tb, tc; pend_t = None
        else: cst = 0.0
        g = (w * r[t]).sum() + wb * br[t] + wc * cr[t]; out[t] = (1 + g) * (1 - cst) - 1
        Gx = 1 + g; w = w * (1 + r[t]) / Gx; wb = wb * (1 + br[t]) / Gx; wc = wc * (1 + cr[t]) / Gx
        if mm[t]:
            d = cal[t]
            if pend is not None: hist.append(pend); pend = None
            sc = m12.loc[d].values.astype(float); ok = np.isfinite(sc); tgt = np.zeros(K); p = conf(hist, prior=prior)
            nv = int(V.get(d.to_period('M'), 0)); stress = nv >= 2; rec = {'票数': nv, '紧张': stress, 'p': round(p, 3), '可参选': int(ok.sum())}
            if not ok.any(): tgt[pi] = 1.0; pick = [pi]; raw = []
            else:
                raw = top(sc, ok)
                nod = [i for i in np.argsort(-np.where(ok, sc, -np.inf))[:N] if ok[i]]
                rec['去重改了名单'] = sorted(raw) != sorted(nod)
                if mode == 'ew':
                    grp = pd.Series(range(K))[ok].groupby([tg[i] or f'_{i}' for i in range(K) if ok[i]]).apply(list)
                    for members in grp: tgt[members] = 1 / len(grp) / len(members)
                    pick = list(np.where(ok)[0])
                else:
                    gate = not bool(above.loc[d].values[pi])
                    ok2 = ok & (sc > 0) if gate else ok
                    frac = p if (stress and mode == 'v6') else 1.0
                    pick = top(sc, ok2); tgt[pick] = frac / N
                    rec['母指数跌破均线'] = gate; rec['股票仓位'] = round(float(tgt.sum()), 3)
                v = mnx.loc[d].values
                if stress and raw and np.isfinite(v[raw]).all(): pend = float(np.mean(v[raw]))
            rec['持有'] = [cols[i] for i in pick] if mode != 'ew' else []
            log[d] = rec
            left = 1 - tgt.sum(); bok = bool(bab.loc[d]) if d in bab.index else False
            pend_t = (tgt, left if bok else 0.0, 0.0 if bok else left)
    return pd.Series(out, cal), turn, log

def mix_daily(a, u): return 0.4 * a + 0.6 * u
def mix_monthly(a, u, cost):
    """两个名额每月末再平衡到 40/60，调拨金额按单边 cost 计。"""
    cal = a.index; mm = np.r_[cal.month[1:] != cal.month[:-1], True]; wa, wu = 0.4, 0.6; out = np.zeros(len(cal)); reb = False
    for t in range(len(cal)):
        cst = 0.0
        if reb: cst = cost * abs(wa - 0.4); wa, wu = 0.4, 0.6; reb = False    # 调拨金额 |wa−0.4|，按单边计（预注册 §1.2）
        g = wa * a.iloc[t] + wu * u.iloc[t]; out[t] = (1 + g) * (1 - cst) - 1
        wa, wu = wa * (1 + a.iloc[t]) / (1 + g), wu * (1 + u.iloc[t]) / (1 + g)
        if mm[t]: reb = True
    return pd.Series(out, cal)
def bm(wcsi, wndx, wspx):
    rr = pd.DataFrame({'c': A['csi300'].pct_change(), 'n': US['NDX'].pct_change(), 's': US['SPX'].pct_change()}).fillna(0)
    cal = rr.index; mm = np.r_[cal.month[1:] != cal.month[:-1], True]; w0 = np.array([wcsi, wndx, wspx]); w = w0.copy(); out = np.zeros(len(cal))
    for t in range(len(cal)):
        g = float((w * rr.iloc[t].values).sum()); out[t] = g; w = w * (1 + rr.iloc[t].values) / (1 + g)
        if mm[t]: w = w0.copy()
    return pd.Series(out, cal)
SEG = {'2006–10': ('2006-01-01', '2010-12-31'), '2011–15': ('2011-01-01', '2015-12-31'), '2006–15': ('2006-01-01', '2015-12-31')}
def cagr(r, a, b):
    x = r.loc[a:b]; return float((1 + x).prod() ** (252 / len(x)) - 1) * 100

ref_a, _, _ = slot(A, 'csi300', 3, None, TAGS['a'], 'v6', 0.002)
A = A_BF
S = {}
for mode in ('ew', 'top', 'v6'):
    a, ta, la = slot(A, 'csi300', 3, None, TAGS['a'], mode, 0.0); u, tu, lu = slot(US, 'SPX', 3, US_PRIOR, TAGS['us'], mode, 0.0)
    S[mode] = (a, u, ta, tu, la, lu)
a1, ta1, la1 = slot(A, 'csi300', 3, None, TAGS['a'], 'v6', 0.002); u1, tu1, lu1 = slot(US, 'SPX', 3, US_PRIOR, TAGS['us'], 'v6', 0.002)
R = {'BM-主（70/15/15）': bm(0.7, 0.15, 0.15), 'BM-同仓位（40/30/30）': bm(0.4, 0.3, 0.3),
     '同结构等权、不设防守': mix_daily(S['ew'][0], S['ew'][1]), '前 3、不设防守': mix_daily(S['top'][0], S['top'][1]),
     'v6 毛（不计成本）': mix_daily(S['v6'][0], S['v6'][1]), 'v6 净（单边 0.2%，每日固定 60/40）': mix_daily(a1, u1),
     'v6 净（每月再平衡 60/40）': mix_monthly(a1, u1, 0.002)}
REF = mix_daily(ref_a, u1)
res = {'说明': '附表 B；设计期 2006–2015，只用 ≤ 2015 的数据；口径与预演相同（美股为人民币价格指数，A 股为预演的指数序列）；年化单位：百分点',
       '年化': {k: {s: round(cagr(v, *ab), 2) for s, ab in SEG.items()} for k, v in R.items()}}
K = list(R)
step = [('仓位差', K[1], K[0]), ('等权倾斜', K[2], K[1]), ('挑选', K[3], K[2]), ('防守', K[4], K[3]), ('成本', K[5], K[4])]
res['收益拆分（每年比 BM-主 多几个点）'] = {n: {s: round(res['年化'][x][s] - res['年化'][y][s], 2) for s in SEG} for n, x, y in step}
res['收益拆分（每年比 BM-主 多几个点）']['合计（v6 净 − BM-主）'] = {s: round(res['年化'][K[5]][s] - res['年化'][K[0]][s], 2) for s in SEG}
res['60/40 按月再平衡 − 每日固定'] = {s: round(res['年化'][K[6]][s] - res['年化'][K[5]][s], 2) for s in SEG}
res['参照：A 股一级行业按发布日截断（第 47 行口径）v6 净，每日固定 60/40'] = {s: round(cagr(REF, *ab), 2) for s, ab in SEG.items()}
res['每年换手（倍，v6 净）'] = {'A 股名额': round(ta1 / 10, 2), '美股名额': round(tu1 / 10, 2)}

def profile(log, name):
    df = pd.DataFrame.from_dict(log, orient='index'); df.index = pd.DatetimeIndex(df.index); df = df.loc['2006-01':'2015-11']
    y = df.groupby(df.index.year)
    out = {'逐年': {str(k): {'紧张月数': int(g['紧张'].sum()), '母指数跌破均线月数': int(g.get('母指数跌破均线', pd.Series(False)).fillna(False).sum()),
                            '去重改了名单的月数': int(g['去重改了名单'].fillna(False).sum()), '年末可参选': int(g['可参选'].iloc[-1]),
                            '年末把握 p': float(g['p'].iloc[-1]), '平均股票仓位': round(float(g['股票仓位'].mean()), 2)} for k, g in y}}
    cnt = pd.Series([c for h in df['持有'] for c in h]).value_counts()
    out['入选月数（前 15）'] = {k: int(v) for k, v in cnt.head(15).items()}
    out['紧张月份'] = [d.strftime('%Y-%m') for d in df.index[df['紧张']]]
    out['紧张时平均股票仓位'] = round(float(df.loc[df['紧张'], '股票仓位'].mean()), 2) if df['紧张'].any() else None
    return out
res['信号画像：A 股名额'] = profile(la1, 'A'); res['信号画像：美股名额'] = profile(lu1, 'US')
for nm, L, lg in (('A 股名额', A, la1), ('美股名额', US, lu1)):
    held = set(c for v in lg.values() for c in v['持有']); res[f'信号画像：{nm}']['从未入选'] = sorted(set(L.columns) - held)
json.dump(res, open(ROOT / 'results/v6-preflight/v6-appendix-b.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: v for k, v in res.items() if not k.startswith('信号画像')}, ensure_ascii=False, indent=1))
for k in ('信号画像：A 股名额', '信号画像：美股名额'):
    print(k); print(pd.DataFrame(res[k]['逐年']).T.to_string()); print(res[k]['入选月数（前 15）']); print('从未入选', res[k]['从未入选'], '紧张时股票仓位', res[k]['紧张时平均股票仓位'])
