"""v5 研究备忘的图。只读已登记的设计期净值（≤2015-12-31）和 holdings.py 的持仓诊断。
用法：python results/v5/diag/memo/charts.py docs/assets/v5-memo
"""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'axes.grid': True, 'grid.alpha': .22, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, GOOD, BAD = '#151b26', '#5d6676', '#15803d', '#c2410c'
COL = {'E2 新口径': '#1d4ed8', 'v5 最终版': '#c2410c', '基准': '#111827', 'A1': '#9ca3af'}
OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
D = ROOT / 'results'
def rd(p): return pd.read_csv(p, index_col=0, parse_dates=True).iloc[:, 0].astype(float)
def bm():
    cache = D / 'v5/diag/memo/benchmark.csv'
    if cache.exists(): return rd(cache)
    from src.v4.r5.design import benchmark_returns
    s = benchmark_returns().loc[:'2015-12-31']; s.to_frame('bm').to_csv(cache, float_format='%.12g'); return s
B = bm()
def nets(pool):
    return {'E2 新口径': rd(D / f'v4/r5/design/B0/{pool}/net.csv'), 'v5 最终版': rd(D / f'v5/design/P2/{pool}/net.csv'),
            '基准': B, 'A1': rd(D / f'v4/r5/design/A1/{pool}/net.csv')}
POOL = {'index': '指数池（能排名的）', 'tradable': '可交易池（当年真能买到的）'}
def cagr(r): r = r.loc['2006':]; return (1 + r).prod() ** (252 / len(r)) - 1
def title(fig, t, s):
    h = fig.get_figheight()
    fig.text(.06, 1 + .42 / h, t, ha='left', va='bottom', fontsize=14.5, weight='bold', color=INK)
    fig.text(.06, 1 + .12 / h, s, fontsize=10.5, color=MUTED, va='bottom')

# m1 净值与回撤
fig, axs = plt.subplots(2, 2, figsize=(13, 6.6), sharex=True, gridspec_kw={'height_ratios': [3, 1.2]})
for j, pool in enumerate(('index', 'tradable')):
    ax, bx = axs[0, j], axs[1, j]; ends = []
    for k, r in nets(pool).items():
        r = r.loc['2006':]; n = (1 + r).cumprod()
        lw = 2.6 if k in ('E2 新口径', 'v5 最终版') else 1.5
        ax.plot(n.index, n.values, color=COL[k], lw=lw, zorder=3 if lw > 2 else 2)
        bx.plot(n.index, (n / n.cummax() - 1) * 100, color=COL[k], lw=1.6 if lw > 2 else 1.0)
        ends.append((n.iloc[-1], k, cagr(r)))
    ends.sort(); last = -1
    for v, k, c in ends:
        y = max(v, last + 0.55) if last > 0 else v; last = y
        ax.text(pd.Timestamp('2016-02-01'), y, f'{k} {c*100:.1f}%', color=COL[k], fontsize=10.5, weight='bold', va='center')
    ax.set_title(POOL[pool], loc='left', fontsize=12.5, weight='bold', color=INK)
    bx.set_ylabel('回撤 %', color=MUTED); bx.set_ylim(-70, 2)
    ax.set_xlim(pd.Timestamp('2006-01-01'), pd.Timestamp('2017-06-01'))
axs[0, 0].set_ylabel('净值（2006 年初 = 1）', color=MUTED)
title(fig, '指数池里 v5 远落后于 E2 新口径；可交易池里 v5 更好，但仍不如简单的 A1',
      '设计期 2006–2015，人民币、含分红、扣成本；图右是十年年化。下排是从高点回落的幅度。')
