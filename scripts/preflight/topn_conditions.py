"""D38 第 25 行 T6：Top N（前 3，不带门槛，单边 0.2%）比全市场多的点数，在不同状态下差多少。
用法：python -I scripts/preflight/topn_conditions.py <49_Industry_Portfolios.csv> results/v6-preflight
"""
import sys, json, pathlib, io
import numpy as np, pandas as pd
FF, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]); COST = 0.002
lines = FF.read_text(errors='replace').splitlines()
def block(title):
    s = next(i for i, l in enumerate(lines) if title in l) + 1; e = s + 1
    while e < len(lines) and lines[e].strip() and lines[e].split(',')[0].strip().isdigit(): e += 1
    d = pd.read_csv(io.StringIO('\n'.join(lines[s:e])), index_col=0); d.columns = [c.strip() for c in d.columns]
    d.index = pd.to_datetime(d.index.astype(str).str.strip(), format='%Y%m') + pd.offsets.MonthEnd(0)
    return d.astype(float).where(lambda x: x > -99)
r = block('Average Value Weighted Returns -- Monthly') / 100
cap = block('Number of Firms in Portfolios') * block('Average Firm Size')
mkt = (cap.shift(1).div(cap.shift(1).sum(axis=1), axis=0) * r).sum(axis=1, min_count=1)
lvl = (1 + r.fillna(0)).cumprod().where(r.notna().cumsum() > 0)
mom = lvl.shift(1) / lvl.shift(12) - 1
upfrac = (r.shift(1).rolling(11).apply(lambda x: (x > 0).mean(), raw=True))     # 前 12 到前 1 个月里上涨月份占比
above = lvl > lvl.rolling(10).mean()
mlvl = (1 + mkt).cumprod()
rows = []; prev = set(); hist = []
for i in range(12, len(r) - 1):
    t, nx = r.index[i], r.index[i + 1]
    sc = mom.loc[t].dropna()
    if len(sc) < 20: continue
    top = list(sc.nlargest(3).index); chg = len(set(top) - prev) / 3 if prev else 1.0; prev = set(top)
    ex = r.loc[nx, top].mean() - mkt.loc[nx] - 2 * COST * chg
    # 平滑 / 跳跃：前 3 里按上涨月份占比分两半（用前 6 名，各取 3 个，比较两组下月收益差）
    top6 = list(sc.nlargest(6).index); uf = upfrac.loc[t, top6].sort_values()
    smooth, jumpy = list(uf.index[3:]), list(uf.index[:3])
    rows.append(dict(t=nx, 超额=ex, 平滑减跳跃=r.loc[nx, smooth].mean() - r.loc[nx, jumpy].mean(),
                     市场36=mlvl.loc[t] / mlvl.shift(36).loc[t] - 1 if i >= 36 else np.nan,
                     市场12=mlvl.loc[t] / mlvl.shift(12).loc[t] - 1,
                     市场24=mlvl.loc[t] / mlvl.shift(24).loc[t] - 1 if i >= 24 else np.nan,
                     市场波动6=mkt.loc[:t].iloc[-6:].std(), 宽度=above.loc[t, sc.index].mean(),
                     自身近况=np.nansum(hist[-12:]) if len(hist) >= 12 else np.nan))
    hist.append(ex)
d = pd.DataFrame(rows).set_index('t').loc['1955':]
def cmp(mask_a, mask_b, la, lb, col='超额'):
    a, b = d.loc[mask_a, col].dropna(), d.loc[mask_b, col].dropna()
    f = lambda x: dict(月数=int(len(x)), 年化点=round(x.mean() * 1200, 1), t=round(x.mean() / x.std() * np.sqrt(len(x)), 2))
    return {la: f(a), lb: f(b)}
volmed = d['市场波动6'].median()
q1, q2 = d['宽度'].quantile([1 / 3, 2 / 3])
res = {
 '全部': cmp(d.index == d.index, d.index != d.index, '全部月份', '—'),
 'H1 市场过去36个月': cmp(d['市场36'] > 0, d['市场36'] <= 0, '涨', '跌'),
 'H1b 市场过去12个月': cmp(d['市场12'] > 0, d['市场12'] <= 0, '涨', '跌'),
 'H2 动量崩溃状态': cmp(~((d['市场24'] < 0) & (d['市场波动6'] > volmed)), (d['市场24'] < 0) & (d['市场波动6'] > volmed), '其他', '过去24个月跌且波动高'),
 'H4 宽度': {**cmp(d['宽度'] >= q2, d['宽度'] <= q1, '宽度高（多数行业在均线上）', '宽度低'),
            **cmp((d['宽度'] > q1) & (d['宽度'] < q2), d.index != d.index, '宽度中', '—')},
 'H5 自身近况': cmp(d['自身近况'] > 0, d['自身近况'] <= 0, '过去12个月前3跑赢', '过去12个月前3跑输'),
 'H3 前6名里平滑减跳跃（下月收益差）': cmp(d.index == d.index, d.index != d.index, '全部月份', '—', col='平滑减跳跃'),
 'H3b 2000年以后': cmp(d.index >= '2000', d.index != d.index, '2000–2026', '—', col='平滑减跳跃'),
}
for k in res: res[k] = {kk: vv for kk, vv in res[k].items() if kk != '—'}
json.dump(res, open(OUT / 'topn-conditions.json', 'w'), ensure_ascii=False, indent=1)
for k, v in res.items(): print(k, v)
