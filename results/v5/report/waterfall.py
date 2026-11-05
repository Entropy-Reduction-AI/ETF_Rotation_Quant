"""E2 新口径相对基准的差距拆解（瀑布图）。读 waterfall.json（attribution 同口径，每年算术贡献，扣费前，检验段另列成本）。
用法：python results/v5/report/waterfall.py
"""
import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
import numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False, 'axes.spines.right': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, GOOD, BAD, BASE = '#151b26', '#5d6676', '#16a34a', '#ea580c', '#475569'
W = json.loads((ROOT / 'results/v5/report/waterfall.json').read_text())
def title(fig, t, s):
    h = fig.get_figheight(); fig.text(.05, 1 + .42 / h, t, fontsize=14.5, weight='bold', color=INK); fig.text(.05, 1 + .12 / h, s, fontsize=10.5, color=MUTED)
def fall(ax, steps, name):
    x = 0; level = 0; labels = []
    for i, (lab, v, kind) in enumerate(steps):
        if kind == 'total':
            ax.bar(i, v, color=BASE if i == 0 else '#1d4ed8', width=.62); level = v
            ax.text(i, v + .6, f'{v:.1f}', ha='center', fontsize=11, weight='bold', color=INK)
        else:
            bottom = level if v >= 0 else level + v
            ax.bar(i, abs(v), bottom=bottom, color=GOOD if v >= 0 else BAD, width=.62)
            ax.text(i, level + v + (.6 if v >= 0 else -.6), f'{v:+.1f}', ha='center', va='bottom' if v >= 0 else 'top', fontsize=11, weight='bold', color=GOOD if v >= 0 else BAD)
            ax.plot([i - .31 - .38, i - .31], [level, level], color=MUTED, lw=.7, ls=':')
            level += v
        labels.append(lab)
    ax.set_xticks(range(len(steps))); ax.set_xticklabels(labels, fontsize=10)
    ax.axhline(0, color=INK, lw=.8); ax.grid(axis='y', alpha=.2); ax.set_title(name, loc='left', fontsize=12.5, weight='bold', color=INK)
s1, t = W['S1'], W['T']
fig, (a, b) = plt.subplots(1, 2, figsize=(13.5, 5.2), gridspec_kw={'width_ratios': [5, 8]})
fall(a, [('基准', s1['BM'], 'total'), ('A 股：躲开 2008\n偏中小盘、行业', s1['A_select'], 's'), ('A 股\n拿得少', s1['A_under'], 's'),
         ('美股', s1['US_under'] + s1['US_timing'], 's'), ('债券、黄金\n现金', s1['defense'], 's'), ('E2 新口径', s1['E2gross'], 'total')], '设计期前五年（2006–2010）：赢 15 个点，几乎全在 A 股')
fall(b, [('基准', t['BM'], 'total'), ('美股\n拿得太少', t['US_under'], 's'), ('美股\n进出时点', t['US_timing'], 's'), ('A 股\n拿得少', t['A_under'], 's'),
         ('A 股里\n拿错了', t['A_select'], 's'), ('海外主题', t['themes'], 's'), ('债券、黄金\n商品等', t['defense'], 's'), ('E2 新口径\n扣费前', t['E2gross'], 'total'),
         ('成本', -t['cost'], 's'), ('E2 新口径\n扣费后', t['E2gross'] - t['cost'], 'total')], '检验段（2016–2026）：输 6 个点，最大一块是美股拿得太少')
a.set_ylim(0, 47); b.set_ylim(-2.2, 11.8); a.set_ylabel('每年收益（百分点，算术口径）', color=MUTED)
title(fig, 'E2 新口径和基准差在哪：设计期赢在 A 股的大行情，检验段输在美股拿得太少、A 股又没赚到',
      '把 E2 新口径每天的持仓和基准逐大类比较：“拿得少”= 仓位比基准低乘以该类收益；其余是该类里拿什么、什么时候拿。每年算术贡献，和年化略有差别。')
fig.tight_layout(); fig.savefig(ROOT / 'docs/assets/retro/r4-gap.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
