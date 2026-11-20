"""预测表第 3 版的图（只读 results/v6-preflight 的结果文件，不重算）。
用法：python scripts/preflight/charts_v3.py docs/assets/v6-preflight
颜色：灰 = 参照（全市场、基准）；同一结构在所有图里颜色相同：新系统青绿、不设防守蓝、逐个门槛橙、增强基准紫。
"""
import sys, pathlib, json
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
ROOT = pathlib.Path(__file__).resolve().parents[2]; RES = ROOT / 'results/v6-preflight'
OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, GREY, BAD, GOOD = '#151b26', '#5d6676', '#9ca3af', '#c2410c', '#15803d'
C = {'新系统': '#0d9488', '不设防守': '#1d4ed8', '逐个门槛': '#d97706', '增强基准': '#7c3aed', '参照': '#6b7280'}
def title(fig, t, s):
    h = fig.get_figheight()
    fig.text(.04, 1 + .42 / h, t, fontsize=14.5, weight='bold', color=INK)
    fig.text(.04, 1 + .12 / h, s, fontsize=10.5, color=MUTED)
def fmt(v, d=1): return '0' if round(v, d) == 0 else f'{v:+.{d}f}'.replace('-', '−')

# ---------- f4：美国 70 年，选最强的 3 个行业 ----------
nav = pd.read_csv(RES / 'longhist-nav.csv', index_col=0, parse_dates=True)
fig, ax = plt.subplots(figsize=(12, 4.8))
spec = [('全市场', C['参照'], '一直持有全市场'), ('前3 逐个均线门槛', C['逐个门槛'], '前 3 + 逐个候选卡均线'),
        ('前3 按把握调节', C['新系统'], '前 3 + 按把握调节（v6）'), ('前3 不设防守', C['不设防守'], '前 3，不设防守')]
ann = {'全市场': '11.0%', '前3 逐个均线门槛': '15.2%', '前3 按把握调节': '16.2%', '前3 不设防守': '16.6%'}
for k, col, lab in spec:
    ax.plot(nav.index, nav[k], color=col, lw=2.2 if k == '前3 按把握调节' else 1.6)
    off = {'前3 不设防守': 1.45, '前3 按把握调节': 0.92, '前3 逐个均线门槛': 0.62, '全市场': 1.0}[k]
    ax.text(nav.index[-1] + pd.Timedelta(days=200), nav[k].iloc[-1] * off, f'{lab}  年化 {ann[k]}', color=INK, va='center', fontsize=10.5)
ax.set_xticks([pd.Timestamp(f'{y}-01-01') for y in range(1960, 2030, 10)]); ax.set_xticklabels([str(y) for y in range(1960, 2030, 10)])
ax.set_yscale('log'); ax.set_ylabel('1 元变成多少元（对数刻度）', color=MUTED)
ax.set_xlim(nav.index[0], nav.index[-1] + pd.Timedelta(days=5600)); ax.grid(axis='y', alpha=.2)
title(fig, '美国 70 年：每月选最强的 3 个行业，每年比全市场多约 5 个点',
      'French 49 个行业 + 全市场，1955–2026；成本按单边 0.2%；按把握调节几乎不吃进攻，逐个卡均线每年少约 1.4 点')
fig.savefig(OUT / 'f4-topn-longhist.png', dpi=150, bbox_inches='tight'); plt.close(fig)

# ---------- f5：市场越窄，领头者越该拿；逐个门槛正好砍在这里 ----------
dfn = json.load(open(RES / 'topn-defense.json'))
rows = [('一直持有全市场', '全市场', C['参照']), ('前3 不设防守', '前 3，不设防守', C['不设防守']),
        ('前3 ①逐个均线门槛', '前 3 + 逐个候选卡均线', C['逐个门槛']), ('前3 ③只在全市场层面', '前 3 + 只在市场层面防守', C['新系统'])]
lv = [('宽度低_月均收益年化', '宽度低\n多数行业在跌，只有少数领涨'), ('宽度中_月均收益年化', '宽度中'), ('宽度高_月均收益年化', '宽度高\n普涨')]
fig, ax = plt.subplots(figsize=(12, 4.4)); w = .2
for j, (k, lab, col) in enumerate(rows):
    vals = [dfn[k][a] for a, _ in lv]
    xs = np.arange(len(lv)) + (j - 1.5) * w
    ax.bar(xs, vals, w * .9, color=col, label=lab)
    for x, v in zip(xs, vals): ax.text(x, v + .4, f'{v:.1f}', ha='center', fontsize=9.5, color=INK)
