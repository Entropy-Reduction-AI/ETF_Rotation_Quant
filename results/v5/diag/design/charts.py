"""v5 备忘第 1、2 节的图。m9：E2 输掉三格的两个原因；m10：冠军赛与 E2 的事前画像。都只用信号层面的目标持仓。
用法：python results/v5/diag/design/charts.py docs/assets/v5-memo
"""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[4]
import pandas as pd, numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, BLUE, GREY, BAD, A1C = '#151b26', '#5d6676', '#1d4ed8', '#9ca3af', '#c2410c', '#d97706'
OUT = pathlib.Path(sys.argv[1]); D = ROOT / 'results/v5/diag/design'
yr = pd.read_csv(D / 'e2-targets-yearly.csv', header=[0, 1], index_col=0)
a1 = pd.read_csv(D / 'a1-picks-yearly.csv', index_col=0)
def title(fig, t, s):
    h = fig.get_figheight()
    fig.text(.06, 1 + .42 / h, t, fontsize=14.5, weight='bold', color=INK)
    fig.text(.06, 1 + .12 / h, s, fontsize=10.5, color=MUTED)
# m9
fig, (ax, bx) = plt.subplots(1, 2, figsize=(13, 4.6))
x = np.arange(len(yr)); ys = [str(v) for v in yr.index]
ax.bar(x - .2, yr[('tradable', 'cash')] * 100, .4, color=BAD, label='当年真能买到的池子', zorder=2)
ax.bar(x + .2, yr[('index', 'cash')] * 100, .4, color=GREY, label='能排名的池子', zorder=2)
for i, v in enumerate(yr[('tradable', 'elig')]): ax.text(i - .2, yr[('tradable', 'cash')].iloc[i] * 100 + 2, f'{v:.0f}', ha='center', fontsize=9, color=BAD)
ax.set_xticks(x, [y[2:] if y != '2006' else y for y in ys]); ax.set_ylim(0, 100); ax.set_ylabel('E2 闲置在现金的仓位 %', color=MUTED)
ax.set_title('① 能买的太少，每只又只给 1/N：钱大半闲着', loc='left', fontsize=12.5, weight='bold', color=INK)
ax.legend(frameon=False, fontsize=10, loc='upper right'); ax.grid(axis='y', alpha=.22)
ax.text(0, -21, '橙柱上的数字 = 当年平均有几只“跑赢现金、真能买到”的', fontsize=9.5, color=MUTED)
r_e2 = yr[('index', 'risk')] * 100; r_a1 = (1 - a1.get('cgb-10y', 0)) * 100
bx.plot(x, r_e2, color=BLUE, lw=2.6, marker='o', label='E2 新口径'); bx.plot(x, r_a1.reindex(yr.index).values, color=A1C, lw=2.6, marker='o', label='A1')
bx.axvspan(4.5, 9.5, color='#f3f4f6', zorder=0); bx.text(7, 8, '2011–15：E2 约六成，A1 近九成', ha='center', fontsize=10.5, color=INK)
bx.set_xticks(x, [y[2:] if y != '2006' else y for y in ys]); bx.set_ylim(0, 105); bx.set_ylabel('风险资产仓位 %', color=MUTED)
bx.set_title('② 后五年押得少：钱被分散到行业和国债上', loc='left', fontsize=12.5, weight='bold', color=INK)
bx.legend(frameon=False, fontsize=10, loc='lower left'); bx.grid(axis='y', alpha=.22)
title(fig, 'E2 输掉的三格，在跑之前就看得出来：可交易池的钱闲着，后五年押得太少',
      '设计期 2006–2015。规则想持有什么（月度决策、四个回看期和 N=3、5、8 平均），不含离场和成交，不算收益。A1 按其规则近似。')
fig.tight_layout(); fig.savefig(OUT / 'm9-e2-cells.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# m10
cy = pd.read_csv(D / 'champion-yearly.csv')
fig, axs = plt.subplots(1, 2, figsize=(13, 4.6), sharey=True)
GREEN = '#15803d'
for ax, pool, key, ttl in zip(axs, ('tradable', 'index'), ('风险', '防守'),
                              ('当年真能买到的池子：风险仓位（闲着的钱收回来了）', '能排名的池子：国债黄金仓位（后五年占得更多）')):
    for arm, col in (('E2', BLUE), ('冠军赛', GREEN)):
        g = cy[(cy.pool == pool) & (cy.arm == arm)].set_index('y'); x = np.arange(len(g))
        ax.plot(x, g[key], color=col, lw=2.6, marker='o', label=arm)
        ax.text(x[-1] + .25, g[key].iloc[-1], arm, color=col, fontsize=10.5, weight='bold', va='center')
    ax.set_xticks(x, [str(v)[2:] if v != 2006 else '2006' for v in g.index]); ax.set_ylim(0, 105); ax.set_xlim(-.4, 10.2); ax.grid(axis='y', alpha=.22)
    ax.set_title(ttl, loc='left', fontsize=12, weight='bold', color=INK)
axs[0].set_ylabel('目标仓位 %', color=MUTED)
title(fig, '冠军赛把可交易池里闲着的钱收回来了；代价是能排名的池子里，后五年国债占得更多',
      '设计期 2006–2015，信号层面的目标持仓，不含离场和成交，不算收益。冠军赛 = 每类一只冠军、冠军之间排名、取前 k 名平分（k=1、2、3 平均）。')
fig.tight_layout(); fig.savefig(OUT / 'm10-champion.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# m11 领先期
sp = pd.read_csv(D / 'leader-spells-250.csv', header=0, names=['spell', 'lead', 'start', 'n', 'x'], parse_dates=['start'])
NAME = {'csi300': '沪深300', 'spx': '标普500', 'hsi': '恒生'}; COLS = {'csi300': '#c2410c', 'spx': '#1d4ed8', 'hsi': '#0d9488'}
fig, ax = plt.subplots(figsize=(13, 4.4))
for i, r in sp.iterrows():
    v = r.x * 100
    ax.bar(i, v, color=COLS[r.lead], width=.7, zorder=2)
    ax.text(i, v + (2 if v >= 0 else -2), f'{v:+.0f}'.replace('-', '−'), ha='center', va='bottom' if v >= 0 else 'top', fontsize=10, color=INK)
    ax.text(i, -32, f"{r.start:%Y-%m}\n{r.n} 个月", ha='center', va='top', fontsize=8.5, color=MUTED)
from matplotlib.patches import Patch
handles = [Patch(color=c, label=NAME[k]) for k, c in COLS.items()]
ax.axhline(0, color=INK, lw=.8); ax.set_xticks([]); ax.set_ylim(-45, 100); ax.set_ylabel('这一段领先市场比三者平均多赚 %', color=MUTED)
ax.legend(handles=handles, frameon=False, fontsize=10.5, loc='upper right', title='领先的市场（按过去 12 个月涨幅）', title_fontsize=10)
ax.grid(axis='y', alpha=.22)
title(fig, '十年只有 12 段领先期，优势几乎全来自 2006–07 年 A 股那一段：只靠这三个市场，证明不了“押最强的大市场”是机制',
      '设计期 2006–2015，沪深300、恒生、标普500（人民币）。每月看过去 12 个月谁涨得最多，下个月持有它，和三者平均比；一段 = 同一个市场连续领先的月份。不扣成本，只作诊断。')
fig.tight_layout(); fig.savefig(OUT / 'm11-leader.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
