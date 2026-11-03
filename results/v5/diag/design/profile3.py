"""v5 设计稿第 3 版 · 第一层事前画像（信号层面，不算组合收益；只用 ≤2015-12-31）。计入诊断次数 1。规则跑之前写死（Owner 2026-11-03 已定：删“回场先买宽基”、第一层用 A）：
每个市场 c ∈ {沪深300、恒生、标普500、10 年国债、黄金}：28 把尺子（3–250 天对数等距），速度 v_n = n 天对数涨幅超出现金的部分 ÷ (σ·√n)，σ = c 过去 250 天日波动（只用过去）。
水平 = 28 个 v_n 的平均；前沿 = v_n < 0 的比例。
第一层：水平 > 0 才有资格；持水平最高的风险市场；换到另一个风险市场要求水平差 > 1（噪音带，只管换市场）。
仓位：前沿 < 0.5 满仓；前沿 ≥ 0.5 风险一半、另一半防守；水平 ≤ 0 全部离场。
防守：国债、黄金水平 > 0 取高者（换另一只要求差 > 1）；都不行拿现金。每周最后一个交易日决策。
输出：每年各市场平均仓位、风险仓位、换市场次数、仓位档位变动次数；五次大转折的减半、离场、回场时点和当时离高点/低点的价格距离；同期第 2 版（噪音带只管换市场）对照。
第二版（同一诊断，看到第一版后按机制修正，两版都登记）：第一版里“前沿过半”和“水平 ≤ 0”几乎同时发生，半仓档很少触发；
大跌后长尺子长期为负，水平要很久才回正，2008 年底 94 天后才回场。改为对称的两条腿：前沿 < 0.5 和 水平 > 0 各占一半仓位，
两条都满足满仓、满足一条半仓、都不满足离场；有资格 = 至少满足一条；选市场仍按水平最高，噪音带不变。
用法：python results/v5/diag/design/profile3.py results/v5/diag/design [sym]
"""
import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v3.engine.sessions import decision_dates
from src.v4.r5.design import Markets
out = pathlib.Path(sys.argv[1]); SYM = len(sys.argv) > 2 and sys.argv[2] == 'sym'; TAG = '-sym' if SYM else ''; m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
ret = m.signal.loc[:'2015-12-31']; cash = m.cash_id
RISK = ['csi300', 'hsi', 'spx']; DEF = ['cgb-10y', 'gold']
NAME = {'csi300': 'A 股', 'hsi': '港股', 'spx': '美股', 'cgb-10y': '国债', 'gold': '黄金', 'cash': '现金'}
G = sorted(set(np.round(np.geomspace(3, 250, 30)).astype(int)))
cl = np.log1p(ret[cash].fillna(0))
LV, FR = {}, {}
for c in RISK + DEF:
    lr = np.log1p(ret[c]); valid = lr.notna().rolling(250, min_periods=1).sum().ge(250); x = lr.fillna(0) - cl; sig = lr.fillna(0).rolling(250).std().shift(1)
    V = pd.DataFrame({n: x.rolling(n).sum() / (sig * np.sqrt(n)) for n in G}).where(valid)
    LV[c] = V.mean(axis=1, skipna=False); FR[c] = (V < 0).mean(axis=1).where(V.notna().all(axis=1))
days = [pd.Timestamp(d).normalize() for d in decision_dates(pd.DatetimeIndex(m.dates), 'week')]
days = [d for d in days if pd.Timestamp('2006-01-01') <= d <= pd.Timestamp('2015-12-31')]
h, dh, rows = None, None, []
for t in days:
    lv = {c: LV[c].get(t) for c in RISK + DEF}; lv = {k: v for k, v in lv.items() if pd.notna(v)}
    fr = {k: FR[k].get(t) for k in RISK}
    ok = [k for k in RISK if k in lv and (lv[k] > 0 or (SYM and fr[k] < 0.5))]
    if h not in ok: h = max(ok, key=lambda k: lv[k]) if ok else None
    elif ok:
        best = max(ok, key=lambda k: lv[k])
        if best != h and lv[best] - lv[h] > 1: h = best
    if h is None: w = 0.0
    elif SYM: w = 0.5 * (lv[h] > 0) + 0.5 * (fr[h] < 0.5)
    else: w = 0.5 if fr[h] >= 0.5 else 1.0
    d = [k for k in DEF if k in lv and lv[k] > 0]
    if not d: dh = None
    elif dh not in d: dh = max(d, key=lambda k: lv[k])
    else:
        best = max(d, key=lambda k: lv[k])
        if best != dh and lv[best] - lv[dh] > 1: dh = best
    rows.append(dict(t=t, y=t.year, risk=h or '无', w=w, defense=dh or 'cash'))
