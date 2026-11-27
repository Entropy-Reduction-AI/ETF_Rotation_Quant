"""事后假设（只报告，不进任何判定）：把库里所有能在 A 股场内交易的 ETF、LOF 放进一个池子，按 v6 的选法每月轮动，看检验段 10 年。

Owner 2026-11-27 要求：“所有可交易的 ETF、LOF 都放进来，原油、商品、黄金……看检验段 10 年真实可交易的情况。”
这是看过检验结果之后提出的假设，池子是 2026 年的眼光挑的（已经退市的基金不在库里，有幸存者偏差），结果只能当参考。

规则（尽量沿用 v6，Orchestrator 定，写在这里）：
- 池子：库里有复权价的全部 6 位代码场内基金（A 股 ETF 用项目统一的后复权序列 v4_series/backward，其余用 bars/hfq）；去掉货币基金。
- 参选：上市当天起就能参选（D36：新基金上市当天就能打分）。打分用跟踪指数的人民币走势还原：
  某天指数有数就用指数当天的涨跌，没有就用基金自己的涨跌，接成一条线；库里没有跟踪指数的基金只能用自己的价格，要上市满 12 个月。
  指数对应关系：A 股基金按 data/universe.csv（执行基金与替代基金 → 研究指数，优先全收益），场内 QDII、LOF 按 config/v4/universe.toml 的 maps_to。
- 排名：12−1（T−1 月末 ÷ T−12 月末 − 1），用上面这条打分线。
- 去重：和已选中的基金过去 250 个交易日日收益相关系数超过 0.95，视为同一指数，跳过。
- 选前 N（N = 6，和 v6 两个名额合计持有数相同；另报 N = 3），等权；不设防守。
- 溢价：库里有净值的基金（QDII、LOF），信号日溢价比之前 60 个交易日中位数高 5 点以上不买，已持有的照旧（冻结稿 §2）。
- 成交：信号日下一个交易日收盘；成本单边 0.2%。
用法：python -I scripts/v6_report/tradable_all.py <market.sqlite> <results/v6/oneshot> <输出目录>
"""
import sys, json, sqlite3, pathlib, csv, re
import numpy as np, pandas as pd

DB, RES, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT.mkdir(parents=True, exist_ok=True)
START, END, EX0 = '2013-01-01', '2026-09-30', '2016-01-01'
COST, CAP, CORR = 0.002, 5.0, 0.95
con = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
q = lambda sql, p=(): pd.read_sql_query(sql, con, params=p)

# ---------- 名字和类别 ----------
names = {r.code: r.name for r in q("select code, name from v4_listing").itertuples()}
with open(ROOT / 'data/universe.csv', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        if r['execution_fund_code']:
            names.setdefault(r['execution_fund_code'], r['execution_fund_name'])
        for alt in (r['execution_alternatives'] or '').split(';'):
            if alt.strip():
                names.setdefault(alt.strip(), f"{r['theme']}（同类）")
for f in (ROOT / 'config').rglob('*.toml'):
    t = f.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'code\s*=\s*"(\d{6})"[^\[]{0,400}?name\s*=\s*"([^"]+)"', t, re.S):
        names.setdefault(m.group(1), m.group(2))
    for m in re.finditer(r'name\s*=\s*"([^"]+)"[^\[]{0,400}?code\s*=\s*"(\d{6})"', t, re.S):
        names.setdefault(m.group(2), m.group(1))
EXTRA = {'518880': '华安黄金ETF', '518800': '国泰黄金ETF', '159934': '易方达黄金ETF', '159985': '华夏饲料豆粕期货ETF',
         '511010': '国泰上证5年期国债ETF', '511260': '国泰上证10年期国债ETF', '511020': '平安中债5-10年国开债ETF', '511360': '海富通中证短融ETF',
         '159919': '嘉实沪深300ETF', '159922': '嘉实中证500ETF', '510330': '华夏沪深300ETF', '512500': '华夏中证500ETF'}
for k, v in EXTRA.items():
    names.setdefault(k, v)


def kind(code, name):
    n = name or ''
    if re.search('货币|短融|现金|添益|日利', n) or code.startswith(('5118', '5119', '5116')):
        return '货币'
    if re.search('黄金|贵金属', n):
        return '黄金'
    if re.search('原油|石油|油气|天然气|能源股票', n):
        return '原油油气'
    if re.search('商品|豆粕|有色.*期货|抗通胀', n):
        return '商品'
    if re.search('国债|国开|债', n):
        return '债券'
    if re.search('纳指|纳斯达克|标普|道琼斯|美国|半导体芯片|海外科技|MSCI美国', n):
        return '美股'
    if re.search('恒生|港股|香港|中概|中国互联网|H股|国企|恒指', n):
        return '港股与中概'
    if re.search('日经|日本|东证|德国|法国|印度|沙特|东南亚|巴西|新兴亚洲|中韩', n):
        return '其他海外'
    return 'A股'


