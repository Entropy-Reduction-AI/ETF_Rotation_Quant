"""v6 一次性检验报告：从结果目录画图、出填数表。结构和读法在开考前定死（骨架 0.4.1、D49–D51），这里只读数、画图、选结论句。
用法：python -I scripts/v6_report/oneshot_fill.py <结果目录> <图输出目录> <填数 JSON 输出>
结果目录：results/v6/oneshot/（正式）或 results/v6/rehearsal/（预演）。可选文件 returns-daily.csv、random-paths.csv 不在时，对应的图跳过。
"""
import sys, json, csv, pathlib
from statistics import NormalDist
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

SRC, OUT, FACTS = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
INK, MUTED, GREY, BLUE, AMBER, TEAL, RED, PEND = '#151b26', '#5d6676', '#9ca3af', '#2563eb', '#d97706', '#0d9488', '#c2410c', '#eef1f5'
J = lambda n: json.load(open(SRC / n, encoding='utf-8'))
C = lambda n: pd.read_csv(SRC / n)
man = J('manifest.json')['窗口']
EX = f"{man['exam_start'][:7]} → {man['exam_end'][:7]}"
FULL = f"{man['full_start'][:4]}–{man['full_end'][:4]}"
REH = man.get('name') == '预演'
facts = {'窗口': man, '检验段': EX, '全段': FULL, '预演': REH}
mm = lambda v: f'{v:+.1f}'.replace('-', '−')
pc = lambda v: f'{100 * v:.1f}%'.replace('-', '−')


NAME = {'NBI': '纳指生物科技', 'NDX': '纳指100', 'SPX': '标普500', 'DJIA': '道琼斯', 'SOX': '费城半导体', 'DWRTF': '美国 REIT',
        'XLY': '美股可选消费', 'XLF': '美股金融', 'XLE': '美股能源', 'XLK': '美股科技', 'XLI': '美股工业', 'XLB': '美股原材料',
        'XLV': '美股医疗', 'XLP': '美股必需消费', 'XLU': '美股公用事业', 'chinext': '创业板', 'csi1000': '中证1000', 'csi300': '沪深300',
        'csi500': '中证500', 'allshare-financials-re': '全指金融地产', 'allshare-communication': '全指通信', 'allshare-healthcare': '全指医药',
        'allshare-staples': '全指主要消费', 'allshare-energy': '全指能源', 'allshare-it': '全指信息', 'allshare-discretionary': '全指可选消费',
        'allshare-materials': '全指原材料', 'allshare-industrials': '全指工业', 'allshare-utilities': '全指公用事业'}
cn = lambda k: NAME.get(k, k.replace('theme-', ''))


def save(fig, name):
    if REH:  # 预演样张：右下角盖章，免得和检验结果混淆
        fig.text(.995, -.01, f'预演样张｜{EX} 当检验段｜只用 ≤ 2015 数据｜不是检验结果', ha='right', va='top', fontsize=10, color='#9a3412',
                 bbox=dict(boxstyle='round,pad=.35', fc='#fff7ed', ec='#fdba74'))
    fig.savefig(OUT / name, dpi=130, bbox_inches='tight'); plt.close(fig)


# ---------- 判定与稳健性 ----------
V = J('verdict.json')
cr = C('criteria.csv')
main = cr[cr['进入判定'] == True].iloc[0]
full = cr[cr['窗口'] == '全段'].iloc[0]
GATES = [('最大回撤', '① 回撤', '≤ 40%'), ('保费', '② 防守保费', '≤ 4 点'), ('年化除以回撤', '③ 对 K2A', '高于 K2A'), ('对同仓位基准', '④ 对同仓位基准', '≥ 0')]
facts['主判'] = V['主判']; facts['总结论'] = V['总结论']
facts['判据'] = {k: {'值': float(main[k]), '过': bool(main['过_' + k])} for k, *_ in GATES}
facts['判据']['年化除以回撤']['K2A'] = float(main['增强基准年化除以回撤'])
facts['全段判据'] = {k: {'值': float(full[k]), '过': bool(full['过_' + k])} for k, *_ in GATES}
rob = V['稳健性']
facts['稳健性'] = [{'项': r['item'], '结论': r['结论'], '敏感': r['敏感'], '判据': r['判据'], '变化': r['变化']} for r in rob]
flips = [r['item'] for r in rob if r['敏感'] == '很敏感']
facts['翻转'] = flips

