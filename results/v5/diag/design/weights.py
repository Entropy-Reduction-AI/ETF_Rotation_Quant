"""诊断（描述，不是规则画像）：Owner 2026-11-03 的“尺子权重随市场动态调整”。只用 ≤2015-12-31 价格，计入诊断次数 1。
跑前写死：28 把尺子（3–250 天对数等距），速度 v_n = n 天对数涨幅 ÷ (σ·√n)，σ 为过去 250 天日波动（只用过去）。
响度 = |v_n| 在最近 n 天里的平均（每把尺子用自己的长度，不新增参数），再换成它在自己过去历史里的分位（至少 250 个值）。
权重 w_n ∝ 响度分位。重心 = exp(Σ w_n·ln n)：权重集中在哪一档尺子上，单位是天；等权时重心约 27 天。
输出 weights.csv（每日重心、等权水平、响度加权水平），和沪深300 几段行情里的重心。
用法：python results/v5/diag/design/weights.py results/v5/diag/design
"""
import sys, pathlib, json, bisect
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets
out = pathlib.Path(sys.argv[1]); m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
ret = m.signal.loc[:'2015-12-31']
G = sorted(set(np.round(np.geomspace(3, 250, 30)).astype(int)))
def pct_past(s):
    v = s.values; o = np.full(len(v), np.nan); h = []
    for i, x in enumerate(v):
        if np.isnan(x): continue
        if len(h) >= 250: o[i] = bisect.bisect_left(h, x) / len(h)
        bisect.insort(h, x)
    return o
res = {}
for c in ('csi300', 'hsi', 'spx'):
    lr = np.log1p(ret[c].fillna(0)); sig = lr.rolling(250).std().shift(1)
    V = pd.DataFrame({n: lr.rolling(n).sum() / (sig * np.sqrt(n)) for n in G})
    Lq = pd.DataFrame({n: pct_past(V[n].abs().rolling(n).mean()) for n in G}, index=V.index)
    W = Lq.div(Lq.sum(axis=1), axis=0)
    ctr = np.exp((W * np.log(G)).sum(axis=1, min_count=len(G)))
    df = pd.DataFrame({'重心天数': ctr, '等权水平': V.mean(axis=1), '响度加权水平': (W * V).sum(axis=1, min_count=len(G)),
                       '价格': np.exp(lr.cumsum())}).loc['2006-01-01':]
    df.to_csv(out / f'weights-{c}.csv')
    if c == 'csi300':
        seg = {'2006 牛市前段': ('2006-01-01', '2006-12-31'), '2007 上半年加速': ('2007-01-01', '2007-06-30'), '2007-10 见顶前三个月': ('2007-07-16', '2007-10-16'),
               '2008 上半年第一波暴跌': ('2007-10-17', '2008-04-30'), '2008 下半年第二波': ('2008-05-01', '2008-11-04'), '2008-11 见底后三个月': ('2008-11-05', '2009-02-04'),
               '2009 反弹中段': ('2009-02-05', '2009-07-31'), '2011–13 震荡': ('2011-01-01', '2013-12-31'), '2015 加速至见顶': ('2015-03-01', '2015-06-12'), '2015 急跌': ('2015-06-13', '2015-09-15')}
        res = {k: dict(重心天数中位=round(float(df.loc[a:b, '重心天数'].median()), 0)) for k, (a, b) in seg.items()}
        # 2008 见底后，水平转正的天数：等权 vs 响度加权
        t0 = pd.Timestamp('2008-11-04'); aft = df.loc[t0:]
        for col in ('等权水平', '响度加权水平'):
            x = aft[aft[col] > 0].index[:1]
            res[f'2008-11 见底后{col}首次转正'] = None if not len(x) else f"{(x[0] - t0).days} 天，离底 +{round((aft.价格.loc[x[0]] / aft.价格.iloc[0] - 1) * 100, 1)}%"
(out / 'weights.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
print(json.dumps(res, ensure_ascii=False, indent=1)); print('等权重心', round(float(np.exp(np.mean(np.log(G)))), 1))
