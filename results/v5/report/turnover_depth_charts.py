"""《v5.1 换手深挖》宽度和深度的图（t8–t12）。读 turnover_depth.json、v51_trades.csv 和 D37 各格。
用法：python results/v5/report/turnover_depth_charts.py
"""
import json, pathlib
import pandas as pd, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
ROOT = pathlib.Path(__file__).resolve().parents[3]; REP = ROOT / 'results/v5/report'; OUT = ROOT / 'docs/assets/v51-turnover'; D37 = ROOT / 'results/v51-diag/d37'
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False, 'axes.spines.right': False, 'font.size': 11, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, GOOD, BAD, GREY = '#151b26', '#5d6676', '#15803d', '#c2410c', '#94a3b8'
DES, TST = '#93c5fd', '#1d4ed8'
REGC = {'牛市': '#16a34a', '震荡': '#cbd5e1', '反转': '#f59e0b', '熊市': '#dc2626'}
J = json.load(open(REP / 'turnover_depth.json'))
def title(fig, t, s):
    h = fig.get_figheight(); fig.text(.04, 1 + .44 / h, t, fontsize=14.5, weight='bold', color=INK); fig.text(.04, 1 + .13 / h, s, fontsize=10.5, color=MUTED)
def save(fig, name): fig.savefig(OUT / name, dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)

# t8 宽度：每类一年几笔（占比）+ 各自正确率
B = J['breadth']; cats = [k for k in sorted(B['检验段'], key=lambda k: -B['检验段'][k]['每年']) if k != '合计']
fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5.6), gridspec_kw={'width_ratios': [1.25, 1]}, sharey=True)
y = np.arange(len(cats))[::-1]
for seg, col, off in (('设计期', DES, .19), ('检验段', TST, -.19)):
    v = [B[seg].get(c, {}).get('每年', 0) for c in cats]; sh = [B[seg].get(c, {}).get('占比', 0) for c in cats]
    a1.barh(y + off, v, .36, color=col, label=f'{seg}（一年 {B[seg]["合计"]["每年"]:.0f} 笔）')
    for yy, vv, ss in zip(y + off, v, sh): a1.text(vv + .3, yy, f'{vv:.1f} 笔 · {ss}%', va='center', fontsize=9.5, color=INK)
a1.set_yticks(y); a1.set_yticklabels(cats); a1.set_xlabel('一年几笔（· 后面是占全部笔数的比例）', color=MUTED); a1.legend(frameon=False, loc='lower right'); a1.grid(axis='x', alpha=.2)
a1.set_title('占比：每周换人最多，三成', loc='left', fontsize=12, weight='bold')
for seg, mk in (('设计期', 'o'), ('检验段', 'o')):
    v = [B[seg].get(c, {}).get('正确率', np.nan) for c in cats]
    if seg == '设计期': a2.scatter(v, y, s=70, facecolor='white', edgecolor=TST, lw=1.8, label='设计期', zorder=3)
    else: a2.scatter(v, y, s=70, color=TST, label='检验段', zorder=3)
for c, yy in zip(cats, y):
    d, t_ = B['设计期'].get(c, {}).get('正确率'), B['检验段'].get(c, {}).get('正确率')
    if d is not None and t_ is not None: a2.plot([d, t_], [yy, yy], color=GREY, lw=1, zorder=1)
    if t_ is not None: a2.text(t_, yy - .32, f'{t_}%', ha='center', fontsize=9.5, color=INK)
a2.axvline(50, color=BAD, ls='--', lw=1.2); a2.text(50.5, y.max() + .45, '50% = 抛硬币', color=BAD, fontsize=10)
a2.set_xlim(35, 85); a2.set_xlabel('正确率（%）：调仓后 20 个交易日，新持仓是否比原持仓多赚', color=MUTED); a2.legend(frameon=False, loc='upper right'); a2.grid(axis='x', alpha=.2)
a2.set_title('正确率：大多挤在 50% 附近', loc='left', fontsize=12, weight='bold')
title(fig, '一年 70 笔都是什么：三成是每周换人；除了“重新进场”和“换市场”，各类正确率都在 42%–57%',
      'v5.1 原规则。设计期 2006–2015，检验段 2016–2026-09。“零星调整”是权重的小幅再平衡，几乎不花钱。')
fig.tight_layout(); save(fig, 't8-breadth.png')

