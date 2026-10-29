"""数据与容器看板的数据生成（2026-10-29，Orchestrator）。

只读 data/market.sqlite、config/v3/universe.toml、config/v4/universe.toml、results/v4/inventory/。
只统计数据的起止、覆盖和状态，不计算任何收益。每次数据轮次结束后重跑：
    python results/v4/diag/data-board/build_data_board.py
输出：results/v4/diag/data-board/out/{summary.json,containers.csv}、docs/assets/data-board/*.png
"""
import csv, json, sqlite3, hashlib, tomllib, collections, pathlib, datetime
ROOT = pathlib.Path(__file__).resolve().parents[4]
OUT = ROOT / 'results/v4/diag/data-board/out'; OUT.mkdir(parents=True, exist_ok=True)
ASSET = ROOT / 'docs/assets/data-board'; ASSET.mkdir(parents=True, exist_ok=True)
DB = ROOT / 'data/market.sqlite'
con = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
CUT = '2026-09-30'

def first_last(code):
    best = None
    for q in ("select min(date),max(date),count(*) from bars where code=? and close>0 and date<=?",
              "select min(date),max(date),count(*) from fund_nav where code=? and unit_nav>0 and date<=?",
              "select min(date),max(date),count(*) from v4_series where code=? and kind in ('backward','otc_nav') and date<=?"):
        r = con.execute(q, (code, CUT)).fetchone()
        if r and r[0] and (best is None or r[0] < best[0]): best = r
    return best or (None, None, 0)

def has_hfq(code):
    a = con.execute("select count(*) from bars where code=? and adj='hfq'", (code,)).fetchone()[0]
    b = con.execute("select count(*) from v4_series where code=? and kind in ('backward','backward_rebuild')", (code,)).fetchone()[0]
    return a + b > 0

def hfq_source(code):
    if con.execute("select 1 from bars where code=? and adj='hfq' limit 1", (code,)).fetchone(): return '东财'
    r = con.execute("select source from v4_series where code=? and kind='backward' limit 1", (code,)).fetchone()
    if r:
        s = r[0]
        return {'eastmoney_fhsp': '东财（无分红拆分）', 'tencent_etf_hfq': '腾讯', 'tencent_etf_hfq_carry': '腾讯', 'yahoo': 'Yahoo', 'eastmoney_etf_hfq': '东财'}.get(s, '还原')
    if con.execute("select 1 from v4_series where code=? and kind='backward_rebuild' limit 1", (code,)).fetchone(): return '还原'
    return '缺'

GROUP = {'A股宽基': 'A 股', 'A股行业': 'A 股', 'A股红利': 'A 股', '港股': '港股', '美股宽基': '美股', '美股和全球主题': '海外主题（QDII、LOF）',
         '商品': '商品、债券、现金', '债券': '商品、债券、现金', '现金': '商品、债券、现金'}
u3 = tomllib.load(open(ROOT / 'config/v3/universe.toml', 'rb'))['container']
u4 = tomllib.load(open(ROOT / 'config/v4/universe.toml', 'rb'))['container']
otc = collections.defaultdict(list)
for r in u4:
    if r.get('instrument_type') == 'otc_fund' and '增强' not in r['name']:
        otc[r.get('maps_to')].append(r)
rows = []
for c in u3:
    if c.get('arm') != 'main': continue
    rs = c['research']; code = rs.get('series_code') or ''
    f, l, n = first_last(code) if code else (None, None, 0)
    mem = []
    for e in c.get('execution', []):
        ld = e.get('list_date') or ''
        fb = con.execute("select min(date) from bars where code=? and close>0", (e['code'],)).fetchone()[0]
        start = ld if ld[:2] in ('19', '20') else fb
        mem.append(dict(code=e['code'], name=e.get('name', ''), start=start, hfq=has_hfq(e['code']), src=hfq_source(e['code'])))
    otcs = [dict(code=o['code'], name=o['name'], start=o.get('first_date') or o.get('official_launch')) for o in otc.get(c['id'], [])]
    starts = [m['start'] for m in mem if m['start']] + [o['start'] for o in otcs if o['start']]
    buy = min(starts) if starts else None
    issues = []
    st = rs.get('series_status')
    if st != 'in_db': issues.append({'取不到': '没有研究序列，用基金自己的价格', 'partial': '研究序列不完整'}.get(st, '研究序列缺'))
    miss = [m['code'] for m in mem if not m['hfq'] and m['start'] and m['start'] <= CUT]
    if miss: issues.append('后复权缺：' + '、'.join(miss))
    rows.append(dict(group=GROUP.get(c['asset_class'], c['asset_class']), id=c['id'], name=c['name'], asset_class=c['asset_class'],
                     research=code, basis=rs.get('return_basis'), research_first=f, research_last=l, research_rows=n,
                     buy_first=buy, members=len(mem), otc=len(otcs), member_codes='、'.join(m['code'] for m in mem),
                     issues='；'.join(issues), pool='v3 起'))
