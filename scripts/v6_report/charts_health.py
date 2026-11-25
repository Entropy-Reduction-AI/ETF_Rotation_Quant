"""v6 体检报告（设计期）的新图。只读冻结的附表 B 结果，设计期 ≤ 2015。
用法：python -I scripts/v6_report/charts_health.py docs/assets/v6-health
h1：预测准不准——预测表各项的事先范围（横条）、中间值（竖线）、设计期实际（实心点）、待补（虚线圈）。
数字出处：
  事先范围、中间值 —《v6 预演预测表》第 3.22 版 = 冻结预注册 §3.1（原样进入）；A 股两块按 D40-12；
  成本的预演估计 — 冻结预注册 §6 疼痛表“预演 1.0–1.1”；
  设计期实际 — results/v6-preflight/v6-appendix-b.json（Dev #377、Reviewer #375 复算差 0）：
    仓位差 = 收益拆分.仓位差；成本 = 收益拆分.成本；合计（不含仓位差）= v6 净（每月再平衡，冻结规则口径） − BM-同仓位。
样式与 scripts/preflight/charts_appendix_b.py 相同。
"""
import sys, json, pathlib
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt, matplotlib.ticker

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
D = json.load(open(ROOT / 'results/v6-preflight/v6-appendix-b.json', encoding='utf-8'))
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'axes.spines.left': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, GREY, TEAL, AMBER, BAND = '#151b26', '#5d6676', '#9ca3af', '#0d9488', '#d97706', '#dbe3ee'
P = '2006–15'
dec, Y = D['收益拆分（每年比 BM-主 多几个点）'], D['年化']
total = Y['v6 净（每月再平衡 60/40）'][P] - Y['BM-同仓位（40/30/30）'][P]

# (名称, 下限, 上限, 中间值或 None, 设计期实际或 None)
rows = [('美股名额挑选', .3, 1.5, 1.0, None),
        ('A 股名额：挑选', -.5, .5, .1, None),
        ('A 股名额：等权倾斜', -1.0, 1.0, .5, None),
        ('防守的平时保费', -1.6, -.4, -.4, None),
        ('成本（预演估计）', -1.1, -1.0, None, dec['成本'][P]),
        ('美股 60% 的仓位差', -3.0, 3.0, 0.0, dec['仓位差'][P]),
        ('合计（不含仓位差）', -1.3, 2.4, 1.2, total)]

fig, ax = plt.subplots(figsize=(11, 4.6))
n = len(rows)
fmt = lambda v: f'{v:+.1f}'.replace('-', '−')
X0, X1 = 1.03, 1.2          # 右侧两列（轴坐标）：事先范围、设计期
ax.text(X0, n - .45, '事先范围', transform=ax.get_yaxis_transform(), fontsize=10, color=MUTED, weight='bold')
ax.text(X1, n - .45, '设计期', transform=ax.get_yaxis_transform(), fontsize=10, color=MUTED, weight='bold')
for i, (nm, lo, hi, mid, act) in enumerate(rows):
    y = n - 1 - i
    bold = nm.startswith('合计')
    ax.barh(y, hi - lo, left=lo, height=.42, color=BAND if not bold else '#c9d4e4', edgecolor='none')
    ax.text(X0, y, f'{fmt(lo)} 到 {fmt(hi)}', transform=ax.get_yaxis_transform(), fontsize=10.5, color=MUTED, va='center')
    if mid is not None:
        ax.plot([mid, mid], [y - .27, y + .27], color=INK, lw=2)
    if act is None:
        ax.scatter([mid], [y], s=150, facecolors='white', edgecolors=GREY, linewidths=1.6, linestyle='--', zorder=3)
        ax.text(X1, y, '待补', transform=ax.get_yaxis_transform(), fontsize=10.5, color=GREY, va='center')
    else:
        c = TEAL if act > hi else (AMBER if act < lo else INK)
        ax.scatter([act], [y], s=110, color=c, zorder=4, edgecolors='white', linewidths=1.5)
        side = 'left' if act > hi else 'right'
        ax.text(act + (.14 if side == 'left' else -.14), y - .02, fmt(act), ha=side, va='center', fontsize=12.5, weight='bold', color=c)
        ax.text(X1, y, fmt(act), transform=ax.get_yaxis_transform(), fontsize=11, weight='bold', color=c, va='center')
ax.axvline(0, color=GREY, lw=.8)
ax.set_yticks(range(n), [r[0] for r in rows][::-1])
for t in ax.get_yticklabels():
    if t.get_text().startswith('合计'):
        t.set_weight('bold')
ax.tick_params(axis='y', length=0)
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:+.0f}'.replace('-', '−') if v else '0'))
ax.set_xlim(-4.3, 4.6); ax.set_ylim(-.6, n - .3)
ax.set_xlabel('每年比基准多几个点', color=MUTED); ax.grid(axis='x', alpha=.2)
fig.subplots_adjust(top=.97, bottom=.12)
h = fig.get_figheight()
fig.text(.04, 1 + .42 / h, f'设计期先对上三项：合计 {total:+.1f} 高出预测上限，仓位差 {dec["仓位差"][P]:+.1f} 略低于下限，成本 {dec["成本"][P]:+.1f} 比预演估计多约 0.4 点'.replace('-', '−'),
         fontsize=14, weight='bold', color=INK)
fig.text(.04, 1 + .12 / h, '横条 = 事先范围，竖线 = 中间值；实心点 = 设计期 2006–15（样本内，高于范围不计功）；虚线圈 = 待补。绿 = 高于范围，橙 = 低于范围',
         fontsize=10.5, color=MUTED)
fig.savefig(OUT / 'h1-forecast.png', dpi=150, bbox_inches='tight'); plt.close(fig)
print('h1-forecast.png', round(total, 2), dec['仓位差'][P], dec['成本'][P])