# ---------- 价格 ----------
cal = pd.to_datetime(q("select date from bars where code='510300' and adj='raw' and date between ? and ? order by date", (START, END))['date'])
cal = pd.DatetimeIndex(cal)
bw = set(q("select distinct code from v4_series where kind='backward'")['code'])
hf = set(q("select distinct code from bars where adj='hfq'")['code'])
codes = sorted(c for c in (bw | hf) if re.fullmatch(r'\d{6}', c))
px, prem, meta = {}, {}, {}
for c in codes:
    if c in bw:
        f = q("select date, close from v4_series where code=? and kind='backward' and close>0 and date<=? order by date", (c, END))
    else:
        f = q("select date, close from bars where code=? and adj='hfq' and close>0 and date<=? order by date", (c, END))
    s = pd.Series(f['close'].astype(float).values, pd.to_datetime(f['date']))
    s = s[~s.index.duplicated(keep='last')]
    if len(s) < 260:
        continue
    k = kind(c, names.get(c, ''))
    if k == '货币':
        continue
    px[c] = s.reindex(cal.union(s.index)).ffill().reindex(cal).where(cal >= s.index[0])
    meta[c] = {'名字': names.get(c, c), '类别': k, '上市': str(s.index[0].date())}
    n = q("select date, unit_nav from fund_nav where code=? and unit_nav>0 and date<=? order by date", (c, END))
    if len(n) > 100:
        r = q("select date, close from bars where code=? and adj='raw' and close>0 and date<=? order by date", (c, END))
        rs = pd.Series(r['close'].values, pd.to_datetime(r['date'])); rs = rs[~rs.index.duplicated(keep='last')]
        ns = pd.Series(n['unit_nav'].values, pd.to_datetime(n['date'])); ns = ns[~ns.index.duplicated(keep='last')]
        prem[c] = (100 * (rs / ns.reindex(rs.index.union(ns.index)).ffill().reindex(rs.index) - 1)).reindex(cal)
P = pd.DataFrame(px)
RET = P.pct_change(fill_method=None)

# ---------- 跟踪指数：给每只基金一条打分线（D36：上市当天就能打分） ----------
import tomllib
FXC = {}
for cur in ['USD', 'HKD', 'JPY', 'EUR']:
    f = q("select date, close from bars where code=? and adj='raw' and close>0 order by date", (cur + 'CNY',))
    x = pd.Series(f['close'].values, pd.to_datetime(f['date'])); FXC[cur] = x[~x.index.duplicated(keep='last')]
MAP = {'csi300': ('H00300', 'CNY'), 'csi500': ('H00905', 'CNY'), 'hsi': ('HSI', 'HKD'), 'hstech': ('HSTECH', 'HKD'),
       'ndx100': ('NDX', 'USD'), 'spx': ('SPX', 'USD'), 'gold': ('Au99.99', 'CNY'), 'crude-oil': ('BRENT', 'USD'),
       'theme-PHLX Semiconductor Sector Index': ('SOX', 'USD'), 'theme-纳斯达克科技市值加权指数': ('NDXTMC', 'USD'),
       'theme-东京日经225指数': ('N225', 'JPY'), 'theme-纳斯达克生物科技指数': ('NBI', 'USD'), 'theme-道琼斯工业平均指数': ('DJIA', 'USD'),
       'theme-道琼斯美国精选REIT指数': ('DWRTF', 'USD'), 'theme-标普500信息科技指数': ('S5INFT', 'USD'),
       'theme-中证韩交所中韩半导体指数': ('931790', 'CNY'), 'theme-中证海外中国互联网指数': ('H11136', 'CNY'),
       'theme-中证海外中国互联网50人民币指数': ('H30533', 'CNY'), 'theme-中证全球中国教育主题人民币指数': ('931456', 'CNY'),
       'theme-法国CAC40指数': ('FCHI', 'EUR'), 'theme-H11146': ('H11146', 'CNY'), 'theme-H50069': ('H50069', 'CNY'),
       'theme-HSFML25': ('HSFML25', 'HKD'), 'theme-HSSCT': ('HSSCT', 'HKD'), 'theme-SPAHLVCP': ('SPAHLVCP', 'USD')}
