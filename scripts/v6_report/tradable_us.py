"""v6 一次性检验 · 可交易池（只报告，D52-3）：美股名额换成 A 股场内真能买到的 QDII，按冻结稿 §2 执行层重放。

做法（冻结稿 §2、附表 A，看过检验结果后补做，不改判定）：
- 信号：每月最后一个交易日，美股 15 个候选按 12−1（T−1 月末 ÷ T−12 月末 − 1，人民币）排名，同行业标签去重；
  母指数 SPX 跌破 10 个月均线时只取 12−1 为正的；选前 3，各占名额 1/3（检验段美股股票仓位一直是 100%）。
- 成交：信号日的下一个交易日收盘价。
- 载体：只用附表 A 的场内基金，上市当日起可买；同一候选有几只时选溢价偏离最小的；
  偏离 = 信号日溢价 − 之前 60 个交易日溢价中位数，超过 5 个点不买；已持有的那只照旧持有。
  候选一只都买不了就递补下一名（去重照旧），再不够就给母指数 SPX 的基金。
- 收益：基金后复权收盘价（含分红）；溢价 = 收盘价 ÷ 当日或最近一日单位净值 − 1。
- 成本：单边 0.2%，按换手计。指数版用同一套时点和成本重放，两者之差只来自载体。
用法：python -I scripts/v6_report/tradable_us.py <market.sqlite> <results/v6/oneshot> <输出目录>
"""
import sys, json, sqlite3, pathlib
import numpy as np, pandas as pd

DB, RES, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
START, END, EX0 = '2014-06-01', '2026-09-30', '2016-01-01'
CANDS = ['SPX', 'NDX', 'DJIA', 'SOX', 'NBI', 'XLK', 'XLV', 'XLE', 'XLY', 'XLP', 'XLF', 'XLI', 'XLB', 'XLU', 'DWRTF']
TAG = {'SOX': '信息技术', 'XLK': '信息技术', 'NBI': '医疗保健', 'XLV': '医疗保健', 'XLE': '能源', 'XLY': '可选消费',
       'DWRTF': '房地产', 'XLP': '必需消费', 'XLF': '金融', 'XLI': '工业', 'XLB': '材料', 'XLU': '公用事业'}
CARRIER = {'SPX': ['513500', '161125', '159612'], 'NDX': ['513100', '159941', '513300'], 'DJIA': ['513400'],
           'SOX': ['501225'], 'NBI': ['513290'], 'XLY': ['159529'], 'DWRTF': ['160140'],
           'XLK': ['161128'], 'XLV': ['161126'], 'XLE': ['163208']}
COST, CAP = 0.002, 5.0
con = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
q = lambda sql, p: pd.read_sql_query(sql, con, params=p)

# 日历：A 股交易日（用 513100 所在交易所的交易日，和 513500 取并集）
cal = pd.DatetimeIndex(sorted(set(q("select date from bars where code in ('513100','513500','510300') and adj='raw' and date between ? and ?", (START, END))['date'])))
cal = pd.to_datetime(cal)
fx = q("select date, close from v4_series where code='USDCNY' and kind='fx' and close>0 and date<=? order by date", (END,))
fx = pd.Series(fx['close'].values, pd.to_datetime(fx['date']))
fx = fx[~fx.index.duplicated(keep='last')]
lv = {}
for c in CANDS:
    f = q("select date, close from bars where code=? and adj='raw' and close>0 and date<=? order by date", (c, END))
    s = pd.Series(f['close'].astype(float).values, pd.to_datetime(f['date']))
    s = s[~s.index.duplicated(keep='last')]
    s = s * fx.reindex(s.index.union(fx.index)).ffill().reindex(s.index)
    lv[c] = s.reindex(cal.union(s.index)).ffill().reindex(cal)