# t9 深度：逐年笔数（按类分组）+ 每月行情
G = {'每周换人': ['每周换人'], '进出和档位': ['全部离场', '重新进场', '满仓降到半仓', '半仓加到满仓'], '单只止损': ['单只止损'], '换市场': ['换市场'], '防守和零星': ['防守换品种', '零星调整']}
GC = {'每周换人': '#1d4ed8', '进出和档位': '#c2410c', '单只止损': '#7c3aed', '换市场': '#15803d', '防守和零星': '#cbd5e1'}
yc = pd.DataFrame(J['yearly_counts']).T.fillna(0); yc.index = yc.index.astype(int); yc = yc.sort_index()
days = {y: 252 for y in yc.index}; days[2026] = 186
fig, (ax0, ax) = plt.subplots(2, 1, figsize=(14, 6.4), gridspec_kw={'height_ratios': [.6, 4]}, sharex=True)
rm = pd.Series(J['regime_by_month']); rm.index = pd.PeriodIndex(rm.index, freq='M')
for p_, r in rm.items():
    x0 = p_.year + (p_.month - 1) / 12 - .5; ax0.axvspan(x0, x0 + 1 / 12, color=REGC[r], lw=0)
ax0.set_yticks([]); ax0.set_ylabel('行情', rotation=0, ha='right', va='center', color=MUTED)
for k, c in REGC.items(): ax0.scatter([], [], marker='s', s=80, color=c, label=k)
ax0.legend(frameon=False, ncol=4, loc='lower left', bbox_to_anchor=(0, 1.0), fontsize=10)
bottom = np.zeros(len(yc))
for g, members in G.items():
    v = yc[[m for m in members if m in yc]].sum(axis=1).values * 252 / np.array([days[y] for y in yc.index])
    ax.bar(yc.index, v, bottom=bottom, color=GC[g], width=.75, label=g); bottom += v
for x_, t_ in zip(yc.index, bottom):
    ax.text(x_, t_ + 1.5, f'{t_:.0f}', ha='center', fontsize=9.5, color=INK)
    h = J['yearly_hit'].get(str(x_)); ax.text(x_, -7, f'{h}%', ha='center', fontsize=8.5, color=GOOD if h >= 52 else (BAD if h <= 47 else MUTED))
ax.text(2005.2, -7, '正确率', fontsize=8.5, color=MUTED, ha='right')
ax.axvline(2015.5, color=GREY, ls='--', lw=1); ax.set_ylim(-10, bottom.max() * 1.15)
ax.set_xticks(range(2006, 2027)); ax.tick_params(axis='x', labelsize=9.5); ax.set_ylabel('一年几笔（2026 年按 9 个月折算全年）', color=MUTED)
ax.legend(frameon=False, ncol=5, loc='upper left', fontsize=10); ax.grid(axis='y', alpha=.2)
title(fig, '每年动多少：2016 年后池子变大，一年从约 50 笔涨到 70 笔；牛熊反转对交易频率几乎没影响',
      '上方色带 = 每个月的行情（按基准过去 6 个月涨跌机械划分，见图下说明）；柱 = 当年调仓笔数，按类分组；柱下数字 = 当年正确率。')
fig.tight_layout(); save(fig, 't9-yearly.png')

# t10 深度：四种行情下 每月笔数 / 正确率 / 每月净赚
R = J['by_regime']; regs = ['牛市', '震荡', '反转', '熊市']
fig, axs = plt.subplots(1, 3, figsize=(14, 4.6))
for ax, key, lab in zip(axs, ('每月笔数', '正确率', '每月净'), ('每月几笔', '正确率（%）', '每月净赚（百分点）')):
    x = np.arange(4)
    for seg, col, off in (('设计期', DES, -.2), ('检验段', TST, .2)):
        v = [R[seg].get(r, {}).get(key, np.nan) for r in regs]
        ax.bar(x + off, v, .38, color=col, label=seg)
        for xx, vv in zip(x + off, v):
            off_ = {'每月笔数': .08, '正确率': .3, '每月净': .05}[key]
            if vv == vv: ax.text(xx, vv + (off_ if vv >= 0 else -off_), f'{vv:g}'.replace('-', '−'), ha='center', va='bottom' if vv >= 0 else 'top', fontsize=9)
    ax.set_xticks(x); ax.set_xticklabels([f'{r}\n{R["检验段"].get(r, {}).get("月数", 0)} 个月' for r in regs], fontsize=10); ax.set_title(lab, loc='left', fontsize=12, weight='bold'); ax.grid(axis='y', alpha=.2)
    if key == '正确率': ax.axhline(50, color=BAD, ls='--', lw=1); ax.set_ylim(35, 60)
    if key == '每月净': ax.axhline(0, color=INK, lw=.8)
