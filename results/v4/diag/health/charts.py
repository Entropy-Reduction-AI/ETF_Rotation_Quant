# v4 体检报告的图。只读 results/v4/r5 的设计期产物，只到 2015-12-31。
# 用法：python results/v4/diag/health/charts.py <输出目录>
# 四种行情的拿现金 / 选标的拆分来自签收与设计期简报（STATES 常量），R5c 之后按新简报更新。
import sys, pathlib
import numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parents[4]
R = ROOT / 'results/v4/r5'
OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'out'); OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'axes.grid': True, 'grid.alpha': .22, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED = '#111827', '#6b7280'
IDX, TRD, A1C, A2C = '#1d4ed8', '#0d9488', '#d97706', '#7c3aed'
GOOD, BAD, CASH = '#16a34a', '#ea580c', '#9ca3af'
POOL = {'index': 'U-指数池（能排名的）', 'tradable': 'U-可交易池（当年真能买到的）'}

# 设计期简报 R5c（2026-10-30）：拿现金、选标的，1 位小数，单位百分点。
# 分项相加与合计 excess 可能差 0.1，来自各自四舍五入。
STATES = {
    'index':    {'牛市': (-24.6, 22.7), '回调': (21.0, 6.4), '熊市': (45.3, 49.7), '反弹': (-23.1, -30.9)},
    'tradable': {'牛市': (-170.9, -5.6), '回调': (70.7, 12.0), '熊市': (97.3, 14.2), '反弹': (-63.2, -7.5)},
}

g = pd.read_csv(R / 'gate-inputs.csv', index_col=0, parse_dates=True)
BM = g['benchmark'].fillna(0.0)
STATE = pd.read_csv(R / 'month-states.csv', index_col=0, parse_dates=True)['state']
def rd(case, pool): return pd.read_csv(R / f'design/{case}/{pool}/net.csv', index_col=0, parse_dates=True)['net']
def cagr(r): r = r.dropna(); return (1 + r).prod() ** (252 / len(r)) - 1
def mdd(r): n = (1 + r.dropna()).cumprod(); return (n / n.cummax() - 1).min()
def head(ax, title, sub, pad=30):
    ax.set_title(title, loc='left', fontsize=14.5, weight='bold', color=INK, pad=pad)
    ax.text(0, 1.02 + pad / 1000, sub, transform=ax.transAxes, fontsize=10.5, color=MUTED, va='bottom')
def minus(s): return s.replace('-', '−')