L = pd.DataFrame(lv)
fund_ret, prem, nav_ret = {}, {}, {}
for c, fs in CARRIER.items():
    for f in fs:
        h = q("select date, close from bars where code=? and adj='hfq' and close>0 and date<=? order by date", (f, END))
        r = q("select date, close from bars where code=? and adj='raw' and close>0 and date<=? order by date", (f, END))
        n = q("select date, unit_nav from fund_nav where code=? and unit_nav>0 and date<=? order by date", (f, END))
        hs = pd.Series(h['close'].values, pd.to_datetime(h['date'])); hs = hs[~hs.index.duplicated(keep='last')]
        rs = pd.Series(r['close'].values, pd.to_datetime(r['date'])); rs = rs[~rs.index.duplicated(keep='last')]
        ns = pd.Series(n['unit_nav'].values, pd.to_datetime(n['date'])); ns = ns[~ns.index.duplicated(keep='last')]
        fund_ret[f] = hs.reindex(cal).ffill().pct_change().where(hs.reindex(cal).notna().cumsum() > 1)
        p = 100 * (rs / ns.reindex(rs.index.union(ns.index)).ffill().reindex(rs.index) - 1)
        prem[f] = p.reindex(cal)  # 不交易的日子为空
        a = q("select date, accum_nav from fund_nav where code=? and accum_nav>0 and date<=? order by date", (f, END))
        a_ = pd.Series(a['accum_nav'].values, pd.to_datetime(a['date'])); a_ = a_[~a_.index.duplicated(keep='last')]
        nav_ret[f] = a_.reindex(cal.union(a_.index)).ffill().reindex(cal).pct_change().where(fund_ret[f].notna())
listed = {f: fund_ret[f].first_valid_index() for f in fund_ret}

ends = pd.DatetimeIndex([d for i, d in enumerate(cal) if i == len(cal) - 1 or cal[i + 1].month != d.month])
M = L.loc[ends]
score = M.shift(1) / M.shift(12) - 1
above = M['SPX'] > M['SPX'].rolling(10).mean()
idx_ret = L.pct_change()


def deviation(f, day):
    p = prem[f].loc[:day].dropna()
    if len(p) < 2 or p.index[-1] < day - pd.Timedelta(days=10):
        return np.nan
    base = p.iloc[-61:-1]
    return float(p.iloc[-1] - base.median()) if len(base) >= 20 else float(p.iloc[-1] - p.iloc[:-1].median())


def ranked(day):
    s = score.loc[day].dropna()
    if not above.loc[day]:
        s = s[s > 0]
    return list(s.sort_values(ascending=False).index)


def picks_index(day):
    out, used = [], set()
    for c in ranked(day):
        if TAG.get(c) and TAG[c] in used:
            continue
        out.append(c); used.add(TAG.get(c))
        if len(out) == 3:
            break
    while len(out) < 3:
        out.append('SPX')
    return out


def picks_tradable(day, held):
    """返回 [(候选, 基金, 说明)]。held: {候选: 基金}。"""
    out, used, notes = [], set(), []
    for c in ranked(day):
        if len(out) == 3:
            break
        if TAG.get(c) and TAG[c] in used:
            continue
        fs = [f for f in CARRIER.get(c, []) if listed[f] is not None and listed[f] <= day]
        if not fs:
            notes.append((c, '没有场内基金' if c not in CARRIER else '基金还没上市'))
            continue
        if c in held and held[c] in fs:
            out.append((c, held[c])); used.add(TAG.get(c)); continue
        dv = [(deviation(f, day), f) for f in fs]
        ok = [x for x in dv if np.isfinite(x[0]) and x[0] <= CAP]
        if not ok:
            notes.append((c, f'溢价偏离 {max(x[0] for x in dv if np.isfinite(x[0])):.1f} 点' if any(np.isfinite(x[0]) for x in dv) else '溢价算不出'))
            continue
        out.append((c, min(ok)[1])); used.add(TAG.get(c))
    while len(out) < 3:  # 母指数
        fs = [f for f in CARRIER['SPX'] if listed[f] is not None and listed[f] <= day]
        dv = sorted((deviation(f, day), f) for f in fs if np.isfinite(deviation(f, day)))
        f = held.get('SPX') if held.get('SPX') in fs else (dv[0][1] if dv else fs[0])
        out.append(('SPX', f)); notes.append(('递补', '给母指数 SPX'))
    return out, notes


