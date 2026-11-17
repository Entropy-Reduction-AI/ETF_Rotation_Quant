"""D38 第 20 行 T1：Top N 能抓到多少（不是整体排名准不准）。
用法：python scripts/preflight/topn_capture.py <49_Industry_Portfolios.csv> results/v6-preflight
"""
import sys, json, pathlib, io
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd
FF, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]); COST = 0.002

def measure(r, segs, Ns):
    lg = np.log1p(r); mom = lg.shift(1).rolling(11, min_periods=11).sum(); fwd = r.shift(-1)
    out = {}
    for N in Ns:
        rows = {}; prev = set()
        for t in r.index:
            a, b = mom.loc[t], fwd.loc[t]; ok = a.notna() & b.notna()
            if ok.sum() < max(8, 2 * N): continue
            top = set(a[ok].nlargest(N).index); orc = b[ok].nlargest(N).mean(); avg = b[ok].mean()
            chg = len(top - prev) / N if prev else 1.0; prev = top
            g = b[list(top)].mean() - avg
            rows[t] = (g, g - 2 * COST * chg, orc - avg, float(g > 0), chg)
        d = pd.DataFrame(rows, index=['超额', '扣成本', '上限', '跑赢', '换手']).T
        for sg, (a, b) in segs.items():
            x = d.loc[a:b]
            out[f'前{N} {sg}'] = dict(月数=len(x), 超额_年化点=round(x['超额'].mean() * 1200, 1), 扣成本_年化点=round(x['扣成本'].mean() * 1200, 1),
                                     上限_年化点=round(x['上限'].mean() * 1200, 1), 抓到几成=f"{x['超额'].mean() / x['上限'].mean():.1%}",
                                     每月跑赢平均的比例=round(x['跑赢'].mean(), 2), 每月换掉=f"{x['换手'].mean():.0%}")
    return out

lines = FF.read_text(errors='replace').splitlines()
s = next(i for i, l in enumerate(lines) if 'Average Value Weighted Returns -- Monthly' in l) + 1
e = s + 1
while e < len(lines) and lines[e].strip() and lines[e].split(',')[0].strip().isdigit(): e += 1
df = pd.read_csv(io.StringIO('\n'.join(lines[s:e])), index_col=0)
df.index = pd.to_datetime(df.index.astype(str).str.strip(), format='%Y%m') + pd.offsets.MonthEnd(0)
ff = df.astype(float).where(lambda x: x > -99) / 100
res = {'French 49 行业': measure(ff, {'1927–1999': ('1927', '1999'), '2000–2026': ('2000', '2026'), '2016–2026': ('2016', '2026')}, (1, 3, 5))}

from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets
m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
A = m.signal.loc[:'2015-12-31', [c for c in m.signal.columns if c.startswith('allshare-')]]
A = (1 + A.fillna(0)).resample('ME').prod() - 1
res['A 股 10 个全指行业'] = measure(A, {'2006–2010': ('2006', '2010'), '2011–2015': ('2011', '2015')}, (1, 3))
json.dump(res, open(OUT / 'topn-capture.json', 'w'), ensure_ascii=False, indent=1)
for k, v in res.items():
    print('==', k); print(pd.DataFrame(v).T.to_string())
