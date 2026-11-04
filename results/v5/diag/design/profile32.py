"""探索（不计入判据 ⑤，D32-1）：设计稿第 3.1 版的离场改为“和选市场同一套读法”，防守默认国债。信号层面，不算收益，≤2015-12-31。
跑之前写死（Owner 2026-11-04：固定 10% 不够 adaptive；回撤覆盖面在扩大就该介入；替换后新的也降速就回第一层；空出来的仓位像 A1 一样放国债）：
读数同 profile31（响度加权，E = 长尺子连续两个月放缓）。
1. 宽度：市场 m 里参加排名、读数有定义的容器不少于 3 个时，B(m,t) = 其中转负前沿 F ≥ 0.5 的比例；少于 3 个时不用宽度。
2. 第一层：腿一 = 代表的 F < 0.5，且 B < 0.5（有宽度时）；腿二 = H > 0 或 E。每条腿一半。选市场、噪音带同 3.1。
3. 每天看：按当天读数算持有市场的仓位，低于当前仓位就当天减（下一交易日成交）；加仓只在周度决策日。
4. 单只 ETF：取代固定 10%。持有的容器自己的 F ≥ 0.5 → 换成排名下一只（H > 0 且 F < 0.5、未持有、本周未卖过）；没有就不补，钱留在已持有的几只里。
   第二层周度挑选也要求 F < 0.5。“替换后新的也降速、回撤面扩大”由宽度和第 3 条自动接上第一层，不另设次数。
5. 防守：没放进风险市场的部分默认放 10 年国债（像 A1）；黄金 H > 0 且比国债高 1 以上才换黄金；国债两条腿都不成立（自己在下跌）才拿现金；国债数据不够时拿现金。
第二次运行（同一探索）：第一次把“国债读数还没有（预热不足一年）”当成拿现金，2008 年国债 0%；Owner 的意思是像 A1 一样直接用国债，改为“国债有价格就默认持有，只有国债两条腿都不成立才拿现金”。
输出：每年日均风险仓位、防守构成、减仓与档位变动次数、单只替换次数；见顶、见底时点（用日度风险仓位）。
第三次运行（2026-11-04，折中，参数 mid）：每天只在“面上的回撤”时减仓——该市场有宽度时 B ≥ 0.5，没有宽度时代表自己的 F ≥ 0.5——当天把腿一关掉；其余变化（腿二、单只替换）都等周度决策日。
第四次运行（2026-11-04，参数 two）：在第二次运行（每天看）的基础上，腿一和宽度都要连续两个交易日越过 0.5 才算失效（市场和单只都一样），看噪音能少多少、转折慢多少。
用法：python results/v5/diag/design/profile32.py results/v5/diag/design [mid|two]
"""
import sys, pathlib, json, bisect
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v3.engine.sessions import decision_dates
from src.v4.r5.design import Markets
from src.v5.campaign import classes_for, class_map
out = pathlib.Path(sys.argv[1]); MID = len(sys.argv) > 2 and sys.argv[2] == 'mid'; TWO = len(sys.argv) > 2 and sys.argv[2] == 'two'; TAG = '-mid' if MID else '-two' if TWO else ''; m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
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
if TWO:
    Fd = pd.concat([Fd, Fd.shift(1)]).groupby(level=0).min().reindex(idx)
    B = pd.concat([B, B.shift(1)]).groupby(level=0).min().reindex(idx)
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
h, w, picks, dh, sold = None, 0.0, [], 'cash', set(); rows = []; nrep = []; nred = []
for t in idx:
    if t in weeks:
        sold = set()
        wl = {c: legs(c, t) for c in RISK}; ok = [c for c in RISK if wl[c]]
        if h not in ok: h = max(ok, key=lambda c: Hd.at[t, c]) if ok else None
        else:
            b = max(ok, key=lambda c: Hd.at[t, c])
            if b != h and Hd.at[t, b] - Hd.at[t, h] > 1: h = b
        w = wl[h] if h else 0.0
        if h:
            rk = sorted([(Hd.at[t, c], c) for c in uni[MK[h]] if pd.notna(Hd.at[t, c]) and Hd.at[t, c] > 0 and Fd.at[t, c] < 0.5], reverse=True)
            picks = [c for _, c in rk[:3]] or [h]
        else: picks = []
        dh = defense(t, dh)
    elif h and MID:
        b = B.at[t, h] if h in B else np.nan
        surf = (pd.notna(b) and b >= 0.5) or (pd.isna(b) and pd.notna(Fd.at[t, h]) and Fd.at[t, h] >= 0.5)
        if surf and w > 0:
            wn = w - 0.5 if w == 1.0 and legs(h, t) is not None and legs(h, t) < 1 else (0.0 if legs(h, t) == 0 else w)
            if wn < w: w = wn; nred.append(t)
            if w == 0: h, picks = None, []
        dh = defense(t, dh)
    elif h:
        wn = legs(h, t)
        if wn is not None and wn < w: w = wn; nred.append(t)
        if w == 0: h, picks = None, []
        for c in list(picks):
            if pd.notna(Fd.at[t, c]) and Fd.at[t, c] >= 0.5 and len(picks) > 0:
                picks.remove(c); sold.add(c); nrep.append(t)
                rk = sorted([(Hd.at[t, x], x) for x in uni[MK[h]] if x not in picks and x not in sold and pd.notna(Hd.at[t, x]) and Hd.at[t, x] > 0 and Fd.at[t, x] < 0.5], reverse=True)
                if rk: picks.append(rk[0][1])
        if not picks and h: picks = [h] if (pd.notna(Fd.at[t, h]) and Fd.at[t, h] < 0.5) else []
        if not picks: w = 0.0; h = None
        dh = defense(t, dh)
    rows.append(dict(t=t, y=t.year, market=h or '无', w=w if h else 0.0, defense=dh, picks='|'.join(picks)))
