"""D38 第 55 行：A 股名额“把同一段涨幅拆开看”——C1 连续性版（Da、Gurun、Warachka 2014 的信息离散度）、C2 隔夜版。
用法：python -I scripts/preflight/a_decompose.py <49_Industry_Portfolios.csv> <DTB3.csv> step1|step2
step1 只算“改不改决定、像不像低波动”，不读下月收益；step2 跑登记的判据、随机对照与描述性秩相关。
"""
import sys, json, math, sqlite3, pathlib, warnings
warnings.filterwarnings('ignore')
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parents[1]
FFP, DTBP, STEP = sys.argv[1], sys.argv[2], sys.argv[3]
import numpy as np, pandas as pd

G = {'__file__': str(HERE / 'a_reactive.py'), '__name__': 'x'}; sys.argv = ['x', FFP, DTBP]
exec(open(HERE / 'a_reactive.py').read().split('def run(')[0], G)
A_OLD, A, bond, TAGS = G['A_OLD'], G['A'], G['bond'], G['TAGS']
COST = 0.002; N = 3; MINDAYS = 200

# ---------- 开盘价与成交额（各自序列的开盘 ÷ 自己的前收） ----------
con = sqlite3.connect(ROOT / 'data/market.sqlite')
ro = pd.read_csv(ROOT / 'results/v51-diag/d37/s1-splice-roster.csv')
code_of = {r['container_id']: str(r['index_code']) for _, r in ro.iterrows() if r['class'] == 'A股' and isinstance(r['index_code'], str)}
code_of['chinext'] = '399006'
L1AMT = dict(zip(['allshare-energy', 'allshare-materials', 'allshare-industrials', 'allshare-discretionary', 'allshare-staples', 'allshare-healthcare',
                  'allshare-financials-re', 'allshare-it', 'allshare-communication', 'allshare-utilities'], [f'H0098{i}' for i in range(6, 10)] + [f'H0099{i}' for i in range(6)]))
def bars(code):
    d = pd.read_sql_query("select date, open, close, amount from bars where code=? and adj='raw' and close>0 and date<='2015-12-31' order by date", con, params=(code,))
    d = d.drop_duplicates('date', keep='last'); d.index = pd.to_datetime(d['date']); return d
ON, AMT = {}, {}
for c in set(A.columns) | set(A_OLD.columns):
    code = L1AMT.get(c) or code_of.get(c)
    if not code: continue
    d = bars(code)
    if d.empty: continue
    if d['open'].notna().sum() > 0 and (d['open'] > 0).sum() > 100:
        o = np.log(d['open'] / d['close'].shift(1)).where(d['open'] > 0)
        ON[c] = o.replace([np.inf, -np.inf], np.nan)
    if (d['amount'] > 0).sum() > 100: AMT[c] = d['amount'].astype(float).where(d['amount'] > 0)

def prep(L):
    """L：日点位。返回月末位置、12−1、窗口内的 ID、隔夜和、过去 12 个月日波动，以及描述用的收益成分。"""
    cal = L.index; mm = np.r_[cal.month[1:] != cal.month[:-1], True]; me_idx = np.where(mm)[0]
    r = L.pct_change(); lr = np.log(L).diff()
    rows = {}
    for k in range(12, len(me_idx)):
        a, b = me_idx[k - 12] + 1, me_idx[k - 1] + 1          # 窗口：12 个月前月末之后 → 上月末（含）
        d = cal[me_idx[k]]; R = r.iloc[a:b]; LR = lr.iloc[a:b]; dts = cal[a:b]
        mom = L.iloc[me_idx[k - 1]] / L.iloc[me_idx[k - 12]] - 1
        nval = R.notna().sum()
        pos, neg = (R > 0).sum() / nval.replace(0, np.nan), (R < 0).sum() / nval.replace(0, np.nan)
        ID = np.sign(mom) * (neg - pos)
        vol = R.std()
        on = pd.Series({c: (ON[c].reindex(dts).sum(min_count=MINDAYS) if c in ON else np.nan) for c in L.columns})
        sd = LR.std(); jump = LR.abs().gt(2 * sd)
        comp = {'总 12−1': LR.sum(min_count=MINDAYS), '跳涨日': LR.where(jump).sum(), '非跳涨日': LR.where(~jump).sum()}
        comp['隔夜'] = on; comp['盘中'] = comp['总 12−1'] - on
        am = pd.DataFrame({c: AMT[c].reindex(dts) for c in L.columns if c in AMT}).reindex(columns=L.columns)
        quiet = am.lt(am.median()); okam = am.notna().sum() >= MINDAYS
        comp['缩量日'] = LR.where(quiet).sum().where(okam); comp['放量日'] = LR.where(~quiet & am.notna()).sum().where(okam)
        rows[d] = dict(mom=mom.where(nval >= MINDAYS), ID=ID.where(nval >= MINDAYS), on=on, vol=vol.where(nval >= MINDAYS), comp=comp)
    return cal, me_idx, rows

