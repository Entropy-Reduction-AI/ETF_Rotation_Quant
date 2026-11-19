"""D38 第 42 行（回看速度随市场状态）与第 43 行（A 股特性诊断、按市场学习挑选把握 q）。
用法：python -I scripts/preflight/topn_speed.py <49_Industry_Portfolios.csv> <DTB3.csv>
"""
import sys, json, math, pathlib, warnings
warnings.filterwarnings('ignore')
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parents[1]
FFP, DTBP = sys.argv[1], sys.argv[2]
import numpy as np, pandas as pd

# ---------- 载入：沿用第 39 行（A 股按发布日校正）的全部数据与函数 ----------
G = {'__file__': str(HERE / 'a_official.py'), '__name__': 'x'}; sys.argv = ['x', FFP, DTBP]
exec(open(HERE / 'a_official.py').read().split("res = {'每年末")[0], G)
A, US_RMB, bond, cash, stats, summ, votes, conf, Phi = G['A'], G['US_RMB'], G['bond'], G['cash'], G['stats'], G['summ'], G['votes'], G['conf'], G['Phi']
X, rf = G['f']['X'], G['f']['rf']; COST = 0.002
RULES = ('R0', 'R1', 'R2')
STATES = ('牛', '回调', '熊', '反弹')

def scores(lvl, parent):
    """月末点位 → 三种速度的打分与母指数状态（全部只用到 t 为止的数据）。"""
    s12 = lvl.shift(1) / lvl.shift(12) - 1; s6 = lvl.shift(1) / lvl.shift(6) - 1; s1 = lvl / lvl.shift(1) - 1
    slow = (lvl[parent] / lvl[parent].shift(12) - 1) > 0; fast = s1[parent] > 0
    st = pd.Series(np.select([slow & fast, slow & ~fast, ~slow & ~fast], ['牛', '回调', '熊'], '反弹'), lvl.index)
    st[lvl[parent].shift(12).isna()] = None
    r12, r1 = s12.rank(axis=1, pct=True), s1.where(s12.notna()).rank(axis=1, pct=True)
    mid = (r12 + r1) / 2
    r2 = r12.where(st.isin(['牛', '熊']), mid, axis=0).where(s12.notna())
    return {'R0': s12, 'R1': s6, 'R2': r2, 'S1': s1}, st

def tstat(x):
    x = pd.Series(x).dropna(); return round(float(x.mean() / x.std(ddof=1) * math.sqrt(len(x))), 2) if len(x) > 2 else None

# ---------- ① ② 美国长历史 ----------
lvlL = (1 + X.fillna(0)).cumprod().where(X.notna().cumsum() > 0)
SC, ST = scores(lvlL, 'MKT'); s12 = SC['R0']
above = lvlL > lvlL.rolling(10).mean(); C = [c for c in X.columns if c != 'MKT']
b1 = above[C].where(lvlL[C].rolling(10).count() == 10).mean(axis=1); blow = b1 <= b1.expanding(min_periods=24).quantile(1 / 3)
ALL = list(X.columns)

def run_long(rule, mode, qmode=False, prior_q=None, end=None):
    sc_all = SC[rule]; wp = pd.Series(0.0, index=ALL); out = []; hist = []; pend = None; qh = []; qpend = None; qlog = {}
    idx = X.index if end is None else X.loc[:end].index
    for i in range(12, len(idx) - 1):
        t, nx = idx[i], idx[i + 1]
        if pend is not None: hist.append(pend); pend = None
        if qpend is not None: qh.append(qpend); qpend = None
        sc = sc_all.loc[t, ALL]; ok = sc.notna() & s12.loc[t, ALL].notna(); pbelow = not bool(above.loc[t, 'MKT']); stress = pbelow and bool(blow.loc[t])
        raw = sc[ok].nlargest(3).index
        if mode == 'phi' and pbelow: ok &= s12.loc[t, ALL] > 0
        pick = sc[ok].nlargest(3).index; frac = conf(hist) if (mode == 'phi' and stress) else 1.0
        q = conf(qh, prior=prior_q) if qmode else 1.0; qlog[t] = q
        w = pd.Series(0.0, index=ALL)
        if len(pick): w[pick] = frac * q / len(pick)
        w['MKT'] += frac * (1 - q) if qmode else 0.0
        wf = 1 - w.sum(); tr = (w - wp).abs().sum(); wp = w
        out.append((nx, float((w * X.loc[nx].fillna(0)).sum() + wf * rf.loc[nx] - COST * tr), tr, ST.loc[t], float(X.loc[nx, raw].mean() - X.loc[nx, 'MKT']) if len(raw) else np.nan))
        if stress and len(raw): pend = float(X.loc[nx, raw].mean())
        if len(raw): qpend = float(X.loc[nx, raw].mean() - X.loc[nx, 'MKT'])
    d = pd.DataFrame(out, columns=['t', 'r', 'tr', 'state', 'ex']).set_index('t')
    run_long.qh = qh; run_long.qlog = pd.Series(qlog)
    return d
