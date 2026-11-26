"""v6 体检报告（设计期）的新图。只读设计期（≤ 2015）的结果文件。
用法：python -I scripts/v6_report/charts_health.py docs/assets/v6-health [结果目录，默认 results/v6]
h1：预测准不准——事先范围（横条）、中间值（竖线）、设计期实际（实心点）。
h2：和别人比——八条线 2006–15 的年化 × 最大回撤（左上更好），参照两点空心。
数字出处：
  事先范围、中间值 —《v6 预演预测表》第 3.22 版 = 冻结预注册 §3.1；A 股两块按 D40-12；成本的预演估计 — 冻结稿 §6 疼痛表“预演 1.0–1.1”；
  设计期实际 — health-forecast.csv（组合贡献列，D47-2、D48-2、D48-3）、health-scatter.csv、health-continuity.csv、health-gates.csv
    （Dev #377 @ a9a1e9e9，与 Reviewer #375 @ 7f1da3ff 独立结果逐项对上）；
  成本 — results/v6-preflight/v6-appendix-b.json 收益拆分.成本（附表 B 口径）；
  合计（不含仓位差）= v6 净 − BM-同仓位（判据 ④，§5.1 全收益基准、每月再平衡）。
样式与 scripts/preflight/charts_appendix_b.py 相同。
"""
import sys, json, csv, pathlib
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt, matplotlib.ticker

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
SRC = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / 'results/v6'
rd = lambda f: list(csv.DictReader(open(SRC / f, encoding='utf-8')))
AB = json.load(open(ROOT / 'results/v6-preflight/v6-appendix-b.json', encoding='utf-8'))
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'axes.spines.left': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, GREY, TEAL, AMBER, BAND, BLUE = '#151b26', '#5d6676', '#9ca3af', '#0d9488', '#d97706', '#dbe3ee', '#2563eb'
SEG = '2006-2015'
fmt = lambda v: f'{v:+.1f}'.replace('-', '−')

# ---------- h1 预测 ----------
F = {r['item']: float(r['contribution_pp']) for r in rd('health-forecast.csv') if r['segment'] == SEG and r['role'] == '主值'}
G = {r['item']: float(r['value']) for r in rd('health-gates.csv') if r['segment'] == SEG}
total = G['v6净减BM-同仓位年化']
cost = AB['收益拆分（每年比 BM-主 多几个点）']['成本']['2006–15']
rows = [('美股名额挑选', .3, 1.5, 1.0, F['美股挑选']),
        ('A 股名额：挑选', -.5, .5, .1, F['A股挑选']),
        ('A 股名额：等权倾斜', -1.0, 1.0, .5, F['A股等权倾斜']),
        ('防守的平时保费', -1.6, -.4, -.4, F['防守保费']),
        ('成本（预演估计）', -1.1, -1.0, None, cost),
        ('美股 60% 的仓位差', -3.0, 3.0, 0.0, F['美股60%仓位差']),
        ('合计（不含仓位差）', -1.3, 2.4, 1.2, total)]
fig, ax = plt.subplots(figsize=(11, 4.6)); n = len(rows)
X0, X1 = 1.03, 1.2
ax.text(X0, n - .45, '事先范围', transform=ax.get_yaxis_transform(), fontsize=10, color=MUTED, weight='bold')
ax.text(X1, n - .45, '设计期', transform=ax.get_yaxis_transform(), fontsize=10, color=MUTED, weight='bold')
for i, (nm, lo, hi, mid, act) in enumerate(rows):
    y = n - 1 - i
    ax.barh(y, hi - lo, left=lo, height=.42, color='#c9d4e4' if nm.startswith('合计') else BAND, edgecolor='none')
    ax.text(X0, y, f'{fmt(lo)} 到 {fmt(hi)}', transform=ax.get_yaxis_transform(), fontsize=10.5, color=MUTED, va='center')
    if mid is not None:
        ax.plot([mid, mid], [y - .27, y + .27], color=INK, lw=2)
    c = TEAL if act > hi else (AMBER if act < lo else INK)
    ax.scatter([act], [y], s=110, color=c, zorder=4, edgecolors='white', linewidths=1.5)
    side = 'left' if act > hi else 'right'
    ax.text(act + (.14 if side == 'left' else -.14), y - .02, fmt(act), ha=side, va='center', fontsize=12.5, weight='bold', color=c)
    ax.text(X1, y, fmt(act), transform=ax.get_yaxis_transform(), fontsize=11, weight='bold', color=c, va='center')
