"""D38 第 26 行 T7：防守放在哪里。French 49 行业 + 全市场，1955–2026，单边 0.2%，选不满或缩下来的仓位放国库券。
用法：python -I scripts/preflight/topn_defense.py <49_Industry_Portfolios.csv> <DTB3.csv> results/v6-preflight
"""
import sys, json, pathlib
import numpy as np, pandas as pd
src = open(pathlib.Path(__file__).with_name('topn_longhist.py')).read().split("ALL = list")[0]
g = {}; exec(src, g)
X, mom, above, rf, COST = g['X'], g['mom'], g['above'], g['rf'], g['COST']
OUT = pathlib.Path(sys.argv[3]); ALL = list(X.columns); INDS = [c for c in ALL if c != 'MKT']

def run(N, mode):
    wp = pd.Series(0.0, index=ALL); out = []; port = []
    mvol_hist = []
    for i in range(12, len(X) - 1):
        t, nx = X.index[i], X.index[i + 1]
        sc = mom.loc[t, ALL]; ok = sc.notna()
        if mode == 'gate': ok &= above.loc[t, ALL]
        if mode == 'absmom': ok &= sc > (1 + rf.loc[:t].iloc[-12:]).prod() - 1
        if mode == 'mktgate' and not above.loc[t, 'MKT']: ok &= sc > 0
        pick = sc[ok].nlargest(N).index
        w = pd.Series(0.0, index=ALL); w[pick] = 1 / N
        if mode == 'volscale':
            mvol_hist.append(X.loc[t, 'MKT'])
            if len(port) >= 6:
                target = np.std(mvol_hist) ; real = np.std(port[-6:])
                w = w * min(1.0, target / real) if real > 0 else w
        wf = 1 - w.sum(); tr = (w - wp).abs().sum(); wp = w
        rr = float((w * X.loc[nx].fillna(0)).sum() + wf * rf.loc[nx] - COST * tr)
        port.append(float(X.loc[nx, pick].mean()) if len(pick) else 0.0)        # 未缩放的前 N 收益，用来量实现波动
        out.append((nx, rr, tr))
    return pd.DataFrame(out, columns=['t', 'r', 'tr']).set_index('t')

br = above[INDS].mean(axis=1).shift(1)
SEGS = {'1955–1979': ('1955', '1979'), '1980–1999': ('1980', '1999'), '2000–2015': ('2000', '2015'), '2016–2026': ('2016', '2026')}
def stats(d):
    o = {}
    for k, (a, b) in {'全程': ('1955', '2026'), **SEGS}.items():
        x = d.loc[a:b, 'r']; nav = (1 + x).cumprod()
        o[k] = dict(年化=round(float(nav.iloc[-1] ** (12 / len(x)) - 1) * 100, 2), 最低剩=round(float(100 * (nav / nav.cummax()).min()), 1))
    x = d.loc['1955':].join(br.rename('b')).dropna(); q1, q2 = x['b'].quantile([1 / 3, 2 / 3])
    for k, msk in {'宽度低': x['b'] <= q1, '宽度中': (x['b'] > q1) & (x['b'] < q2), '宽度高': x['b'] >= q2}.items():
        o[f'{k}_月均收益年化'] = round(float(x.loc[msk, 'r'].mean() * 1200), 1)
    o['每年换手_倍'] = round(float(d['tr'].mean() * 12), 2); return o
res = {'一直持有全市场': stats(pd.DataFrame({'r': X['MKT'], 'tr': 0.0}).iloc[13:])}
for N in (3, 5):
    for mode, name in (('none', '不设防守'), ('gate', '①逐个均线门槛'), ('absmom', '②绝对动量'), ('mktgate', '③只在全市场层面'), ('volscale', '④整体按波动缩放')):
        res[f'前{N} {name}'] = stats(run(N, mode))
json.dump(res, open(OUT / 'topn-defense.json', 'w'), ensure_ascii=False, indent=1)
rows = {k: {'全程': f"{v['全程']['年化']}% / {v['全程']['最低剩']}", **{s: f"{v[s]['年化']}% / {v[s]['最低剩']}" for s in SEGS},
            '宽度低/中/高': f"{v['宽度低_月均收益年化']}/{v['宽度中_月均收益年化']}/{v['宽度高_月均收益年化']}", '换手': v['每年换手_倍']} for k, v in res.items()}
print(pd.DataFrame(rows).T.to_string())