NAMES = {'S1': 'S1 成本加倍', 'S2': 'S2 晚 1 天', 'S3': 'S3 去掉第 1', 'S4': 'S4 去掉前 2', 'S5': 'S5 去掉前 3', 'S6': 'S6 美股 50%', 'S7': 'S7 选前 2', 'S8': 'S8 三票全中'}
rnd = C('random.csv')
paths = C('random-paths.csv') if (SRC / 'random-paths.csv').exists() else None
fig, (a, b) = plt.subplots(1, 2, figsize=(12.5, 5), gridspec_kw={'width_ratios': [1.35, 1]})
cols = ['最大回撤', '保费', '年化除以回撤', '对同仓位基准']
rows = [('主判', {k: facts['判据'][k]['过'] for k in cols}, facts['主判'])] + [(NAMES[r['item']], r['判据'], r['结论']) for r in rob]
for i, (lab, g, concl) in enumerate(rows):
    y = -i
    a.text(-.15, y, lab, ha='right', va='center', fontsize=11.5, color=INK, weight='bold' if i == 0 else 'normal')
    for j, k in enumerate(cols):
        ok = g[k]
        a.add_patch(Rectangle((j, y - .42), .92, .84, fc='#d1fae5' if ok else '#ffedd5', ec='white'))
        a.text(j + .46, y, '过' if ok else '不过', ha='center', va='center', fontsize=11, color=TEAL if ok else RED, weight='bold')
    ok = concl == '通过'
    flip = i > 0 and lab.split()[0] in flips
    a.add_patch(Rectangle((4.15, y - .42), 1.1, .84, fc='#d1fae5' if ok else '#ffedd5', ec=INK if flip else 'white', lw=2.2 if flip else 1))
    a.text(4.7, y, concl + ('　翻转' if flip else ''), ha='center', va='center', fontsize=10.5, color=TEAL if ok else RED, weight='bold')
    if i == 0:
        a.plot([-2.3, 5.3], [y - .55, y - .55], color=GREY, lw=.8)
for j, t in enumerate(['①', '②', '③', '④']):
    a.text(j + .46, .8, t, ha='center', fontsize=12, color=MUTED, weight='bold')
a.text(4.7, .8, '总结论', ha='center', fontsize=11, color=MUTED, weight='bold')
a.set_xlim(-2.4, 5.4); a.set_ylim(-len(rows) + .3, 1.3); a.axis('off')
a.set_title(('主判不通过；8 项也都不通过' if facts['主判'] == '不通过' and not flips else f'稳健性 8 项：{"没有一项让总结论翻转" if not flips else "、".join(flips) + " 让总结论翻转"}'), fontsize=12.5, loc='left', color=INK)
ln0 = C('lines.csv')
if paths is not None:
    for i, w in enumerate(['检验段', '全段']):
        x = 100 * paths[paths['segment'] == w]['annual'].to_numpy()
        me = 100 * float(ln0[(ln0['窗口'] == w) & (ln0['线'] == 'v6')]['年化'].iloc[0])
        pct = 100 * (x < me).mean(); y0 = -1.25 * i
        h, e = np.histogram(x, bins=30); h = h / h.max()
        b.bar(e[:-1], h, width=np.diff(e), bottom=y0, align='edge', color='#cbd5e1', ec='white', lw=.4)
        c = TEAL if pct >= 95 else (AMBER if pct < 50 else '#64748b')
        b.plot([me, me], [y0, y0 + 1.05], color=c, lw=2.4)
        b.text(me, y0 + 1.08, f'v6 {me:.1f}%　第 {pct:.1f}', ha='center', fontsize=10.5, color=c, weight='bold')
        b.text(x.min(), y0 + .55, w, ha='right', fontsize=11.5, color=INK); facts[f'随机分位_{w}'] = pct
    b.set_yticks([]); b.spines['left'].set_visible(False); b.set_xlabel('随机 1000 次的年化 %', color=MUTED)
    b.set_title('同结构随机 1000 次：v6 年化落在哪', fontsize=12.5, loc='left', color=INK)
