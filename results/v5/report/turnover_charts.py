"""《v5.1 换手深挖》的图。只读已签收结果、D37 各格和本目录的 v51_turnover / v51_sells 输出。
用法：python results/v5/report/turnover_charts.py   → docs/assets/v51-turnover/t1…t7.png
"""
import json, pathlib
import pandas as pd, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
import matplotlib.dates as mdates
ROOT = pathlib.Path(__file__).resolve().parents[3]
import os
REP = ROOT / 'results/v5/report'; D37 = ROOT / 'results/v51-diag/d37'; OUT = ROOT / 'docs/assets/v51-turnover'
S1ROOT = pathlib.Path(os.environ.get('D37_S1_ROOT', str(D37)))  # 第四轮 S1 未合入时指向分支导出的目录
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'font.size': 11, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, GOOD, BAD, BLUE, GREY, LIGHT = '#151b26', '#5d6676', '#15803d', '#c2410c', '#1d4ed8', '#94a3b8', '#cbd5e1'
SEGC = {'设计期': '#93c5fd', '美国 ETF': '#7c3aed', '检验段 · 原池子': '#1d4ed8', '检验段 · 全市场': '#0f766e'}
def title(fig, t, s):
    h = fig.get_figheight(); fig.text(.04, 1 + .44 / h, t, fontsize=14.5, weight='bold', color=INK); fig.text(.04, 1 + .13 / h, s, fontsize=10.5, color=MUTED)
def save(fig, name):
    fig.savefig(OUT / name, dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)

# ---------- t1：每类调仓扣成本后每年净赚 ----------
J = json.load(open(REP / 'v51_turnover.json'))
def net(seg, keys):
    return sum(J[seg][k]['每年增值20'] - J[seg][k]['每年成本'] for k in keys if k in J[seg])
CATS = [('换市场', ['换市场']), ('全部离场 + 重新进场\n（成对算）', ['整体进场', '整体离场']), ('满仓 ↔ 半仓\n（加、减成对算）', ['加仓档', '减仓档']),
        ('每周换人', ['周度换掉']), ('单只止损', ['单只离场']), ('防守换品种', ['防守换品种'])]
fig, ax = plt.subplots(figsize=(11, 5.2))
y = np.arange(len(CATS))[::-1]
for k, (seg, col, off) in enumerate((('设计期', SEGC['设计期'], .19), ('检验段', SEGC['检验段 · 原池子'], -.19))):
    v = [net(seg, ks) for _, ks in CATS]
    ax.barh(y + off, v, height=.36, color=col, label=seg)
    for yy, vv in zip(y + off, v):
        ax.text(vv + (.12 if vv >= 0 else -.12), yy, f'{vv:+.1f}'.replace('-', '−'), va='center', ha='left' if vv >= 0 else 'right', fontsize=10, color=INK)
ax.axvline(0, color=INK, lw=.9); ax.set_yticks(y); ax.set_yticklabels([c for c, _ in CATS]); ax.grid(axis='x', alpha=.2)
ax.set_xlabel('每年净赚（百分点）= 调仓后 20 日多赚 − 成本', color=MUTED); ax.legend(frameon=False, loc='lower right')
hit = {c: (J['检验段'][ks[0]]['做对比例20']) for c, ks in CATS}
title(fig, '扣掉成本，只有“换市场”这一层一直在赚；每周换人亏得最多',
      '每类调仓一年的净贡献。设计期 2006–2015、检验段 2016–2026-09。检验段一年 70 笔，做对的只有 49%。')
fig.tight_layout(); save(fig, 't1-net-by-layer.png')

# ---------- t2：减仓在周中、加仓在周度日；离场后几天回来 ----------
st = pd.read_csv(ROOT / 'results/v5/oneshot/index/v5.1-对照/state.csv', parse_dates=['date']).set_index('date')
idx = st.index; W = set(pd.Series(idx).groupby(pd.Series(idx).dt.to_period('W')).max())
R = st.risk.where(st.market.notna(), 0.0); prev = R.shift(1)
dn = [d for d in idx[1:] if R[d] < prev[d] - 1e-9]; up = [d for d in idx[1:] if R[d] > prev[d] + 1e-9]
LAB = ['周一', '周二', '周三', '周四', '周度决策日']
def bucket(d): return 4 if d in W else min(d.weekday(), 3)
cd = np.bincount([bucket(d) for d in dn], minlength=5) / (len(idx) / 252)
cu = np.bincount([bucket(d) for d in up], minlength=5) / (len(idx) / 252)
sells = pd.read_csv(REP / 'v51_sells.csv'); t = sells[(sells.段 == '检验段') & sells.整体离场]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={'width_ratios': [1.2, 1]})
x = np.arange(5)
a1.bar(x - .2, cd, .38, color=BAD, label='减仓（降档或离场）'); a1.bar(x + .2, cu, .38, color=GOOD, label='加仓（升档或进场）')
for xx, v in zip(x - .2, cd): a1.text(xx, v + .2, f'{v:.1f}', ha='center', fontsize=9.5)
for xx, v in zip(x + .2, cu):
    if v > 0: a1.text(xx, v + .2, f'{v:.1f}', ha='center', fontsize=9.5)