SRC = lambda kind: fund_ret if kind == 'tradable' else (nav_ret if kind == 'nav' else idx_ret)


def replay(kind):
    w, ret, log, held = {}, pd.Series(0.0, index=cal), [], {}
    pending = None
    sig = set(ends)
    for i, d in enumerate(cal):
        if pending is not None:  # 信号日后的第一个交易日收盘成交：当天收益用旧仓位，收盘后换仓
            pass
        r = 0.0
        for k, x in w.items():
            v = SRC(kind)[k].loc[d]
            r += x * (0.0 if not np.isfinite(v) else v)
        g = 1 + r
        w = {k: x * (1 + (lambda v: 0.0 if not np.isfinite(v) else v)(SRC(kind)[k].loc[d])) / g for k, x in w.items()}
        fee = 0.0
        if pending is not None:
            tgt = pending; pending = None
            keys = set(tgt) | set(w)
            fee = COST * sum(abs(tgt.get(k, 0) - w.get(k, 0)) for k in keys)
            w = dict(tgt)
        ret.loc[d] = (1 + r) * (1 - fee) - 1
        if d in sig and d >= pd.Timestamp('2015-06-30') and d <= pd.Timestamp('2026-08-31'):
            if kind in ('tradable', 'nav'):
                pk, notes = picks_tradable(d, held)
                held = {c: f for c, f in pk}
                tgt = {}
                for c, f in pk:
                    tgt[f] = tgt.get(f, 0) + 1 / 3
                log.append({'月': str(d.date()), '持有': [f'{c}:{f}' for c, f in pk], '指数版': picks_index(d), '跳过': [f'{c}（{why}）' for c, why in notes]})
            else:
                pk = picks_index(d)
                tgt = {}
                for c in pk:
                    tgt[c] = tgt.get(c, 0) + 1 / 3
            pending = tgt
    return ret, log


ri, _ = replay('index')
rt, log = replay('tradable')
rn, _ = replay('nav')

# ---------- 校对：指数版前 3 对上官方 positions-monthly 的美股持有 ----------
P = pd.read_csv(RES / 'supplement/positions-monthly.csv', encoding='utf-8-sig')
P['月'] = pd.to_datetime(P.iloc[:, 0])
U = P[(P['名额'] == '美股') & (P['月'] >= '2015-12-01') & (P['月'] <= '2026-08-31')]
match = 0
for _, r in U.iterrows():
    off = sorted(x for x in [r.get(f'持有{i}') for i in range(1, 7)] if isinstance(x, str))
    mine = sorted(set(picks_index(r['月'])))
    match += off == mine
n_months = len(U)