d = pd.DataFrame(rows); d.to_csv(out / ('profile32' + TAG + '-daily.csv'), index=False)
yr = pd.DataFrame({'风险仓位': d.groupby('y').w.mean() * 100})
for c, nm in (('csi300', 'A 股'), ('hsi', '港股'), ('spx', '美股')): yr[nm] = d.assign(v=np.where(d.market == c, d.w, 0)).groupby('y').v.mean() * 100
for c, nm in (('cgb-10y', '国债'), ('gold', '黄金'), ('cash', '现金')): yr[nm] = d.assign(v=np.where(d.defense == c, 1 - d.w, 0)).groupby('y').v.mean() * 100
yr['档位变动'] = d.groupby('y').w.apply(lambda s: int((s != s.shift()).iloc[1:].sum()))
yr['当天减仓'] = pd.Series([t.year for t in nred]).value_counts().reindex(yr.index).fillna(0).astype(int)
yr['单只替换'] = pd.Series([t.year for t in nrep]).value_counts().reindex(yr.index).fillna(0).astype(int)
yr = yr.round(0); yr.to_csv(out / ('profile32' + TAG + '-yearly.csv'))
p300 = np.exp(np.log1p(ret['csi300'].fillna(0)).cumsum()); ws = d.set_index('t').w
def turn(t0, kind):
    t0 = pd.Timestamp(t0); x = ws.loc[t0:]
    def f(mask):
        z = x[mask]
        if z.empty: return None
        t = z.index[0]; return f"{(t - t0).days} 天，沪深300 {p300.loc[t] / p300.loc[:t0].iloc[-1] * 100 - 100:+.1f}%"
    return {'减到半仓或以下': f(x <= 0.5), '风险清零': f(x == 0)} if kind == 'top' else {'回到半仓或以上': f(x >= 0.5), '满仓': f(x == 1)}
T = {'2007-10 顶': turn('2007-10-16', 'top'), '2009-08 顶': turn('2009-08-04', 'top'), '2015-06 顶': turn('2015-06-12', 'top'), '2008-11 底': turn('2008-11-04', 'bot')}
res = dict(平均风险仓位=round(float(yr['风险仓位'].mean()), 0), 十年档位变动=int(yr['档位变动'].sum()), 十年单只替换=len(nrep), 十年当天减仓=len(nred), 转折=T)
(out / ('profile32' + TAG + '.json')).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
print(json.dumps(res, ensure_ascii=False, indent=1, default=str)); print(yr.to_string())
