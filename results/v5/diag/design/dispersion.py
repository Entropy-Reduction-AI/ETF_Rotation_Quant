"""描述统计：设计期内 A 股十个行业、宽基之间的分化有没有随时间变大（不算任何策略收益；只用 ≤2015-12-31）。
每年：行业日收益两两相关的平均值；每月末过去 12 个月行业涨幅的“最强减最弱”和标准差，按年平均。
用法：python results/v5/diag/design/dispersion.py results/v5/diag/design
"""
import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets
out = pathlib.Path(sys.argv[1]); m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
SEC = [c for c in m.signal.columns if c.startswith('allshare-')]
r = m.signal.loc['2005':'2015-12-31', SEC]
corr = {y: round(g.corr().values[np.triu_indices(len(SEC), 1)].mean(), 3) for y, g in r.groupby(r.index.year)}
lr = np.log1p(r.fillna(0)); tw = np.expm1(lr.rolling(250).sum()).resample('ME').last().loc['2006':]
spread = (tw.max(1) - tw.min(1)).groupby(tw.index.year).mean().round(3).to_dict()
sd = tw.std(1).groupby(tw.index.year).mean().round(3).to_dict()
res = dict(行业数=len(SEC), 两两相关=corr, 十二个月涨幅最强减最弱=spread, 十二个月涨幅标准差=sd)
(out / 'dispersion.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str)); print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