a1.set_xticks(x); a1.set_xticklabels(LAB); a1.set_ylabel('一年几次', color=MUTED); a1.legend(frameon=False, loc='upper left'); a1.grid(axis='y', alpha=.2)
a1.set_title('减仓分散在周中，加仓只在周度决策日', loc='left', fontsize=12, weight='bold')
days = t.回来天数.clip(upper=60)
a2.hist(days, bins=np.arange(0, 64, 3), color=BAD, edgecolor='white')
med = int(t.回来天数.median()); a2.axvline(med, color=INK, lw=1.2, ls='--'); a2.text(med + 1, a2.get_ylim()[1] * .9, f'中位 {med} 天', fontsize=10.5)
share = (t.回来天数 <= 14).mean() * 100
a2.set_xlabel('整体离场到再次进场的日历天数（超过 60 天的并入最右）', color=MUTED); a2.set_ylabel('次数', color=MUTED); a2.grid(axis='y', alpha=.2)
a2.set_title(f'整体离场后 {share:.0f}% 两周内又买回来', loc='left', fontsize=12, weight='bold')
title(fig, '来回打脸的样子：周中卖掉，到周度决策日又买回来', '检验段 2016–2026-09，原规则。周度决策日 = 每周最后一个交易日。')
fig.tight_layout(); save(fig, 't2-ratchet.png')

# ---------- t3：共振减仓逐年净赚 ----------
s = sells[sells.周中 & sells.整体离场].copy(); s['净'] = s.减仓价值 - s.一来一回成本
yr = s.groupby('年').净.sum().reindex(range(2006, 2027), fill_value=0.0)
fig, ax = plt.subplots(figsize=(13, 4.6))
ax.bar(yr.index, yr.values, color=[GOOD if v > 0 else BAD for v in yr.values], width=.72)
for x_, v in yr.items():
    if abs(v) > 3: ax.text(x_, v + (1 if v > 0 else -1), f'{v:+.1f}'.replace('-', '−'), ha='center', va='bottom' if v > 0 else 'top', fontsize=9.5)
ax.axvline(2015.5, color=GREY, ls='--', lw=1); ax.text(2010.5, yr.max() * .95, '设计期', ha='center', color=MUTED); ax.text(2021, yr.max() * .95, '检验段', ha='center', color=MUTED)
ax.axhline(0, color=INK, lw=.8); ax.set_xticks(range(2006, 2027, 2)); ax.grid(axis='y', alpha=.2); ax.set_ylabel('当年共振减仓的净赚（百分点）', color=MUTED)
d_tot = s[s.段 == '设计期'].净.sum(); t_tot = s[s.段 == '检验段'].净.sum()
title(fig, f'“保险”只在 2008 年大额赔付：设计期合计 {d_tot:+.1f}，其中 2008 年 {yr[2008]:+.1f}；检验段合计 {t_tot:+.1f}'.replace('-', '−'),
      '每一年里“两条腿同时断、周中整体离场”的净赚（减仓价值 − 一来一回成本），原规则。')
fig.tight_layout(); save(fig, 't3-insurance-years.png')

# ---------- t4：正确率 × 赚亏比，保本线 ----------
P = [('共振减仓', .46, 325.7 / 203.5, .41, 161.4 / 200.1), ('换市场', .78, 870 / 573, .55, 502 / 273),
     ('每周换人', .48, 234 / 267, .46, 227 / 201), ('单只离场', .59, 226 / 80, .50, 104 / 110), ('降一档', .43, 203 / 468, .46, 235 / 220)]
