"""v5 设计稿第 3.1 版 · 第一层 + 第二层事前画像（信号层面：只算规则想持有什么和触发次数，不算任何收益；只用 ≤2015-12-31）。计入诊断次数 1。
规则跑之前写死（D31 + Owner 2026-11-03 同意：响度加权、镜像两条腿、离场两种情况）：
量：每个序列 28 把尺子（3–250 天对数等距）。v_n = 最近 n 天（对数涨幅 − 现金对数涨幅）之和 ÷ (σ·√n)，σ = 过去 250 天日波动（不含当天）。
  响度_n = |v_n| 在最近 n 天的平均，换成它在自己过去历史里的分位（至少 250 个值）；权重 w_n ∝ 响度分位。
  预热：任何一把尺子的响度分位历史不足 250 个时，当天 28 把尺子等权（同一诊断的修正：第一次运行发现响度分位要到 2008 年才有，2006–07 年整段空白；两次都登记）。
  水平 H = Σ w_n·v_n；转负前沿 F = v_n < 0 的尺子比例（不加权）；长尺子放缓 E = 60 天以上尺子的平均速度比 20 个交易日前高。
第一层（每周最后一个交易日）：腿一 = F < 0.5；腿二 = H > 0 或 E。每条腿一半仓位。至少一条腿满足才有资格；
  持 H 最高的有资格的风险市场（沪深300、恒生、标普500 代表 A、港、美）；换到另一个市场要求 H 差 > 1。其余仓位去防守：国债、黄金 H > 0 取高者（换另一只要求差 > 1），都不行拿现金。
第二层：选中的市场里，该大类全部有数据的容器按 H 排名，取 H > 0 的前 3 只平分；不足 3 只就平分给够格的；一只都没有就持该市场宽基。
单只离场（每天看）：持有的容器从买入后的最高点回落 10%：当天宽基 F < 0.5 → 换成排名下一只、未持有、H > 0 的容器（没有就宽基）；F ≥ 0.5 → 当天重做第一层判断。本画像只统计两种情况各触发几次，不改写周度目标。
用法：python results/v5/diag/design/profile31.py results/v5/diag/design
"""
import sys, pathlib, json, bisect
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v3.engine.sessions import decision_dates
from src.v4.r5.design import Markets
from src.v5.campaign import classes_for, class_map
out = pathlib.Path(sys.argv[1]); m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
ret = m.signal.loc[:'2015-12-31']; cash = m.cash_id; cls = classes_for(list(m.names), cash, class_map())
BROAD = {'A股': 'csi300', '港股': 'hsi', '美股': 'spx'}; RISK = list(BROAD.values()); DEF = ['cgb-10y', 'gold']
NAME = {'csi300': 'A 股', 'hsi': '港股', 'spx': '美股', 'cgb-10y': '国债', 'gold': '黄金', 'cash': '现金'}
G = sorted(set(np.round(np.geomspace(3, 250, 30)).astype(int))); LONG = [n for n in G if n >= 60]
cl = np.log1p(ret[cash].fillna(0))
def pct_past(a):
    o = np.full(len(a), np.nan); h = []
    for i, x in enumerate(a):
        if np.isnan(x): continue
        if len(h) >= 250: o[i] = bisect.bisect_left(h, x) / len(h)
        bisect.insort(h, x)
    return o
def state(c):
    lr = np.log1p(ret[c]); ok = lr.notna().rolling(250, min_periods=1).sum().ge(250); lr0 = lr.fillna(0); x = lr0 - cl
    sig = lr0.rolling(250).std().shift(1)
    V = pd.DataFrame({n: x.rolling(n).sum() / (sig * np.sqrt(n)) for n in G}).where(ok, axis=0)
    Q = pd.DataFrame({n: pct_past(V[n].abs().rolling(n).mean().values) for n in G}, index=V.index)
    W = Q.div(Q.sum(axis=1), axis=0)
    eq = Q.isna().any(axis=1) & V.notna().all(axis=1); W.loc[eq] = 1.0 / len(G)
    H = (W * V).sum(axis=1, min_count=len(G)); F = (V < 0).mean(axis=1).where(V.notna().all(axis=1))
    lm = V[LONG].mean(axis=1, skipna=False); E = (lm > lm.shift(20)).where(lm.notna() & lm.shift(20).notna())
    return pd.DataFrame({'H': H, 'F': F, 'E': E})
uni = {k: [c for c in m.names if cls.get(c) == k and ret[c].notna().any()] for k in BROAD}
S = {c: state(c) for c in set(sum(uni.values(), [])) | set(DEF)}
px = {c: np.exp(np.log1p(ret[c].fillna(0)).cumsum()) for c in S}
days = [pd.Timestamp(d).normalize() for d in decision_dates(pd.DatetimeIndex(m.dates), 'week')]
days = [d for d in days if pd.Timestamp('2006-01-01') <= d <= pd.Timestamp('2015-12-31')]
def g(c, t, k):
    v = S[c][k].get(t); return None if v is None or pd.isna(v) else v
