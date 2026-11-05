"""复盘第 3 版：E2 新口径、A1、A2、v5.1 的收益来源和相对基准的差距拆解（三段：2006–10、2011–15、2016–26）。
持仓：设计期用冻结规则在 ≤2015 复跑（与签收净值逐位一致），检验段读签收的 results/v5/oneshot。
收益：各容器当天收益（行情数据）。不算新的组合收益。输出 results/v5/report/attribution_all.json。
用法：python results/v5/report/attribution_all.py <attr.pkl> <peers_design.pkl> <ref.pkl>
"""
import sys, json, pickle, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'results/v5/report'))
import pandas as pd, numpy as np
from results_v5_group import group
d = pickle.load(open(sys.argv[1], 'rb')); pdz = pickle.load(open(sys.argv[2], 'rb')); ref = pd.read_pickle(sys.argv[3])
pnl = d['pnl_all']; pnl.index = pd.to_datetime(pnl.index)
O = ROOT / 'results/v5/oneshot/index'
def rd(p, col): x = pd.read_csv(p, parse_dates=['date']).set_index('date'); return x[col] if col in x else None
H = {
 'E2 新口径': (d['held_design'].loc['2006':'2015'], pd.read_csv(O / 'E2-B0/held.csv', parse_dates=['date']).set_index('date')),
 'A1': (pdz['A1']['held'].loc['2006':'2015'], pd.read_csv(O / 'A1/held.csv', parse_dates=['date']).set_index('date')),
 'A2': (pdz['A2']['held'].loc['2006':'2015'], pd.read_csv(O / 'A2/held.csv', parse_dates=['date']).set_index('date')),
 'v5.1': (pd.read_csv(ROOT / 'results/v5.1/design/index/held.csv', parse_dates=['date']).set_index('date').loc['2006':'2015'],
          pd.read_csv(O / 'v5.1-对照/held.csv', parse_dates=['date']).set_index('date')),
}
NET = {
 'E2 新口径': (pd.read_csv(ROOT / 'results/v4/r5/design/B0/index/net.csv', parse_dates=[0], index_col=0).iloc[:, 0], rd(O / 'E2-B0/net.csv', 'net')),
 'A1': (pd.read_csv(ROOT / 'results/v4/r5/design/A1/index/net.csv', parse_dates=[0], index_col=0).iloc[:, 0], rd(O / 'A1/net.csv', 'net')),
 'A2': (pd.read_csv(ROOT / 'results/v4/r5/design/A2/index/net.csv', parse_dates=[0], index_col=0).iloc[:, 0], rd(O / 'A2/net.csv', 'net')),
 'v5.1': (pd.read_csv(ROOT / 'results/v5.1/design/index/daily.csv', parse_dates=['date']).set_index('date').net, rd(O / 'v5.1-对照/net.csv', 'net')),
}
SEG = (('前五年', '2006', '2010', 0), ('后五年', '2011', '2015', 0), ('设计期', '2006', '2015', 0), ('检验段', '2016', '2026', 1))
def contrib(h):
    h = h.copy(); h.index = pd.to_datetime(h.index)
    cols = [c for c in h.columns if c in pnl.columns or c == 'cash']
    r = pnl.reindex(index=h.index, columns=cols).fillna(0.0)
    c = h[cols] * r
    return c, c.T.groupby(group).sum().T, h[cols].T.groupby(group).sum().T
