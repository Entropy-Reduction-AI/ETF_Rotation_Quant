"""v5 备忘第 1、2 节的图。m9：E2 输掉三格的两个原因；m10：冠军赛与 E2 的事前画像。都只用信号层面的目标持仓。
用法：python results/v5/diag/design/charts.py docs/assets/v5-memo
"""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[4]
import pandas as pd, numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
GOOD = '#15803d'
INK, MUTED, BLUE, GREY, BAD, A1C = '#151b26', '#5d6676', '#1d4ed8', '#9ca3af', '#c2410c', '#d97706'
OUT = pathlib.Path(sys.argv[1]); D = ROOT / 'results/v5/diag/design'
yr = pd.read_csv(D / 'e2-targets-yearly.csv', header=[0, 1], index_col=0)
a1 = pd.read_csv(D / 'a1-picks-yearly.csv', index_col=0)
def title(fig, t, s):
    h = fig.get_figheight()
    fig.text(.06, 1 + .42 / h, t, fontsize=14.5, weight='bold', color=INK)
    fig.text(.06, 1 + .12 / h, s, fontsize=10.5, color=MUTED)
# m9
fig, (ax, bx) = plt.subplots(1, 2, figsize=(13, 4.6))
x = np.arange(len(yr)); ys = [str(v) for v in yr.index]
ax.bar(x - .2, yr[('tradable', 'cash')] * 100, .4, color=BAD, label='当年真能买到的池子', zorder=2)
ax.bar(x + .2, yr[('index', 'cash')] * 100, .4, color=GREY, label='能排名的池子', zorder=2)
for i, v in enumerate(yr[('tradable', 'elig')]): ax.text(i - .2, yr[('tradable', 'cash')].iloc[i] * 100 + 2, f'{v:.0f}', ha='center', fontsize=9, color=BAD)
ax.set_xticks(x, [y[2:] if y != '2006' else y for y in ys]); ax.set_ylim(0, 100); ax.set_ylabel('E2 闲置在现金的仓位 %', color=MUTED)
ax.set_title('① 能买的太少，每只又只给 1/N：钱大半闲着', loc='left', fontsize=12.5, weight='bold', color=INK)
ax.legend(frameon=False, fontsize=10, loc='upper right'); ax.grid(axis='y', alpha=.22)
ax.text(0, -21, '橙柱上的数字 = 当年平均有几只“跑赢现金、真能买到”的', fontsize=9.5, color=MUTED)
r_e2 = yr[('index', 'risk')] * 100; r_a1 = (1 - a1.get('cgb-10y', 0)) * 100
bx.plot(x, r_e2, color=BLUE, lw=2.6, marker='o', label='E2 新口径'); bx.plot(x, r_a1.reindex(yr.index).values, color=A1C, lw=2.6, marker='o', label='A1')
bx.axvspan(4.5, 9.5, color='#f3f4f6', zorder=0); bx.text(7, 8, '2011–15：E2 约六成，A1 近九成', ha='center', fontsize=10.5, color=INK)
bx.set_xticks(x, [y[2:] if y != '2006' else y for y in ys]); bx.set_ylim(0, 105); bx.set_ylabel('风险资产仓位 %', color=MUTED)
bx.set_title('② 后五年押得少：钱被分散到行业和国债上', loc='left', fontsize=12.5, weight='bold', color=INK)
bx.legend(frameon=False, fontsize=10, loc='lower left'); bx.grid(axis='y', alpha=.22)
title(fig, 'E2 输掉的三格，在跑之前就看得出来：可交易池的钱闲着，后五年押得太少',
      '设计期 2006–2015。规则想持有什么（月度决策、四个回看期和 N=3、5、8 平均），不含离场和成交，不算收益。A1 按其规则近似。')