h, dh, rows, hold = None, None, [], {}
for t in days:
    H = {c: g(c, t, 'H') for c in RISK + DEF}; F = {c: g(c, t, 'F') for c in RISK}; E = {c: g(c, t, 'E') for c in RISK}
    w = {c: (0.5 * (F[c] < 0.5) + 0.5 * ((H[c] > 0) or bool(E[c]))) if None not in (H[c], F[c], E[c]) else 0.0 for c in RISK}
    ok = [c for c in RISK if w[c] > 0]
    if h not in ok: h = max(ok, key=lambda c: H[c]) if ok else None
    else:
        b = max(ok, key=lambda c: H[c])
        if b != h and H[b] - H[h] > 1: h = b
    wr = w[h] if h else 0.0
    d = [c for c in DEF if H[c] is not None and H[c] > 0]
    if not d: dh = None
    elif dh not in d: dh = max(d, key=lambda c: H[c])
    else:
        b = max(d, key=lambda c: H[c])
        if b != dh and H[b] - H[dh] > 1: dh = b
    picks = []
    if h:
        k = [kk for kk, v in BROAD.items() if v == h][0]
        rk = sorted([(g(c, t, 'H'), c) for c in uni[k] if g(c, t, 'H') is not None and g(c, t, 'H') > 0], reverse=True)
        picks = [c for _, c in rk[:3]] or [h]
    rows.append(dict(t=t, y=t.year, market=h or '无', w=wr, defense=dh or 'cash', picks='|'.join(picks), n=len(picks), legs=f"{int(F[h] < 0.5) if h else ''}{int((H[h] > 0) or bool(E[h])) if h else ''}"))
d = pd.DataFrame(rows); d.to_csv(out / 'profile31-weekly.csv', index=False)
# 单只离场：每周持仓在下一周内，每天看从买入后最高点的回落（买入 = 首次进入持仓的那周）
stops = []; entry_hi = {}
for i, r in d.iterrows():
    cur = set(r.picks.split('|')) if r.picks else set()
    entry_hi = {c: entry_hi.get(c, None) for c in cur}
    t0 = r.t; t1 = d.t.iloc[i + 1] if i + 1 < len(d) else pd.Timestamp('2015-12-31')
    for c in cur:
        p = px[c].loc[t0:t1].iloc[1:]
        hi = entry_hi[c] if entry_hi[c] is not None else float(px[c].loc[:t0].iloc[-1])
        for tt, v in p.items():
            hi = max(hi, v)
            if v / hi - 1 <= -0.10:
                fb = g(BROAD[[k for k, b in BROAD.items() if b == r.market][0]], tt, 'F') if r.market != '无' else None
                stops.append(dict(t=tt, y=tt.year, id=c, market=r.market, 市场共振=(fb is not None and fb >= 0.5))); hi = v; break
        entry_hi[c] = hi
st = pd.DataFrame(stops); st.to_csv(out / 'profile31-stops.csv', index=False)
alloc = []
for _, r in d.iterrows():
    a = {k: 0.0 for k in NAME}
    if r.market != '无': a[r.market] += r.w
    a[r.defense] += 1 - r.w; alloc.append(a)
A = pd.DataFrame(alloc); A['y'] = d.y.values
yr = (A.groupby('y').mean() * 100).round(0); yr['风险仓位'] = yr[RISK].sum(axis=1)
yr['换市场'] = d.groupby('y').market.apply(lambda s: int(((s != s.shift()) & (s != '无') & (s.shift() != '无')).iloc[1:].sum()))
yr['档位变动'] = d.groupby('y').w.apply(lambda s: int((s != s.shift()).iloc[1:].sum()))
yr['半仓周%'] = (d.groupby('y').w.apply(lambda s: (s == 0.5).mean()) * 100).round(0)
a = d[d.market == 'csi300']
yr['A股里持宽基%'] = (a.groupby('y').picks.apply(lambda s: s.str.contains('csi300').mean()) * 100).round(0)
yr['第二层换手'] = d.groupby('y').picks.apply(lambda s: int(sum(len(set(x.split('|')) - set(y.split('|'))) for x, y in zip(s.iloc[1:], s.iloc[:-1]) if x and y)))
yr['止损_自身'] = st[~st.市场共振].groupby('y').size().reindex(yr.index).fillna(0).astype(int) if len(st) else 0
yr['止损_共振'] = st[st.市场共振].groupby('y').size().reindex(yr.index).fillna(0).astype(int) if len(st) else 0
yr.columns = [NAME.get(c, c) for c in yr.columns]; yr.to_csv(out / 'profile31-yearly.csv')
p300 = px['csi300']
def turn(t0, kind):
    t0 = pd.Timestamp(t0); x = d[d.t >= t0]; risk = x.w.where(x.market != '无', 0)
    def f(mask):
        z = x[mask]
        if z.empty: return None
        t = z.t.iloc[0]; return f"{(t - t0).days} 天，沪深300 {p300.loc[:t].iloc[-1] / p300.loc[:t0].iloc[-1] * 100 - 100:+.1f}%"
    return {'减到半仓或以下': f(risk <= 0.5), '风险清零': f(risk == 0)} if kind == 'top' else {'回到半仓或以上': f(risk >= 0.5), '满仓': f(risk == 1)}
T = {'2007-10 顶': turn('2007-10-16', 'top'), '2009-08 顶': turn('2009-08-04', 'top'), '2015-06 顶': turn('2015-06-12', 'top'),
     '2008-11 底': turn('2008-11-04', 'bot'), '2014-03 起涨': turn('2014-03-20', 'bot')}
pk = d[d.market == 'csi300'].picks.str.split('|').explode().value_counts(normalize=True).round(3).head(8).to_dict()
res = dict(十年换市场=int(yr['换市场'].sum()), 十年档位变动=int(yr['档位变动'].sum()), 平均风险仓位=float(yr['风险仓位'].mean().round(0)),
           第二层平均持几只=round(float(d[d.market != '无'].n.mean()), 2), A股时最常持有=pk,
           单只止损=dict(合计=len(st), 自身问题=int((~st.市场共振).sum()) if len(st) else 0, 市场共振=int(st.市场共振.sum()) if len(st) else 0), 转折=T)
(out / 'profile31.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
print(json.dumps(res, ensure_ascii=False, indent=1, default=str)); print(yr.to_string())