# ---------- h1 净值与回撤：两个池并排 ----------
def chart_nav():
    fig, axes = plt.subplots(2, 2, figsize=(12, 7.4), sharex=True, sharey='row', gridspec_kw={'height_ratios': [2.5, 1], 'hspace': .08, 'wspace': .32})
    for j, pool in enumerate(['index', 'tradable']):
        ser = {'E2 新口径': rd('B0', pool), '基准': BM, 'A1 双动量': rd('A1', pool), 'A2 五腿均线': rd('A2', pool)}
        col = {'E2 新口径': IDX if pool == 'index' else TRD, '基准': INK, 'A1 双动量': A1C, 'A2 五腿均线': A2C}
        ax, bx = axes[0, j], axes[1, j]
        ends = []
        for k, r in ser.items():
            r = r.loc['2006':]; n = (1 + r).cumprod()
            ax.plot(n.index, n.values, color=col[k], lw=2.4 if k == 'E2 新口径' else 1.6, zorder=3 if k == 'E2 新口径' else 2)
            ends.append((n.iloc[-1], k, cagr(r), mdd(r)))
            bx.plot(n.index, (n / n.cummax() - 1) * 100, color=col[k], lw=1.8 if k == 'E2 新口径' else 1.3)
        ends.sort(reverse=True); last = None
        for v, k, c, d in ends:
            y = v if last is None else min(v, last / 1.38); last = y
            ax.text(pd.Timestamp('2016-02-01'), y, f'{k}\n{v:.1f} 倍 · 年化 {c*100:.1f}%', color=col[k], fontsize=10, weight='bold', va='center')
        ax.set_yscale('log'); ax.set_yticks([1, 2, 4, 8]); ax.set_yticklabels(['1', '2', '4', '8']); ax.set_ylim(.85, 13)
        ax.set_title(POOL[pool], loc='left', fontsize=12.5, weight='bold', color=col['E2 新口径'])
        dd = '  '.join(minus(f'{k} {d*100:.0f}%') for _, k, _, d in sorted(ends, key=lambda e: e[3]))
        bx.text(.01, .06, '最大回撤：' + dd, transform=bx.transAxes, fontsize=9.5, color=INK)
        bx.set_ylim(-72, 3); bx.set_xlim(pd.Timestamp('2006-01-01'), pd.Timestamp('2019-01-01'))
        bx.set_xticks([pd.Timestamp(f'{y}-01-01') for y in (2006, 2008, 2010, 2012, 2014, 2016)])
        bx.set_xticklabels(['2006', '2008', '2010', '2012', '2014', '2016'])
    axes[0, 0].set_ylabel('净值（对数，2006 年初 = 1）'); axes[1, 0].set_ylabel('从高点回撤（%）')
    fig.suptitle('E2 新口径：能排名的池子跑赢基准；换成当年真能买到的，十年没跑过基准', x=.125, ha='left', va='bottom', y=1.04, fontsize=14.5, weight='bold', color=INK)
    fig.text(.125, 1.005, '设计期 2006–2015，人民币、含分红、扣成本。A1、A2 是公开同行，只做对照；两个池都用 R5c 签收后的净值。', fontsize=10.5, color=MUTED, va='bottom')
    fig.savefig(OUT / 'h1-nav.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)

# ---------- h3 四种行情：两个池并排，拿现金 / 选标的 ----------
def chart_states():
    mb = (1 + BM).resample('ME').prod() - 1
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.4), sharey=True, gridspec_kw={'wspace': .06})
    names = ['牛市', '回调', '熊市', '反弹']; sub = ['大势涨\n本月涨', '大势涨\n本月跌', '大势跌\n本月跌', '大势跌\n本月涨']
    for ax, pool in zip(axes, ['index', 'tradable']):
        m = (1 + rd('B0', pool)).resample('ME').prod() - 1
        df = pd.DataFrame({'x': m - mb}).join(STATE.rename('s'), how='inner')
        x = np.arange(4); w = .36
        for i, s in enumerate(names):
            c, sel = STATES[pool][s]; tot = c + sel
            ax.bar(i - w / 2 - .01, c, w, color=CASH, zorder=2); ax.bar(i + w / 2 + .01, sel, w, color=IDX if pool == 'index' else TRD, zorder=2)
            for v, dx in ((c, -w / 2), (sel, w / 2)):
                ax.text(i + dx, v + (4 if v >= 0 else -4), minus(f'{v:+.0f}'), ha='center', va='bottom' if v >= 0 else 'top', fontsize=10, color=INK)
            win = (df[df.s == s].x > 0).mean() * 100; n = int((df.s == s).sum())
            ax.text(i, 160, minus(f'合计 {tot:+.0f}'), ha='center', fontsize=12.5, weight='bold', color=GOOD if tot > 0 else BAD)
            ax.text(i, 128, f'{n} 个月\n跑赢 {win:.0f}% 的月份', ha='center', fontsize=9, color=MUTED, linespacing=1.3)
        ax.axhline(0, color=INK, lw=.9); ax.set_xticks(x); ax.set_xticklabels([f'{a}\n{b}' for a, b in zip(names, sub)], fontsize=10.5)
        ax.grid(axis='x', visible=False); ax.set_ylim(-200, 175)
        ax.set_title(POOL[pool], loc='left', fontsize=12.5, weight='bold', color=IDX if pool == 'index' else TRD, pad=8)
    axes[0].set_ylabel('相对基准的超额（百分点，按月相加）')
    h = [plt.Rectangle((0, 0), 1, 1, color=CASH), plt.Rectangle((0, 0), 1, 1, color=IDX), plt.Rectangle((0, 0), 1, 1, color=TRD)]
    fig.legend(h, ['拿现金带来的', '选标的带来的（U-指数）', '选标的带来的（U-可交易）'], loc='lower center', ncol=3, frameon=False, bbox_to_anchor=(.5, -.1), fontsize=10.5)
    fig.suptitle('熊市两头都赢；牛市里指数池打平，可交易池被现金拖累 176 个百分点', x=.125, ha='left', va='bottom', y=1.04, fontsize=14.5, weight='bold', color=INK)
    fig.text(.125, 1.005, 'E2 新口径，设计期 2006–2015 的 120 个月，按沪深300 全收益的 12 个月和 1 个月涨跌，只用当时的数据分成四种行情。', fontsize=10.5, color=MUTED, va='bottom')
    fig.savefig(OUT / 'h3-states.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)

# ---------- h4 任意起点：持有 3 年，每个月一个起点 ----------
def rolling(r, years):
    idx = r.index; n = (1 + r).cumprod(); nb = (1 + BM).cumprod(); rows = []
    for s in pd.date_range('2006-01-01', '2015-12-31', freq='MS'):
        e = s + pd.DateOffset(years=years)
        if e > pd.Timestamp('2016-01-01'): break
        a = idx[idx >= s][0]; b = idx[idx < e][-1]; p = idx[idx < a][-1]
        rows.append((s, ((n[b] / n[p]) ** (1 / years) - (nb[b] / nb[p]) ** (1 / years)) * 100))
    return pd.Series(dict(rows))
def chart_anystart(years=3):
    fig, axes = plt.subplots(2, 1, figsize=(11.5, 6.6), sharex=True, gridspec_kw={'hspace': .22})
    for ax, pool in zip(axes, ['index', 'tradable']):
        d = rolling(rd('B0', pool), years)
        ax.bar(d.index, d.values, width=24, color=[GOOD if v > 0 else BAD for v in d.values], zorder=2)
        ax.axhline(0, color=INK, lw=.9)
        ax.text(.99, .92, f'跑赢 {(d > 0).mean()*100:.0f}% 的起点 · 中位数 {minus(f"{d.median():+.1f}")}', transform=ax.transAxes, ha='right', fontsize=11, weight='bold', color=INK)
        ax.set_ylabel('每年多（少）赚\n（百分点）', fontsize=10.5)
        ax.set_title(POOL[pool], loc='left', fontsize=12, weight='bold', color=IDX if pool == 'index' else TRD, pad=6)
    axes[1].xaxis.set_major_locator(matplotlib.dates.YearLocator()); axes[1].xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%Y'))
    fig.suptitle(f'什么时候买入决定了结果：好看的十年主要靠 2006–07 年买入', x=.125, ha='left', va='bottom', y=1.04, fontsize=14.5, weight='bold', color=INK)
    fig.text(.125, 1.005, f'每根柱子 = 从那个月初买入、持有 {years} 年，E2 新口径比基准每年多（少）赚的百分点。设计期 2006–2015。', fontsize=10.5, color=MUTED, va='bottom')
    fig.savefig(OUT / 'h4-anystart.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)

# ---------- h2 逐年超额：E2 与 A1（U-指数） ----------
def chart_yearly():
    e = rd('B0', 'index').loc['2006':]; a = rd('A1', 'index').loc['2006':]; b = BM.loc['2006':]
    y = lambda r: (1 + r).groupby(r.index.year).prod() - 1
    ex, exa = (y(e) - y(b)) * 100, (y(a) - y(b)) * 100
    fig, ax = plt.subplots(figsize=(11, 4.6)); x = np.arange(len(ex)); w = .38
    ax.bar(x - w / 2, ex.values, w, color=IDX, zorder=2, label='E2 新口径 − 基准')
    ax.bar(x + w / 2, exa.values, w, color=A1C, zorder=2, label='A1 双动量 − 基准')
    for i, (v, va) in enumerate(zip(ex.values, exa.values)):
        ax.text(i - w / 2, v + (1.5 if v > 0 else -1.5), minus(f'{v:+.0f}'), ha='center', va='bottom' if v > 0 else 'top', fontsize=9.5, color=INK, weight='bold')
        ax.text(i + w / 2, va + (1.5 if va > 0 else -1.5), minus(f'{va:+.0f}'), ha='center', va='bottom' if va > 0 else 'top', fontsize=9.5, color=MUTED)
    ax.axhline(0, color=INK, lw=.9); ax.set_xticks(x); ax.set_xticklabels(ex.index); ax.grid(axis='x', visible=False)
    ax.set_ylim(-95, 92); ax.set_ylabel('当年收益 − 基准（百分点）'); ax.legend(loc='lower right', frameon=False, fontsize=10.5)
    head(ax, '2008 年 A1 拿国债多赚 76 点，2013 年拿美股多赚 25 点；E2 新口径两次都没跟上', 'U-指数池。每根柱子 = 当年收益减基准（百分点）。2009 年两者都大幅落后于反弹。')
    fig.savefig(OUT / 'h2-yearly.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)

# ---------- h5 稳健性：只改一处，年化和回撤变了多少 ----------
def chart_robust():
    rows = [('回看期', '10/40/90/180 日', 'lookback-10-40-90-180'), ('回看期', '15/50/100/200 日', 'lookback-15-50-100-200'), ('回看期', '30/80/150/300 日', 'lookback-30-80-150-300'),
            ('离场线', '8%', 'exit-8'), ('离场线', '12%', 'exit-12'), ('离场线', '15%', 'exit-15'),
            ('成本与时点', '成本加倍', 'cost-double'), ('成本与时点', '晚一天成交', 'delay-1d'), ('成本与时点', '美股分红只拿 90%', 'us-div-90'),
            ('去掉最好的', '去掉第 1 名', 'drop-best-1'), ('去掉最好的', '去掉前 2 名', 'drop-best-2'), ('去掉最好的', '去掉前 3 名', 'drop-best-3'),
            ('载体', '不用相近替身', 'no-substitute')]
    base = {p: (cagr(rd('B0', p).loc['2006':]), mdd(rd('B0', p).loc['2006':])) for p in ('index', 'tradable')}
    fig, axes = plt.subplots(1, 2, figsize=(12, 7.2), sharey=True, gridspec_kw={'wspace': .08})
    ylab = []; yy = []; pos = 0; grp = None; seps = []
    for gname, lab, case in rows:
        if gname != grp:
            if grp is not None: pos += .6; seps.append(pos - .3)
            grp = gname
        ylab.append(f'{gname} · {lab}'); yy.append(pos); pos += 1
    yy = np.array(yy)[::-1] if False else -np.array(yy)
    for k, (ax, metric) in enumerate(zip(axes, ['年化', '最大回撤'])):
        ax.axvspan(-1, 1, color='#f3f4f6', zorder=0, lw=0)
        for pool, mk, c in (('index', 'o', IDX), ('tradable', 'D', TRD)):
            vals = []
            for (_, _, case), y in zip(rows, yy):
                f = R / f'design/{case}/{pool}/net.csv'
                if not f.exists(): vals.append(np.nan); continue
                r = rd(case, pool).loc['2006':]
                v = (cagr(r) - base[pool][0]) * 100 if k == 0 else (mdd(r) - base[pool][1]) * 100
                vals.append(v)
                ax.scatter(v, y + (.16 if pool == 'index' else -.16), marker=mk, s=60, color=c, zorder=3, edgecolor='white', linewidth=1)
                ax.text(v + (0.25 if v >= 0 else -0.25), y + (.16 if pool == 'index' else -.16), minus(f'{v:+.1f}'), va='center', ha='left' if v >= 0 else 'right', fontsize=8.5, color=c)
        ax.axvline(0, color=INK, lw=1); ax.set_xlim(-7, 8.5); ax.grid(axis='y', visible=False)
        for s in seps: ax.axhline(-s, color='#e5e7eb', lw=1)
        ax.set_xlabel('年化比原样多（+）或少（−）几个百分点' if k == 0 else '最大回撤比原样浅（+）或深（−）几个百分点', fontsize=10.5)
        ax.set_title(metric, loc='left', fontsize=12.5, weight='bold', color=INK, pad=6)
    axes[0].set_yticks(yy); axes[0].set_yticklabels(ylab, fontsize=10.5)
    h = [plt.Line2D([], [], marker='o', ls='', color=IDX, ms=8), plt.Line2D([], [], marker='D', ls='', color=TRD, ms=7), plt.Rectangle((0, 0), 1, 1, color='#f3f4f6')]
    fig.legend(h, [f'U-指数池（原样年化 {base["index"][0]*100:.1f}%）', f'U-可交易池（原样年化 {base["tradable"][0]*100:.1f}%）', '±1 个百分点以内'], loc='lower center', ncol=3, frameon=False, bbox_to_anchor=(.55, -.03), fontsize=10.5)
    fig.suptitle('改参数不会塌；可交易池更怕“少了最好的那只”和“晚一天成交”', x=.125, ha='left', va='bottom', y=1.04, fontsize=14.5, weight='bold', color=INK)
    fig.text(.125, 1.005, '每行只改一处，其余和 E2 新口径原样相同。点在灰带里 = 差别在 1 个百分点以内。设计期 2006–2015。', fontsize=10.5, color=MUTED, va='bottom')
    fig.savefig(OUT / 'h5-robust.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)

# ---------- h0 两个池子每年能参加排名的容器（按大类） ----------
GCOL = {'A 股': '#2563eb', '港股': '#0d9488', '美股': '#7c3aed', '海外主题（QDII、LOF）': '#d97706', '商品、债券、现金': '#9ca3af'}
def chart_pools():
    f = pathlib.Path(__file__).with_name('pool-counts.csv')
    if not f.exists(): return
    d = pd.read_csv(f); years = list(range(2006, 2016))
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True, gridspec_kw={'wspace': .06})
    for ax, pool in zip(axes, ['index', 'tradable']):
        t = d[d.pool == pool].groupby(['year', 'group']).size().unstack(fill_value=0).reindex(years, fill_value=0)
        base = np.zeros(len(years))
        for gname, c in GCOL.items():
            v = t[gname].values if gname in t else np.zeros(len(years))
            ax.bar(years, v, .72, bottom=base, color=c, edgecolor='white', linewidth=1, zorder=2, label=gname); base += v
        for x, v in zip(years, base): ax.text(x, v + .4, str(int(v)), ha='center', fontsize=10, weight='bold', color=INK)
        ax.set_xticks(years); ax.set_xticklabels([str(y) for y in years], fontsize=9.5); ax.grid(axis='x', visible=False)
        ax.set_title(POOL[pool], loc='left', fontsize=12.5, weight='bold', color=IDX if pool == 'index' else TRD, pad=6)
    axes[0].set_ylabel('当年能参加排名的容器数'); axes[0].set_ylim(0, 30)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc='lower center', ncol=5, frameon=False, bbox_to_anchor=(.5, -.08), fontsize=10)
    fig.suptitle('能排名的一开始就有 17 个；当年真能买到的，2006 年只有沪深300 一个', x=.125, ha='left', va='bottom', y=1.04, fontsize=14.5, weight='bold', color=INK)
    fig.text(.125, 1.005, '不含 T4 的美股行业和港股分类，不含现金。可交易池按当天有没有载体（含 3,000 万成交额门槛）统计，一年里有一天能买就算。', fontsize=10.5, color=MUTED, va='bottom')
    fig.savefig(OUT / 'h0-pools.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)

# ---------- h6 两次大跌：从沪深300 高点算起的跌幅和现金 ----------
def chart_crash():
    f = pathlib.Path(__file__).with_name('b0-cash-weights.csv')
    if not f.exists(): return
    cw = pd.read_csv(f, index_col=0, parse_dates=True)
    lines = {'沪深300': (cw['csi300_level'].pct_change().fillna(0), INK, 1.6), 'A1 双动量': (rd('A1', 'index'), A1C, 1.6),
             'E2 · U-指数': (rd('B0', 'index'), IDX, 2.3), 'E2 · U-可交易': (rd('B0', 'tradable'), TRD, 2.3)}
    eps = [('2008：跌了一年', '2007-10-16', 290), ('2015：三周跌掉一半', '2015-06-08', 140)]
    fig, axes = plt.subplots(2, 2, figsize=(12, 7.2), sharex=True, gridspec_kw={'height_ratios': [2.4, 1], 'hspace': .1, 'wspace': .12})
    for j, (title, peak, n) in enumerate(eps):
        ax, bx = axes[0, j], axes[1, j]
        idx = cw.index; i0 = idx.get_loc(pd.Timestamp(peak)); lo = max(i0 - 20, 0); hi = min(i0 + n, len(idx) - 1)
        win = idx[lo:hi + 1]; x = np.arange(lo, hi + 1) - i0
        ends = []
        for k, (r, c, lw) in lines.items():
            r = r.reindex(win).fillna(0); lvl = (1 + r).cumprod(); lvl = lvl / lvl.loc[pd.Timestamp(peak)] - 1
            ax.plot(x, lvl.values * 100, color=c, lw=lw, label=k)
            ends.append([lvl.values[-1] * 100, k, c])
        ends.sort(key=lambda e: -e[0])
        for a in range(1, len(ends)):
            ends[a][0] = min(ends[a][0], ends[a - 1][0] - 5.5)
        for v, k, c in ends:
            ax.text(x[-1] + 3, v, minus(f'{k} {v:+.0f}%') if False else k, color=c, fontsize=9.5, weight='bold', va='center')
        ax.axvline(0, color=MUTED, lw=.8, ls='--'); ax.axhline(0, color=INK, lw=.6)
        ax.set_title(title, loc='left', fontsize=12.5, weight='bold', color=INK, pad=6); ax.set_ylim(-75, 25)
        for k, cc in (('index_cash', IDX), ('tradable_cash', TRD)):
            bx.plot(x, cw[k].reindex(win).values * 100, color=cc, lw=1.6)
        bx.set_ylim(0, 105); bx.axvline(0, color=MUTED, lw=.8, ls='--'); bx.set_xlim(-20, 330)
        bx.set_xlabel('沪深300 见顶后的交易日（0 = 见顶那天）', fontsize=10.5)
    axes[0, 0].set_ylabel('从沪深300 见顶那天算起（%）'); axes[1, 0].set_ylabel('E2 现金（%）')
    axes[0, 0].annotate('A1：标普500 的 12 个月\n先跌破现金，全部换国债', xy=(32, -18), xytext=(5, -62), fontsize=9.5, color=A1C, arrowprops=dict(arrowstyle='->', color=A1C))
    axes[0, 1].annotate('A1：沪深300 过去 12 个月\n仍涨 115%，一直满仓', xy=(15, -20), xytext=(70, 12), fontsize=9.5, color=A1C, arrowprops=dict(arrowstyle='->', color=A1C))
    axes[1, 0].text(115, 4, 'U-指数：2008 年 1–2 月\n反弹时又几乎满仓买回', fontsize=9.5, color=IDX)
    if float(rd('B0', 'tradable').get(pd.Timestamp('2008-01-03'), 0)) > 0.2:
        axes[0, 0].annotate('这一跳是数据错误：红利 ETF\n2008-01-02 一笔错价（R5c 修）', xy=(55, 18), xytext=(120, 18), fontsize=9.5, color=TRD, va='center', arrowprops=dict(arrowstyle='->', color=TRD))
    axes[1, 1].text(30, 80, '第 10 天现金升到一半时，U-指数已经亏了 20%', fontsize=9.5, color=IDX)
    fig.suptitle('同样的规则，2008 年有时间反应，2015 年来不及', x=.125, ha='left', va='bottom', y=1.0, fontsize=14.5, weight='bold', color=INK)
    fig.text(.125, .965, '上：从沪深300 见顶那天起各自的涨跌。下：E2 新口径的现金仓位（蓝 = U-指数池，绿 = U-可交易池）。两张图的横轴长度相同，可以直接比速度。', fontsize=10.5, color=MUTED, va='bottom')
    fig.savefig(OUT / 'h6-crash.png', dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)

if __name__ == '__main__':
    chart_nav(); chart_states(); chart_anystart(); chart_yearly(); chart_robust(); chart_pools(); chart_crash()
    print('written to', OUT)