ax.set_xticks(range(len(lv))); ax.set_xticklabels([b for _, b in lv]); ax.set_ylabel('下个月收益（年化，%）', color=MUTED)
ax.legend(frameon=False, ncol=4, loc='upper center', bbox_to_anchor=(.5, -.18), fontsize=10.5); ax.grid(axis='y', alpha=.2)
ax.annotate('逐个门槛在这里每年少约 4.5 点', xy=(0.1, dfn['前3 ①逐个均线门槛']['宽度低_月均收益年化'] - 3), xytext=(.55, 21),
            color=BAD, fontsize=10.5, arrowprops=dict(arrowstyle='->', color=BAD))
title(fig, '市场越窄，领头的几个越赚钱；逐个候选卡均线，恰好砍在这些月份',
      'French 49 个行业，1955–2026；按上月末站上均线的行业占比分三档；月均收益折年化，未扣成本差异')
fig.savefig(OUT / 'f5-breadth.png', dpi=150, bbox_inches='tight'); plt.close(fig)

# ---------- f6：合成行情，100 万最难受时剩多少 ----------
n3 = pd.read_csv(RES / 'msim-v6-n3.csv'); n2 = pd.read_csv(RES / 'msim-v6.csv')
n3 = n3[n3['防守资产'] == '不帮忙']; n2 = n2[n2['防守资产'] == '不帮忙']
REG = ['慢牛', '震荡', '市场接力', '急跌', '慢熊', 'V型反转']
LAB = {'慢牛': '慢牛', '震荡': '震荡', '市场接力': '市场接力', '急跌': '急跌\n20 天 −30%', '慢熊': '慢熊\n18 个月 −45%', 'V型反转': 'V 型反转'}
src = [('基准', n2, '基准', C['参照']), ('增强基准', n2, '上一版（增强基准）', C['增强基准']), ('新系统', n3, '新系统（前 3，美股 60%）', C['新系统'])]
fig, ax = plt.subplots(figsize=(12, 4.6)); w = .26
for j, (k, d, lab, col) in enumerate(src):
    for i, r in enumerate(REG):
        row = d[(d['行情'] == r) & (d['结构'] == k)].iloc[0]; x = i + (j - 1) * w
        ax.plot([x, x], [row['最低剩_万_p10'], row['最低剩_万_中位']], color=col, lw=5, alpha=.35, solid_capstyle='round')
        ax.plot(x, row['最低剩_万_中位'], 'o', color=col, ms=8, label=lab if i == 0 else None)
        if k == '新系统': ax.text(x + .05, row['最低剩_万_中位'] + 1.2, f"{row['最低剩_万_中位']:.0f}", fontsize=9.5, color=INK)
ax.axhline(60, color=BAD, lw=1.2, ls='--'); ax.text(5.55, 60.8, '你的底线 60 万', color=BAD, fontsize=10, ha='right')
ax.set_xticks(range(len(REG))); ax.set_xticklabels([LAB[r] for r in REG]); ax.set_ylabel('100 万最难受时剩多少（万）', color=MUTED)
ax.set_ylim(30, 95); ax.grid(axis='y', alpha=.2)
ax.legend(frameon=False, ncol=3, loc='upper center', bbox_to_anchor=(.5, -.2), fontsize=10.5)
title(fig, '六种合成行情：新系统的中间情况都守住 60 万；较差的十分之一在急跌、震荡差 1 万左右',
      '圆点 = 200 种可能未来的中间情况，竖条下端 = 较差的十分之一；合成行情没有动量，挑选只是噪声（对挑选最不利）')
fig.savefig(OUT / 'f6-synthetic.png', dpi=150, bbox_inches='tight'); plt.close(fig)

# ---------- f7：预测表 ----------
rows = [('美股名额挑选（前 3）', 1.0, 0.3, 1.5), ('A 股名额挑选（前 3）', 0.0, -1.0, 1.0), ('防守的平时保费', -0.4, -1.6, -0.4),
        ('美股 60% 的仓位差\n（两地一样强时）', 0.0, -3.0, 3.0), ('合计（不含仓位差）', 0.6, -2.3, 2.1)]
