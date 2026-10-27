"""Owner 看板图表。数据：探索脚本重建（series.pkl / weights.pkl）+ 正式复跑产物（P1/P6）+ BM-主。"""
import pickle, numpy as np, pandas as pd, matplotlib, os
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

OUT = os.environ.get('OUT', 'out'); os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({
    'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False,
    'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True,
    'grid.alpha': .22, 'grid.linewidth': .8, 'font.size': 11.5,
    'axes.edgecolor': '#9ca3af', 'xtick.color': '#374151', 'ytick.color': '#374151',
})
INK, MUTED = '#111827', '#6b7280'
C = {'基准': '#111827', 'v3': '#9ca3af', 'E1': '#60a5fa', 'E2': '#1d4ed8', 'E3': '#f59e0b'}
# 版本标签：与看板第 3 节定义表一致（数字取原探索记录，曲线为重建）
LAB = {'基准': ('基准', '15.4%', '−65%'), 'v3': ('v3', '12.6%', '−43%'),
       'E1': ('E1', '22.6%', '−44%'), 'E2': ('E2', '26.0%', '−37%')}

S = pickle.load(open('series.pkl', 'rb'))
W = pickle.load(open('weights.pkl', 'rb'))
bm = pickle.load(open('aux.pkl', 'rb'))[0]
P1 = pd.read_csv('P1-paths.csv', index_col=0, parse_dates=True)['executed']
P6 = pd.read_csv('P6-paths.csv', index_col=0, parse_dates=True)['executed']
H1 = pd.read_csv('P1-held.csv', index_col=0, parse_dates=True)['cash']
H6 = pd.read_csv('P6-held.csv', index_col=0, parse_dates=True)['cash']
A0, A1 = '2006-01-05', '2015-12-31'
ser = {'基准': bm, 'v3': S['v3'], 'E1': S['E1'], 'E2': S['exit10']}
nav = {k: (1 + v.loc[A0:A1]).cumprod() for k, v in ser.items()}
dd = {k: n / n.cummax() - 1 for k, n in nav.items()}

def title(ax, t, sub=None, y=1.0):
    ax.set_title(t, loc='left', fontsize=14.5, weight='bold', color=INK, pad=28 if sub else 12)
    if sub: ax.text(0, 1.035, sub, transform=ax.transAxes, fontsize=10.5, color=MUTED, va='bottom')

