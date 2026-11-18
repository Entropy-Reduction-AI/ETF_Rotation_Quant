"""D38 第 37 行 S2：按市场选防守用法（A 股：按票减仓；美股：分级要求），另测 10% 机动（A 股确认紧张时移到美股）。
用法：python scripts/preflight/topn_permarket.py <49_Industry_Portfolios.csv> <DTB3.csv>
"""
import sys, json, pathlib
HERE = pathlib.Path(__file__).resolve().parent
g = {'__file__': str(HERE / 'topn_tiered.py'), '__name__': 'x'}
exec(open(HERE / 'topn_tiered.py').read().split("res = {'设计期'")[0], g)
import numpy as np, pandas as pd
A_LVL, US_RMB, bond, cash, stats = g['A_LVL'], g['US_RMB'], g['bond'], g['cash'], g['stats']
def summarize(ret, ta, tu):
    st = stats(ret, '2006-01-01', {'2006–10': ('2006', '2010'), '2011–15': ('2011', '2015')}); s = (1 + ret.loc['2006':]).cumprod()
    for k, (x0, x1) in {'2008': ('2007-06-01', '2009-12-31'), '2015': ('2015-01-01', '2015-12-31')}.items():
        x = s.loc[x0:x1]; pk = s.loc[:x.index[-1]].cummax().loc[x.index]; st[f'最低剩_{k}'] = round(float(100 * (x / pk).min()), 1)
    yr = s.resample('YE').last().pct_change(); yr.iloc[0] = s.resample('YE').last().iloc[0] - 1
    st['最差一年'] = round(float(yr.min()) * 100, 1); st['每年换手_倍'] = round((ta + tu) / 2 / (len(s) / 252), 2); return st
res = {}
for N in (2, 3):
    a, ta, la = g['g']['slot_vote'](A_LVL, 'csi300', N, ['均线', '宽度', 'TRIN'], bond, cash)
    u, tu, _ = g['slot_tier'](US_RMB, 'SPX', N, bond, cash)
    res[f'前{N} A 按票减仓 + 美 分级要求'] = summarize(0.5 * a + 0.5 * u, ta, tu)
    # 10% 机动：A 股名额 ≥2 票的月份，次日起 A 40% / 美 60%
    st = (la >= 2).astype(float); st.index = pd.DatetimeIndex(st.index)
    wa = pd.Series(np.where(st.reindex(a.index, method='ffill').shift(1).fillna(0) > 0, 0.4, 0.5), a.index)
    sw = wa.diff().abs().fillna(0) * 2 * 0.002
    ret = wa * a + (1 - wa) * u - sw
    r = summarize(ret, ta, tu); r['机动生效月数'] = int((la.loc['2006':] >= 2).sum()); res[f'前{N} 同上 + 10% 机动'] = r
for f_, keys in (('topn-tiered.json', ('前2 分级要求', '前3 分级要求')), ('topn-vote.json', ('前2 三票', '前3 三票', '前2 两票：均线+宽度', '前2 ③只在母指数层面', '参照 基准（美股30%）', '参照 增强基准（K2A 美股50%）'))):
    o = json.load(open(f'results/v6-preflight/{f_}')); o = o.get('设计期', o.get('设计期 2006–2015（美股 + A 股各半，单边 0.2%）'))
    for k in keys: res[f'参照 {k}' if not k.startswith('参照') else k] = o[k]
json.dump(res, open('results/v6-preflight/topn-permarket.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(pd.DataFrame(res).T.to_string())