# ---------- 汇总 ----------
cagr = lambda s: 100 * ((1 + s).prod() ** (252 / len(s)) - 1)
mdd = lambda s: 100 * float(((1 + s).cumprod() / (1 + s).cumprod().cummax() - 1).min())
ex = slice(EX0, END)
R = pd.read_csv(RES / 'returns-daily.csv', parse_dates=['date']).set_index('date').loc[EX0:END].fillna(0)
d_us = (rt - ri).reindex(R.index).fillna(0)
v6t = R['v6'] + 0.6 * d_us  # 近似：组合 60% 在美股名额，按日把载体差加回去
v6n = R['v6'] + 0.6 * (rn - ri).reindex(R.index).fillna(0)  # 只换载体、不算溢价变化
k2a_ratio = cagr(R['K2A']) / abs(mdd(R['K2A']))
row = lambda s: {'年化': round(cagr(s), 2), '最大回撤': round(mdd(s), 2)}
summary = {
    '说明': '只报告，不改判定（冻结稿 §5.1：指数池主判，可交易池只报告；D52-3）。看过检验结果后补做。',
    '校对': {'指数版前 3 与官方持有一致的月数': int(match), '月数': int(n_months)},
    '美股名额（检验段）': {'指数版重放': row(ri.loc[ex]), '可交易版': row(rt.loc[ex]), '每年差（点）': round(cagr(rt.loc[ex]) - cagr(ri.loc[ex]), 2),
                          '拆开': {'换成能买到的（按基金净值算）': round(cagr(rn.loc[ex]) - cagr(ri.loc[ex]), 2), '溢价变化（场内价 − 净值）': round(cagr(rt.loc[ex]) - cagr(rn.loc[ex]), 2)}, '净值版': row(rn.loc[ex])},
    '组合（近似）': {
        'v6 官方': row(R['v6']), 'v6 可交易（近似）': row(v6t), 'v6 净值版（近似）': row(v6n),
        '③ 年化÷回撤': {'官方': round(cagr(R['v6']) / abs(mdd(R['v6'])), 3), '可交易（近似）': round(cagr(v6t) / abs(mdd(v6t)), 3), '净值版（近似）': round(cagr(v6n) / abs(mdd(v6n)), 3), 'K2A': round(k2a_ratio, 3)},
        '④ 对同仓位基准（点）': {'官方': round(cagr(R['v6']) - cagr(R['BM-同仓位']), 2), '可交易（近似）': round(cagr(v6t) - cagr(R['BM-同仓位']), 2), '净值版（近似）': round(cagr(v6n) - cagr(R['BM-同仓位']), 2)},
    },
}
# 每个候选：指数版持有月数 vs 实际买到的月数，买的是哪只
cnt = {}
for e in log:
    if e['月'] < '2015-12-01':
        continue
    for c in set(e['指数版']):
        cnt.setdefault(c, {'指数版月数': 0, '买到的月数': 0, '基金': {}})['指数版月数'] += 1
    for h in sorted(set(e['持有'])):
        c, f = h.split(':')
        cnt.setdefault(c, {'指数版月数': 0, '买到的月数': 0, '基金': {}})
        cnt[c]['买到的月数'] += 1
        cnt[c]['基金'][f] = cnt[c]['基金'].get(f, 0) + 1
summary['候选'] = dict(sorted(cnt.items(), key=lambda x: -x[1]['指数版月数']))
why = {}
for e in log:
    if e['月'] < '2015-12-01':
        continue
    for s in e['跳过']:
        c = s.split('（')[0]; k = s.split('（')[1].rstrip('）')
        k = '溢价偏离超 5 点' if k.startswith('溢价偏离') else k
        why.setdefault(c, {}).setdefault(k, 0); why[c][k] += 1
summary['被跳过的原因（月数）'] = why
yr = pd.DataFrame({'指数版': ri.loc[ex], '净值版': rn.loc[ex], '可交易版': rt.loc[ex]})
summary['逐年（美股名额，%）'] = {str(y): {k: round(100 * ((1 + g[k]).prod() - 1), 1) for k in g} for y, g in yr.groupby(yr.index.year)}
# AI 高弹两只：溢价
for f in ['501225', '513100', '159941', '513300']:
    p = prem[f].loc[EX0:END].dropna()
    summary.setdefault('溢价（检验段）', {})[f] = {'中位': round(float(p.median()), 2), '最高': round(float(p.max()), 2), '最高日': str(p.idxmax().date()), '2026-09-30': round(float(p.iloc[-1]), 2)}
json.dump(summary, open(OUT / 'tradable-us.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
pd.DataFrame(log).to_csv(OUT / 'tradable-us-monthly.csv', index=False, encoding='utf-8')
pd.DataFrame({'date': R.index, '美股指数版': ri.reindex(R.index).values, '美股可交易版': rt.reindex(R.index).values, 'v6': R['v6'].values, 'v6可交易近似': v6t.values, 'v6净值版近似': v6n.values}).to_csv(OUT / 'tradable-us-daily.csv', index=False)
print(json.dumps({k: summary[k] for k in ['校对', '美股名额（检验段）', '组合（近似）']}, ensure_ascii=False, indent=1))
