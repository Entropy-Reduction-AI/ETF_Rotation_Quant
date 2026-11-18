"""D38 第 38 行 S3：按把握调节防守（紧张时股票仓位 = Φ(t)，t = 领头者紧张时下月绝对收益的 t 值，只用当时已知结果）。
用法：python scripts/preflight/topn_phi.py <49_Industry_Portfolios.csv> <DTB3.csv>
"""
import sys, json, io, math, sqlite3, pathlib, warnings
warnings.filterwarnings('ignore')
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parents[1]
FFP, DTBP = sys.argv[1], sys.argv[2]
import numpy as np, pandas as pd
Phi = lambda t: 0.5 * (1 + math.erf(t / math.sqrt(2)))
COST = 0.002

def conf(hist, min_n=12, prior=None):
    """hist：已知结果的紧张月领头者下月绝对收益列表。"""
    h = list(prior or []) + list(hist)
    if len(h) < min_n: return 0.5
    a = np.array(h); sd = a.std(ddof=1)
    return Phi(a.mean() / sd * math.sqrt(len(a))) if sd > 0 else 0.5

# ---------- 月度引擎（长历史、港股） ----------
def monthly(X, parent, N, mode, rf, start):
    lvl = (1 + X.fillna(0)).cumprod().where(X.notna().cumsum() > 0)
    mom = lvl.shift(1) / lvl.shift(12) - 1; above = lvl > lvl.rolling(10).mean()
    C = [c for c in X.columns if c != parent]
    b1 = above[C].where(lvl[C].rolling(10).count() == 10).mean(axis=1); blow = b1 <= b1.expanding(min_periods=24).quantile(1 / 3)
    ALL = list(X.columns); wp = pd.Series(0.0, index=ALL); out = []; hist = []; pend = None; plog = []
    for i in range(12, len(X) - 1):
        t, nx = X.index[i], X.index[i + 1]
        if pend is not None: hist.append(pend); pend = None
        sc = mom.loc[t, ALL]; ok = sc.notna(); pbelow = not bool(above.loc[t, parent]); stress = pbelow and bool(blow.loc[t])
        raw_top = sc.dropna().nlargest(N).index
        if mode in ('mkt', 'tier', 'phi') and pbelow: ok &= sc > 0
        if mode == 'tier' and stress: ok &= above.loc[t, ALL].astype(bool)
        pick = sc[ok].nlargest(N).index; frac = 1.0
        if mode == 'vote': frac = 1 - (float(pbelow) + float(blow.loc[t])) / 2
        if mode == 'phi' and stress: frac = conf(hist); plog.append((t, frac))
        w = pd.Series(0.0, index=ALL); w[pick] = frac / N; wf = 1 - w.sum(); tr = (w - wp).abs().sum(); wp = w
        out.append((nx, float((w * X.loc[nx].fillna(0)).sum() + wf * rf.loc[nx] - COST * tr), tr))
        if stress and len(raw_top): pend = float(X.loc[nx, raw_top].mean())          # 下月末才知道结果
    d = pd.DataFrame(out, columns=['t', 'r', 'tr']).set_index('t').loc[start:]
    monthly.hist = hist
    return d, plog
def lst(d, segs):
    o = {}
    for k, (a, b) in segs.items():
        x = d.loc[a:b, 'r']
        if len(x) < 12: continue
        nav = (1 + x).cumprod(); o[k] = f"{round(float(nav.iloc[-1] ** (12 / len(x)) - 1) * 100, 2)}% / {round(float(100 * (nav / nav.cummax()).min()), 1)}"
    o['换手'] = round(float(d['tr'].mean() * 12), 2); return o

