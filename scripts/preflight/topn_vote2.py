"""D38 第 34 行 M3：确认后才减仓。复用 topn_vote.py 的定义。
用法：python scripts/preflight/topn_vote2.py <49_Industry_Portfolios.csv> <DTB3.csv>
"""
import sys, json, pathlib
HERE = pathlib.Path(__file__).resolve().parent
src = open(HERE / 'topn_vote.py').read().split("res = {'设计期")[0]
g = {'__file__': str(HERE / 'topn_vote.py'), '__name__': 'x'}; exec(src, g)
import pandas as pd
res = {'设计期': {}}
for N in (2, 3):
    res['设计期'][f'前{N} 三票，≥2 票才减仓'] = g['system'](N, ['均线', '宽度', 'TRIN'], confirm=True)[0]
    res['设计期'][f'前{N} 两票（均线+宽度），两票同时才减仓'] = g['system'](N, ['均线', '宽度'], confirm=True)[0]
old = json.load(open('results/v6-preflight/topn-vote.json'))
D0 = old['设计期 2006–2015（美股 + A 股各半，单边 0.2%）']
for k in ('前2 三票', '前2 两票：均线+宽度', '前2 ③只在母指数层面', '参照 基准（美股30%）'): res['设计期'][k] = D0[k]
lt = "\n".join(open(HERE / "topn_vote.py").read().split("# 长历史")[1].split("dfn = json.load")[0].split("\n")[1:])
f = dict(g); exec(lt, f)
L = {}
for N in (3, 5):
    L[f'前{N} 两票同时成立才转国库券'] = f['lst'](f['run_vote'](N, ['均线', '宽度', 'confirm']))
L0 = old['长历史 French 49 行业 1955–2026（年化 / 最低剩，单边 0.2%）']
for k in ('一直持有全市场', '前3 不设防守', '前3 ③只在全市场层面', '前5 ③只在全市场层面', '前3 两票：均线+宽度'): L[k] = L0[k]
res['长历史'] = L
json.dump(res, open('results/v6-preflight/topn-vote2.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(pd.DataFrame(res['设计期']).T.to_string()); print(pd.DataFrame(L).T.to_string())
