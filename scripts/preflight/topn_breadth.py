"""D38 第 21 行 T2：前 3 的超额怎么随候选个数变（French 49 行业随机子集）。
用法：python -I scripts/preflight/topn_breadth.py <49_Industry_Portfolios.csv> results/v6-preflight
"""
import sys, json, pathlib, io
import numpy as np, pandas as pd
FF, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]); COST = 0.002
lines = FF.read_text(errors='replace').splitlines()
s = next(i for i, l in enumerate(lines) if 'Average Value Weighted Returns -- Monthly' in l) + 1
e = s + 1
while e < len(lines) and lines[e].strip() and lines[e].split(',')[0].strip().isdigit(): e += 1
df = pd.read_csv(io.StringIO('\n'.join(lines[s:e])), index_col=0)
df.index = pd.to_datetime(df.index.astype(str).str.strip(), format='%Y%m') + pd.offsets.MonthEnd(0)
r = (df.astype(float).where(lambda x: x > -99) / 100).loc['1960':]
r = r.loc[:, r.notna().mean() > 0.97]                                  # 1960 年起几乎全程都有数据的行业
mom = np.log1p(r).shift(1).rolling(11, min_periods=11).sum().values; fwd = r.shift(-1).values; idx = r.index
rng = np.random.default_rng(20261117); res = {}
def run(cols):
    prev = None; out = []
    for t in range(len(idx)):
        a, b = mom[t, cols], fwd[t, cols]; ok = np.isfinite(a) & np.isfinite(b)
        if ok.sum() < 6: continue
        aa = np.where(ok, a, -np.inf); top = set(np.argsort(-aa)[:3])
        chg = len(top - prev) / 3 if prev is not None else 1.0; prev = top
        out.append((idx[t], b[list(top)].mean() - b[ok].mean() - 2 * COST * chg))
    return pd.Series(dict(out))
for k in (10, 15, 25, r.shape[1]):
    vals = {'1960–1999': [], '2000–2026': []}
    for _ in range(200 if k < r.shape[1] else 1):
        x = run(rng.choice(r.shape[1], k, replace=False))
        vals['1960–1999'].append(x.loc['1960':'1999'].mean() * 1200); vals['2000–2026'].append(x.loc['2000':].mean() * 1200)
    res[f'{k} 个候选'] = {sg: dict(中位=round(float(np.median(v)), 1), p10=round(float(np.percentile(v, 10)), 1), p90=round(float(np.percentile(v, 90)), 1)) for sg, v in vals.items()}
json.dump(dict(行业数=r.shape[1], 结果=res), open(OUT / 'topn-breadth.json', 'w'), ensure_ascii=False, indent=1)
print(r.shape[1]); [print(k, v) for k, v in res.items()]
