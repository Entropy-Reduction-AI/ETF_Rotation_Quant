"""D38 预演第 5 项：清点（不涉及 2016 年以后的收益）。

① 每年有数据的容器数，按地区（2005–2026，只数存在与否）。
② 全市场口径下自成一个“市场”的单只基金（引用 D37 已签收的 S1 方案 B 市场表）。
③ 主题基金是不是多在最热时上市：只看 2015-12-31 及以前上市的主题，上市日所跟指数的过去 12 个月涨幅
   在当天全池里的横截面分位，以及在它自己历史里的分位。
④ 溢价控制是否接入执行链（读代码）。
用法：python scripts/preflight/census.py results/v6-preflight
"""
import sys, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets

OUT = pathlib.Path(sys.argv[1])
m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
S = m.signal                                   # 只数 notna，不读 2016 年以后的数值
roster = pd.read_csv(ROOT / 'results/v51-diag/d37/s1-splice-roster.csv', dtype=str)
cls = dict(zip(roster.container_id, roster['class']))
BASE = {'csi300': 'A股', 'csi500': 'A股', 'csi1000': 'A股', 'chinext': 'A股', 'star50': 'A股', 'csi-dividend': 'A股',
        'hsi': '港股', 'hstech': '港股', 'ndx100': '美股', 'spx': '美股', 'gold': '防守', 'cgb-10y': '防守', 'cgb-5y': '防守',
        'cash': '防守', 'soymeal': '商品', 'crude-oil': '商品', 'cross-border-commodity': '商品'}
def region(c):
    if c.startswith('allshare-'): return 'A股'
    return BASE.get(c) or cls.get(c) or '其他'

res = {}
# ① 每年有数据的容器数（年末那天有行情）
alive = S.notna().groupby(S.index.year).any()
reg = pd.Series({c: region(c) for c in S.columns})
cnt = {int(y): alive.loc[y][alive.loc[y]].index.map(reg).value_counts().to_dict() for y in alive.index}
res['①每年容器数_按地区'] = {y: dict(合计=int(sum(v.values())), **{k: int(n) for k, n in v.items()}) for y, v in cnt.items()}

# ② 单只基金自成市场
mk = pd.read_csv(ROOT / 'results/v51-diag/d37/S1/检验段/B/markets.csv')
single = mk[~mk.market.isin(['A股', '港股', '美股', '防守或现金'])]
res['②自成市场的单只基金'] = dict(市场总数=int(len(mk) - 1), 单只成市场=int(len(single)),
                              名单=single.market.tolist(),
                              合计平均仓位=round(float(single.avg_weight.sum()), 3),
                              说明='D37 第五轮 S1 检验段方案 B，已签收；这里只引用仓位，不引用收益')

# ③ 上市时的热度（只看 ≤2015 上市）
R = S.loc[:'2015-12-31']
lvl = np.exp(np.log1p(R).cumsum().where(R.notna()))
r12 = lvl / lvl.shift(250) - 1
rows = []
for _, x in roster.iterrows():
    c, fl = x.container_id, x.first_list
    if not isinstance(fl, str) or fl > '2015-12-31' or c not in r12.columns: continue
    t = r12.index[r12.index.searchsorted(pd.Timestamp(fl)) - 1] if pd.Timestamp(fl) > r12.index[0] else None
    if t is None or pd.isna(r12.at[t, c]): continue
    xs = r12.loc[t].dropna()
    own = r12[c].loc[:t].dropna()
    rows.append(dict(容器=c, 地区=x['class'], 首只上市=fl, 上市前12个月涨幅=round(float(r12.at[t, c]) * 100, 1),
                     当天全池分位=round(float((xs < r12.at[t, c]).mean()), 2), 全池容器数=int(len(xs)),
                     自身历史分位=round(float((own < r12.at[t, c]).mean()), 2) if len(own) > 250 else None))
heat = pd.DataFrame(rows).sort_values('首只上市'); heat.to_csv(OUT / 'census-listing-heat.csv', index=False)
res['③上市时热度_≤2015'] = dict(主题数=int(len(heat)),
                              全池分位中位=round(float(heat['当天全池分位'].median()), 2) if len(heat) else None,
                              分位高于0_67的比例=round(float((heat['当天全池分位'] > 0.67).mean()), 2) if len(heat) else None,
                              自身历史分位中位=round(float(heat['自身历史分位'].dropna().median()), 2) if heat['自身历史分位'].notna().any() else None)

# ④ 溢价控制
res['④溢价控制'] = dict(核心配置=('config/portfolio.toml premium_cap=0.10；src/portfolio/execution.py 按溢价卖出、超上限不新买'),
                     v51引擎='src/v51/execute.py 调用溢价排程',
                     结论='已接入执行链；看板“未接入”一条过时')
json.dump(res, open(OUT / 'census.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str)); print(heat.to_string())
