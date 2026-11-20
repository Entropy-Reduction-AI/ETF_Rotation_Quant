"""D38 第 46 行：候选去重（同一行业只留分数最高的一个）。第六轮入库之后运行。
用法：python -I scripts/preflight/topn_dedupe.py <49_Industry_Portfolios.csv> <DTB3.csv>
"""
import sys, json, sqlite3, tomllib, pathlib, warnings
warnings.filterwarnings('ignore')
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parents[1]; sys.path.insert(0, str(ROOT))
FFP, DTBP = sys.argv[1], sys.argv[2]
import numpy as np, pandas as pd
from src.v4.engine.pool import load_mid

G = {'__file__': str(HERE / 'a_official.py'), '__name__': 'x'}; sys.argv = ['x', FFP, DTBP]
exec(open(HERE / 'a_official.py').read().split("res = {'每年末")[0], G)
A, US_RMB, bond, cash, summ, stats, votes, conf, US_PRIOR = G['A'], G['US_RMB'], G['bond'], G['cash'], G['summ'], G['stats'], G['votes'], G['conf'], G['US_PRIOR']
TAGS = tomllib.load(open(ROOT / 'config/v6-preflight/sector-tags.toml', 'rb')); COST = 0.002

# 第六轮入库的美股候选（价格口径，人民币）；SP5NENRS 净总回报，不参选
NEW = ['S5INFT', 'SPSIBI', 'DJSOEP', 'SPSIOP', 'S35', 'DWRTF', 'IXY', 'SPGOGUP']
con = sqlite3.connect(ROOT / 'data/market.sqlite'); usd = load_mid(con, 'USDCNY', '2015-12-31', filled=True); idx = US_RMB.index
def lvl(code):
    d = pd.read_sql_query("select date, close from bars where code=? and adj='raw' and close>0 and date<='2015-12-31' order by date", con, params=(code,))
    s = pd.Series(d['close'].astype(float).values, pd.to_datetime(d['date'])); s = s[~s.index.duplicated(keep='last')]
    s = s * usd.reindex(s.index.union(usd.index)).ffill().reindex(s.index)
    return s.reindex(idx.union(s.index)).ffill().reindex(idx).where(lambda x: x.index >= s.index[0])
US_NEW = US_RMB.copy()
for c in NEW: US_NEW[c] = lvl(c)
assert set(US_NEW.columns) <= set(TAGS['us']) and set(A.columns) <= set(TAGS['a']), '有候选没有登记标签'

def slot(L, parent, N, prior, tags, dedupe):
    cal = L.index; r = L.pct_change().fillna(0).values; K = L.shape[1]; cols = list(L.columns); pi = cols.index(parent)
    tg = np.array([tags.get(c, '') for c in cols], dtype=object)
    mm = np.r_[cal.month[1:] != cal.month[:-1], True]; me = L[mm]; m12 = me.shift(1) / me.shift(12) - 1; above = me > me.rolling(10).mean(); mnx = me.pct_change().shift(-1)
    blvl = np.exp(np.log1p(bond.fillna(0)).cumsum()).where(bond.notna().cumsum() > 0); bme = blvl[mm]; bab = (bme > bme.rolling(10).mean()) & bme.notna()
    V, _ = votes(L, parent, ['均线', '宽度', 'TRIN'])
    def top(sc, ok):
        out, used = [], set()
        for i in np.argsort(-np.where(ok, sc, -np.inf)):
            if not ok[i] or len(out) == N: break
            if dedupe and tg[i] and tg[i] in used: continue
            out.append(i); used.add(tg[i])
        return out
    w = np.zeros(K); wb = 0.0; wc = 1.0; out = np.zeros(len(cal)); turn = 0.0; pend_t = None; br, cr = bond.fillna(0).values, cash.values
    hist = []; pend = None; log = {}
    for t in range(len(cal)):
        if pend_t is not None:
            tgt, tb, tc = pend_t; tr = np.abs(tgt - w).sum() + abs(tb - wb); turn += tr; cst = COST * tr; w, wb, wc = tgt, tb, tc; pend_t = None
        else: cst = 0.0
        g = (w * r[t]).sum() + wb * br[t] + wc * cr[t]; out[t] = (1 + g) * (1 - cst) - 1
        Gx = 1 + g; w = w * (1 + r[t]) / Gx; wb = wb * (1 + br[t]) / Gx; wc = wc * (1 + cr[t]) / Gx
        if mm[t]:
            d = cal[t]
            if pend is not None: hist.append(pend); pend = None
            sc = m12.loc[d].values.astype(float); ok = np.isfinite(sc); tgt = np.zeros(K); p = conf(hist, prior=prior)
            if not ok.any(): tgt[pi] = 1.0; pick = [pi]
            else:
                raw = top(sc, ok)
                if not bool(above.loc[d].values[pi]): ok &= sc > 0
                stress = int(V.get(d.to_period('M'), 0)) >= 2; frac = p if stress else 1.0
                pick = top(sc, ok); tgt[pick] = frac / N
                v = mnx.loc[d].values
                if stress and raw and np.isfinite(v[raw]).all(): pend = float(np.mean(v[raw]))
            sh = pd.Series(tgt, index=tg).groupby(level=0).sum(); sh = sh[sh.index != '']
            log[d] = ([cols[i] for i in pick], float(sh.max() / max(tgt.sum(), 1e-9)) if len(sh) and tgt.sum() > 0 else 0.0)
            left = 1 - tgt.sum(); bok = bool(bab.loc[d]) if d in bab.index else False
            pend_t = (tgt, left if bok else 0.0, 0.0 if bok else left)
    return pd.Series(out, cal), turn, log

