"""诊断（Orchestrator 自己提出的观察）：多把尺子是否“同步”向同一方向加速。只用 ≤2015-12-31 价格，计入诊断次数 1。
同步度 = 七把尺子（3–120 天）里，加速度同号且超过 1.5 倍噪音的把数，向上记正、向下记负（scales.py 的输出）。
看几个顶部前 60 个交易日的同步度，以及同步度很高（≥4 把同时向上）之后 20、60 天沪深300 的涨跌。
用法：python results/v5/diag/design/sync.py results/v5/diag/design
"""
import sys, pathlib, json
import pandas as pd, numpy as np
D = pathlib.Path(sys.argv[1])
out = {}
for c in ('csi300', 'spx'):
    A = pd.read_csv(D / f'scales-{c}.csv', index_col=0, parse_dates=True)
    up = (A > 1.5).sum(axis=1); dn = (A < -1.5).sum(axis=1); sync = up - dn
    px = None
    if c == 'csi300':
        px = pd.read_csv(D / 'breadth.csv', index_col=0, parse_dates=True)['csi300']
    tops = {'csi300': ['2007-10-16', '2009-08-03', '2015-06-08'], 'spx': ['2007-10-10']}[c]
    rows = {}
    for t in tops:
        w = sync.loc[:t].iloc[-60:]
        rows[t] = dict(顶前60天平均向上把数=round(up.loc[:t].iloc[-60:].mean(), 2), 顶前60天最多同时向上=int(up.loc[:t].iloc[-60:].max()),
                       顶前20天平均=round(up.loc[:t].iloc[-20:].mean(), 2))
    res = dict(顶部=rows, 同时向上4把以上的天数占比=round((up >= 4).mean(), 3))
    if px is not None:
        ev = up[up >= 4].index; fw = []
        last = None
        for t in ev:
            if last is not None and (t - last).days < 30: continue
            last = t; p0 = px.loc[t]; f20 = px.loc[t:].iloc[min(20, len(px.loc[t:]) - 1)] / p0 - 1; f60 = px.loc[t:].iloc[min(60, len(px.loc[t:]) - 1)] / p0 - 1
            fw.append(dict(日期=str(t.date()), 之后20天=round(f20, 3), 之后60天=round(f60, 3)))
        res['同步向上事件'] = fw
    out[c] = res
(D / 'sync.json').write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str)); print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
