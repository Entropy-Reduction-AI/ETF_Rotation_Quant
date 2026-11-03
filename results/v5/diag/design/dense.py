"""诊断：尺子铺满（3–250 天，按对数等距）以后，到底多了多少信息、多了多少噪音。只用 ≤2015-12-31 的价格，不算任何组合收益，计入诊断次数 1。
速度 v_n = 最近 n 天对数涨幅 ÷ (σ·√n)（σ = 过去 250 天日波动，只用过去）——按各自的噪音折算，1 = 一个噪音单位。
加速度 a_n = (最近 n 天 − 再之前 n 天) ÷ (σ·√(2n))。
输出：相邻尺子相关系数；主成分各自解释的比例；等效独立尺子个数（参与率 = (Σλ)²/Σλ²）；前三个主成分的形状。
用法：python results/v5/diag/design/dense.py results/v5/diag/design
"""
import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets
out = pathlib.Path(sys.argv[1]); m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
ret = m.signal.loc[:'2015-12-31']
G = sorted(set(np.round(np.geomspace(3, 250, 30)).astype(int)))
res = {'尺子': [int(g) for g in G]}
for c in ('csi300', 'hsi', 'spx'):
    lr = np.log1p(ret[c].fillna(0)); sig = lr.rolling(250).std().shift(1)
    V = pd.DataFrame({n: lr.rolling(n).sum() / (sig * np.sqrt(n)) for n in G})
    A = pd.DataFrame({n: (lr.rolling(n).sum() - lr.rolling(n).sum().shift(n)) / (sig * np.sqrt(2 * n)) for n in G})
    for name, X in (('速度', V), ('加速度', A)):
        X = X.loc['2006-06-01':].dropna()
        C = X.corr().values; lam, vec = np.linalg.eigh(C); lam, vec = lam[::-1], vec[:, ::-1]
        r = dict(相邻尺子相关中位=round(float(np.median([C[i, i + 1] for i in range(len(G) - 1)])), 3),
                 前三主成分解释=[round(float(x), 3) for x in (lam[:3] / lam.sum())],
                 前三累计=round(float(lam[:3].sum() / lam.sum()), 3),
                 等效独立尺子=round(float(lam.sum() ** 2 / (lam ** 2).sum()), 1),
                 形状={f'PC{k+1}': [round(float(x * np.sign(vec[:, k].sum() or 1)), 2) for x in vec[:, k]] for k in range(3)},
                 三天与250天相关=round(float(C[0, -1]), 3))
        res[f'{c}·{name}'] = r
(out / 'dense.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
for k, v in res.items():
    if k == '尺子': print(v); continue
    print(k, {kk: vv for kk, vv in v.items() if kk != '形状'})
    for p, s in v['形状'].items(): print('   ', p, s[::4])
