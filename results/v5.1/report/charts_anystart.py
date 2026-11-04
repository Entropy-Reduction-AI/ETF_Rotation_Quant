"""v5.1 任意起点的图（读 health.py 的输出）。m21 跑赢比例；m22 每个起点持有 5 年的年化超额。
用法：python results/v5.1/report/charts_anystart.py docs/assets/v5-memo
"""
import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[3]
import pandas as pd, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False, 'axes.spines.right': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, BLUE, GREY, BAD, GOOD, A1C = '#151b26', '#5d6676', '#1d4ed8', '#9ca3af', '#c2410c', '#15803d', '#d97706'
OUT = pathlib.Path(sys.argv[1]); R = ROOT / 'results/v5.1/report'; H = json.loads((R / 'health.json').read_text())
def title(fig, t, s):
    h = fig.get_figheight(); fig.text(.06, 1 + .42 / h, t, fontsize=14.5, weight='bold', color=INK); fig.text(.06, 1 + .12 / h, s, fontsize=10.5, color=MUTED)
vs = ['基准', '沪深300', '标普500', '纳指100', 'E2 新口径', 'A1']
fig, axs = plt.subplots(1, 2, figsize=(13, 4.8), sharey=True)
for ax, pool, nm in zip(axs, ('index', 'tradable'), ('能排名的池子（U-指数）', '能买到的池子（U-可交易）')):
    x = np.arange(len(vs)); w = .26
    for j, (y, c) in enumerate(((1, '#cbd5e1'), (3, '#93c5fd'), (5, BLUE))):
        vals = [H[pool]['任意起点'][f'{y}年'][k]['跑赢'] for k in vs]
        b = ax.bar(x + (j - 1) * w, vals, w, color=c, label=f'持有 {y} 年')
        if y == 5:
            for xi, v in zip(x, vals): ax.text(xi + w, v + 2, f'{v:.0f}', ha='center', fontsize=10, color=INK, weight='bold')
    ax.axhline(60, color=BAD, lw=1.2, ls='--'); ax.text(len(vs) - .5, 62, '期望线 60%', color=BAD, fontsize=9.5, ha='right')
    ax.set_xticks(x); ax.set_xticklabels(vs, fontsize=10.5); ax.set_title(nm, loc='left', fontsize=12.5, weight='bold', color=INK); ax.set_ylim(0, 110); ax.grid(axis='y', alpha=.22)
axs[0].set_ylabel('v5.1 跑赢的起点占比 %', color=MUTED); axs[0].legend(frameon=False, fontsize=10, loc='lower left')
title(fig, '任意月初买入：能排名的池子几乎每个起点都赢；能买到的池子，持有 5 年只有三成多起点赢基准',
      '2006–2015 每个月第一个交易日买入，分别持有 1、3、5 年，比较年化收益。深蓝柱上的数字 = 持有 5 年跑赢的起点占比。')
fig.tight_layout(); fig.savefig(OUT / 'm21-v51-anystart.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
fig, axs = plt.subplots(1, 2, figsize=(13, 4.6), sharey=True)
for ax, pool, nm in zip(axs, ('index', 'tradable'), ('能排名的池子', '能买到的池子')):
    A = pd.read_csv(R / f'anystart-{pool}.csv', parse_dates=['start']); A = A[A.yrs == 5]
    for k, c, lw in (('基准', GREY, 2.6), ('E2 新口径', BLUE, 1.8), ('A1', A1C, 1.8)):
        g = A[A.vs == k]; ax.plot(g.start, g['diff'], color=c, lw=lw, label=f'v5.1 减 {k}')
    ax.axhline(0, color=INK, lw=.9); ax.set_title(nm, loc='left', fontsize=12.5, weight='bold', color=INK); ax.grid(axis='y', alpha=.22)
axs[0].set_ylabel('持有 5 年的年化超额（百分点）', color=MUTED); axs[0].legend(frameon=False, fontsize=10)
title(fig, '起点决定输赢：在顶部附近买入（2007 下半年、2008）v5.1 赢；在牛市开头或底部买入（2006、2009）就输',
      '横轴 = 买入月份（2006-01 到 2010-12），纵轴 = 持有 5 年 v5.1 比对手每年多（少）多少。0 线以上 = v5.1 赢。')
fig.tight_layout(); fig.savefig(OUT / 'm22-v51-anystart-path.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# m23 两次急跌：从沪深300 见顶算起，净值和 v5.1 的风险仓位
import sys as _s; _s.path.insert(0, str(ROOT))
from src.v3.engine.spec import load_spec
from src.v4.r5.design import Markets
R0 = ROOT / 'results'
def rd(f, col=None):
    d = pd.read_csv(f, parse_dates=[0], index_col=0); return d[col] if col else d.iloc[:, 0]
dd = pd.read_csv(R0 / 'v5.1/design/index/daily.csv', parse_dates=['date']).set_index('date')
cs = Markets(load_spec()).get('index', t4=False, allow_substitute=True).signal['csi300']
D = pd.DataFrame({'v5.1': dd.net, 'E2 新口径': rd(R0 / 'v4/r5/design/B0/index/net.csv'), 'A1': rd(R0 / 'v4/r5/design/A1/index/net.csv'), '沪深300': cs}).loc['2006':'2015'].fillna(0)
fig, axs = plt.subplots(2, 2, figsize=(13, 6.2), sharex='col', gridspec_kw={'height_ratios': [2.3, 1]})
for j, (nm, a, b) in enumerate((('2008：沪深300 从 2007-10-16 见顶', '2007-10-16', '2008-11-04'), ('2015：沪深300 从 2015-06-12 见顶', '2015-06-12', '2015-09-15'))):
    w = D.loc[a:b]; nav = (1 + w).cumprod(); nav = nav / nav.iloc[0]; x = np.arange(len(w))
    ax = axs[0, j]
    for c, col, lw in (('v5.1', BAD, 2.8), ('E2 新口径', BLUE, 1.8), ('A1', A1C, 1.8), ('沪深300', GREY, 1.8)):
        ax.plot(x, (nav[c] - 1) * 100, color=col, lw=lw); ax.text(x[-1] + 2, (nav[c].iloc[-1] - 1) * 100 + (3 if (c == 'A1' and j == 1) else 0), f'{c} {(nav[c].iloc[-1] - 1) * 100:+.0f}%', color=col, fontsize=10, va='center', weight='bold' if c == 'v5.1' else None)
    ax.axhline(0, color=GREY, lw=.8); ax.set_title(nm, loc='left', fontsize=12.5, weight='bold', color=INK); ax.grid(axis='y', alpha=.22); ax.set_xlim(0, len(x) * 1.22)
    bx = axs[1, j]; rk = dd.risk.loc[a:b].values * 100
    bx.fill_between(x, rk, color=BAD, alpha=.25, lw=0); bx.plot(x, rk, color=BAD, lw=1.2); bx.set_ylim(0, 105); bx.grid(axis='y', alpha=.22)
    bx.set_xlabel('见顶后的交易日', color=MUTED)
axs[0, 0].set_ylabel('从见顶日起 %', color=MUTED); axs[1, 0].set_ylabel('v5.1 风险仓位 %', color=MUTED)
title(fig, '两次急跌：2008 年 v5.1 只亏 5%；2015 年满仓吃了前 5 天的 −13%，之后三次买回，最后一次撞上 8 月第二波',
      '能排名的池子，扣费后。下排 = v5.1 每天收盘时的风险资产仓位（其余在国债、黄金或现金）。')
fig.tight_layout(); fig.savefig(OUT / 'm23-v51-crash.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
