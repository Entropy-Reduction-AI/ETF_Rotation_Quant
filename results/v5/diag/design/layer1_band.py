"""v5 设计稿第 2 版 · 第一层加噪音带后的事前画像（信号层面，不算收益；只用 ≤2015-12-31）。规则跑之前写死：
强度 M、动态周期 L 同 layer1.py；噪音 = 过去 250 天日波动 × √L；z = M ÷ 噪音。
持有某风险市场 h 时：z_h < −b 才离场（转防守/现金）；另一个市场 k 满足 z_k − z_h > b 且 z_k > 0 才换到 k。
不持有风险市场时：某市场 z_k > b 才进场（取 z 最大者）。防守之间：国债、黄金 M > 0 取大者，换另一只要求 z 差 > b；都 ≤ 0 拿现金。
b 取 0（不设噪音带，但进出仍按 M 的正负）、0.5、1、2，看换手和画像是否稳定。每周最后一个交易日决策。
另记录沪深300 几次大转折附近，第一层离开 / 回到 A 股的日期。
第二版（同一诊断，看到第一版后按机制修正）：噪音带只管“换市场”，进场、离场仍按强度正负（b=0 的进出规则）。原因：大跌后过去一年的波动里装满了暴跌，噪音被高估，进场被拖了 4 个月。
用法：python results/v5/diag/design/layer1_band.py results/v5/diag/design [swap]
"""
import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v3.engine.sessions import decision_dates
from src.v4.r5.design import Markets
out = pathlib.Path(sys.argv[1]); SWAP = len(sys.argv) > 2 and sys.argv[2] == 'swap'; m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
ret = m.signal.loc[:'2015-12-31']; cash = m.cash_id
NAME = {'csi300': 'A 股', 'hsi': '港股', 'spx': '美股', 'cgb-10y': '国债', 'gold': '黄金', 'cash': '现金'}
RISK = ['csi300', 'hsi', 'spx']; DEF = ['cgb-10y', 'gold']
clr = np.log1p(ret[cash].fillna(0)).cumsum()
def strength(c):
    lr = np.log1p(ret[c]); valid = lr.notna(); lr = lr.fillna(0); cl = lr.cumsum()
    ratio = lr.rolling(20).std() / lr.rolling(250).std(); q = pd.Series(np.nan, index=lr.index); vals = []
    for t, v in ratio.dropna().items():
        q[t] = (np.array(vals) < v).mean() if len(vals) >= 250 else 0.5; vals.append(v)
    L = np.round(250 ** (1 - q) * 20 ** q); i = np.arange(len(cl)); Li = np.nan_to_num(L.values, nan=10**9).astype(np.int64); j = np.clip(i - Li, 0, None)
    ok = (i - Li >= 0) & valid.rolling(250, min_periods=1).sum().ge(250).values
    M = pd.Series(np.where(ok, (cl.values - cl.values[j]) - (clr.values - clr.values[j]), np.nan), index=cl.index)
    return M, M / (lr.rolling(250).std() * np.sqrt(L))
S = {c: strength(c) for c in RISK + DEF}
days = [pd.Timestamp(d).normalize() for d in decision_dates(pd.DatetimeIndex(m.dates), 'week')]
days = [d for d in days if pd.Timestamp('2006-01-01') <= d <= pd.Timestamp('2015-12-31')]
def run(b):
    h, rows = 'cash', []
    for t in days:
        z = {c: S[c][1].get(t) for c in RISK + DEF}; M = {c: S[c][0].get(t) for c in RISK + DEF}
        z = {k: v for k, v in z.items() if pd.notna(v)}
        if h in RISK:
            cand = [k for k in RISK if k in z and k != h and z[k] > 0 and (h not in z or z[k] - z[h] > b)]
            if SWAP:
                if h in z and M[h] < 0: h = None
            elif h in z and z[h] < -b and not (b == 0 and M[h] >= 0): h = None
            elif b == 0 and h in z and M[h] < 0: h = None
            if h is not None and cand: h = max(cand, key=lambda k: z[k])
        if h not in RISK:
            ent = [k for k in RISK if k in z and ((z[k] > b) if (b > 0 and not SWAP) else M[k] > 0)]
            if ent: h = max(ent, key=lambda k: z[k])
            else:
                d = [k for k in DEF if k in z and M[k] > 0]
                if not d: h = 'cash'
                elif h in DEF and h in d:
                    best = max(d, key=lambda k: z[k])
                    if best != h and z[best] - z[h] > b: h = best
                else: h = max(d, key=lambda k: z[k])
        rows.append(dict(t=t, y=t.year, pick=h))
    return pd.DataFrame(rows)
res = {}
for b in (0, 0.5, 1, 2):
    tag = f'swap-{b}' if SWAP else str(b)
    d = run(b); d.to_csv(out / f'layer1-band-{tag}.csv', index=False)
    sw = d.groupby('y').pick.apply(lambda s: int((s != s.shift()).iloc[1:].sum()))
    yr = (d.groupby('y').pick.value_counts(normalize=True).unstack().fillna(0) * 100).round(0)
    a = (d.pick == 'csi300').astype(int); d['A'] = a
    turns = {}
    for name, t, kind in (('2007-10 顶', '2007-10-16', 'out'), ('2008-11 底', '2008-11-04', 'in'), ('2009-08 顶', '2009-08-03', 'out'), ('2015-06 顶', '2015-06-08', 'out'), ('2014-03 底', '2014-03-20', 'in')):
        aft = d[d.t >= pd.Timestamp(t)]
        hit = aft[aft.A == (0 if kind == 'out' else 1)]
        turns[name] = None if hit.empty else f"{(hit.t.iloc[0] - pd.Timestamp(t)).days} 天后{'离开' if kind == 'out' else '回到'} A 股（那周持有 {NAME[hit.pick.iloc[0]]}）"
    res[tag] = dict(每年换几次=sw.to_dict(), 十年合计=int(sw.sum()), 持有占比=yr.mean().round(0).to_dict(), 转折=turns)
    yr['换几次'] = sw; yr.to_csv(out / f'layer1-band-{tag}-yearly.csv')
(out / ('layer1-band-swap.json' if SWAP else 'layer1-band.json')).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
for b, v in res.items(): print('b =', b, '| 十年换', v['十年合计'], '次 | 每年', v['每年换几次'], '\n   ', v['转折'])
print(pd.read_csv(out / ('layer1-band-swap-1-yearly.csv' if SWAP else 'layer1-band-1-yearly.csv'), index_col=0).to_string())
