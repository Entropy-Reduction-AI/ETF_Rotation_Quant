"""v5 设计硬伤的描述性诊断（只用设计期 2006–2015 的指数池，不新增策略，不算 2016 年以后的收益）。

每个调仓决策日、每个回看期，把 v5 的“每类最强”放回全局排名里看：
1. 开着几个风险大类（k），防守位打开过几次；
2. v5 的每类最强在全部跑赢现金的容器里排第几，有多少仓位落在全局前 5 名以外；
3. 被选中以后下一个月实际涨了多少（按全局排名分档），检验“每类最强”是不是真的强。
用法：python results/v5/diag/memo/flaws.py results/v5/diag/memo/flaws
"""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v3.engine.score import lookback_panel
from src.v3.engine.sessions import decision_dates
from src.v4.r5.design import Markets
from src.v5.campaign import classes_for, class_map
from src.v5.engine.allocate import sleeves_on, group_weights, _winners
from src.v5.engine.classes import RISK_CLASSES, DEFENSIVE_CLASSES

out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
spec = load_spec(); markets = Markets(spec)
m = markets.get('index', t4=False, allow_substitute=True)
cls = classes_for(list(m.names), m.cash_id, class_map())
cash = m.cash_id
names = [*list(m.names), cash]
ret = m.signal
logret = np.log1p(ret.where(ret > -1).fillna(0.0))
fwd = np.expm1(logret[::-1].rolling(21, min_periods=1).sum()[::-1].shift(-1))  # 下一个 21 个交易日
fwd_x = fwd.sub(fwd[cash], axis=0)  # 相对现金

rows, picks = [], []
for L in spec.lookbacks:
    p = lookback_panel(ret, cash, L)
    for day in decision_dates(pd.DatetimeIndex(m.dates), 'month'):
        t = pd.Timestamp(day).normalize()
        if t < pd.Timestamp('2006-01-01') or t > pd.Timestamp('2015-12-31') or t not in p.score.index:
            continue
        sl = sleeves_on(p, t, names, cls, cash, None)
        elig = sorted([s for s in sl if s.participates and s.beats_cash and np.isfinite(s.score) or (s.participates and s.beats_cash and np.isinf(s.score))],
                      key=lambda s: (-s.score, s.container_id))
        rank = {s.container_id: i + 1 for i, s in enumerate(elig)}
        risk = _winners(sl, RISK_CLASSES)
        k = sum(v is not None for v in risk.values())
        w = group_weights(sl, cash_id=cash)
        top = elig[0].score if elig else np.nan
        rows.append(dict(date=t, L=L, k=k, n_elig=len(elig),
                         cash=w.get(cash, 0.0),
                         defense=sum(v for c, v in w.items() if c != cash and cls.get(c) in DEFENSIVE_CLASSES)))
        for c, v in w.items():
            if c == cash or v == 0:
                continue
            picks.append(dict(date=t, L=L, id=c, cls=cls[c], w=v, rank=rank.get(c, np.nan),
                              rel=(next(s.score for s in sl if s.container_id == c) / top) if top and np.isfinite(top) else np.nan,
                              fwd=fwd_x.at[t, c] if t in fwd_x.index else np.nan))
        # E2 式对照：全局前 5、每只 1/5、不足拿现金（只做描述，不是 B0 的完整执行）
        for s in elig[:5]:
            picks.append(dict(date=t, L=L, id=s.container_id, cls=cls[s.container_id], w=0.2, rank=rank[s.container_id],
                              rel=s.score / top, fwd=fwd_x.at[t, s.container_id], arm='E2top5'))

g = pd.DataFrame(rows); pk = pd.DataFrame(picks); pk['arm'] = pk['arm'].fillna('v5')
g.to_csv(out / 'groups.csv', index=False); pk.to_csv(out / 'picks.csv', index=False)

v5 = pk[pk.arm == 'v5']
risk5 = v5[v5.cls.isin(RISK_CLASSES)]
summ = {}
summ['k 分布（组占比）'] = g.k.value_counts(normalize=True).sort_index().round(3).to_dict()
summ['k=0 的组占比'] = round((g.k == 0).mean(), 3)
summ['防守位平均仓位'] = round(g.defense.mean(), 3)
summ['现金平均仓位'] = round(g.cash.mean(), 3)
summ['v5 风险仓位里落在全局前5以外的占比'] = round(risk5.loc[risk5['rank'] > 5, 'w'].sum() / risk5.w.sum(), 3)
summ['v5 风险仓位里落在全局前3以外的占比'] = round(risk5.loc[risk5['rank'] > 3, 'w'].sum() / risk5.w.sum(), 3)
summ['v5 风险持仓得分/当日最高分（加权中位）'] = round(np.average(risk5.rel.clip(-5, 5), weights=risk5.w), 3)
bucket = pd.cut(risk5['rank'], [0, 5, 10, 1000], labels=['全局前5', '第6–10', '第11名以后'])
summ['v5 各档仓位占比'] = risk5.groupby(bucket, observed=False).w.sum().div(risk5.w.sum()).round(3).to_dict()
summ['v5 各档下月超额（月均，%）'] = (risk5.groupby(bucket, observed=False).apply(lambda d: np.average(d.fwd, weights=d.w) * 100, include_groups=False).round(2).to_dict())
e2 = pk[pk.arm == 'E2top5']
summ['E2 前5 下月超额（月均，%）'] = round(e2.fwd.mean() * 100, 2)
summ['v5 风险持仓下月超额（加权，%）'] = round(np.average(risk5.fwd, weights=risk5.w) * 100, 2)
by_cls = risk5.groupby('cls').apply(lambda d: pd.Series({
    '开着的组占比': d[['date', 'L']].drop_duplicates().shape[0] / g.shape[0],
    '平均仓位(开着时)': d.w.mean(),
    '全局排名中位': d['rank'].median(),
    '落在前5以外的比例': (d['rank'] > 5).mean(),
    '下月超额%': d.fwd.mean() * 100}), include_groups=False).round(3)
by_cls.to_csv(out / 'by-class.csv')
import json
(out / 'summary.json').write_text(json.dumps(summ, ensure_ascii=False, indent=1, default=str))
print(json.dumps(summ, ensure_ascii=False, indent=1, default=str)); print(by_cls.to_string())
