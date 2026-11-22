"""D38 第 53 行：v6 的 A 股候选池（含主题，按发布日截断），拆开等权倾斜与挑选，并量挑选空间。
用法：python -I scripts/preflight/a_theme_split.py <49_Industry_Portfolios.csv> <DTB3.csv>
"""
import sys, json, math, pathlib, warnings
warnings.filterwarnings('ignore')
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parents[1]
FFP, DTBP = sys.argv[1], sys.argv[2]
import numpy as np, pandas as pd
G = {'__file__': str(HERE / 'a_official.py'), '__name__': 'x'}; sys.argv = ['x', FFP, DTBP]
exec(open(HERE / 'a_official.py').read().split("res = {'每年末")[0], G)
A = G['A']; COST = 0.002
cal = A.index; me = A[np.r_[cal.month[1:] != cal.month[:-1], True]]
mom = me.shift(1) / me.shift(12) - 1; nxt = me.pct_change().shift(-1)
rows = []; prev = pd.Series(0.0, index=me.columns)
for d in me.loc['2011-08':'2015-11'].index:
    s = mom.loc[d].dropna(); s = s[nxt.loc[d, s.index].notna()]
    if len(s) < 5 or not np.isfinite(nxt.loc[d, 'csi300']): continue
    pool = s.index; ew = float(nxt.loc[d, pool].mean()); top = s.nlargest(3).index
    w = pd.Series(0.0, index=me.columns); w[top] = 1 / 3; tr = float((w - prev).abs().sum()); prev = w
    best = float(nxt.loc[d, pool].nlargest(3).mean())
    rows.append((d, len(pool), ew - float(nxt.loc[d, 'csi300']), float(nxt.loc[d, top].mean()) - ew - COST * tr, best - ew, tr))
df = pd.DataFrame(rows, columns=['d', 'n', 'ew_vs_300', 'sel', 'oracle', 'tr']).set_index('d')
tt = lambda x: round(float(x.mean() / x.std(ddof=1) * math.sqrt(len(x))), 2)
def seg(x):
    return {'月数': int(len(x)), '平均候选个数': round(float(x['n'].mean()), 1),
            '① 等权全部对沪深300 每年点': round(float(x['ew_vs_300'].mean()) * 1200, 1), '① t': tt(x['ew_vs_300']),
            '② 12−1 前 3 对等权 每年点（扣成本）': round(float(x['sel'].mean()) * 1200, 1), '② t': tt(x['sel']),
            '③ 事后最好 3 个对等权 每年点（不可交易）': round(float(x['oracle'].mean()) * 1200, 1),
            '12−1 抓住了挑选空间的几成': round(float(x['sel'].mean() / x['oracle'].mean()), 3)}
res = {'说明': 'v6 的 A 股候选池（含主题，按官方发布日截断）；前 3 等分；2016 年以后不看',
       '全段 2011-08 → 2015-11': seg(df), '2011-08 → 2013-12': seg(df.loc[:'2013-12']), '2014-01 → 2015-11': seg(df.loc['2014-01':])}
json.dump(res, open(ROOT / 'results/v6-preflight/a-theme-split.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
