"""第二阶段复盘的图。读 attribution.json、签收结果和行情（不算新的组合收益）。
用法：python results/v5/report/retro_charts.py <attr.pkl> <ref.pkl>
"""
import sys, json, pickle, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False, 'axes.spines.right': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED = '#151b26', '#5d6676'
OUT = ROOT / 'docs/assets/retro'; J = json.loads((ROOT / 'results/v5/report/attribution.json').read_text())
GC = {'A股宽基': '#1d4ed8', 'A股行业': '#60a5fa', '港股': '#7c3aed', '美股宽基': '#c2410c', '海外主题': '#fdba74', '债券': '#94a3b8', '黄金': '#eab308', '商品': '#0d9488', '现金': '#e5e7eb'}
def title(fig, t, s):
    h = fig.get_figheight(); fig.text(.06, 1 + .42 / h, t, fontsize=14.5, weight='bold', color=INK); fig.text(.06, 1 + .12 / h, s, fontsize=10.5, color=MUTED)
# r1 收益从哪来：E2 三段 + 基准三段
segs = [('E2 新口径\n2006–10', J['E2设计_前五年']), ('E2 新口径\n2011–15', J['E2设计_后五年']), ('E2 新口径\n2016–26', J['E2检验'])]
ref = pd.read_pickle(sys.argv[2])
bm = []
for nm, a, b in (('基准\n2006–10', '2006', '2010'), ('基准\n2011–15', '2011', '2015'), ('基准\n2016–26', '2016', '2026')):
    x = ref.loc[a:b]; yrs = len(x) / 252
    bm.append((nm, {'A股宽基': {'贡献_每年': float(x.H00300.sum() * .7 / yrs * 100)}, '美股宽基': {'贡献_每年': float((x.XNDX + x.SP500TR).sum() * .15 / yrs * 100)}}))
order = ['E2 新口径\n2006–10', '基准\n2006–10', 'E2 新口径\n2011–15', '基准\n2011–15', 'E2 新口径\n2016–26', '基准\n2016–26']
allseg = dict(segs + bm)
fig, ax = plt.subplots(figsize=(13, 5.4)); x = np.arange(len(order))
for i, k in enumerate(order):
    pos = neg = 0
    for g, col in GC.items():
        v = allseg[k].get(g, {}).get('贡献_每年', 0)
        if abs(v) < .05: continue
        if v >= 0: ax.bar(i, v, bottom=pos, color=col, width=.62, label=g if i == 0 or g not in [h.get_label() for h in ax.patches] else None); pos += v
        else: ax.bar(i, v, bottom=neg, color=col, width=.62); neg += v
    ax.text(i, pos + .6, f'{sum(v.get("贡献_每年", 0) for v in allseg[k].values()):.1f}', ha='center', fontsize=11, weight='bold', color=INK)
h, l = ax.get_legend_handles_labels(); seen = {}
for hh, ll in zip(h, l):
    if ll and ll not in seen: seen[ll] = hh
ax.legend(seen.values(), seen.keys(), frameon=False, ncol=5, loc='upper right', fontsize=10)
ax.set_xticks(x); ax.set_xticklabels(order); ax.axhline(0, color=INK, lw=.9); ax.set_ylabel('每年贡献的收益（百分点，扣费前）', color=MUTED); ax.grid(axis='y', alpha=.2)
for i in (1.5, 3.5): ax.axvline(i, color=MUTED, lw=.6, ls=':')
title(fig, '收益从哪来：设计期前五年 E2 和基准都靠 A 股；检验段基准六成靠美股，E2 的钱却分在海外主题和债券上',
      '能排名的池子。E2 新口径 = 每天持仓 × 各容器当天收益，按大类加总（与扣费前净值的相关系数 1.00）。基准按 70/15/15 拆。柱顶数字 = 合计。')