fig, ax = plt.subplots(figsize=(11, 6))
p = np.linspace(.3, .85, 200); ax.plot(p * 100, (1 - p) / p, color=INK, lw=1.6)
ax.fill_between(p * 100, (1 - p) / p, 3.2, color='#dcfce7', alpha=.6); ax.fill_between(p * 100, 0, (1 - p) / p, color='#ffedd5', alpha=.6)
ax.text(33, 2.95, '这一侧：期望为正', color=GOOD, fontsize=11, weight='bold'); ax.text(70, .12, '这一侧：期望为负', color=BAD, fontsize=11, weight='bold')
ax.text(31, 1.95, '保本线：正确率 × 赚 = 错误率 × 亏', fontsize=9.5, color=INK, rotation=-38)
for name, pd_, rd, pt, rt in P:
    ax.annotate('', xy=(pt * 100, rt), xytext=(pd_ * 100, rd), arrowprops=dict(arrowstyle='->', color=GREY, lw=1.2))
    ax.scatter(pd_ * 100, rd, s=70, facecolor='white', edgecolor=BLUE, lw=1.8, zorder=3)
    ax.scatter(pt * 100, rt, s=70, color=BLUE, zorder=3)
    dx, dy = {'每周换人': (1.2, .12), '降一档': (1.2, -.08)}.get(name, (.8, .05))
    ax.text(pt * 100 + dx, rt + dy, name, fontsize=10.5, color=INK, weight='bold')
ax.scatter([], [], s=60, facecolor='white', edgecolor=BLUE, label='设计期'); ax.scatter([], [], s=60, color=BLUE, label='检验段')
ax.set_xlim(30, 85); ax.set_ylim(0, 3.2); ax.set_xlabel('正确率（%）', color=MUTED); ax.set_ylabel('赚亏比 = 做对时平均赚 ÷ 做错时平均亏', color=MUTED)
ax.legend(frameon=False, loc='upper right'); ax.grid(alpha=.2)
title(fig, '正确率低也能赚钱，只要做对时赚得够多：共振减仓从线上掉到了线下',
      '每个点是 v5.1 里的一类动作（原规则），空心 = 设计期，实心 = 检验段，箭头是从设计期到检验段的变化。保本线未计成本，计成本后整条线再往上移一点。')
fig.tight_layout(); save(fig, 't4-hit-vs-payoff.png')

# ---------- t5：五个版本 × 四段 ----------
def perf(sc, seg, v):
    p = json.load(open((S1ROOT if sc == 'S1' else D37) / sc / seg / v / 'stats.json'))['performance']; return p['ann'] * 100, p['max_drawdown'] * 100
SEGS = [('设计期', 'S0', '设计期'), ('美国 ETF', 'S0', '别的市场'), ('检验段 · 原池子', 'S0', '检验段'), ('检验段 · 全市场', 'S1', '检验段')]
VS = [('V1 全按周', 'V1'), ('V2 共振才按天减', 'V2'), ('V3 加减都按天', 'V3'), ('V4 共振减 + 按天加', 'V4')]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5.2), sharey=False)
x = np.arange(len(VS)); w = .2
for k, (lab, sc, seg) in enumerate(SEGS):
    a0, d0 = perf(sc, seg, 'V0')
    da = [perf(sc, seg, v)[0] - a0 for _, v in VS]; dd = [perf(sc, seg, v)[1] - d0 for _, v in VS]
    a1.bar(x + (k - 1.5) * w, da, w * .92, color=SEGC[lab], label=lab)
    a2.bar(x + (k - 1.5) * w, dd, w * .92, color=SEGC[lab], label=lab)
for a, t_ in ((a1, '年化比原规则多（百分点）'), (a2, '最大回撤比原规则浅（百分点，正 = 更浅）')):
    a.axhline(0, color=INK, lw=.9); a.set_xticks(x); a.set_xticklabels([l for l, _ in VS], fontsize=10.5); a.grid(axis='y', alpha=.2); a.set_title(t_, loc='left', fontsize=12, weight='bold')
    a.axvspan(.5, 1.5, color='#dcfce7', alpha=.5, zorder=-1)
a1.legend(frameon=False, fontsize=9.5, loc='upper right')
title(fig, '只有 V2（两条腿都断才按天减）在四段数据里都没变差；“加也按天”（V3、V4）在美国那段回撤深了 15 个点',
      '每根柱 = 该版本减去同一段原规则（V0）。绿底是 V2。检验段原池子用当前库。')
