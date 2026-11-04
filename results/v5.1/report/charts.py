"""v5.1 设计期报告的图（读已签收的结果文件，不重跑）。m18 中国指数池净值和回撤；m19 别的市场扣费前后；m20 换手来源。
用法：python results/v5.1/report/charts.py docs/assets/v5-memo
"""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
import pandas as pd, numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False, 'axes.spines.right': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, BLUE, GREY, BAD, GOOD, A1C, TEAL = '#151b26', '#5d6676', '#1d4ed8', '#9ca3af', '#c2410c', '#15803d', '#d97706', '#0d9488'
OUT = pathlib.Path(sys.argv[1]); R = ROOT / 'results'
def title(fig, t, s):
    h = fig.get_figheight(); fig.text(.06, 1 + .42 / h, t, fontsize=14.5, weight='bold', color=INK); fig.text(.06, 1 + .12 / h, s, fontsize=10.5, color=MUTED)
def net(f, col='net'):
    d = pd.read_csv(f, parse_dates=[0], index_col=0); return d[col] if col in d else d.iloc[:, 0]
# m18
v = net(R / 'v5.1/design/index/daily.csv').loc['2006':'2015']
b0 = net(R / 'v4/r5/design/B0/index/net.csv').loc['2006':'2015']; a1 = net(R / 'v4/r5/design/A1/index/net.csv').loc['2006':'2015']
bm = net(R / 'v5.1/design/benchmark.csv', 'benchmark').loc['2006':'2015']
df = pd.DataFrame({'v5.1': v, 'E2 新口径': b0, 'A1': a1, '基准': bm}).fillna(0); nav = (1 + df).cumprod()
cols = {'v5.1': BAD, 'E2 新口径': BLUE, 'A1': A1C, '基准': GREY}
fig, (ax, bx) = plt.subplots(2, 1, figsize=(13, 6.4), sharex=True, gridspec_kw={'height_ratios': [2.2, 1]})
for c in nav:
    ax.plot(nav.index, nav[c], color=cols[c], lw=2.8 if c == 'v5.1' else 1.8, label=c)
    ax.text(nav.index[-1] + pd.Timedelta(days=40), nav[c].iloc[-1], f'{c} {nav[c].iloc[-1]:.1f} 倍', color=cols[c], fontsize=10.5, weight='bold' if c == 'v5.1' else None, va='center')
    dd = nav[c] / nav[c].cummax() - 1; bx.plot(dd.index, dd * 100, color=cols[c], lw=2.2 if c == 'v5.1' else 1.4)
ax.set_ylabel('净值（2006 年初 = 1）', color=MUTED); ax.grid(axis='y', alpha=.22); ax.set_xlim(nav.index[0], nav.index[-1] + pd.Timedelta(days=500))
bx.set_ylabel('回撤 %', color=MUTED); bx.grid(axis='y', alpha=.22); bx.axhline(0, color=GREY, lw=.8)
bx.text(nav.index[-1] + pd.Timedelta(days=40), -26, 'v5.1 最深 −26%', color=BAD, fontsize=10, weight='bold'); bx.text(nav.index[-1] + pd.Timedelta(days=40), -62, '基准最深 −65%', color=GREY, fontsize=10)
ax.set_title('① 净值', loc='left', fontsize=12.5, weight='bold', color=INK); bx.set_title('② 回撤', loc='left', fontsize=12.5, weight='bold', color=INK)
title(fig, '中国设计期：v5.1 年化 30%、最深回撤 −26%，是项目到目前最好的一版',
      '能排名的池子（U-指数），2006–2015，扣费后。基准 = 70% 沪深300 + 15% 纳指100 + 15% 标普500。E2 新口径、A1 引用 v4 账本。')