fund_index = {}
cfg = tomllib.load(open(ROOT / 'config/v4/universe.toml', 'rb'))
for row in cfg.get('container', []):
    if isinstance(row, dict) and row.get('code') in P.columns and row.get('maps_to') in MAP:
        fund_index[row['code']] = MAP[row['maps_to']]
have = set(q("select distinct code from bars where adj='raw'")['code'])
with open(ROOT / 'data/universe.csv', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        cands = [x.strip().split(' ')[0] for x in (r['tr_code_candidates'] or '').split(';')] + [r['research_index_code']]
        idx = next((x for x in cands if x and x in have), None)
        if r['theme'] == '黄金':
            idx = 'Au99.99'
        for code in [r['execution_fund_code']] + [x.strip() for x in (r['execution_alternatives'] or '').split(';')]:
            if idx and code in P.columns and code not in fund_index:
                fund_index[code] = (idx, 'CNY')
for code in ['518880', '518800', '159934']:
    if code in P.columns:
        fund_index[code] = ('Au99.99', 'CNY')
ilv = {}
for code, (ix, cur) in fund_index.items():
    if (ix, cur) not in ilv:
        f = q("select date, close from bars where code=? and adj='raw' and close>0 and date<=? order by date", (ix, END))
        x = pd.Series(f['close'].astype(float).values, pd.to_datetime(f['date'])); x = x[~x.index.duplicated(keep='last')]
        if cur != 'CNY':
            x = x * FXC[cur].reindex(x.index.union(FXC[cur].index)).ffill().reindex(x.index)
        ilv[(ix, cur)] = x.reindex(cal.union(x.index)).ffill().reindex(cal).where(lambda v: v.index >= x.index[0]).where(lambda v: v.index <= x.index[-1])
SRET = RET.copy()
for code, key in fund_index.items():
    ir = ilv[key].pct_change(fill_method=None)
    SRET[code] = ir.where(ir.notna(), RET[code])  # 指数有数用指数，没有用基金
SL = (1 + SRET.fillna(0)).cumprod().where(SRET.notna().cumsum() > 0)
listed = {c: P[c].first_valid_index() for c in P.columns}
for c in P.columns:
    meta[c]['打分用'] = f'{fund_index[c][0]}（{fund_index[c][1]}）' if c in fund_index else '基金自己的价格'

ends = pd.DatetimeIndex([d for i, d in enumerate(cal) if i == len(cal) - 1 or cal[i + 1].month != d.month])
M = SL.loc[ends]
SC = M.shift(1) / M.shift(12) - 1
SC = SC.where(pd.DataFrame({c: ends >= listed[c] for c in P.columns}, index=ends))  # 基金上市了才能买


def deviation(c, day):
    if c not in prem:
        return 0.0
    p = prem[c].loc[:day].dropna()
    if len(p) < 21 or p.index[-1] < day - pd.Timedelta(days=10):
        return 0.0
    return float(p.iloc[-1] - p.iloc[-61:-1].median())


def choose(day, n, held):
    s = SC.loc[day].dropna().sort_values(ascending=False)
    i = cal.get_loc(day)
    win = SRET.iloc[max(0, i - 249):i + 1]
    out, skipped = [], []
    for c in s.index:
        if len(out) == n:
            break
        if any(win[c].corr(win[o]) > CORR for o in out):
            continue
        if c not in held and deviation(c, day) > CAP:
            skipped.append(c); continue
        out.append(c)
    return out, skipped


def replay(n):
    w, ret, log, held = {}, pd.Series(0.0, index=cal), [], set()
    pending = None
    sig = set(ends[(ends >= '2015-11-30') & (ends <= '2026-08-31')])
    for d in cal:
        rr = RET.loc[d]
        r = sum(x * (0.0 if not np.isfinite(rr[k]) else rr[k]) for k, x in w.items())
        g = 1 + r
        w = {k: x * (1 + (0.0 if not np.isfinite(rr[k]) else rr[k])) / g for k, x in w.items()}
        fee = 0.0
        if pending is not None:
            fee = COST * sum(abs(pending.get(k, 0) - w.get(k, 0)) for k in set(pending) | set(w))
            w, pending = dict(pending), None
        ret.loc[d] = (1 + r) * (1 - fee) - 1
        if d in sig:
            pk, sk = choose(d, n, held)
            held = set(pk)
            pending = {c: 1 / len(pk) for c in pk} if pk else {}
            log.append({'月': str(d.date()), '持有': pk, '溢价跳过': sk, '可参选': int(SC.loc[d].notna().sum())})
    return ret, log


def equal_all():
    w, ret, pending = {}, pd.Series(0.0, index=cal), None
    sig = set(ends[(ends >= '2015-11-30') & (ends <= '2026-08-31')])
    for d in cal:
        rr = RET.loc[d]
        r = sum(x * (0.0 if not np.isfinite(rr[k]) else rr[k]) for k, x in w.items())
        g = 1 + r
        w = {k: x * (1 + (0.0 if not np.isfinite(rr[k]) else rr[k])) / g for k, x in w.items()}
        fee = 0.0
        if pending is not None:
            fee = COST * sum(abs(pending.get(k, 0) - w.get(k, 0)) for k in set(pending) | set(w))
            w, pending = dict(pending), None
        ret.loc[d] = (1 + r) * (1 - fee) - 1
        if d in sig:
            el = list(SC.loc[d].dropna().index)
            pending = {c: 1 / len(el) for c in el}
    return ret


r6, log6 = replay(6)
r3, log3 = replay(3)
rew = equal_all()
cagr = lambda s: 100 * ((1 + s).prod() ** (252 / len(s)) - 1)
mdd = lambda s: 100 * float(((1 + s).cumprod() / (1 + s).cumprod().cummax() - 1).min())
R = pd.read_csv(RES / 'returns-daily.csv', parse_dates=['date']).set_index('date').loc[EX0:END].fillna(0)
lines = {'全部可交易，前 6': r6, '全部可交易，前 3': r3, '全部可交易，等权全拿': rew}
for k in ['v6', 'BM-同仓位', 'BM-主', 'K2A']:
    lines[k] = R[k]
for k, c in [('标普500全收益', '标普500全收益'), ('沪深300全收益', '沪深300全收益')]:
    if c in R:
        lines[k] = R[c]
D = pd.DataFrame({k: v.reindex(R.index).fillna(0) for k, v in lines.items()})
summ_index = {'有跟踪指数的基金': len(fund_index), '只能用自己价格的基金': len(P.columns) - len(fund_index)}
summ = {'打分': summ_index, '说明': '事后假设，只报告，不进任何判定；池子按 2026 年库里有的基金，已退市的不在，有幸存者偏差。',
        '池子': {'基金数': len(P.columns), '按类别': pd.Series([m['类别'] for m in meta.values()]).value_counts().to_dict(),
               '2016-01 可参选': int(SC.loc[ends[ends >= '2015-12-31'][0]].notna().sum()), '2026-08 可参选': int(SC.loc[ends[ends <= '2026-08-31'][-1]].notna().sum())},
        '检验段': {k: {'年化': round(cagr(D[k]), 2), '最大回撤': round(mdd(D[k]), 2), '100 万变成': round(100 * float((1 + D[k]).prod()), 0)} for k in D}}
for n, lg in [(6, log6), (3, log3)]:
    cnt, catm = {}, {}
    for e in lg[1:]:
        for c in e['持有']:
            cnt[c] = cnt.get(c, 0) + 1
            k = meta[c]['类别']; catm[k] = catm.get(k, 0) + 1 / len(e['持有'])
    months = len(lg) - 1
    summ[f'前 {n} 持有'] = {'最常拿的': [{'代码': c, '名字': meta[c]['名字'], '类别': meta[c]['类别'], '月数': m} for c, m in sorted(cnt.items(), key=lambda x: -x[1])[:15]],
                          '各类平均仓位%': {k: round(100 * v / months, 1) for k, v in sorted(catm.items(), key=lambda x: -x[1])},
                          '溢价挡下的次数': sum(len(e['溢价跳过']) for e in lg[1:])}
summ['逐年%'] = {str(y): {k: round(100 * ((1 + g[k]).prod() - 1), 1) for k in ['全部可交易，前 6', '全部可交易，前 3', 'v6', 'BM-同仓位']} for y, g in D.groupby(D.index.year)}
json.dump(summ, open(OUT / 'tradable-all.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(meta, open(OUT / 'tradable-all-pool.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
pd.DataFrame([{'月': e['月'], '持有': '；'.join(f"{c} {meta[c]['名字']}" for c in e['持有']), '溢价跳过': '；'.join(e['溢价跳过']), '可参选': e['可参选']} for e in log6]).to_csv(OUT / 'tradable-all-top6-monthly.csv', index=False, encoding='utf-8')
D.reset_index().to_csv(OUT / 'tradable-all-daily.csv', index=False)
print(json.dumps({k: summ[k] for k in ['池子', '检验段']}, ensure_ascii=False, indent=1))
