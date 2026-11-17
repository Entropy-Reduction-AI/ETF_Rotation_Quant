"""D38 第 16 行 M1：五腿合成行情仿真。基准、增强基准（K2A 美股 50%）、A2、R1 在同一批路径上比较。
腿：0 A 股、1 美股、2 港股、3 10 年国债、4 黄金。噪声来自项目池 2008-08-13 → 2015-12-31 五腿成对日收益（标准化，20 日块抽样），只取波动和相关。
行情段落和股票漂移沿用 sim.py（港股取 A 与美股平均）；防守资产两种假设见登记。
用法：python scripts/preflight/msim.py results/v6-preflight [路径数]
"""
import sys, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'scripts/preflight'))
OUT = pathlib.Path(sys.argv[1]); NP = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
sys.argv = [sys.argv[0], '/tmp/simout', str(NP)]
import numpy as np, pandas as pd, sim
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets
D, COST, CASH, SEED = 252, 0.001, 0.02, 20261117
VOL = np.array([None, None, None, 0.04, 0.15], dtype=object)   # 国债、黄金的年化波动；股票腿用段落设定

m = Markets(load_spec()).get('index', t4=False, allow_substitute=True)
P = m.signal.loc['2008-08-13':'2015-12-31', ['csi300', 'spx', 'ndx100', 'hsi', 'cgb-10y', 'gold']].dropna()
J = pd.DataFrame({'A': P['csi300'], 'US': (P['spx'] + P['ndx100']) / 2, 'HK': P['hsi'], 'B': P['cgb-10y'], 'G': P['gold']})
L = np.log1p(J); Z = ((L - L.mean()) / L.std()).values
rng = np.random.default_rng(SEED)

def draw(n):
    k = int(np.ceil(n / 20)); st = rng.integers(0, len(Z) - 20, size=(NP, k))
    return Z[(st[:, :, None] + np.arange(20)).reshape(NP, -1)[:, :n]]

def build(segs, helps):
    out = []
    for days, ma, mu, va, vu in segs:
        e = draw(days); e = e - e.mean(axis=1, keepdims=True)
        down = (ma + mu) / 2 < 0
        if helps: b, g = (0.04, 0.06) if down else (0.03, 0.03)
        else: b, g = (0.0, 0.0) if down else (0.025, 0.02)
        mus = np.array([ma, mu, (ma + mu) / 2, b, g]); vols = np.array([va, vu, (va + vu) / 2, 0.04, 0.15])
        out.append(np.log1p(mus) / D + e * vols / np.sqrt(D))
    return np.concatenate(out, axis=1)

def five(lr, mode):
    """A2（mode='fixed'：五腿各 1/5，跌破均线的腿去现金）或 R1（'realloc'：过门槛的腿等分，单腿 ≤ 2/5）。"""
    n, T, K = lr.shape; R = np.expm1(lr); lvl = np.exp(np.cumsum(lr, axis=1))
    cd = (1 + CASH) ** (1 / D) - 1
    w = np.full((n, K), 0.2); wc = np.zeros(n); v = np.ones(n); navs = np.empty((n, T)); turn = np.zeros(n); expo = np.empty((n, T))
    for t in range(T):
        g = 1 + (w * R[:, t]).sum(1) + wc * cd
        v = v * g; w = w * (1 + R[:, t]) / g[:, None]; wc = wc * (1 + cd) / g
        if t >= 210 and t % 21 == 0:
            ma = lvl[:, t - 210:t + 1:21].mean(axis=1)               # 10 个月末均值（含本月末）
            ok = lvl[:, t] > ma
            if mode == 'fixed': tgt = 0.2 * ok
            else:
                cnt = ok.sum(1, keepdims=True); tgt = np.where(ok, np.minimum(0.4, 1 / np.maximum(cnt, 1)), 0.0)
            tr = np.abs(tgt - w).sum(1); v = v * (1 - COST * tr); turn += tr; w = tgt; wc = 1 - tgt.sum(1)
        navs[:, t] = v; expo[:, t] = w[:, :3].sum(1)
    return navs, expo, turn

def summarize(navs, bm_ann, a, b, yrs):
    seg = navs[:, a - 1:b] / navs[:, a - 1:a]; ann = seg[:, -1] ** (1 / yrs) - 1
    low = 100 * (seg / np.maximum.accumulate(seg, axis=1)).min(axis=1)
    return dict(最低剩_万_中位=round(float(np.median(low)), 1), 最低剩_万_p10=round(float(np.percentile(low, 10)), 1),
                比基准年化_中位=round(float(np.median(ann - bm_ann)) * 100, 2),
                比基准年化_p10=round(float(np.percentile(ann - bm_ann, 10)) * 100, 2))

rows = []
for helps in (True, False):
    for name, segs in sim.SCEN.items():
        rng = np.random.default_rng(SEED)
        lr = build(segs, helps); T = lr.shape[1]; a, b = sim.WARM, T; yrs = (b - a) / D
        bm = sim.run(lr[:, :, :2], s_us=0.30, kind='K0')[0]
        bm_seg = bm[:, a - 1:b] / bm[:, a - 1:a]; bm_ann = bm_seg[:, -1] ** (1 / yrs) - 1
        ek = sim.run(lr[:, :, :2], s_us=0.50, kind='K2A', bond=np.expm1(lr[:, :, 3]))
        out = {'基准': bm, '增强基准(K2A美50)': ek[0], 'A2': five(lr, 'fixed')[0]}
        r1 = five(lr, 'realloc'); out['R1'] = r1[0]
        for k, nv in out.items():
            rows.append(dict(防守资产='帮忙' if helps else '不帮忙', 行情=name, 结构=k, **summarize(nv, bm_ann, a, b, yrs)))
        rows[-1]['R1每年换手_倍'] = round(float(np.median(r1[2]) / (T / D)), 2)
        rows[-1]['R1平均股票仓位'] = round(float(np.median(r1[1][:, a:].mean(1))), 2)
d = pd.DataFrame(rows); d.to_csv(OUT / 'msim.csv', index=False)
print(d.to_string(index=False))
