"""D38 预演第 3 项：三个信号在各自那一层的月度准确度（信号与下月相对涨幅的秩相关，IC）。

数据：项目池（index 口径，≤2015-12-31，Markets(...).get('index')，同 v5 设计期诊断）；长历史 ^GSPC 1955–2003、^HSI/^N225 1987–2015。
只算信号与下月收益的相关，不算任何组合收益。回看期 3、6、12−1 个月是报告网格，不据此选参数。

① 自己的 10 个月均线（时间序列）：每个容器，月末 (收盘 ÷ 10 个月末均值 − 1) 与下月超额现金收益的秩相关；另报“在均线上方时下月平均超额 − 下方时”。
② 市场之间（A 股 沪深300、港股 恒生、美股 标普和纳指100 平均）：每月三者的回看涨幅排名与下月涨幅排名的秩相关；另报 A 对美两两：强的一边下月更强的比例。
③ 同市场内挑选（A 股：10 个全指行业 + 5 个宽基）：每月横截面，回看涨幅（以及涨幅 ÷ 波动）与下月涨幅的秩相关。
用法：python scripts/preflight/ic.py results/v6-preflight
"""
import sys, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd

def spearmanr(x, y):
    x, y = pd.Series(np.asarray(x, float)), pd.Series(np.asarray(y, float))
    return (x.rank().corr(y.rank()),)
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets

OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
R = m.signal.loc[:'2015-12-31']
SEGS = {'2006–10': ('2006-01-01', '2010-12-31'), '2011–15': ('2011-01-01', '2015-12-31')}

def monthly(r):
    """日收益 → 月末点位（缺值不补；容器上市前为空）。"""
    lvl = np.exp(np.log1p(r).cumsum().where(r.notna()))
    return lvl.resample('ME').last()

P = monthly(R)
cash_m = (1 + R['cash'].fillna(0)).resample('ME').prod() - 1
fwd = P.shift(-1) / P - 1                                   # 下月涨幅
fwd_ex = fwd.sub(cash_m.shift(-1), axis=0)

def lb_ret(P, k):
    return P.shift(1) / P.shift(k) - 1 if k == 12 else P / P.shift(k) - 1   # 12−1：跳过最近 1 个月

def seg_stats(ic):
    out = {}
    for s, (a, b) in SEGS.items():
        x = ic.loc[a:b].dropna()
        out[s] = dict(IC均值=round(float(x.mean()), 3) if len(x) else None,
                      t=round(float(x.mean() / x.std() * np.sqrt(len(x))), 2) if len(x) > 2 and x.std() > 0 else None,
                      月数=int(len(x)), 为正比例=round(float((x > 0).mean()), 2) if len(x) else None)
    return out

res = {}

# ① 10 个月均线（时间序列）
ma_rows = []
dist = P / P.rolling(10).mean() - 1
for c in P.columns:
    if c == 'cash': continue
    d = pd.concat([dist[c], fwd_ex[c]], axis=1).dropna()
    d = d.loc[:'2015-11-30']
    if len(d) < 36: continue
    row = dict(容器=c, 月数=len(d))
    for s, (a, b) in SEGS.items():
        x = d.loc[a:b]
        if len(x) >= 24:
            row[f'IC_{s}'] = round(spearmanr(x.iloc[:, 0], x.iloc[:, 1])[0], 3)
            up, dn = x[x.iloc[:, 0] >= 0].iloc[:, 1], x[x.iloc[:, 0] < 0].iloc[:, 1]
            row[f'上方减下方_月_{s}'] = round(float(up.mean() - dn.mean()) * 100, 2) if len(up) and len(dn) else None
    ma_rows.append(row)
ma = pd.DataFrame(ma_rows); ma.to_csv(OUT / 'ic-ma10.csv', index=False)
res['①均线_项目池'] = {s: dict(容器数=int(ma[f'IC_{s}'].notna().sum()), IC中位=round(float(ma[f'IC_{s}'].median()), 3),
                         IC为正的容器比例=round(float((ma[f'IC_{s}'] > 0).mean()), 2),
                         上方减下方_月_中位=round(float(ma[f'上方减下方_月_{s}'].median()), 2)) for s in SEGS}