axs[0].legend(frameon=False, loc='upper right', fontsize=9.5)
title(fig, '分行情看：检验段不管什么行情都是每月 4–6 笔；亏钱集中在反转和熊市的月份',
      '不含零星调整。x 轴下的月数是检验段的；设计期是牛市 46、震荡 24、反转 32、熊市 18 个月。')
fig.tight_layout(); save(fig, 't10-regime.png')

# t11 减仓：分行情的每次净赚 + 共振减仓按市场合计
S = J['sells_by_regime']; M = J['resonance_by_market']
fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 4.6))
x = np.arange(4)
for seg, col, off in (('设计期', DES, -.2), ('检验段', TST, .2)):
    v = [S[seg].get(r, {}).get('每次净', np.nan) for r in regs]
    a1.bar(x + off, v, .38, color=col, label=seg)
    for xx, vv in zip(x + off, v): a1.text(xx, vv + (.03 if vv >= 0 else -.03), f'{vv:+.2f}'.replace('-', '−'), ha='center', va='bottom' if vv >= 0 else 'top', fontsize=9)
a1.axhline(0, color=INK, lw=.8); a1.set_xticks(x); a1.set_xticklabels(regs); a1.grid(axis='y', alpha=.2); a1.legend(frameon=False, fontsize=9.5)
a1.set_title('每次减仓净赚：只在熊市是正的', loc='left', fontsize=12, weight='bold'); a1.set_ylabel('百分点（扣一来一回成本）', color=MUTED)
MN = {'csi300': 'A 股', 'hsi': '港股', 'spx': '美股'}
x = np.arange(3)
for seg, col, off in (('设计期', DES, -.2), ('检验段', TST, .2)):
    v = [M[seg].get(k, {}).get('合计', 0) for k in MN]; n = [M[seg].get(k, {}).get('次数', 0) for k in MN]
    a2.bar(x + off, v, .38, color=col, label=seg)
    for xx, vv, nn in zip(x + off, v, n): a2.text(xx, vv + (.6 if vv >= 0 else -.6), f'{vv:+.1f}\n{nn} 次'.replace('-', '−'), ha='center', va='bottom' if vv >= 0 else 'top', fontsize=9)
a2.axhline(0, color=INK, lw=.8); a2.set_xticks(x); a2.set_xticklabels(list(MN.values())); a2.grid(axis='y', alpha=.2); a2.set_ylim(-42, 25)
a2.set_title('共振减仓按市场合计：检验段在美股亏了 30.8', loc='left', fontsize=12, weight='bold'); a2.set_ylabel('合计净赚（百分点）', color=MUTED)
title(fig, '保险只在熊市里值钱；检验段只有 6 个熊市月，共振减仓 61 次里 35 次在美股，合计亏 30.8',
      '左：所有减仓（含降半仓），按减仓当月的行情分。右：两条腿都断、周中整体离场，按当时持有的市场分。原规则。')
fig.tight_layout(); save(fig, 't11-sells-depth.png')

# t12 深度：检验段逐年，V1、V2 比原规则多赚
def yearly(v):
    d = pd.read_csv(D37 / 'S0/检验段' / v / 'daily.csv', parse_dates=['date']).set_index('date').net
    return (1 + d).groupby(d.index.year).prod() - 1
y0 = yearly('V0'); y1 = yearly('V1') - y0; y2 = yearly('V2') - y0
fig, ax = plt.subplots(figsize=(13, 4.4)); x = np.arange(len(y0))
ax.bar(x - .2, y1 * 100, .38, color=GREY, label='V1 不按天减 − 原规则'); ax.bar(x + .2, y2 * 100, .38, color=TST, label='V2 共振才按天减 − 原规则')
for xx, v in zip(x + .2, y2 * 100): ax.text(xx, v + (.3 if v >= 0 else -.3), f'{v:+.1f}'.replace('-', '−'), ha='center', va='bottom' if v >= 0 else 'top', fontsize=8.5, color=INK)
ax.axhline(0, color=INK, lw=.8); ax.set_xticks(x); ax.set_xticklabels(y0.index); ax.grid(axis='y', alpha=.2); ax.legend(frameon=False, loc='upper left')
ax.set_ylabel('当年多赚（百分点）', color=MUTED)
pos2 = int((y2 > 0).sum())
title(fig, f'检验段逐年看：V2 有 {pos2} 年好于原规则，每年差别都不大；完全不按天减（V1）年份之间摆动大：2021 年 +14.7，2018 年 −7.5',
      '检验段 · 原池子，当前库。每年 = 该版本当年收益减原规则当年收益。')
fig.tight_layout(); save(fig, 't12-cadence-yearly.png')
print('ok', pos2, (y1 * 100).round(1).to_dict())
