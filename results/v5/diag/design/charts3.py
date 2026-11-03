"""v5 备忘设计稿第 3 版的图。m15：尺子铺满后的结构（dense.json）；m16：传导前沿（propagate.json）。只读诊断输出，不算收益。
用法：python results/v5/diag/design/charts3.py docs/assets/v5-memo
"""
import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[4]
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, BLUE, GREY, BAD, GOOD, TEAL = '#151b26', '#5d6676', '#1d4ed8', '#9ca3af', '#c2410c', '#15803d', '#0d9488'
OUT = pathlib.Path(sys.argv[1]); D = ROOT / 'results/v5/diag/design'
def title(fig, t, s):
    h = fig.get_figheight()
    fig.text(.06, 1 + .42 / h, t, fontsize=14.5, weight='bold', color=INK)
    fig.text(.06, 1 + .12 / h, s, fontsize=10.5, color=MUTED)
# m15
d = json.loads((D / 'dense.json').read_text()); G = d['尺子']; x = np.arange(len(G))
NAME = {'csi300': '沪深300', 'hsi': '恒生', 'spx': '标普500'}; LS = {'csi300': '-', 'hsi': '--', 'spx': ':'}
fig, (ax, bx) = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={'width_ratios': [1.6, 1]})
for k, (pc, col, lab) in enumerate((('PC1', BLUE, '水平：所有尺子同向'), ('PC2', BAD, '斜率：短尺子减长尺子'), ('PC3', TEAL, '弯曲：两端减中段'))):
    for m in NAME:
        ax.plot(x, d[f'{m}·速度']['形状'][pc], color=col, ls=LS[m], lw=2.2, label=lab if m == 'csi300' else None)
ax.axhline(0, color=GREY, lw=.8)
tick = [i for i, g in enumerate(G) if g in (3, 5, 10, 19, 40, 74, 117, 250)]
ax.set_xticks(tick, [f'{G[i]}天' for i in tick]); ax.set_xlabel('尺子（3–250 天，按对数等距铺 28 把）', color=MUTED)
ax.set_ylabel('权重', color=MUTED); ax.grid(axis='y', alpha=.22); ax.legend(frameon=False, fontsize=10, loc='lower left')
ax.text(len(G) - 1, .36, '实线 沪深300 · 虚线 恒生 · 点线 标普500', ha='right', fontsize=9.5, color=MUTED)
ax.set_title('① 三个综合量的形状，三个市场几乎重合', loc='left', fontsize=12.5, weight='bold', color=INK)
ms = list(NAME); xx = np.arange(3)
v = [d[f'{m}·速度']['等效独立尺子'] for m in ms]; a = [d[f'{m}·加速度']['等效独立尺子'] for m in ms]
bx.bar(xx - .2, v, .4, color=BLUE, label='速度', zorder=2); bx.bar(xx + .2, a, .4, color=BAD, label='加速度（逐把尺子做差）', zorder=2)
for i in range(3):
    bx.text(i - .2, v[i] + .3, f'{v[i]:.1f}', ha='center', fontsize=10, color=BLUE, weight='bold')
    bx.text(i + .2, a[i] + .3, f'{a[i]:.1f}', ha='center', fontsize=10, color=BAD, weight='bold')
bx.set_xticks(xx, [NAME[m] for m in ms]); bx.set_ylim(0, 13); bx.set_ylabel('28 把尺子相当于几把独立的', color=MUTED)
bx.grid(axis='y', alpha=.22); bx.legend(frameon=False, fontsize=10, loc='upper left')
bx.set_title('② 噪音在加速度上，不在尺子多', loc='left', fontsize=12.5, weight='bold', color=INK)
title(fig, '尺子铺满不会多出噪音：28 把尺子的速度只说三件事，形状在三个市场一样',
      '设计期 ≤2015，只用价格。每把尺子按自己的噪音折算（÷ 波动 × √天数）。前三个综合量解释速度变化的 83–88%；逐把尺子的加速度只能解释 42–49%。')
fig.tight_layout(); fig.savefig(OUT / 'm15-dense.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# m16
r = json.loads((D / 'propagate.json').read_text()); k = [e['k'] for e in r]
fig, (ax, bx) = plt.subplots(1, 2, figsize=(13, 4.6))
ax.plot(k, [e['前沿_见顶'] for e in r], color=BAD, lw=2.8, marker='o', label='后来见顶（8 次）')
ax.plot(k, [e['前沿_回调'] for e in r], color=BLUE, lw=2.8, marker='o', label='后来只是回调（161 次）')
ax.axhline(.5, color=GREY, lw=1, ls='--'); ax.text(40, .52, '一半尺子转负', ha='right', fontsize=9.5, color=MUTED)
for e in r: ax.text(e['k'], e['前沿_回调'] - .07, f"{e['未揭晓_回调']}", ha='center', fontsize=8.5, color=BLUE)
ax.text(40, .8, '蓝色数字 = 那天结局还没揭晓、仍在统计里的回调个数', fontsize=9, color=MUTED, ha='right')
ax.set_ylim(0, .85); ax.set_xlabel('最短尺子转负之后第几天', color=MUTED); ax.set_ylabel('速度已转负的尺子比例', color=MUTED)
ax.grid(axis='y', alpha=.22); ax.legend(frameon=False, fontsize=10, loc='upper left', bbox_to_anchor=(0, .92))
ax.set_title('① 见顶时一路往长尺子传；回调停在三成后退回', loc='left', fontsize=12.5, weight='bold', color=INK)
bx.plot(k, [e['AUC_前沿'] for e in r], color=TEAL, lw=2.8, marker='o', label='传导前沿')
bx.plot(k, [e['AUC_回撤'] for e in r], color=GREY, lw=2.8, marker='o', label='已经跌了多少')
bx.axhline(.5, color=GREY, lw=1, ls='--'); bx.text(40, .52, '0.5 = 抛硬币', ha='right', fontsize=9.5, color=MUTED)
bx.annotate('当天：价格看不出，\n传导已经看得出', xy=(0, .67), xytext=(1.5, .42), fontsize=10, color=TEAL, weight='bold',
            arrowprops=dict(arrowstyle='->', color=TEAL))
bx.set_ylim(.4, 1); bx.set_xlabel('最短尺子转负之后第几天', color=MUTED); bx.set_ylabel('分得开的程度（AUC，越高越好）', color=MUTED)
bx.grid(axis='y', alpha=.22); bx.legend(frameon=False, fontsize=10, loc='lower right')
bx.set_title('② 传导的新信息集中在最开始', loc='left', fontsize=12.5, weight='bold', color=INK)
title(fig, '你说的“传导”数据上看得到：见顶时转负一路传向长尺子，回调传到三成就退回',
      '设计期 ≤2015，沪深300、恒生、标普500，创新高后最短尺子首次转负的 169 次。每天只统计结局还没揭晓的事件。见顶只有 8 次，只能当方向。')
fig.tight_layout(); fig.savefig(OUT / 'm16-propagate.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
