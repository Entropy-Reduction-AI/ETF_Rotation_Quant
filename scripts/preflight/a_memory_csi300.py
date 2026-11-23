"""D38 第 45 行：沪深300 十个行业（官方全收益 H00908–H00917，发布日 2007-07-02 起）检验 A 股“记忆更短”。
R0 = 12−1、S1 = 上月涨幅；前 3 等分、单边 0.2%、不设防守、对沪深300；母指数沪深300 也是候选。
用法：python -I scripts/preflight/a_memory_csi300.py <49_Industry_Portfolios.csv> <DTB3.csv>
"""
import sys, json, math, pathlib, warnings
warnings.filterwarnings('ignore')
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parents[1]
FFP, DTBP = sys.argv[1], sys.argv[2]
import numpy as np, pandas as pd

G = {'__file__': str(HERE / 'a_official.py'), '__name__': 'x'}; sys.argv = ['x', FFP, DTBP]
exec(open(HERE / 'a_official.py').read().split("res = {'每年末")[0], G)
A_OLD = G['A_OLD']; COST = 0.002
M = {'__file__': str(HERE / 'a_memory_backfill.py'), '__name__': 'x'}; sys.argv = ['x', FFP, DTBP]
exec(open(HERE / 'a_memory_backfill.py').read().split("res = {'说明'")[0], M)
run, fmt, me_of = M['run'], M['fmt'], M['me_of']

PKG = ROOT / 'incoming/grok-csi300-sectors-20261123/dailies/from-publish-date'
L = {'csi300': A_OLD['csi300']}
for i in range(8, 18):
    code = f'H00{900 + i}'; f = next(PKG.glob(f'{code}*.csv'))
    d = pd.read_csv(f, dtype={'tradeDate': str}); d.index = pd.to_datetime(d['tradeDate']); d = d[d['close'] > 0]
    assert d.index[0] >= pd.Timestamp('2007-07-02'), (code, d.index[0])
    L[code] = d['close'].loc[:'2015-12-31']
lvl = pd.DataFrame(L).loc['2005-01-01':'2015-12-31']
lvl = lvl.reindex(A_OLD.loc['2005-01-01':'2015-12-31'].index).ffill().where(lambda x: x.notna())
for c in lvl.columns:                                  # 发布日之前不补
    if c != 'csi300': lvl[c] = lvl[c].where(lvl.index >= L[c].index[0])
me = me_of(lvl)

res = {'说明': '第 45 行；前 3 等分，对沪深300 全收益的月超额，年化点数；净 = 扣单边 0.2% × 换手；决策月到 2015-11',
       '每年末可参选个数（含沪深300）': {str(d.year): int((me.shift(1) / me.shift(12) - 1).loc[d].notna().sum()) for d in me.index if d.month == 12}}
O = {}
for seg, (a, b) in {'新段 2008-07 → 2011-07（第 43 行没看过）': ('2008-07', '2011-07'), '旧段 2011-08 → 2015-11（已看过，只作一致性）': ('2011-08', '2015-11'),
                    '全段 2008-07 → 2015-11': ('2008-07', '2015-11')}.items():
    o = run(me, 'csi300', a, b); O[seg] = o; res[seg] = {('R0 12−1' if k == '12−1' else 'S1 上月涨幅'): fmt(v) for k, v in o.items()}
new, full = O['新段 2008-07 → 2011-07（第 43 行没看过）'], O['全段 2008-07 → 2015-11']
t = lambda x: float(x.mean() / x.std(ddof=1) * math.sqrt(len(x)))
s1n, r0n = new['上月涨幅']['net'].mean(), new['12−1']['net'].mean()
res['判据'] = {'新段 S1 净超额 > 0': bool(s1n > 0), '新段 S1 > R0': bool(s1n > r0n), '全段 S1 净超额 t ≥ 2': bool(t(full['上月涨幅']['net']) >= 2),
             '全段 S1 t': round(t(full['上月涨幅']['net']), 2)}
res['判据']['结论'] = '把“A 股名额用上月涨幅”列为 v6 候选' if all(v for k, v in res['判据'].items() if k.startswith(('新段', '全段 S1 净'))) \
    else '维持 12−1，A 股名额继续记 0；上月涨幅不进 v6'
json.dump(res, open(ROOT / 'results/v6-preflight/a-memory-csi300.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
