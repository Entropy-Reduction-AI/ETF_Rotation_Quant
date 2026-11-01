"""v5 设计稿“冠军赛”的事前画像：信号层面的目标持仓，不算收益。设计期 2006–2015，两个池子。
规则：每个回看期 L，七个大类各出一只冠军（类内跑赢现金且得分最高）；冠军之间按同一个得分排名；
取前 k 名平分（k ∈ {1,2,3} 三路平均）；合格冠军不足 k 名时，钱平分给合格的；一个都没有才拿现金。
第三种：冠军赛·防守补位（风险冠军先按得分取，名额不满再由跑赢现金的防守冠军补，仍不满则平分给已选的）。另一把尺子：冠军赛·比涨幅（类内、类间都按 L 天涨幅排，门槛仍是跑赢现金）。对照：E2 规则（前 N 名、每名 1/N、空位现金，N ∈ {3,5,8}）。
用法：python results/v5/diag/design/profile.py results/v5/diag/design
"""
import sys, pathlib, math
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v3.engine.score import lookback_panel
from src.v3.engine.sessions import decision_dates
from src.v4.r5.design import Markets
from src.v5.campaign import classes_for, class_map
from src.v5.engine.allocate import sleeves_on
out = pathlib.Path(sys.argv[1]); spec = load_spec(); M = Markets(spec)
K = ['A股', '港股', '美股', '其他海外', '商品', '国债', '黄金', '现金']
rows = []
for pool in ('index', 'tradable'):
    mk = M.get(pool, t4=False, allow_substitute=True); cs = mk.cash_id
    names = [*list(mk.names), cs]; cl = classes_for(list(mk.names), cs, class_map())
    liq = mk.liquidity if pool == 'tradable' else None
    ds = [pd.Timestamp(d).normalize() for d in decision_dates(pd.DatetimeIndex(mk.dates), 'month')]
    ds = [d for d in ds if pd.Timestamp('2006-01-01') <= d <= pd.Timestamp('2015-12-31')]
    for L in spec.lookbacks:
        p = lookback_panel(mk.signal, cs, L)
        for t in ds:
            if t not in p.score.index: continue
            sl = sleeves_on(p, t, names, cl, cs, liq)
            el = sorted([s for s in sl if s.participates and s.beats_cash and not math.isnan(s.score)], key=lambda s: -s.score)
            def champs(key):
                got, seen = [], set()
                for s in sorted(el, key=key):
                    c = cl[s.container_id]
                    if c not in seen: got.append(s); seen.add(c)
                return got
            champ_by = {'冠军赛': champs(lambda s: -s.score), '冠军赛·比涨幅': champs(lambda s: -s.total)}
            risk_c = [c for c in champ_by['冠军赛'] if cl[c.container_id] not in ('国债', '黄金')]
            def_c = [c for c in champ_by['冠军赛'] if cl[c.container_id] in ('国债', '黄金')]
            for arm, sizes in (('冠军赛', (1, 2, 3)), ('冠军赛·比涨幅', (1, 2, 3)), ('冠军赛·防守补位', (1, 2, 3)), ('E2', (3, 5, 8))):
                for n in sizes:
                    w = dict.fromkeys(K, 0.0)
                    if arm == '冠军赛·防守补位':
                        top = (risk_c[:n] + def_c)[:n]
                        for s in top: w[cl[s.container_id]] += 1 / len(top)
                        if not top: w['现金'] = 1.0
                    elif arm != 'E2':
                        top = champ_by[arm][:n]
                        for s in top: w[cl[s.container_id]] += 1 / len(top)
                        if not top: w['现金'] = 1.0
                    else:
                        top = el[:n]
                        for s in top: w[cl[s.container_id]] += 1 / n
                        w['现金'] = 1 - len(top) / n
                    rows.append(dict(pool=pool, arm=arm, t=t, y=t.year, L=L, n=n, **w))
d = pd.DataFrame(rows); d.to_csv(out / 'champion-targets.csv', index=False, float_format='%.4f')
d['风险'] = d[['A股', '港股', '美股', '其他海外', '商品']].sum(axis=1); d['防守'] = d[['国债', '黄金']].sum(axis=1)
y = d.groupby(['pool', 'arm', 'y'])[['A股', '港股', '美股', '风险', '防守', '现金']].mean().mul(100).round(0)
y.to_csv(out / 'champion-yearly.csv')
h = d.assign(h=np.where(d.y <= 2010, '06-10', '11-15')).groupby(['pool', 'arm', 'h'])[['风险', '防守', '现金']].mean().mul(100).round(0)
h.to_csv(out / 'champion-half.csv')
print(h.to_string()); print(y.unstack('arm').loc['tradable'].to_string()); print(y.unstack('arm').loc['index'].to_string())
