"""D38 第 15 行 G1：10 个月均线门槛的尾部准确度（只量门槛，不跑组合）。
月末在均线上方 / 下方，下月的平均收益、波动、最差 5% 月份平均；以及“下月跌超 10% 的月份里有几成发生在下方”。
用法：python -I scripts/preflight/gate_tail.py <French 49 行业 CSV> results/v6-preflight
"""
import sys, json, pathlib, io
import numpy as np, pandas as pd
FF, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
RAW = pathlib.Path(__file__).resolve().parents[2] / 'data/research/long-history/raw'

def stat(ret, above):
    d = pd.DataFrame({'r': ret, 'a': above}).dropna(); d['a'] = d['a'].astype(bool)
    out = {}
    for k, g in (('上方', d[d.a]), ('下方', d[~d.a])):
        q = g.r.quantile(0.05)
        out[k] = dict(月数=len(g), 下月平均_年化点=round(g.r.mean() * 1200, 1), 下月波动_年化=round(g.r.std() * np.sqrt(12) * 100, 1),
                     最差5pct月平均=round(g.r[g.r <= q].mean() * 100, 1))
    big = d[d.r <= -0.10]
    out['跌超10%的月份数'] = len(big); out['其中发生在下方的比例'] = round(float((~big.a).mean()), 2) if len(big) else None
    out['下方月份占比'] = round(float((~d.a).mean()), 2)
    return out

res = {}
for name, f, a, b in (('标普500 1955–2003', '^GSPC.csv', '1955-01-01', '2003-06-30'),
                      ('恒生 1987–2015', '^HSI.csv', '1987-01-01', '2015-12-31'),
                      ('日经 1987–2015', '^N225.csv', '1987-01-01', '2015-12-31')):
    px = pd.read_csv(RAW / f, parse_dates=['date']).set_index('date')['close'].loc[a:b]
    me = px.resample('ME').last(); r = me.pct_change().shift(-1)
    res[name] = stat(r, me > me.rolling(10).mean())

lines = FF.read_text(errors='replace').splitlines()
s = next(i for i, l in enumerate(lines) if 'Average Value Weighted Returns -- Monthly' in l) + 1
e = s + 1
while e < len(lines) and lines[e].strip() and lines[e].split(',')[0].strip().isdigit(): e += 1
df = pd.read_csv(io.StringIO('\n'.join(lines[s:e])), index_col=0)
df.index = pd.to_datetime(df.index.astype(str).str.strip(), format='%Y%m') + pd.offsets.MonthEnd(0)
rr = df.astype(float).where(lambda x: x > -99) / 100
lvl = (1 + rr.fillna(0)).cumprod().where(rr.notna())
ab = lvl > lvl.rolling(10).mean(); fw = rr.shift(-1)
for seg, (a, b) in {'French 49 行业 1927–1999': ('1927', '1999'), 'French 49 行业 2000–2026': ('2000', '2026')}.items():
    res[seg] = stat(fw.loc[a:b].stack(), ab.loc[a:b].stack())
json.dump(res, open(OUT / 'gate-tail.json', 'w'), ensure_ascii=False, indent=1)
for k, v in res.items():
    print(k, '| 上方', v['上方'], '| 下方', v['下方'], '| 大跌月在下方', v['其中发生在下方的比例'], '/', v['跌超10%的月份数'], '下方占比', v['下方月份占比'])
