"""复盘第 4 版：检验段四个策略相对基准的差距，按“地区”分组（config/v5/classes.csv 的 class 列：
美股 = 美股宽基 + 美股行业/主题；港股 = 港股宽基 + 港股主题 + 中概；其他海外 = 日本、欧洲、中韩等）。
收益 = 持仓 × 各容器当天收益（行情数据），不算新的组合收益。
用法：python results/v5/report/region_attr.py <attr.pkl> <ref.pkl>
输出：results/v5/report/region_attr.json
"""
import sys, json, pickle, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
import pandas as pd, numpy as np
d = pickle.load(open(sys.argv[1], 'rb')); ref = pd.read_pickle(sys.argv[2])
pnl = d['pnl_all']; pnl.index = pd.to_datetime(pnl.index)
CLS = pd.read_csv(ROOT / 'config/v5/classes.csv').set_index('container_id')['class'].to_dict()
def region(c): return '现金' if c == 'cash' else CLS.get(c, '其他')
O = ROOT / 'results/v5/oneshot/index'
ARMS = {'E2 新口径': 'E2-B0', 'A1': 'A1', 'A2': 'A2', 'v5.1': 'v5.1-对照'}
x = ref.loc['2016':'2026']; A = x.H00300.sum() / len(x) * 252 * 100; U = ((x.XNDX + x.SP500TR) / 2).sum() / len(x) * 252 * 100
out = {'基准': dict(A股=A, 美股=U, 合计=.7 * A + .3 * U)}
for arm, dn in ARMS.items():
    h = pd.read_csv(O / dn / 'held.csv', parse_dates=['date']).set_index('date')
    net = pd.read_csv(O / dn / 'net.csv', parse_dates=['date']).set_index('date').net
    cols = [c for c in h.columns if c in pnl.columns or c == 'cash']
    r = pnl.reindex(index=h.index, columns=cols).fillna(0.0)
    c = h[cols] * r; yrs = len(c) / 252
    E = (c.T.groupby(region).sum().T.sum() / yrs * 100).to_dict()
    W = (h[cols].T.groupby(region).sum().T.mean() * 100).to_dict()
    wu, wa = W.get('美股', 0), W.get('A股', 0)
    # 美股里：宽基（spx、ndx100）和主题分开看仓位
    wb = h[[q for q in ('spx', 'ndx100') if q in h]].sum(axis=1).mean() * 100
    gross = sum(E.values()); arith = float(net.mean() * 252 * 100)
    res = {'美股仓位': (wu / 100 - .3) * U, '美股里拿什么、何时拿': E.get('美股', 0) - wu / 100 * U,
           'A股仓位': (wa / 100 - .7) * A, 'A股里拿什么、何时拿': E.get('A股', 0) - wa / 100 * A,
           '港股': E.get('港股', 0), '其他海外': E.get('其他海外', 0),
           '债券黄金现金': sum(E.get(q, 0) for q in ('国债', '黄金', '现金', '商品')),
           '成本': arith - gross}
    res['合计'] = sum(res.values())
    res['年化'] = float(((1 + net).prod() ** (252 / len(net)) - 1) * 100)
    res['仓位'] = {k: round(v, 1) for k, v in W.items()}; res['仓位']['美股宽基'] = round(wb, 1)
    res['贡献'] = {k: round(v, 2) for k, v in E.items()}
    out[arm] = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in res.items()}
(ROOT / 'results/v5/report/region_attr.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out, ensure_ascii=False, indent=1))
