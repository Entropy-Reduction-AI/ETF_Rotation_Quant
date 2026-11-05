"""复盘第 3 版和一次性检验报告的图：E2 新口径、A1、v5.1 三个都画（A2 只在表里）。只读签收结果、attribution_all.json 和行情。
用法：python results/v5/report/retro3_charts.py <attr.pkl> <peers_design.pkl>
"""
import sys, json, pickle, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'results/v5/report'))
import pandas as pd, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from results_v5_group import group
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False, 'axes.spines.right': False, 'font.size': 11, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, GOOD, BAD, BASE = '#151b26', '#5d6676', '#16a34a', '#ea580c', '#475569'
ARMC = {'E2 新口径': '#1d4ed8', 'A1': '#d97706', 'v5.1': '#c2410c', '基准': INK}
GC = {'A股宽基': '#1d4ed8', 'A股行业': '#60a5fa', '港股': '#7c3aed', '美股宽基': '#c2410c', '海外主题': '#fdba74', '债券': '#94a3b8', '黄金': '#eab308', '商品': '#0d9488', '现金': '#e5e7eb'}
J = json.loads((ROOT / 'results/v5/report/attribution_all.json').read_text())
A3 = ('E2 新口径', 'A1', 'v5.1')
RET, OS = ROOT / 'docs/assets/retro', ROOT / 'docs/assets/v5-oneshot'
def title(fig, t, s):
    h = fig.get_figheight(); fig.text(.05, 1 + .42 / h, t, fontsize=14.5, weight='bold', color=INK); fig.text(.05, 1 + .12 / h, s, fontsize=10.5, color=MUTED)
ref = None
# r1 收益从哪来：三段 × 四个
fig, axs = plt.subplots(1, 3, figsize=(14, 5.2), sharey=True)
for ax, seg in zip(axs, ('前五年', '后五年', '检验段')):
    names = list(A3) + ['基准']
    for i, arm in enumerate(names):
        if arm == '基准':
            s = J['segments']['E2 新口径'][seg]; A = s['A股少拿'] / (s['仓位_A'] / 100 - .7) if abs(s['仓位_A'] / 100 - .7) > 1e-9 else 0
            parts = {'A股宽基': .7 * A, '美股宽基': s['基准'] - .7 * A}
        else:
            parts = J['segments'][arm][seg]['贡献']
        pos = neg = 0
        for g, col in GC.items():
            v = parts.get(g, 0)
            if abs(v) < .05: continue
            if v >= 0: ax.bar(i, v, bottom=pos, color=col, width=.66, label=g); pos += v
            else: ax.bar(i, v, bottom=neg, color=col, width=.66); neg += v
        tot = sum(parts.values())
        ax.text(i, pos + .8, f'{tot:.1f}', ha='center', fontsize=10.5, weight='bold', color=ARMC[arm])
    ax.set_xticks(range(4)); ax.set_xticklabels(names, fontsize=10.5); ax.axhline(0, color=INK, lw=.8); ax.grid(axis='y', alpha=.2)
    ax.set_title({'前五年': '2006–2010', '后五年': '2011–2015', '检验段': '2016–2026（检验段）'}[seg], loc='left', fontsize=12, weight='bold', color=INK)
seen = {}
for a_ in axs:
    for hh, ll in zip(*a_.get_legend_handles_labels()): seen.setdefault(ll, hh)
seen = {k: seen[k] for k in GC if k in seen}
fig.legend(seen.values(), seen.keys(), frameon=False, ncol=9, loc='lower center', bbox_to_anchor=(.5, -.04), fontsize=10)
axs[0].set_ylabel('每年贡献的收益（百分点，扣费前）', color=MUTED)
title(fig, '收益从哪来：设计期三个策略都靠 A 股；检验段基准靠美股，只有 A1 拿到了美股，E2 新口径和 v5.1 的钱分在海外主题和债券上',
      '能排名的池子。每天持仓 × 各容器当天收益，按大类加总（和扣费前净值相关系数 1.00）。柱顶数字 = 合计。')