fig, ax = plt.subplots(figsize=(12, 4.4))
for i, (n, c, lo, hi) in enumerate(rows):
    y = len(rows) - 1 - i; col = GOOD if c > 0 else (BAD if c < 0 else C['参照'])
    ax.plot([lo, hi], [y, y], color=col, lw=6, alpha=.28, solid_capstyle='round'); ax.plot(c, y, 'o', color=col, ms=11, zorder=3)
    ax.text(c, y + .33, fmt(c), ha='center', color=INK, weight='bold', fontsize=11.5, bbox=dict(boxstyle='round,pad=.12', fc='white', ec='none'))
ax.axvline(0, color=INK, lw=1)
ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows][::-1], fontsize=11)
ax.set_xticks(range(-3, 4)); ax.set_xticklabels([fmt(v, 0) for v in range(-3, 4)])
ax.set_xlim(-3.6, 3.6); ax.set_ylim(-.6, len(rows) - .2); ax.grid(axis='x', alpha=.22)
ax.set_xlabel('每年比基准（沪深300 70% + 美股 30%）多或少几个点；粗线 = 范围，圆点 = 中间值', color=MUTED)
title(fig, '预计每年比基准多约 0.6 个点，唯一的超额来源是美股名额的挑选',
      '来自历史的超额打五折，再按候选个数（约 14 个）打六折；成本按单边 0.2% 已扣；美股比 A 股每年强或弱 10 点，仓位差约 ±3 点')
fig.savefig(OUT / 'f7-forecast.png', dpi=150, bbox_inches='tight'); plt.close(fig)
print('ok')

# ---------- f8：一个月怎么定持仓（流程 + 两个真实月份的结果） ----------
from matplotlib.patches import FancyBboxPatch
ex = json.load(open(RES / 'exec-example.json'))
fig = plt.figure(figsize=(12, 3.6))
ax = fig.add_axes([0.22, 0.02, 0.64, 0.92])
NAMES = {'theme-中证军工': '军工', 'theme-中证全指软件': '软件', 'allshare-utilities': '公用', 'NBI': '生物科技', 'XLV': '医疗', 'XLY': '可选消费',
         'theme-沪深300医药卫生': '300医药', 'allshare-healthcare': '全指医药', 'chinext': '创业板', 'XLF': '金融'}
rows = [('2015-08-31', 'A 股名额（40 万）', 40), ('2015-08-31', '美股名额（60 万）', 60), ('2013-04-26', 'A 股名额（40 万）', 40), ('2013-04-26', '美股名额（60 万）', 60)]
key = {'A 股名额（40 万）': 'A 股名额（40%）', '美股名额（60 万）': '美股名额（60%）'}
for i, (d, slot, amt) in enumerate(rows):
    y = len(rows) - 1 - i - (0.4 if i >= 2 else 0); e = ex[key[slot]][d]; x = 0
    for nm in e['入选']:
        w_ = amt * e['每只仓位_占名额']
        ax.barh(y, w_, left=x, height=.62, color=C['新系统'], edgecolor='white', lw=2)
        ax.text(x + w_ / 2, y, f"{NAMES.get(nm, nm)}\n{w_:.1f}" if w_ < 6 else f"{NAMES.get(nm, nm)}\n{w_:.1f} 万", ha='center', va='center', color='white', fontsize=8.5 if w_ < 6 else 10.5, weight='bold')
        x += w_
    rest = amt - x
    if rest > .5:
        ax.barh(y, rest, left=x, height=.62, color='#d1d5db', edgecolor='white', lw=2)
        ax.text(x + rest / 2, y, f'国债 {rest:.1f} 万', ha='center', va='center', color=INK, fontsize=10)
    lab = f"{'股灾后 2015-08' if d.startswith('2015') else '平静 2013-04'}  {slot}"
    ax.text(-1.5, y, lab, ha='right', va='center', fontsize=12, color=INK)
    ax.text(amt + 1.2, y, f"{e['票数']} 票 · 把握 {e['把握p']:.3g}" if e['确认紧张'] else f"{e['票数']} 票 · 不紧张", va='center', fontsize=10, color=BAD if e['确认紧张'] else MUTED)
ax.set_xlim(0, 72); ax.axis('off')
title(fig, '一个月怎么定持仓：2015 年 8 月股灾后，A 股 40 万里只拿 10.6 万股票，美股几乎满仓',
      '用设计期真实数据按规则复现的两个月，100 万本金；青绿 = 股票，灰 = 国债；右侧是当月的票数和把握 p')
fig.savefig(OUT / 'f8-exec.png', dpi=150, bbox_inches='tight'); plt.close(fig)
print('f8 ok')
