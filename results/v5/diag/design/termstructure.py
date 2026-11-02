"""诊断：Owner 2026-11-02 手绘的“多周期加速度期限结构”。只用 ≤2015-12-31 的价格（沪深300、恒生、标普500），计入诊断次数 1。
口径（跑之前写死）：
  尺子 {3,5,10,20,30,60} 天（与手绘一致）。加速度 a_n = 最近 n 天对数涨幅 − 再之前 n 天对数涨幅。
  “跟自己比”：每个 a_n 换成它在此前全部历史里的分位（只用过去，至少 250 个值），0.5 = 平常，接近 1 = 历史上少见的向上加速。
检验一：回调还是见顶（Owner 的分歧点）。
  事件：价格创 60 天新高后，最短尺子（3 天）加速度第一次转负的那天。
  结局：之后先回落 20% → 见顶；先再创新高、且回落不到 15% → 回调；其余不计。
  事件当天看 5、10、20、30 天尺子的分位：Owner 认为见顶时它们“开始衰竭”（比 10 天前明显下降），回调时“还在维持”。
检验二：熊市里的短期反弹，还是真正的反转。
  事件：价格在 60 天新低附近（10 天内创过新低）时，3 天尺子加速度第一次转正。
  结局：之后先涨 20% → 反转；先再创新低 → 熊市反弹。事件当天看 10、20、30、60 天尺子：Owner 认为反转时向下的加速度“逐步放缓”（分位比 20 天前明显上升）。
用法：python results/v5/diag/design/termstructure.py results/v5/diag/design
"""
import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets
out = pathlib.Path(sys.argv[1]); m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
ret = m.signal.loc[:'2015-12-31']
G = [3, 5, 10, 20, 30, 60]
def pct_past(s):
    v = s.values; outp = np.full(len(v), np.nan); hist = []
    import bisect
    for i, x in enumerate(v):
        if np.isnan(x): continue
        if len(hist) >= 250: outp[i] = bisect.bisect_left(hist, x) / len(hist)
        bisect.insort(hist, x)
    return pd.Series(outp, index=s.index)
ev1, ev2 = [], []
for c in ('csi300', 'hsi', 'spx'):
    lr = np.log1p(ret[c].fillna(0)); p = np.exp(lr.cumsum())
    Q = pd.DataFrame({n: pct_past(lr.rolling(n).sum() - lr.rolling(n).sum().shift(n)) for n in G})
    a3 = lr.rolling(3).sum() - lr.rolling(3).sum().shift(3)
    hi60 = p.rolling(60).max(); lo60 = p.rolling(60).min()
    idx = p.index; last = None
    for i in range(300, len(idx) - 1):
        t = idx[i]
        if t < pd.Timestamp('2006-06-01'): continue
        newhigh = (p.iloc[i - 10:i + 1] >= hi60.iloc[i - 10:i + 1] - 1e-12).any()
        if newhigh and a3.iloc[i] < 0 <= a3.iloc[i - 1] and (last is None or (t - last).days > 20):
            peak = p.iloc[i - 10:i + 1].max(); fut = p.iloc[i + 1:]
            dd20 = fut[fut <= peak * 0.8].index[:1]; nh = fut[fut > peak].index[:1]
            if len(dd20) and (not len(nh) or dd20[0] < nh[0]): kind = '见顶'
            elif len(nh) and (fut.loc[:nh[0]].min() / peak - 1) > -0.15: kind = '回调'
            else: kind = None
            if kind:
                last = t
                ev1.append(dict(市场=c, 日期=str(t.date()), 结局=kind, **{f'{n}天分位': Q.at[t, n] for n in (5, 10, 20, 30)},
                                **{f'{n}天比10天前': Q.at[t, n] - Q.iloc[i - 10][n] for n in (5, 10, 20, 30)}))
    last = None
    for i in range(300, len(idx) - 1):
        t = idx[i]
        if t < pd.Timestamp('2006-06-01'): continue
        newlow = (p.iloc[i - 10:i + 1] <= lo60.iloc[i - 10:i + 1] + 1e-12).any()
        if newlow and a3.iloc[i] > 0 >= a3.iloc[i - 1] and (last is None or (t - last).days > 20):
            trough = p.iloc[i - 10:i + 1].min(); fut = p.iloc[i + 1:]
            up20 = fut[fut >= trough * 1.2].index[:1]; nl = fut[fut < trough].index[:1]
            if len(up20) and (not len(nl) or up20[0] < nl[0]): kind = '反转'
            elif len(nl): kind = '熊市反弹'
            else: kind = None
            if kind:
                last = t
                ev2.append(dict(市场=c, 日期=str(t.date()), 结局=kind, **{f'{n}天分位': Q.at[t, n] for n in (10, 20, 30, 60)},
                                **{f'{n}天比20天前': Q.at[t, n] - Q.iloc[i - 20][n] for n in (10, 20, 30, 60)}))
e1 = pd.DataFrame(ev1); e2 = pd.DataFrame(ev2)
e1.to_csv(out / 'ts-top-vs-pullback.csv', index=False); e2.to_csv(out / 'ts-rally-vs-reversal.csv', index=False)
def summ(e, cols):
    g = e.groupby('结局')[cols].mean().round(2); g['事件数'] = e.结局.value_counts(); return g
c1 = ['5天分位', '10天分位', '20天分位', '30天分位', '5天比10天前', '10天比10天前', '20天比10天前', '30天比10天前']
c2 = ['10天分位', '20天分位', '30天分位', '60天分位', '10天比20天前', '20天比20天前', '30天比20天前', '60天比20天前']
s1 = summ(e1, c1); s2 = summ(e2, c2)
# 简单判别：中段尺子（5–30 天）里，比 10 天前下降超过 0.2 的把数 ≥ 2 → 判为见顶
e1['判见顶'] = (e1[[f'{n}天比10天前' for n in (5, 10, 20, 30)]] < -0.2).sum(axis=1) >= 2
e2['判反转'] = (e2[[f'{n}天比20天前' for n in (20, 30, 60)]] > 0.2).sum(axis=1) >= 2
acc1 = pd.crosstab(e1.结局, e1.判见顶); acc2 = pd.crosstab(e2.结局, e2.判反转)
res = dict(回调还是见顶=s1.reset_index().to_dict('records'), 判别一=acc1.to_dict(), 熊市反弹还是反转=s2.reset_index().to_dict('records'), 判别二=acc2.to_dict())
(out / 'termstructure.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
print(s1.to_string()); print(acc1); print(s2.to_string()); print(acc2); print(e1[['市场','日期','结局']].to_string())
