"""v5 设计稿的证据（描述性诊断，设计期 2006–2015，只用 ≤2015-12-31 的中国数据；不跑任何新策略）。
1. 各回看期的“该不该持有”信号：大市场代表在 L 天跑赢现金时，下个月比现金多赚多少；以及每年开关切换几次。
2. E2 规则在两个池子里每年想持有的风险仓位、现金，以及合格只数（信号层面目标，不含离场和成交）。
3. A1 每月想持有什么（按其规则用信号序列近似）。
用法：python results/v5/diag/design/evidence.py results/v5/diag/design
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

out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
spec = load_spec(); M = Markets(spec)
REPS = ['csi300', 'csi500', 'hsi', 'spx', 'ndx100', 'gold', 'cgb-10y']
res = {}

# ---------- 1. 时序信号按回看期 ----------
m = M.get('index', t4=False, allow_substitute=True); cash = m.cash_id
ret = m.signal.loc[:'2015-12-31']
lr = np.log1p(ret.where(ret > -1).fillna(0.0))
fwd = np.expm1(lr[::-1].rolling(21, min_periods=21).sum()[::-1].shift(-1))
fx = fwd.sub(fwd[cash], axis=0)
days = [pd.Timestamp(d).normalize() for d in decision_dates(pd.DatetimeIndex(m.dates), 'month')]
days = [d for d in days if pd.Timestamp('2006-01-01') <= d <= pd.Timestamp('2015-11-30')]
rows = []
for L in spec.lookbacks:
    p = lookback_panel(ret, cash, L)
    for t in days:
        for c in REPS:
            if not bool(p.rankable.at[t, c]) or pd.isna(fx.at[t, c]): continue
            on = p.total.at[t, c] > p.total.at[t, cash]
            rows.append(dict(t=t, L=L, c=c, on=on, fx=fx.at[t, c]))
ts = pd.DataFrame(rows)
sig = []
for L, g in ts.groupby('L'):
    mon = g.groupby(['t', 'on']).fx.mean().unstack()  # 每月：开着的平均、关着的平均
    d = (mon[True] - mon[False]).dropna()
    flips = g.sort_values('t').groupby('c').on.apply(lambda s: (s != s.shift()).iloc[1:].sum()).sum() / len(REPS) / 10
    sig.append(dict(L=L, 开着时下月超额=round(g[g.on].fx.mean() * 100, 2), 关着时下月超额=round(g[~g.on].fx.mean() * 100, 2),
                    差=round(d.mean() * 100, 2), 可信度=round(d.mean() / d.std() * math.sqrt(len(d)), 2), 月数=len(d),
                    开着占比=round(g.on.mean(), 2), 每年切换次数=round(flips, 1)))
sig = pd.DataFrame(sig); sig.to_csv(out / 'ts-by-lookback.csv', index=False); res['ts'] = sig.to_dict('records')

# ---------- 2. E2 规则两个池子的目标 ----------
def e2_targets(pool):
    mk = M.get(pool, t4=False, allow_substitute=True); cs = mk.cash_id
    names = [*list(mk.names), cs]; cl = classes_for(list(mk.names), cs, class_map())
    liq = mk.liquidity if pool == 'tradable' else None
    ds = [pd.Timestamp(d).normalize() for d in decision_dates(pd.DatetimeIndex(mk.dates), 'month')]
    ds = [d for d in ds if pd.Timestamp('2006-01-01') <= d <= pd.Timestamp('2015-12-31')]
    pans = {L: lookback_panel(mk.signal, cs, L) for L in spec.lookbacks}
    rr = []
    for t in ds:
        for L, p in pans.items():
            if t not in p.score.index: continue
            sl = sleeves_on(p, t, names, cl, cs, liq)
            part = sum(s.participates for s in sl)
            el = sorted([s for s in sl if s.participates and s.beats_cash and not math.isnan(s.score)], key=lambda s: -s.score)
            for n in (3, 5, 8):
                top = el[:n]
                risk = sum(cl[s.container_id] not in ('国债', '黄金') for s in top) / n
                dfn = sum(cl[s.container_id] in ('国债', '黄金') for s in top) / n
                rr.append(dict(t=t, y=t.year, L=L, n=n, part=part, elig=len(el), risk=risk, defense=dfn, cash=1 - len(top) / n))
    return pd.DataFrame(rr)
e2 = {p: e2_targets(p) for p in ('index', 'tradable')}
yr = pd.concat({p: d.groupby('y')[['part', 'elig', 'risk', 'defense', 'cash']].mean() for p, d in e2.items()}, axis=1).round(2)
yr.to_csv(out / 'e2-targets-yearly.csv')
res['e2_avg'] = {p: d[['risk', 'defense', 'cash']].mean().round(3).to_dict() for p, d in e2.items()}
res['e2_half'] = {p: d.assign(h=np.where(d.y <= 2010, '2006-10', '2011-15')).groupby('h')[['risk', 'defense', 'cash']].mean().round(3).to_dict('index') for p, d in e2.items()}
by_L = e2['index'].assign(h=np.where(e2['index'].y <= 2010, '06-10', '11-15')).groupby(['h', 'L'])[['risk', 'cash']].mean().round(2)
by_L.to_csv(out / 'e2-risk-by-lookback.csv'); res['e2_by_L'] = by_L.reset_index().to_dict('records')

# ---------- 3. A1 近似 ----------
tot = np.expm1(lr.rolling(250, min_periods=250).sum())
a1 = []
for t in days:
    if pd.isna(tot.at[t, 'spx']): continue
    on = tot.at[t, 'spx'] > tot.at[t, cash]
    pick = ('spx' if tot.at[t, 'spx'] >= tot.at[t, 'csi300'] else 'csi300') if on else 'cgb-10y'
    a1.append(dict(t=t, y=t.year, pick=pick))
a1 = pd.DataFrame(a1)
a1y = a1.groupby('y').pick.value_counts(normalize=True).unstack().fillna(0).round(2)
a1y.to_csv(out / 'a1-picks-yearly.csv'); res['a1_risk_half'] = a1.assign(r=a1.pick != 'cgb-10y', h=np.where(a1.y <= 2010, '2006-10', '2011-15')).groupby('h').r.mean().round(2).to_dict()
res['a1_switches_per_year'] = round((a1.pick != a1.pick.shift()).iloc[1:].sum() / 10, 1)
(out / 'summary.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
print(sig.to_string()); print(yr.to_string()); print(json.dumps({k: res[k] for k in ('e2_avg', 'e2_half', 'a1_risk_half', 'a1_switches_per_year')}, ensure_ascii=False, indent=1)); print(by_L.to_string()); print(a1y.to_string())
