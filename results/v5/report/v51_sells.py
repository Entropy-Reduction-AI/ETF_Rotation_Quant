"""v5.1 减仓（卖出）行为单独看：周中按天减仓 vs 周五减仓，减对了多少、每笔期望多少。
只读签收的持仓、状态、成本和行情，不产生新的组合收益。
对每一次减仓（整体离场或降档；状态在 s 日变化，s+1 日成交 = T）：
  卖出部分 = held[T+1] − held[T] 里风险资产的减少量；
  到“再加回来”的那笔成交 T2 为止，卖出部分的累计收益减去换进防守（国债、黄金、现金）部分的累计收益 = g。
  减仓的价值 = −g（跌了 = 减对）；一来一回的成本 = T 和 T2 两天成本里风险部分的近似（两次成交成本）。
  如果到下一个周五还没加回（持续减仓），再算“等到周五再减”会差多少：T 到周五成交日之间的 −g。
用法：python results/v5/report/v51_sells.py <attr.pkl> → results/v5/report/v51_sells.json、v51_sells.csv
"""
import sys, json, pickle, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
import pandas as pd, numpy as np
pnl = pickle.load(open(sys.argv[1], 'rb'))['pnl_all']; pnl.index = pd.to_datetime(pnl.index)
CLS = pd.read_csv(ROOT / 'config/v5/classes.csv').set_index('container_id')['class'].to_dict()
DEF = {c for c, k in CLS.items() if k in ('国债', '黄金', '现金')} | {'cash'}
def load(seg):
    if seg == '设计期':
        d = pd.read_csv(ROOT / 'results/v5.1/design/index/daily.csv', parse_dates=['date']).set_index('date').loc['2006':'2015']
        h = pd.read_csv(ROOT / 'results/v5.1/design/index/held.csv', parse_dates=['date']).set_index('date').loc['2006':'2015']
        return h, d[['cost', 'buy', 'sell']], d[['market', 'risk']]
    O = ROOT / 'results/v5/oneshot/index/v5.1-对照'
    h = pd.read_csv(O / 'held.csv', parse_dates=['date']).set_index('date')
    n = pd.read_csv(O / 'net.csv', parse_dates=['date']).set_index('date')
    st = pd.read_csv(O / 'state.csv', parse_dates=['date']).set_index('date')
    return h, n[['cost', 'buy', 'sell']], st[['market', 'risk']]
rows = []
for seg in ('设计期', '检验段'):
    h, n, st = load(seg)
    idx = h.index; pos = {d: i for i, d in enumerate(idx)}
    W = set(pd.Series(idx).groupby(pd.Series(idx).dt.to_period('W')).max())
    cols = list(h.columns); risky = [c for c in cols if c not in DEF]
    lr = np.log1p(pnl.reindex(index=idx, columns=cols).fillna(0.0)); cl = lr.cumsum()
    R = st.risk.where(st.market.notna(), 0.0)
    prev = R.shift(1)
    downs = [d for d in idx[1:] if R[d] < prev[d] - 1e-9]
    ups = [d for d in idx[1:] if R[d] > prev[d] + 1e-9]
    for s in downs:
        i = pos[s] + 1
        if i + 1 >= len(idx): continue
        T = idx[i]
        dwa = h.iloc[i + 1] - h.iloc[i]; dw = dwa[risky]; sold = (-dw).clip(lower=0)
        bought = dwa[[c for c in cols if c in DEF]].clip(lower=0)
        if sold.sum() < 1e-3: continue
        nxt_up = [u for u in ups if u > s]
        if nxt_up:
            j = min(pos[nxt_up[0]] + 1, len(idx) - 1)
        else:
            j = len(idx) - 1
        T2 = idx[j]
        def gain(a, b):
            c = np.expm1(cl.iloc[b][sold.index].values - cl.iloc[a][sold.index].values)
            d = np.expm1(cl.iloc[b][bought.index].values - cl.iloc[a][bought.index].values)
            return (float(np.dot(sold.values, c)) - float(np.dot(bought.values, d))) * 100
        g = gain(i, j)
        fri = [w for w in sorted(W) if w >= s]
        fri_t = min(pos[fri[0]] + 1, len(idx) - 1) if fri else j
        cost_rt = 2 * float(n.cost.iloc[i]) * 100 * min(1.0, sold.sum() / max(1e-9, float((n.buy + n.sell).iloc[i]) / 2))
        full = R[s] == 0
        rows.append(dict(段=seg, 状态日=s.strftime('%Y-%m-%d'), 周中=s not in W, 整体离场=bool(full), 卖出仓位=round(float(sold.sum()), 3),
                         回来天数=int((T2 - T).days), 周五前回来=bool(nxt_up and nxt_up[0] <= (fri[0] if fri else s)),
                         减仓价值=-g, 一来一回成本=cost_rt,
                         比等到周五多赚=(-gain(i, fri_t)) if (s not in W and not (nxt_up and nxt_up[0] <= (fri[0] if fri else s))) else np.nan,
                         年=s.year))
df = pd.DataFrame(rows); df.to_csv(ROOT / 'results/v5/report/v51_sells.csv', index=False)
yrs = {'设计期': 10.0, '检验段': len(pd.read_csv(ROOT / 'results/v5/oneshot/index/v5.1-对照/held.csv')) / 252}
def summ(g, y):
    v = g.减仓价值; net = v - g.一来一回成本
    return dict(笔数=len(g), 每年笔数=round(len(g) / y, 1), 减对比例=round(float((v > 0).mean() * 100)), 扣成本后减对=round(float((net > 0).mean() * 100)),
                每笔价值bp=round(float(v.mean() * 100), 1), 每笔成本bp=round(float(g.一来一回成本.mean() * 100), 1), 每笔净期望bp=round(float(net.mean() * 100), 1),
                每年净=round(float(net.sum() / y), 2), 中位价值bp=round(float(v.median() * 100), 1),
                减对时平均bp=round(float(v[v > 0].mean() * 100), 1) if (v > 0).any() else None, 减错时平均bp=round(float(v[v <= 0].mean() * 100), 1) if (v <= 0).any() else None,
                避开大跌_超2pct=int((v > 2).sum()), 踏空大涨_超2pct=int((v < -2).sum()))
out = {}
for seg, g in df.groupby('段'):
    y = yrs[seg]; o = {}
    o['全部减仓'] = summ(g, y)
    for k, m in (('周中减仓', g.周中), ('周五减仓', ~g.周中)):
        o[k] = summ(g[m], y)
    for k, m in (('周中·整体离场（两条腿都断）', g.周中 & g.整体离场), ('周中·降一档（一条腿断）', g.周中 & ~g.整体离场)):
        o[k] = summ(g[m], y)
    for k, m in (('周中·周五前就加回', g.周中 & g.周五前回来), ('周中·过了周五还在减', g.周中 & ~g.周五前回来)):
        o[k] = summ(g[m], y)
    s = g[g.周中 & ~g.周五前回来].比等到周五多赚.dropna()
    o['周中提前减·比等到周五'] = dict(笔数=len(s), 提前减更好比例=round(float((s > 0).mean() * 100)) if len(s) else None, 每笔bp=round(float(s.mean() * 100), 1) if len(s) else None, 每年=round(float(s.sum() / y), 2))
    out[seg] = o
(ROOT / 'results/v5/report/v51_sells.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
for seg in out:
    print('==', seg); print(pd.DataFrame(out[seg]).T.to_string())
