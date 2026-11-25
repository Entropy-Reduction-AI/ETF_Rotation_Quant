"""v6 预注册附表 A：候选序列口径与实盘载体清单（只读行情库的日期与行数，不读收益）。
用法：python -I scripts/preflight/v6_appendix_a.py
输出 results/v6-preflight/v6-appendix-a.csv：每个候选的代码、口径、发布日、库内起止、检验段（2016-01 → 2026-09）缺口、实盘载体。
"""
import sqlite3, tomllib, pathlib, json
import pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[2]
con = sqlite3.connect(ROOT / 'data/market.sqlite')
TAGS = tomllib.load(open(ROOT / 'config/v6-preflight/sector-tags.toml', 'rb'))
U3 = {c.get('id'): c for c in tomllib.load(open(ROOT / 'config/v3/universe.toml', 'rb'))['container']}
U4 = tomllib.load(open(ROOT / 'config/v4/universe.toml', 'rb'))['container']
RO = pd.read_csv(ROOT / 'results/v51-diag/d37/s1-splice-roster.csv'); RO = RO.set_index('container_id')
UC = pd.read_csv(ROOT / 'data/universe.csv', dtype=str)

def cover(code):
    d = pd.read_sql_query("select date from bars where code=? and adj='raw' and close>0 order by date", con, params=(code,))
    if d.empty: return None, None, 0, None
    s = pd.to_datetime(d['date']).drop_duplicates(); t = s[(s >= '2016-01-01') & (s <= '2026-09-30')]
    gap = t.diff().dt.days.max() if len(t) > 1 else None
    return s.iloc[0].date().isoformat(), s.iloc[-1].date().isoformat(), int(len(s)), (int(gap) if gap == gap and gap is not None else None)

def funds4(key):
    out = []
    for c in U4:
        if c['market'] == 'CN' and c.get('maps_to') == key:
            out.append((c['code'], c.get('official_launch') or c.get('first_date') or ''))
    return sorted(out, key=lambda x: x[1] or '9999')

# ---------- 美股名额：价格指数或行业 SPDR（美元收盘 × 人民币中间价），与预演同口径 ----------
US = [('SPX', '标普500（母）', 'spx'), ('NDX', '纳指100', 'ndx100'), ('DJIA', '道指', 'theme-道琼斯工业平均指数'),
      ('SOX', '费城半导体', 'theme-PHLX Semiconductor Sector Index'), ('NBI', '纳斯达克生物科技', 'theme-纳斯达克生物科技指数'),
      ('XLK', '科技 SPDR', 'theme-标普500信息科技指数'), ('XLV', '医疗 SPDR', 'theme-标普500医疗保健等权重指数'),
      ('XLE', '能源 SPDR', 'theme-S&P 500 Energy Sector Index(NTR)'), ('XLY', '可选消费 SPDR', 'theme-标普500消费精选指数'),
      ('XLP', '必需消费 SPDR', None), ('XLF', '金融 SPDR', None), ('XLI', '工业 SPDR', None), ('XLB', '材料 SPDR', None), ('XLU', '公用 SPDR', None),
      ('DWRTF', '道琼斯美国精选 REIT', 'theme-道琼斯美国精选REIT指数')]
SAME = {'spx', 'ndx100', 'theme-道琼斯工业平均指数', 'theme-PHLX Semiconductor Sector Index', 'theme-纳斯达克生物科技指数', 'theme-标普500消费精选指数', 'theme-道琼斯美国精选REIT指数'}
rows = []
for code, name, key in US:
    f, l, n, gap = cover(code); fs = funds4(key) if key else []
    rows.append({'名额': '美股', '候选': code, '名称': name, '行业标签': TAGS['us'].get(code, ''), '序列代码': code,
                 '口径': '价格（美元，按人民币中间价换算）', '发布日': '早于 2005', '库内起': f, '库内止': l, '行数': n, '检验段最长间隔天': gap,
                 '实盘载体': '；'.join(f'{a}（{b}）' for a, b in fs[:3]) if fs else '无场内基金',
                 '载体与候选': ('同一指数' if key in SAME else '相近指数，非同一指数') if fs else '—'})

# ---------- A 股名额 ----------
A_IDS = ['csi300', 'csi500', 'csi1000', 'chinext', 'star50', 'csi-dividend', 'theme-上证红利', 'theme-中证红利低波动'] + \
        [c for c in RO.index if c.startswith('allshare-')] + \
        ['theme-沪深300医药卫生', 'theme-中证主要消费', 'theme-中证农业', 'theme-中证酒', 'theme-中证创新药产业',
         'theme-中证半导体材料设备主题', 'theme-中证全指半导体产品与设备', 'theme-中证全指软件', 'theme-中证全指通信设备', 'theme-中证人工智能主题', 'theme-中证消费电子主题',
         'theme-中证有色金属', 'theme-中证煤炭', 'theme-中证钢铁', 'theme-中证细分化工产业主题',
         'theme-中证银行', 'theme-中证全指证券公司', 'theme-中证全指房地产',
         'theme-中证军工', 'theme-中证机器人', 'theme-中证新能源汽车', 'theme-中证光伏产业', 'theme-中证全球中国教育主题人民币指数']
for cid in A_IDS:
    r = RO.loc[cid] if cid in RO.index else None
    u = U3.get(cid, {}); res = u.get('research', {})
    code = str(r['index_code']) if r is not None else res.get('series_code', '')
    basis = res.get('return_basis') or ('price' if code[:1].isdigit() else '')
    pub = (r['publish_date'] if r is not None and isinstance(r['publish_date'], str) else res.get('publish_date', '')) or ''
    f, l, n, gap = cover(code)
    ex = [(e['code'], e.get('list_date', '')) for e in u.get('execution', [])]
    if not ex:
        m = UC[UC.research_index_code == code]
        if len(m): ex = [(m.iloc[0].execution_fund_code, '')] + [(x, '') for x in str(m.iloc[0].execution_alternatives).split(';') if x and x != 'nan']
    if not ex: ex = funds4(cid)
    note = []
    if r is not None and r['status'] == 'frozen': note.append('拼接未完成（frozen）：没有第二条来源核对')
    if cid == 'theme-中证半导体材料设备主题': note.append('官网发布日 2012-12-21 早于基日 2018-12-28，发布日存疑')
    if cid.startswith('allshare-'): note.append('第 48 行：2011-08-02 之前允许用回填点位')
    rows.append({'名额': 'A 股', '候选': cid, '名称': (u.get('name') or (r['index_code'] if r is not None else '')), '行业标签': TAGS['a'].get(cid, ''),
                 '序列代码': code, '口径': {'total_return': '全收益', 'price': '价格', 'unit_nav': '基金单位净值'}.get(basis, basis or '价格'),
                 '发布日': pub, '库内起': f, '库内止': l, '行数': n, '检验段最长间隔天': gap,
                 '实盘载体': '；'.join(f'{a}' + (f'（{b}）' if b and b != '取不到' else '') for a, b in ex[:3]) if ex else '无场内基金',
                 '载体与候选': '同一指数' if ex else '—', '备注': '；'.join(note)})
df = pd.DataFrame(rows)
df.to_csv(ROOT / 'results/v6-preflight/v6-appendix-a.csv', index=False)
print(df.drop(columns=['名称']).to_string())
print('库内止早于 2026-09-30：', df.loc[df['库内止'].fillna('') < '2026-09-30', ['候选', '库内止']].to_dict('records'))
print('检验段间隔超过 10 天：', df.loc[df['检验段最长间隔天'].fillna(0) > 10, ['候选', '检验段最长间隔天']].to_dict('records'))
