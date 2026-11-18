"""D38 第 36 行 S1：紧张期领头者存活度（美国、港股、A 股）。
用法：python scripts/preflight/leader_stress.py <49_Industry_Portfolios.csv>
"""
import sys, json, io, sqlite3, pathlib, warnings
warnings.filterwarnings('ignore')
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parents[1]; FF = pathlib.Path(sys.argv[1])
import numpy as np, pandas as pd

def measure(lvl_me, parent_me, N, segs=None):
    """lvl_me：候选月末点位；parent_me：母指数月末点位。"""
    mom = lvl_me.shift(1) / lvl_me.shift(12) - 1; nx = lvl_me.pct_change().shift(-1); pnx = parent_me.pct_change().shift(-1)
    pbelow = parent_me < parent_me.rolling(10).mean()
    b1 = (lvl_me > lvl_me.rolling(10).mean()).where(lvl_me.rolling(10).count() == 10).mean(axis=1)
    blow = b1 <= b1.expanding(min_periods=24).quantile(1 / 3)
    rows = []
    for t in lvl_me.index:
        s = mom.loc[t].dropna()
        if len(s) < N + 1 or pd.isna(pnx.get(t)) or pd.isna(b1.get(t)): continue
        top = s.nlargest(N).index; lr = nx.loc[t, top].mean()
        if pd.isna(lr): continue
        rows.append(dict(t=t, 紧张=bool(pbelow.loc[t] and blow.loc[t]), 领头=lr, 母=pnx.loc[t]))
    d = pd.DataFrame(rows).set_index('t')
    def f(x):
        if len(x) < 5: return None
        return dict(月数=int(len(x)), 领头者下月绝对_年化=round(x['领头'].mean() * 1200, 1), 为正比例=round(float((x['领头'] > 0).mean()), 2),
                    母指数下月_年化=round(x['母'].mean() * 1200, 1), 领头超额_年化=round((x['领头'] - x['母']).mean() * 1200, 1),
                    t_领头绝对=round(float(x['领头'].mean() / x['领头'].std() * np.sqrt(len(x))), 2))
    out = {'紧张月': f(d[d['紧张']]), '其余月': f(d[~d['紧张']])}
    if segs:
        out['紧张月分段'] = {k: f(d.loc[a:b][d.loc[a:b, '紧张']]) for k, (a, b) in segs.items()}
    v = out['紧张月']
    out['判定'] = None if v is None else ('分级要求（领头者紧张时平均仍在涨）' if v['领头者下月绝对_年化'] > 0 else '按票减仓（领头者紧张时平均也在跌）')
    return out

res = {}
# 美国：French 49 行业
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
lvl = (1 + r.fillna(0)).cumprod().where(r.notna().cumsum() > 0); ml = (1 + mkt.fillna(0)).cumprod()
res['美国 49 行业 1927–2026（前 3）'] = measure(lvl, ml, 3, {'1927–1954': ('1927', '1954'), '1955–1979': ('1955', '1979'), '1980–1999': ('1980', '1999'),
                                                      '2000–2015': ('2000', '2015'), '2016–2026': ('2016', '2026')})
# 港股：恒生四个分类指数 + 恒指（价格口径）
c = sqlite3.connect(ROOT / 'data/market.sqlite')
def bar(code):
    d = pd.read_sql_query("select date, close from bars where code=? and adj='raw' and close>0 and date<='2015-12-31' order by date", c, params=(code,))
    return pd.Series(d['close'].values, pd.to_datetime(d['date'])).groupby(level=0).last()
hk = pd.DataFrame({k: bar(k) for k in ('HSC', 'HSF', 'HSU', 'HSP')}).resample('ME').last()
hsi = pd.read_csv(ROOT / 'data/research/long-history/raw/^HSI.csv', parse_dates=['date']).set_index('date')['close'].loc[:'2015-12-31'].resample('ME').last()
res['港股 恒生四个分类 1993–2015（前 1）'] = measure(hk.loc['1992':], hsi.reindex(hk.index).loc['1992':], 1)
# A 股：第 22 行候选（项目池 index 口径，全收益）
sys.argv = [sys.argv[0], 'results/v6-preflight']
g = {'__file__': str(HERE / 'topn_system.py'), '__name__': 'x'}; exec(open(HERE / 'topn_system.py').read().split("res = {'第22行")[0], g)
A = g['A_LVL']; Ame = A.resample('ME').last()
res['A 股 第 22 行候选 2006–2015（前 2）'] = measure(Ame.drop(columns=['csi300']), Ame['csi300'], 2)
json.dump(res, open('results/v6-preflight/leader-stress.json', 'w'), ensure_ascii=False, indent=1)
for k, v in res.items():
    print('==', k); print(' 紧张月', v['紧张月']); print(' 其余月', v['其余月']); print(' 判定', v['判定'])
    if '紧张月分段' in v: [print('   ', kk, vv) for kk, vv in v['紧张月分段'].items()]
