"""诊断：把整个池子当传感器（Owner 2026-11-01 的直觉）。只用 ≤2015-12-31，指数池，计入诊断次数 1。
每天：参加排名的容器里，过去 L 天跑赢现金的比例（宽度，L=20、60）；最弱五分之一的 20 天平均涨幅（底部有没有在加深）；
各容器 60 天涨幅的离散程度。与沪深300 的大转折对照：宽度比单个资产的门槛早多少、晚多少。
宽度急升（20 个交易日内从 30% 以下升到 70% 以上）记为一次“宽度推力”，列出日期和之后沪深300 3、6 个月的涨跌。
用法：python results/v5/diag/design/breadth.py results/v5/diag/design
"""
import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v3.engine.score import lookback_panel
from src.v4.r5.design import Markets
from src.v5.campaign import classes_for, class_map
out = pathlib.Path(sys.argv[1]); spec = load_spec()
m = Markets(spec).get('index', t4=False, allow_substitute=True); cs = m.cash_id
cl = classes_for(list(m.names), cs, class_map())
ret = m.signal.loc[:'2015-12-31']
names = [c for c in m.names if c != cs]
P = {L: lookback_panel(ret, cs, L) for L in (20, 60)}
def breadth(L):
    p = P[L]; ok = p.rankable[names].astype(bool); beat = p.total[names].gt(p.total[cs], axis=0) & ok
    return beat.sum(1) / ok.sum(1).replace(0, np.nan)
b20, b60 = breadth(20), breadth(60)
r20 = P[20].total[names].where(P[20].rankable[names].astype(bool))
bottom = r20.apply(lambda row: row.dropna().nsmallest(max(1, int(row.notna().sum() / 5))).mean(), axis=1)
disp = P[60].total[names].where(P[60].rankable[names].astype(bool)).std(axis=1)
lv = (1 + ret['csi300'].fillna(0)).cumprod()
df = pd.DataFrame(dict(b20=b20, b60=b60, bottom20=bottom, disp60=disp, csi300=lv)).loc['2006':]
df.to_csv(out / 'breadth.csv', float_format='%.4f')
# 宽度推力
th = []
x = df.b20
for i in range(20, len(x)):
    w = x.iloc[i - 20:i + 1]
    if x.iloc[i] >= 0.7 and w.min() <= 0.3 and (not th or (x.index[i] - th[-1]).days > 60):
        th.append(x.index[i])
thr = []
for t in th:
    p0 = lv.loc[t]; f3 = lv.loc[t:].iloc[min(63, len(lv.loc[t:]) - 1)]; f6 = lv.loc[t:].iloc[min(126, len(lv.loc[t:]) - 1)]
    thr.append(dict(日期=str(t.date()), 三个月后沪深300=round(f3 / p0 - 1, 3), 六个月后=round(f6 / p0 - 1, 3)))
# 转折点附近：宽度跌破 30%（离场信号）、升回 50%（回场信号）的日期
ev = {}
for name, t, kind in (('2007-10 顶', '2007-10-16', 'top'), ('2008-11 底', '2008-11-04', 'bot'), ('2015-06 顶', '2015-06-08', 'top'), ('2015-08 底', '2015-08-26', 'bot')):
    t = pd.Timestamp(t); s = df.b20
    if kind == 'top':
        pre = s.loc[:t].iloc[-60:]; aft = s.loc[t:]
        hit = aft[aft < 0.3].index[:1]
        ev[name] = dict(顶前60天宽度均值=round(pre.mean(), 2), 顶当天宽度=round(s.loc[:t].iloc[-1], 2), 跌破30_晚了天数=int(len(s.loc[t:hit[0]]) - 1) if len(hit) else None,
                        那时沪深300已跌=round(lv.loc[hit[0]] / lv.loc[t] - 1, 3) if len(hit) else None, 底部五分之一20天涨幅_顶前=round(df.bottom20.loc[:t].iloc[-20:].mean(), 3))
    else:
        aft = s.loc[t:]; hit = aft[aft > 0.5].index[:1]
        ev[name] = dict(底当天宽度=round(s.loc[:t].iloc[-1], 2), 升过50_晚了天数=int(len(s.loc[t:hit[0]]) - 1) if len(hit) else None,
                        那时沪深300已涨=round(lv.loc[hit[0]] / lv.loc[t] - 1, 3) if len(hit) else None)
yr = df.groupby(df.index.year)[['b20', 'b60', 'disp60']].mean().round(2)
res = dict(宽度推力=thr, 转折点=ev, 每年=yr.to_dict('index'))
(out / 'breadth.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str)); print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
