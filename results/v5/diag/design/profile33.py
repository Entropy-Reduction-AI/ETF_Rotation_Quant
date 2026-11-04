"""设计评审（D30-1）· 冻结规则下的信号画像：预注册 v5.1 定稿第 3.2 版全文（含 D33-6 硬闸门、R1 MF-§3.3-1 卖后不买回）。信号层面，不算收益，≤2015-12-31。
读数、宽度、两条腿、每天只减不加、默认国债，同 profile32 第二次运行。区别：
1. 单只：自己的 F ≥ 0.5，或从持有期最高收盘回落 10%（硬闸门），先到者卖出；周度决策日同样检查。
2. 卖后不买回：按单只规则（前沿或硬闸门）卖出的容器，到下一个周度决策日（含该日挑选）之前不得买入；该周度调仓完成后才解除；周度决策日当天卖出的，留到再下一个周度决策日。周度挑选正常换掉的不进名单。
3. 排序：H 从高到低，同分按容器 id 升序。
输出：每年仓位与档位变动（档位 = 日度风险仓位 r 的取值变化，0/0.5/1）、一个月内变回比例、单只离场按原因计数、转折时点、每段持有的最大回撤。
用法：python results/v5/diag/design/profile33.py results/v5/diag/design
"""
import sys, pathlib, json, bisect
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v3.engine.sessions import decision_dates
from src.v4.r5.design import Markets
from src.v5.campaign import classes_for, class_map
out = pathlib.Path(sys.argv[1]);  m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
ret = m.signal.loc[:'2015-12-31']; cash = m.cash_id; cls = classes_for(list(m.names), cash, class_map())
BROAD = {'A股': 'csi300', '港股': 'hsi', '美股': 'spx'}; RISK = list(BROAD.values()); MK = {v: k for k, v in BROAD.items()}
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
    W = Q.div(Q.sum(axis=1), axis=0); eq = Q.isna().any(axis=1) & V.notna().all(axis=1); W.loc[eq] = 1.0 / len(G)
    H = (W * V).sum(axis=1, min_count=len(G)); F = (V < 0).mean(axis=1).where(V.notna().all(axis=1))
    lm = V[LONG].mean(axis=1, skipna=False); E = ((lm > lm.shift(20)) & (lm.shift(20) > lm.shift(40))).where(lm.notna() & lm.shift(40).notna())
    return pd.DataFrame({'H': H, 'F': F, 'E': E})
uni = {k: [c for c in m.names if cls.get(c) == k and ret[c].notna().any()] for k in BROAD}
S = {c: state(c) for c in set(sum(uni.values(), [])) | {'cgb-10y', 'gold'}}
idx = ret.loc['2006-01-01':].index
Hd = pd.DataFrame({c: S[c].H for c in S}).reindex(idx); Fd = pd.DataFrame({c: S[c].F for c in S}).reindex(idx); Ed = pd.DataFrame({c: S[c].E for c in S}).reindex(idx)
B = {}
for k, mem in uni.items():
    f = Fd[mem]; n = f.notna().sum(axis=1); B[BROAD[k]] = ((f >= 0.5).sum(axis=1) / n).where(n >= 3)
B = pd.DataFrame(B)
def legs(c, t):
    h, f, e = Hd.at[t, c], Fd.at[t, c], Ed.at[t, c]
    if pd.isna(h) or pd.isna(f) or pd.isna(e): return None
    b = B.at[t, c] if c in B else np.nan
    l1 = (f < 0.5) and not (pd.notna(b) and b >= 0.5); l2 = (h > 0) or bool(e)
    return 0.5 * l1 + 0.5 * l2
def defense(t, cur):
    hb, hg = Hd.at[t, 'cgb-10y'], Hd.at[t, 'gold']
    if pd.isna(ret.at[t, 'cgb-10y']) and pd.isna(hb): return 'cash'
    wb = legs('cgb-10y', t)
    base = 'cgb-10y' if (wb is None or wb > 0) else 'cash'
    if pd.notna(hg) and hg > 0 and hg - (hb if (base == 'cgb-10y' and pd.notna(hb)) else 0) > 1: return 'gold'
    if cur == 'gold' and pd.notna(hg) and hg > 0 and base == 'cgb-10y' and pd.notna(hb) and hg >= hb: return 'gold'
    return base
weeks = set(pd.Timestamp(d).normalize() for d in decision_dates(pd.DatetimeIndex(m.dates), 'week'))
PX = {c: np.exp(np.log1p(ret[c].fillna(0)).cumsum()).reindex(idx) for c in S}
def rank(cands):
    return [c for _, c in sorted([(-Hd.at[t, c], c) for c in cands])]
