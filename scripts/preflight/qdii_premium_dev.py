"""D38 第 30 行 P2：溢价偏离自身常态后，未来 21 个交易日溢价怎么变。
用法：python scripts/preflight/qdii_premium_dev.py results/v6-preflight
"""
import sys, json, sqlite3, pathlib
import numpy as np, pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[2]; OUT = pathlib.Path(sys.argv[1])
codes = pd.read_csv(OUT / 'qdii-premium.csv', dtype={'代码': str})
c = sqlite3.connect(ROOT / 'data/market.sqlite'); allr = []; per = {}
for code, name in zip(codes['代码'], codes['名称']):
    d = pd.read_sql_query("select b.date, b.close, n.unit_nav from bars b join fund_nav n on b.code=n.code and b.date=n.date "
                          "where b.code=? and b.adj='raw' and b.close>0 and n.unit_nav>0 order by b.date", c, params=(code,))
    p = (d['close'] / d['unit_nav'] - 1).clip(-0.5, 1.0)                      # 去掉明显的坏点
    dev = p - p.rolling(60).median(); fut = p.shift(-21) - p
    x = pd.DataFrame({'dev': dev, 'fut': fut, 'lvl': p}).dropna(); x['code'] = name; allr.append(x)
    per[name] = dict(中位溢价=round(p.median() * 100, 1), 偏离超5点时未来21日溢价变化=round(x.loc[x.dev > 0.05, 'fut'].mean() * 100, 1) if (x.dev > 0.05).any() else None,
                     偏离超5点天数=int((x.dev > 0.05).sum()), 未来21日溢价跌超5点的比例=round(float((x.fut < -0.05).mean()), 2))
X = pd.concat(allr)
bins = [-1, -0.02, 0.02, 0.05, 0.10, 1]; X['档'] = pd.cut(X['dev'], bins, labels=['低于常态2点以上', '常态±2点', '高2–5点', '高5–10点', '高10点以上'])
g = X.groupby('档', observed=True)['fut'].agg(['count', 'mean', lambda s: (s < -0.05).mean()])
g.columns = ['天数', '未来21日溢价平均变化', '未来21日溢价跌超5点的比例']; g['未来21日溢价平均变化'] = (g['未来21日溢价平均变化'] * 100).round(1); g.iloc[:, 2] = g.iloc[:, 2].round(2)
lv = pd.cut(X['lvl'], [-1, 0.02, 0.05, 0.10, 1], labels=['<2%', '2–5%', '5–10%', '>10%'])
h = X.groupby(lv, observed=True)['fut'].agg(['count', 'mean']); h['mean'] = (h['mean'] * 100).round(1)
json.dump(dict(按偏离=g.reset_index().astype(str).to_dict('records'), 按绝对水平=h.reset_index().astype(str).to_dict('records'), 分基金=per),
          open(OUT / 'qdii-premium-deviation.json', 'w'), ensure_ascii=False, indent=1)
print(g.to_string()); print(h.to_string()); print(pd.DataFrame(per).T.loc[['纳指科技', '纳指100(国泰)', '标普科技(易方达)', '标普500(国泰)']].to_string())
