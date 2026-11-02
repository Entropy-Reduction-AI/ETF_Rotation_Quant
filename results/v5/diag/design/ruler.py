"""诊断：Owner 2026-11-02 的“收尺子”——尺子随速度、加速度的共振收短，加速度衰减时继续收，平静时逐步放宽。
只用 ≤2015-12-31 的价格（沪深300、标普500），计入诊断次数 1。规则跑之前写死：
  尺子 G = {3,5,10,20,40,60,120,250} 天。加速度 a_n = 最近 n 天涨幅 − 再之前 n 天涨幅，除以 (250 天日波动 × √(2n))（scales.py 同口径）。
  每周最后一个交易日：在不长于当前尺子的那些尺子里，找 |a_n| 最大的；若它超过阈值 T（倍噪音），尺子换成它（收）；
  否则尺子往长放一档（放），最长 250。起始 250。
  持有判断：用当前尺子 n，过去 n 天涨幅 > 同期现金 就持有（与 adaptive.py 同一种门槛），尺子在周内不变、门槛每日判断。
  T 取 1.5、2、2.5。对照：波动比动态周期，最短 20 天、10 天（adaptive.py 已登记）。
用法：python results/v5/diag/design/ruler.py results/v5/diag/design
"""
import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v3.engine.sessions import decision_dates
from src.v4.r5.design import Markets
out = pathlib.Path(sys.argv[1]); m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
ret = m.signal.loc[:'2015-12-31']; cash = m.cash_id
G = [3, 5, 10, 20, 40, 60, 120, 250]
clr = np.log1p(ret[cash].fillna(0)).cumsum()
weeks = set(pd.Timestamp(d).normalize() for d in decision_dates(pd.DatetimeIndex(m.dates), 'week'))
def swings(p, th=0.2):
    pts, mode, ext, ext_t = [], 'up', p.iloc[0], p.index[0]
    for t, v in p.items():
        if mode == 'up':
            if v > ext: ext, ext_t = v, t
            elif v < ext * (1 - th): pts.append(['顶', ext_t, ext]); mode, ext, ext_t = 'down', v, t
        else:
            if v < ext: ext, ext_t = v, t
            elif v > ext * (1 + th): pts.append(['底', ext_t, ext]); mode, ext, ext_t = 'up', v, t
    return pts
res = {}
for c in ('csi300', 'spx'):
    lr = np.log1p(ret[c].fillna(0)); cl = lr.cumsum(); p = np.exp(cl); sd = lr.rolling(250, min_periods=120).std()
    A = pd.DataFrame({n: (lr.rolling(n).sum() - lr.rolling(n).sum().shift(n)) / (sd * np.sqrt(2 * n)) for n in G})
    pts = [x for x in swings(p.loc['2005-06':]) if x[1] >= pd.Timestamp('2006-03-01')]
    kinds = []
    for i, (k, t, lvl) in enumerate(pts):
        nxt = [x for x in pts[i + 1:] if x[0] == k]
        kinds.append('未定' if not nxt else (('真底' if nxt[0][2] > lvl else '假底') if k == '底' else ('真顶' if nxt[0][2] < lvl else '中途的顶')))
    for T in (1.5, 2.0, 2.5):
        L = 250; Ls = []; gate = []
        idx = list(cl.index)
        for i, t in enumerate(idx):
            if t in weeks and t >= pd.Timestamp('2005-12-01'):
                cand = [n for n in G if n <= L and pd.notna(A.at[t, n])]
                if cand:
                    best = max(cand, key=lambda n: abs(A.at[t, n]))
                    if abs(A.at[t, best]) > T: L = best
                    elif L < 250: L = G[G.index(L) + 1]
            Ls.append(L)
            j = max(0, i - L)
            gate.append((cl.iloc[i] - cl.iloc[j]) > (clr.iloc[i] - clr.iloc[j]))
        s = pd.Series(gate, index=cl.index).loc['2006':]; Lser = pd.Series(Ls, index=cl.index).loc['2006':]
        rows = []
        for (k, t, lvl), kind in zip(pts, kinds):
            aft = s.loc[t:]; hit = aft[(~aft) if k == '顶' else aft].index[:1]
            if len(hit):
                r = dict(转折=f'{t:%Y-%m} {kind}', 晚几天=int(len(s.loc[t:hit[0]]) - 1), 涨跌=round(p[hit[0]] / p[t] - 1, 3))
                if k == '底':
                    off = s.loc[hit[0]:]; off = off[~off].index[:1]
                    if len(off): r['回场后到再离场'] = round(p[off[0]] / p[hit[0]] - 1, 3)
                rows.append(r)
        flips = (s != s.shift()).iloc[1:]
        res[f'{c}-T{T}'] = dict(转折=rows, 十年切换=int(flips.sum()), 每年切换=flips.groupby(flips.index.year).sum().to_dict(),
                                尺子中位每年=Lser.groupby(Lser.index.year).median().to_dict(), 尺子分布=Lser.value_counts(normalize=True).round(2).sort_index().to_dict())
        if c == 'csi300' and T == 2.0: Lser.to_csv(out / 'ruler-csi300-T2.csv')
(out / 'ruler.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
for k, v in res.items():
    print('==', k, '十年切换', v['十年切换'], '尺子中位', v['尺子中位每年'])
    print('   ', {r['转折']: (r['晚几天'], r['涨跌'], r.get('回场后到再离场')) for r in v['转折']})
