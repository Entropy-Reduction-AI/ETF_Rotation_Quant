"""D38 预测表的图（只读 results/v6-preflight 的结果文件，不重算）。
用法：python scripts/preflight/charts.py docs/assets/v6-preflight
颜色：橙 = 比底仓差，绿 = 比底仓好，灰 = 参照；同一结构在所有图里颜色相同。
"""
import sys, pathlib, json
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
ROOT = pathlib.Path(__file__).resolve().parents[2]; RES = ROOT / 'results/v6-preflight'
OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, GREY, BAD, GOOD, BLUE = '#151b26', '#5d6676', '#9ca3af', '#c2410c', '#15803d', '#1d4ed8'
SC = {'K1': '#d97706', 'K2': '#1d4ed8', 'K2A': '#0d9488', 'K3': '#7c3aed'}

def title(fig, t, s):
    h = fig.get_figheight()
    fig.text(.04, 1 + .42 / h, t, fontsize=14.5, weight='bold', color=INK)
    fig.text(.04, 1 + .12 / h, s, fontsize=10.5, color=MUTED)

# ---------- f1：每层每年多少、回撤砍多少（预测表第 1 节的数字，原样） ----------
def fmt(v, d=1):
    return '0' if round(v, d) == 0 else f'{v:+.{d}f}'.replace('-', '−')
BOX = dict(boxstyle='round,pad=.15', fc='white', ec='none')

rows = [  # 层, 合计中间值（None = 只有范围）, 低, 高, 回撤改善说明
    ('K1 慢趋势保险', -1.9, -2.6, 0.0, '回撤浅三到五成'),
    ('K2 = K1 + 按波动降仓', -2.2, -2.4, -0.4, '回撤约砍一半'),
    ('K2A 只保 A 股腿', -1.6, -2.1, 2.3, '回撤约砍三成'),
    ('K3 倾斜层（加在 K1 上）', None, -0.1, 0.4, '回撤基本不变'),
    ('挑选层（A 股内 12−1）', None, 0.0, 0.4, '回撤不变'),
]
fig, ax = plt.subplots(figsize=(12, 4.2))
for i, (n, c, lo, hi, dd) in enumerate(rows):
    y = len(rows) - 1 - i
    col = BAD if (c if c is not None else (lo + hi) / 2) < 0 else GOOD
    ax.plot([lo, hi], [y, y], color=col, lw=6, alpha=.28 if c is not None else .7, solid_capstyle='round')
    if c is not None:
        ax.plot(c, y, 'o', color=col, ms=11, zorder=3)
        ax.text(c, y + .3, fmt(c), ha='center', color=col, weight='bold', fontsize=11.5)
    else:
        ax.text((lo + hi) / 2, y + .3, f'{fmt(lo)} ~ {fmt(hi)}', ha='center', color=col, weight='bold', fontsize=11.5, bbox=BOX, zorder=4)
    ax.text(2.75, y, dd, va='center', color=MUTED, fontsize=10.5)
ax.axvline(0, color=INK, lw=1)
ax.axvline(-2, color=GREY, lw=1.2, ls='--'); ax.text(-2.05, -.45, '保费上限 2 个点', color=MUTED, ha='right', fontsize=10)
ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows][::-1], fontsize=11.5)
ax.set_xlim(-3.2, 4.2); ax.set_ylim(-.6, len(rows) - .2)
ax.set_xticks(range(-3, 5)); ax.set_xticklabels([fmt(v, 0) if v else '0' for v in range(-3, 5)])
ax.set_xlabel('每年比底仓（70/15/15）多或少几个点；粗线 = 范围，圆点 = 中间值', color=MUTED)
ax.grid(axis='x', alpha=.22)
title(fig, '保险层每年付 1.6–2.2 个点换回撤；挑选和倾斜打折后不到半个点',
      '换算口径：股票 8.7%、国债 2.5%；历史得来的收益打五折，成本取上限')
fig.savefig(OUT / 'f1-forecast.png', dpi=150, bbox_inches='tight'); plt.close(fig)

# ---------- f2：每种行情里 K1、K2、K2A 比 K0（合成行情中位数） ----------
b = pd.read_csv(RES / 'behavior.csv')
ev = {}  # V 型反转用“这一次累计”，与预测表第 2 节一致
ev_v = {'K1': -26, 'K2': -20, 'K2A': -15}
REG = ['慢牛', '震荡', '市场接力', '急跌', '慢熊', 'V型反转']
LAB = {'慢牛': '慢牛\n3 年 +15%/年', '震荡': '震荡\n3 年横盘', '市场接力': '市场接力', '急跌': '急跌\n20 天 −30%',
       '慢熊': '慢熊\n18 个月 −45%', 'V型反转': 'V 型反转\n（这一次累计）'}
