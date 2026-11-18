"""D38 第 31 行：整套系统，防守⑤ = 母指数跌破均线 且 候选池 TRIN 偏高（扩展分位，不看未来）。
用法：python scripts/preflight/topn_system3.py
"""
import sys, json, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.argv = [sys.argv[0], 'results/v6-preflight']
src = open(HERE / 'topn_system2.py').read().split("res = {}")[0]
g = {'__file__': str(HERE / 'topn_system2.py'), '__name__': 'x'}; exec(src, g)
vs = {'__file__': str(HERE / 'volume_signals.py')}; exec(open(HERE / 'volume_signals.py').read().split("def analyse")[0], vs)
import numpy as np, pandas as pd
A_LVL, US_RMB, bond, cash, stats = g['A_LVL'], g['US_RMB'], g['bond'], g['cash'], g['stats']

def trin_flag(codes, amt, parent_code, parent_amt, start):
    PX, AM, _ = vs['universe'](codes, amt, parent_code, parent_amt, start)
    me = PX.resample('ME').last(); mr = me.pct_change(); am = AM.resample('ME').sum(min_count=5)
    adv, dec = mr > 0, mr < 0
    tr = ((adv.sum(axis=1) / dec.sum(axis=1).replace(0, np.nan)) / ((am * adv).sum(axis=1) / (am * dec).sum(axis=1).replace(0, np.nan))).replace([np.inf, -np.inf], np.nan)
    thr = tr.expanding(min_periods=24).quantile(2 / 3)
    return (tr >= thr).where(thr.notna())            # True = 偏高；NaN = 历史不足
FLAG = {'csi300': trin_flag(vs['AS'], True, 'H00300', True, '2005-01-01'), 'SPX': trin_flag(vs['US'], False, 'SPX', False, '1999-01-01')}

def slot3(lvl, parent, N, bret, cret, cost=0.002):
    cal = lvl.index; r = lvl.pct_change().fillna(0).values; K = lvl.shape[1]; pi = list(lvl.columns).index(parent)
    me_mask = np.r_[cal.month[1:] != cal.month[:-1], True]
    me = lvl[me_mask]; mom = me.shift(1) / me.shift(12) - 1; above = me > me.rolling(10).mean()
    blvl = np.exp(np.log1p(bret.fillna(0)).cumsum()).where(bret.notna().cumsum() > 0)
    bme = blvl[me_mask]; babove = (bme > bme.rolling(10).mean()) & bme.notna()
    fl = FLAG[parent].copy(); fl.index = pd.DatetimeIndex(fl.index).to_period('M')
    w = np.zeros(K); wb = 0.0; wc = 1.0; out = np.zeros(len(cal)); turn = 0.0; pending = None; br, cr = bret.fillna(0).values, cret.values; trig = 0
    for t in range(len(cal)):
        if pending is not None:
            tgt, tb, tc = pending; tr = np.abs(tgt - w).sum() + abs(tb - wb); turn += tr; cst = cost * tr; w, wb, wc = tgt, tb, tc; pending = None
        else: cst = 0.0
        gg = (w * r[t]).sum() + wb * br[t] + wc * cr[t]; out[t] = (1 + gg) * (1 - cst) - 1
        G = 1 + gg; w = w * (1 + r[t]) / G; wb = wb * (1 + br[t]) / G; wc = wc * (1 + cr[t]) / G
        if me_mask[t]:
            d = cal[t]; sc = mom.loc[d].values.astype(float); ok = np.isfinite(sc); tgt = np.zeros(K)
            if not ok.any(): tgt[pi] = 1.0
            else:
                below = not bool(above.loc[d].values[pi]); f = fl.get(d.to_period('M'), np.nan)
                hot = below if pd.isna(f) else (below and bool(f))
                if hot: ok &= sc > 0; trig += 1
                pick = [i for i in np.argsort(-np.where(ok, sc, -np.inf))[:N] if ok[i]]; tgt[pick] = 1 / N
            left = 1 - tgt.sum(); bok = bool(babove.loc[d]) if d in babove.index else False
            pending = (tgt, left if bok else 0.0, 0.0 if bok else left)
    return pd.Series(out, cal), turn, trig

def system(N):
    a, ta, ka = slot3(A_LVL, 'csi300', N, bond, cash); u, tu, ku = slot3(US_RMB, 'SPX', N, bond, cash)
    ret = 0.5 * a + 0.5 * u; st = stats(ret, '2006-01-01', {'2006–10': ('2006', '2010'), '2011–15': ('2011', '2015')})
    s = (1 + ret.loc['2006':]).cumprod()
    for k, (x0, x1) in {'2008': ('2007-06-01', '2009-12-31'), '2015': ('2015-01-01', '2015-12-31')}.items():
        x = s.loc[x0:x1]; pk = s.loc[:x.index[-1]].cummax().loc[x.index]; st[f'最低剩_{k}'] = round(float(100 * (x / pk).min()), 1)
    yr = s.resample('YE').last().pct_change(); yr.iloc[0] = s.resample('YE').last().iloc[0] - 1
    st['最差一年'] = round(float(yr.min()) * 100, 1); st['每年换手_倍'] = round((ta + tu) / 2 / (len(s) / 252), 2); st['防守触发月数_A/美'] = f'{ka}/{ku}'
    return st
res = {f'前{N} ⑤均线+TRIN': system(N) for N in (2, 3)}
old = json.load(open('results/v6-preflight/topn-system2.json'))
for k in ('前2 ③只在母指数层面', '前3 ③只在母指数层面', '前2 不设防守', '参照 基准（美股30%）', '参照 增强基准（K2A 美股50%）'): res[k] = old[k]
json.dump(res, open('results/v6-preflight/topn-system3.json', 'w'), ensure_ascii=False, indent=1)
print(pd.DataFrame(res).T.to_string())