SEG = {'全程': ('1955', '2026'), '1955–1979': ('1955', '1979'), '1980–1999': ('1980', '1999'), '2000–2015': ('2000', '2015'), '2016–2026': ('2016', '2026')}
mk = X['MKT']
def lst(d):
    o = {}
    for k, (a, b) in SEG.items():
        x = d.loc[a:b, 'r']; nav = (1 + x).cumprod(); m = (1 + mk.reindex(x.index)).prod() ** (12 / len(x)) - 1
        o[k] = f"{round(float(nav.iloc[-1] ** (12 / len(x)) - 1) * 100, 2)}% / {round(float(100 * (nav / nav.cummax()).min()), 1)} / 比全市场 {round(float(nav.iloc[-1] ** (12 / len(x)) - 1 - m) * 100, 2):+}"
    o['每年换手_倍'] = round(float(d['tr'].mean() * 12), 2); return o

res = {'说明': '年化 / 100 万最低剩（万） / 比全市场每年多几个点；单边 0.2%'}
L = {}; D0 = {}
for rule in RULES:
    d = run_long(rule, 'none'); D0[rule] = d.loc['1955':]; L[f'{rule} 不设防守'] = lst(d.loc['1955':])
for rule in RULES:
    L[f'{rule} 按把握调节'] = lst(run_long(rule, 'phi').loc['1955':])
dq = run_long('R0', 'phi', qmode=True); L['R0 按把握调节 + 挑选把握 q（第 43 行 A2）'] = lst(dq.loc['1955':])
L['R0 + q：q 的年末样例'] = {str(k): round(v, 2) for k, v in run_long.qlog.loc['1955':].groupby(run_long.qlog.loc['1955':].index.year).last().iloc[::7].items()}
L['一直持有全市场'] = lst(pd.DataFrame({'r': mk.loc['1955':], 'tr': 0.0}))
res['① ② 美国 49 行业 1955–2026，前 3'] = L

# 按状态拆开：前 3（未设防守、未过滤）下月比全市场多多少，年化、t 值、月数
S = {}
for rule in RULES:
    d = D0[rule]; o = {}
    for s in STATES:
        x = d.loc[d['state'] == s, 'ex']; o[s] = f"{round(float(x.mean()) * 1200, 1):+} 点（t {tstat(x)}，{len(x)} 个月）"
    for k, (a, b) in list(SEG.items())[1:]:
        x = d.loc[a:b]; o[k] = {s: round(float(x.loc[x['state'] == s, 'ex'].mean()) * 1200, 1) for s in STATES}
    S[rule] = o
S['状态出现的比例'] = {s: round(float((D0['R0']['state'] == s).mean()), 2) for s in STATES}
res['① 按母指数状态拆开（前 3 比全市场，年化点数）'] = S

# ---------- ③ 设计期整套系统 ----------
X0 = X.loc[:'1998-12']; US_PRIOR = G['US_PRIOR']
run_long('R0', 'phi', qmode=True, end='1998-12'); US_QPRIOR = list(run_long.qh)
def slot(lvl, parent, N, bret, cret, prior, rule, qmode=False, qprior=None):
    cal = lvl.index; r = lvl.pct_change().fillna(0).values; K = lvl.shape[1]; cols = list(lvl.columns); pi = cols.index(parent)
    me_mask = np.r_[cal.month[1:] != cal.month[:-1], True]; me = lvl[me_mask]
    SCd, STd = scores(me, parent); m12 = SCd['R0']; sc_all = SCd[rule]; above = me > me.rolling(10).mean(); mnx = me.pct_change().shift(-1)
    blvl = np.exp(np.log1p(bret.fillna(0)).cumsum()).where(bret.notna().cumsum() > 0); bme = blvl[me_mask]; babove = (bme > bme.rolling(10).mean()) & bme.notna()
    V, _ = votes(lvl, parent, ['均线', '宽度', 'TRIN'])
    w = np.zeros(K); wb = 0.0; wc = 1.0; out = np.zeros(len(cal)); turn = 0.0; pending = None; br, cr = bret.fillna(0).values, cret.values
    hist = []; pend = None; qh = []; qpend = None; qlog = {}
    for t in range(len(cal)):
        if pending is not None:
            tgt, tb, tc = pending; tr = np.abs(tgt - w).sum() + abs(tb - wb); turn += tr; cst = COST * tr; w, wb, wc = tgt, tb, tc; pending = None
        else: cst = 0.0
        gg = (w * r[t]).sum() + wb * br[t] + wc * cr[t]; out[t] = (1 + gg) * (1 - cst) - 1
        Gx = 1 + gg; w = w * (1 + r[t]) / Gx; wb = wb * (1 + br[t]) / Gx; wc = wc * (1 + cr[t]) / Gx
        if me_mask[t]:
            d = cal[t]
            if pend is not None: hist.append(pend); pend = None
            if qpend is not None: qh.append(qpend); qpend = None
            sc = sc_all.loc[d].values.astype(float); ok = np.isfinite(sc) & np.isfinite(m12.loc[d].values.astype(float)); tgt = np.zeros(K)
            p = conf(hist, prior=prior); q = conf(qh, prior=qprior) if qmode else 1.0; qlog[d] = q
            if not ok.any(): tgt[pi] = 1.0
            else:
                raw = [i for i in np.argsort(-np.where(ok, sc, -np.inf))[:N] if ok[i]]
                if not bool(above.loc[d].values[pi]): ok &= m12.loc[d].values > 0
                stress = int(V.get(d.to_period('M'), 0)) >= 2; frac = p if stress else 1.0
                pick = [i for i in np.argsort(-np.where(ok, sc, -np.inf))[:N] if ok[i]]
                tgt[pick] = frac * q / N
                if qmode: tgt[pi] += frac * (1 - q)
                v = mnx.loc[d].values
                if stress and raw and np.isfinite(v[raw]).all(): pend = float(np.mean(v[raw]))
                if raw and np.isfinite(v[raw]).all() and np.isfinite(v[pi]): qpend = float(np.mean(v[raw]) - v[pi])
            left = 1 - tgt.sum(); bok = bool(babove.loc[d]) if d in babove.index else False
            pending = (tgt, left if bok else 0.0, 0.0 if bok else left)
    return pd.Series(out, cal), turn, pd.Series(qlog)
