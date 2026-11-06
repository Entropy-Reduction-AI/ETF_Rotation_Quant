"""《v5.1 换手深挖》的宽度和深度：每类调仓占多少、各自正确率；每年、每种行情下动得多不多、做得对不对。
只读 v51_trades.csv、v51_sells.csv（同目录）、签收的状态文件和基准成分（ref.pkl）。
行情按基准（BM-主 = 70% 沪深300 + 15% 纳指100 + 15% 标普500，每日加权近似）逐月机械划分：
  r6 = 过去 6 个月累计收益；
  反转：r6 与 3 个月前的 r6 符号相反，且两者相差 ≥ 10 个百分点；
  牛市：不是反转，且 r6 ≥ +10%；熊市：不是反转，且 r6 ≤ −10%；其余为震荡。
用法：python results/v5/report/turnover_depth.py <ref.pkl>  → turnover_depth.json
"""
import sys, json, pathlib
import pandas as pd, numpy as np
ROOT = pathlib.Path(__file__).resolve().parents[3]; REP = ROOT / 'results/v5/report'
ref = pd.read_pickle(sys.argv[1]); ref.index = pd.to_datetime(ref.index)
bm = (.7 * ref.H00300 + .15 * ref.XNDX + .15 * ref.SP500TR).fillna(0)
m = (1 + bm).groupby(bm.index.to_period('M')).prod()
r6 = m.rolling(6).apply(np.prod, raw=True) - 1
r6_3 = r6.shift(3)
reg = pd.Series('震荡', index=m.index)
reg[r6 >= .10] = '牛市'; reg[r6 <= -.10] = '熊市'
rev = (np.sign(r6) != np.sign(r6_3)) & ((r6 - r6_3).abs() >= .10)
reg[rev] = '反转'
reg = reg[(reg.index >= pd.Period('2006-01', 'M')) & (reg.index <= pd.Period('2026-09', 'M'))]
NAME = {'换市场': '换市场', '整体进场': '重新进场', '整体离场': '全部离场', '加仓档': '半仓加到满仓', '减仓档': '满仓降到半仓',
        '周度换掉': '每周换人', '单只离场': '单只止损', '防守换品种': '防守换品种', '其他': '零星调整', '换人（其他）': '零星调整'}
t = pd.read_csv(REP / 'v51_trades.csv', parse_dates=['日期'])
t['类'] = t.类别.map(NAME).fillna('零星调整'); t['月'] = t.日期.dt.to_period('M'); t['行情'] = t.月.map(reg); t['年'] = t.日期.dt.year
t['对'] = t.VA20 > 0; t['净'] = t.VA20 - t.成本
yrs = {'设计期': 10.0, '检验段': 2611 / 252}
out = {'regime_months': {s: reg[(reg.index.year < 2016) if s == '设计期' else (reg.index.year >= 2016)].value_counts().to_dict() for s in yrs},
       'regime_by_month': {str(k): v for k, v in reg.items()}}
# 宽度：每类占比、正确率、每笔净期望
br = {}
for s, g in t.groupby('段'):
    n = len(g); y = yrs[s]
    br[s] = {k: dict(每年=round(len(h) / y, 1), 占比=round(len(h) / n * 100), 正确率=round(h.对.mean() * 100), 每笔净期望=round(h.净.mean(), 3),
                     做对平均=round(h[h.对].VA20.mean(), 3) if h.对.any() else None, 做错平均=round(h[~h.对].VA20.mean(), 3) if (~h.对).any() else None)
             for k, h in g.groupby('类')}
    br[s]['合计'] = dict(每年=round(n / y, 1), 占比=100, 正确率=round(g.对.mean() * 100), 每笔净期望=round(g.净.mean(), 3))
out['breadth'] = br
# 深度：逐年笔数（按类）、正确率
yr = t.groupby(['年', '类']).size().unstack(fill_value=0)
out['yearly_counts'] = {int(k): v for k, v in yr.T.to_dict().items()}
out['yearly_hit'] = {int(k): round(v * 100) for k, v in t.groupby('年').对.mean().items()}
# 每种行情：每月笔数、正确率、每笔净期望（不含零星调整）
core = t[t.类 != '零星调整']
dep = {}
for s, g in core.groupby('段'):
    months = out['regime_months'][s]
    dep[s] = {r: dict(月数=int(months.get(r, 0)), 每月笔数=round(len(h) / max(1, months.get(r, 0)), 1), 正确率=round(h.对.mean() * 100),
                      每笔净期望=round(h.净.mean(), 3), 每月净=round(h.净.sum() / max(1, months.get(r, 0)), 2))
              for r, h in g.groupby('行情')}
out['by_regime'] = dep
# 来回打脸（整体离场后 14 天内回来）按行情
sl = pd.read_csv(REP / 'v51_sells.csv', parse_dates=['状态日'])
sl['行情'] = sl.状态日.dt.to_period('M').map(reg); sl['净'] = sl.减仓价值 - sl.一来一回成本
ws = {}
for s, g in sl.groupby('段'):
    months = out['regime_months'][s]
    ws[s] = {r: dict(每月减仓=round(len(h) / max(1, months.get(r, 0)), 2), 两周内回来=round((h.回来天数 <= 14).mean() * 100), 每次净=round(h.净.mean(), 3))
             for r, h in g.groupby('行情')}
out['sells_by_regime'] = ws
# 共振减仓按市场
def states(seg):
    if seg == '设计期':
        d = pd.read_csv(ROOT / 'results/v5.1/design/index/daily.csv', parse_dates=['date']).set_index('date')
    else:
        d = pd.read_csv(ROOT / 'results/v5/oneshot/index/v5.1-对照/state.csv', parse_dates=['date']).set_index('date')
    return d.market.ffill()
res = sl[sl.周中 & sl.整体离场].copy(); mk = {}
for s, g in res.groupby('段'):
    st = states(s); prevm = st.shift(1)
    g = g.assign(市场=[prevm.get(d, None) for d in g.状态日])
    mk[s] = {str(k): dict(次数=len(h), 正确率=round((h.减仓价值 > 0).mean() * 100), 每次净=round(h.净.mean(), 3), 合计=round(h.净.sum(), 1)) for k, h in g.groupby('市场')}
out['resonance_by_market'] = mk
(REP / 'turnover_depth.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
for k in ('regime_months', 'breadth', 'by_regime', 'sells_by_regime', 'resonance_by_market'):
    print(k, json.dumps(out[k], ensure_ascii=False)[:1800])
print('hit by year', out['yearly_hit'])