# 长历史：单指数
RAW = ROOT / 'data/research/long-history/raw'
lh = {}
for name, f, a, b in (('标普500', '^GSPC.csv', '1955-01-01', '2003-06-30'), ('恒生', '^HSI.csv', '1987-01-01', '2015-12-31'),
                      ('日经', '^N225.csv', '1987-01-01', '2015-12-31')):
    px = pd.read_csv(RAW / f, parse_dates=['date']).set_index('date')['close']
    px = px[(px.index >= a) & (px.index <= b) & (px > 0)].resample('ME').last()
    f1 = px.shift(-1) / px - 1; dd = (px / px.rolling(10).mean() - 1)
    d = pd.concat([dd, f1], axis=1).dropna()
    up, dn = d[d.iloc[:, 0] >= 0].iloc[:, 1], d[d.iloc[:, 0] < 0].iloc[:, 1]
    lh[name] = dict(月数=len(d), IC=round(spearmanr(d.iloc[:, 0], d.iloc[:, 1])[0], 3),
                    上方减下方_月=round(float(up.mean() - dn.mean()) * 100, 2),
                    上方时下月平均=round(float(up.mean()) * 100, 2), 下方时下月平均=round(float(dn.mean()) * 100, 2),
                    在上方的时间=round(float((d.iloc[:, 0] >= 0).mean()), 2))
    lh[name]['_px'] = px
res['①均线_长历史'] = {k: {kk: vv for kk, vv in v.items() if kk != '_px'} for k, v in lh.items()}

# ② 市场之间
mk = pd.DataFrame({'A': P['csi300'], 'HK': P['hsi'], 'US': (P['spx'] / P['spx'].dropna().iloc[0] + P['ndx100'] / P['ndx100'].dropna().iloc[0]) / 2})
fm = mk.shift(-1) / mk - 1
cross = {}
for k in (3, 6, 12):
    sig = lb_ret(mk, k)
    ic = pd.Series({t: spearmanr(sig.loc[t], fm.loc[t])[0] for t in sig.index
                    if sig.loc[t].notna().all() and fm.loc[t].notna().all()})
    pair = pd.concat([sig['US'] - sig['A'], fm['US'] - fm['A']], axis=1).dropna()
    hit = {s: round(float((np.sign(pair.loc[a:b].iloc[:, 0]) == np.sign(pair.loc[a:b].iloc[:, 1])).mean()), 3) for s, (a, b) in SEGS.items()}
    cross[f'{k}个月' if k < 12 else '12−1'] = dict(三市场IC=seg_stats(ic), A对美_强者下月仍强的比例=hit)
res['②市场之间_项目池'] = cross
# 长历史：标普、恒生、日经 1988–2003（三地本币）
L = pd.DataFrame({k: v['_px'] for k, v in lh.items()}).loc['1987-01':'2003-06'].dropna()
fl = L.shift(-1) / L - 1
lcross = {}
for k in (3, 6, 12):
    sig = lb_ret(L, k)
    ic = pd.Series({t: spearmanr(sig.loc[t], fl.loc[t])[0] for t in sig.index if sig.loc[t].notna().all() and fl.loc[t].notna().all()})
    lcross[f'{k}个月' if k < 12 else '12−1'] = dict(IC均值=round(float(ic.mean()), 3), t=round(float(ic.mean() / ic.std() * np.sqrt(len(ic))), 2), 月数=len(ic))
res['②市场之间_长历史_标普恒生日经_1988-2003'] = lcross

# ③ 同市场内挑选（A 股）
SEL = [c for c in P.columns if c.startswith('allshare-')] + ['csi300', 'csi500', 'csi1000', 'chinext', 'csi-dividend']
volm = R[SEL].rolling(60).std().resample('ME').last() * np.sqrt(252)
within = {}
for k in (3, 6, 12):
    sig = lb_ret(P[SEL], k)
    for nm, s in (('涨幅', sig), ('涨幅÷波动', sig / volm)):
        ic = {}
        for t in s.index:
            x, y = s.loc[t], fwd[SEL].loc[t]
            ok = x.notna() & y.notna()
            if ok.sum() >= 8: ic[t] = spearmanr(x[ok], y[ok])[0]
        within[f'{k if k < 12 else "12−1"}|{nm}'] = seg_stats(pd.Series(ic))
res['③A股内挑选_项目池'] = within
res['③说明'] = '项目池 2015 年以前只有 10 个 A 股全指行业 + 5 个宽基；外部行业数据（Kenneth French）待取，见 D38 数据需求。'

json.dump(res, open(OUT / 'ic.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
