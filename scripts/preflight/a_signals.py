"""D38 第 49 行：A 股选法有限候选集（A0 12−1 / A1 6−1 / A2 风险调整 12−1 / A4 拥挤度刹车；A3 缺开盘价，本次不算）。
用法：python -I scripts/preflight/a_signals.py <49_Industry_Portfolios.csv> <DTB3.csv>
"""
import sys, json, math, sqlite3, itertools, pathlib, warnings
warnings.filterwarnings('ignore')
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parents[1]
FFP, DTBP = sys.argv[1], sys.argv[2]
import numpy as np, pandas as pd

G = {'__file__': str(HERE / 'a_official.py'), '__name__': 'x'}; sys.argv = ['x', FFP, DTBP]
exec(open(HERE / 'a_official.py').read().split("res = {'每年末")[0], G)
A_OLD = G['A_OLD']; COST = 0.002
COLS = ['csi300'] + [c for c in A_OLD.columns if c.startswith('allshare-')]
D = A_OLD[COLS]                                   # 日点位（全收益，含 2011-08 之前的回填段）
cal = D.index; mm = np.r_[cal.month[1:] != cal.month[:-1], True]; me = D[mm]

# 成交额（2011-08-03 起才有）
con = sqlite3.connect(ROOT / 'data/market.sqlite')
import tomllib
U = {c['id']: c for c in tomllib.load(open(ROOT / 'config/v3/universe.toml', 'rb'))['container']}
AMT = {}
for c in COLS:
    code = U[c]['research']['series_code']
    d = pd.read_sql_query("select date, amount from bars where code=? and amount>0 and date<='2015-12-31'", con, params=(code,))
    AMT[c] = pd.Series(d['amount'].astype(float).values, pd.to_datetime(d['date'])).groupby(level=0).last()
AM = pd.DataFrame(AMT).reindex(cal)

# ---------- 打分（月末，只用到 t 为止） ----------
s12 = me.shift(1) / me.shift(12) - 1
s6 = me.shift(1) / me.shift(6) - 1
dr = D.pct_change()
vol = pd.DataFrame(index=me.index, columns=COLS, dtype=float)
pos = {d: i for i, d in enumerate(cal)}; mei = [pos[d] for d in me.index]
for k, d in enumerate(me.index):
    if k < 12: continue
    a, b = mei[k - 12], mei[k - 1]                # 12 个月前月末 → 1 个月前月末
    vol.loc[d] = dr.iloc[a + 1:b + 1].std() * math.sqrt(252)
s_risk = s12 / vol
sec = [c for c in COLS if c != 'csi300']
share = AM[sec].div(AM[sec].sum(axis=1), axis=0).rolling(20, min_periods=15).mean()
pct = share.rolling(250, min_periods=200).apply(lambda x: (x[:-1] < x[-1]).mean() if np.isfinite(x[-1]) else np.nan, raw=True)
hot = pct[mm] > 0.9                                            # 自身过去 250 天的最高 10%
s_crowd = s12.copy(); s_crowd[sec] = s12[sec].where(~hot.reindex(index=me.index).fillna(False))
# 母指数没有拥挤度，照常参选；A4 只在拥挤度可算的月份评估
crowd_ok = pct[mm][sec].notna().all(axis=1)
SC = {'A0 12−1': s12, 'A1 6−1': s6, 'A2 风险调整 12−1': s_risk, 'A4 12−1 + 拥挤度刹车': s_crowd}

