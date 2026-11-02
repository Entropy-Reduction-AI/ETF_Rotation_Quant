"""诊断（Owner 2026-11-02 的观察：钱涌向当下波动最高、人声鼎沸的地方）。只用 ≤2015-12-31 的 A 股十个行业，计入诊断次数 1。
每月末：在过去 60 天跑赢现金的行业里，取 60 天波动最高的一个（最热）；对照：取 60 天涨幅最高的一个（最强）。
看下一个月（21 个交易日）相对十个行业平均的超额；按前后两段、按年；以及“最热”之后 3 个月的最大回撤，看热的地方是不是也最容易急跌。
用法：python results/v5/diag/design/hot.py results/v5/diag/design
"""
import sys, pathlib, json, math
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v3.engine.sessions import decision_dates
from src.v4.r5.design import Markets
out = pathlib.Path(sys.argv[1]); m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
SEC = [c for c in m.signal.columns if c.startswith('allshare-')]; cash = m.cash_id
r = m.signal.loc[:'2015-12-31']; lr = np.log1p(r[SEC + [cash]].fillna(0))
R60 = np.expm1(lr.rolling(60).sum()); V60 = lr[SEC].rolling(60).std()
f21 = np.expm1(lr[::-1].rolling(21, min_periods=21).sum()[::-1].shift(-1))
lv = np.exp(lr[SEC].cumsum())
days = [pd.Timestamp(d).normalize() for d in decision_dates(pd.DatetimeIndex(m.dates), 'month')]
days = [d for d in days if pd.Timestamp('2006-01-01') <= d <= pd.Timestamp('2015-11-30')]
rows = []
for t in days:
    ok = [s for s in SEC if R60.at[t, s] > R60.at[t, cash]]
    if not ok: continue
    hot = max(ok, key=lambda s: V60.at[t, s]); strong = max(ok, key=lambda s: R60.at[t, s])
    avg = f21.loc[t, SEC].mean()
    w = lv[hot].loc[t:].iloc[:64]; dd = (w / w.cummax() - 1).min()
    wa = lv[SEC].loc[t:].iloc[:64]; dda = (wa / wa.cummax() - 1).min().mean()
    rows.append(dict(t=t, y=t.year, hot=hot, strong=strong, same=hot == strong, hot_x=f21.at[t, hot] - avg, strong_x=f21.at[t, strong] - avg, hot_dd=dd, avg_dd=dda))
d = pd.DataFrame(rows).dropna()
cred = lambda s: round(s.mean() / s.std() * math.sqrt(len(s)), 2)
res = dict(月数=len(d), 最热与最强是同一个的比例=round(d.same.mean(), 2),
           最热_下月超额=round(d.hot_x.mean() * 100, 2), 最热_可信度=cred(d.hot_x),
           最强_下月超额=round(d.strong_x.mean() * 100, 2), 最强_可信度=cred(d.strong_x),
           最热_前五年=round(d[d.y <= 2010].hot_x.mean() * 100, 2), 最热_后五年=round(d[d.y > 2010].hot_x.mean() * 100, 2),
           最热之后3个月最大回撤=round(d.hot_dd.mean(), 3), 行业平均之后3个月最大回撤=round(d.avg_dd.mean(), 3),
           最热行业出现次数=d.hot.value_counts().to_dict(),
           按年最热=d.groupby('y').hot.agg(lambda s: s.value_counts().index[0]).to_dict())
(out / 'hot.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str)); print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
