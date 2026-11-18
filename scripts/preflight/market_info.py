"""D38 第 32 行 M1：宽度、TRIN、量价七个指标的信息量（只量信息，不定用法）。
用法：python scripts/preflight/market_info.py <49_Industry_Portfolios.csv> results/v6-preflight
"""
import sys, json, io, pathlib, warnings
warnings.filterwarnings('ignore')
HERE = pathlib.Path(__file__).resolve().parent
FF, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
vs = {'__file__': str(HERE / 'volume_signals.py')}; exec(open(HERE / 'volume_signals.py').read().split("def analyse")[0], vs)
import numpy as np, pandas as pd

def indicators(PX, AM):
    dr = PX.pct_change(); me = PX.resample('ME').last(); mr = me.pct_change()
    ind = pd.DataFrame(index=me.index)
    ind['B1 站上均线占比'] = (me > me.rolling(10).mean()).where(me.rolling(10).count() == 10).mean(axis=1)
    ind['B2 当月上涨占比'] = (mr > 0).where(mr.notna()).mean(axis=1)
    adr = ((dr > 0).sum(axis=1) / dr.notna().sum(axis=1).replace(0, np.nan))
    ind['B3 日涨跌比10日均'] = adr.rolling(10).mean().resample('ME').last()
    am = AM.resample('ME').sum(min_count=5); adv, dec = mr > 0, mr < 0
    ind['T1 月度TRIN'] = ((adv.sum(axis=1) / dec.sum(axis=1).replace(0, np.nan)) / ((am * adv).sum(axis=1) / (am * dec).sum(axis=1).replace(0, np.nan))).replace([np.inf, -np.inf], np.nan)
    up, dn = dr > 0, dr < 0
    dtr = ((up.sum(axis=1) / dn.sum(axis=1).replace(0, np.nan)) / ((AM * up).sum(axis=1) / (AM * dn).sum(axis=1).replace(0, np.nan))).replace([np.inf, -np.inf], np.nan)
    ind['T2 日TRIN10日均'] = dtr.clip(upper=dtr.quantile(0.99)).rolling(10, min_periods=7).mean().resample('ME').last()
    tot = AM.sum(axis=1, min_count=3); upv = (AM * up).sum(axis=1)
    ind['V1 上涨日成交额占比21日'] = (upv.rolling(21).sum() / tot.rolling(21).sum()).resample('ME').last()
    ind['V2 成交额热度'] = (tot.rolling(21).mean() / tot.rolling(252, min_periods=150).mean()).resample('ME').last()
    mom = me.shift(1) / me.shift(12) - 1
    return ind, me, mr, mom

def evaluate(ind, par_me, mr, mom):
    pm = par_me.pct_change(); nx = pm.shift(-1); below = par_me < par_me.rolling(10).mean()
    top = mom.apply(lambda r: r.dropna().nlargest(3).index.tolist() if r.notna().sum() >= 6 else [], axis=1)
    nmr = mr.shift(-1); tex = pd.Series({t: nmr.loc[t, top[t]].mean() - nx.loc[t] for t in mr.index if len(top[t]) and t in nx.index})
    out = {}
    for col in ind.columns:
        x = pd.DataFrame({'v': ind[col], 'nx': nx, 'tex': tex, 'below': below}).dropna(subset=['v', 'nx'])
        lo = x['v'].expanding(min_periods=24).quantile(1 / 3).shift(1); hi = x['v'].expanding(min_periods=24).quantile(2 / 3).shift(1)
        x['档'] = np.where(x['v'] <= lo, '低', np.where(x['v'] >= hi, '高', np.where(lo.notna(), '中', None)))
        x = x[x['档'].notna()]
        def f(y):
            if len(y) < 5: return None
            return dict(月数=int(len(y)), 下月母指数_年化=round(y['nx'].mean() * 1200, 1), 下月跌超5pct概率=round(float((y['nx'] < -0.05).mean()), 2),
                        下月前3超额_年化=round(y['tex'].mean() * 1200, 1) if y['tex'].notna().sum() >= 5 else None)
        r = {}
        for cond, msk in (('全部', x.index == x.index), ('母在均线上', ~x['below'].astype(bool)), ('母在均线下', x['below'].astype(bool))):
            r[cond] = {b: f(x[msk & (x['档'] == b)]) for b in ('低', '中', '高')}
        a, b = x.loc[x['档'] == '高', 'nx'], x.loc[x['档'] == '低', 'nx']
        r['高减低_t'] = round(float((a.mean() - b.mean()) / np.sqrt(a.var() / len(a) + b.var() / len(b))), 2) if len(a) > 5 and len(b) > 5 else None
        out[col] = r
    return out, ind.corr().round(2)