else:
    rk = rnd[(rnd['book'] == '组合')]
    for i, (_, r) in enumerate(rk.iterrows()):
        c = TEAL if r['percentile'] >= 95 else (AMBER if r['percentile'] < 50 else '#64748b')
        b.barh(-i, r['percentile'], color=c, height=.55)
        b.text(r['percentile'] + 1, -i, f"第 {r['percentile']:.1f}", va='center', fontsize=10.5, color=c, weight='bold')
        b.text(-2, -i, str(r['segment']), ha='right', va='center', fontsize=11)
    b.set_xlim(0, 130); b.set_yticks([]); b.spines['left'].set_visible(False)
    b.set_title('同结构随机 1000 次：v6 排第几百分位', fontsize=12.5, loc='left', color=INK)
facts['随机'] = rnd.to_dict('records')
save(fig, 'o2-robust.png')

# ---------- 钱从哪来 ----------
bl = C('blocks.csv')
BK = ['分红', '仓位差', '等权倾斜', '挑选', '防守', '成本']
facts['拆账'] = bl.to_dict('records')
ex_row = bl[bl['段'].astype(str).str.contains('检验段')]
wrow = ex_row.iloc[0] if len(ex_row) else bl.iloc[-1]
fig, ax = plt.subplots(figsize=(12, 4.2))
cum = 0; xs = ['BM-主'] + BK + ['v6 净']
ax.bar(0, 0, color=GREY)
for i, k in enumerate(BK, 1):
    v = float(wrow[k]); c = TEAL if v >= 0 else RED
    ax.bar(i, v, bottom=cum, color=c, width=.6)
    ax.text(i, cum + v + (.25 if v >= 0 else -.25), mm(v), ha='center', va='bottom' if v >= 0 else 'top', fontsize=11, color=c, weight='bold')
    cum += v
