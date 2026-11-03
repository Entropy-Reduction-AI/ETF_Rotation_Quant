"""诊断：Owner 2026-11-02 的“传导”直觉。只用 ≤2015-12-31 价格，不算组合收益，计入诊断次数 1。
事件沿用 termstructure.py（创 60 天新高后 3 天加速度首次转负；见顶 = 先跌 20%，回调 = 先创新高且回撤 < 15%）。
对事件后第 k 天（k = 0,5,10,15,20,30,40），只看那天“结局还没揭晓”的事件（还没跌满 20%、也还没创新高），算：
  传导前沿 = 28 把尺子（3–250 天对数等距）里速度已转负的比例（速度 = n 天对数涨幅 ÷ σ√n，σ 只用过去）；
  长尺子速度变化 = 60 天以上尺子的平均速度，比事件当天变了多少（回调：先降后回；见顶：持续降）；
  已承受回撤 = 当天价格 ÷ 事件前后最高点 − 1。
分得开的程度用 AUC（0.5 = 抛硬币，1 = 完全分开）：传导前沿 vs 已承受回撤，看传导是否提供了“价格已经跌了多少”之外的信息。
用法：python results/v5/diag/design/propagate.py results/v5/diag/design
"""
import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets
out = pathlib.Path(sys.argv[1]); m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
ret = m.signal.loc[:'2015-12-31']
G = sorted(set(np.round(np.geomspace(3, 250, 30)).astype(int)))
ev = pd.read_csv(out / 'ts-top-vs-pullback.csv')
def auc(pos, neg):
    pos, neg = np.asarray(pos), np.asarray(neg)
    if len(pos) == 0 or len(neg) == 0: return np.nan
    return float(np.mean([(p > neg).mean() + 0.5 * (p == neg).mean() for p in pos]))
data = {}
for c in ev['市场'].unique():
    lr = np.log1p(ret[c].fillna(0)); sig = lr.rolling(250).std().shift(1); p = np.exp(lr.cumsum())
    V = pd.DataFrame({n: lr.rolling(n).sum() / (sig * np.sqrt(n)) for n in G})
    data[c] = (p, V)
K = [0, 5, 10, 15, 20, 30, 40]; rows = []
for _, e in ev.iterrows():
    p, V = data[e['市场']]; i = p.index.get_loc(pd.Timestamp(e['日期']))
    peak0 = p.iloc[i - 10:i + 1].max(); longs = [n for n in G if n >= 60]
    for k in K:
        if i + k >= len(p): continue
        path = p.iloc[i:i + k + 1]
        if k > 0 and (path.min() <= peak0 * 0.8 or path.iloc[1:].max() > peak0): continue  # 结局已揭晓
        rows.append(dict(市场=e['市场'], 日期=e['日期'], 结局=e['结局'], k=k,
                         传导前沿=float((V.iloc[i + k] < 0).mean()),
                         长尺子变化=float(V.iloc[i + k][longs].mean() - V.iloc[i][longs].mean()),
                         已承受回撤=float(p.iloc[i + k] / peak0 - 1)))
d = pd.DataFrame(rows); d.to_csv(out / 'propagate.csv', index=False)
res = []
for k in K:
    x = d[d.k == k]; t, b = x[x.结局 == '见顶'], x[x.结局 == '回调']
    res.append(dict(k=k, 未揭晓_见顶=len(t), 未揭晓_回调=len(b),
                    前沿_见顶=round(t.传导前沿.mean(), 2), 前沿_回调=round(b.传导前沿.mean(), 2),
                    长尺子变化_见顶=round(t.长尺子变化.mean(), 2), 长尺子变化_回调=round(b.长尺子变化.mean(), 2),
                    回撤_见顶=round(t.已承受回撤.mean(), 3), 回撤_回调=round(b.已承受回撤.mean(), 3),
                    AUC_前沿=round(auc(t.传导前沿, b.传导前沿), 2), AUC_回撤=round(auc(-t.已承受回撤, -b.已承受回撤), 2),
                    AUC_长尺子=round(auc(-t.长尺子变化, -b.长尺子变化), 2)))
r = pd.DataFrame(res); (out / 'propagate.json').write_text(r.to_json(orient='records', force_ascii=False, indent=1))
print(r.to_string(index=False))
# 前沿到达“过半尺子转负”时，见顶与回调各占多少、此时已跌多少
half = d[d.传导前沿 >= 0.5].sort_values('k').groupby(['市场', '日期']).first()
print('\n前沿首次过半：', half.groupby('结局').agg(个数=('k', 'size'), 中位天数=('k', 'median'), 中位回撤=('已承受回撤', 'median')).round(3).to_string())