out = {'segments': {}, 'fit': {}, 'top': {}, 'selection': {}}
for arm, (hd, ht) in H.items():
    for nm, a, b, k in SEG:
        h = (hd if k == 0 else ht).loc[a:b]
        c, g, w = contrib(h); yrs = len(g) / 252
        x = ref.loc[a:b]; A = x.H00300.sum() / len(x) * 252 * 100; U = ((x.XNDX + x.SP500TR) / 2).sum() / len(x) * 252 * 100
        E = {k2: float(g[k2].sum() / yrs * 100) for k2 in g}; W = {k2: float(w[k2].mean() * 100) for k2 in w}
        wa = W.get('A股宽基', 0) + W.get('A股行业', 0); wu = W.get('美股宽基', 0)
        ea = E.get('A股宽基', 0) + E.get('A股行业', 0); eu = E.get('美股宽基', 0)
        net = NET[arm][k].loc[a:b]
        res = dict(基准=.7 * A + .3 * U, 美股少拿=(wu / 100 - .3) * U, 美股时点=eu - wu / 100 * U, A股少拿=(wa / 100 - .7) * A, A股选择=ea - wa / 100 * A,
                   海外主题=E.get('海外主题', 0), 防守=sum(E.get(q, 0) for q in ('债券', '黄金', '现金', '商品')), 港股=E.get('港股', 0),
                   扣费前=sum(E.values()), 扣费后算术=float(net.mean() * 252 * 100), 年化=float(((1 + net).prod() ** (252 / len(net)) - 1) * 100),
                   仓位_A=wa, 仓位_美股宽基=wu, 仓位_主题=W.get('海外主题', 0), 仓位_港股=W.get('港股', 0), 仓位_防守=sum(W.get(q, 0) for q in ('债券', '黄金', '现金', '商品')),
                   贡献={k2: round(v, 2) for k2, v in E.items()})
        res['成本'] = res['扣费前'] - res['扣费后算术']
        out['segments'].setdefault(arm, {})[nm] = {k2: (round(v, 2) if isinstance(v, float) else v) for k2, v in res.items()}
        fitc = float(np.corrcoef(c.sum(axis=1), net.reindex(c.index).fillna(0))[0, 1])
        out['fit'][f'{arm}|{nm}'] = round(fitc, 3)
        s = c.sum() * 100; s = s[s.abs() > .05]
        out['top'][f'{arm}|{nm}'] = dict(最好=s.nlargest(5).round(1).to_dict(), 最差=s.nsmallest(5).round(1).to_dict())
# 选的本事
def sel_vs_ew(h, pool_fn):
    h = h.copy(); h.index = pd.to_datetime(h.index)
    risk = [c for c in h.columns if c in pnl.columns and group(c) not in ('现金', '债券', '黄金')]
    r = pnl.reindex(index=h.index, columns=risk); w = h[risk]; tot = w.sum(axis=1)
    sleeve = (w * r.fillna(0)).sum(axis=1) / tot.where(tot > .05)
    ew = pool_fn(h, r)
    return (sleeve - ew).dropna()
def ew_all(h, r): return r.where(r.notna() & (r != 0)).mean(axis=1)
def ew_a1(h, r): return r[['spx', 'csi300']].mean(axis=1) if 'spx' in r else None
MK = {'A': ('A股宽基', 'A股行业'), 'HK': ('港股',), 'US': ('美股宽基', '海外主题')}
def ew_market(h, r):
    # 只和当天持有的那个市场里的容器比（v5.1 第二层的“选”）
    held_grp = h[[c for c in r.columns]].T.groupby(group).sum().T
    dom = held_grp.idxmax(axis=1)
    out_ = pd.Series(np.nan, index=r.index)
    for mk, gs in MK.items():
        cols = [c for c in r.columns if group(c) in gs and not (mk == 'US' and ('恒生' in c or '港' in c))]
        if mk == 'HK': cols += [c for c in r.columns if group(c) == '海外主题' and ('恒生' in c or '港' in c)]
        m = dom.isin(gs)
        out_[m] = r.loc[m, cols].where(r.loc[m, cols].notna() & (r.loc[m, cols] != 0)).mean(axis=1)
    return out_
for arm, fn in (('E2 新口径', ew_all), ('A1', ew_a1), ('v5.1', ew_market)):
    hd, ht = H[arm]
    for nm, hh in (('设计期', hd), ('检验段', ht)):
        s = sel_vs_ew(hh, fn)
        out['selection'][f'{arm}|{nm}'] = dict(每年=round(float(s.mean() * 252 * 100), 2), 信息比率=round(float(s.mean() / s.std() * np.sqrt(252)), 2),
                                             逐年={int(y): round(float(v * 100), 1) for y, v in s.groupby(s.index.year).sum().items()})
(ROOT / 'results/v5/report/attribution_all.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
for arm in H:
    for nm, *_ in SEG:
        r = out['segments'][arm][nm]
        print(arm, nm, {k: r[k] for k in ('基准', '美股少拿', '美股时点', 'A股少拿', 'A股选择', '海外主题', '港股', '防守', '扣费前', '成本', '年化', '仓位_A', '仓位_美股宽基', '仓位_主题', '仓位_防守')})
print(out['fit']); print({k: (v['每年'], v['信息比率']) for k, v in out['selection'].items()})
