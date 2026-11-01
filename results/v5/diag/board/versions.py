"""Owner 看板第 2 节的版本进化图。数字全部来自已登记的设计期结果（2006–2015，≤2015-12-31）：
v3/E1/E2 见 docs/owner/phase2-owner-board.md 留档区与 v3.1 设计期报告；E2 新口径、A1、基准见 results/v4/r5/design；
v5 最终版见 results/v5/design/P2。用法：python results/v5/diag/board/versions.py docs/assets/owner-board/b8-versions.png
"""
import sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED = '#151b26', '#5d6676'
ROWS = [  # 名称, 指数池年化, 指数池回撤, 可交易池年化, 颜色
    ('v3 · 原规则', 12.6, -43, None, '#9ca3af'),
    ('E1 · 补全池子', 22.6, -44, None, '#9ca3af'),
    ('E2 · 加 10% 离场', 25.1, -34, 5.2, '#1d4ed8'),
    ('v4 · E2 新口径（真实条件）', 24.9, -35, 8.7, '#1d4ed8'),
]
fig, axs = plt.subplots(1, 2, figsize=(13, 4.2), gridspec_kw={'width_ratios': [1.6, 1]}, sharey=True)
y = list(range(len(ROWS)))[::-1]
ax, bx = axs
for yi, (n, a, d, t, c) in zip(y, ROWS):
    ax.barh(yi, a, color=c, height=.55, zorder=2)
    ax.text(a + .4, yi, f'{a:.1f}%', va='center', fontsize=11, weight='bold', color=INK)
    if t is not None:
        ax.plot([t], [yi], marker='o', ms=8, mfc='white', mec=INK, mew=1.6, zorder=3)
        ax.text(t, yi + .34, f'可交易 {t:.1f}%', ha='center', va='bottom', fontsize=9.5, color=MUTED)
    bx.barh(yi, d, color=c, height=.55, zorder=2)
    bx.text(d - 1, yi, f'{d}%'.replace('-', '−'), va='center', ha='right', fontsize=11, color=INK)
for v, lab, col in ((15.6, '基准 15.6%', INK), (27.0, 'A1 27.0%', '#9ca3af')):
    ax.axvline(v, color=col, lw=1.2, ls='--', zorder=1); ax.text(v, len(ROWS) - .35, lab, ha='center', va='bottom', fontsize=10, color=col)
bx.axvline(-66, color=INK, lw=1.2, ls='--'); bx.text(-66, len(ROWS) - .35, '基准 −66%', ha='center', va='bottom', fontsize=10, color=INK)
ax.set_yticks(y); ax.set_yticklabels([r[0] for r in ROWS]); ax.set_xlim(0, 31); bx.set_xlim(-75, 0)
ax.set_title('设计期年化（指数池；圆点 = 可交易池）', loc='left', fontsize=12, weight='bold', color=INK, pad=22)
bx.set_title('最大回撤（指数池）', loc='left', fontsize=12, weight='bold', color=INK, pad=22)
for a_ in axs: a_.grid(axis='x', alpha=.22); a_.set_axisbelow(True)
h = fig.get_figheight()
fig.text(.02, 1 + .42 / h, 'E2 至今仍是最好的一版：补全池子和 10% 离场是两次真改进，v4 的四个微调都没赢过它', fontsize=14.5, weight='bold', color=INK)
fig.text(.02, 1 + .12 / h, '设计期 2006–2015，人民币、含分红、扣成本。灰 = 探索阶段，蓝 = E2 系列。', fontsize=10.5, color=MUTED)
fig.tight_layout(); fig.savefig(sys.argv[1], dpi=200, bbox_inches='tight', facecolor='white')
