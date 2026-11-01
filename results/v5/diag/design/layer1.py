"""v5 设计稿第 2 版的事前画像：第一层（选市场）在信号层面每周想持有什么。不算收益；只用 ≤2015-12-31。
每个市场用宽基代表：A 股 沪深300、港股 恒生、美股 标普500；防守：10 年国债、黄金；否则现金。
动态周期：q = (20 天波动 ÷ 250 天波动) 在此前所有值里的分位；L = 250^(1−q) × 20^q 天（adaptive.py 第二版）。
强度 M = 过去 L 天涨幅 − 同期现金；M > 0 才有资格；有资格的市场里取 M 最大的一个（按涨幅比，不除以波动）。
都没资格：国债、黄金各用自己的动态周期，M > 0 的取 M 大的；都不行拿现金。每周最后一个交易日决策。
用法：python results/v5/diag/design/layer1.py results/v5/diag/design
"""
import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v3.engine.sessions import decision_dates
from src.v4.r5.design import Markets
out = pathlib.Path(sys.argv[1]); m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
ret = m.signal.loc[:'2015-12-31']; cash = m.cash_id
RISK = {'csi300': 'A 股', 'hsi': '港股', 'spx': '美股'}; DEF = {'cgb-10y': '国债', 'gold': '黄金'}
clr = np.log1p(ret[cash].fillna(0)).cumsum()
def strength(c):
    lr = np.log1p(ret[c]); valid = lr.notna(); lr = lr.fillna(0); cl = lr.cumsum()
    ratio = lr.rolling(20).std() / lr.rolling(250).std()
    q = pd.Series(np.nan, index=lr.index); vals = []
    for t, v in ratio.dropna().items():
        q[t] = (np.array(vals) < v).mean() if len(vals) >= 250 else 0.5; vals.append(v)
    L = np.round(250 ** (1 - q) * 20 ** q)
    i = np.arange(len(cl)); Li = np.nan_to_num(L.values, nan=10**9).astype(np.int64); j = i - Li
    ok = (j >= 0) & valid.rolling(250, min_periods=1).sum().ge(250).values
    jj = np.clip(j, 0, None)
    M = (cl.values - cl.values[jj]) - (clr.values - clr.values[jj])
    return pd.Series(np.where(ok, M, np.nan), index=cl.index), L
S = {}; Ls = {}
for c in [*RISK, *DEF]: S[c], Ls[c] = strength(c)
days = [pd.Timestamp(d).normalize() for d in decision_dates(pd.DatetimeIndex(m.dates), 'week')]
days = [d for d in days if pd.Timestamp('2006-01-01') <= d <= pd.Timestamp('2015-12-31')]
rows = []
for t in days:
    r = {RISK[c]: S[c].get(t) for c in RISK}; r = {k: v for k, v in r.items() if pd.notna(v) and v > 0}
    if r: pick = max(r, key=r.get)
    else:
        d = {DEF[c]: S[c].get(t) for c in DEF}; d = {k: v for k, v in d.items() if pd.notna(v) and v > 0}
        pick = max(d, key=d.get) if d else '现金'
    rows.append(dict(t=t, y=t.year, pick=pick, L_A=Ls['csi300'].get(t), L_US=Ls['spx'].get(t)))
d = pd.DataFrame(rows)
yr = (d.groupby('y').pick.value_counts(normalize=True).unstack().fillna(0) * 100).round(0)
sw = d.groupby('y').pick.apply(lambda s: int((s != s.shift()).iloc[1:].sum()))
Ly = d.groupby('y')[['L_A', 'L_US']].median()
yr['每年换几次'] = sw; yr = yr.join(Ly)
yr.to_csv(out / 'layer1-yearly.csv'); d.to_csv(out / 'layer1-weekly.csv', index=False)
print(yr.to_string())