fig.tight_layout(rect=(0, .04, 1, 1)); fig.savefig(RET / 'r1-sources.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# r4 差距瀑布：设计期、检验段 × 三个
STEPS = [('美股\n仓位', '美股少拿'), ('美股\n时点', '美股时点'), ('A 股\n仓位', 'A股少拿'), ('A 股里\n拿什么', 'A股选择'), ('海外\n主题', '海外主题'), ('防守\n港股', None), ('成本', '成本')]
fig, axs = plt.subplots(2, 3, figsize=(15, 8.6))
for r, seg in enumerate(('设计期', '检验段')):
    for c, arm in enumerate(A3):
        ax = axs[r, c]; s = J['segments'][arm][seg]
        vals = [s['美股少拿'], s['美股时点'], s['A股少拿'], s['A股选择'], s['海外主题'], s['防守'] + s['港股'], -s['成本']]
        level = s['基准']; ax.bar(0, level, color=BASE, width=.62); ax.text(0, level + .5, f'{level:.1f}', ha='center', fontsize=9.5, weight='bold')
        for i, v in enumerate(vals, 1):
            bottom = level if v >= 0 else level + v
            ax.bar(i, abs(v), bottom=bottom, color=GOOD if v >= 0 else BAD, width=.62)
            if abs(v) >= .3: ax.text(i, (level + v + .5) if v >= 0 else (level + v - .5), f'{v:+.1f}', ha='center', va='bottom' if v >= 0 else 'top', fontsize=9, color=GOOD if v >= 0 else BAD, weight='bold')
            level += v
        ax.bar(len(vals) + 1, level, color=ARMC[arm], width=.62); ax.text(len(vals) + 1, level + .5 if level >= 0 else level - .5, f'{level:.1f}', ha='center', va='bottom' if level >= 0 else 'top', fontsize=9.5, weight='bold', color=ARMC[arm])
        ax.set_xticks(range(len(vals) + 2)); ax.set_xticklabels(['基准'] + [x[0] for x in STEPS] + [arm.replace(' ', '\n')], fontsize=8.6)
        ax.axhline(0, color=INK, lw=.7); ax.grid(axis='y', alpha=.2)
        gap = level - s['基准']
        ax.set_title(f'{arm} · {"设计期 2006–15" if seg == "设计期" else "检验段 2016–26"}：{gap:+.1f}', loc='left', fontsize=11.5, weight='bold', color=GOOD if gap > 0 else BAD)
    lo = min(axs[r, i].get_ylim()[0] for i in range(3)); hi = max(axs[r, i].get_ylim()[1] for i in range(3))
    for i in range(3): axs[r, i].set_ylim(min(lo, -1) - 1.5, hi * 1.08)
axs[0, 0].set_ylabel('设计期：每年收益（百分点）', color=MUTED); axs[1, 0].set_ylabel('检验段：每年收益（百分点）', color=MUTED)
title(fig, '和基准差在哪：设计期三个都赢在“A 股里拿什么、什么时候拿”；检验段 E2 新口径输在美股少拿和 A 股，v5.1 最大一块是成本 −6.6，A1 拿对了美股却输在进出时点',
      '从基准出发，逐项加上与基准的差：“仓位”= 比基准多拿或少拿乘以该类收益；“时点 / 拿什么”= 该类里实际赚的减去按基准方式持有能赚的。每年算术贡献，和年化略有差别。')
fig.tight_layout(); fig.savefig(RET / 'r4-gap.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# r3 选的本事，逐年
fig, axs = plt.subplots(3, 1, figsize=(13, 8.4), sharex=True)
lab = {'E2 新口径': '比当天全部可选股票类容器等权', 'A1': '比标普500、沪深300 各半', 'v5.1': '比所选市场里的容器等权'}
for ax, arm in zip(axs, A3):
    y = {}
    for seg in ('设计期', '检验段'):
        y.update({int(k): v for k, v in J['selection'][f'{arm}|{seg}']['逐年'].items()})
    ys = pd.Series(y).sort_index()
    ax.bar(ys.index, ys.values, color=[GOOD if v > 0 else BAD for v in ys.values], width=.7)
    ax.axhline(0, color=INK, lw=.8); ax.axvspan(2005.5, 2015.5, color='#f1f5f9', zorder=-1); ax.grid(axis='y', alpha=.2)
    d1, d2 = J['selection'][f'{arm}|设计期'], J['selection'][f'{arm}|检验段']
    ax.set_title(f'{arm}（{lab[arm]}）：设计期每年 {d1["每年"]:+.1f}、检验段 {d2["每年"]:+.1f}', loc='left', fontsize=11.5, weight='bold', color=ARMC[arm])
    ax.set_ylabel('百分点', color=MUTED)
title(fig, '“挑哪一只”的本事：E2 新口径和 v5.1 平均每年只有 +1 个点左右；只有 A1 的二选一在设计期有用（每年 +13.9），检验段只剩 +2.2',
      '股票类持仓的收益减去一个“闭眼也能做到”的对照，逐年加总。灰底是设计期。能排名的池子，扣费前。')
fig.tight_layout(); fig.savefig(RET / 'r3-selection.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# o6 逐月柱：三个，横轴到 2026-09
O = ROOT / 'results/v5/oneshot/index'
fig, axs = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
for ax, (arm, fold) in zip(axs, (('E2 新口径（入围）', 'E2-B0'), ('A1 双动量（对照）', 'A1'), ('v5.1（对照）', 'v5.1-对照'))):
    w = pd.read_csv(O / fold / 'criterion-1-windows.csv', parse_dates=['start', 'end']); w = w[w.months == 36]
    y = w.excess.values * 100
    ax.bar(w.start, y, width=22, color=[GOOD if v > 0 else BAD for v in y])
    ax.axvspan(pd.Timestamp('2023-11-01'), pd.Timestamp('2026-09-30'), color='#f1f5f9', zorder=-1)
    ax.text(pd.Timestamp('2025-03-15'), ax.get_ylim()[0] * .55 if ax.get_ylim()[0] < -3 else 1, '这段买入的\n还没持满 3 年', ha='center', fontsize=9.5, color=MUTED)
    ax.axhline(0, color=INK, lw=.8); ax.grid(axis='y', alpha=.18)
    ax.set_title(f'{arm} · 跑赢 {(y > 0).mean() * 100:.0f}% 的起点 · 中位数 {np.median(y):+.1f}', loc='left', fontsize=12, weight='bold', color=ARMC[arm.split('（')[0].replace(' 双动量', '')])
    ax.set_ylabel('每年多（少）赚\n（百分点）', color=MUTED, fontsize=10)
axs[-1].set_xlim(pd.Timestamp('2015-11-01'), pd.Timestamp('2026-10-31'))
title(fig, '检验段每个月初买入、持有 3 年：E2 新口径只有 2020 年底到 2021 年买入才赢；A1 2020 年以后买入多数赢；v5.1 几乎全输',
      '横轴 = 买入月份，最后一个持满 3 年的起点是 2023-10（持有到 2026-09）；灰底以后买入的还没满 3 年。能排名的池子，94 个起点。')
fig.tight_layout(); fig.savefig(OS / 'o6-bars.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# o2 逐年超额：三个
def net(p): return pd.read_csv(p, parse_dates=['date']).set_index('date').net
S = pd.DataFrame({'E2 新口径': net(O / 'E2-B0/net.csv'), 'A1': net(O / 'A1/net.csv'), 'v5.1': net(O / 'v5.1-对照/net.csv'), '基准': net(ROOT / 'results/v5/oneshot/benchmarks/BM-main/net.csv')}).fillna(0)
yr = (1 + S).groupby(S.index.year).prod() - 1; ex = yr[list(A3)].sub(yr['基准'], axis=0) * 100
fig, ax = plt.subplots(figsize=(13.5, 4.8)); x = np.arange(len(ex)); w = .27
for j, arm in enumerate(A3):
    ax.bar(x + (j - 1) * w, ex[arm], w, color=ARMC[arm], label=arm)
ax.axhline(0, color=INK, lw=.9); ax.set_xticks(x); ax.set_xticklabels([f'{y}' + ('\n(到 9 月)' if y == 2026 else '') for y in ex.index]); ax.set_ylabel('比基准多（少）赚，百分点', color=MUTED); ax.grid(axis='y', alpha=.22); ax.legend(frameon=False, ncol=3, loc='lower left')
title(fig, '逐年比基准：E2 新口径只赢 2018、2022 两个下跌年；A1 赢 6 年；v5.1 赢的 4 年都是下跌或震荡年，2019 年一年就少 47 个点',
      '每年 E2 新口径（蓝）、A1（橙）、v5.1（红）减基准的收益。能排名的池子，扣费后。')
fig.tight_layout(); fig.savefig(OS / 'o2-yearly.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
print((ex > 0).sum().to_dict())
# o3 持仓结构：三个
fig, axs = plt.subplots(1, 3, figsize=(15, 4.8), sharey=True)
G2 = {'A股': ('A股宽基', 'A股行业'), '美股宽基': ('美股宽基',), '海外主题': ('海外主题',), '港股': ('港股',), '债券': ('债券',), '黄金商品': ('黄金', '商品'), '现金': ('现金',)}
C2 = {'A股': '#1d4ed8', '美股宽基': '#c2410c', '海外主题': '#fdba74', '港股': '#7c3aed', '债券': '#94a3b8', '黄金商品': '#eab308', '现金': '#e5e7eb'}
for ax, (arm, fold) in zip(axs, (('E2 新口径', 'E2-B0'), ('A1', 'A1'), ('v5.1', 'v5.1-对照'))):
    h = pd.read_csv(O / fold / 'held.csv', parse_dates=['date']).set_index('date')
    g = h.T.groupby(group).sum().T
    yrs = g.groupby(g.index.year).mean() * 100; bottom = np.zeros(len(yrs))
    for k, gs in G2.items():
        v = sum(yrs[c] for c in gs if c in yrs) if any(c in yrs for c in gs) else pd.Series(0, index=yrs.index)
        ax.bar(yrs.index, v, bottom=bottom, color=C2[k], width=.75, label=k); bottom += np.asarray(v, dtype=float)
    us = g['美股宽基'] if '美股宽基' in g else pd.Series([0.0])
    ax.set_title(f'{arm}：美股宽基平均 {float(us.mean() * 100):.0f}%（基准 30%）', loc='left', fontsize=11.5, weight='bold', color=ARMC[arm]); ax.set_ylim(0, 100)
axs[0].set_ylabel('平均仓位 %', color=MUTED)
h, l = axs[0].get_legend_handles_labels(); fig.legend(h, l, frameon=False, ncol=7, loc='lower center', bbox_to_anchor=(.5, -.05))
title(fig, '钱放在哪：E2 新口径和 v5.1 把三四成放在海外主题、两三成放在债券；A1 一大半在美股宽基',
      '检验段每年的平均持仓结构，能排名的池子。基准是 70% 沪深300 + 30% 美股。')
fig.tight_layout(rect=(0, .05, 1, 1)); fig.savefig(OS / 'o3-exposure.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