fig.tight_layout(); fig.savefig(OUT / 'm18-v51-china.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# m19
rows = []
for k, f in (('v5.1', 'v51'), ('E2 式', 'e2')):
    d = pd.read_csv(R / f'v5.1/other-market/{f}/daily.csv', parse_dates=['date']); yrs = len(d) / 252
    rows.append((k, ((1 + d.gross).prod() ** (1 / yrs) - 1) * 100, ((1 + d.net).prod() ** (1 / yrs) - 1) * 100, (d.buy + d.sell).sum() / yrs))
sm = pd.read_csv(R / 'v5.1/other-market/summary.csv'); sm = sm[sm.segment == 'full'].set_index('case')
rows += [('A1', None, sm.at['A1', 'cagr'] * 100, None), ('基准 G', None, sm.at['BM-G', 'cagr'] * 100, None)]
fig, ax = plt.subplots(figsize=(13, 4.4)); y = np.arange(len(rows))[::-1]
for yi, (k, g, n, t) in zip(y, rows):
    if g is not None:
        ax.barh(yi + .18, g, .34, color='#cbd5e1', zorder=2); ax.text(g + .15, yi + .18, f'扣费前 {g:.1f}%', va='center', fontsize=10, color=MUTED)
    col = BAD if k == 'v5.1' else (GREY if k == '基准 G' else BLUE if k == 'E2 式' else A1C)
    ax.barh(yi - .18 if g is not None else yi, n, .34, color=col, zorder=2); ax.text(n + .15, (yi - .18) if g is not None else yi, f'扣费后 {n:.1f}%' + (f'　每年双边换手 {t:.0f} 倍' if t else ''), va='center', fontsize=10.5, color=col, weight='bold')
ax.set_yticks(y, [r[0] for r in rows]); ax.set_xlim(0, 13); ax.set_xlabel('年化 %（2003-07 → 2026-09）', color=MUTED); ax.grid(axis='x', alpha=.22)
title(fig, '换到美国 ETF：v5.1 扣费前就没赢基准，换手又吃掉近 6 个点，只剩 1.3%',
      '别的市场检验（G 池：美国、发达市场、新兴市场 ETF + IEF、GLD，美元，每腿成本 0.1%）。规则一个数都没改。')
fig.tight_layout(); fig.savefig(OUT / 'm19-v51-gpool.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# m20
SRC = ['第一层档位', '周度替换', '前沿离场', '换防守', '换市场', '硬闸门']
NM = {'第一层档位': '第一层仓位档位（满仓 ↔ 半仓 ↔ 离场）', '周度替换': '第二层每周换人', '前沿离场': '单只前沿过半', '换防守': '国债、黄金、现金之间切换', '换市场': '换市场', '硬闸门': '硬闸门'}
CL = {'第一层档位': BAD, '周度替换': A1C, '前沿离场': TEAL, '换防守': GREY, '换市场': BLUE, '硬闸门': '#7c3aed'}
fig, ax = plt.subplots(figsize=(13, 3.6)); labs = []
for i, (f, nm) in enumerate((('g', '美国 ETF（G 池）'), ('index', '中国指数池'), ('tradable', '中国可交易池'))):
    t = pd.read_csv(R / f'v5.1/turnover/{f}.csv'); n = t.year.nunique(); a = t[t.source.isin(SRC)].groupby('source').turnover_one_way.sum() / n
    left = 0
    for s in SRC:
        ax.barh(i, a.get(s, 0), left=left, color=CL[s], label=NM[s] if i == 0 else None, zorder=2, edgecolor='white')
        if a.get(s, 0) > 1.2: ax.text(left + a.get(s, 0) / 2, i, f'{a.get(s, 0):.0f}', ha='center', va='center', color='white', fontsize=10, weight='bold')
        left += a.get(s, 0)
    ax.text(left + .3, i, f'合计单边 {left:.0f} 倍/年', va='center', fontsize=10.5, color=INK, weight='bold'); labs.append(nm)
ax.set_yticks(range(3), labs); ax.set_xlim(0, 34); ax.set_xlabel('每年单边换手（本金的倍数）', color=MUTED); ax.grid(axis='x', alpha=.22)
ax.legend(frameon=False, ncol=3, fontsize=9.5, loc='upper center', bbox_to_anchor=(.5, -.28))
title(fig, '换手的一大半来自第一层仓位在满仓和半仓之间来回切，其次是第二层每周换人',
      '设计期（中国 2006–2015）和别的市场（美国 2003–2026），按来源拆开的单边换手；双边换手和成本约为它的两倍。')
fig.tight_layout(); fig.savefig(OUT / 'm20-v51-turnover.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