fig.tight_layout(); save(fig, 't5-cadence-versions.png')

# ---------- t6：有保险 vs 没保险的净值 ----------
def nav(sc, seg, v):
    d = pd.read_csv((S1ROOT if sc == 'S1' else D37) / sc / seg / v / 'daily.csv', parse_dates=['date']).set_index('date'); return (1 + d.net).cumprod()
fig, axs = plt.subplots(1, 2, figsize=(14, 4.8))
for ax, (lab, sc, seg) in zip(axs, (('美国 ETF（2003-07 → 2026-09）', 'S0', '别的市场'), ('检验段 · 原池子（2016 → 2026-09）', 'S0', '检验段'))):
    n1, n2 = nav(sc, seg, 'V1'), nav(sc, seg, 'V2')
    ax.plot(n1.index, n1, color=GREY, lw=1.6, label='没保险（V1，不按天减）'); ax.plot(n2.index, n2, color=BLUE, lw=1.8, label='有保险（V2，共振才按天减）')
    for n, c in ((n1, GREY), (n2, BLUE)):
        dd = n / n.cummax() - 1; ax.text(n.index[-1], n.iloc[-1], f'  回撤 {dd.min() * 100:.0f}%', color=c, fontsize=10, va='center')
    ax.set_title(lab, loc='left', fontsize=12, weight='bold'); ax.grid(alpha=.2); ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    if '美国' in lab:
        for a_, b_, t_ in (('2008-09-01', '2009-03-31', '2008 年'), ('2020-02-15', '2020-04-15', '2020 年 3 月')):
            ax.axvspan(pd.Timestamp(a_), pd.Timestamp(b_), color='#fee2e2', zorder=-1); ax.text(pd.Timestamp(b_), ax.get_ylim()[1] * .95, ' ' + t_, fontsize=9.5, color=BAD)
axs[0].legend(frameon=False, loc='upper left', bbox_to_anchor=(0, -.08), ncol=2, fontsize=10); axs[0].set_ylabel('净值（起点 = 1）', color=MUTED)
title(fig, '保险在急跌时赔付（美国 2008 年拉开差距，2020 年 3 月又挡了一次），在慢慢流血时没用（检验段 2018–2025）', '同一段数据上，只差“两条腿都断时是否当天减仓”。红底 = 急跌窗口。')
fig.tight_layout(); save(fig, 't6-insurance-nav.png')

# ---------- t7：全市场 vs 原池子，满仓押注的窗口 ----------
n0, n1 = nav('S0', '检验段', 'V0'), nav('S1', '检验段', 'V0')
h = pd.read_csv(S1ROOT / 'S1/检验段/V0/held.csv', parse_dates=['date']).set_index('date')
fig, ax = plt.subplots(figsize=(13, 5))
ax.plot(n0.index, n0, color=GREY, lw=1.6, label='原池子（只选 A 股、港股、美股）'); ax.plot(n1.index, n1, color='#0f766e', lw=1.9, label='全市场（其他海外、商品各自成一个市场）')
for cid, col, nm in (('cross-border-commodity', '#fde68a', '跨境商品满仓'), ('theme-中证韩交所中韩半导体指数', '#ddd6fe', '中韩半导体满仓')):
    on = (h[cid] > .5) if cid in h else pd.Series(False, index=h.index)
    first = True
    for g, blk in on.groupby((on != on.shift()).cumsum()):
        if blk.iloc[0]:
            ax.axvspan(blk.index[0], blk.index[-1], color=col, alpha=.8, zorder=-1, label=nm if first else None); first = False
for n, c in ((n0, GREY), (n1, '#0f766e')):
    ann = n.iloc[-1] ** (252 / len(n)) - 1; ax.text(n.index[-1], n.iloc[-1], f'  年化 {ann * 100:+.1f}%'.replace('+-', '−'), color=c, fontsize=10.5, va='center')
ax.legend(frameon=False, loc='upper left', fontsize=10); ax.grid(alpha=.2); ax.set_ylabel('净值（起点 = 1）', color=MUTED); ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
title(fig, '全市场多出来的收益，几乎都出现在两段“单只满仓”的窗口里：2021–22 年跨境商品、2026 年中韩半导体',
      '检验段 2016–2026-09，原规则节奏（V0），D37 第四轮数据。色块 = 该标的占整个组合 100% 的日子。')
fig.tight_layout(); save(fig, 't7-full-market.png')
print('ok')
