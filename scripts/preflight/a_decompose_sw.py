"""D38 第 56 行：(一) C2 隔夜版在 P1（沪深300 + 10 个全指一级行业）的正式判据，开盘价来自 PR #340 的价格指数 000986–000995；
(二) 申万一级 2021 版（PR #343）参考检验：B0、C1、C2、EW，定义与第 55 行逐字相同（复用 a_decompose.py 的函数）。
用法：python -I scripts/preflight/a_decompose_sw.py <49_Industry_Portfolios.csv> <DTB3.csv> step1|step2
step1 只算“改不改决定、像不像低波动”，不读下月收益；step2 只跑 step1 通过的选法。
"""
import sys, json, math, pathlib, warnings
warnings.filterwarnings('ignore')
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parents[1]
FFP, DTBP, STEP = sys.argv[1], sys.argv[2], sys.argv[3]
import numpy as np, pandas as pd

src = open(HERE / 'a_decompose.py').read()
G = {'__file__': str(HERE / 'a_decompose.py'), '__name__': 'x'}; sys.argv = ['x', FFP, DTBP, 'step1']
exec(src.split('# ---------- 池子 ----------')[0], G)
exec(src[src.index('# ======================= 第二步'):src.index("P1PH = {")].replace('# ======================= 第二步 =======================', ''), G)
A_OLD, A, ON, AMT = G['A_OLD'], G['A'], G['ON'], G['AMT']
step1, run, report, P1PH, P2PH = G['step1'], G['run'], G['report'], None, None
P1PH = {'2006-01 → 2007-10 大牛': ('2006-01', '2007-10'), '2007-11 → 2008-10 崩盘': ('2007-11', '2008-10'), '2008-11 → 2009-07 反弹': ('2008-11', '2009-07'),
        '2009-08 → 2014-06 结构与震荡': ('2009-08', '2014-06'), '2014-07 → 2015-11 大牛与崩盘': ('2014-07', '2015-11')}
P2PH = {'2011-08 → 2013-12': ('2011-08', '2013-12'), '2014-01 → 2015-11': ('2014-01', '2015-11')}
cal = A_OLD.loc[:'2015-12-31'].index

def onof(d, o, c):
    x = np.log(d[o] / d[c].shift(1)).where((d[o] > 0) & (d[c].shift(1) > 0))
    return x.replace([np.inf, -np.inf], np.nan)

# ---------- (一) 全指一级的开盘价：价格指数 000986–000995（PR #340，完整官方载荷，第 48 行允许回填段） ----------
L1IDS = ['allshare-energy', 'allshare-materials', 'allshare-industrials', 'allshare-discretionary', 'allshare-staples', 'allshare-healthcare',
         'allshare-financials-re', 'allshare-it', 'allshare-communication', 'allshare-utilities']
for i, cid in enumerate(L1IDS):
    d = pd.read_csv(ROOT / f'incoming/grok-csi-allshare-l1-20261123/dailies/{986 + i:06d}.index-perf.csv', dtype={'tradeDate': str})
    d.index = pd.to_datetime(d['tradeDate']); d = d.loc[:'2015-12-31']
    ON[cid] = onof(d, 'open', 'close')
    AMT.setdefault(cid, d['tradingValue'].astype(float).where(d['tradingValue'] > 0))
L1 = A_OLD[['csi300'] + L1IDS]
L1s = A_OLD[L1IDS]                                         # 沪深300 2021 年前无开盘价：C2 与 B0、EW 在 10 个一级行业子池里比
P2s = A[[c for c in A.columns if c in ON]]

# ---------- (二) 申万一级 2021 版（PR #343），从官方接口首日起计 ----------
SWD = ROOT / 'incoming/grok-sw-l1-20261123/dailies'
SW = {}
for f in sorted(SWD.glob('*.trend.csv')):
    d = pd.read_csv(f, dtype={'bargaindate': str}); d.index = pd.to_datetime(d['bargaindate'])
    cid = 'sw-' + f.name.split('.')[0]                    # sw-801010-农林牧渔
    if d.index[0] > pd.Timestamp('2015-12-31'): continue
    d = d.loc[:'2015-12-31']
    SW[cid] = d['closeindex'].reindex(cal).ffill().where(lambda s: s.index >= d.index[0])
    ON[cid] = onof(d, 'openindex', 'closeindex')
    AMT[cid] = d['bargainsum'].astype(float).where(d['bargainsum'] > 0)