fig, ax = plt.subplots(figsize=(12.5, 4.6))
w = .26
for j, k in enumerate(('K1', 'K2', 'K2A')):
    vals = [ev_v[k] if r == 'V型反转' else float(b[(b.行情 == r) & (b.结构 == k)]['比K0年化_p50'].iloc[0]) for r in REG]
    xs = np.arange(len(REG)) + (j - 1) * w
    ax.bar(xs, vals, w * .92, color=[GOOD if v > 0 else BAD for v in vals], alpha=[.95, .7, .45][j], edgecolor=SC[k], lw=1.4)
    for x, v in zip(xs, vals):
        ax.text(x, v + (1 if v >= 0 else -1), fmt(v, 0) if abs(v) >= 10 else fmt(v), ha='center',
                va='bottom' if v >= 0 else 'top', fontsize=9.5, color=INK)
for j, k in enumerate(('K1', 'K2', 'K2A')):
    ax.bar([0], [0], color='white', edgecolor=SC[k], lw=1.4, label={'K1': 'K1 慢趋势保险', 'K2': 'K2 + 按波动降仓', 'K2A': 'K2A 只保 A 股腿'}[k])
ax.axhline(0, color=INK, lw=1); ax.axvline(2.5, color=GREY, lw=1, ls=':')
ax.text(1, 37, '← 付保费', ha='center', color=BAD, weight='bold'); ax.text(4, 37, '拿赔付（V 型反转除外）→', ha='center', color=GOOD, weight='bold')
ax.set_xticks(range(len(REG))); ax.set_xticklabels([LAB[r] for r in REG], fontsize=10.5)
ax.set_ylim(-31, 40); ax.set_yticks(range(-30, 41, 10)); ax.set_yticklabels([fmt(v, 0) if v else '0' for v in range(-30, 41, 10)]); ax.set_ylabel('每年比底仓（个点）', color=MUTED); ax.grid(axis='y', alpha=.22)
ax.legend(frameon=False, loc='lower left', fontsize=10)
title(fig, '保费付在慢牛和 V 型反转，赔付在慢熊和急跌',
      '合成行情 1000 条路径中位数；合成行情没有动量，量的是“没有信号时”的保费')
fig.savefig(OUT / 'f2-regimes.png', dpi=150, bbox_inches='tight'); plt.close(fig)

# ---------- f3：底仓美股比例（K0，比 70/30） ----------
s = pd.read_csv(RES / 'sensitivity.csv'); s = s[s.结构 == 'K0']
fig, ax = plt.subplots(figsize=(12, 4.4))
cols = {'-10%': BAD, '+0%': MUTED, '+10%': '#16a34a', '+20%': GOOD}
for sp, g in s.groupby('美股比A股每年多涨', sort=False):
    xs = g['底仓美股'].str.rstrip('%').astype(int); ys = g['比70_30年化_p50']
    ax.plot(xs, ys, 'o-', color=cols[sp], lw=2.4)
    lab = {'-10%': '美股每年少涨 10 个点', '+0%': '两地一样', '+10%': '美股每年多涨 10 个点', '+20%': '美股每年多涨 20 个点'}[sp]
    ax.text(82, ys.iloc[-1] + (.45 if sp == '+0%' else 0), f'{lab}：{fmt(ys.iloc[-1])}', va='center', color=cols[sp], fontsize=10.5, weight='bold', bbox=BOX)
ax.axhline(0, color=INK, lw=1); ax.axvline(30, color=GREY, lw=1, ls='--'); ax.text(30.5, 9.3, '现行 30%', color=MUTED, fontsize=10)
ax.set_xlim(28, 100); ax.set_xticks([30, 40, 50, 60, 70, 80]); ax.set_xticklabels([f'{v}%' for v in (30, 40, 50, 60, 70, 80)])
ax.set_yticks(range(-4, 11, 2)); ax.set_yticklabels([fmt(v, 0) if v else '0' for v in range(-4, 11, 2)])
ax.set_xlabel('底仓里美股的比例', color=MUTED); ax.set_ylabel('每年比 70/30 多或少（个点）', color=MUTED); ax.grid(axis='y', alpha=.22)
title(fig, '底仓美股每多 10 个点，每年约多（少）0.1 × 两地涨幅差',
      '十年合成行情，A 股每年 6%、波动 25%，美股波动 17%（两地波动是假设）')
fig.savefig(OUT / 'f3-us-share.png', dpi=150, bbox_inches='tight'); plt.close(fig)
print('ok')