ys = np.cumsum([0] + [float(wrow[k]) for k in BK]); lo_, hi_ = min(ys.min(), 0), max(ys.max(), 0); ax.set_ylim(lo_ - .18 * (hi_ - lo_) - .3, hi_ + .18 * (hi_ - lo_) + .3)
ax.bar(len(BK) + 1, cum, color=BLUE, width=.6); ax.text(len(BK) + 1, cum + (.25 if cum >= 0 else -.25), mm(cum), ha='center', va='bottom' if cum >= 0 else 'top', fontsize=11.5, color=BLUE, weight='bold')
ax.axhline(0, color=GREY, lw=.8); ax.set_xticks(range(len(xs))); ax.set_xticklabels(xs)
ax.set_ylabel('每年比 BM-主多几个点', color=MUTED)
big = max(BK, key=lambda k: abs(float(wrow[k])))
ax.text(0, 0, '起点 0', ha='center', va='bottom', fontsize=10, color=MUTED)
ax.set_title(f'{wrow["段"]}：v6 比 BM-主每年{"多" if cum >= 0 else "少"} {abs(cum):.1f} 点，最大的一块是{big}（{mm(float(wrow[big]))}）', fontsize=12.5, loc='left', color=INK)
save(fig, 'o3w-waterfall.png')
if (SRC / 'cost-real.json').exists():
    CR = J('cost-real.json'); facts['实盘成本'] = CR
    q = CR['指数池']['检验段']; m = main
    fig, (c1, c2) = plt.subplots(1, 2, figsize=(12, 3.4))
    for ax_, lab, v2, v1, thr, fmt in [(c1, '④ 对同仓位基准（点）', q['对同仓位基准'], float(m['对同仓位基准']), 0, '{:+.2f}'),
                                      (c2, '③ 年化 ÷ 回撤', q['年化除以回撤'], float(m['年化除以回撤']), float(m['增强基准年化除以回撤']), '{:.3f}')]:
        for j, (nm, v, c) in enumerate([('单边 0.2%（判定）', v1, BLUE), ('单边 0.01%（只报告）', v2, '#94a3b8')]):
            ax_.barh(-j, v, color=c, height=.55); ax_.text(max(v, 0) if thr == 0 else v, -j, '  ' + fmt.format(v).replace('-', '−'), va='center', fontsize=11, color=INK, weight='bold')
        ax_.axvline(thr, color=RED, ls='--', lw=1.2); ax_.text(thr, .5, ' 门槛 ' + ('0' if thr == 0 else fmt.format(thr)), color=RED, fontsize=10, ha='left')
        ax_.set_yticks([0, -1]); ax_.set_yticklabels(['单边 0.2%（判定）', '单边 0.01%（只报告）']); ax_.tick_params(axis='y', length=0); ax_.spines['left'].set_visible(False); ax_.set_title(lab, fontsize=12, loc='left', color=INK); ax_.set_ylim(-1.6, .9)
        ax_.margins(x=.25)
    fig.suptitle(f'成本两个口径（检验段）：判定只看 0.2%；0.01% 下成本块 {mm(q["成本块"])} 点', x=.01, ha='left', fontsize=12.5, color=INK)
    fig.tight_layout(); save(fig, 'o3c-cost.png')
fig, ax = plt.subplots(figsize=(12, 4.6))
segs = list(bl['段'])
for j, sg in enumerate(segs):
    ax.text(j + .46, .8, str(sg).replace('2021-01→2026-09', '2021–26.9'), ha='center', fontsize=11, color=MUTED, weight='bold')
for i, k in enumerate(BK):
    ax.text(-.15, -i, k, ha='right', va='center', fontsize=12)
    for j, sg in enumerate(segs):
        v = float(bl[bl['段'] == sg][k].iloc[0])
        ax.add_patch(Rectangle((j, -i - .42), .92, .84, fc='#d1fae5' if v >= .5 else ('#ffedd5' if v <= -.5 else '#f3f4f6'), ec='white'))
        ax.text(j + .46, -i, mm(v), ha='center', va='center', fontsize=11.5, color=INK)
LB = pd.read_csv(SRC / 'block-labels.csv').set_index('块')['标签'].to_dict() if (SRC / 'block-labels.csv').exists() else {}
TONE = {'稳定': ('#d1fae5', TEAL), '设计期才有': ('#ffedd5', RED), '不稳定': ('#f3f4f6', MUTED)}
if LB:
    ax.text(len(segs) + .6, .8, '读法（D49-8）', ha='center', fontsize=11, color=MUTED, weight='bold')
    for i, k in enumerate(BK):
        t = LB.get(k, '—'); fc_, tc = TONE.get(t, ('white', MUTED))
        ax.add_patch(Rectangle((len(segs) + .1, -i - .42), 1.0, .84, fc=fc_, ec='white'))
        ax.text(len(segs) + .6, -i, t, ha='center', va='center', fontsize=11, color=tc, weight='bold')
facts['读法'] = LB
ax.set_xlim(-1.6, len(segs) + (1.2 if LB else .1)); ax.set_ylim(-len(BK) + .3, 1.2); ax.axis('off')
ax.set_title('六块 × 各段：每年多或少几个点（绿 ≥ +0.5，橙 ≤ −0.5）', fontsize=12.5, loc='left', color=INK)
save(fig, 'o3-sources.png')

