"""随机对照：每月末从当时已有 20 日以上数据的风险容器里随机挑 5 只，等权、满仓持有一个月，重复 2000 次。
回答“E2 新口径、v5 比瞎挑强多少”。同时记录每次的最大回撤。只用设计期 2006–2015 的 U-指数池日收益；不扣成本（对随机更有利）；
不是策略候选，只作对照。用法：python results/v5/diag/memo/random_baseline.py results/v5/diag/memo/random-baseline.csv
"""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets
from src.v5.campaign import classes_for, class_map
m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
cls = classes_for(list(m.names), m.cash_id, class_map())
risk = [n for n in m.names if cls.get(n) in ('A股', '港股', '美股', '其他海外', '商品')]
full = m.pnl[risk]
pnl = full.loc['2006-01-01':'2015-12-31']
months = pnl.index.to_period('M')
blocks, avails = [], []
for per in months.unique():
    block = pnl[months == per]
    prev = full.loc[:block.index[0]].iloc[:-1]
    avails.append([c for c in risk if prev[c].tail(20).notna().all() and len(prev) >= 20])
    blocks.append(block.fillna(0))
rng = np.random.default_rng(20261101)
out = []
for k in range(2000):
    parts = [b[list(rng.choice(a, size=min(5, len(a)), replace=False))].mean(axis=1) for b, a in zip(blocks, avails)]
    r = pd.concat(parts)
    nav = (1 + r).cumprod()
    out.append(((1 + r).prod() ** (252 / len(r)) - 1, (nav / nav.cummax() - 1).min()))
d = pd.DataFrame(out, columns=['cagr', 'mdd']); d.to_csv(sys.argv[1], index=False, float_format='%.6f'); s = d['cagr']
print(d['mdd'].describe().round(3).to_dict())
print(s.describe().round(4).to_dict(), 'avail2006', len(avails[0]))
for v in (0.249, 0.127, 0.156, 0.270):
    print(v, round((s < v).mean(), 3))
