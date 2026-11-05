"""复盘用的收益来源拆解（近似）：持仓权重 × 各容器当日收益，按大类和年份加总。
设计期的 E2 新口径持仓用冻结规则在 ≤2015 复跑（与已签收净值逐位一致）；检验段持仓读签收的 results/v5/oneshot。
各容器日收益是行情数据，不是组合收益。输出 results/v5/report/attribution.json。
用法：python results/v5/report/attribution.py <attr.pkl>
"""
import sys, json, pickle, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v4.r5.design import load_containers
d = pickle.load(open(sys.argv[1], 'rb'))
pnl = d['pnl_all']; pnl.index = pd.to_datetime(pnl.index)
ac = {str(r.get('id')): str(r.get('asset_class')) for r in load_containers()}
def group(c):
    a = ac.get(c, '')
    if c == 'cash' or a == '现金': return '现金'
    if c == 'gold': return '黄金'
    if a == '债券' or '债' in c: return '债券'
    if a in ('A股宽基', 'A股红利'): return 'A股宽基'
    if a == 'A股行业': return 'A股行业'
    if a == '港股': return '港股'
    if a == '美股宽基': return '美股宽基'
    if a == '美股和全球主题' or c.startswith('theme-'): return '海外主题'
    if a == '商品': return '商品'
    return a or '其他'
def attribute(held, gross):
    held = held.copy(); held.index = pd.to_datetime(held.index)
    cols = [c for c in held.columns if c in pnl.columns or c == 'cash']
    r = pnl.reindex(index=held.index, columns=cols).fillna(0.0)
    contrib = held[cols] * r
    fit = contrib.sum(axis=1)
    g = contrib.T.groupby(group).sum().T
    w = held[cols].T.groupby(group).sum().T
    return contrib, g, w, float(np.corrcoef(fit, gross.reindex(fit.index).fillna(0))[0, 1])
out = {}
# 设计期 E2
hd = d['held_design'].loc['2006':'2015']
net = pd.read_csv(ROOT / 'results/v4/r5/design/B0/index/net.csv', parse_dates=[0], index_col=0).iloc[:, 0].loc['2006':'2015']
c1, g1, w1, fit1 = attribute(hd, net)
# 检验段 E2
ho = pd.read_csv(ROOT / 'results/v5/oneshot/index/E2-B0/held.csv', parse_dates=['date']).set_index('date')
go = pd.read_csv(ROOT / 'results/v5/oneshot/index/E2-B0/net.csv', parse_dates=['date']).set_index('date').gross
c2, g2, w2, fit2 = attribute(ho, go)
# v5.1 设计期
hv = pd.read_csv(ROOT / 'results/v5.1/design/index/held.csv', parse_dates=['date']).set_index('date').loc['2006':'2015']
gv = pd.read_csv(ROOT / 'results/v5.1/design/index/daily.csv', parse_dates=['date']).set_index('date').gross.loc['2006':'2015']
c3, g3, w3, fit3 = attribute(hv, gv)
hv2 = pd.read_csv(ROOT / 'results/v5/oneshot/index/v5.1-对照/held.csv', parse_dates=['date']).set_index('date')
gv2 = pd.read_csv(ROOT / 'results/v5/oneshot/index/v5.1-对照/net.csv', parse_dates=['date']).set_index('date').gross
c4, g4, w4, fit4 = attribute(hv2, gv2)
def seg(g, w, a, b):
    yrs = len(g.loc[a:b]) / 252
    return {k: dict(贡献_每年=round(float(g.loc[a:b, k].sum() / yrs * 100), 2), 平均仓位=round(float(w.loc[a:b, k].mean() * 100), 1)) for k in g.columns}
out['拟合'] = dict(E2设计=round(fit1, 4), E2检验=round(fit2, 4), v51设计=round(fit3, 4), v51检验=round(fit4, 4))
out['E2设计_前五年'] = seg(g1, w1, '2006', '2010'); out['E2设计_后五年'] = seg(g1, w1, '2011', '2015'); out['E2检验'] = seg(g2, w2, '2016', '2026')
out['v51设计'] = seg(g3, w3, '2006', '2015'); out['v51检验'] = seg(g4, w4, '2016', '2026')
def top(c, a, b, n=8):
    s = c.loc[a:b].sum() * 100; s = s[s.abs() > 0]
    return dict(最好=s.nlargest(n).round(1).to_dict(), 最差=s.nsmallest(n).round(1).to_dict())
out['E2设计_容器'] = top(c1, '2006', '2015'); out['E2检验_容器'] = top(c2, '2016', '2026')
out['v51设计_容器'] = top(c3, '2006', '2015'); out['v51检验_容器'] = top(c4, '2016', '2026')
# 债券仓位逐年（设计期就能看见）
bond = pd.concat([w1['债券'], w2['债券']]); risk = 1 - pd.concat([w1[['现金', '债券', '黄金']].sum(axis=1), w2[['现金', '债券', '黄金']].sum(axis=1)])
out['E2_债券仓位_逐年'] = (bond.groupby(bond.index.year).mean() * 100).round(0).to_dict()
out['E2_风险仓位_逐年'] = (risk.groupby(risk.index.year).mean() * 100).round(0).to_dict()
# 池子构成（每年有数据的容器数，按大类；只看行情是否存在）
have = pnl.notna() & (pnl != 0)
cnt = have.groupby(have.index.year).mean() > .5
by = {int(y): cnt.loc[y][cnt.loc[y]].index.map(group).value_counts().to_dict() for y in cnt.index if y >= 2006}
out['池子构成'] = by
# 持仓分散度：每天持有 >0.5% 的容器数
def breadth(h): return ((h.drop(columns=['cash'], errors='ignore') > .005).sum(axis=1))
b = pd.concat([breadth(hd), breadth(ho)])
out['E2_持有只数_逐年'] = b.groupby(b.index.year).mean().round(1).to_dict()
(ROOT / 'results/v5/report/attribution.json').write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
print(json.dumps({k: out[k] for k in ('拟合', 'E2设计_前五年', 'E2设计_后五年', 'E2检验', 'E2_债券仓位_逐年', 'E2_持有只数_逐年')}, ensure_ascii=False, indent=0))