# ---------- 挑选与防守 ----------
pk = J('picks.json'); st = J('stress.json')
fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))
for ax, slot, c in zip(axes, ['美股', 'A股'], [BLUE, AMBER]):
    top = pk[slot]['前10']
    tot = sum(max(x['对挑选的贡献'], 0) for x in top)
    for i, x in enumerate(top):
        ax.barh(-i, x['对挑选的贡献'], color=c if i < 3 else '#cbd5e1')
        ax.text(max(x['对挑选的贡献'], 0) + .3, -i, f"{x['入选月数']} 个月", va='center', fontsize=9.5, color=MUTED)
    ax.axvline(0, color=GREY, lw=.8); ax.set_xlabel('对挑选的贡献（点）', color=MUTED)
    ax.set_yticks([-i for i in range(len(top))]); ax.set_yticklabels([cn(x['候选']) for x in top], fontsize=10.5)
    share = sum(x['对挑选的贡献'] for x in top[:3]) / tot if tot else 0
    ax.set_title(f'{slot}名额：前 3 名占前 10 名贡献的 {100 * share:.0f}%', fontsize=12, loc='left', color=INK)
    facts[f'挑选前3占比_{slot}'] = share
fig.tight_layout(); save(fig, 'o4-picks-defense.png')
fig, ax = plt.subplots(figsize=(12.5, 3.4))
for s_ in st['紧张段']:
    y = 1 if s_['名额'] == '美股' else 0
    a0, a1 = pd.Timestamp(s_['起']), pd.Timestamp(s_['止']) + pd.offsets.MonthEnd(0)
    c = TEAL if s_['累计差'] >= 0 else RED
    ax.add_patch(Rectangle((mdates := a0.toordinal(), y - .3), a1.toordinal() - a0.toordinal(), .6, fc=c, alpha=.8))
    if abs(s_['累计差']) >= .5: ax.text((a0.toordinal() + a1.toordinal()) / 2, y + .42, mm(s_['累计差']), ha='center', fontsize=9, color=c)
ax.set_yticks([0, 1]); ax.set_yticklabels(['A 股名额', '美股名额'])
yrs = range(int(man['full_start'][:4]), int(man['full_end'][:4]) + 2)
ax.set_xticks([pd.Timestamp(f'{y}-01-01').toordinal() for y in yrs]); ax.set_xticklabels([str(y)[2:] for y in yrs], fontsize=9)
ax.set_xlim(pd.Timestamp(man['full_start']).toordinal(), pd.Timestamp(man['full_end']).toordinal()); ax.set_ylim(-.6, 1.8)
ax.set_title('每一次紧张段：绿 = 防守比不设防守多赚，橙 = 少赚（段内累计，点；|差| < 0.5 不标数）', fontsize=12.5, loc='left', color=INK)
save(fig, 'o4b-stress.png')
facts['紧张段'] = st['紧张段']; facts['指名时段'] = st['指名时段']; facts['平时保费'] = st['不紧张保费']

# ---------- 和别人比 ----------
ln = C('lines.csv')
fig, ax = plt.subplots(figsize=(11, 5.2))
for w, fill in [('检验段', True), ('全段', False)]:
    for _, r in ln[ln['窗口'] == w].iterrows():
        c = BLUE if r['线'] == 'v6' else (GREY if str(r['线']).startswith('BM') else INK)
        ax.scatter(100 * r['最大回撤'], r['年化百分点'], s=110 if fill else 70, facecolors=c if fill else 'none', edgecolors=c, lw=1.6, zorder=3)
        if fill:
            ax.annotate(r['线'], (100 * r['最大回撤'], r['年化百分点']), xytext=(6, 4), textcoords='offset points', fontsize=10.5, color=c)
