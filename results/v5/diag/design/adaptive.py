"""诊断：Owner 2026-11-01 的“动态周期”——周期随市场的快慢伸缩，快的时候（不论涨跌）缩短，平静了才拉长。
只用 ≤2015-12-31 的价格（沪深300、标普500，人民币），计入诊断次数 1。规则跑之前写死：
  效率 ER = |60 天净涨跌| ÷ 60 天每日涨跌绝对值之和（Kaufman）；q = 当天 ER 在此前所有 ER 里的分位（只用过去，前 250 天取 0.5）；
  周期 L = 250^(1−q) × 20^q，在 20 天（E2 最短）和 250 天（E2 最长）之间按几何插值，四舍五入到整数天；
  门槛：过去 L 天跑赢现金就持有，否则不持有。对照：固定 20、60、250 天，以及 E2 式（四个周期里过半跑赢才持有）。
指标：每个转折点离场、回场晚几天、那时已跌/已涨多少；假底回场后到再次离场的涨跌（假信号的代价）；每年切换次数。
第二版（同一次登记的修正，原因：效率在 V 形底附近反而变低）：python ... results/v5/diag/design vol，速度改用 20 天波动 ÷ 250 天波动，其余不变。
第三项（Owner 2026-11-02 问：最短 1 个月能否适配牛市尾部、熊市头尾）：周期下限改为 10 天、5 天，其余不变，同一诊断登记。
用法：python results/v5/diag/design/adaptive.py results/v5/diag/design [er|vol] [最短天数，默认 20]
"""
import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets
out = pathlib.Path(sys.argv[1]); GAUGE = sys.argv[2] if len(sys.argv) > 2 else 'er'; LMIN = int(sys.argv[3]) if len(sys.argv) > 3 else 20; m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
ret = m.signal.loc[:'2015-12-31']; cash = m.cash_id
clr = np.log1p(ret[cash].fillna(0)).cumsum()
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
res = {}
for c in ('csi300', 'spx'):
    lr = np.log1p(ret[c].fillna(0)); cl = lr.cumsum(); p = np.exp(cl)
    er = lr.rolling(60).sum().abs() / lr.abs().rolling(60).sum()
    if GAUGE == 'vol':  # 第二版：速度 = 最近 20 天波动 ÷ 过去 250 天波动（大跌后会在高位停留，有“记忆”）
        er = lr.rolling(20).std() / lr.rolling(250).std()
    hist = er.dropna()
    q = pd.Series(0.5, index=er.index)
    vals = []
    for t, v in hist.items():
        if len(vals) >= 250: q[t] = (np.array(vals) < v).mean()
        vals.append(v)
    L = np.round(250 ** (1 - q) * LMIN ** q).astype(int)
    def gate_fixed(n): return (cl - cl.shift(n)) > (clr - clr.shift(n))
    idx = np.arange(len(cl))
    shift_idx = np.clip(idx - L.values, 0, None)
    ad = pd.Series((cl.values - cl.values[shift_idx]) > (clr.values - clr.values[shift_idx]), index=cl.index)
    g = {'动态周期': ad, '固定 20 天': gate_fixed(20), '固定 60 天': gate_fixed(60), '固定 250 天': gate_fixed(250),
         'E2 式（四个过半）': (sum(gate_fixed(n).astype(int) for n in (20, 60, 120, 250)) >= 2)}
    pts = [x for x in swings(p.loc['2005-06':]) if x[1] >= pd.Timestamp('2006-03-01')]
    kinds = []
    for i, (k, t, lvl) in enumerate(pts):
        nxt = [x for x in pts[i + 1:] if x[0] == k]
        kinds.append('未定' if not nxt else (('真底' if nxt[0][2] > lvl else '假底') if k == '底' else ('真顶' if nxt[0][2] < lvl else '中途的顶')))
    tab = {}
    for name, s in g.items():
        s = s.loc['2006':]; rows = []
        for (k, t, lvl), kind in zip(pts, kinds):
            aft = s.loc[t:]
            if k == '顶':
                hit = aft[~aft].index[:1]
                if len(hit): rows.append(dict(转折=f'{t:%Y-%m} {kind}', 晚几天=int(len(s.loc[t:hit[0]]) - 1), 涨跌=round(p[hit[0]] / p[t] - 1, 3)))
            else:
                hit = aft[aft].index[:1]
                if len(hit):
                    r = dict(转折=f'{t:%Y-%m} {kind}', 晚几天=int(len(s.loc[t:hit[0]]) - 1), 涨跌=round(p[hit[0]] / p[t] - 1, 3))
                    off = s.loc[hit[0]:]; off = off[~off].index[:1]
                    if len(off): r['回场后到再离场'] = round(p[off[0]] / p[hit[0]] - 1, 3)
                    rows.append(r)
        flips = (s != s.shift()).iloc[1:]
        tab[name] = dict(转折=rows, 每年切换=flips.groupby(flips.index.year).sum().to_dict(), 持有占比=round(s.mean(), 2))
    Ly = L.loc['2006':].groupby(L.loc['2006':].index.year).median().to_dict()
    res[c] = dict(周期中位数每年=Ly, 规则=tab)
(out / (f'adaptive-{GAUGE}.json' if LMIN == 20 else f'adaptive-{GAUGE}-min{LMIN}.json')).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
for c, v in res.items():
    print('=====', c, '每年周期中位数', v['周期中位数每年'])
    rows = []
    for name, d in v['规则'].items():
        for r in d['转折']: rows.append(dict(规则=name, **r))
    df = pd.DataFrame(rows)
    print(df.pivot(index='转折', columns='规则', values='晚几天').to_string())
    print(df.pivot(index='转折', columns='规则', values='涨跌').to_string())
    if '回场后到再离场' in df: print(df.dropna(subset=['回场后到再离场']).pivot(index='转折', columns='规则', values='回场后到再离场').to_string())
    for name, d in v['规则'].items(): print(name, '持有', d['持有占比'], '切换', d['每年切换'])