res = {'说明': '设计期整套（A 股按发布日校正、美股 60%、前 3、按把握调节，单边 0.2%）；第六轮入库后的行情库'}
LOG = {}
for nm, UL in (('旧 14 个美股候选', US_RMB), ('新 22 个美股候选', US_NEW)):
    for dd in (False, True):
        a, ta, la = slot(A, 'csi300', 3, None, TAGS['a'], dd); u, tu, lu = slot(UL, 'SPX', 3, US_PRIOR, TAGS['us'], dd)
        k = f'{nm}，{"去重" if dd else "不去重"}'; o = summ(0.4 * a + 0.6 * u, ta, tu)
        for lab, lg in (('A 股', la), ('美股', lu)):
            sh = pd.Series({d: v[1] for d, v in lg.items()}).loc['2006':]
            o[f'{lab}名额单一行业最大占比_平均'] = round(float(sh.mean()), 2); o[f'{lab}名额单一行业≥2/3 的月份比例'] = round(float((sh >= 0.66).mean()), 2)
        res[k] = o; LOG[k] = (la, lu)
# 第 47 行（看过第 46 行后登记）：每个行业一个代表 = 旧 14 个 + REIT
US_REP = US_RMB.copy(); US_REP['DWRTF'] = US_NEW['DWRTF']
a, ta, la = slot(A, 'csi300', 3, None, TAGS['a'], True); u, tu, lu = slot(US_REP, 'SPX', 3, US_PRIOR, TAGS['us'], True)
o = summ(0.4 * a + 0.6 * u, ta, tu)
for lab, lg in (('A 股', la), ('美股', lu)):
    sh = pd.Series({d: v[1] for d, v in lg.items()}).loc['2006':]
    o[f'{lab}名额单一行业最大占比_平均'] = round(float(sh.mean()), 2); o[f'{lab}名额单一行业≥2/3 的月份比例'] = round(float((sh >= 0.66).mean()), 2)
res['第 47 行：每个行业一个代表（旧 14 个 + REIT），去重'] = o
# 逐月核对：新 22 个候选，去重前后选的不一样的月份
diff = {}
for lab, j in (('A 股', 0), ('美股', 1)):
    x, y = LOG['新 22 个美股候选，不去重'][j], LOG['新 22 个美股候选，去重'][j]; ch = [d for d in x if d.year >= 2006 and x[d][0] != y[d][0]]
    diff[lab] = {'不一样的月份数': len(ch), '总月数': sum(1 for d in x if d.year >= 2006),
                 '例': {str(d.date()): {'不去重': x[d][0], '去重': y[d][0]} for d in ch[:: max(1, len(ch) // 6)][:6]}}
diff['A 股 2013-04'] = {k: v[0] for k, v in (('不去重', LOG['新 22 个美股候选，不去重'][0][pd.Timestamp('2013-04-26')]), ('去重', LOG['新 22 个美股候选，去重'][0][pd.Timestamp('2013-04-26')]))}
res['逐月核对'] = diff
json.dump(res, open(ROOT / 'results/v6-preflight/topn-dedupe.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