for nm in ln['线'].unique():
    t_ = ln[(ln['线'] == nm)].set_index('窗口')
    if {'检验段', '全段'} <= set(t_.index):
        ax.plot([100 * t_.loc['全段', '最大回撤'], 100 * t_.loc['检验段', '最大回撤']], [t_.loc['全段', '年化百分点'], t_.loc['检验段', '年化百分点']], color='#cbd5e1', lw=1, zorder=1)
ax.grid(alpha=.2); ax.set_xlabel('最大回撤 %（越靠右越浅）', color=MUTED); ax.set_ylabel('年化 %', color=MUTED)
ax.text(.98, .97, f'实心 = 检验段 {EX}\n空心 = 全段 {FULL}，细线连同一条线', transform=ax.transAxes, ha='right', va='top', fontsize=11, color=MUTED)
v = ln[(ln['窗口'] == '检验段') & (ln['线'] == 'v6')].iloc[0]
ax.set_title(f'检验段 v6 年化 {v["年化百分点"]:.1f}%、最大回撤 {100 * v["最大回撤"]:.1f}%'.replace('-', '−'), fontsize=12.5, loc='left', color=INK)
save(fig, 'o5-peers.png')
facts['八条线'] = ln.to_dict('records')

# ---------- 性格：净值与回撤（需要 returns-daily.csv） ----------
if (SRC / 'returns-daily.csv').exists():
    R = pd.read_csv(SRC / 'returns-daily.csv', parse_dates=['date']).set_index('date')
    LINE = {'沪深300全收益': ('#fca5a5', 1.0, '-'), '标普500全收益': ('#93c5fd', 1.0, '-'), 'v6': (BLUE, 2.6, '-'), 'K2A': (INK, 1.5, '-'), '现行配置': (AMBER, 1.3, '-'), 'A1': (TEAL, 1.3, '-'), 'BM-主': (GREY, 1.6, '-'), 'BM-同仓位': (GREY, 1.3, '--')}
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(12, 6.8), sharex=True, gridspec_kw={'height_ratios': [2.4, 1], 'hspace': .08})
    for k, (c, lw, ls) in LINE.items():
        if k not in R:
            continue
        r_ = R[k].loc[man['full_start']:man['full_end']].fillna(0); nav = 100 * (1 + r_).cumprod(); w = nav.resample('W').last().dropna()
        dd = 100 * (w / w.cummax() - 1)
        a1.plot(w.index, w, color=c, lw=lw, ls=ls, label=f'{k} {w.iloc[-1]:.0f} 万')
        a2.plot(dd.index, dd, color=c, lw=lw * .7, ls=ls)
    for ax_ in (a1, a2):
        ax_.axvline(pd.Timestamp(man['exam_start']), color=INK, lw=1)
    a1.legend(loc='upper left', frameon=False, ncol=3, fontsize=10.5); a1.set_ylabel('100 万变成多少万', color=MUTED); a2.set_ylabel('回撤 %', color=MUTED)
    a1.set_ylim(0, None); a1.grid(alpha=.2); a2.grid(alpha=.2)
    a1.set_title(f'{FULL} 一条线走下来；竖线是检验段起点 {man["exam_start"][:7]}', fontsize=12.5, loc='left', color=INK)
    save(fig, 'o6-nav.png')
facts['性格'] = J('character.json')

