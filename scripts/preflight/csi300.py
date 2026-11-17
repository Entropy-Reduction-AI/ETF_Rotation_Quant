"""D38 预演（第 3 版登记）：沪深300 单市场回放，2005-01 → 2015-12-31（项目池 index 口径，设计期以内）。
K0 一直持有；K1、K2 规则与 longhist.py 相同（函数直接复用）。现金 = 项目池 cash 容器的日收益折成年化利率。
用途：给 K2A（只给 A 股腿买保险）提供 A 股本身的回放证据。
用法：python scripts/preflight/csi300.py results/v6-preflight
"""
import sys, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'scripts/preflight'))
import numpy as np, pandas as pd
from longhist import simulate, ann, mdd, bears
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets

OUT = pathlib.Path(sys.argv[1])
m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
R = m.signal.loc[:'2015-12-31', ['csi300', 'cash']].dropna()
px = np.exp(np.log1p(R['csi300']).cumsum())
# simulate() 按“年化 % × 天数 / 360”计现金；把 cash 日收益换成等价的年化 %
gap = px.index.to_series().diff().dt.days.fillna(1)
rate = (R['cash'] / gap * 360 * 100)
res = {k: simulate(px, rate, k) for k in ('K0', 'K1', 'K2')}
st = px.index[0] + pd.Timedelta(days=366)
bs = bears(px[px.index >= st])
cash_ann = float((1 + R['cash'][R.index >= st]).prod() ** (252 / (R.index >= st).sum()) - 1)
k0 = res['K0'][0][res['K0'][0].index >= st]
yrs = (px.index[-1] - st).days / 365.25
out = {}
for k, (nav, expo, turn, fb) in res.items():
    nv = nav[nav.index >= st]
    e = float(expo[expo.index >= st].mean())
    net = (ann(nv) - ann(k0)) * 100
    pos = (e - 1) * (ann(k0) - cash_ann) * 100
    cost = -turn / yrs * 0.1
    out[k] = dict(年化=round(ann(nv) * 100, 2), 比K0年化=round(net, 2), 最大回撤=round(mdd(nv) * 100, 1), 平均仓位=round(e, 3),
                  成本_每年_百分点=round(turn / yrs * 0.1, 3), 仓位差=round(pos, 2), 进出时点=round(net - pos - cost, 2))
out['_说明'] = dict(区间=f'{st.date()}→{px.index[-1].date()}', 现金年化=round(cash_ann * 100, 2),
                  熊市=[(str(a.date()), str(b.date()), round(d * 100, 1)) for a, b, d in bs])
json.dump(out, open(OUT / 'csi300.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
