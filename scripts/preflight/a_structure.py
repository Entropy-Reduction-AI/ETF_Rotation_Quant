"""D38 第 50 行：A 股结构的描述性统计（不选规则）。
用法：python -I scripts/preflight/a_structure.py <49_Industry_Portfolios.csv> <DTB3.csv>
"""
import sys, json, math, pathlib, warnings
warnings.filterwarnings('ignore')
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parents[1]
FFP, DTBP = sys.argv[1], sys.argv[2]
import numpy as np, pandas as pd

G = {'__file__': str(HERE / 'a_official.py'), '__name__': 'x'}; sys.argv = ['x', FFP, DTBP]
exec(open(HERE / 'a_official.py').read().split("res = {'每年末")[0], G)
A_OLD, A, X, bond, votes = G['A_OLD'], G['A'], G['f']['X'], G['bond'], G['votes']
SEC = [c for c in A_OLD.columns if c.startswith('allshare-')]
cal = A_OLD.index; mm = np.r_[cal.month[1:] != cal.month[:-1], True]
meA = A_OLD[mm]; rA = meA.pct_change().loc['2006-01':'2015-12']
rU = X.loc['2006-01':'2015-12', [c for c in X.columns if c != 'MKT']]; mU = X.loc['2006-01':'2015-12', 'MKT']
res = {'说明': '只用 ≤2015；描述性统计，不选规则'}

def space(R, M):
    c = R.corr().values; iu = np.triu_indices_from(c, 1)
    disp = R.std(axis=1)
    return {'平均两两相关': round(float(np.nanmean(c[iu])), 2), '截面离散度_月均%': round(float(disp.mean()) * 100, 2),
            '市场月波动%': round(float(M.std()) * 100, 2), '离散度 ÷ 市场波动': round(float(disp.mean() / M.std()), 2)}
res['① 挑选的空间（2006–2015 月度）'] = {'A 股 10 个一级行业': space(rA[SEC], rA['csi300']), '美国 49 行业': space(rU, mU),
                                  '美国 49 行业 1955–2015': space(X.loc['1955':'2015', [c for c in X.columns if c != 'MKT']], X.loc['1955':'2015', 'MKT'])}

# ② 收益集中度
r3 = rA['csi300']; lg = np.log1p(r3); k = int(round(len(r3) * 0.1)); top = lg.nlargest(k)
above = (meA["csi300"] > meA["csi300"].rolling(10).mean()).shift(1).fillna(False).astype(bool).loc[r3.index]   # 上月末是否在均线上方 → 本月
bm = np.exp(np.log1p(bond.fillna(0)).cumsum()).reindex(cal).ffill(); bme = bm[mm].pct_change().loc[r3.index]
res['② 沪深300 收益集中度（2006–2015，120 个月）'] = {
    '累计收益%': round(float(np.expm1(lg.sum())) * 100, 1), f'最好 {k} 个月的累计贡献%': round(float(np.expm1(top.sum())) * 100, 1),
    f'去掉最好 {k} 个月后累计%': round(float(np.expm1(lg.sum() - top.sum())) * 100, 1),
    '最好的月份都在哪一年': {str(y): int(n) for y, n in top.groupby(top.index.year).size().items()},
    '同期 10 年国债累计%': round(float(np.expm1(np.log1p(bme).sum())) * 100, 1),
    '均线上方的月份': {'占比': round(float(above.mean()), 2), '月均%': round(float(r3[above].mean()) * 100, 2), '月波动%': round(float(r3[above].std()) * 100, 2)},
    '均线下方的月份': {'占比': round(float((~above).mean()), 2), '月均%': round(float(r3[~above].mean()) * 100, 2), '月波动%': round(float(r3[~above].std()) * 100, 2)}}

# ③ 红利（按发布日截断）
dv = A['csi-dividend'][mm].pct_change().loc['2008-06':'2015-12']; base = r3.reindex(dv.index); ex = (dv - base).dropna()
V, _ = votes(A, 'csi300', ['均线', '宽度', 'TRIN']); st = pd.Series({d: int(V.get((d - pd.offsets.MonthEnd(1)).to_period('M'), 0)) >= 2 for d in ex.index})
ab = above.reindex(ex.index).fillna(False).astype(bool)
def g(x): return {'月数': int(len(x)), '月均超额%': round(float(x.mean()) * 100, 2), '胜率': round(float((x > 0).mean()), 2)}
res['③ 中证红利对沪深300（2008-06 → 2015-12）'] = {'全部': g(ex), '母指数在均线上方': g(ex[ab.values]), '母指数在均线下方': g(ex[~ab.values]),
                                          '上月确认紧张': g(ex[st.values]), '红利月波动% / 沪深300 月波动%': [round(float(dv.std()) * 100, 2), round(float(base.std()) * 100, 2)]}

# ④ t ≥ 2 需要多大的超额（用第 49 行 A0 的月度净超额）
S = json.load(open(ROOT / 'results/v6-preflight/a-signals.json'))
a0 = S['各选法']['A0 12−1']['全段 2006-01 → 2015-11']
mu = a0['净超额_点每年'] / 1200; t = a0['t_净']; n = a0['月数']; sd = mu * math.sqrt(n) / t
res['④ A 股名额前 3 要到 t ≥ 2 需要什么'] = {
    '现在：每年净超额点': a0['净超额_点每年'], 't': t, '月数': n, '月跟踪误差%': round(sd * 100, 2), '年跟踪误差%': round(sd * math.sqrt(12) * 100, 1),
    '同样月数下 t = 2 需要的每年超额点': round(2 * sd / math.sqrt(n) * 1200, 1),
    '同样超额下 t = 2 需要的月数': int(math.ceil((2 * sd / mu) ** 2)), '折合年数': round((2 * sd / mu) ** 2 / 12, 1)}
# A0 月度超额的胜率与盈亏比（重算一遍，与第 49 行同口径）
s12 = meA.shift(1) / meA.shift(12) - 1; nxt = meA.pct_change().shift(-1); cols = ['csi300'] + SEC; exm = []
for d in meA.loc['2006-01':'2015-11'].index:
    s = s12.loc[d, cols].dropna()
    if len(s) < 5: continue
    top3 = s.nlargest(3).index; exm.append(float(nxt.loc[d, top3].mean() - nxt.loc[d, 'csi300']))
exm = pd.Series(exm)
res['④ A 股名额前 3 要到 t ≥ 2 需要什么']['A0 月度毛超额：胜率 / 平均赚% / 平均亏% / 偏度'] = [
    round(float((exm > 0).mean()), 2), round(float(exm[exm > 0].mean()) * 100, 2), round(float(exm[exm < 0].mean()) * 100, 2), round(float(exm.skew()), 2)]
json.dump(res, open(ROOT / 'results/v6-preflight/a-structure.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