res = {}
# ① 美国长历史
src = open(HERE / 'topn_longhist.py').read().split("ALL = list")[0]; f = {}; sys.argv = ['x', FFP, DTBP, 'results/v6-preflight']; exec(src, f)
X, rf = f['X'], f['rf']
SEG = {'全程': ('1955', '2026'), '1955–1979': ('1955', '1979'), '1980–1999': ('1980', '1999'), '2000–2015': ('2000', '2015'), '2016–2026': ('2016', '2026')}
L = {}
X1 = X.loc['1926-07':]
for N in (3, 5):
    for mode, nm in (('none', '不设防守'), ('mkt', '③'), ('tier', '分级要求'), ('vote', '按票减仓'), ('phi', '按把握调节')):
        d, pl = monthly(X1, 'MKT', N, mode, rf.reindex(X1.index).fillna(0), '1955')
        L[f'前{N} {nm}'] = lst(d, SEG)
        if mode == 'phi' and N == 3: L['前3 按把握调节：紧张月的把握 p（样例）'] = {str(k.date()): round(v, 2) for k, v in pl[-1::-max(1, len(pl) // 8)]}
L['一直持有全市场'] = lst(pd.DataFrame({'r': X['MKT'].loc['1955':], 'tr': 0.0}), SEG)
res['① 美国长历史 1955–2026（年化 / 最低剩）'] = L
# ② 港股
c = sqlite3.connect(ROOT / 'data/market.sqlite')
def bar(code):
    d = pd.read_sql_query("select date, close from bars where code=? and adj='raw' and close>0 and date<='2015-12-31' order by date", c, params=(code,))
    return pd.Series(d['close'].values, pd.to_datetime(d['date'])).groupby(level=0).last()
hk = pd.DataFrame({k: bar(k) for k in ('HSC', 'HSF', 'HSU', 'HSP')}).resample('ME').last()
hsi = pd.read_csv(ROOT / 'data/research/long-history/raw/^HSI.csv', parse_dates=['date']).set_index('date')['close'].loc[:'2015-12-31'].resample('ME').last()
HX = pd.concat([hk, hsi.rename('HSI')], axis=1).loc['1992-04':].pct_change().iloc[1:]
H = {}; SEGH = {'全程 1994–2015': ('1994', '2015'), '1994–2002': ('1994', '2002'), '2003–2015': ('2003', '2015')}
for mode, nm in (('none', '不设防守'), ('mkt', '③'), ('tier', '分级要求'), ('vote', '按票减仓'), ('phi', '按把握调节')):
    d, _ = monthly(HX, 'HSI', 1, mode, rf.reindex(HX.index).fillna(0), '1994'); H[f'前1 {nm}'] = lst(d, SEGH)
H['一直持有恒指'] = lst(pd.DataFrame({'r': HX['HSI'].loc['1994':], 'tr': 0.0}), SEGH)
res['② 港股 1994–2015（价格口径，年化 / 最低剩）'] = H
json.dump(res, open('results/v6-preflight/topn-phi.json', 'w'), ensure_ascii=False, indent=1, default=str)
for k, v in res.items():
    print('==', k); print(pd.DataFrame({kk: vv for kk, vv in v.items() if '样例' not in kk}).T.to_string())
print(res['① 美国长历史 1955–2026（年化 / 最低剩）']['前3 按把握调节：紧张月的把握 p（样例）'])

# ③ 设计期整套系统（2006–2015）
X0 = X1.loc[:'1998-12']; monthly(X0, 'MKT', 3, 'phi', rf.reindex(X0.index).fillna(0), '1955'); US_PRIOR = list(monthly.hist)
sys.argv = [sys.argv[0], FFP, DTBP]
g = {'__file__': str(HERE / 'topn_tiered.py'), '__name__': 'x'}; exec(open(HERE / 'topn_tiered.py').read().split("res = {'设计期'")[0], g)
A_LVL, US_RMB, bond, cash, stats, votes = g['A_LVL'], g['US_RMB'], g['bond'], g['cash'], g['stats'], g['votes']
def slot_phi(lvl, parent, N, bret, cret, prior):
    cal = lvl.index; r = lvl.pct_change().fillna(0).values; K = lvl.shape[1]; cols = list(lvl.columns); pi = cols.index(parent)
    me_mask = np.r_[cal.month[1:] != cal.month[:-1], True]; me = lvl[me_mask]; mom = me.shift(1) / me.shift(12) - 1; above = me > me.rolling(10).mean()
    mnx = me.pct_change().shift(-1)
    blvl = np.exp(np.log1p(bret.fillna(0)).cumsum()).where(bret.notna().cumsum() > 0); bme = blvl[me_mask]; babove = (bme > bme.rolling(10).mean()) & bme.notna()
    V, _ = votes(lvl, parent, ['均线', '宽度', 'TRIN'])
    w = np.zeros(K); wb = 0.0; wc = 1.0; out = np.zeros(len(cal)); turn = 0.0; pending = None; br, cr = bret.fillna(0).values, cret.values
    hist = []; pend = None; plog = {}
    for t in range(len(cal)):
        if pending is not None:
            tgt, tb, tc = pending; tr = np.abs(tgt - w).sum() + abs(tb - wb); turn += tr; cst = COST * tr; w, wb, wc = tgt, tb, tc; pending = None
        else: cst = 0.0
        gg = (w * r[t]).sum() + wb * br[t] + wc * cr[t]; out[t] = (1 + gg) * (1 - cst) - 1
        G = 1 + gg; w = w * (1 + r[t]) / G; wb = wb * (1 + br[t]) / G; wc = wc * (1 + cr[t]) / G
        if me_mask[t]:
            d = cal[t]
            if pend is not None: hist.append(pend); pend = None
            sc = mom.loc[d].values.astype(float); ok = np.isfinite(sc); tgt = np.zeros(K)
            p = conf(hist, prior=prior); plog[d] = p
            if not ok.any(): tgt[pi] = 1.0
            else:
                raw = [i for i in np.argsort(-np.where(ok, sc, -np.inf))[:N] if ok[i]]
                if not bool(above.loc[d].values[pi]): ok &= sc > 0
                stress = int(V.get(d.to_period('M'), 0)) >= 2
                pick = [i for i in np.argsort(-np.where(ok, sc, -np.inf))[:N] if ok[i]]
                tgt[pick] = (p if stress else 1.0) / N
                if stress and raw:
                    v = mnx.loc[d].values[raw]
                    if np.isfinite(v).all(): pend = float(np.mean(v))
            left = 1 - tgt.sum(); bok = bool(babove.loc[d]) if d in babove.index else False
            pending = (tgt, left if bok else 0.0, 0.0 if bok else left)
    return pd.Series(out, cal), turn, pd.Series(plog)
def summ(ret, ta, tu):
    st = stats(ret, '2006-01-01', {'2006–10': ('2006', '2010'), '2011–15': ('2011', '2015')}); s_ = (1 + ret.loc['2006':]).cumprod()
    for k, (x0, x1) in {'2008': ('2007-06-01', '2009-12-31'), '2015': ('2015-01-01', '2015-12-31')}.items():
        x = s_.loc[x0:x1]; pk = s_.loc[:x.index[-1]].cummax().loc[x.index]; st[f'最低剩_{k}'] = round(float(100 * (x / pk).min()), 1)
    yr = s_.resample('YE').last().pct_change(); yr.iloc[0] = s_.resample('YE').last().iloc[0] - 1
    st['最差一年'] = round(float(yr.min()) * 100, 1); st['每年换手_倍'] = round((ta + tu) / 2 / (len(s_) / 252), 2); return st
Dz = {}
for N in (2, 3):
    a, ta, pa = slot_phi(A_LVL, 'csi300', N, bond, cash, None); u, tu, pu = slot_phi(US_RMB, 'SPX', N, bond, cash, US_PRIOR)
    Dz[f'前{N} 按把握调节（美 50%）'] = summ(0.5 * a + 0.5 * u, ta, tu)
    for us in (0.55, 0.60): Dz[f'前{N} 按把握调节，美股常驻 {int(us*100)}%'] = summ((1 - us) * a + us * u, ta, tu)
    pA = pa.copy(); pA.index = pd.DatetimeIndex(pA.index)
    wu = (0.5 + 0.1 * (1 - pA)).reindex(a.index, method='ffill').shift(1).fillna(0.5)
    Dz[f'前{N} 按把握调节，美股 = 50% + 10%×(1−A 股把握)'] = summ((1 - wu) * a + wu * u - wu.diff().abs().fillna(0) * 2 * COST, ta, tu)
    if N == 2: Dz['A 股名额把握 p（年末）'] = {str(k): round(v, 2) for k, v in pA.groupby(pA.index.year).last().items()}; Dz['美股名额把握 p（年末）'] = {str(k): round(v, 2) for k, v in pu.groupby(pd.DatetimeIndex(pu.index).year).last().items()}
o = json.load(open('results/v6-preflight/topn-permarket.json'))
for k in ('前2 A 按票减仓 + 美 分级要求', '参照 前2 ③只在母指数层面', '参照 基准（美股30%）', '参照 增强基准（K2A 美股50%）'): Dz[k] = o[k]
res['③ 设计期整套系统 2006–2015'] = Dz
json.dump(res, open('results/v6-preflight/topn-phi.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(pd.DataFrame({k: v for k, v in Dz.items() if '把握 p' not in k}).T.to_string())
print(Dz['A 股名额把握 p（年末）']); print(Dz['美股名额把握 p（年末）'])