P3 = pd.concat([A_OLD['csi300'].loc[:'2015-12-31'], pd.DataFrame(SW)], axis=1)
P3s = pd.DataFrame(SW)
c300 = A_OLD['csi300']

def cnt(L, need_on):
    _, _, rows = G['prep'](L); return {str(d.year): int(G['elig_of'](r, need_on).sum()) for d, r in rows.items() if d.month == 12}

S1 = {'P1 子池（10 个一级行业，有开盘价）2006-01 → 2015-11': (L1s, '2006-01', '2015-11', ['C2'], True),
      'P2 子池（官方池中有开盘价的候选）2011-08 → 2015-11': (P2s, '2011-08', '2015-11', ['C2'], True),
      'P3 申万一级 + 沪深300 2006-01 → 2015-11': (P3, '2006-01', '2015-11', ['C1'], False),
      'P3 子池（申万一级，有开盘价）2006-01 → 2015-11': (P3s, '2006-01', '2015-11', ['C1', 'C2'], True)}
if STEP == 'step1':
    res = {'说明': '第 56 行第一步：不读下月收益。平均每月与 B0 前 3 不同少于 0.5 个、或与低波动排名秩相关超过 0.8 的选法停止'}
    for k, (L, a, b, rules, need_on) in S1.items():
        res[k] = step1(L, a, b, rules, need_on)
    res['每年末可参选个数'] = {'P1 子池': cnt(L1s, True), 'P2 子池': cnt(P2s, True), 'P3': cnt(P3, False), 'P3 子池': cnt(P3s, True)}
    res['P2 子池成员'] = list(P2s.columns); res['P3 成员'] = list(P3.columns)
    json.dump(res, open(ROOT / 'results/v6-preflight/a-decompose-sw-step1.json', 'w'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str)); sys.exit()

# ======================= 第二步（只跑第一步通过的选法） =======================
s1 = json.load(open(ROOT / 'results/v6-preflight/a-decompose-sw-step1.json'))
def passed(k, rule): return bool(s1[k][rule]['第一步是否通过'])
res = {'说明': '第 56 行第二步；只看挑选层、不加防守、单边 0.2%、不去重；EW = 按行业标签等权全部可参选候选；申万部分只作参考（Owner 2026-11-23 选 A）'}
for k, (L, a, b, rules, need_on) in S1.items():
    keep = ['B0'] + (['C1'] if 'C1' in rules and passed(k, 'C1') else []) + (['C2'] if 'C2' in rules and passed(k, 'C2') else [])
    if keep == ['B0']: res[k] = '第一步未通过，不看收益'; continue
    if 'P3 申万一级 + 沪深300' in k or 'P3 子池' in k: ph = P1PH
    elif k.startswith('P1'): ph = P1PH
    else: ph = P2PH
    O, r = run(L, a, '2015-12-31', keep, need_on, c300)
    res[k] = report(O, r, L, a, b, keep, ph, need_on)
p1, p2 = res[list(S1)[0]], res[list(S1)[1]]
if isinstance(p1, dict) and 'C2' in p1:
    ok_phase = int(p1['C2 好于 B0 的阶段数'].split(' / ')[0]) >= 4; ok_t = (p1['C2']['对等权 t'] or 0) >= 1
    ok_dir = p1['C2']['对 B0 每年点'] > 0 and isinstance(p2, dict) and 'C2' in p2 and p2['C2']['对 B0 每年点'] > 0
    res['(一) C2 正式判据'] = {'P1 子池五段至少四段好于 B0': ok_phase, 'P1 子池对等权 t ≥ 1': ok_t, 'P1 子池、P2 子池对 B0 同为正': ok_dir,
                          '换规则': ok_phase and ok_t and ok_dir, '报钱（P1 子池对等权 t ≥ 2）': (p1['C2']['对等权 t'] or 0) >= 2}
    res['(一) C2 正式判据']['结论'] = '满足判据：报 Owner 决定是否作为第二个挑战者（不自动进 v6）' if res['(一) C2 正式判据']['换规则'] else 'C2 关闭'
else:
    res['(一) C2 正式判据'] = {'结论': 'C2 第一步未通过，关闭'}
json.dump(res, open(ROOT / 'results/v6-preflight/a-decompose-sw.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