def pick(rule, row, elig):
    m = row['mom'].where(elig).dropna()
    if len(m) < 5: return None
    if rule == 'B0': return list(m.nlargest(N).index)
    if rule == 'C1':
        top = m.nlargest(math.ceil(len(m) / 2)).index
        x = pd.DataFrame({'id': row['ID'][top], 'm': m[top]}).dropna()
        return list(x.sort_values(['id', 'm'], ascending=[True, False]).index[:N]) if len(x) >= N else None
    if rule == 'C2':
        o = row['on'].where(elig).dropna()
        return list(o.nlargest(N).index) if len(o) >= N else None

def elig_of(row, need_on):
    e = row['mom'].notna()
    return e & row['on'].notna() if need_on else e

def step1(L, a, b, rules, need_on):
    cal, me_idx, rows = prep(L); out = {}
    for rule in rules:
        diff, rho, n = [], [], 0
        for d, row in rows.items():
            if not (pd.Timestamp(a) <= d <= pd.Timestamp(b) + pd.offsets.MonthEnd(0)): continue
            el = elig_of(row, need_on); p0, p1 = pick('B0', row, el), pick(rule, row, el)
            if p0 is None or p1 is None: continue
            n += 1; diff.append(len(set(p1) - set(p0)))
            sig = (-row['ID'] if rule == 'C1' else row['on']).where(el)
            if rule == 'C1': sig = sig.where(row['mom'].rank(ascending=False) <= math.ceil(el.sum() / 2))   # C1 只在前一半里排
            x = pd.DataFrame({'s': sig, 'v': -row['vol']}).dropna()
            if len(x) >= 4: rho.append(x['s'].rank().corr(x['v'].rank()))
        out[rule] = {'月数': n, '每月与 B0 前 3 不同的个数（平均）': round(float(np.mean(diff)), 2) if diff else None,
                     '至少有 1 个不同的月份比例': round(float(np.mean([x > 0 for x in diff])), 2) if diff else None,
                     '与“波动由低到高”的秩相关（逐月平均）': round(float(np.nanmean(rho)), 2) if rho else None,
                     '第一步是否通过': bool(diff and np.mean(diff) >= 0.5 and (not rho or np.nanmean(rho) <= 0.8))}
    return out

# ---------- 池子 ----------
L1 = A_OLD[['csi300'] + [c for c in A_OLD.columns if c.startswith('allshare-')]]
SUB = [c for c in A.columns if c in ON]                      # 官方池中有开盘价的候选
P2s = A[SUB]
def cnt(L, need_on):
    _, _, rows = prep(L); return {str(d.year): int(elig_of(r, need_on).sum()) for d, r in rows.items() if d.month == 12}

if STEP == 'step1':
    res = {'说明': '第一步：不读下月收益。平均每月与 B0 前 3 不同少于 0.5 个、或与低波动排名秩相关超过 0.8 的选法停止',
           'P1 沪深300 + 10 个一级行业 2006-01 → 2015-11': step1(L1, '2006-01', '2015-11', ['C1'], False),
           'P2 官方池 2011-08 → 2015-11': step1(A, '2011-08', '2015-11', ['C1'], False),
           'P2 子池（官方池中有开盘价的候选）2011-08 → 2015-11': step1(P2s, '2011-08', '2015-11', ['C1', 'C2'], True),
           '子池每年末可参选个数（C2 口径）': cnt(P2s, True), '子池成员': SUB}
    json.dump(res, open(ROOT / 'results/v6-preflight/a-decompose-step1.json', 'w'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str)); sys.exit()

