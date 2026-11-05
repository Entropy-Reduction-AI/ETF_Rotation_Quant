"""v5.1 高换手深挖：每一笔调仓“做对了没有”。只读已签收的持仓、状态和行情，不产生新的组合收益。
对每个交易日 T（buy+sell>0）：Δw = held[T+1] − held[T]，增值 VA(h) = Σ Δw_i × 之后 h 个交易日累计收益_i。
VA > 0 = 这笔调仓比“不调”多赚（不含成本）；净值 = VA − 当天成本。
类别按 T−1 相对 T−2 的状态变化（成交在信号次日）。设计期 2006–2015、检验段 2016–2026-09 用同一套代码。
用法：python results/v5/report/v51_turnover.py <attr.pkl>  → results/v5/report/v51_turnover.json、v51_trades.csv
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
        ex = pd.read_csv(ROOT / 'results/v5.1/design/index/exits.csv', parse_dates=['t'])
        return h, d[['cost', 'buy', 'sell']], d[['market', 'risk', 'defense', 'picks']], ex
    O = ROOT / 'results/v5/oneshot/index/v5.1-对照'
    h = pd.read_csv(O / 'held.csv', parse_dates=['date']).set_index('date')
    n = pd.read_csv(O / 'net.csv', parse_dates=['date']).set_index('date')
    st = pd.read_csv(O / 'state.csv', parse_dates=['date']).set_index('date')
    return h, n[['cost', 'buy', 'sell']], st[['market', 'risk', 'defense', 'picks']], pd.read_csv(O / 'exits.csv', parse_dates=['t'])
H = (5, 20, 60)
out, rows = {}, []
for seg in ('设计期', '检验段'):
    h, n, st, ex = load(seg)
    cols = [c for c in h.columns]
    r = pnl.reindex(index=h.index, columns=cols).fillna(0.0)
    lr = np.log1p(r); cl = lr.cumsum()
    idx = h.index
    prev = st.shift(1)
    mk, pmk = st.market.fillna(''), prev.market.fillna('')
    cls = pd.Series('', index=idx)
    cls[(mk != '') & (pmk == '')] = '整体进场'
    cls[(mk == '') & (pmk != '')] = '整体离场'
    cls[(mk != '') & (pmk != '') & (mk != pmk)] = '换市场'
    m = (cls == '') & (st.risk != prev.risk)
    cls[m & (st.risk > prev.risk)] = '加仓档'; cls[m & (st.risk < prev.risk)] = '减仓档'
    m = (cls == '') & (st.picks.fillna('') != prev.picks.fillna(''))
    exw = ex.groupby('t').why.agg(lambda x: '周度换掉' if (x == '周度换掉').any() else '单只离场')
    cls[m] = exw.reindex(idx[m]).fillna('换人（其他）').values
    cls[(cls == '') & (st.defense.fillna('') != prev.defense.fillna(''))] = '防守换品种'
    tcls = cls.shift(1).fillna('')   # 成交日 = 状态变化次日
    tv = n.buy + n.sell
    for i in np.where(tv.values > 1e-3)[0]:
        if i + 1 >= len(idx): break
        T = idx[i]; dw = (h.iloc[i + 1] - h.iloc[i]).values
        rec = dict(段=seg, 日期=T.strftime('%Y-%m-%d'), 类别=tcls.iloc[i] or '其他', 换手=float(tv.iloc[i]), 成本=float(n.cost.iloc[i]) * 100,
                   风险仓位变化=float(sum(dw[j] for j, c in enumerate(cols) if c not in DEF)))
        for hh in H:
            j = min(i + hh, len(idx) - 1)
            c = np.expm1(cl.iloc[j].values - cl.iloc[i].values)
            rec[f'VA{hh}'] = float(np.dot(dw, c)) * 100
        rows.append(rec)
df = pd.DataFrame(rows)
df.to_csv(ROOT / 'results/v5/report/v51_trades.csv', index=False)
yrs = {'设计期': 10.0, '检验段': len(pd.read_csv(ROOT / 'results/v5/oneshot/index/v5.1-对照/held.csv')) / 252}
for (seg, k), g in df.groupby(['段', '类别']):
    y = yrs[seg]
    out.setdefault(seg, {})[k] = dict(
        每年次数=round(len(g) / y, 1), 每年换手=round(g.换手.sum() / y, 1), 每年成本=round(g.成本.sum() / y, 2),
        **{f'做对比例{hh}': round(float((g[f'VA{hh}'] > 0).mean() * 100)) for hh in H},
        **{f'每年增值{hh}': round(g[f'VA{hh}'].sum() / y, 2) for hh in H},
        **{f'扣成本后每笔为正{hh}': round(float((g[f'VA{hh}'] > g.成本).mean() * 100)) for hh in H},
        每笔成本bp=round(g.成本.mean() * 100, 1), 每笔增值bp20=round(g.VA20.mean() * 100, 1))
for seg, g in df.groupby('段'):
    y = yrs[seg]
    out[seg]['合计'] = dict(每年次数=round(len(g) / y, 1), 每年换手=round(g.换手.sum() / y, 1), 每年成本=round(g.成本.sum() / y, 2),
                          **{f'做对比例{hh}': round(float((g[f'VA{hh}'] > 0).mean() * 100)) for hh in H},
                          **{f'每年增值{hh}': round(g[f'VA{hh}'].sum() / y, 2) for hh in H})
(ROOT / 'results/v5/report/v51_turnover.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
for seg in out:
    print('==', seg)
    print(pd.DataFrame(out[seg]).T[['每年次数', '每年换手', '每年成本', '做对比例5', '做对比例20', '每年增值5', '每年增值20', '每年增值60', '扣成本后每笔为正20']].to_string())
