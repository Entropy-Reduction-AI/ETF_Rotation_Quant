"""D38 第 51 行：补估值数据之前的信息价值预估（长期反转作价值的替代）。
用法：python -I scripts/preflight/voi_value.py <49_Industry_Portfolios.csv> <DTB3.csv>
"""
import sys, json, math, pathlib, warnings
warnings.filterwarnings('ignore')
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parents[1]
FFP, DTBP = sys.argv[1], sys.argv[2]
import numpy as np, pandas as pd

G = {'__file__': str(HERE / 'a_official.py'), '__name__': 'x'}; sys.argv = ['x', FFP, DTBP]
exec(open(HERE / 'a_official.py').read().split("res = {'每年末")[0], G)
A_OLD, X = G['A_OLD'], G['f']['X']; COST = 0.002
COLS = ['csi300'] + [c for c in A_OLD.columns if c.startswith('allshare-')]
cal = A_OLD.index; meA = A_OLD[COLS][np.r_[cal.month[1:] != cal.month[:-1], True]]
lvlU = (1 + X.fillna(0)).cumprod().where(X.notna().cumsum() > 0)

def legs(me, parent, a, b, mincand):
    mom = me.shift(1) / me.shift(12) - 1
    cheap = -(me.shift(12) / me.shift(48) - 1)            # 3 年前到 1 年前涨得越少越“便宜”
    nxt = me.pct_change().shift(-1); out = {}
    for nm, sc in (('12−1', mom), ('便宜（长期反转）', cheap)):
        rows = []; prev = pd.Series(0.0, index=me.columns)
        for d in me.loc[a:b].index:
            s = sc.loc[d].where(mom.loc[d].notna()).dropna()
            if len(s) < mincand or not np.isfinite(nxt.loc[d, parent]): prev = pd.Series(0.0, index=me.columns); continue
            top = s.nlargest(3).index; v = nxt.loc[d, top]
            if v.isna().any(): continue
            w = pd.Series(0.0, index=me.columns); w[top] = 1 / 3; tr = float((w - prev).abs().sum()); prev = w
            rows.append((d, float(v.mean() - nxt.loc[d, parent]) - COST * tr))
        out[nm] = pd.Series(dict(rows))
    return pd.DataFrame(out).dropna()

def summarise(df, label):
    ir = (df.mean() / df.std(ddof=1) * math.sqrt(12)); rho = float(df.corr().iloc[0, 1])
    i1, i2 = float(ir.iloc[0]), float(ir.iloc[1])
    best = math.sqrt(max(0.0, (i1 ** 2 + i2 ** 2 - 2 * rho * i1 * i2) / (1 - rho ** 2))) if abs(rho) < 0.999 else max(i1, i2)
    eq = (i1 + i2) / math.sqrt(2 * (1 + rho))                  # 等权合成（两条腿波动相近时）
    te = float(df.iloc[:, 0].std(ddof=1) * math.sqrt(12)); n = len(df)
    o = {'月数': n, '12−1 每年净超额点': round(float(df.iloc[:, 0].mean()) * 1200, 1), '12−1 信息比率': round(i1, 2),
         '便宜 每年净超额点': round(float(df.iloc[:, 1].mean()) * 1200, 1), '便宜 信息比率': round(i2, 2), '两者月度相关': round(rho, 2),
         '合起来最多能到的信息比率（最优权重）': round(best, 2), '等权合起来的信息比率': round(eq, 2)}
    return o, i1, best, eq, te

res = {'说明': '长期反转（3 年前到 1 年前涨得越少越便宜）当估值的替代；前 3 等分、扣单边 0.2%；只估信息价值，不选规则'}
dA = legs(meA, 'csi300', '2009-01', '2015-11', 5); oA, i1, best, eq, te = summarise(dA, 'A')
# 换算：A 股名额每年超额 = 信息比率 × 跟踪误差；组合 = × 0.5 × 0.6 × 40%
for nm, ir in (('现在（只用 12−1，第 49 行全段）', None), ('等权合起来', eq), ('最优权重合起来', best)):
    pass
a0_ir = 5.3 / 16.2                                              # 第 49、50 行：A0 全段 +5.3，跟踪误差 16.2
def money(ir): ex = ir * 16.2; return {'A 股名额每年超额点': round(ex, 1), '组合每年点（打折后）': round(ex * 0.5 * 0.6 * 0.4, 2), '119 个月的 t': round(ir / math.sqrt(12) * math.sqrt(119), 2)}
oA['换算（跟踪误差按 16.2% 不变）'] = {'现在：只用 12−1': money(a0_ir),
                                 '等权合起来（按本行比例放大）': money(a0_ir * eq / i1 if i1 > 0 else a0_ir),
                                 '最优权重合起来（按本行比例放大）': money(a0_ir * best / i1 if i1 > 0 else a0_ir)}
