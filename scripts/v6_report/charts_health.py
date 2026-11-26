"""v6 体检报告（设计期）的新图。只读设计期（≤ 2015）的结果文件。
用法：python -I scripts/v6_report/charts_health.py docs/assets/v6-health [结果目录，默认 results/v6]
h1：预测准不准——事先范围（横条）、中间值（竖线）、设计期实际（实心点）。
h2：和别人比——八条线 2006–15 的年化 × 最大回撤（左上更好），参照两点空心。
数字出处：
  事先范围、中间值 —《v6 预演预测表》第 3.22 版 = 冻结预注册 §3.1；A 股两块按 D40-12；成本的预演估计 — 冻结稿 §6 疼痛表“预演 1.0–1.1”；
  设计期实际 — health-forecast.csv（组合贡献列，D47-2、D48-2、D48-3）、health-scatter.csv、health-continuity.csv、health-gates.csv
    （Dev #377 @ a9a1e9e9，与 Reviewer #375 @ 7f1da3ff 独立结果逐项对上）；
  成本 — results/v6-preflight/v6-appendix-b.json 收益拆分.成本（附表 B 口径）；
  合计（不含仓位差）= v6 净 − BM-同仓位（判据 ④，§5.1 全收益基准、每月再平衡）。
样式与 scripts/preflight/charts_appendix_b.py 相同。
"""
import sys, json, csv, pathlib
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt, matplotlib.ticker

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
SRC = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / 'results/v6'
rd = lambda f: list(csv.DictReader(open(SRC / f, encoding='utf-8')))
AB = json.load(open(ROOT / 'results/v6-preflight/v6-appendix-b.json', encoding='utf-8'))
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'axes.spines.left': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, GREY, TEAL, AMBER, BAND, BLUE = '#151b26', '#5d6676', '#9ca3af', '#0d9488', '#d97706', '#dbe3ee', '#2563eb'
SEG = '2006-2015'
fmt = lambda v: f'{v:+.1f}'.replace('-', '−')

# ---------- h1 预测 ----------
F = {r['item']: float(r['contribution_pp']) for r in rd('health-forecast.csv') if r['segment'] == SEG and r['role'] == '主值'}
G = {r['item']: float(r['value']) for r in rd('health-gates.csv') if r['segment'] == SEG}
total = G['v6净减BM-同仓位年化']
cost = AB['收益拆分（每年比 BM-主 多几个点）']['成本']['2006–15']
rows = [('美股名额挑选', .3, 1.5, 1.0, F['美股挑选']),
        ('A 股名额：挑选', -.5, .5, .1, F['A股挑选']),
        ('A 股名额：等权倾斜', -1.0, 1.0, .5, F['A股等权倾斜']),
        ('防守的平时保费', -1.6, -.4, -.4, F['防守保费']),
        ('成本（预演估计）', -1.1, -1.0, None, cost),
        ('美股 60% 的仓位差', -3.0, 3.0, 0.0, F['美股60%仓位差']),
        ('合计（不含仓位差）', -1.3, 2.4, 1.2, total)]
fig, ax = plt.subplots(figsize=(11, 4.6)); n = len(rows)
X0, X1 = 1.03, 1.2
ax.text(X0, n - .45, '事先范围', transform=ax.get_yaxis_transform(), fontsize=10, color=MUTED, weight='bold')
ax.text(X1, n - .45, '设计期', transform=ax.get_yaxis_transform(), fontsize=10, color=MUTED, weight='bold')
for i, (nm, lo, hi, mid, act) in enumerate(rows):
    y = n - 1 - i
    ax.barh(y, hi - lo, left=lo, height=.42, color='#c9d4e4' if nm.startswith('合计') else BAND, edgecolor='none')
    ax.text(X0, y, f'{fmt(lo)} 到 {fmt(hi)}', transform=ax.get_yaxis_transform(), fontsize=10.5, color=MUTED, va='center')
    if mid is not None:
        ax.plot([mid, mid], [y - .27, y + .27], color=INK, lw=2)
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
ax.set_xlabel('每年比基准多几个点（组合层面）', color=MUTED); ax.grid(axis='x', alpha=.2)
fig.subplots_adjust(top=.97, bottom=.12)
h = fig.get_figheight()
fig.text(.04, 1 + .42 / h, f'挑选三项都高于事先范围，防守保费和仓位差在范围内；合计 {fmt(total)} 刚过上限 +2.4', fontsize=14, weight='bold', color=INK)
fig.text(.04, 1 + .12 / h, '横条 = 事先范围，竖线 = 中间值；圆点 = 设计期 2006–15（样本内，高于范围不计功）。绿 = 高于范围，橙 = 低于范围',
         fontsize=10.5, color=MUTED)