res = {}
for name, codes, amt, pcode, pamt, start in (('美股 9 个行业 SPDR 1999–2015', vs['US'], False, 'SPX', False, '1999-01-01'),
                                             ('A 股 16 个指数 2006–2015（临时）', vs['AS'], True, 'H00300', True, '2005-01-01')):
    PX, AM, par = vs['universe'](codes, amt, pcode, pamt, start)
    ind, me, mr, mom = indicators(PX, AM)
    ev, corr = evaluate(ind, par.resample('ME').last(), mr, mom)
    res[name] = dict(信息量=ev, 指标相关=corr.to_dict())

# 长历史：French 49 行业的宽度 B1、B2
lines = FF.read_text(errors='replace').splitlines()
def block(title):
    s = next(i for i, l in enumerate(lines) if title in l) + 1; e = s + 1
    while e < len(lines) and lines[e].strip() and lines[e].split(',')[0].strip().isdigit(): e += 1
    d = pd.read_csv(io.StringIO('\n'.join(lines[s:e])), index_col=0); d.columns = [c.strip() for c in d.columns]
    d.index = pd.to_datetime(d.index.astype(str).str.strip(), format='%Y%m') + pd.offsets.MonthEnd(0)
    return d.astype(float).where(lambda x: x > -99)
r = block('Average Value Weighted Returns -- Monthly') / 100
cap = block('Number of Firms in Portfolios') * block('Average Firm Size')
mkt = (cap.shift(1).div(cap.shift(1).sum(axis=1), axis=0) * r).sum(axis=1, min_count=1)
lvl = (1 + r.fillna(0)).cumprod().where(r.notna().cumsum() > 0); mlvl = (1 + mkt.fillna(0)).cumprod()
indF = pd.DataFrame({'B1 站上均线占比': (lvl > lvl.rolling(10).mean()).where(lvl.rolling(10).count() == 10).mean(axis=1),
                     'B2 当月上涨占比': (r > 0).where(r.notna()).mean(axis=1)})
momF = lvl.shift(1) / lvl.shift(12) - 1
evF, corrF = evaluate(indF.loc['1927':], mlvl.loc['1927':], r.loc['1927':], momF.loc['1927':])
res['French 49 行业 1927–2026（只有宽度）'] = dict(信息量=evF, 指标相关=corrF.to_dict())
json.dump(res, open(OUT / 'market-info.json', 'w'), ensure_ascii=False, indent=1, default=float)
for name, v in res.items():
    print('\n==', name)
    for col, rr in v['信息量'].items():
        g = rr['全部']; dn = rr['母在均线下']
        fmt = lambda d: '—' if d is None else f"{d['下月母指数_年化']:>6}/{d['下月跌超5pct概率']:.2f}/{d['下月前3超额_年化']}({d['月数']})"
        print(f"{col:<16} 全部 低{fmt(g['低'])} 高{fmt(g['高'])} t={rr['高减低_t']} | 均线下 低{fmt(dn['低'])} 高{fmt(dn['高'])}")
    print(pd.DataFrame(v['指标相关']).to_string())
