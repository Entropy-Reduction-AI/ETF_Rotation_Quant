"""诊断：国债、黄金靠“涨幅 ÷ 波动”排在风险冠军前面时，下个月谁赚得多（相对现金，21 个交易日，不扣成本）。
只用设计期 ≤2015-12-31 的中国数据；回答 v5 设计稿“防守怎么进来”这一个问题，计入诊断次数 1。
用法：python results/v5/diag/design/displace.py results/v5/diag/design
"""
import sys, pathlib, math, json
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v3.engine.score import lookback_panel
from src.v3.engine.sessions import decision_dates
from src.v4.r5.design import Markets
from src.v5.campaign import classes_for, class_map
from src.v5.engine.allocate import sleeves_on
out = pathlib.Path(sys.argv[1]); spec = load_spec()
m = Markets(spec).get('index', t4=False, allow_substitute=True); cs = m.cash_id
names = [*list(m.names), cs]; cl = classes_for(list(m.names), cs, class_map())
ret = m.signal.loc[:'2015-12-31']; lr = np.log1p(ret.where(ret > -1).fillna(0.0))
fwd = np.expm1(lr[::-1].rolling(21, min_periods=21).sum()[::-1].shift(-1)); fx = fwd.sub(fwd[cs], axis=0)
ds = [pd.Timestamp(d).normalize() for d in decision_dates(pd.DatetimeIndex(m.dates), 'month')]
ds = [d for d in ds if pd.Timestamp('2006-01-01') <= d <= pd.Timestamp('2015-11-30')]
rows = []
for L in spec.lookbacks:
    p = lookback_panel(ret, cs, L)
    for t in ds:
        sl = sleeves_on(p, t, names, cl, cs, None)
        el = sorted([s for s in sl if s.participates and s.beats_cash and not math.isnan(s.score)], key=lambda s: -s.score)
        risk = [s for s in el if cl[s.container_id] not in ('国债', '黄金')]
        dfn = [s for s in el if cl[s.container_id] in ('国债', '黄金')]
        if not risk or not dfn: continue
        if dfn[0].score > risk[0].score:  # 防守冠军排在最强风险冠军前面
            rows.append(dict(t=t, L=L, risk=fx.at[t, risk[0].container_id], defense=fx.at[t, dfn[0].container_id]))
d = pd.DataFrame(rows).dropna(); d['diff'] = d.risk - d.defense
mon = d.groupby('t')['diff'].mean()
res = dict(组数=len(d), 月数=len(mon), 风险冠军下月超额=round(d.risk.mean() * 100, 2), 防守冠军下月超额=round(d.defense.mean() * 100, 2),
           差=round(mon.mean() * 100, 2), 可信度=round(mon.mean() / mon.std() * math.sqrt(len(mon)), 2),
           风险冠军赢的月份占比=round((mon > 0).mean(), 2),
           按年=d.assign(y=d.t.dt.year).groupby('y')['diff'].mean().mul(100).round(1).to_dict(),
           按回看期=d.groupby('L')['diff'].mean().mul(100).round(2).to_dict())
(out / 'displace.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str)); print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