# ======================= 第二步 =======================
def run(L, a, b, rules, need_on, c300):
    cal, me_idx, rows = prep(L); L = L.loc[:b]; cal = L.index
    r = L.pct_change().fillna(0.0).values; br = bond.reindex(cal).fillna(0.0).values; cols = list(L.columns); K = len(cols)
    grp = {}
    for j, c in enumerate(cols): grp.setdefault(TAGS.get(c, '') or f'_{c}', []).append(j)
    pos_of = {cal[i]: i for i in range(len(cal))}
    dec = {}
    for d, row in rows.items():
        if d > pd.Timestamp(b): continue
        el = elig_of(row, need_on)
        dec[pos_of[d]] = (row, el)
    out = {}
    for rule in rules + ['EW']:
        w = np.zeros(K); wb = 1.0; nav = np.zeros(len(cal)); cost = np.zeros(len(cal)); pend = None; picks = {}
        for t in range(len(cal)):
            if pend is not None:
                tgt, tb = pend; tr = np.abs(tgt - w).sum() + abs(tb - wb); cost[t] = COST * tr; w, wb = tgt.copy(), tb; pend = None
            g = (w * r[t]).sum() + wb * br[t]; nav[t] = (1 + g) * (1 - cost[t]) - 1
            Gx = 1 + g; w = w * (1 + r[t]) / Gx; wb = wb * (1 + br[t]) / Gx
            if t in dec:
                row, el = dec[t]
                if el.sum() < 5: pend = (np.zeros(K), 1.0); continue
                if rule == 'EW':
                    tgt = np.zeros(K); gs = [[j for j in js if el.iloc[j]] for js in grp.values()]; gs = [x for x in gs if x]
                    for x in gs:
                        for j in x: tgt[j] = 1 / len(gs) / len(x)
                else:
                    p = pick(rule, row, el)
                    if p is None: pend = (np.zeros(K), 1.0); continue
                    tgt = np.zeros(K); tgt[[cols.index(c) for c in p]] = 1 / N; picks[cal[t]] = p
                pend = (tgt, 1 - tgt.sum())
        out[rule] = dict(r=pd.Series(nav, cal), cost=pd.Series(cost, cal), picks=picks)
    out['_c300'] = c300.reindex(cal).pct_change().fillna(0.0)
    return out, rows

def mon(x): return (1 + x).groupby([x.index.year, x.index.month]).prod() - 1
def tt(x): x = pd.Series(x).dropna(); return round(float(x.mean() / x.std(ddof=1) * math.sqrt(len(x))), 2) if len(x) > 2 else None
Phi = lambda z: 0.5 * (1 + math.erf(z / math.sqrt(2)))

def report(O, rows, L, a, b, rules, phases, need_on):
    keys = rules + ['EW']
    M = {k: mon(O[k]['r'].loc[a:b]) for k in keys}; c3 = mon(O['_c300'].loc[a:b])
    idx = pd.Index([pd.Timestamp(y, m, 1) for y, m in M['EW'].index]); M = {k: pd.Series(v.values, idx) for k, v in M.items()}; c3 = pd.Series(c3.values, idx)
    yrs = len(idx) / 12; res = {}
    for k in keys:
        dx = M[k] - M['EW']; ir = float(dx.mean() / dx.std(ddof=1) * math.sqrt(12)) if k != 'EW' else None
        res[k] = {'对沪深300 每年点': round(float((M[k] - c3).mean()) * 1200, 1), '对等权全部 每年点': round(float(dx.mean()) * 1200, 1),
                  '对等权 t': tt(dx) if k != 'EW' else None, '每年成本点': round(float(O[k]['cost'].loc[a:b].sum()) / yrs * 100, 2)}
        if k != 'EW':
            res[k]['对等权 信息比率'] = round(ir, 2); res[k]['5 年跑赢等权的概率 Φ(IR×√5)'] = round(Phi(ir * math.sqrt(5)), 2)
        if k not in ('EW', 'B0'):
            res[k]['对 B0 每年点'] = round(float((M[k] - M['B0']).mean()) * 1200, 1); res[k]['对 B0 t'] = tt(M[k] - M['B0'])
    res['分阶段（每年点）'] = {}
    for ph, (pa, pb) in phases.items():
        s = slice(pd.Timestamp(pa + '-01'), pd.Timestamp(pb + '-01')); e = {'月数': int(len(M['EW'].loc[s])), 'B0 对等权': round(float((M['B0'] - M['EW']).loc[s].mean()) * 1200, 1)}
        for k in rules:
            if k != 'B0': e[f'{k} − B0'] = round(float((M[k] - M['B0']).loc[s].mean()) * 1200, 1)
        res['分阶段（每年点）'][ph] = e
    for k in rules:
        if k != 'B0': res[f'{k} 好于 B0 的阶段数'] = f"{sum(v[f'{k} − B0'] > 0 for v in res['分阶段（每年点）'].values())} / {len(phases)}"
    # 随机对照（月度、不扣成本，同一可参选集合）
    me = L.loc[:b][np.r_[L.loc[:b].index.month[1:] != L.loc[:b].index.month[:-1], True]]; nxt = me.pct_change().shift(-1)
    rng = np.random.default_rng(20261122); R = []; G_ = {k: [] for k in rules}
    for d, row in rows.items():
        if not (pd.Timestamp(a) <= d <= pd.Timestamp(b) + pd.offsets.MonthEnd(0)) or d not in nxt.index: continue
        el = elig_of(row, need_on); nr = nxt.loc[d]; cand = [c for c in el[el].index if np.isfinite(nr.get(c, np.nan))]
        if len(cand) < 5: continue
        ps = {k: pick(k, row, el) for k in rules}
        if any(p is None for p in ps.values()): continue
        v = nr[cand].values; draws = np.array([v[rng.choice(len(v), N, replace=False)].mean() for _ in range(1000)]); R.append(draws)
        for k in rules: G_[k].append(float(nr[ps[k]].mean()))
    R = np.array(R); med = np.median(R, axis=1); rand_means = R.mean(axis=0)
    res['随机对照（月度、不扣成本）'] = {'月数': int(len(R))}
    for k in rules:
        gk = np.array(G_[k])
        res['随机对照（月度、不扣成本）'][k] = {'规则月均%': round(float(gk.mean()) * 100, 2), '随机月均%（中位）': round(float(np.median(rand_means)) * 100, 2),
                                         '在 1000 条随机路径中的百分位': round(float((rand_means < gk.mean()).mean()) * 100, 1),
                                         '跑赢当月随机中位数的月份比例': round(float((gk > med).mean()), 2)}
    # 描述：各收益成分与下月收益的逐月秩相关
    ic = {}
    for d, row in rows.items():
        if not (pd.Timestamp(a) <= d <= pd.Timestamp(b) + pd.offsets.MonthEnd(0)) or d not in nxt.index: continue
        el = elig_of(row, need_on); nr = nxt.loc[d]
        for name, s in row['comp'].items():
            x = pd.DataFrame({'s': s.where(el), 'n': nr}).dropna()
            if len(x) >= 5: ic.setdefault(name, []).append(x['s'].rank().corr(x['n'].rank()))
    res['描述：成分与下月收益的逐月秩相关（平均 / t / 月数）'] = {k: [round(float(np.nanmean(v)), 3), tt(v), len(v)] for k, v in ic.items()}
    return res

