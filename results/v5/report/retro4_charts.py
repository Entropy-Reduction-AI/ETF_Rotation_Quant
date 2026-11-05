"""复盘第 4 版的图：按“地区”分组（config/v5/classes.csv），美股主题算美股、港股主题算港股。
r1-sources（三段收益来源）、r2-pool（池子每年的容器数）、o3-exposure（检验段持仓结构）。
用法：python results/v5/report/retro4_charts.py <attr.pkl> <peers_design.pkl> <ref.pkl>
"""
import sys, pickle, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
import pandas as pd, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False, 'axes.spines.right': False, 'font.size': 11, 'axes.edgecolor': '#9ca3af'})
INK, MUTED = '#151b26', '#5d6676'
ARMC = {'E2 新口径': '#1d4ed8', 'A1': '#d97706', 'v5.1': '#c2410c', '基准': INK}
CLS = pd.read_csv(ROOT / 'config/v5/classes.csv').set_index('container_id')['class'].to_dict()
def reg(c):
    if c == 'cash': return '现金'
    k = CLS.get(c, '其他')
    if k == '美股': return '美股宽基' if c in ('spx', 'ndx100') else '美股主题'
    if k in ('黄金', '商品'): return '黄金商品'
    return k
GC = {'A股': '#1d4ed8', '美股宽基': '#c2410c', '美股主题': '#fdba74', '港股': '#7c3aed', '其他海外': '#14b8a6', '国债': '#94a3b8', '黄金商品': '#eab308', '现金': '#e5e7eb'}
d = pickle.load(open(sys.argv[1], 'rb')); pdz = pickle.load(open(sys.argv[2], 'rb')); ref = pd.read_pickle(sys.argv[3])
pnl = d['pnl_all']; pnl.index = pd.to_datetime(pnl.index)
O = ROOT / 'results/v5/oneshot/index'
def rh(p): return pd.read_csv(p, parse_dates=['date']).set_index('date')
H = {'E2 新口径': (d['held_design'], rh(O / 'E2-B0/held.csv')), 'A1': (pdz['A1']['held'], rh(O / 'A1/held.csv')),
     'v5.1': (rh(ROOT / 'results/v5.1/design/index/held.csv'), rh(O / 'v5.1-对照/held.csv'))}
RET, OS = ROOT / 'docs/assets/retro', ROOT / 'docs/assets/v5-oneshot'
def title(fig, t, s):
    h = fig.get_figheight(); fig.text(.05, 1 + .42 / h, t, fontsize=14.5, weight='bold', color=INK); fig.text(.05, 1 + .12 / h, s, fontsize=10.5, color=MUTED)
def contrib(h, a, b):
    h = h.copy(); h.index = pd.to_datetime(h.index); h = h.loc[a:b]
    cols = [c for c in h.columns if c in pnl.columns or c == 'cash']
    c = h[cols] * pnl.reindex(index=h.index, columns=cols).fillna(0)
    return (c.T.groupby(reg).sum().T.sum() / (len(c) / 252) * 100).to_dict()
# r1
SEG = (('2006–2010', '2006', '2010', 0), ('2011–2015', '2011', '2015', 0), ('2016–2026（检验段）', '2016', '2026', 1))
fig, axs = plt.subplots(1, 3, figsize=(14, 5.2), sharey=True)
for ax, (nm, a, b, k) in zip(axs, SEG):
    x = ref.loc[a:b]; A = x.H00300.sum() / len(x) * 252 * 100; U = ((x.XNDX + x.SP500TR) / 2).sum() / len(x) * 252 * 100
    for i, arm in enumerate(list(H) + ['基准']):
        parts = {'A股': .7 * A, '美股宽基': .3 * U} if arm == '基准' else contrib(H[arm][k], a, b)
        pos = neg = 0
        for g, col in GC.items():
            v = parts.get(g, 0)
            if abs(v) < .05: continue
            if v >= 0: ax.bar(i, v, bottom=pos, color=col, width=.66, label=g); pos += v
            else: ax.bar(i, v, bottom=neg, color=col, width=.66); neg += v
        ax.text(i, pos + .8, f'{sum(parts.values()):.1f}', ha='center', fontsize=10.5, weight='bold', color=ARMC[arm])
    ax.set_xticks(range(4)); ax.set_xticklabels(list(H) + ['基准'], fontsize=10.5); ax.axhline(0, color=INK, lw=.8); ax.grid(axis='y', alpha=.2)
    ax.set_title(nm, loc='left', fontsize=12, weight='bold', color=INK)
seen = {}
for a_ in axs:
    for hh, ll in zip(*a_.get_legend_handles_labels()): seen.setdefault(ll, hh)