fig.tight_layout(); fig.savefig(OUT / 'm1-nav.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)

# m2 逐年：v5 − E2
fig, axs = plt.subplots(1, 2, figsize=(13, 4.4), sharey=True)
for ax, pool in zip(axs, ('index', 'tradable')):
    n = nets(pool); y = {k: (1 + r.loc['2006':]).groupby(r.loc['2006':].index.year).prod() - 1 for k, r in n.items()}
    d = (y['v5 最终版'] - y['E2 新口径']) * 100
    ax.bar(d.index, d.values, color=[GOOD if v > 0 else BAD for v in d.values], width=.7, zorder=2)
    for x, v in d.items(): ax.text(x, v + (2 if v >= 0 else -2), ('0' if abs(v) < .5 else f'{v:+.0f}'.replace('-', '−')), ha='center', va='bottom' if v >= 0 else 'top', fontsize=10, color=INK)
    ax.axhline(0, color=INK, lw=.9); ax.set_xticks(d.index); ax.set_xticklabels([str(x)[2:] for x in d.index])
    ax.set_title(POOL[pool], loc='left', fontsize=12.5, weight='bold', color=INK); ax.grid(axis='x', visible=False)
axs[0].set_ylabel('v5 减 E2 新口径（百分点）', color=MUTED); axs[0].set_ylim(-95, 95)
title(fig, '指数池：v5 输在 2006–07 大牛市和 2008、2011、2015 的下跌；可交易池正好反过来',
      '每年收益之差，绿 = v5 多赚，橙 = v5 少赚。年份写后两位。')
fig.tight_layout(); fig.savefig(OUT / 'm2-yearly.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)

# m3 四种行情
st = {'E2 新口径': [-2.4, 27.3, 95.0, -54.0], 'v5 最终版': [-92.4, 28.2, 64.6, -38.7]}
names = ['牛市', '回调', '熊市', '反弹']; sub = ['大势涨\n本月涨', '大势涨\n本月跌', '大势跌\n本月跌', '大势跌\n本月涨']
fig, ax = plt.subplots(figsize=(10, 4.6)); x = np.arange(4); w = .36
for i, (k, vals) in enumerate(st.items()):
    xs = x + (i - .5) * w
    ax.bar(xs, vals, w, color=COL[k], zorder=2, label=k)
    for xi, v in zip(xs, vals): ax.text(xi, v + (3 if v >= 0 else -3), f'{v:+.0f}'.replace('-', '−'), ha='center', va='bottom' if v >= 0 else 'top', fontsize=10.5, color=INK)
ax.axhline(0, color=INK, lw=.9); ax.set_xticks(x); ax.set_xticklabels([f'{a}\n{b}' for a, b in zip(names, sub)])
ax.set_ylabel('相对基准的超额（百分点，按月相加）', color=MUTED); ax.grid(axis='x', visible=False)
ax.legend(frameon=False, loc='upper left', fontsize=11)
title(fig, 'v5 在牛市里少赚 90 个百分点、熊市里少躲 30 个；反弹里少输一些',
      '指数池，设计期 120 个月，按沪深300 全收益只用当时的数据分成四种行情。')
fig.tight_layout(); fig.savefig(OUT / 'm3-states.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)

# m4 持仓按大类
W = pd.read_csv(D / 'v5/diag/memo/class-weights.csv', index_col=0, parse_dates=True).loc['2006':'2015'].resample('ME').mean()
GR = [('A股', 'A 股', '#2563eb'), ('港股', '港股', '#0d9488'), ('美股', '美股', '#7c3aed'),
      ('防守', '国债、黄金', '#a3a3a3'), ('现金', '现金', '#e5e7eb'), ('其他', '其他海外、商品', '#d97706')]
def grp(prefix):
    g = {}
    for k, _, _ in GR:
        cols = {'防守': ['国债', '黄金'], '其他': ['其他海外', '商品']}.get(k, [k])
        g[k] = sum(W.get(f'{prefix}:{c}', 0) for c in cols)
    return pd.DataFrame(g)
fig, axs = plt.subplots(2, 1, figsize=(13, 6.6), sharex=True)
for ax, (prefix, lab) in zip(axs, (('E2', 'E2 新口径'), ('v5', 'v5 最终版'))):
    g = grp(prefix)
    ax.stackplot(g.index, *[g[k] * 100 for k, _, _ in GR], colors=[c for _, _, c in GR], linewidth=0)
    ax.set_ylim(0, 100); ax.set_ylabel('%', color=MUTED); ax.set_title(lab, loc='left', fontsize=12.5, weight='bold', color=COL[lab])

h = [plt.Rectangle((0, 0), 1, 1, color=c) for _, _, c in GR]
fig.legend(h, [n for _, n, _ in GR], loc='lower center', ncol=6, frameon=False, bbox_to_anchor=(.5, -.04), fontsize=11)
title(fig, 'E2 新口径：牛市满仓 A 股，弱市大量拿国债和现金；v5：牛市只有四成 A 股，弱市里仍几乎满仓风险资产',
      '指数池每月平均的实际持仓，按 v5 大类汇总；两条路径（E2 是六路）平均。')
fig.tight_layout(rect=(0, .04, 1, 1)); fig.savefig(OUT / 'm4-holdings.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)

# m5 稳健性与结构对照
R = pd.read_csv(D / 'v5/design/robustness.csv'); R = R[(R.pool == 'index') & (R.kind == 'robustness')]
lab = {'strongest-class': '只持最强的一类（A1 式）', 'fixed-budget': '固定预算（A2 式）', 'no-defense': '不设防守位',
       'lookback-10-40-90-180': '回看期短一档', 'lookback-15-50-100-200': '回看期稍短', 'lookback-30-80-150-300': '回看期长一档',
       'cost-double': '成本加倍', 'delay-1d': '晚一天成交', 'drop-best-1': '去掉最好的 1 个', 'drop-best-2': '去掉最好的 2 个',
       'drop-best-3': '去掉最好的 3 个', 'exit-8': '离场线 8%', 'exit-12': '离场线 12%'}
R = R[R.case.isin(lab)].copy(); R['name'] = R.case.map(lab); R = R.iloc[::-1]
fig, ax = plt.subplots(figsize=(10.5, 6))
y = np.arange(len(R))
ax.scatter(R.d_s1_pp, y, color='#1d4ed8', s=46, zorder=3, label='前五年 2006–10')
ax.scatter(R.d_s2_pp, y, color='#0d9488', s=46, marker='D', zorder=3, label='后五年 2011–15')
ax.axvline(0, color=INK, lw=.9)
gap = (19.6 - (-0.6))
ax.axvline(gap, color=BAD, lw=1.2, ls='--'); ax.text(gap, len(R) - .2, f'追平 E2 新口径前五年\n需要 +{gap:.0f}', color=BAD, fontsize=9.5, ha='right', va='top')
ax.set_yticks(y); ax.set_yticklabels(R.name); ax.set_xlabel('相对 v5 最终版，年化超额的变化（百分点）', color=MUTED)
ax.get_yticklabels()[list(R.case).index('strongest-class')].set_color(BAD); ax.get_yticklabels()[list(R.case).index('strongest-class')].set_weight('bold')
ax.legend(frameon=False, loc='lower right'); ax.grid(axis='y', visible=False)
title(fig, '只有“只持最强的一类”明显更好，但仍追不上 E2 新口径；其他改动影响都不大',
      '指数池，每项只改一处；只报告，不改判（预注册 §7.1）。')
fig.tight_layout(); fig.savefig(OUT / 'm5-robust.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
print('ok')