# ---------- 几次急跌：BM-主 当年最低点之前 250 个交易日里的最高日起，看 250 个交易日 ----------
CRASH_YEARS = [2007, 2011, 2015] if REH else [2015, 2018, 2020, 2022]  # 正式：骨架 0.5 写定；预演：设计期里同法取三次
if (SRC / 'returns-daily.csv').exists():
    R2 = pd.read_csv(SRC / 'returns-daily.csv', parse_dates=['date']).set_index('date').loc[man['full_start']:man['full_end']].fillna(0)
    navs = (1 + R2).cumprod()
    POS = pd.read_csv(SRC / 'positions-monthly.csv', parse_dates=['月']).set_index('月') if (SRC / 'positions-monthly.csv').exists() else None
    fig, axs = plt.subplots(1, len(CRASH_YEARS), figsize=(3.3 * len(CRASH_YEARS), 3.8), sharey=True)
    crash = []
    for ax, yr in zip(axs, CRASH_YEARS):
        tr = navs['BM-主'][str(yr)].idxmin(); j = navs.index.get_loc(tr)  # 当年最低点
        pk = navs['BM-主'].iloc[max(0, j - 250):j + 1].idxmax(); i0 = navs.index.get_loc(pk); win = navs.iloc[i0:i0 + 250]
        rec = {'年': yr, '见顶日': str(pk.date())}
        for k, (c, lw) in {'BM-主': (GREY, 1.4), 'BM-同仓位': ('#94a3b8', 1.1), 'K2A': (INK, 1.1), 'v6': (BLUE, 2.4)}.items():
            dd = 100 * (win[k] / win[k].iloc[0] - 1)
            ax.plot(range(len(dd)), dd, color=c, lw=lw, label=k); rec[k] = float(dd.min())
        if POS is not None:
            m = POS.loc[pk.to_period('M').to_timestamp():].head(12)['股票仓位']
            rec['最低股票仓位'] = float(m.min())
        ax.axhline(0, color=GREY, lw=.6); ax.set_xticks([0, 125, 250]); ax.set_xticklabels(['见顶', '半年', '一年'])
        ax.set_title(f'{yr}：v6 {mm(rec["v6"])}% 对 BM-主 {mm(rec["BM-主"])}%' + (f'\n最低股票仓位 {100 * rec["最低股票仓位"]:.0f}%' if '最低股票仓位' in rec else ''), fontsize=11, loc='left', color=INK)
        ax.grid(alpha=.2); crash.append(rec)
    axs[0].set_ylabel('从见顶日算的跌幅 %', color=MUTED); axs[-1].legend(frameon=False, fontsize=9, loc='lower left')
    save(fig, 'o6b-crash.png'); facts['急跌'] = crash

# ---------- 任意起点 ----------
AS = J('anystart.json'); facts['任意起点'] = AS
fig, ax = plt.subplots(figsize=(11, 3.6))
refs3 = ['BM-主', 'BM-同仓位', 'K2A']
for i, y in enumerate(['1', '3', '5']):
    if y not in AS or not AS[y]['起点数']:
        continue
    for j, ref in enumerate(refs3):
        v = 100 * AS[y]['跑赢占比'][ref]; yy = -(i * 4 + j)
        ax.barh(yy, v, color=TEAL if v >= 50 else AMBER, height=.7)
        ax.text(v + 1, yy, f'{v:.0f}%', va='center', fontsize=10, color=INK)
        ax.text(-1, yy, f'持有 {y} 年 · 对 {ref}' if j == 0 else f'对 {ref}', ha='right', va='center', fontsize=10.5)
ax.axvline(50, color=GREY, ls='--', lw=1); ax.set_xlim(0, 110); ax.set_yticks([]); ax.spines['left'].set_visible(False)
ax.set_xlabel('任意一天买进，持有期满时跑赢对照的起点占比 %', color=MUTED)
ax.set_title('什么时候买进来会输：跑赢占比（绿 ≥ 50%，橙 < 50%）', fontsize=12.5, loc='left', color=INK)
save(fig, 'o7b-anystart.png')

# ---------- 四种行情 ----------
rg = [x for x in J('regimes.json') if x.get('窗口', '全段') == '全段']
fig, ax = plt.subplots(figsize=(11.5, 4.4))
names = ['牛市', '回调', '熊市', '反弹']; refs = ['BM-主', 'BM-同仓位', 'K2A']; cc = [GREY, '#94a3b8', INK]
for j, ref in enumerate(refs):
    for i, n in enumerate(names):
        r = next((x for x in rg if x['对照'] == ref and x['行情'] == n), None)
        if r:
            ax.bar(i + (j - 1) * .26, r['合计'], .24, color=cc[j], label=ref if i == 0 else None)
            ax.text(i + (j - 1) * .26, r['合计'] + (3 if r['合计'] >= 0 else -3), f"{r['合计']:+.0f}".replace('-', '−'), ha='center', va='bottom' if r['合计'] >= 0 else 'top', fontsize=9)