def save(fig, name):
    fig.savefig(f'{OUT}/{name}.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)

# ---------- 图 1：v3 的钱在哪（2.1） ----------
A = ['沪深300', '中证500', '中证1000', '中证红利', '能源', '原材料', '工业', '可选消费', '主要消费', '医药', '金融地产', '信息技术', '通信', '公用事业']
def groups(Wk):
    g = pd.DataFrame({'A股': Wk.reindex(columns=A, fill_value=0).sum(axis=1), '港股': Wk.get('恒生指数', 0),
                      '美股': Wk.get('纳指100', 0) + Wk.get('标普500', 0), '现金': Wk['cash']})
    return g.loc['2006':'2015'].groupby(g.loc['2006':'2015'].index.year).mean() * 100
g3, g1 = groups(W['v3']), groups(W['E1'])
c3 = W['avail_v3'].groupby(W['avail_v3'].index.year).mean(); c1 = W['avail_full'].groupby(W['avail_full'].index.year).mean()
fig, axs = plt.subplots(1, 2, figsize=(12, 4.9), sharey=True, gridspec_kw=dict(wspace=.06))
for ax, g, c, nm in [(axs[0], g3, c3, 'v3：指数发布日之后才能选'), (axs[1], g1, c1, 'E1：行业指数用 2005 年起的官方回溯数据')]:
    x = np.arange(len(g)); bb = np.zeros(len(g))
    for k, col in zip(g.columns, ['#1d4ed8', '#a855f7', '#16a34a', '#d1d5db']):
        ax.bar(x, g[k], .66, bottom=bb, color=col, label=k, zorder=2); bb += g[k].values
    for i, v in enumerate(c.values): ax.text(i, 102.5, f'{v:.0f}', ha='center', fontsize=10, color='#374151')
    for i in (0, 1):
        cv = g['现金'].values[i]
        if cv > 12: ax.text(i, 100 - cv / 2, f"现金\n{cv:.0f}%", ha='center', va='center', fontsize=9.5, weight='bold', color='#111827', linespacing=1)
        else: ax.text(i, 104 + 0, '', ha='center')
    ax.set_xticks(x, [str(y)[2:] for y in g.index]); ax.set_ylim(0, 112); ax.set_yticks([0, 25, 50, 75, 100])
    ax.grid(axis='x', visible=False); ax.set_xlabel('年份（20xx）', fontsize=10, color=MUTED)
    ax.set_title(nm, loc='left', fontsize=12, weight='bold', color=INK, pad=22)
    ax.text(-.5, 108.5, '柱顶数字 = 当年能选几个', fontsize=9.5, color=MUTED)
    if nm.startswith('E1'): ax.annotate('现金只剩 4% 和 3%', xy=(0.5, 97), xytext=(2.2, 104.5), fontsize=10, weight='bold', color='#111827', arrowprops=dict(arrowstyle='->', color='#111827', lw=1))
axs[0].set_ylabel('全年平均仓位 %')
axs[1].legend(ncol=4, frameon=False, loc='upper center', bbox_to_anchor=(-.03, -.13), fontsize=10)
fig.suptitle('同一套规则，可选标的从 4–6 个变成 17 个，牛市里的现金从 60% 降到 4%', x=.125, ha='left', y=1.04, fontsize=14.5, weight='bold', color=INK)
save(fig, 'b1-positions')

# ---------- 图 2：E 系列净值 + 回撤（2.2） ----------
fig, (ax, ax2) = plt.subplots(2, 1, figsize=(11, 7.2), sharex=True, gridspec_kw=dict(height_ratios=[2.3, 1], hspace=.08))
order = ['基准', 'v3', 'E1', 'E2']
lw = {'基准': 2, 'v3': 2, 'E1': 2, 'E2': 2.6}
ax.axvspan(pd.Timestamp('2006-01-01'), pd.Timestamp('2007-12-31'), color='#dbeafe', alpha=.45, lw=0, zorder=0)
ax.axvspan(pd.Timestamp('2010-01-01'), pd.Timestamp('2014-10-31'), color='#f3f4f6', alpha=.8, lw=0, zorder=0)
ax.text(pd.Timestamp('2006-02-01'), 11.6, '超额主要来自这两年\n（A 股行业牛市）', fontsize=10, color='#1e40af', va='top')
ax.text(pd.Timestamp('2010-03-01'), 11.6, '2010–2014：和基准基本同步，没有明显超额', fontsize=10, color='#374151', va='top')
ends = {}
for k in order:
    n = nav[k]; ax.plot(n.index, n.values, color=C[k], lw=lw[k], zorder=3)
    ends[k] = n.iloc[-1]
# 末端标签（错开避免重叠）
ypos = {'E2': ends['E2'], 'E1': ends['E1'], '基准': ends['基准'] + .25, 'v3': ends['v3'] - .35}
for k in order:
    nm, ann, mdd = LAB[k]
    ax.text(pd.Timestamp('2016-01-25'), ypos[k], f'{nm}  {ends[k]:.1f} 元（+{(ends[k]-1)*100:.0f}%）\n年化 {ann}', color=C[k] if k != 'v3' else '#6b7280',
            fontsize=10.5, weight='bold', va='center', linespacing=1.15)
ax.set_ylabel('1 元变成多少'); ax.set_ylim(0, 12)
for k in order:
    ax2.plot(dd[k].index, dd[k].values * 100, color=C[k], lw=1.6 if k != 'E2' else 2.1, zorder=3)
# 最大回撤标注
spots = {'基准': (-65, '2008-10-28'), 'E2': (-37, '2015-09-15'), 'E1': (-44, '2015-09-15'), 'v3': (-43, '2015-09-15')}
for k in order:
    t = dd[k].idxmin(); v = dd[k].min() * 100
    ax2.plot([t], [v], 'o', color=C[k], ms=5, zorder=4)
off = {'基准': (25, -2), 'v3': (-118, -16), 'E1': (-150, 4), 'E2': (18, 6)}
for k in order:
    t = dd[k].idxmin(); v = dd[k].min() * 100
    ax2.annotate(f'{k} 最深 {LAB[k][2]}', xy=(t, v), xytext=off[k], textcoords='offset points', fontsize=9.5,
                 color=C[k] if k != 'v3' else '#6b7280', weight='bold')
ax2.set_ylabel('从最高点回落 %'); ax2.set_ylim(-75, 3)
ax2.set_xlim(pd.Timestamp('2006-01-01'), pd.Timestamp('2017-04-01'))
ax.legend(handles=[Line2D([], [], color=C[k], lw=2.4, label={'基准': '基准：70% 沪深300 + 15% 纳指 + 15% 标普', 'v3': 'v3：原规则',
          'E1': 'E1：v3 + 补全池子', 'E2': 'E2：E1 + 单只 10% 离场（已批准）'}[k]) for k in order],
          frameon=False, loc='upper left', bbox_to_anchor=(0, .86), fontsize=10)
title(ax, '补全池子让 v3 从跑输变成跑赢；再加 10% 离场，收益更高、回撤更浅',
      '设计期 2006-01 → 2015-12，扣成本；下图是同期每条线离自己最高点跌了多少。')
fig.text(0.125, 0.015, '曲线按原探索脚本重建。原黄金序列取不到，重建时去掉黄金；年化与原记录相差不超过 0.1 个百分点，标签用原记录数字。',
         fontsize=9, color=MUTED)
save(fig, 'b2-e-series')

# ---------- 图 3：离场阈值平台 + E3（2.3） ----------
labels = ['不离场\n(E1)', '8%', '10%\n(E2)', '12%', '15%', '组合波动\n减仓 (E3)']
ann = [22.6, 25.2, 26.0, 25.8, 23.8, 20.9]; mdd = [-43.9, -35.6, -37.2, -39.1, -43.5, -39.4]
cols = ['#93c5fd', '#3b82f6', '#1d4ed8', '#3b82f6', '#3b82f6', '#fbbf24']
fig, ax = plt.subplots(figsize=(11, 4.6))
xs = np.array([0, 1.25, 2.25, 3.25, 4.25, 5.6])
bars = ax.bar(xs, ann, .7, color=cols, zorder=2)
ax.axhline(22.6, color=MUTED, ls='--', lw=1, zorder=1); ax.axhline(15.4, color=INK, ls=':', lw=1.2, zorder=1)
ax.text(6.05, 22.6, '不离场', va='center', fontsize=9.5, color=MUTED, bbox=dict(fc='white', ec='none', pad=1)); ax.text(6.05, 15.4, '基准 15.4%', va='center', fontsize=9.5, color=INK, bbox=dict(fc='white', ec='none', pad=1))
for xx, a, m in zip(xs, ann, mdd):
    ax.text(xx, a + .5, f'{a:.1f}%', ha='center', fontsize=11.5, weight='bold', color=INK)
    ax.text(xx, 2.2, f'最深 {m:.0f}%', ha='center', fontsize=9.5, color='white', weight='bold')
ax.annotate('', xy=(4.6, 27.6), xytext=(0.9, 27.6), arrowprops=dict(arrowstyle='-', color='#1d4ed8', lw=1.4))
ax.text(2.75, 28.1, '单只离场：8%–15% 四档都比不离场好 → 是一片平台，不是一个尖峰', ha='center', fontsize=10.5, color='#1e40af')
ax.text(5.6, 24.2, '期望变低\n不采用', ha='center', fontsize=10, color='#b45309')
ax.set_xticks(xs, labels); ax.set_ylim(0, 31); ax.set_ylabel('设计期年化 %'); ax.grid(axis='x', visible=False)
ax.set_xlim(-.6, 6.6)
title(ax, '为什么是 10%：离场阈值换哪档都更好，10% 只是事先定下的整数',
      '柱高 = 设计期 2006–2015 年化；柱内 = 最大回撤。数字取自原探索记录。')
save(fig, 'b3-exit-plateau')

# ---------- 图 4：正式引擎复现 E2 + 逐年超额（2.4） ----------
f_nav = (1 + P1.loc[A0:A1]).cumprod(); e_nav = nav['E2']; b_nav = nav['基准']
fig, (ax, ax2) = plt.subplots(2, 1, figsize=(11, 7), gridspec_kw=dict(height_ratios=[1.7, 1], hspace=.32))
ax.plot(b_nav.index, b_nav, color=C['基准'], lw=2)
ax.plot(e_nav.index, e_nav, color=C['E2'], lw=2.2, alpha=.45)
ax.plot(f_nav.index, f_nav, color=C['E2'], lw=2.4)
ax.text(pd.Timestamp('2016-01-25'), e_nav.iloc[-1] + .35, f'E2 探索  {e_nav.iloc[-1]:.1f} 元\n年化 26.0% · 最深 −37%', color='#60a5fa', fontsize=10, weight='bold', va='center')
ax.text(pd.Timestamp('2016-01-25'), f_nav.iloc[-1] - .45, f'E2 正式  {f_nav.iloc[-1]:.1f} 元\n年化 25.1% · 最深 −34%', color=C['E2'], fontsize=10, weight='bold', va='center')
ax.text(pd.Timestamp('2016-01-25'), b_nav.iloc[-1], f'基准  {b_nav.iloc[-1]:.1f} 元\n年化 15.4% · 最深 −65%', color=INK, fontsize=10, weight='bold', va='center')
ax.set_xlim(pd.Timestamp('2006-01-01'), pd.Timestamp('2017-06-01')); ax.set_ylabel('1 元变成多少')
ax.legend(handles=[Line2D([], [], color=C['E2'], lw=2.4, label='E2 正式引擎（81 个指数、正式成本）'),
                   Line2D([], [], color=C['E2'], lw=2.2, alpha=.45, label='E2 探索（18 个序列）'),
                   Line2D([], [], color=INK, lw=2, label='基准')], frameon=False, loc='upper left', fontsize=10)
title(ax, '正式引擎复现了 E2，但十年超额几乎全部来自 2006–08 年',
      '上：设计期 2006-01 → 2015-12 累计。下：E2 正式版每年比基准多（少）赚多少个百分点。')
yr = (1 + P1.loc[A0:A1]).groupby(P1.loc[A0:A1].index.year).prod() - 1
yb = (1 + bm.loc[A0:A1]).groupby(bm.loc[A0:A1].index.year).prod() - 1
ex = (yr - yb) * 100
ax2.bar(ex.index, ex.values, .62, color=['#1d4ed8' if v > 0 else '#ef4444' for v in ex.values], zorder=2)
for xx, v in ex.items():
    ax2.text(xx, v + (2 if v > 0 else -2), f'{v:+.0f}', ha='center', va='bottom' if v > 0 else 'top', fontsize=10, color=INK)
ax2.axhline(0, color=INK, lw=.8); ax2.set_ylim(-52, 66); ax2.set_ylabel('超额（百分点）')
ax2.set_xticks(ex.index, [str(y) for y in ex.index]); ax2.grid(axis='x', visible=False)
ax2.text(2009.45, -40, '← 底部之后回场太慢，2009 上半年四成仓位还在现金、国债、黄金（见 3.5）', ha='left', fontsize=9.5, color='#b91c1c')
ax2.text(2013, 50, '2011–2015 按年化算只比基准多 0.8 个百分点', ha='center', fontsize=10, color='#374151',
         bbox=dict(fc='#f3f4f6', ec='none', pad=3))
save(fig, 'b4-formal')

# ---------- 图 5：研究池 vs 可交易池的现金（2.5） ----------
c1 = H1.loc['2006':'2015'].groupby(H1.loc['2006':'2015'].index.year).mean() * 100
c6 = H6.loc['2006':'2015'].groupby(H6.loc['2006':'2015'].index.year).mean() * 100
fig, ax = plt.subplots(figsize=(11, 4.4))
x = np.arange(len(c1))
ax.bar(x - .19, c1.values, .36, color=C['E2'], label='E2 正式 · 指数池（研究口径）', zorder=2)
ax.bar(x + .19, c6.values, .36, color='#d1d5db', label='E2 正式 · 可交易池（只能买当年已上市的 ETF）', zorder=2)
for i, (a, b_) in enumerate(zip(c1.values, c6.values)):
    ax.text(i + .19, b_ + 1.5, f'{b_:.0f}', ha='center', fontsize=9.5, color='#374151')
    ax.text(i - .19, a + 1.5, f'{a:.0f}', ha='center', fontsize=9.5, color=C['E2'])
ax.axvspan(6.55, 9.5, color='#ecfdf5', zorder=0)
ax.text(8.02, 110, '预注册里可交易池从 2013-07 才开始算', ha='center', fontsize=10, color='#047857')
ax.set_xticks(x, c1.index); ax.set_ylim(0, 118); ax.set_yticks([0, 25, 50, 75, 100]); ax.set_ylabel('全年平均现金 %')
ax.grid(axis='x', visible=False)
ax.legend(frameon=False, loc='upper center', bbox_to_anchor=(.5, -.08), ncol=2, fontsize=10)
title(ax, '可交易池：2013 年以前几乎买不到对应的 ETF，只能拿现金',
      '同一套规则跑两遍：蓝柱可以买指数，灰柱只能买当年已经上市的 ETF。灰柱越高，说明能买的越少。')
save(fig, 'b5-tradable')
print('ok', sorted(os.listdir(OUT)))
print('E2 recon end', round(e_nav.iloc[-1], 2), 'formal', round(f_nav.iloc[-1], 2), 'excess 11-15 mean', round(ex.loc[2011:2015].mean(), 1))

# ---------- 图 6：2009 年跑输的原因（3.5） ----------
H = pd.read_csv('P1-held.csv', index_col=0, parse_dates=True)
dfn = H[['cash', 'cgb-5y', 'cgb-10y', 'gold']].sum(axis=1)
ov = H[['ndx100', 'spx', 'hsi'] + [c for c in H.columns if c.startswith('theme-')]].sum(axis=1)
ash = 1 - dfn - ov
win = slice('2008-06-01', '2009-12-31')
fig, ax = plt.subplots(figsize=(11, 4.8))
xx = H.loc[win].index
ax.stackplot(xx, ash.loc[win] * 100, ov.loc[win] * 100, dfn.loc[win] * 100, colors=['#1d4ed8', '#16a34a', '#d1d5db'],
             labels=['A 股', '海外', '现金 + 国债 + 黄金'], zorder=2, alpha=.95)
ax.set_ylim(0, 100); ax.set_ylabel('E2 正式版仓位 %')
ax2 = ax.twinx(); ax2.spines['right'].set_visible(True)
hs = P['沪深300'] if 'P' in dir() else None
import pickle as _p
PP = _p.load(open('data.pkl', 'rb'))[0]['沪深300'].loc[win]
ax2.plot(PP.index, PP / PP.iloc[0], color=INK, lw=2.2, zorder=5, label='沪深300（右轴，期初 = 1）')
ax2.set_ylabel('沪深300（期初 = 1）', color=INK); ax2.grid(False); ax2.set_ylim(0.2, 1.3)
for d, t, y in [('2008-11-04', '沪深300 见底', 1.22), ('2009-03-02', '120 日信号转正', 1.22), ('2009-06-01', '250 日信号转正', 1.22)]:
    ax2.axvline(pd.Timestamp(d), color='#b91c1c', ls='--', lw=1.1, zorder=6)
    ax2.text(pd.Timestamp(d) + pd.Timedelta(days=4), y, t, color='#b91c1c', fontsize=10, va='top', bbox=dict(fc='white', ec='none', pad=1))
ax.text(pd.Timestamp('2008-11-25'), 70, '2009 上半年平均\n43% 在防守', fontsize=11, weight='bold', color='#111827', bbox=dict(fc='white', ec='none', alpha=.85, pad=2))
h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, ncol=4, frameon=False, loc='upper center', bbox_to_anchor=(.5, -.09), fontsize=10)
ax.set_xlim(xx[0], xx[-1])
title(ax, '2009 年为什么跑输：见底之后半年，四成仓位还在防守',
      '上半年策略 +22%，基准 +55%；下半年 +18% 对 +18%，打平。差距全在回场太慢。')
