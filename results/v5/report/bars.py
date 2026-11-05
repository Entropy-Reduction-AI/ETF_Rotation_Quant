"""每个月初买入、持有 3 年的超额柱状图（v4 体检报告 h4 的样式）。只读签收结果。
用法：python results/v5/report/bars.py
输出：docs/assets/v5-memo/m24-v51-bars.png（设计期，v5.1 两个池子）
      docs/assets/v5-oneshot/o6-bars.png（检验段，E2 新口径和 A1，能排名的池子）
"""
import pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[3]
import pandas as pd, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False, 'axes.spines.right': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, GOOD, BAD = '#151b26', '#5d6676', '#16a34a', '#ea580c'
R = ROOT / 'results'
def title(fig, t, s):
    h = fig.get_figheight(); fig.text(.06, 1 + .42 / h, t, fontsize=14.5, weight='bold', color=INK); fig.text(.06, 1 + .12 / h, s, fontsize=10.5, color=MUTED)
def panel(ax, x, y, name, color):
    ax.bar(x, y, width=22, color=[GOOD if v > 0 else BAD for v in y])
    ax.axhline(0, color=INK, lw=.9); ax.grid(axis='both', alpha=.18)
    ax.set_title(name, loc='left', fontsize=12.5, weight='bold', color=color)
    ax.text(.99, .95, f'跑赢 {(y > 0).mean() * 100:.0f}% 的起点 · 中位数 {np.median(y):+.1f}', transform=ax.transAxes, ha='right', va='top', fontsize=11, weight='bold', color=INK)
    ax.set_ylabel('每年多（少）赚\n（百分点）', color=MUTED, fontsize=10.5)
# 设计期：v5.1 两个池子，持有 3 年，对基准
fig, axs = plt.subplots(2, 1, figsize=(13, 6.6), sharex=True)
for ax, pool, nm, col in zip(axs, ('index', 'tradable'), ('U-指数池（能排名的）', 'U-可交易池（当年真能买到的）'), ('#1d4ed8', '#0d9488')):
    A = pd.read_csv(R / f'v5.1/report/anystart-{pool}.csv', parse_dates=['start'])
    g = A[(A.yrs == 3) & (A.vs == '基准')]
    panel(ax, g.start, g['diff'].values, nm, col)
title(fig, 'v5.1 什么时候买入决定了结果：能排名的池子 95% 的月份都赢；能买到的池子只有 2008 年中以前和 2012 年下半年买入才赢',
      '每根柱子 = 从那个月初买入、持有 3 年，v5.1 比基准每年多（少）赚的百分点。设计期 2006–2015。')
fig.tight_layout(); fig.savefig(ROOT / 'docs/assets/v5-memo/m24-v51-bars.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# 检验段：E2 新口径、A1，能排名的池子，持有 3 年
O = R / 'v5/oneshot/index'
fig, axs = plt.subplots(2, 1, figsize=(13, 6.6), sharex=True)
for ax, arm, nm, col in zip(axs, ('E2-B0', 'A1'), ('E2 新口径（入围）', 'A1 双动量（对照）'), ('#1d4ed8', '#d97706')):
    w = pd.read_csv(O / arm / 'criterion-1-windows.csv', parse_dates=['start']); w = w[w.months == 36]
    panel(ax, w.start, w.excess.values * 100, nm, col)
title(fig, '检验段每个月初买入、持有 3 年：E2 新口径只有 2020 年底到 2021 年买入才赢（先躲过 2022 年下跌）；A1 一半一半',
      '每根柱子 = 从那个月初买入、持有 36 个月，比基准每年多（少）赚的百分点。能排名的池子，2016-01 到 2023-10 共 94 个起点。')
fig.tight_layout(); fig.savefig(ROOT / 'docs/assets/v5-oneshot/o6-bars.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
w = pd.read_csv(O / 'E2-B0/criterion-1-windows.csv', parse_dates=['start']); w = w[w.months == 36]
print(w[w.excess > 0][['start', 'excess']].to_string())