fig.savefig(OUT / 'h1-forecast.png', dpi=150, bbox_inches='tight'); plt.close(fig)

# ---------- h2 散点 ----------
S = {r['series']: (float(r['cagr_pct']), -100 * float(r['max_drawdown'])) for r in rd('health-scatter.csv') if r['segment'] == SEG and r['status'] == 'ok'}
C = {r['role']: r for r in rd('health-continuity.csv') if r['segment'] == SEG}
ref = {'连续性版（不过滤，参照）': (float(C['参照']['cagr_pct']), -100 * float(C['参照']['max_drawdown']))}
fig, ax = plt.subplots(figsize=(11, 5.4))
style = {'v6': (BLUE, 190), '连续性版': (BLUE, 90), 'BM-主': (GREY, 90), 'BM-同仓位': (GREY, 90)}
offs = {'v6': (12, -18), '连续性版': (12, 10), 'A1': (10, -4), 'A2': (-10, 10), 'K2A': (-10, 10), '现行配置': (10, 8),
        'BM-主': (10, 8), 'BM-同仓位': (10, -16)}
for k, (y, x) in S.items():
    c, s = style.get(k, (INK, 90))
    ax.scatter([x], [y], s=s, color=c, zorder=4, edgecolors='white', linewidths=1.5)
    dx, dy = offs.get(k, (10, -4))
    ax.annotate(f'{k}  {y:.1f}% / −{x:.1f}%', (x, y), xytext=(dx, dy), textcoords='offset points', fontsize=11,
                ha='left' if dx > 0 else 'right', weight='bold' if k == 'v6' else 'normal', color=BLUE if k.startswith(('v6', '连续')) else INK)
for k, (y, x) in ref.items():
    ax.scatter([x], [y], s=80, facecolors='white', edgecolors=GREY, linewidths=1.4, zorder=3)
    ax.annotate(k, (x, y), xytext=(-10, -16), textcoords='offset points', fontsize=10, color=MUTED, ha='right')
ax.set_xlim(70, 5); ax.set_ylim(5, 30)
ax.set_xlabel('最大回撤（%，越往右越浅）', color=MUTED); ax.set_ylabel('年化（%）', color=MUTED)
ax.grid(alpha=.2); ax.spines['left'].set_visible(True)
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'−{v:.0f}'))
fig.subplots_adjust(top=.97)
h = fig.get_figheight(); v6y, v6x = S['v6']; by, bx = S['BM-主']
fig.text(.04, 1 + .42 / h, f'v6 回撤 −{v6x:.1f}%，不到 BM-主（−{bx:.1f}%）的一半；年化 {v6y:.2f}%，比 BM-主少 {by - v6y:.2f} 点，也低于 A1、现行配置、K2A',
         fontsize=14, weight='bold', color=INK)
fig.text(.04, 1 + .12 / h, '设计期 2006–15，扣成本，基准为全收益（§5.1）。越靠右上越好：右 = 回撤浅，上 = 收益高。蓝 = v6 与挑战者，灰 = 基准，空心 = 参照',
         fontsize=10.5, color=MUTED)
fig.savefig(OUT / 'h2-peers.png', dpi=150, bbox_inches='tight'); plt.close(fig)
print('ok', round(total, 2), {k: tuple(round(x, 1) for x in v) for k, v in S.items()})