Dz = {}
for rule in RULES:
    a, ta, _ = slot(A, 'csi300', 3, bond, cash, None, rule); u, tu, _ = slot(US_RMB, 'SPX', 3, bond, cash, US_PRIOR, rule)
    Dz[f'{rule}（美股 60%）'] = summ(0.4 * a + 0.6 * u, ta, tu)
    Dz[f'{rule} A 股名额单独'] = stats(a, '2006-01-01', {'2006–10': ('2006', '2010'), '2011–15': ('2011', '2015')})
a, ta, qa = slot(A, 'csi300', 3, bond, cash, None, 'R0', True, None); u, tu, qu = slot(US_RMB, 'SPX', 3, bond, cash, US_PRIOR, 'R0', True, US_QPRIOR)
Dz['R0 + 挑选把握 q（美股 60%）'] = summ(0.4 * a + 0.6 * u, ta, tu)
Dz['R0 + q A 股名额单独'] = stats(a, '2006-01-01', {'2006–10': ('2006', '2010'), '2011–15': ('2011', '2015')})
qa.index = pd.DatetimeIndex(qa.index); qu.index = pd.DatetimeIndex(qu.index)
Dz['A 股挑选把握 q（年末）'] = {str(k): round(v, 2) for k, v in qa.groupby(qa.index.year).last().items()}
Dz['美股挑选把握 q（年末）'] = {str(k): round(v, 2) for k, v in qu.groupby(qu.index.year).last().items()}
Dz['参照 一直持有沪深300'] = stats(A['csi300'].pct_change().fillna(0), '2006-01-01', {'2006–10': ('2006', '2010'), '2011–15': ('2011', '2015')})
res['③ 设计期整套（A 股按发布日校正，美股 60%，前 3）'] = Dz

# ---------- A1 诊断：前 3 对母指数的月超额，按速度和状态 ----------
def diag(lvl, parent, a, b, mincand):
    cal = lvl.index; me = lvl[np.r_[cal.month[1:] != cal.month[:-1], True]]
    SCd, STd = scores(me, parent); nxt = me.pct_change().shift(-1); o = {}
    for nm, key in (('12−1', 'R0'), ('6−1', 'R1'), ('上月涨幅', 'S1'), ('R2 随状态', 'R2')):
        sc = SCd[key].where(SCd['R0'].notna()); ex = []; sts = []
        for d in me.loc[a:b].index:
            s = sc.loc[d].dropna()
            if len(s) < mincand or not np.isfinite(nxt.loc[d, parent]): continue
            top = s.nlargest(3).index; v = nxt.loc[d, top]
            if v.isna().any(): continue
            ex.append(float(v.mean() - nxt.loc[d, parent])); sts.append(STd.loc[d])
        e = pd.Series(ex, index=sts) if ex else pd.Series(dtype=float)
        o[nm] = {'全部': f"{round(float(e.mean()) * 1200, 1):+} 点（t {tstat(e)}，{len(e)} 个月）"} | {s: f"{round(float(e[e.index == s].mean()) * 1200, 1):+}（{int((e.index == s).sum())}）" for s in STATES if (e.index == s).any()}
    return o
res['A1 前 3 比母指数（年化点数，t 值，月数）'] = {'A 股 2011-08 → 2015-12（≥5 个候选的月份）': diag(A, 'csi300', '2011-08', '2015-11', 5),
                                          '美股 14 个候选 2000–2015': diag(US_RMB, 'SPX', '2000-01', '2015-11', 5)}
json.dump(res, open(ROOT / 'results/v6-preflight/topn-speed.json', 'w'), ensure_ascii=False, indent=1, default=str)
for k, v in res.items():
    print('==', k)
    if isinstance(v, dict):
        for kk, vv in v.items(): print(' ', kk, ':', vv)
