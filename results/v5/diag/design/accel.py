"""诊断：Owner 2026-11-01 的“加速度”直觉。只用 ≤2015-12-31 的价格（沪深300、标普500，人民币），不算任何策略收益；计入诊断次数 1。
速度 v = 过去 20 个交易日的对数涨幅；加速度 = 这 20 天的速度 − 前 20 天的速度。效率 ER = |60 天净涨跌| ÷ 60 天每日涨跌绝对值之和（Kaufman）。
转折点：涨跌 ≥ 20% 的摆动高低点。底部之后的下一个底更高 = “真底”，更低 = “中途反弹的底”；顶部同理。
对每个转折点：速度最极端（跌得最快 / 涨得最快）的那天，比价格的最低 / 最高点早几天；转折当天的速度只剩极端值的几成。
用法：python results/v5/diag/design/accel.py results/v5/diag/design
"""
import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets
out = pathlib.Path(sys.argv[1]); m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
ret = m.signal.loc[:'2015-12-31']
def swings(p, th=0.2):
    pts, mode, ext, ext_t = [], 'up', p.iloc[0], p.index[0]
    for t, v in p.items():
        if mode == 'up':
            if v > ext: ext, ext_t = v, t
            elif v < ext * (1 - th): pts.append(['顶', ext_t, ext]); mode, ext, ext_t = 'down', v, t
        else:
            if v < ext: ext, ext_t = v, t
            elif v > ext * (1 + th): pts.append(['底', ext_t, ext]); mode, ext, ext_t = 'up', v, t
    return pts
res, rows = {}, []
for c in ('csi300', 'spx'):
    lr = np.log1p(ret[c].fillna(0)); p = np.exp(lr.cumsum())
    v = lr.rolling(20).sum(); acc = v - v.shift(20)
    er = (lr.rolling(60).sum().abs() / lr.abs().rolling(60).sum())
    pts = [x for x in swings(p.loc['2005-06':]) if x[1] >= pd.Timestamp('2006-03-01')]
    for i, (k, t, lvl) in enumerate(pts):
        nxt = [x for x in pts[i + 1:] if x[0] == k]
        if not nxt: kind = '未定'
        elif k == '底': kind = '真底' if nxt[0][2] > lvl else '中途反弹的底'
        else: kind = '真顶' if nxt[0][2] < lvl else '牛市中途的顶'
        win = v.loc[:t].iloc[-61:]
        ext_t = win.idxmin() if k == '底' else win.idxmax()
        rows.append(dict(市场=c, 转折=f'{t:%Y-%m-%d} {k}', 类型=kind, 速度最极端比转折早几天=int(len(v.loc[ext_t:t]) - 1),
                         转折当天速度占极端值=round(v.loc[t] / win.loc[ext_t], 2) if win.loc[ext_t] != 0 else None,
                         转折前20天加速度=round(acc.loc[t], 3)))
    yr = er.loc['2006':].groupby(er.loc['2006':].index.year).mean().round(2).to_dict()
    res[c] = dict(效率每年=yr)
d = pd.DataFrame(rows); d.to_csv(out / 'accel-turns.csv', index=False)
res['转折'] = d.to_dict('records')
(out / 'accel.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
print(d.to_string()); print(json.dumps({k: v for k, v in res.items() if k != '转折'}, ensure_ascii=False))