seen = {k: seen[k] for k in GC if k in seen}
fig.legend(seen.values(), seen.keys(), frameon=False, ncol=8, loc='lower center', bbox_to_anchor=(.5, -.04), fontsize=10)
axs[0].set_ylabel('每年贡献的收益（百分点，扣费前）', color=MUTED)
title(fig, '收益从哪来：设计期三个策略都靠 A 股（深蓝）；检验段基准靠美股，三个策略的 A 股都不再赚钱',
      '按地区分组：美股主题算美股（浅橙），港股主题和中概算港股。每天持仓 × 各容器当天收益（和扣费前净值相关系数 1.00）。柱顶 = 合计。')
fig.tight_layout(rect=(0, .04, 1, 1)); fig.savefig(RET / 'r1-sources.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# r2 池子：能排名的池子每年有行情的容器数（当年过半交易日有收益）
uni = [c for c in pnl.columns if c in CLS or c == 'cash']
live = pnl[uni].notna() & (pnl[uni] != 0)
cnt = live.groupby(live.index.year).mean() > .5
years = [y for y in cnt.index if 2006 <= y <= 2026]
fig, ax = plt.subplots(figsize=(13, 4.6)); bottom = np.zeros(len(years))
for g, col in GC.items():
    v = np.array([sum(cnt.loc[y, c] for c in uni if reg(c) == g) for y in years], dtype=float)
    if v.sum() == 0: continue
    ax.bar(years, v, bottom=bottom, color=col, label=g, width=.75); bottom += v
for y, t in zip(years, bottom): ax.text(y, t + 1.5, f'{int(t)}', ha='center', fontsize=9.5, color=INK)
ax.axvspan(2005.5, 2015.5, color='#f1f5f9', zorder=-1); ax.text(2010.5, bottom.max() * .92, '设计期', ha='center', color=MUTED, fontsize=11)
ax.text(2021, bottom.max() * .92, '检验段', ha='center', color=MUTED, fontsize=11)
ax.set_ylabel('当年有行情的容器数', color=MUTED); ax.legend(frameon=False, ncol=8, fontsize=9.5, loc='upper left', bbox_to_anchor=(0, -.08)); ax.grid(axis='y', alpha=.2)
us = [sum(cnt.loc[y, c] for c in uni if reg(c) in ('美股主题',)) for y in years]; hk = [sum(cnt.loc[y, c] for c in uni if reg(c) == '港股') for y in years]
title(fig, f'测的不是同一个池子：设计期 {int(bottom[:10].min())}–{int(bottom[:10].max())} 个、以 A 股为主；检验段涨到 {int(bottom[-1])} 个，新增的多是港股主题和美股主题',
      '能排名的池子里每年有行情的容器数（当年过半交易日有收益），按地区分组。每个主题从第一只 ETF 上市那天才进池子。这在跑任何回测之前就能数出来。')
fig.tight_layout(); fig.savefig(RET / 'r2-pool.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
print('pool', dict(zip(years, bottom.astype(int))), 'us theme', us[-1], 'hk', hk[-1])
# o3 持仓结构（检验段）
fig, axs = plt.subplots(1, 3, figsize=(15, 4.8), sharey=True)
for ax, arm in zip(axs, H):
    h = H[arm][1]; g = h.T.groupby(reg).sum().T
    yrs = g.groupby(g.index.year).mean() * 100; bottom = np.zeros(len(yrs))
    for k, col in GC.items():
        v = yrs[k] if k in yrs else pd.Series(0.0, index=yrs.index)
        ax.bar(yrs.index, v, bottom=bottom, color=col, width=.75, label=k); bottom += np.asarray(v, dtype=float)
    ub = float(g.get('美股宽基', pd.Series([0.0])).mean() * 100); ut = float(g.get('美股主题', pd.Series([0.0])).mean() * 100)
    ax.set_title(f'{arm}：美股 {ub + ut:.0f}%（宽基 {ub:.0f} + 主题 {ut:.0f}）', loc='left', fontsize=11.5, weight='bold', color=ARMC[arm]); ax.set_ylim(0, 100)
axs[0].set_ylabel('平均仓位 %', color=MUTED)
hh, ll = axs[0].get_legend_handles_labels(); fig.legend(hh, ll, frameon=False, ncol=8, loc='lower center', bbox_to_anchor=(.5, -.05))
title(fig, '钱放在哪：按地区算，三个都拿了美股（基准 30%）；A1 拿的全是标普，E2 新口径和 v5.1 的美股六成是主题',
      '检验段每年的平均持仓结构，能排名的池子。美股主题 = 能源、石油、REIT、生物科技、信息科技、半导体等。')
fig.tight_layout(rect=(0, .05, 1, 1)); fig.savefig(OS / 'o3-exposure.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