fig.tight_layout(); fig.savefig(OUT / 'r1-sources.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# r2 池子构成
P = J['池子构成']; years = sorted(int(y) for y in P)
fig, ax = plt.subplots(figsize=(13, 4.6)); bottom = np.zeros(len(years))
for g, col in GC.items():
    v = np.array([P[str(y)].get(g, 0) for y in years], dtype=float)
    if v.sum() == 0: continue
    ax.bar(years, v, bottom=bottom, color=col, label=g, width=.75); bottom += v
for y, t in zip(years, bottom): ax.text(y, t + 1.5, f'{int(t)}', ha='center', fontsize=9.5, color=INK)
ax.axvspan(2005.5, 2015.5, color='#f1f5f9', zorder=-1); ax.text(2010.5, bottom.max() * .92, '设计期', ha='center', color=MUTED, fontsize=11)
ax.text(2021, bottom.max() * .92, '一次性检验段', ha='center', color=MUTED, fontsize=11)
ax.set_ylabel('当年有数据的容器数', color=MUTED); ax.legend(frameon=False, ncol=9, fontsize=9.5, loc='upper left', bbox_to_anchor=(0, -.08)); ax.grid(axis='y', alpha=.2)
title(fig, '测的不是同一个池子：设计期 18–26 个、以 A 股为主；检验段涨到 102 个，七成是海外主题',
      '能排名的池子里每年有行情的容器数（当年过半交易日有收益）。这在跑任何回测之前就能数出来。')
fig.tight_layout(); fig.savefig(OUT / 'r2-pool.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
# r3 选强的本事：风险资产部分 vs 当天全部可选风险容器等权
d = pickle.load(open(sys.argv[1], 'rb')); pnl = d['pnl_all']; pnl.index = pd.to_datetime(pnl.index)
from results_v5_group import group  # noqa
hd = d['held_design'].loc['2006':'2015']; ho = pd.read_csv(ROOT / 'results/v5/oneshot/index/E2-B0/held.csv', parse_dates=['date']).set_index('date')
def sel(h):
    h = h.copy(); h.index = pd.to_datetime(h.index)
    risk = [c for c in h.columns if c in pnl.columns and group(c) not in ('现金', '债券', '黄金')]
    r = pnl.reindex(index=h.index, columns=risk); w = h[risk]; tot = w.sum(axis=1)
    sleeve = (w * r.fillna(0)).sum(axis=1) / tot.where(tot > .05)
    ew = r.where(r.notna() & (r != 0)).mean(axis=1)
    return (sleeve - ew).dropna()
s = pd.concat([sel(hd), sel(ho)]); y = s.groupby(s.index.year).sum() * 100
fig, ax = plt.subplots(figsize=(13, 4.2))
ax.bar(y.index, y.values, color=['#16a34a' if v > 0 else '#ea580c' for v in y.values], width=.7)
for xx, v in zip(y.index, y.values): ax.text(xx, v + (.6 if v >= 0 else -.6), f'{v:+.0f}', ha='center', va='bottom' if v >= 0 else 'top', fontsize=9.5)
ax.axhline(0, color=INK, lw=.9); ax.axvspan(2005.5, 2015.5, color='#f1f5f9', zorder=-1); ax.grid(axis='y', alpha=.2)
ax.set_ylabel('比等权多（少）赚，百分点', color=MUTED)
d1 = sel(hd); d2 = sel(ho)
ax.text(2010.5, y.min() * .85, f'设计期平均每年 {d1.mean() * 252 * 100:+.1f}', ha='center', color=INK, fontsize=11, weight='bold')
ax.text(2022.5, y.min() * .85, f'检验段平均每年 {d2.mean() * 252 * 100:+.1f}', ha='center', color=INK, fontsize=11, weight='bold')
title(fig, '“挑哪一只”的本事一直接近 0：设计期每年只比闭眼等权多 1 个点，检验段 0.4 个点',
      'E2 新口径股票类持仓的收益，减去当天所有可选股票类容器的等权收益（不含债券、黄金、现金）。能排名的池子，扣费前。')
fig.tight_layout(); fig.savefig(OUT / 'r3-selection.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
print('ok', round(d1.mean() * 252 * 100, 2), round(d2.mean() * 252 * 100, 2))