h, w, picks, dh = None, 0.0, [], 'cash'; sold = set(); prev_n = 0; hi = {}; rows = []; exits = []; nred = []
for t in idx:
    # 单只检查（每天，含周度决策日）：前沿过半或硬闸门
    today = set()
    for c in list(picks):
        hi[c] = max(hi.get(c, PX[c].at[t]), PX[c].at[t])
        why = 'F' if (pd.notna(Fd.at[t, c]) and Fd.at[t, c] >= 0.5) else ('硬闸门' if PX[c].at[t] / hi[c] - 1 <= -0.10 else None)
        if why: picks.remove(c); sold.add(c); today.add(c); hi.pop(c, None); exits.append((t, c, why))
    if t in weeks:
        wl = {c: legs(c, t) for c in RISK}; ok = [c for c in RISK if wl[c]]
        if h not in ok: h = max(ok, key=lambda c: Hd.at[t, c]) if ok else None
        else:
            b = max(ok, key=lambda c: Hd.at[t, c])
            if b != h and Hd.at[t, b] - Hd.at[t, h] > 1: h = b
        w = wl[h] if h else 0.0
        if h:
            el = [c for c in uni[MK[h]] if c not in sold and pd.notna(Hd.at[t, c]) and Hd.at[t, c] > 0 and Fd.at[t, c] < 0.5]
            new = rank(el)[:3] or ([h] if h not in sold else [])
        else: new = []
        for c in picks:
            if c not in new: exits.append((t, c, '周度换掉')); hi.pop(c, None)
        picks = new
        if not picks: h, w = None, 0.0
        sold = set(today)   # 周度调仓完成后解除；当天才卖出的，留到再下一个周度决策日
        dh = defense(t, dh)
    elif h:
        wn = legs(h, t)
        if wn is not None and wn < w: w = wn; nred.append(t)
        if w == 0:
            for c in picks: exits.append((t, c, '市场退出')); hi.pop(c, None)
            h, picks = None, []
        else:
            while len(picks) < 3:
                el = [x for x in uni[MK[h]] if x not in picks and x not in sold and pd.notna(Hd.at[t, x]) and Hd.at[t, x] > 0 and Fd.at[t, x] < 0.5]
                # 只补被卖出的名额：补到和卖出前一样多为止
                if not el or len(picks) >= prev_n: break
                picks.append(rank(el)[0])
            if not picks:
                if h not in sold and pd.notna(Fd.at[t, h]) and Fd.at[t, h] < 0.5: picks = [h]
                else: h, w = None, 0.0
        dh = defense(t, dh)
    prev_n = len(picks)
    rows.append(dict(t=t, y=t.year, market=h or '无', w=w if h else 0.0, defense=dh, picks='|'.join(picks)))
d = pd.DataFrame(rows); d.to_csv(out / 'profile33-daily.csv', index=False)
E = pd.DataFrame(exits, columns=['t', 'id', 'why']); E.to_csv(out / 'profile33-exits.csv', index=False)
yr = pd.DataFrame({'风险仓位': d.groupby('y').w.mean() * 100})
for c, nm in (('csi300', 'A 股'), ('hsi', '港股'), ('spx', '美股')): yr[nm] = d.assign(v=np.where(d.market == c, d.w, 0)).groupby('y').v.mean() * 100
for c, nm in (('cgb-10y', '国债'), ('gold', '黄金'), ('cash', '现金')): yr[nm] = d.assign(v=np.where(d.defense == c, 1 - d.w, 0)).groupby('y').v.mean() * 100
yr['档位变动'] = d.groupby('y').w.apply(lambda s: int((s != s.shift()).iloc[1:].sum()))
for why in ('F', '硬闸门', '周度换掉', '市场退出'):
    yr[f'离场_{why}'] = E[E.why == why].t.dt.year.value_counts().reindex(yr.index).fillna(0).astype(int)
yr = yr.round(0); yr.to_csv(out / 'profile33-yearly.csv')
ws = d.set_index('t').w
ch = ws[ws.diff() != 0].iloc[1:]; rev = [bool((ws.loc[x:].iloc[1:21] == ws.loc[:x].iloc[-2]).any()) for x in ch.index]
p300 = np.exp(np.log1p(ret['csi300'].fillna(0)).cumsum())
def turn(t0, kind):
    t0 = pd.Timestamp(t0); x = ws.loc[t0:]
    def f(mask):
        z = x[mask]
        if z.empty: return None
        tt = z.index[0]; return f"{(tt - t0).days} 天，沪深300 {p300.loc[tt] / p300.loc[:t0].iloc[-1] * 100 - 100:+.1f}%"
    return {'减到半仓或以下': f(x <= 0.5), '风险清零': f(x == 0)} if kind == 'top' else {'回到半仓或以上': f(x >= 0.5), '满仓': f(x == 1)}
T = {'2007-10 顶': turn('2007-10-16', 'top'), '2009-08 顶': turn('2009-08-04', 'top'), '2015-06 顶': turn('2015-06-12', 'top'), '2008-11 底': turn('2008-11-04', 'bot')}
# 每段持有的最大回撤
held = d.set_index('t').picks.fillna('').str.split('|'); dds = []
for c in sorted({x for v in held for x in v if x}):
    inn = held.apply(lambda v: c in v); g = (inn != inn.shift()).cumsum()
    for _, seg in inn[inn].groupby(g[inn]):
        nx = inn.index[inn.index > seg.index[-1]][:1]; te = nx[0] if len(nx) else seg.index[-1]
        pp = PX[c].loc[seg.index[0]:te]; dds.append(float((pp / pp.cummax() - 1).min()))
dds = np.array(dds)
res = dict(平均风险仓位=round(float(yr['风险仓位'].mean()), 0), 十年档位变动=int(len(ch)), 一个月内变回=round(float(np.mean(rev)), 2), 十年当天减仓=len(nred),
           单只离场=E.why.value_counts().to_dict(), 持有段数=int(len(dds)), 持有段最大回撤中位=round(float(np.median(dds)), 3), 持有段最大回撤最深=round(float(dds.min()), 3),
           超过15的段=int((dds <= -0.15).sum()), 第二层平均持几只=round(float(d[d.market != '无'].picks.str.split('|').str.len().mean()), 2), 转折=T)
(out / 'profile33.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
print(json.dumps(res, ensure_ascii=False, indent=1, default=str)); print(yr.to_string())