d = pd.DataFrame(rows); d.to_csv(out / ('profile3' + TAG + '-weekly.csv'), index=False)
alloc = []
for _, r in d.iterrows():
    a = {k: 0.0 for k in NAME}
    if r.risk != '无': a[r.risk] += r.w
    a[r.defense] += 1 - r.w
    alloc.append(a)
A = pd.DataFrame(alloc, index=d.t); A['y'] = d.y.values
yr = (A.groupby('y').mean() * 100).round(0)
yr['风险仓位'] = yr[RISK].sum(axis=1)
yr['换市场次数'] = d.groupby('y').risk.apply(lambda s: int(((s != s.shift()) & (s != '无') & (s.shift() != '无')).iloc[1:].sum()))
yr['档位变动次数'] = d.groupby('y').w.apply(lambda s: int((s != s.shift()).iloc[1:].sum()))
yr['半仓周数占比'] = (d.groupby('y').w.apply(lambda s: (s == 0.5).mean()) * 100).round(0)
yr.columns = [NAME.get(c, c) for c in yr.columns]
yr.to_csv(out / ('profile3' + TAG + '-yearly.csv'))
v2 = pd.read_csv(out / 'layer1-band-swap-1-yearly.csv', index_col=0)
v2r = v2[[c for c in v2.columns if c in RISK]].sum(axis=1).round(0)
# 转折
px = {c: np.exp(np.log1p(ret[c].fillna(0)).cumsum()) for c in RISK}
def turn(name, t0, kind, c='csi300'):
    t0 = pd.Timestamp(t0); aft = d[d.t >= t0]; p = px[c]; ref = p.loc[:t0].iloc[-1]
    def hit(mask):
        x = aft[mask(aft)]
        return None if x.empty else (x.t.iloc[0], (x.t.iloc[0] - t0).days, round(float(p.loc[:x.t.iloc[0]].iloc[-1] / ref - 1) * 100, 1))
    if kind == 'top':
        a = hit(lambda x: (x.risk != c) | (x.w < 1)); b = hit(lambda x: x.risk != c)
        return {'先减半或换走': a and f'{a[1]} 天后，离顶 {a[2]}%', '全部离开 A 股': b and f'{b[1]} 天后，离顶 {b[2]}%'}
    a = hit(lambda x: x.risk != '无'); b = hit(lambda x: (x.risk != '无') & (x.w == 1))
    return {'回到风险市场': a and f'{a[1]} 天后（{NAME.get(aft[aft.risk != "无"].risk.iloc[0])}），离底 +{a[2]}%', '满仓': b and f'{b[1]} 天后，离底 +{b[2]}%'}
T = {'2007-10 顶': turn('', '2007-10-16', 'top'), '2008-11 底': turn('', '2008-11-04', 'bot'), '2009-08 顶': turn('', '2009-08-04', 'top'),
     '2014-03 底': turn('', '2014-03-20', 'bot'), '2015-06 顶': turn('', '2015-06-12', 'top')}
res = dict(十年换市场=int(yr['换市场次数'].sum()), 十年档位变动=int(yr['档位变动次数'].sum()), 平均风险仓位=round(float(yr['风险仓位'].mean()), 0),
           第2版平均风险仓位=round(float(v2r.mean()), 0), 第2版十年换手=int(v2['换几次'].sum()), 转折=T)
(out / ('profile3' + TAG + '.json')).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
yr['第2版风险仓位'] = v2r.values; yr['第2版换手'] = v2['换几次'].values
print(yr.to_string())
