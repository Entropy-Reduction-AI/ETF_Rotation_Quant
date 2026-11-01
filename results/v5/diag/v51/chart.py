"""v5 备忘第 1 节的图 m8：E2 与 v5.1 每年的目标持仓（信号层面，不算收益）。
用法：python results/v5/diag/v51/chart.py docs/assets/v5-memo/m8-follow.png
"""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[4]
import pandas as pd, numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED = '#151b26', '#5d6676'
df = pd.read_csv(ROOT / 'results/v5/diag/v51/targets.csv', parse_dates=['date'])
df['y'] = df.date.dt.year; df['其他'] = df['其他海外'] + df['商品']
K = [('A股', 'A 股', '#2563eb'), ('港股', '港股', '#14b8a6'), ('美股', '美股', '#8b5cf6'), ('其他', '其他海外、商品', '#f59e0b'),
     ('国债', '国债', '#475569'), ('黄金', '黄金', '#ca8a04'), ('现金', '现金', '#d1d5db')]
fig, axs = plt.subplots(1, 2, figsize=(13, 4.8), sharey=True)
for ax, arm, ttl in zip(axs, ('E2', 'v5.1'), ('E2 新口径：没有上限', 'v5.1：每类最多占一半名额')):
    g = df[df.arm == arm].groupby('y')[[k for k, _, _ in K]].mean() * 100
    bot = np.zeros(len(g))
    for k, lab, col in K:
        ax.bar(g.index, g[k], bottom=bot, color=col, width=.75, label=lab, zorder=2); bot += g[k].values
    for x, v in g['A股'].items():
        if v >= 15: ax.text(x, v / 2, f'{v:.0f}', ha='center', va='center', fontsize=9.5, color='white', weight='bold')
    ax.set_title(ttl, loc='left', fontsize=12.5, weight='bold', color=INK)
    ax.set_xticks(g.index, [str(y)[2:] if y != 2006 else '2006' for y in g.index]); ax.set_ylim(0, 100)
axs[0].set_ylabel('目标仓位 %', color=MUTED)
axs[1].legend(frameon=False, ncol=1, fontsize=10, loc='center left', bbox_to_anchor=(1.01, .5))
h = fig.get_figheight()
fig.text(.06, 1 + .42 / h, '排名表每月重排，钱跟着最强的市场走；v5.1 只在 A 股独强的年份让出一部分，防守照旧', fontsize=14.5, weight='bold', color=INK)
fig.text(.06, 1 + .12 / h, '设计期 2006–2015，指数池。规则想持有什么（月路、四个回看期和 N=3、5、8 平均），不含离场和成交限制，不算收益。柱内数字 = A 股仓位。', fontsize=10.5, color=MUTED)
fig.tight_layout(); fig.savefig(sys.argv[1], dpi=200, bbox_inches='tight', facecolor='white')
