"""v6 一次性检验报告骨架的图位。只读设计期（≤ 2015）的已对上结果；检验段一律画成待填的空位，不读也不画任何 2016 年以后的数。
用法：python -I scripts/v6_report/charts_oneshot_skeleton.py docs/assets/v6-oneshot [结果目录，含 health-*.csv 与 health-extra.json]
跑完一次性检验后，这些图由同名的正式图替换（同一张图、同一位置，只是把空位填上）。
"""
import sys, json, csv, pathlib
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch

OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
SRC = pathlib.Path(sys.argv[2])
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, GREY, BLUE, AMBER, TEAL, PEND = '#151b26', '#5d6676', '#9ca3af', '#2563eb', '#d97706', '#0d9488', '#eef1f5'
TODO = '检验段：开考后填'


def save(fig, name):
    fig.savefig(OUT / name, dpi=130, bbox_inches='tight'); plt.close(fig)


def pending_grid(ax, rows, cols, title_cols=None, filled=None):
    """空格子：灰底虚线；filled[(i, j)] = (文字, 颜色) 的格子照填。"""
    filled = filled or {}
    for i, r in enumerate(rows):
        ax.text(-0.15, -i, r, ha='right', va='center', fontsize=12, color=INK)
        for j, c in enumerate(cols):
            if (i, j) in filled:
                t, col = filled[(i, j)]
                ax.add_patch(Rectangle((j, -i - .42), .92, .84, fc=col, ec='white'))
                ax.text(j + .46, -i, t, ha='center', va='center', fontsize=11.5, color=INK)
            else:
                ax.add_patch(Rectangle((j, -i - .42), .92, .84, fc=PEND, ec=GREY, ls='--', lw=.8))
                ax.text(j + .46, -i, '?', ha='center', va='center', fontsize=12, color=GREY)
    for j, c in enumerate(title_cols or cols):
        ax.text(j + .46, .75, c, ha='center', va='center', fontsize=11.5, color=MUTED, weight='bold')
    ax.set_xlim(-2.4, len(cols) + .1); ax.set_ylim(-len(rows) + .3, 1.2); ax.axis('off')


# ---------- o2 稳健性与随机 ----------
fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.8), gridspec_kw={'width_ratios': [1.35, 1]})
pending_grid(a, ['S1 成本加倍', 'S2 晚 1 天', 'S3 去掉第 1', 'S4 去掉前 2', 'S5 去掉前 3', 'S6 美股 50%', 'S7 选前 2', 'S8 三票全中'],
             ['①', '②', '③', '④', '总结论'])
a.set_title('稳健性 8 项 × 四条判据：总结论翻转的格子框出，记“很敏感”', fontsize=12.5, loc='left', color=INK)
xs = np.linspace(-6, 6, 200)
b.fill_between(xs, np.exp(-xs ** 2 / 8), color=PEND, ec=GREY, ls='--')
b.axvline(0, color=GREY, ls=':', lw=1); b.text(.3, .9, '随机中位数', ha='left', color=MUTED, fontsize=10.5); b.set_ylim(0, 1.1)
b.text(0, .45, '1000 次同结构随机的年化分布\nv6 一条竖线\n（' + TODO + '）', ha='center', va='center', color=MUTED, fontsize=11)
b.set_yticks([]); b.set_xticks([]); b.spines['left'].set_visible(False)
b.set_title('跑赢随机吗：v6 在 1000 次里排第几', fontsize=12.5, loc='left', color=INK)
save(fig, 'o2-robust.png')

# ---------- o3 六块 × 四段 ----------
fig, ax = plt.subplots(figsize=(11.5, 4.4))
pending_grid(ax, ['分红', '仓位差', '等权倾斜', '挑选', '防守', '成本'], ['2006–10', '2011–15', '2016–20', '2021–26.09', '读法标签'])
ax.add_patch(Rectangle((2 - .06, -5.55), 2.04, 6.1, fc='none', ec=BLUE, lw=1.6))
ax.text(3, -6.05, '检验段两段：决定“稳定 / 设计期才有 / 不稳定”', ha='center', color=BLUE, fontsize=11)
ax.set_ylim(-6.4, 1.2)
ax.set_title('钱从哪来：六块 × 四个五年段，正绿负橙；同一块在检验段还在不在', fontsize=12.5, loc='left', color=INK)
save(fig, 'o3-sources.png')