save(fig, 'b6-2009')

# ---------- 图 7：回场改进候选（3.5） ----------
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw=dict(wspace=.28))
nm = ['E2', 'C1\n快信号回场', 'C2\n准入看 60 日', '基准']
v1 = [28, 43, 50, 55]; v2 = [1.71, 1.69, 1.59]
cc = ['#1d4ed8', '#0891b2', '#7c3aed', '#111827']
a1.bar(range(4), v1, .62, color=cc, zorder=2)
for i, v in enumerate(v1): a1.text(i, v + 1.2, f'+{v}%', ha='center', fontsize=11, weight='bold', color=INK)
a1.set_xticks(range(4), nm, fontsize=10); a1.set_ylim(0, 64); a1.grid(axis='x', visible=False)
a1.set_title('2009 上半年收益：修好了', loc='left', fontsize=12, weight='bold', color='#15803d')
a2.bar(range(3), v2, .62, color=cc[:3], zorder=2)
for i, v in enumerate(v2): a2.text(i, v + .02, f'{v:.2f} 元', ha='center', fontsize=11, weight='bold', color=INK)
a2.set_xticks(range(3), nm[:3], fontsize=10); a2.set_ylim(1.0, 1.85); a2.grid(axis='x', visible=False)
a2.set_title('2011–2015 一元变成：没有帮助', loc='left', fontsize=12, weight='bold', color='#b91c1c')
fig.suptitle('回场改进只在 2009 这一次大底上有效，另一段没有改善', x=.125, ha='left', y=1.05, fontsize=14.5, weight='bold', color=INK)
fig.text(.125, .965, '两个候选都在 E2 上只改一处，跑之前写定。18 个序列复现口径，设计期 2006–2015。', fontsize=10.5, color=MUTED)
save(fig, 'b7-candidates')
