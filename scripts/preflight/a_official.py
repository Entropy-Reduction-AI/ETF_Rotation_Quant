"""D38 第 39 行：A 股按发布日校正重跑（R1），以及 Owner 不对称判断的检验（R2）。
用法：python scripts/preflight/a_official.py <49_Industry_Portfolios.csv> <DTB3.csv>
"""
import sys, json, math, sqlite3, tomllib, pathlib, warnings
warnings.filterwarnings('ignore')
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parents[1]
FFP, DTBP = sys.argv[1], sys.argv[2]
import numpy as np, pandas as pd

# ---------- 载入：沿用 topn_tiered 的设计期数据与 votes ----------
sys.argv = [sys.argv[0], FFP, DTBP]
T = {'__file__': str(HERE / 'topn_tiered.py'), '__name__': 'x'}
exec(open(HERE / 'topn_tiered.py').read().split("res = {'设计期'")[0], T)
V = T['g']                                         # topn_vote 的命名空间（含 TRIN、votes、vs）
A_OLD, US_RMB, bond, cash, stats, P = T['A_LVL'], T['US_RMB'], T['bond'], T['cash'], T['stats'], T['g']['g']['P']
idx = A_OLD.index

# ---------- A 股官方候选 ----------
pub = {}
for c in tomllib.load(open(ROOT / 'config/v3/universe.toml', 'rb'))['container']:
    r = c.get('research', {}); cid = c.get('id') or c.get('container_id')
    if r.get('publish_date') and r['publish_date'] != '取不到': pub[cid] = r['publish_date']
pub.setdefault('chinext', '2010-06-01')                     # 创业板指 2010-06-01 发布，基日 2010-05-31，无回填
ro = pd.read_csv(ROOT / 'results/v51-diag/d37/s1-splice-roster.csv')
th = ro[(ro['class'] == 'A股') & (ro['status'] == 'spliced') & ro['publish_date'].notna()]
con = sqlite3.connect(ROOT / 'data/market.sqlite')
def bars(code):
    d = pd.read_sql_query("select date, close, amount from bars where code=? and adj='raw' and close>0 and date<='2015-12-31' order by date", con, params=(code,))
    d = d.drop_duplicates('date', keep='last'); d.index = pd.to_datetime(d['date']); return d
A = A_OLD.copy(); AMT = {}
for c in A.columns:
    if c in pub: A.loc[:pd.Timestamp(pub[c]) - pd.Timedelta(days=1), c] = np.nan
    A[c] = A[c] / A[c].dropna().iloc[0] if A[c].notna().any() else A[c]
for _, r in th.iterrows():
    d = bars(str(r['index_code']))
    if d.empty: continue
    d = d.loc[r['publish_date']:]
    if len(d) < 60: continue
    A[r['container_id']] = d['close'].reindex(idx).ffill().where(lambda s: s.index >= d.index[0])
    AMT[r['container_id']] = d['amount'].where(d['amount'] > 0)
for c, code in (('csi500', 'H00905'), ('csi1000', 'H00852')) + tuple((c, f'H0098{i}') for i, c in zip(range(6, 10), ['allshare-energy', 'allshare-materials', 'allshare-industrials', 'allshare-discretionary'])) + \
               tuple((c, f'H0099{i}') for i, c in zip(range(0, 6), ['allshare-staples', 'allshare-healthcare', 'allshare-financials-re', 'allshare-it', 'allshare-communication', 'allshare-utilities'])):
    d = bars(code)
    if not d.empty and c in pub: AMT[c] = d['amount'].where(d['amount'] > 0).loc[pub[c]:]
ncand = (A.drop(columns=['csi300']).notna().astype(float).rolling(252).sum() >= 252).sum(axis=1)
ncand_y = {str(k): int(v) for k, v in ncand.groupby(ncand.index.year).last().items()}

# 官方 A 股 TRIN（日 TRIN 10 日均）：有成交额的候选，按发布日截断
AM = pd.DataFrame(AMT).astype(float).reindex(idx); PX = A[AM.columns]   # 第六轮入库后成交额可能是 object 列
dr = PX.pct_change(); up, dn = dr > 0, dr < 0
d_ = ((up.sum(axis=1) / dn.sum(axis=1).replace(0, np.nan)) / ((AM * up).sum(axis=1) / (AM * dn).sum(axis=1).replace(0, np.nan))).replace([np.inf, -np.inf], np.nan)
d_ = d_.where(up.sum(axis=1) + dn.sum(axis=1) >= 4)
t2 = d_.clip(upper=d_.quantile(0.99)).rolling(10, min_periods=7).mean().resample('ME').last(); t2.index = t2.index.to_period('M')
V['TRIN']['csi300'] = t2

# ---------- 按把握调节的系统（与 topn_phi 相同的规则） ----------
Phi = lambda t: 0.5 * (1 + math.erf(t / math.sqrt(2))); COST = 0.002
def conf(hist, prior=None, min_n=12):
    h = list(prior or []) + list(hist)
    if len(h) < min_n: return 0.5
    a = np.array(h); sd = a.std(ddof=1); return Phi(a.mean() / sd * math.sqrt(len(a))) if sd > 0 else 0.5
src = open(HERE / 'topn_phi.py').read()
exec(src[src.index('def slot_phi'):src.index('def summ')], globals())
exec(src[src.index('def summ'):src.index('Dz = {}')], globals())
votes = V['votes']
# 美股起点经验：French 1999 年以前的紧张月
F = {'__file__': str(HERE / 'topn_phi.py'), '__name__': 'x'}; sys.argv = ['x', FFP, DTBP, 'results/v6-preflight']
exec(open(HERE / 'topn_phi.py').read().split("res = {}")[0], F)
f = {'__file__': str(HERE / 'topn_longhist.py')}; exec(open(HERE / 'topn_longhist.py').read().split("ALL = list")[0], f)
X0 = f['X'].loc['1926-07':'1998-12']; F['monthly'](X0, 'MKT', 3, 'phi', f['rf'].reindex(X0.index).fillna(0), '1955'); US_PRIOR = list(F['monthly'].hist)