ax.axvline(0, color=GREY, lw=.8)
ax.set_yticks(range(n), [r[0] for r in rows][::-1])
for t in ax.get_yticklabels():
    if t.get_text().startswith('合计'):
        t.set_weight('bold')
ax.tick_params(axis='y', length=0)
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:+.0f}'.replace('-', '−') if v else '0'))
ax.set_xlim(-4.3, 4.6); ax.set_ylim(-.6, n - .3)
ax.set_xlabel('每年比基准多几个点（组合层面）', color=MUTED); ax.grid(axis='x', alpha=.2)
fig.subplots_adjust(top=.97, bottom=.12)
h = fig.get_figheight()
fig.text(.04, 1 + .42 / h, f'挑选三项都高于事先范围，防守保费和仓位差在范围内；合计 {fmt(total)} 刚过上限 +2.4', fontsize=14, weight='bold', color=INK)
fig.text(.04, 1 + .12 / h, '横条 = 事先范围，竖线 = 中间值；圆点 = 设计期 2006–15（样本内，高于范围不计功）。绿 = 高于范围，橙 = 低于范围',
         fontsize=10.5, color=MUTED)
fig.savefig(OUT / 'h1-forecast.png', dpi=150, bbox_inches='tight'); plt.close(fig)

# ---------- h2 散点 ----------
S = {r['series']: (float(r['cagr_pct']), -100 * float(r['max_drawdown'])) for r in rd('health-scatter.csv') if r['segment'] == SEG and r['status'] == 'ok'}
C = {r['role']: r for r in rd('health-continuity.csv') if r['segment'] == SEG}
ref = {'连续性版（不过滤，参照）': (float(C['参照']['cagr_pct']), -100 * float(C['参照']['max_drawdown']))}
fig, ax = plt.subplots(figsize=(11, 5.4))
style = {'v6': (BLUE, 190), '连续性版': (BLUE, 90), 'BM-主': (GREY, 90), 'BM-同仓位': (GREY, 90)}
offs = {'v6': (12, -18), '连续性版': (12, 10), 'A1': (10, -4), 'A2': (-10, 10), 'K2A': (-10, 10), '现行配置': (10, 8),
        'BM-主': (10, 8), 'BM-同仓位': (10, -16)}
for k, (y, x) in S.items():
    c, s = style.get(k, (INK, 90))
    ax.scatter([x], [y], s=s, color=c, zorder=4, edgecolors='white', linewidths=1.5)
    dx, dy = offs.get(k, (10, -4))
    ax.annotate(f'{k}  {y:.1f}% / −{x:.1f}%', (x, y), xytext=(dx, dy), textcoords='offset points', fontsize=11,
                ha='left' if dx > 0 else 'right', weight='bold' if k == 'v6' else 'normal', color=BLUE if k.startswith(('v6', '连续')) else INK)
for k, (y, x) in ref.items():
    ax.scatter([x], [y], s=80, facecolors='white', edgecolors=GREY, linewidths=1.4, zorder=3)
    ax.annotate(k, (x, y), xytext=(-10, -16), textcoords='offset points', fontsize=10, color=MUTED, ha='right')
ax.set_xlim(70, 5); ax.set_ylim(5, 30)
ax.set_xlabel('最大回撤（%，越往右越浅）', color=MUTED); ax.set_ylabel('年化（%）', color=MUTED)
ax.grid(alpha=.2); ax.spines['left'].set_visible(True)
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'−{v:.0f}'))
fig.subplots_adjust(top=.97)
h = fig.get_figheight(); v6y, v6x = S['v6']; by, bx = S['BM-主']
fig.text(.04, 1 + .42 / h, f'v6 回撤 −{v6x:.1f}%，不到 BM-主（−{bx:.1f}%）的一半；年化 {v6y:.2f}%，比 BM-主少 {by - v6y:.2f} 点，也低于 A1、现行配置、K2A',
         fontsize=14, weight='bold', color=INK)
