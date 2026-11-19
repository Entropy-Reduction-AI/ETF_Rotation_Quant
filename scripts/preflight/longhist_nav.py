"""预测表第 3 版用：美国 49 行业长历史四条净值（全市场、前 3 不设防守、前 3 逐个门槛、前 3 按把握调节），只导出，不改规则。
用法：python scripts/preflight/longhist_nav.py <49_Industry_Portfolios.csv> <DTB3.csv>
"""
import sys, pathlib
HERE = pathlib.Path(__file__).resolve().parent; FFP, DTBP = sys.argv[1], sys.argv[2]
import pandas as pd
P = {'__file__': str(HERE / 'topn_phi.py'), '__name__': 'x'}; sys.argv = ['x', FFP, DTBP, 'results/v6-preflight']
exec(open(HERE / 'topn_phi.py').read().split("res = {}")[0], P)
f = {'__file__': str(HERE / 'topn_longhist.py')}; exec(open(HERE / 'topn_longhist.py').read().split("ALL = list")[0], f)
X = f['X'].loc['1926-07':]; rf = f['rf'].reindex(X.index).fillna(0)
out = {'全市场': X['MKT'].loc['1955':]}
for mode, nm in (('none', '前3 不设防守'), ('phi', '前3 按把握调节')):
    out[nm] = P['monthly'](X, 'MKT', 3, mode, rf, '1955')[0]['r']
out['前3 逐个均线门槛'] = f['run'](3, True, list(f['X'].columns))['r'].loc['1955':]
nav = (1 + pd.DataFrame(out).dropna()).cumprod(); nav.to_csv('results/v6-preflight/longhist-nav.csv')
print(nav.iloc[-1].round(1))
