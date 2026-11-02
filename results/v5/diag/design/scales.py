"""诊断：Owner 2026-11-02 的“一轮完整走势”复盘。只用 ≤2015-12-31 的价格，计入诊断次数 1。
1. 多尺度加速度：尺子 n ∈ {3,5,10,20,40,60,120} 天；加速度 a_n = 最近 n 天涨幅 − 再之前 n 天涨幅，除以 (过去 250 天日波动 × √(2n)) 化成“几倍于噪音”。沪深300、标普500。
2. 换仓为什么多：第一层（layer1.py 的规则）每一次换仓，当时信号离“噪音”有多远：
   领先市场换人时，前两名强度差 ÷ 噪音；进出场时，强度 ÷ 噪音（噪音 = 日波动 × √L）。
用法：python results/v5/diag/design/scales.py results/v5/diag/design
"""
import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v3.engine.sessions import decision_dates
from src.v4.r5.design import Markets
out = pathlib.Path(sys.argv[1]); m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
ret = m.signal.loc[:'2015-12-31']; cash = m.cash_id
NS = (3, 5, 10, 20, 40, 60, 120)
acc = {}
for c in ('csi300', 'spx'):
    lr = np.log1p(ret[c].fillna(0)); sd = lr.rolling(250, min_periods=120).std()
    A = pd.DataFrame({n: (lr.rolling(n).sum() - lr.rolling(n).sum().shift(n)) / (sd * np.sqrt(2 * n)) for n in NS}).loc['2006':]
    A.to_csv(out / f'scales-{c}.csv', float_format='%.3f'); acc[c] = A
# 2. 换仓时信号离噪音多远
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
    noise = lr.rolling(250).std() * np.sqrt(L)
    return M, M / noise
S = {c: strength(c) for c in RISK + DEF}
days = [pd.Timestamp(d).normalize() for d in decision_dates(pd.DatetimeIndex(m.dates), 'week')]
days = [d for d in days if pd.Timestamp('2006-01-01') <= d <= pd.Timestamp('2015-12-31')]
prev, rows = None, []
for t in days:
    r = {c: S[c][0].get(t) for c in RISK}; r = {k: v for k, v in r.items() if pd.notna(v) and v > 0}
    if r:
        pick = max(r, key=r.get)
    else:
        d = {c: S[c][0].get(t) for c in DEF}; d = {k: v for k, v in d.items() if pd.notna(v) and v > 0}; pick = max(d, key=d.get) if d else 'cash'
    if prev is not None and pick != prev:
        if prev in RISK and pick in RISK:
            kind = '领先市场换人'; z = abs(S[pick][1].get(t) - S[prev][1].get(t))
        else:
            kind = '进出场'; c = pick if pick in RISK else prev; z = abs(S[c][1].get(t)) if c in S else np.nan
        rows.append(dict(t=t, y=t.year, kind=kind, frm=prev, to=pick, z=z))
    prev = pick
sw = pd.DataFrame(rows); sw.to_csv(out / 'switches.csv', index=False)
res = dict(换仓总数=len(sw), 按类型=sw.kind.value_counts().to_dict(),
           信号在噪音半倍以内的占比=round((sw.z < 0.5).mean(), 2), 一倍以内=round((sw.z < 1).mean(), 2),
           按年=sw.groupby('y').apply(lambda d: dict(次数=len(d), 半倍以内=int((d.z < 0.5).sum())), include_groups=False).to_dict())
(out / 'switches.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str)); print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