P1PH = {'2006-01 → 2007-10 大牛': ('2006-01', '2007-10'), '2007-11 → 2008-10 崩盘': ('2007-11', '2008-10'), '2008-11 → 2009-07 反弹': ('2008-11', '2009-07'),
        '2009-08 → 2014-06 结构与震荡': ('2009-08', '2014-06'), '2014-07 → 2015-11 大牛与崩盘': ('2014-07', '2015-11')}
P2PH = {'2011-08 → 2013-12': ('2011-08', '2013-12'), '2014-01 → 2015-11': ('2014-01', '2015-11')}
c300 = A_OLD['csi300']
O1, r1 = run(L1, '2006-01', '2015-12-31', ['B0', 'C1'], False, c300)
O2, r2 = run(A, '2011-08', '2015-12-31', ['B0', 'C1'], False, c300)
O3, r3 = run(P2s, '2011-08', '2015-12-31', ['B0', 'C1', 'C2'], True, c300)
res = {'说明': '第 55 行第二步；只看挑选层、不加防守、单边 0.2%、不去重；EW = 按行业标签等权全部可参选候选；C2 仅初步',
       'P1 沪深300 + 10 个一级行业 2006-01 → 2015-11': report(O1, r1, L1, '2006-01', '2015-11', ['B0', 'C1'], P1PH, False),
       'P2 官方池 2011-08 → 2015-11': report(O2, r2, A, '2011-08', '2015-11', ['B0', 'C1'], P2PH, False),
       'P2 子池（有开盘价）2011-08 → 2015-11（初步）': report(O3, r3, P2s, '2011-08', '2015-11', ['B0', 'C1', 'C2'], P2PH, True)}
p1, p2 = res['P1 沪深300 + 10 个一级行业 2006-01 → 2015-11'], res['P2 官方池 2011-08 → 2015-11']
ok_phase = int(p1['C1 好于 B0 的阶段数'].split(' / ')[0]) >= 4; ok_t = (p1['C1']['对等权 t'] or 0) >= 1; ok_dir = p1['C1']['对 B0 每年点'] > 0 and p2['C1']['对 B0 每年点'] > 0
res['C1 判据'] = {'P1 五段至少四段好于 B0': ok_phase, 'P1 对等权 t ≥ 1': ok_t, 'P1、P2 对 B0 同为正': ok_dir,
                 '换规则': ok_phase and ok_t and ok_dir, '报钱（P1 对等权 t ≥ 2）': (p1['C1']['对等权 t'] or 0) >= 2}
json.dump(res, open(ROOT / 'results/v6-preflight/a-decompose.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