res = {'每年末 A 股可参选候选个数（发布满 12 个月）': ncand_y, 'R1 设计期整套系统（A 股按发布日校正）': {}}
D = res['R1 设计期整套系统（A 股按发布日校正）']
for N in (2, 3):
    a, ta, pa = slot_phi(A, 'csi300', N, bond, cash, None); u, tu, pu = slot_phi(US_RMB, 'SPX', N, bond, cash, US_PRIOR)
    for us in (0.50, 0.55, 0.60): D[f'前{N} 按把握调节，美股 {int(us*100)}%'] = summ((1 - us) * a + us * u, ta, tu)
    if N == 2:
        D['A 股名额单独（前2）'] = stats(a, '2006-01-01', {'2006–10': ('2006', '2010'), '2011–15': ('2011', '2015')})
        D['A 股名额把握 p（年末）'] = {str(k): round(v, 2) for k, v in pa.groupby(pd.DatetimeIndex(pa.index).year).last().items()}
hold = A_OLD['csi300'].pct_change().fillna(0); D['参照 一直持有沪深300'] = stats(hold, '2006-01-01', {'2006–10': ('2006', '2010'), '2011–15': ('2011', '2015')})
old = json.load(open(ROOT / 'results/v6-preflight/topn-phi.json'))['③ 设计期整套系统 2006–2015']
for k in ('前2 按把握调节（美 50%）', '前2 按把握调节，美股常驻 60%', '参照 基准（美股30%）', '参照 增强基准（K2A 美股50%）'): D[f'校正前 {k}' if not k.startswith('参照') else k] = old[k]

# 第 36 行 A 股部分重跑
L = {'__file__': str(HERE / 'leader_stress.py')}; sys.argv = ['x', FFP]
exec(open(HERE / 'leader_stress.py').read().split("res = {}")[0], L)
Ame = A.resample('ME').last()
res['R1 A 股紧张期领头者存活度（校正后，前 2）'] = L['measure'](Ame.drop(columns=['csi300']), Ame['csi300'], 2)

# ---------- R2 不对称 ----------
us_r = ((P['spx'] + P['ndx100']) / 2); a_r = P['csi300']
def asym(ra, rb, freq, la, lb):
    x = pd.DataFrame({la: (1 + ra).resample(freq).prod() - 1, lb: (1 + rb).resample(freq).prod() - 1}).dropna()
    x = x[(x[la] != 0) & (x[lb] != 0)]
    o = {'期数': len(x), f'P({la}涨|{lb}涨)': round(float((x[la] > 0)[x[lb] > 0].mean()), 2), f'P({la}涨|{lb}跌)': round(float((x[la] > 0)[x[lb] < 0].mean()), 2),
         f'P({lb}涨|{la}涨)': round(float((x[lb] > 0)[x[la] > 0].mean()), 2), f'P({lb}涨|{la}跌)': round(float((x[lb] > 0)[x[la] < 0].mean()), 2), '相关': round(float(x.corr().iloc[0, 1]), 2)}
    if freq == 'QE':
        o[f'{lb}单季跌超10%时{la}平均'] = f"{round(float(x.loc[x[lb] < -0.10, la].mean()) * 100, 1)}%（{int((x[lb] < -0.10).sum())} 次）"
        o[f'{la}单季跌超10%时{lb}平均'] = f"{round(float(x.loc[x[la] < -0.10, lb].mean()) * 100, 1)}%（{int((x[la] < -0.10).sum())} 次）"
        o[f'{lb}单季涨超10%时{la}平均'] = f"{round(float(x.loc[x[lb] > 0.10, la].mean()) * 100, 1)}%（{int((x[lb] > 0.10).sum())} 次）"
        o[f'{la}单季涨超10%时{lb}平均'] = f"{round(float(x.loc[x[la] > 0.10, lb].mean()) * 100, 1)}%（{int((x[la] > 0.10).sum())} 次）"
    return o
R2 = {'A 股 vs 美股（人民币，2005–2015）月度': asym(a_r, us_r, 'ME', 'A', '美'), 'A 股 vs 美股（人民币，2005–2015）季度': asym(a_r, us_r, 'QE', 'A', '美')}
raw = ROOT / 'data/research/long-history/raw'
hsi = pd.read_csv(raw / '^HSI.csv', parse_dates=['date']).set_index('date')['close'].loc['1987':'2015']
spx = pd.read_csv(raw / '^GSPC.csv', parse_dates=['date']).set_index('date')['close'].loc['1987':'2015']
R2['恒指 vs 标普（价格，1987–2015，代理）季度'] = asym(hsi.pct_change().dropna(), spx.pct_change().dropna(), 'QE', '港', '美')
res['R2 不对称'] = R2
json.dump(res, open(ROOT / 'results/v6-preflight/a-official.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(res['每年末 A 股可参选候选个数（发布满 12 个月）']); print({c: str(A[c].first_valid_index().date()) for c in ['allshare-energy','csi1000','csi-dividend','csi500','chinext']})
print(pd.DataFrame({k: v for k, v in D.items() if '把握 p' not in k}).T.to_string()); print(D['A 股名额把握 p（年末）'])
print(json.dumps(res['R1 A 股紧张期领头者存活度（校正后，前 2）'], ensure_ascii=False, default=str))
for k, v in R2.items(): print(k, v)
