"""Owner 看板 v4 摘要图：v4 做了两件事——换成真实交易条件（E2 → E2 新口径），在它上面试四个各改一处的微调（都没过）。
数字来自已登记的 results/v4/r5/candidate-gate.csv（指数池）与 v4 体检报告；只读设计期。
用法：python results/v5/diag/board/v4_fold.py docs/assets/owner-board/b9-v4.png
"""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[4]
import pandas as pd, numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'font.size': 11.5})
INK, MUTED, GOOD, BAD, BLUE = '#151b26', '#5d6676', '#15803d', '#c2410c', '#1d4ed8'
g = pd.read_csv(ROOT / 'results/v4/r5/candidate-gate.csv'); g = g[g.pool == 'index'].set_index('arm')
TARGET = {'T1': ('pp_rebound', '反弹'), 'T2': ('pp_correction', '回调'), 'T3': ('pp_bull', '牛市'), 'T4': ('pp_bull', '牛市')}
NAME = {'T1': 'T1 转折点换挡', 'T2': 'T2 按市场状态分配速度', 'T3': 'T3 空位当天补', 'T4': 'T4 加美股行业、港股分类'}
fig = plt.figure(figsize=(13, 5.5))
ax = fig.add_axes([.04, .08, .30, .66])
bars = [('E2（v3.1 冻结）\n理想条件', 25.1, '#9ca3af'), ('E2 新口径\n真实条件 · 指数池', 24.9, BLUE), ('E2 新口径\n真实条件 · 可交易池', 8.7, BLUE)]
for i, (n, v, c) in enumerate(bars):
    ax.bar(i, v, color=c, width=.62, alpha=1 if i < 2 else .45, zorder=2)
    ax.text(i, v + .6, f'{v:.1f}%', ha='center', fontsize=12, weight='bold', color=INK)
ax.axhline(15.6, color=INK, ls='--', lw=1.2); ax.text(2.45, 15.9, '基准 15.6%', ha='right', va='bottom', fontsize=10, color=INK)
ax.set_xticks(range(3), [b[0] for b in bars], fontsize=10); ax.set_ylim(0, 30); ax.set_ylabel('设计期年化 %', color=MUTED)
for s in ('top', 'right'): ax.spines[s].set_visible(False)
ax.grid(axis='y', alpha=.22); ax.set_axisbelow(True)
ax.set_title('① 换成真实交易条件', loc='left', fontsize=12.5, weight='bold', color=INK, pad=10)
# 右：四个微调的过关格
bx = fig.add_axes([.40, .08, .58, .66]); bx.axis('off'); bx.set_xlim(0, 10); bx.set_ylim(0, 5.4)
bx.set_title('② 在 E2 新口径上各改一处：三条都要过，没有一个过', loc='left', fontsize=12.5, weight='bold', color=INK, pad=10)
cols = [(3.0, '前五年超额'), (4.75, '后五年超额'), (6.5, '瞄准的行情'), (8.55, '结果')]
for x, t in cols: bx.text(x, 5.05, t, ha='center', fontsize=10.5, color=MUTED, weight='bold')
b0 = g.loc['B0']
for r, t in enumerate(['T1', 'T2', 'T3', 'T4']):
    y = 4.2 - r * 1.05; row = g.loc[t]
    bx.text(0.0, y, NAME[t], va='center', fontsize=11, color=INK, weight='bold')
    d1 = (row.ann_excess_s1 - b0.ann_excess_s1) * 100; d2 = (row.ann_excess_s2 - b0.ann_excess_s2) * 100
    col, lab = TARGET[t]; d3 = row[col] - b0[col]
    for x, v, ok, txt in ((3.0, d1, d1 > 0, f'{d1:+.1f}'), (4.75, d2, d2 > 0, f'{d2:+.1f}'), (6.5, d3, d3 > 0, f'{lab} {d3:+.1f}')):
        bx.add_patch(FancyBboxPatch((x - .78, y - .34), 1.56, .68, boxstyle='round,pad=0.02,rounding_size=0.12',
                                    fc='#e8f5ed' if ok else '#fdeee6', ec='none'))
        bx.text(x, y, txt.replace('-', '−'), ha='center', va='center', fontsize=11, weight='bold', color=GOOD if ok else BAD)
    bx.text(8.55, y, '没过', ha='center', va='center', fontsize=11.5, weight='bold', color=BAD)
bx.text(0, -.2, '格子是相对 E2 新口径的变化（百分点）：超额是每年多赚几个点；瞄准的行情是该行情所有月份相对基准的超额之和。绿 = 变好，橙 = 变差。', fontsize=9.5, color=MUTED)
fig.text(.04, .99, 'v4 做了两件事：换成真实条件后，E2 在能排名的池子里几乎不变、在当年真能买到的池子里只剩 8.7%；四个微调都没过关', fontsize=14, weight='bold', color=INK, va='top')
fig.text(.04, .915, '设计期 2006–2015，人民币、含分红、扣成本。v4 最终版 = E2 新口径（一处都没改）。', fontsize=10.5, color=MUTED, va='top')
fig.savefig(sys.argv[1], dpi=200, bbox_inches='tight', facecolor='white')
