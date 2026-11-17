"""D38 第 24 行 T5：Top N + 门槛的长历史裁判（French 49 行业，月度）。
用法：python -I scripts/preflight/topn_longhist.py <49_Industry_Portfolios.csv> <DTB3.csv> results/v6-preflight
"""
import sys, json, pathlib, io
import numpy as np, pandas as pd
FF, DTB, OUT = map(pathlib.Path, sys.argv[1:4]); COST = 0.002
lines = FF.read_text(errors='replace').splitlines()
def block(title):
    s = next(i for i, l in enumerate(lines) if title in l) + 1; e = s + 1
    while e < len(lines) and lines[e].strip() and lines[e].split(',')[0].strip().isdigit(): e += 1
    d = pd.read_csv(io.StringIO('\n'.join(lines[s:e])), index_col=0); d.columns = [c.strip() for c in d.columns]
    d.index = pd.to_datetime(d.index.astype(str).str.strip(), format='%Y%m') + pd.offsets.MonthEnd(0)
    return d.astype(float).where(lambda x: x > -99)
r = block('Average Value Weighted Returns -- Monthly') / 100
cap = block('Number of Firms in Portfolios') * block('Average Firm Size')
wv = cap.shift(1).div(cap.shift(1).sum(axis=1), axis=0)                  # 上月末市值权重
mkt = (wv * r).sum(axis=1, min_count=1)
tb = pd.read_csv(DTB, parse_dates=['date'], na_values=['.', '']).set_index('date')['DTB3'].dropna(); tb = tb[tb > -1]                   # 源文件里有负的哨兵值
rf = (tb.resample('ME').mean() / 100 / 12).reindex(r.index).ffill().fillna(0)
r = r.loc['1953':]; mkt = mkt.loc['1953':]; rf = rf.loc['1953':]
X = pd.concat([r, mkt.rename('MKT')], axis=1)
lvl = (1 + X.fillna(0)).cumprod().where(X.notna().cumsum() > 0)
mom = lvl.shift(1) / lvl.shift(12) - 1; above = lvl > lvl.rolling(10).mean()

def run(N, gate, cands):
    w_prev = pd.Series(0.0, index=X.columns); out = []
    for i in range(12, len(X) - 1):
        t, nx = X.index[i], X.index[i + 1]
        sc = mom.loc[t, cands]; ok = sc.notna()
        if gate: ok &= above.loc[t, cands]
        pick = sc[ok].nlargest(N).index
        w = pd.Series(0.0, index=X.columns); w[pick] = 1 / N; wf = 1 - w.sum()
        tr = (w - w_prev).abs().sum(); w_prev = w
        out.append((nx, float((w * X.loc[nx].fillna(0)).sum() + wf * rf.loc[nx] - COST * tr), tr))
    d = pd.DataFrame(out, columns=['t', 'r', 'tr']).set_index('t'); return d
SEGS = {'1955–1979': ('1955', '1979'), '1980–1999': ('1980', '1999'), '2000–2015': ('2000', '2015'), '2016–2026': ('2016', '2026')}
def stats(d):
    o = {}
    for k, (a, b) in {'全程1955–2026': ('1955', '2026'), **SEGS}.items():
        x = d.loc[a:b, 'r']; nav = (1 + x).cumprod()
        o[k] = dict(年化=round(float(nav.iloc[-1] ** (12 / len(x)) - 1) * 100, 2), 最低剩=round(float(100 * (nav / nav.cummax()).min()), 1))
    o['每年换手_倍'] = round(float(d['tr'].mean() * 12), 2); return o
ALL = list(X.columns); res = {}
hold = pd.DataFrame({'r': X['MKT'], 'tr': 0.0}).iloc[13:]; res['一直持有全市场'] = stats(hold)
res['全市场+门槛（不挑选）'] = stats(run(1, True, ['MKT']))
for N in (3, 5):
    res[f'前{N}（不带门槛）'] = stats(run(N, False, ALL))
    res[f'前{N}+门槛'] = stats(run(N, True, ALL))
json.dump(res, open(OUT / 'topn-longhist.json', 'w'), ensure_ascii=False, indent=1)
rows = {k: {f'{s}': f"{v[s]['年化']}% / {v[s]['最低剩']}" for s in ['全程1955–2026', *SEGS]} | {'换手': v['每年换手_倍']} for k, v in res.items()}
print(pd.DataFrame(rows).T.to_string())