seen = set()
for r in u4:
    if r['id'] in seen or r.get('status') != 'in_db': continue
    if r['id'].startswith('us-') or (r['id'].startswith('hk-') and r.get('return_basis') == 'price'):
        seen.add(r['id'])
        f, l, n = first_last(r['code'])
        if r['id'].startswith('us-'):
            hb = con.execute("select min(date) from v4_series where code=? and kind='backward'", (r['code'],)).fetchone()[0]
        rows.append(dict(group='美股' if r['id'].startswith('us-') else '港股', id=r['id'], name=r['name'], asset_class='美股行业' if r['id'].startswith('us-') else '港股分类',
                         research=r['code'], basis='后复权' if r['id'].startswith('us-') else 'price', research_first=f, research_last=l, research_rows=n,
                         buy_first=(r.get('official_launch') or f) if r['id'].startswith('us-') else None, members=1 if r['id'].startswith('us-') else 0, otc=0,
                         member_codes=r['code'] if r['id'].startswith('us-') else '', issues='', pool='v4 新池（T4）'))
with open(OUT / 'containers.csv', 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

years = list(range(2005, 2027))
groups = ['A 股', '港股', '美股', '海外主题（QDII、LOF）', '商品、债券、现金']
def count(field):
    out = {g: [] for g in groups}
    for y in years:
        end = f'{y}-12-31' if y < 2026 else CUT
        for g in groups:
            out[g].append(sum(1 for r in rows if r['group'] == g and r[field] and r[field] <= end))
    return out
res_cnt, buy_cnt = count('research_first'), count('buy_first')

census = list(csv.DictReader(open(ROOT / 'results/v4/inventory/r1e/census.csv')))
listed = [c for c in census if c.get('list_date', '') <= CUT]
hfq_ok = sum(1 for c in listed if has_hfq(c['code']))
nav_ok = sum(1 for c in listed if con.execute("select count(*) from fund_nav where code=?", (c['code'],)).fetchone()[0] > 0)
src_mix = collections.Counter(hfq_source(c['code']) for c in listed)
integ = collections.Counter((r.get('manager_class') or '未分类') for r in csv.DictReader(open(ROOT / 'results/v4/inventory/integrity-findings.csv')))
sha = hashlib.sha256(DB.read_bytes()).hexdigest()
summary = dict(
    generated=datetime.date.today().isoformat(), db_sha256=sha, cutoff=CUT,
    containers_total=len(rows), containers_v3=sum(r['pool'] == 'v3 起' for r in rows), containers_t4=sum(r['pool'] != 'v3 起' for r in rows),
    by_group={g: sum(r['group'] == g for r in rows) for g in groups},
    research_by_year={g: dict(zip(years, v)) for g, v in res_cnt.items()}, buy_by_year={g: dict(zip(years, v)) for g, v in buy_cnt.items()},
    census_total=len(census), census_listed=len(listed), hfq_ok=hfq_ok, nav_ok=nav_ok, hfq_source=dict(src_mix),
    integrity=dict(integ), bars_rows=con.execute('select count(*) from bars').fetchone()[0],
    series_rows=con.execute('select count(*) from v4_series').fetchone()[0], nav_rows=con.execute('select count(*) from fund_nav').fetchone()[0],
    open_issues=[dict(id=r['id'], name=r['name'], issues=r['issues']) for r in rows if r['issues']],
)
json.dump(summary, open(OUT / 'summary.json', 'w'), ensure_ascii=False, indent=1)

import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.grid': True, 'grid.alpha': .22, 'font.size': 11, 'axes.edgecolor': '#9ca3af'})
COL = {'A 股': '#2563eb', '港股': '#0d9488', '美股': '#7c3aed', '海外主题（QDII、LOF）': '#d97706', '商品、债券、现金': '#9ca3af'}
fig, axs = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True, gridspec_kw=dict(wspace=.08))
for ax, cnt, t in [(axs[0], res_cnt, '研究池：有数据可以排名的容器'), (axs[1], buy_cnt, '当年真能买到的容器（场内、场外、美股原生 ETF）')]:
    base = [0] * len(years)
    for g in groups:
        top = [b + v for b, v in zip(base, cnt[g])]
        ax.fill_between(years, base, top, color=COL[g], alpha=.85, lw=0, step='post', label=g)
        base = top
    ax.axvline(2015.99, color='#111827', lw=1, ls='--'); ax.text(2015.6, max(base) * .98, '设计期 ｜ 检验段', ha='center', fontsize=9.5, color='#111827',
                                                              bbox=dict(fc='white', ec='none', pad=1))
    for y in (2006, 2015, 2026):
        i = years.index(y); ax.text(y + .1, base[i] + 1.5, str(base[i]), fontsize=10, weight='bold', color='#111827')
    ax.set_title(t, loc='left', fontsize=12, weight='bold', color='#111827'); ax.set_xlim(2005, 2026.9); ax.grid(axis='x', visible=False)
    ax.set_xticks([2006, 2010, 2015, 2020, 2026]); ax.set_xticklabels(['2006', '2010', '2015', '2020', '2026'])
axs[0].set_ylabel('容器个数（年末）'); axs[1].legend(frameon=False, fontsize=9.5, loc='upper left')
fig.suptitle('池子随时代长大：设计期里能排名的多，当年真能买到的少', x=.125, ha='left', y=1.06, fontsize=14.5, weight='bold', color='#111827')
fig.text(.125, .975, f'每年年末累计。“能买到”只看有没有上市或成立，未套 3,000 万成交额门槛。数据截至 {CUT}，只统计起止日，不含任何收益。', fontsize=10, color='#6b7280')
fig.savefig(ASSET / 'd1-pool-growth.png', dpi=200, bbox_inches='tight', facecolor='white')
print(json.dumps({k: summary[k] for k in ('containers_total', 'containers_v3', 'containers_t4', 'by_group', 'census_listed', 'hfq_ok', 'nav_ok', 'hfq_source', 'integrity')}, ensure_ascii=False))