fig.text(.04, 1 + .12 / h, '设计期 2006–15，扣成本，基准为全收益（§5.1）。越靠右上越好：右 = 回撤浅，上 = 收益高。蓝 = v6 与挑战者，灰 = 基准，空心 = 参照',
         fontsize=10.5, color=MUTED)
fig.savefig(OUT / 'h2-peers.png', dpi=150, bbox_inches='tight'); plt.close(fig)
print('ok', round(total, 2), {k: tuple(round(x, 1) for x in v) for k, v in S.items()})

# ---------- h3–h6：读 health_extra.py 的输出（同目录 health-extra.json） ----------
EX = SRC / 'health-extra.json'
if EX.exists():
    import matplotlib.dates as mdates, numpy as np, pandas as pd
    X = json.load(open(EX, encoding='utf-8'))
    wk = pd.to_datetime(X['weeks'])
    LINE = {'v6': (BLUE, 2.6, '-'), 'K2A': (INK, 1.4, '-'), '现行配置': ('#7c3aed', 1.4, '-'), 'BM-主': (GREY, 1.6, '-'),
            'BM-同仓位': ('#cbd5e1', 1.6, '-'), 'A1': (INK, 1.0, ':')}
    ch = X['character']
    # h3 净值 + 回撤
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 6.4), sharex=True, gridspec_kw={'height_ratios': [2.2, 1], 'hspace': .08})
    ends = sorted(((X['nav_weekly'][k][-1], k) for k in LINE), key=lambda t: t[0])
    ly, last = {}, -1e9
    for y, k in ends:                       # 终点标签在对数刻度上至少隔开 0.2（对数）
        v = np.log(y); v = max(v, last + .2); ly[k] = np.exp(v); last = v
    for k, (c, lw, ls) in LINE.items():
        a1.plot(wk, X['nav_weekly'][k], color=c, lw=lw, ls=ls)
        a1.annotate(f'{k}  {100 * ch[k]["年化"]:.1f}%', (wk[-1], X['nav_weekly'][k][-1]), xytext=(wk[-1] + pd.Timedelta(days=40), ly[k]),
                    textcoords='data', va='center', fontsize=10.5, color=c if k != 'BM-同仓位' else MUTED, weight='bold' if k == 'v6' else 'normal',
                    arrowprops=dict(arrowstyle='-', color=GREY, lw=.6))
    a1.set_yscale('log'); a1.set_ylabel('净值（2006 年初 = 1，对数）', color=MUTED); a1.grid(alpha=.2); a1.spines['left'].set_visible(True)
    a1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:g}')); a1.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    for k in ('BM-主', 'K2A', 'v6'):
        c = LINE[k][0]
        a2.fill_between(wk, np.array(X['dd_weekly'][k]) * 100, 0, color=c, alpha=.35 if k == 'v6' else .18, lw=0)
        a2.plot(wk, np.array(X['dd_weekly'][k]) * 100, color=c, lw=1.2 if k != 'v6' else 1.8)
    a2.set_ylabel('回撤（%）', color=MUTED); a2.grid(alpha=.2); a2.spines['left'].set_visible(True); a2.set_ylim(-70, 2)
    a2.text(wk[len(wk) // 9], -66, f'BM-主 最深 {100 * ch["BM-主"]["最大回撤"]:.1f}%'.replace('-', '−'), color=MUTED, fontsize=10)
    a2.text(wk[len(wk) // 9], -30, f'v6 最深 {100 * ch["v6"]["最大回撤"]:.1f}%'.replace('-', '−'), color=BLUE, fontsize=10, weight='bold')
    a2.xaxis.set_major_locator(mdates.YearLocator()); a2.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    fig.subplots_adjust(top=.97, right=.86)
    h = fig.get_figheight()
    fig.text(.04, 1 + .42 / h, f'v6 一路的回撤都比基准浅一半以上；终点和 BM-主、K2A 差不多，比现行配置和 A1 低', fontsize=14, weight='bold', color=INK)
    fig.text(.04, 1 + .12 / h, '设计期 2006–15，扣成本，基准为全收益。上：净值（对数刻度）；下：从此前最高点算的回撤，蓝 = v6，黑 = K2A，灰 = BM-主', fontsize=10.5, color=MUTED)
    fig.savefig(OUT / 'h3-nav.png', dpi=150, bbox_inches='tight'); plt.close(fig)

    # h4 两次急跌
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
    for ax, tag in zip(axs, ('2008', '2015')):
        C = X['crash'][tag]; n = len(C['csi300']); t = np.arange(n)
        ax.plot(t, (np.array(C['csi300']) - 1) * 100, color=AMBER, lw=1.4, label='沪深300（全收益）')
        for k in ('BM-主', 'K2A', 'v6'):
            c, lw, _ = LINE[k]
            ax.plot(t, (np.array(C['path'][k]) - 1) * 100, color=c, lw=lw, label=k)
        for k, c in (('v6', BLUE), ('K2A', INK), ('沪深300', AMBER)):
            v = C['low'][k] * 100
            ax.annotate(f'{k} 最低 {v:.0f}%'.replace('-', '−'), (n - 1, (C['end'][k]) * 100), xytext=(4, 0), textcoords='offset points',
                        fontsize=9.5, color=c, va='center', weight='bold' if k == 'v6' else 'normal')
        ax.axhline(0, color=GREY, lw=.8); ax.grid(alpha=.2); ax.spines['left'].set_visible(True)
        ax.set_title(f'{tag}：从沪深300 见顶（{C["peak"]}）算起 {n - 1} 个交易日', fontsize=11.5, color=INK, loc='left')
        ax.set_xlabel('见顶后第几个交易日', color=MUTED)
    axs[0].set_ylabel('相对见顶日的涨跌（%）', color=MUTED); axs[0].legend(frameon=False, fontsize=9.5, loc='lower left')
    fig.subplots_adjust(top=.86, wspace=.32, right=.92)
    h = fig.get_figheight(); L8, L15 = X['crash']['2008']['low'], X['crash']['2015']['low']
    fig.text(.04, 1 + .3 / h, f'2008 年 v6 最多亏 {-100 * L8["v6"]:.0f}%（沪深300 亏 {-100 * L8["沪深300"]:.0f}%），比 K2A 少亏；2015 年亏 {-100 * L15["v6"]:.0f}%，比 K2A（{-100 * L15["K2A"]:.0f}%）多亏',
             fontsize=14, weight='bold', color=INK)
    fig.text(.04, 1 + .04 / h, '净值从沪深300 全收益见顶当天算起；蓝 = v6，黑 = K2A，灰 = BM-主，橙 = 沪深300', fontsize=10.5, color=MUTED)
    fig.savefig(OUT / 'h4-crash.png', dpi=150, bbox_inches='tight'); plt.close(fig)

    # h5 四种行情
    names = ['牛市', '回调', '熊市', '反弹']; Rg = X['regimes']
    fig, ax = plt.subplots(figsize=(11, 4.2))
    refs = [('BM-主', GREY), ('BM-同仓位', '#94a3b8'), ('K2A', INK)]
    x = np.arange(4); wdt = .26
    for j, (ref, c) in enumerate(refs):
        vals = [Rg[nm][ref]['合计'] for nm in names]
        bars = ax.bar(x + (j - 1) * wdt, vals, wdt * .92, color=[TEAL if v > 0 else AMBER for v in vals], alpha=1 - .28 * j, edgecolor='none')
        for xi, v in zip(x + (j - 1) * wdt, vals):
            ax.text(xi, v + (4 if v >= 0 else -4), f'{v:+.0f}'.replace('-', '−'), ha='center', va='bottom' if v >= 0 else 'top', fontsize=9.5, color=INK)
        for xi in x + (j - 1) * wdt:
            ax.text(xi, -175, ref, ha='center', fontsize=8.5, color=MUTED, rotation=0)
    ax.axhline(0, color=GREY, lw=.8)
    ax.set_xticks(x, [f'{nm}（{Rg[nm]["月数"]} 个月）' for nm in names]); ax.tick_params(axis='x', length=0, pad=22)
    ax.set_ylabel('v6 月超额相加（百分点）', color=MUTED); ax.set_ylim(-190, 150); ax.grid(axis='y', alpha=.2); ax.spines['left'].set_visible(True)
    fig.subplots_adjust(top=.97)
    h = fig.get_figheight()
    fig.text(.04, 1 + .42 / h, f'熊市和回调对 BM-主多赚 {Rg["熊市"]["BM-主"]["合计"] + Rg["回调"]["BM-主"]["合计"]:.0f} 点，牛市和反弹少赚 {-(Rg["牛市"]["BM-主"]["合计"] + Rg["反弹"]["BM-主"]["合计"]):.0f} 点；对 K2A 四种行情都差不多',
             fontsize=14, weight='bold', color=INK)
    fig.text(.04, 1 + .12 / h, '按沪深300 全收益在每个月末划分：12 个月涨且当月涨 = 牛市，12 个月涨当月跌 = 回调，12 个月跌当月跌 = 熊市，12 个月跌当月涨 = 反弹。每组三根柱依次对 BM-主、BM-同仓位、K2A',
             fontsize=10, color=MUTED)
    fig.savefig(OUT / 'h5-regime.png', dpi=150, bbox_inches='tight'); plt.close(fig)

    # h6 任意起点
    A = X['anystart']; refs = ['BM-主', 'BM-同仓位', 'K2A', '现行配置', 'A1']
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw={'width_ratios': [1, 1.35], 'wspace': .28})
    for j, y in enumerate(('1', '3', '5')):
        vals = [100 * A[y][r]['跑赢占比'] for r in refs]
        a1.barh(np.arange(5) + (j - 1) * .26, vals, .24, color=BLUE, alpha=.35 + .3 * j, label=f'持有 {y} 年')
        if y == '5':
            for i, v in enumerate(vals):
                a1.text(v + 1.5, i + .26, f'{v:.0f}%', va='center', fontsize=10, color=INK, weight='bold')
    a1.axvline(50, color=GREY, lw=.8, ls='--'); a1.set_yticks(np.arange(5), [f'对 {r}' for r in refs]); a1.invert_yaxis()
    a1.set_xlim(0, 110); a1.set_xlabel('v6 跑赢的起点占比（%）', color=MUTED); a1.legend(frameon=False, fontsize=9, loc='lower right'); a1.tick_params(axis='y', length=0)
    st = pd.to_datetime(A['3']['起点']); ex = np.array(A['3']['BM-主']['逐个'])
    a2.bar(st, ex, width=25, color=[TEAL if v > 0 else AMBER for v in ex], edgecolor='none')
    a2.axhline(0, color=GREY, lw=.8); a2.grid(axis='y', alpha=.2); a2.spines['left'].set_visible(True)
    a2.set_ylabel('持有 3 年，每年比 BM-主多（点）', color=MUTED); a2.xaxis.set_major_locator(mdates.YearLocator()); a2.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    a2.set_title('每个月初买入、持有 3 年的超额（对 BM-主）', fontsize=11, color=INK, loc='left')
    fig.subplots_adjust(top=.86)
    h = fig.get_figheight(); f5 = A['5']
    fig.text(.04, 1 + .3 / h, f'持有 5 年，{100 * f5["BM-主"]["跑赢占比"]:.0f}% 的起点跑赢 BM-主、{100 * f5["BM-同仓位"]["跑赢占比"]:.0f}% 跑赢同仓位基准；对 K2A 和现行配置只有六成左右',
             fontsize=14, weight='bold', color=INK)
    fig.text(.04, 1 + .04 / h, '2006–15 每个月第一个交易日买入，持满 1 / 3 / 5 年（252 / 756 / 1260 个交易日），比较年化；虚线 = 一半起点', fontsize=10.5, color=MUTED)
    fig.savefig(OUT / 'h6-anystart.png', dpi=150, bbox_inches='tight'); plt.close(fig)
    print('extra charts ok')
