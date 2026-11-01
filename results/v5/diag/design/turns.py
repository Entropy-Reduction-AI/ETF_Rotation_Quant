"""诊断：设计期的大转折里，“跑赢现金”这道门槛在不同回看期下，离场晚多少、痛多少，回场晚多少、少赚多少，震荡时来回切几次。
只用 ≤2015-12-31 的价格（沪深300、标普500，人民币），不算任何策略收益；计入诊断次数 1。
转折点：从高点跌 ≥20% 记为一次下跌（高点→最低点），最低点之后涨 ≥20% 记为一次回升。
用法：python results/v5/diag/design/turns.py results/v5/diag/design
"""
import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets
out = pathlib.Path(sys.argv[1]); m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
ret = m.signal.loc[:'2015-12-31']; cash = m.cash_id
lv = (1 + ret.fillna(0)).cumprod()
def swings(p, th=0.2):
    pts, mode, ext, ext_t = [], 'up', p.iloc[0], p.index[0]
    for t, v in p.items():
        if mode == 'up':
            if v > ext: ext, ext_t = v, t
            elif v < ext * (1 - th): pts.append(('顶', ext_t)); mode, ext, ext_t = 'down', v, t
        else:
            if v < ext: ext, ext_t = v, t
            elif v > ext * (1 + th): pts.append(('底', ext_t)); mode, ext, ext_t = 'up', v, t
    return pts
res = {}
for c in ('csi300', 'spx'):
    p = lv[c].loc['2005-06':]; pts = [x for x in swings(p) if x[1] >= pd.Timestamp('2006-01-01')]
    rows = []
    for L in (20, 60, 120, 250):
        tot = np.expm1(np.log1p(ret[[c, cash]].fillna(0)).rolling(L, min_periods=L).sum())
        on = (tot[c] > tot[cash]).loc['2006':]
        for kind, t in pts:
            after = on.loc[t:]
            if kind == '顶':
                off = after[~after].index[:1]
                if len(off): rows.append(dict(L=L, 事件=f'{t:%Y-%m} 顶', 晚了天数=int(len(on.loc[t:off[0]]) - 1), 离场时已跌=round(p[off[0]] / p[t] - 1, 3)))
            else:
                onn = after[after].index[:1]
                if len(onn): rows.append(dict(L=L, 事件=f'{t:%Y-%m} 底', 晚了天数=int(len(on.loc[t:onn[0]]) - 1), 回场时已涨=round(p[onn[0]] / p[t] - 1, 3)))
        flips = (on != on.shift()).iloc[1:]
        rows.append(dict(L=L, 事件='每年切换次数', 晚了天数=None, 切换=flips.groupby(flips.index.year).sum().to_dict()))
    res[c] = dict(转折点=[(k, str(t.date())) for k, t in pts], 明细=rows)
(out / 'turns.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
for c, v in res.items():
    print(c, v['转折点'])
    print(pd.DataFrame([r for r in v['明细'] if r['事件'] != '每年切换次数']).pivot(index='事件', columns='L', values=['晚了天数']).to_string())
    print(pd.DataFrame([r for r in v['明细'] if r['事件'] != '每年切换次数']).assign(痛=lambda d: d.get('离场时已跌').fillna(d.get('回场时已涨'))).pivot(index='事件', columns='L', values='痛').to_string())
    for r in v['明细']:
        if r['事件'] == '每年切换次数': print(r['L'], r['切换'])