fig.tight_layout(); fig.savefig(OUT / 'm9-e2-cells.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# m10
cy = pd.read_csv(D / 'champion-yearly.csv')
fig, axs = plt.subplots(1, 2, figsize=(13, 4.6), sharey=True)
GREEN = '#15803d'
for ax, pool, key, ttl in zip(axs, ('tradable', 'index'), ('风险', '防守'),
                              ('当年真能买到的池子：风险仓位（闲着的钱收回来了）', '能排名的池子：国债黄金仓位（后五年占得更多）')):
    for arm, col in (('E2', BLUE), ('冠军赛', GREEN)):
        g = cy[(cy.pool == pool) & (cy.arm == arm)].set_index('y'); x = np.arange(len(g))
        ax.plot(x, g[key], color=col, lw=2.6, marker='o', label=arm)
        ax.text(x[-1] + .25, g[key].iloc[-1], arm, color=col, fontsize=10.5, weight='bold', va='center')
    ax.set_xticks(x, [str(v)[2:] if v != 2006 else '2006' for v in g.index]); ax.set_ylim(0, 105); ax.set_xlim(-.4, 10.2); ax.grid(axis='y', alpha=.22)
    ax.set_title(ttl, loc='left', fontsize=12, weight='bold', color=INK)
axs[0].set_ylabel('目标仓位 %', color=MUTED)
title(fig, '冠军赛把可交易池里闲着的钱收回来了；代价是能排名的池子里，后五年国债占得更多',
      '设计期 2006–2015，信号层面的目标持仓，不含离场和成交，不算收益。冠军赛 = 每类一只冠军、冠军之间排名、取前 k 名平分（k=1、2、3 平均）。')
fig.tight_layout(); fig.savefig(OUT / 'm10-champion.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# m11 领先期
sp = pd.read_csv(D / 'leader-spells-250.csv', header=0, names=['spell', 'lead', 'start', 'n', 'x'], parse_dates=['start'])
NAME = {'csi300': '沪深300', 'spx': '标普500', 'hsi': '恒生'}; COLS = {'csi300': '#c2410c', 'spx': '#1d4ed8', 'hsi': '#0d9488'}
fig, ax = plt.subplots(figsize=(13, 4.4))
for i, r in sp.iterrows():
    v = r.x * 100
    ax.bar(i, v, color=COLS[r.lead], width=.7, zorder=2)
    ax.text(i, v + (2 if v >= 0 else -2), f'{v:+.0f}'.replace('-', '−'), ha='center', va='bottom' if v >= 0 else 'top', fontsize=10, color=INK)
    ax.text(i, -32, f"{r.start:%Y-%m}\n{r.n} 个月", ha='center', va='top', fontsize=8.5, color=MUTED)
from matplotlib.patches import Patch
handles = [Patch(color=c, label=NAME[k]) for k, c in COLS.items()]
ax.axhline(0, color=INK, lw=.8); ax.set_xticks([]); ax.set_ylim(-45, 100); ax.set_ylabel('这一段领先市场比三者平均多赚 %', color=MUTED)
ax.legend(handles=handles, frameon=False, fontsize=10.5, loc='upper right', title='领先的市场（按过去 12 个月涨幅）', title_fontsize=10)
ax.grid(axis='y', alpha=.22)
title(fig, '十年只有 12 段领先期，优势几乎全来自 2006–07 年 A 股那一段：只靠这三个市场，证明不了“押最强的大市场”是机制',
      '设计期 2006–2015，沪深300、恒生、标普500（人民币）。每月看过去 12 个月谁涨得最多，下个月持有它，和三者平均比；一段 = 同一个市场连续领先的月份。不扣成本，只作诊断。')
fig.tight_layout(); fig.savefig(OUT / 'm11-leader.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# m12 代价对比（哑铃图，越短越好）
import json as _json
J = _json.loads((D / 'adaptive-vol.json').read_text())['csi300']['规则']
def get(rule, key):
    return {r['转折']: r for r in J[rule]['转折']}.get(key)
EV = [('2007-10 真顶', '2007 年 10 月见顶', '离场前多跌'), ('2009-12 真顶', '2009 年 12 月见顶', '离场前多跌'), ('2015-06 未定', '2015 年 6 月见顶', '离场前多跌'),
      ('2008-11 真底', '2008 年 11 月见底', '回场前错过'), ('2012-12 真底', '2012 年 12 月见底', '回场前错过'), ('2014-03 真底', '2014 年 3 月见底（平静）', '回场前错过')]
fig, ax = plt.subplots(figsize=(13, 4.9))
for i_, (k, lab, what) in enumerate(EV):
    e = abs(get('E2 式（四个过半）', k)['涨跌']) * 100; d = abs(get('动态周期', k)['涨跌']) * 100
    diff = d - e; col = GOOD if diff < -2 else (BAD if diff > 2 else MUTED)
    ax.plot([e, d], [i_, i_], color='#d1d5db', lw=6, solid_capstyle='round', zorder=1)
    ax.scatter([e], [i_], s=120, color='#6b7280', zorder=3); ax.scatter([d], [i_], s=150, color=col, zorder=4)
    verdict = f'少付 {abs(diff):.0f} 个点' if diff < -2 else (f'多付 {diff:.0f} 个点' if diff > 2 else '差不多')
    ax.text(42, i_, verdict, va='center', fontsize=11, weight='bold', color=col)
    ax.text(-1, i_, f'{lab}\n{what}', va='center', ha='right', fontsize=10.5, color=INK)
ax.scatter([], [], s=100, color='#6b7280', label='E2 式（1、3、6、12 个月四道门过半）'); ax.scatter([], [], s=120, color=GOOD, label='动态周期（按波动伸缩）')
ax.set_yticks([]); ax.invert_yaxis(); ax.set_xlim(0, 52); ax.set_xlabel('付出的代价：见顶后离场前多跌了多少 / 见底后回场前错过了多少（%，越小越好）', color=MUTED)
ax.axhline(2.5, color='#e5e7eb', lw=1); ax.grid(axis='x', alpha=.22); ax.spines['left'].set_visible(False)
ax.legend(frameon=False, fontsize=10, loc='upper center', bbox_to_anchor=(.5, -.16), ncol=2)
title(fig, '六次关键转折里，动态周期三次少付很多、两次差不多、一次多付（平静中慢慢形成的底）',
      '设计期沪深300（人民币），只看价格：过去 L 天跑赢现金就持有。动态周期的 L 由最近 1 个月波动 ÷ 过去一年波动决定，在 1–12 个月之间伸缩。不算收益。')
fig.tight_layout(); fig.savefig(OUT / 'm12-adaptive.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# m13 第一层画像
L1 = pd.read_csv(D / 'layer1-yearly.csv', index_col=0)
fig, ax = plt.subplots(figsize=(13, 4.4))
COLS1 = [('A 股', '#c2410c'), ('港股', '#0d9488'), ('美股', '#1d4ed8'), ('国债', '#475569'), ('黄金', '#ca8a04'), ('现金', '#d1d5db')]
bot = np.zeros(len(L1)); x = np.arange(len(L1))
for k, col in COLS1:
    v = L1[k].values if k in L1 else np.zeros(len(L1))
    ax.bar(x, v, .7, bottom=bot, color=col, label=k, zorder=2)
    for xi, vi, bi in zip(x, v, bot):
        if vi >= 15: ax.text(xi, bi + vi / 2, f'{vi:.0f}', ha='center', va='center', fontsize=9.5, color='white', weight='bold')
    bot += v
for xi, s in zip(x, L1['每年换几次']): ax.text(xi, 102, f'换 {s} 次', ha='center', fontsize=9, color=MUTED)
ax.set_xticks(x, [str(v)[2:] if v != 2006 else '2006' for v in L1.index]); ax.set_ylim(0, 110); ax.set_ylabel('一年里持有它的周数占比 %', color=MUTED)
ax.legend(frameon=False, fontsize=10, loc='center left', bbox_to_anchor=(1.01, .5))
title(fig, '第一层的样子：2006–07 年押 A 股，2008 年拿现金，2010–14 年转到美股；震荡年份换得太勤',
      '设计期每周决策，信号层面“想持有什么”，不算收益。A 股 = 沪深300，港股 = 恒生，美股 = 标普500；国债数据 2008 年还不满一年，那年防守只能拿现金。')
fig.tight_layout(); fig.savefig(OUT / 'm13-layer1.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# m14 哪把尺子在响
A = pd.read_csv(D / 'scales-csi300.csv', index_col=0, parse_dates=True)
PH = [('牛市前段', '2006-01', '2007-06', '加速度刚出现'), ('牛市末段', '2007-07', '2007-10-16', '长尺子先熄火'), ('熊市', '2007-10-17', '2008-10', '长尺子向下最响'),
      ('底部前后', '2008-10', '2009-01', '各尺子都在减弱'), ('反弹', '2009-02', '2009-07', '长尺子响、短尺子静'), ('震荡', '2011-01', '2014-06', '全是噪音'),
      ('2015 加速', '2014-11', '2015-06-08', '各尺子都响'), ('2015 急跌', '2015-06-09', '2015-08-26', '中短尺子最响')]
G = pd.DataFrame({ph: A.loc[a:b].abs().mean() / 0.8 for ph, a, b, _ in PH}).T
fig, ax = plt.subplots(figsize=(13, 4.8))
im = ax.imshow(G.values, cmap='YlOrRd', vmin=0.4, vmax=2.4, aspect='auto')
for r in range(G.shape[0]):
    for c_ in range(G.shape[1]):
        v = G.values[r, c_]; ax.text(c_, r, f'{v:.1f}', ha='center', va='center', fontsize=10, color='white' if v > 1.7 else INK, weight='bold' if v >= 1.4 else None)
ax.set_xticks(range(G.shape[1]), [f'{n} 天' for n in G.columns]); ax.set_yticks(range(G.shape[0]), [f'{ph}（{note}）' for ph, _, _, note in PH])
ax.set_xlabel('量加速度的尺子', color=MUTED); ax.spines[:].set_visible(False)
cb = fig.colorbar(im, ax=ax, fraction=.025, pad=.01); cb.set_label('响度：1 = 纯噪音的水平', color=MUTED, fontsize=9.5)
title(fig, '一轮走势里，加速度出现在哪把尺子上会变：牛市末段长尺子先熄火，急跌时中短尺子最响，震荡时全是噪音',
      '设计期沪深300（人民币），只用价格。加速度 = 最近 n 天涨幅 − 再之前 n 天涨幅，按平常波动折算；格子是这一段里的平均响度，1.0 相当于纯噪音，1.4 以上加粗。')
fig.tight_layout(); fig.savefig(OUT / 'm14-scales.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
