"""一次性检验报告的图（只读 Reviewer 签收的 results/v5/oneshot，不重跑）。
用法：python results/v5/report/charts.py docs/assets/v5-oneshot
"""
import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[3]
import pandas as pd, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False, 'axes.spines.right': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, BLUE, GREY, BAD, GOOD, A1C, TEAL, PURP = '#151b26', '#5d6676', '#1d4ed8', '#9ca3af', '#c2410c', '#15803d', '#d97706', '#0d9488', '#7c3aed'
OUT = pathlib.Path(sys.argv[1]); O = ROOT / 'results/v5/oneshot'
def title(fig, t, s):
    h = fig.get_figheight(); fig.text(.06, 1 + .42 / h, t, fontsize=14.5, weight='bold', color=INK); fig.text(.06, 1 + .12 / h, s, fontsize=10.5, color=MUTED)
def net(p): return pd.read_csv(p, parse_dates=['date']).set_index('date').net
S = pd.DataFrame({'E2 新口径': net(O / 'index/E2-B0/net.csv'), 'A1': net(O / 'index/A1/net.csv'), 'A2': net(O / 'index/A2/net.csv'),
                  'v5.1（对照）': net(O / 'index/v5.1-对照/net.csv'), '基准': net(O / 'benchmarks/BM-main/net.csv'), '沪深300': net(O / 'benchmarks/HS300/net.csv')}).fillna(0)
cols = {'E2 新口径': BLUE, 'A1': A1C, 'A2': TEAL, 'v5.1（对照）': BAD, '基准': INK, '沪深300': GREY}
# o1 净值和回撤
nav = (1 + S).cumprod()
fig, (ax, bx) = plt.subplots(2, 1, figsize=(13, 6.4), sharex=True, gridspec_kw={'height_ratios': [2.2, 1]})
for c in nav:
    lw = 3 if c == 'E2 新口径' else (2.2 if c == '基准' else 1.6)
    ls = '--' if c == '沪深300' else '-'
    ax.plot(nav.index, nav[c], color=cols[c], lw=lw, ls=ls)
    y = nav[c].iloc[-1]; off = {'A1': -.08, '基准': .06, 'A2': 0, 'E2 新口径': -.06, '沪深300': .06}.get(c, 0)
    ax.text(nav.index[-1] + pd.Timedelta(days=40), y + off, f'{c} {y:.2f} 倍', color=cols[c], fontsize=10.5, va='center', weight='bold' if c in ('E2 新口径', '基准') else None)
    dd = nav[c] / nav[c].cummax() - 1; bx.plot(dd.index, dd * 100, color=cols[c], lw=lw * .7, ls=ls)
ax.axhline(1, color=GREY, lw=.8); ax.set_ylabel('净值（2016 年初 = 1）', color=MUTED); ax.grid(axis='y', alpha=.22); ax.set_xlim(nav.index[0], nav.index[-1] + pd.Timedelta(days=620))
bx.set_ylabel('回撤 %', color=MUTED); bx.grid(axis='y', alpha=.22)
ax.set_title('① 净值', loc='left', fontsize=12.5, weight='bold', color=INK); bx.set_title('② 回撤', loc='left', fontsize=12.5, weight='bold', color=INK)
title(fig, '2016–2026：E2 新口径年化 3.0%，基准 8.7%；回撤最浅，但钱几乎没涨',
      '能排名的池子（过关判定用这个），扣费后，2016-01-04 → 2026-09-30。基准 = 70% 沪深300 + 15% 纳指100 + 15% 标普500，人民币全收益。')