# ---------- o4 挑选与防守 ----------
fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw={'width_ratios': [1, 1.3]})
for i in range(10):
    a.barh(-i, 10 - i * .8, color=PEND, ec=GREY, ls='--', lw=.8)
    a.text(-.3, -i, f'第 {i + 1}', ha='right', va='center', color=MUTED, fontsize=10.5)
a.set_xlim(-2, 11); a.axis('off')
a.set_title('挑选贡献最大的 10 个候选（' + TODO + '）', fontsize=12.5, loc='left', color=INK)
A = {2006: 0, 2007: 0, 2008: 12, 2009: 2, 2010: 6, 2011: 8, 2012: 8, 2013: 0, 2014: 2, 2015: 4}   # 体检第 9 节逐年表（设计期，两边已对上）
U = {2006: 0, 2007: 3, 2008: 12, 2009: 4, 2010: 3, 2011: 5, 2012: 0, 2013: 0, 2014: 0, 2015: 2}
yrs = list(range(2006, 2027))
for y in yrs:
    if y in A:
        b.bar(y - .2, A[y], .4, color=AMBER); b.bar(y + .2, U[y], .4, color=BLUE)
    else:
        b.bar(y, 12, .8, color=PEND, ec=GREY, ls='--', lw=.6)
b.axvline(2015.5, color=INK, lw=1); b.text(2015.7, 12.6, TODO, color=MUTED, fontsize=10.5)
b.text(2006, 12.6, '■ A 股', color=AMBER, fontsize=10.5); b.text(2008.4, 12.6, '■ 美股', color=BLUE, fontsize=10.5)
b.set_ylim(0, 13.5); b.set_ylabel('一年里紧张的月份', color=MUTED)
b.set_title('防守：每年紧张几个月，每一段帮了多少', fontsize=12.5, loc='left', color=INK)
save(fig, 'o4-picks-defense.png')

# ---------- o5 八条线散点 ----------
S = [r for r in csv.DictReader(open(SRC / 'health-scatter.csv', encoding='utf-8')) if r['segment'] == '2006-2015']
fig, ax = plt.subplots(figsize=(11, 5))
for r in S:
    x, y = 100 * float(r['max_drawdown']), float(r['cagr_pct'])
    c = BLUE if r['series'] == 'v6' else GREY
    ax.scatter(x, y, s=90, facecolors='none', edgecolors=c, lw=1.8)
    ax.annotate(r['series'], (x, y), xytext=(6, 4), textcoords='offset points', fontsize=10.5, color=c)
ax.text(.98, .97, '空心 = 设计期 2006–15（已对上）\n实心 = 检验段 2016–2026（开考后画）', transform=ax.transAxes, ha='right', va='top', color=MUTED, fontsize=11)
ax.set_xlabel('最大回撤 %（越靠右越浅）', color=MUTED); ax.set_ylabel('年化 %', color=MUTED); ax.grid(alpha=.2)
ax.set_title('和别人比：八条线的年化 × 最大回撤，检验段的实心点开考后画', fontsize=12.5, loc='left', color=INK)
save(fig, 'o5-peers.png')

# ---------- o6 净值（设计期已画，检验段留白） ----------
X = json.load(open(SRC / 'health-extra.json', encoding='utf-8'))
wk = pd.to_datetime(X['weeks'])
LINE = {'v6': (BLUE, 2.6, '-'), 'K2A': (INK, 1.6, '-'), '现行配置': (AMBER, 1.4, '-'), 'A1': (TEAL, 1.4, '-'),
        'BM-主': (GREY, 1.6, '-'), 'BM-同仓位': (GREY, 1.4, '--')}
fig, (a1, a2) = plt.subplots(2, 1, figsize=(12, 6.6), sharex=True, gridspec_kw={'height_ratios': [2.4, 1], 'hspace': .08})
for k, (c, lw, ls) in LINE.items():
    if k in X['nav_weekly']:
        a1.plot(wk, 100 * np.array(X['nav_weekly'][k]), color=c, lw=lw, ls=ls, label=k)
        a2.plot(wk, 100 * np.array(X['dd_weekly'][k]), color=c, lw=lw * .7, ls=ls)
end = pd.Timestamp('2026-09-30')
for ax_ in (a1, a2):
    ax_.axvspan(pd.Timestamp('2016-01-01'), end, color=PEND)
    ax_.axvline(pd.Timestamp('2016-01-01'), color=INK, lw=1)
