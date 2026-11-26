"""D38 第 29 行：候选池 TRIN（月度）与候选量价。只看信息量，不定规则。
用法：python scripts/preflight/volume_signals.py results/v6-preflight
"""
import sys, json, sqlite3, pathlib
import numpy as np, pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[2]; OUT = pathlib.Path(sys.argv[1])
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from src.v6.guard import load_end_text
END = load_end_text()
c = sqlite3.connect(ROOT / 'data/market.sqlite')
def load(code, amt):
    d = pd.read_sql_query("select date, close, volume, amount from bars where code=? and adj='raw' and close>0 and date<=? order by date", c, params=(code, END))
    d = d.drop_duplicates('date', keep='last'); d.index = pd.to_datetime(d['date'])
    a = d['amount'] if amt else d['close'] * d['volume']
    return d['close'], a.where(a > 0)
US = ['XLK', 'XLV', 'XLE', 'XLY', 'XLP', 'XLF', 'XLI', 'XLB', 'XLU']
AS = ['H30184', 'H30202', '000819', '399998', 'H30187', '399967', '000913', '000932', '399987', '000949', '399986', '399975', '931775', 'H30269', 'H00905', 'H00852']
def universe(codes, amt, parent_code, parent_amt, start):
    px, am = {}, {}
    for k in codes: px[k], am[k] = load(k, amt)
    PX = pd.DataFrame(px).loc[start:]; AM = pd.DataFrame(am).loc[start:]
    par = load(parent_code, parent_amt)[0].reindex(PX.index).ffill()
    return PX, AM, par
def analyse(PX, AM, par):
    dr = PX.pct_change(); me = PX.resample('ME').last(); mr = me.pct_change()
    amt_m = AM.resample('ME').sum(min_count=5)
    adv = mr > 0; dec = mr < 0
    na, nd = adv.sum(1), dec.sum(1); va, vd = (amt_m * adv).sum(1), (amt_m * dec).sum(1)
    trin = ((na / nd.replace(0, np.nan)) / (va / vd.replace(0, np.nan))).replace([np.inf, -np.inf], np.nan)
    pm = par.resample('ME').last().pct_change()
    mom = me.shift(1) / me.shift(12) - 1
    top3 = mom.apply(lambda r: r.dropna().nlargest(3).index.tolist() if r.notna().sum() >= 6 else [], axis=1)
    nxt = mr.shift(-1); top_ex = pd.Series({t: nxt.loc[t, top3[t]].mean() - pm.shift(-1).loc[t] for t in mr.index if len(top3[t])})
    d = pd.DataFrame({'trin': trin, '母下月': pm.shift(-1), '前3下月超额': top_ex}).dropna()
    q = d['trin'].quantile([1 / 3, 2 / 3]).values
    d['档'] = np.where(d['trin'] <= q[0], 'TRIN低（成交集中在上涨的候选）', np.where(d['trin'] >= q[1], 'TRIN高（成交集中在下跌的候选）', '中'))
    v1 = (d.groupby('档')[['母下月', '前3下月超额']].mean() * 1200).round(1); v1['月数'] = d.groupby('档').size()
    # V2：12−1 前 6 名里，按量价分两半
    up = (AM * (dr > 0)).rolling(63, min_periods=40).sum() / AM.rolling(63, min_periods=40).sum()
    heat = AM.rolling(21, min_periods=15).mean() / AM.rolling(252, min_periods=150).mean()
    upm, hm = up.resample('ME').last(), heat.resample('ME').last()
    n3 = (me.shift(-3) / me - 1)
    rows = []
    for t in mr.index:
        s = mom.loc[t].dropna()
        if len(s) < 8: continue
        top6 = s.nlargest(6).index
        for name, met in (('上涨日成交额占比', upm), ('成交额热度', hm)):
            m = met.loc[t, top6].dropna() if t in met.index else pd.Series(dtype=float)
            if len(m) < 6: continue
            hi, lo = m.sort_values().index[3:], m.sort_values().index[:3]
            rows.append(dict(t=t, 指标=name, 下月高减低=nxt.loc[t, hi].mean() - nxt.loc[t, lo].mean(), 下3月高减低=n3.loc[t, hi].mean() - n3.loc[t, lo].mean()))
    v2 = pd.DataFrame(rows).dropna()
    f = lambda x: dict(月数=int(len(x)), 年化点=round(x.mean() * 1200, 1), t=round(x.mean() / x.std() * np.sqrt(len(x)), 2))
    v2r = {k: dict(下月=f(g['下月高减低']), 下3月_每月折算=f(g['下3月高减低'] / 3)) for k, g in v2.groupby('指标')}
    return v1, v2r
res = {}
for name, args in (('美股 9 个行业 SPDR 1999–2015', (US, False, 'SPX', False, '1999-01-01')),
                   ('A 股 16 个主题和宽基 2006–2015（临时：发布日未核）', (AS, True, 'H00300', True, '2005-01-01'))):
    v1, v2 = analyse(*universe(*args)); res[name] = dict(V1_TRIN三档=v1.reset_index().to_dict('records'), V2_前6名里高减低=v2)
    print('==', name); print(v1.to_string()); [print(k, v) for k, v in v2.items()]
json.dump(res, open(OUT / 'volume-signals.json', 'w'), ensure_ascii=False, indent=1, default=float)