fig.tight_layout(); fig.savefig(OUT / 'o1-nav.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# o2 逐年超额
yr = (1 + S).groupby(S.index.year).prod() - 1
ex = yr[['E2 新口径', 'A1']].sub(yr['基准'], axis=0) * 100
fig, ax = plt.subplots(figsize=(13, 4.4)); x = np.arange(len(ex)); w = .38
for j, (c, col) in enumerate((('E2 新口径', BLUE), ('A1', A1C))):
    b = ax.bar(x + (j - .5) * w, ex[c], w, color=col, label=c)
    if c == 'E2 新口径':
        for xi, v in zip(x, ex[c]): ax.text(xi - .5 * w, v + (1 if v >= 0 else -1), f'{v:+.0f}', ha='center', va='bottom' if v >= 0 else 'top', fontsize=9.5, color=BLUE, weight='bold')
ax.axhline(0, color=INK, lw=.9); ax.set_xticks(x); ax.set_xticklabels([f'{y}' + ('\n(到 9 月)' if y == 2026 else '') for y in ex.index]); ax.set_ylabel('比基准多（少）赚，百分点', color=MUTED); ax.grid(axis='y', alpha=.22); ax.legend(frameon=False, loc='lower left')
title(fig, 'E2 新口径 11 年里只赢了 2018、2022 两个熊市年（和 2026 前九个月）；大涨的年份都输',
      '每年 E2 新口径（蓝）、A1（橙）减基准的收益。能排名的池子，扣费后。')
fig.tight_layout(); fig.savefig(OUT / 'o2-yearly.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# o3 E2 的仓位：风险、国债、黄金、现金
h = pd.read_csv(O / 'index/E2-B0/held.csv', parse_dates=['date']).set_index('date')
bond = [c for c in h if c.startswith('cgb') or '债' in c]
E = pd.DataFrame({'现金': h.cash, '国债': h[bond].sum(axis=1), '黄金': h['gold']}); E['风险资产'] = 1 - E.sum(axis=1)
Ey = E.groupby(E.index.year).mean() * 100
fig, ax = plt.subplots(figsize=(13, 4.6)); bottom = np.zeros(len(Ey))
for c, col in (('风险资产', BLUE), ('国债', '#93c5fd'), ('黄金', '#fcd34d'), ('现金', '#e5e7eb')):
    ax.bar(Ey.index, Ey[c], bottom=bottom, color=col, label=c, width=.7)
    if c == '风险资产':
        for xi, v in zip(Ey.index, Ey[c]): ax.text(xi, 6, f'{v:.0f}%', ha='center', color='white', fontsize=10, weight='bold')
    bottom += Ey[c].values
bx = ax.twinx(); bx.plot(yr.index, yr['基准'] * 100, color=INK, lw=2, marker='o'); bx.set_ylabel('基准当年收益 %（黑线）', color=INK); bx.spines['right'].set_visible(True); bx.axhline(0, color=GREY, lw=.6, ls=':')
ax.set_ylabel('E2 新口径平均仓位 %', color=MUTED); ax.set_ylim(0, 100); ax.legend(frameon=False, ncol=4, loc='upper left', bbox_to_anchor=(0, -.08))
title(fig, '为什么输：国债常年占三成，基准大涨的 2019 年风险资产只有 46%',
      'E2 新口径每年平均持仓结构（能排名的池子）。“涨幅 ÷ 波动”的尺子让波动小的国债排到股票前面。')
fig.tight_layout(); fig.savefig(OUT / 'o3-exposure.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# o4 设计期 vs 检验期：相对基准的年化超额
H = json.loads((ROOT / 'results/v5.1/report/health.json').read_text())['index']
cg = lambda r: ((1 + r).prod() ** (252 / len(r)) - 1) * 100
cur = {k: cg(S[k]) - cg(S['基准']) for k in ('E2 新口径', 'A1', 'A2', 'v5.1（对照）')}
d = {'E2 新口径': (H['E2 新口径']['S1'] - 22.3, H['E2 新口径']['S2'] - 9.4), 'A1': (H['A1']['S1'] - 22.3, H['A1']['S2'] - 9.4),
     'A2': (14.5 - 22.3, 3.5 - 9.4), 'v5.1（对照）': (H['v5.1']['S1'] - 22.3, H['v5.1']['S2'] - 9.4)}
fig, ax = plt.subplots(figsize=(13, 4.6)); x = np.arange(4); w = .26; names = list(d)
for j, (lab, col) in enumerate((('2006–2010（设计期）', '#cbd5e1'), ('2011–2015（设计期）', '#93c5fd'), ('2016–2026（一次性检验）', BLUE))):
    vals = [d[k][j] if j < 2 else cur[k] for k in names]
    ax.bar(x + (j - 1) * w, vals, w, color=col, label=lab)
    for xi, v in zip(x, vals): ax.text(xi + (j - 1) * w, v + (.5 if v >= 0 else -.5), f'{v:+.1f}', ha='center', va='bottom' if v >= 0 else 'top', fontsize=9.5, color=INK if j == 2 else MUTED, weight='bold' if j == 2 else None)
ax.axhline(0, color=INK, lw=.9); ax.set_xticks(x); ax.set_xticklabels(names); ax.set_ylabel('相对基准的年化超额，百分点', color=MUTED); ax.grid(axis='y', alpha=.22); ax.legend(frameon=False, loc='lower left')
title(fig, '设计期的优势没有延续：四个策略到 2016 年以后全部跑输基准',
      '能排名的池子，扣费后。每组三根柱 = 前五年、后五年、一次性检验段，各自相对同期基准的年化超额。')
fig.tight_layout(); fig.savefig(OUT / 'o4-decay.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# o5 每个起点持有 5 年
fig, ax = plt.subplots(figsize=(13, 4.2))
for a, c, lw in (('E2-B0', BLUE, 2.6), ('A1', A1C, 1.8), ('A2', TEAL, 1.6)):
    w5 = pd.read_csv(O / f'index/{a}/criterion-1-windows.csv', parse_dates=['start']); w5 = w5[w5.months == 60]
    ax.plot(w5.start, w5.excess * 100, color=c, lw=lw, label={'E2-B0': 'E2 新口径', 'A1': 'A1', 'A2': 'A2'}[a])
ax.axhline(0, color=INK, lw=.9); ax.grid(axis='y', alpha=.22); ax.set_ylabel('持有 5 年的年化超额，百分点', color=MUTED); ax.legend(frameon=False)
title(fig, '任何一个月初买入 E2 新口径、持有 5 年，都没有跑赢基准（70 个起点，0 个赢）',
      '横轴 = 买入月份（2016-01 到 2021-10），纵轴 = 持有 60 个月相对基准每年多（少）赚多少。能排名的池子。')
fig.tight_layout(); fig.savefig(OUT / 'o5-anystart.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
print(ex.round(1).to_string()); print({k: round(v, 1) for k, v in cur.items()}); print(Ey.round(0).to_string())
