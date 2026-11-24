"""v6 预注册附表 B 的两张图（只读 results/v6-preflight/v6-appendix-b.json，设计期 ≤ 2015）。
用法：python -I scripts/preflight/charts_appendix_b.py docs/assets/v6-prereg
p3：2006–15 收益拆分瀑布（BM-主 → 仓位差 → 等权倾斜 → 挑选 → 防守 → 成本 → v6 净）；
p4：两个名额逐年确认紧张的月数 + 平均股票仓位（小多图，同一纵轴各自一张）。
样式与 charts_prereg.py 相同。
"""
import sys, json, pathlib
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
D = json.load(open(ROOT / 'results/v6-preflight/v6-appendix-b.json', encoding='utf-8'))
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, GREY, TEAL, AMBER, BLUE = '#151b26', '#5d6676', '#9ca3af', '#0d9488', '#d97706', '#1f5fd6'


def title(fig, t, s):
    h = fig.get_figheight()
    fig.text(.04, 1 + .42 / h, t, fontsize=14.5, weight='bold', color=INK)
    fig.text(.04, 1 + .12 / h, s, fontsize=10.5, color=MUTED)


# ---------- p3 waterfall ----------
Y, P = D['年化'], '2006–15'
dec = D['收益拆分（每年比 BM-主 多几个点）']
steps = [('仓位差\n（美股 60%）', dec['仓位差'][P]), ('等权倾斜', dec['等权倾斜'][P]), ('挑选\n（前 3）', dec['挑选'][P]),
         ('防守', dec['防守'][P]), ('成本', dec['成本'][P])]
bm, net = Y['BM-主（70/15/15）'][P], Y['v6 净（单边 0.2%，每日固定 60/40）'][P]
fig, ax = plt.subplots(figsize=(11, 4.4))
x = 0
ax.bar(x, bm, color=GREY, width=.62); ax.text(x, bm + .3, f'{bm:.1f}%', ha='center', color=INK, weight='bold')
lvl = bm
for i, (lb, v) in enumerate(steps, 1):
    c = TEAL if v >= 0 else AMBER
    ax.bar(i, v, bottom=lvl, color=c, width=.62, edgecolor='white', linewidth=2)
    ax.plot([i - 1.31, i - .31], [lvl, lvl], color=GREY, lw=.8, ls=':')
    ax.text(i, max(lvl, lvl + v) + .3, f'{v:+.1f}'.replace('-', '−'), ha='center', color=c, weight='bold', fontsize=12.5 if abs(v) > 3 else 11.5)
    lvl += v
n = len(steps) + 1
ax.plot([n - 1.31, n - .31], [lvl, lvl], color=GREY, lw=.8, ls=':')
ax.bar(n, net, color=INK, width=.62); ax.text(n, net + .3, f'{net:.1f}%', ha='center', color=INK, weight='bold')
ref = D['参照：A 股一级行业按发布日截断（第 47 行口径）v6 净，每日固定 60/40'][P]
ax.hlines(ref, n - .42, n + .42, color=BLUE, lw=2.2); ax.text(n + .46, ref, f'只用当年已发布\n的指数 {ref:.1f}%', va='center', color=BLUE, fontsize=10)
ax.set_xticks(range(n + 1), ['BM-主'] + [s[0] for s in steps] + ['v6 净'])
ax.set_ylim(8, 20); ax.set_xlim(-.6, n + 1.3); ax.set_ylabel('每年 %', color=MUTED); ax.grid(axis='y', alpha=.2)
title(fig, f'设计期 v6 净每年 {net:.1f}%，比 BM-主多 {net - bm:.1f} 点：挑选 {dec["挑选"][P]:+.1f} 抵掉了仓位差 {dec["仓位差"][P]:+.1f} 和成本 {dec["成本"][P]:+.1f}'.replace('-', '−'),
      '2006–2015，只用 ≤ 2015 的数据；一级行业用回填点位（Owner 2026-11-24）；绿 = 加分，橙 = 减分；蓝线 = 一级行业按发布日截断时的 v6 净（第 47 行）')
fig.savefig(OUT / 'p3-decompose.png', dpi=150, bbox_inches='tight'); plt.close(fig)

# ---------- p4 signal profile ----------
A, U = D['信号画像：A 股名额']['逐年'], D['信号画像：美股名额']['逐年']
yrs = [int(y) for y in A]
fig, axs = plt.subplots(1, 2, figsize=(11, 3.9), sharey=True)
for ax, S, nm, avg in ((axs[0], A, 'A 股名额（40 万）', D['信号画像：A 股名额']['紧张时平均股票仓位']),
                        (axs[1], U, '美股名额（60 万）', D['信号画像：美股名额']['紧张时平均股票仓位'])):
    m = [S[str(y)]['紧张月数'] for y in yrs]
    ax.bar(yrs, m, color='#64748b', width=.7)
    for y, v in zip(yrs, m):
        if v:
            ax.text(y, v + .25, str(v), ha='center', color=INK, fontsize=10.5, weight='bold')
    ax.set_title(f'{nm}：紧张时平均拿 {avg:.0%} 股票', loc='left', fontsize=12, color=INK, weight='bold')
    ax.set_xticks([2006, 2008, 2010, 2012, 2014]); ax.set_ylim(0, 13.5); ax.grid(axis='y', alpha=.2)
axs[0].set_ylabel('确认紧张的月数（每年）', color=MUTED)
title(fig, '紧张集中在 2008 年，A 股 2010–12 年又连着三年紧张；同样确认紧张，A 股只拿约四分之一股票，美股拿一半以上',
      '设计期 2006–2015；≥ 2 票为确认紧张；A 股把握 p 年末从 0.31 升到 0.57，美股始终约 0.997（逐年见附表 B 明细）')
fig.savefig(OUT / 'p4-signals.png', dpi=150, bbox_inches='tight'); plt.close(fig)
print('ok')