a1.text(pd.Timestamp('2021-03-01'), a1.get_ylim()[1] * .55, '检验段 2016-01 → 2026-09\n开考后接着画', ha='center', color=MUTED, fontsize=12)
a1.set_xlim(wk[0], end); a1.set_ylim(0, None); a1.legend(loc='upper left', frameon=False, ncol=3, fontsize=10.5)
a1.set_ylabel('100 万变成多少万', color=MUTED); a2.set_ylabel('回撤 %', color=MUTED)
a1.set_title('一条线走 20 年：左边设计期已对上，右边检验段开考后接着画；最深一跌是否跨 2016-01 要写明', fontsize=12.5, loc='left', color=INK)
save(fig, 'o6-nav.png')

# ---------- o7 四种行情（设计期对 BM-主已算，检验段留白） ----------
R = X['regimes']
names = ['牛市', '回调', '熊市', '反弹']
fig, ax = plt.subplots(figsize=(11, 4.4))
for i, n in enumerate(names):
    v = R[n]['BM-主']['合计']
    ax.bar(i - .2, v, .38, color=TEAL if v > 0 else AMBER)
    ax.text(i - .2, v + (6 if v > 0 else -6), f'{v:+.0f}'.replace('-', '−'), ha='center', va='bottom' if v > 0 else 'top', fontsize=11)
    ax.bar(i + .2, 60, .38, bottom=-30, color=PEND, ec=GREY, ls='--', lw=.8)
    ax.text(i + .2, 0, '?', ha='center', va='center', color=GREY)
ax.axhline(0, color=GREY, lw=.8); ax.set_xticks(range(4)); ax.set_xticklabels(names)
ax.set_ylabel('对 BM-主每月差相加（点）', color=MUTED)
ax.text(.01, .97, '左柱 = 设计期 2006–15；右柱 = 检验段（开考后画）', transform=ax.transAxes, ha='left', va='top', color=MUTED, fontsize=11)
ax.set_title('四种行情：设计期熊市、回调多赚，牛市、反弹少赚；检验段还是这样吗', fontsize=12.5, loc='left', color=INK)
save(fig, 'o7-regime.png')

# ---------- o8 预测对账 ----------
rows = [('美股名额挑选', .3, 1.5, 1.0, 3.41), ('A 股名额：挑选', -.5, .5, .1, 1.48), ('A 股名额：等权倾斜', -1.0, 1.0, .5, 2.28),
        ('防守的平时保费', -1.6, -.4, -.4, -.79), ('美股 60% 的仓位差', -3.0, 3.0, 0.0, -2.83), ('合计（不含仓位差）', -1.3, 2.4, 1.2, 2.46)]
fig, ax = plt.subplots(figsize=(11, 4.4))
for i, (n, lo, hi, mid, d) in enumerate(rows):
    y = -i
    ax.plot([lo, hi], [y, y], color='#dbe3ee', lw=9, solid_capstyle='round')
    ax.plot([mid, mid], [y - .22, y + .22], color=INK, lw=1.4)
    ax.scatter(d, y + .12, s=50, color=GREY, zorder=3)
    ax.add_patch(Rectangle((4.0, y - .3), .55, .6, fc=PEND, ec=GREY, ls='--', lw=.8)); ax.text(4.27, y, '?', ha='center', va='center', color=GREY)
    ax.text(-3.4, y, n, ha='right', va='center', fontsize=11.5)
ax.set_yticks([]); ax.set_xlim(-3.3, 4.65); ax.set_xticks(range(-3, 4)); ax.text(4.27, .55, '检验段', ha='center', color=MUTED, fontsize=10.5, weight='bold'); ax.axvline(0, color=GREY, lw=.6); ax.spines['left'].set_visible(False)
ax.set_xlabel('每年比基准多几个点（组合贡献）', color=MUTED)
ax.set_title('预测准不准：检验段的点落在横条里吗（只对账，不判过不过）', fontsize=12.5, loc='left', color=INK, pad=26)
ax.text(0, 1.03, '横条 = 事先范围；竖线 = 中间值；灰点 = 设计期；右侧空格 = 检验段（开考后画）', transform=ax.transAxes, ha='left', color=MUTED, fontsize=10.5)
save(fig, 'o8-forecast.png')
print('ok')