res['A 股：沪深300 + 10 个一级行业，2009–2015'] = oA
dU = legs(lvlU, 'MKT', '1955-01', '2026-12', 10); oU, *_ = summarise(dU, 'US')
res['美国 49 行业 1955–2026（对照、先验）'] = oU
# 第 51 行补注：不挑选的等权基线
sec = [c for c in COLS if c != 'csi300']; nxtA = meA.pct_change().shift(-1); momA = meA.shift(1) / meA.shift(12) - 1
ew, sel = [], []
prev = pd.Series(0.0, index=COLS)
for d in meA.loc['2006-01':'2015-11'].index:
    s = momA.loc[d, COLS].dropna()
    if len(s) < 5: continue
    e = float(nxtA.loc[d, sec].mean()); top = s.nlargest(3).index
    w = pd.Series(0.0, index=COLS); w[top] = 1 / 3; tr = float((w - prev).abs().sum()); prev = w
    ew.append((d, e - float(nxtA.loc[d, 'csi300']))); sel.append((d, float(nxtA.loc[d, top].mean()) - e - COST * tr))
ew = pd.Series(dict(ew)); sel = pd.Series(dict(sel))
tt = lambda x: round(float(x.mean() / x.std(ddof=1) * math.sqrt(len(x))), 2)
res['第 51 行补注：A 股名额 +5.3 拆开'] = {
    '等权 10 个一级行业对沪深300（不挑选）': {k: {'每年点': round(float(ew.loc[a:b].mean()) * 1200, 1), 't': tt(ew.loc[a:b]), '月数': int(len(ew.loc[a:b]))}
                                for k, (a, b) in {'回填段 2006-01 → 2011-07': ('2006-01', '2011-07'), '发布后 2011-08 → 2015-11': ('2011-08', '2015-11'), '全段': ('2006-01', '2015-11')}.items()},
    '12−1 前 3 对等权基线（真正的挑选，扣成本）': {k: {'每年点': round(float(sel.loc[a:b].mean()) * 1200, 1), 't': tt(sel.loc[a:b]), '月数': int(len(sel.loc[a:b]))}
                                for k, (a, b) in {'回填段 2006-01 → 2011-07': ('2006-01', '2011-07'), '发布后 2011-08 → 2015-11': ('2011-08', '2015-11'), '全段': ('2006-01', '2015-11')}.items()},
    '挑选部分的年跟踪误差%': round(float(sel.std(ddof=1) * math.sqrt(12)) * 100, 1)}
# 第 51 行补注 2：美股同样拆开
indU = [c for c in X.columns if c != 'MKT']; momU = lvlU.shift(1) / lvlU.shift(12) - 1
ewU, selU = [], []; prev = pd.Series(0.0, index=X.columns)
for d in X.loc['1955-01':'2026-11'].index:
    i = X.index.get_loc(d)
    if i + 1 >= len(X.index): break
    nx = X.index[i + 1]; s = momU.loc[d, list(X.columns)].dropna()
    if len(s) < 10: continue
    e = float(X.loc[nx, indU].mean()); top = s.nlargest(3).index
    w = pd.Series(0.0, index=X.columns); w[top] = 1 / 3; tr = float((w - prev).abs().sum()); prev = w
    ewU.append((nx, e - float(X.loc[nx, 'MKT']))); selU.append((nx, float(X.loc[nx, top].mean()) - e - COST * tr))
ewU = pd.Series(dict(ewU)); selU = pd.Series(dict(selU))
res['第 51 行补注 2：美股 前 3 比全市场 拆开（1955–2026）'] = {
    '等权 49 行业对全市场（不挑选）': {'每年点': round(float(ewU.mean()) * 1200, 1), 't': tt(ewU), '月数': int(len(ewU))},
    '12−1 前 3 对等权基线（真正的挑选，扣成本）': {'每年点': round(float(selU.mean()) * 1200, 1), 't': tt(selU), '月数': int(len(selU))},
    '分段：挑选部分每年点': {k: round(float(selU.loc[a:b].mean()) * 1200, 1) for k, (a, b) in {'1955–1979': ('1955', '1979'), '1980–1999': ('1980', '1999'), '2000–2015': ('2000', '2015'), '2016–2026': ('2016', '2026')}.items()}}
json.dump(res, open(ROOT / 'results/v6-preflight/voi-value.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
