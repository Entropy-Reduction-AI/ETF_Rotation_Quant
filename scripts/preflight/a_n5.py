"""D38 第 52 行：A 股名额选 5 个对选 3 个（设计期整套，去重，美股原 14 个 + REIT）。
用法：python -I scripts/preflight/a_n5.py <49_Industry_Portfolios.csv> <DTB3.csv>
"""
import sys, json, math, pathlib
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parents[1]
FFP, DTBP = sys.argv[1], sys.argv[2]
src = open(HERE / 'topn_dedupe.py').read().split("res = {'说明'")[0]
G = {'__file__': str(HERE / 'topn_dedupe.py'), '__name__': 'x'}; sys.argv = ['x', FFP, DTBP]
exec(src, G)
import numpy as np, pandas as pd
A, US_RMB, US_NEW, TAGS, slot, summ, US_PRIOR = G['A'], G['US_RMB'], G['US_NEW'], G['TAGS'], G['slot'], G['summ'], G['US_PRIOR']
US_REP = US_RMB.copy(); US_REP['DWRTF'] = US_NEW['DWRTF']
u, tu, _ = slot(US_REP, 'SPX', 3, US_PRIOR, TAGS['us'], True)
c3 = A['csi300'].pct_change().fillna(0)
def mon(x): return (1 + x).groupby([x.index.year, x.index.month]).prod() - 1
res = {'说明': '设计期整套：A 股按发布日校正（含主题）、去重、美股原 14 个 + REIT、按把握调节、美股 60%；只改 A 股的 N'}
for N in (3, 5):
    a, ta, la = slot(A, 'csi300', N, None, TAGS['a'], True)
    o = summ(0.4 * a + 0.6 * u, ta, tu)
    ex = (mon(a.loc['2006':]) - mon(c3.loc['2006':]))
    o['A 股名额对沪深300：每年超额点'] = round(float(ex.mean()) * 1200, 1); o['A 股名额对沪深300：年跟踪误差%'] = round(float(ex.std(ddof=1)) * math.sqrt(12) * 100, 1)
    res[f'A 股选 {N} 个'] = o
json.dump(res, open(ROOT / 'results/v6-preflight/a-n5.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