ax.axhline(0, color=GREY, lw=.8); ax.set_xticks(range(4)); ax.set_xticklabels([f'{n}' for n in names]); ax.legend(frameon=False, loc='lower right', ncol=3); ax.margins(y=.15)
ax.set_ylabel('每月差相加（点）', color=MUTED)
ax.set_title('四种行情里 v6 对三个对照每月多或少的合计', fontsize=12.5, loc='left', color=INK)
save(fig, 'o7-regime.png')
facts['行情'] = rg

# ---------- 预测对账 ----------
fc = C('forecast.csv')
RANGE = {'美股挑选': (.3, 1.5, 1.0, 3.41), 'A股挑选': (-.5, .5, .1, 1.48), 'A股等权倾斜': (-1.0, 1.0, .5, 2.28), '防守保费': (-1.6, -.4, -.4, -.79), '美股60%仓位差': (-3.0, 3.0, 0.0, -2.83)}
fig, ax = plt.subplots(figsize=(11, 4.2))
for i, (_, r) in enumerate(fc.iterrows()):
    lo, hi, mid, d = RANGE[r['项']]; y = -i; x = float(r['组合贡献'])
    ax.plot([lo, hi], [y, y], color='#dbe3ee', lw=9, solid_capstyle='round'); ax.plot([mid, mid], [y - .22, y + .22], color=INK, lw=1.4)
    ax.scatter(d, y, s=40, color=GREY, zorder=3)
    inr = lo <= x <= hi
    ax.scatter(x, y, s=90, color=TEAL if inr else (BLUE if x > hi else RED), zorder=4)
    ax.text(5.2, y, mm(x) + ('　范围内' if inr else ('　高于范围' if x > hi else '　低于范围')), va='center', fontsize=10.5, color=TEAL if inr else (BLUE if x > hi else RED))
    ax.text(-3.4, y, r['项'], ha='right', va='center', fontsize=11.5)
ax.set_yticks([]); ax.set_xlim(-3.3, 7.5); ax.axvline(0, color=GREY, lw=.6); ax.spines['left'].set_visible(False)
ax.set_title('预测对账（检验段）：彩点 = 检验段，灰点 = 设计期，横条 = 事先范围', fontsize=12.5, loc='left', color=INK)
save(fig, 'o8-forecast.png')
facts['预测'] = fc.to_dict('records')

# ---------- 结论句（三版预写，只选不改） ----------
v6ex = ln[(ln['窗口'] == '检验段') & (ln['线'] == 'v6')].iloc[0]
X, Z = v6ex['年化百分点'], 100 * v6ex['最大回撤']
Y = facts['判据']['对同仓位基准']['值']
miss = [lab for k, lab, _ in GATES if not facts['判据'][k]['过']]
if facts['总结论'] == '通过':
    s = f'一次性检验通过：四条判据都过；每年 {X:.1f}%，比同仓位基准多 {Y:.1f} 点，回撤 {Z:.1f}%'
elif facts['总结论'] == '通过（有条件）':
    parts = []
    for r in rob:
        if r['item'] in flips:
            bad = [k for k in cols if not r['判据'][k]]
            parts.append(f"{NAMES[r['item']]}在{'、'.join(bad)}翻转")
    s = '通过（有条件）：四条都过；' + '；'.join(parts)
else:
    s = f'一次性检验不通过：判据 {"、".join(miss)} 没过；每年 {X:.1f}%，比同仓位基准{"多" if Y >= 0 else "少"} {abs(Y):.1f} 点'
facts['结论句'] = s.replace('-', '−')
json.dump(facts, open(FACTS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
print(facts['结论句'])