nxt = me.pct_change().shift(-1)
def monthly(sc, a, b, need=None):
    rows = []; prev = pd.Series(0.0, index=COLS)
    for d in me.loc[a:b].index:
        if need is not None and not bool(need.get(d, False)): prev = pd.Series(0.0, index=COLS); continue
        s = sc.loc[d].where(s12.loc[d].notna()).dropna()
        if len(s) < 5 or not np.isfinite(nxt.loc[d, 'csi300']): prev = pd.Series(0.0, index=COLS); continue
        top = s.nlargest(3).index; v = nxt.loc[d, top]
        if v.isna().any(): continue
        w = pd.Series(0.0, index=COLS); w[top] = 1 / 3; tr = float((w - prev).abs().sum()); prev = w
        g = float(v.mean() - nxt.loc[d, 'csi300']); rows.append((d, g, g - COST * tr, tr))
    return pd.DataFrame(rows, columns=['d', 'gross', 'net', 'tr']).set_index('d')
def tt(x): x = pd.Series(x).dropna(); return round(float(x.mean() / x.std(ddof=1) * math.sqrt(len(x))), 2) if len(x) > 2 else None
def fmt(df):
    return {'净超额_点每年': round(float(df['net'].mean()) * 1200, 1), '毛超额_点每年': round(float(df['gross'].mean()) * 1200, 1),
            't_净': tt(df['net']), '月数': len(df), '每年换手_倍': round(float(df['tr'].mean()) * 12, 1)}

SEG = {'回填段 2006-01 → 2011-07': ('2006-01', '2011-07'), '发布后 2011-08 → 2015-11': ('2011-08', '2015-11'), '全段 2006-01 → 2015-11': ('2006-01', '2015-11')}
res = {'说明': '沪深300 + 10 个全指一级行业，前 3 等分，对沪深300；净 = 扣单边 0.2% × 换手；A3 缺开盘价未算'}
R = {}
for nm, sc in SC.items():
    if nm.startswith('A4'):
        R[nm] = {'发布后可算月份（2012-08 起）': fmt(monthly(sc, '2012-08', '2015-11', crowd_ok)),
                 '对照 A0 同月份': fmt(monthly(s12, '2012-08', '2015-11', crowd_ok))}
    else:
        R[nm] = {seg: fmt(monthly(sc, a, b)) for seg, (a, b) in SEG.items()}
res['各选法'] = R

# ---------- 滚动前推：每年末在 A0–A2 里选到当时净超额最高的，用于下一年 ----------
M = {nm: monthly(SC[nm], '2006-01', '2015-11')['net'] for nm in ['A0 12−1', 'A1 6−1', 'A2 风险调整 12−1']}
MM = pd.DataFrame(M).dropna()
wf, pick = [], {}
for yr in range(2008, 2016):
    past = MM.loc[:f'{yr - 1}-12']; best = past.mean().idxmax(); pick[str(yr)] = best
    wf.append(MM.loc[str(yr), best])
wf = pd.concat(wf)
res['滚动前推（2008–2015）'] = {'每年选中的': pick, '滚动前推净超额_点每年': round(float(wf.mean()) * 1200, 1), 't': tt(wf),
                         '一直用 A0 同期_点每年': round(float(MM.loc['2008':, 'A0 12−1'].mean()) * 1200, 1), 'A0 t': tt(MM.loc['2008':, 'A0 12−1'])}

# ---------- 过拟合概率（CSCV，8 段） ----------
S = 8; blocks = np.array_split(np.arange(len(MM)), S); logits = []
for comb in itertools.combinations(range(S), S // 2):
    ins = np.concatenate([blocks[i] for i in comb]); oos = np.concatenate([blocks[i] for i in range(S) if i not in comb])
    best = MM.iloc[ins].mean().values.argmax(); r = MM.iloc[oos].mean().rank().values[best] / (MM.shape[1] + 1)
    logits.append(math.log(r / (1 - r)))
res['过拟合概率（CSCV，A0–A2，8 段）'] = {'PBO': round(float(np.mean(np.array(logits) <= 0)), 2), '组合数': len(logits),
                                    '样本内最好者在样本外排名后一半的比例即 PBO': ''}
res['A0–A2 月度净超额相关'] = MM.corr().round(2).to_dict()
json.dump(res, open(ROOT / 'results/v6-preflight/a-signals.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
