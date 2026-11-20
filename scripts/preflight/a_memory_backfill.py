"""D38 第 48 行：用 10 个中证全指一级行业的回填段，补充检验 A 股“记忆更短”（12−1 对 上月涨幅）。
用法：python -I scripts/preflight/a_memory_backfill.py <49_Industry_Portfolios.csv> <DTB3.csv>
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
assert len(COLS) == 11, COLS

def me_of(lvl):
    cal = lvl.index; return lvl[np.r_[cal.month[1:] != cal.month[:-1], True]] if not isinstance(cal, pd.PeriodIndex) else lvl

def run(me, parent, a, b, mincand=5):
    """月末点位 → 两种速度的前 3 对母指数的月超额（毛、净）与换手。"""
    nxt = me.pct_change().shift(-1); s12 = me.shift(1) / me.shift(12) - 1; s1 = (me / me.shift(1) - 1).where(s12.notna())
    out = {}
    for nm, sc in (('12−1', s12), ('上月涨幅', s1)):
        rows = []; prev = pd.Series(0.0, index=me.columns)
        for d in me.loc[a:b].index:
            s = sc.loc[d].dropna()
            if len(s) < mincand or not np.isfinite(nxt.loc[d, parent]): prev = pd.Series(0.0, index=me.columns); continue
            top = s.nlargest(3).index; v = nxt.loc[d, top]
            if v.isna().any(): continue
            w = pd.Series(0.0, index=me.columns); w[top] = 1 / 3; tr = float((w - prev).abs().sum()); prev = w
            g = float(v.mean() - nxt.loc[d, parent]); rows.append((d, g, g - COST * tr, tr))
        out[nm] = pd.DataFrame(rows, columns=['d', 'gross', 'net', 'tr']).set_index('d')
    return out

def fmt(df):
    if df.empty: return '无'
    t = lambda x: round(float(x.mean() / x.std(ddof=1) * math.sqrt(len(x))), 2)
    return (f"毛 {df['gross'].mean() * 1200:+.1f} 点 · 净 {df['net'].mean() * 1200:+.1f} 点（t {t(df['net'])}，{len(df)} 个月）"
            f" · 每年换手 {df['tr'].mean() * 12:.1f} 倍")

res = {'说明': '前 3 等分，对母指数的月超额，年化点数；净 = 扣单边 0.2% × 换手'}
meA = me_of(A_OLD[COLS])
R = {}
for seg, (a, b) in {'回填段 2006-01 → 2011-07（速度比较没看过）': ('2006-01', '2011-07'), '发布后 2011-08 → 2015-11': ('2011-08', '2015-11'),
                    '全段 2006-01 → 2015-11': ('2006-01', '2015-11')}.items():
    o = run(meA, 'csi300', a, b); R[seg] = {k: fmt(v) for k, v in o.items()}
    if seg.startswith('回填段'):
        y = {k: v['net'].groupby(v.index.year).sum().mul(100).round(1).to_dict() for k, v in o.items()}
        R['回填段逐年净超额（点）'] = {str(yr): {k: y[k].get(yr) for k in y} for yr in sorted(set().union(*[set(v) for v in y.values()]))}
res['A 股：沪深300 + 10 个全指一级行业（含 2011-08 之前的回填点位）'] = R
lvlL = (1 + X.fillna(0)).cumprod().where(X.notna().cumsum() > 0)
res['对照：美国 49 行业 1955–2026（对全市场）'] = {k: fmt(v) for k, v in run(lvlL, 'MKT', '1955-01', '2026-12', 10).items()}
json.dump(res, open(ROOT / 'results/v6-preflight/a-memory-backfill.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
