"""D38 第 12 行 F2：French 49 行业，回看期网格 1、3、6、12−1 个月的横截面 IC，及前 5 名换手、扣成本后的超额。
只回答“更快的信号能否抓住几个月一轮的行业轮动”，不据此选回看期。
用法：python -I scripts/preflight/french_lookback.py <49_Industry_Portfolios.csv> results/v6-preflight
"""
import sys, pathlib, io
import numpy as np, pandas as pd
SRC, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]); COST = 0.002
lines = SRC.read_text(errors='replace').splitlines()
s = next(i for i, l in enumerate(lines) if 'Average Value Weighted Returns -- Monthly' in l) + 1
e = s + 1
while e < len(lines) and lines[e].strip() and lines[e].split(',')[0].strip().isdigit(): e += 1
df = pd.read_csv(io.StringIO('\n'.join(lines[s:e])), index_col=0); df.columns = [c.strip() for c in df.columns]
df.index = pd.to_datetime(df.index.astype(str).str.strip(), format='%Y%m') + pd.offsets.MonthEnd(0)
r = df.astype(float).where(lambda x: x > -99) / 100; lg = np.log1p(r); fwd = r.shift(-1)
LB = {'1个月': lg.rolling(1).sum(), '3个月': lg.rolling(3).sum(), '6个月': lg.rolling(6).sum(),
      '12−1': lg.shift(1).rolling(11, min_periods=11).sum()}
SEG = {'1927–1999': ('1927', '1999'), '2000–2026': ('2000', '2026'), '2016–2026': ('2016', '2026')}
rows = []
for k, mom in LB.items():
    ic, net, gross, to = {}, {}, {}, {}; prev = set()
    for t in r.index:
        a, b = mom.loc[t], fwd.loc[t]; ok = a.notna() & b.notna()
        if ok.sum() < 20: continue
        ic[t] = a[ok].rank().corr(b[ok].rank())
        top = set(a[ok].nlargest(5).index); chg = len(top - prev) / 5 if prev else 1.0; prev = top
        g = b[list(top)].mean() - b[ok].mean(); gross[t] = g; to[t] = chg; net[t] = g - 2 * COST * chg
    ic, gross, net, to = map(pd.Series, (ic, gross, net, to))
    for sg, (a, b) in SEG.items():
        x = ic.loc[a:b]
        rows.append(dict(回看=k, 段=sg, IC均值=round(x.mean(), 3), t=round(x.mean() / x.std() * np.sqrt(len(x)), 2),
                         前5每月换掉=f'{to.loc[a:b].mean():.0%}', 前5超额_未扣=round(gross.loc[a:b].mean() * 1200, 1),
                         前5超额_扣成本=round(net.loc[a:b].mean() * 1200, 1)))
d = pd.DataFrame(rows); d.to_csv(OUT / 'french-lookback.csv', index=False); print(d.to_string(index=False))
