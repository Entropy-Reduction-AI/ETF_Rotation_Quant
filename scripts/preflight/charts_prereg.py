"""v6 预注册页面的图（数字全部照抄预注册正文，不读收益、不重算）。
用法：python scripts/preflight/charts_prereg.py docs/assets/v6-prereg
p1：§3.4 事前预判 → 四条判据各自的事先通过机会；p2：附表 A 的发布日 → A 股可参选候选个数逐年。
样式与 charts_v3.py 相同。
"""
import sys, pathlib
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt

OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, GREY, TEAL, AMBER = '#151b26', '#5d6676', '#9ca3af', '#0d9488', '#d97706'


def title(fig, t, s):
    h = fig.get_figheight()
    fig.text(.04, 1 + .42 / h, t, fontsize=14.5, weight='bold', color=INK)
    fig.text(.04, 1 + .12 / h, s, fontsize=10.5, color=MUTED)


# ---------- p1：事前预判（§3.4 原文：约八成、约八成五、约六成、约五成；全部约三成；连续性版换上约两成） ----------
rows = [('① 底线：最大回撤不超过 −40%', 80, TEAL), ('② 保费：不超过 4 点', 85, TEAL),
        ('③ 年化 ÷ 回撤 高于增强基准', 60, TEAL), ('④ 不落后同仓位基准', 50, TEAL),
        ('四条全部通过', 30, INK), ('连续性版换上', 20, AMBER)]
fig, ax = plt.subplots(figsize=(11, 3.9))
for i, (lab, v, col) in enumerate(rows):
    y = len(rows) - 1 - i + (-.35 if i >= 4 else 0)
    ax.barh(y, 100, color='#eef0f3', height=.56)
    ax.barh(y, v, color=col, height=.56)
    ax.text(-2, y, lab, ha='right', va='center', color=INK, fontsize=11.5, weight='bold' if i == 4 else 'normal')
    ax.text(v + 1.5, y, f'约 {v}%', va='center', color=INK, fontsize=11.5, weight='bold' if i == 4 else 'normal')
ax.axhline(1.8 - .35 + .17, color=GREY, lw=.8, ls=(0, (3, 3)))
ax.set_xlim(0, 100); ax.set_xticks([]); ax.set_yticks([]); ax.spines['left'].set_visible(False); ax.spines['bottom'].set_visible(False)
title(fig, '四条判据要全过：单条约五到八成五，合起来约三成',
      '事前预判，写在 Owner 批准检验之前（§3.4），不影响规则；判据 ④ 对同仓位基准最难')
fig.savefig(OUT / 'p1-criteria.png', dpi=150, bbox_inches='tight'); plt.close(fig)

# ---------- p2：A 股可参选候选个数（附表 A 的发布日；一级行业按 D38 第 48 行用回填点位，从 2005 年起计） ----------
pub = {
    '宽基': ['2005-04-08', '2007-01-15', '2014-10-17', '2010-06-01', '2020-07-23'],
    '红利': ['2008-05-26', '2005-01-04', '2013-12-19'],
    '一级行业': ['2005-01-04'] * 10,
    '主题': ['2007-07-02', '2009-07-03', '2009-10-28', '2014-12-10', '2019-04-22',
             '2023-07-27', '2013-07-15', '2013-07-15', '2013-07-15', '2015-07-31', '2020-06-12',
             '2012-05-09', '2015-02-13', '2015-03-31',
             '2013-07-15', '2013-07-15', '2013-07-15',
             '2013-12-26', '2015-02-10', '2017-07-19', '2019-04-22', '2020-04-21'],
}
years = list(range(2005, 2027))
cols = {'宽基': '#64748b', '红利': '#a16207', '一级行业': TEAL, '主题': '#7c3aed'}
fig, ax = plt.subplots(figsize=(11, 4.2))
bottom = [0] * len(years)
for k, ds in pub.items():
    n = [sum(int(d[:4]) <= y for d in ds) for y in years]
    ax.bar(years, n, bottom=bottom, color=cols[k], width=.72, label=f'{k}（{len(ds)} 个）', edgecolor='white', linewidth=1.5)
    bottom = [a + b for a, b in zip(bottom, n)]
for y, b in zip(years, bottom):
    if y in (2005, 2010, 2015, 2016, 2020, 2026):
        ax.text(y, b + .6, str(b), ha='center', color=INK, fontsize=11, weight='bold')
ax.axvspan(2015.5, 2026.6, color='#fef3c7', alpha=.45, zorder=0)
ax.text(2021, 44.5, '检验段 2016–2026', ha='center', color='#92400e', fontsize=10.5)
ax.set_xticks([2005, 2010, 2015, 2020, 2026]); ax.set_ylim(0, 47); ax.set_ylabel('可参选个数（按发布日）', color=MUTED)
ax.grid(axis='y', alpha=.2); ax.legend(frameon=False, loc='upper left', fontsize=10.5)
title(fig, 'A 股候选随主题发布逐步增加：设计期末 33 个，检验段末 40 个',
      '附表 A 的参选起点；一级行业用回填点位（D38 第 48 行，Owner 2026-11-24），从 2005 年起计；半导体材料设备从首只基金上市 2023-07-27 起；细分化工不参选；参选还要满 12 个月')
fig.savefig(OUT / 'p2-a-pool.png', dpi=150, bbox_inches='tight'); plt.close(fig)
