"""v5.1 设计评审的事前画像：只用信号层面的排名和目标持仓（月路、四个回看期、N=3/5/8 平均），不算任何组合收益。
E2 = 全局前 N；v5.1 = 同一张表，每类最多 ceil(N/2) 只，被截的名额顺延给下一名，合格的不够 N 只则拿现金。
不含 10% 离场、成交限制和周路，所以是“规则想持有什么”，不是实际持仓。设计期 2006–2015、指数池。
用法：python results/v5/diag/v51/profile.py results/v5/diag/v51
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
spec = load_spec(); m = Markets(spec).get('index', t4=False, allow_substitute=True)
cash = m.cash_id; names = [*list(m.names), cash]
cls = classes_for(list(m.names), cash, class_map())
NS = (3, 5, 8)

def pick(elig, n, cap):
    got, per = [], {}
    for s in elig:
        c = cls[s.container_id]
        if cap and per.get(c, 0) >= cap: continue
        got.append(s.container_id); per[c] = per.get(c, 0) + 1
        if len(got) == n: break
    return got

rows, ex = [], []
days = [pd.Timestamp(d).normalize() for d in decision_dates(pd.DatetimeIndex(m.dates), 'month')]
days = [d for d in days if pd.Timestamp('2006-01-01') <= d <= pd.Timestamp('2015-12-31')]
panels = {L: lookback_panel(m.signal, cash, L) for L in spec.lookbacks}
for t in days:
    for L, p in panels.items():
        if t not in p.score.index: continue
        sl = sleeves_on(p, t, names, cls, cash, None)
        elig = sorted([s for s in sl if s.participates and s.beats_cash and not math.isnan(s.score)], key=lambda s: (-s.score, s.container_id))
        for n in NS:
            for arm, cap in (('E2', None), ('v5.1', math.ceil(n / 2))):
                g = pick(elig, n, cap)
                w = {}
                for c in g: w[cls[c]] = w.get(cls[c], 0) + 1 / n
                w['现金'] = 1 - len(g) / n
                rows.append(dict(date=t, L=L, N=n, arm=arm, bind=(arm == 'v5.1' and pick(elig, n, None) != g), **w))
                if L == 60 and n == 5 and t.strftime('%Y-%m') in ('2007-05', '2011-07', '2012-05', '2015-06', '2009-03'):
                    ex.append(dict(date=t.date(), arm=arm, picks=' · '.join(f'{c}（{cls[c]}）' for c in g) or '全现金'))
df = pd.DataFrame(rows)
for k in ['A股', '港股', '美股', '其他海外', '商品', '国债', '黄金', '现金']:
    df[k] = df.get(k, 0.0)
df = df.fillna(0.0)
df.to_csv(out / 'targets.csv', index=False, float_format='%.4f')
pd.DataFrame(ex).to_csv(out / 'examples.csv', index=False)
K = ['A股', '港股', '美股', '其他海外', '商品', '国债', '黄金', '现金']
df['y'] = df.date.dt.year
avg = df.groupby(['arm'])[K].mean().mul(100).round(1)
yr = df.groupby(['y', 'arm'])[['A股', '港股', '美股', '国债', '黄金', '现金']].mean().mul(100).round(0)
v = df[df.arm == 'v5.1']
summ = {'上限触发的组占比': round(v.bind.mean(), 3),
        '按 N': v.groupby('N').bind.mean().round(3).to_dict(),
        '按年': v.groupby('y').bind.mean().round(2).to_dict()}
(out / 'summary.json').write_text(json.dumps(summ, ensure_ascii=False, indent=1))
yr.to_csv(out / 'yearly.csv'); avg.to_csv(out / 'average.csv')
print(json.dumps(summ, ensure_ascii=False)); print(avg.to_string()); print(yr.unstack('arm').to_string()); print(pd.DataFrame(ex).to_string())
