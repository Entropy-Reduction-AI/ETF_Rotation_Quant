"""v6 体检报告（设计期）的派生分析：净值与回撤、上涨/下跌跟随、四种行情、两次急跌、任意起点。
只做算术：输入是 Dev 与 Reviewer 已对上的日收益（results/v6/health-returns.csv）和沪深300 全收益（H00300，行情库），
全部截到 2015-12-31。输出 JSON 供页面引用，图另由 charts_health.py 画。
用法：python -I scripts/v6_report/health_extra.py <输出 json> [结果目录，默认 results/v6] [行情库，默认 data/market.sqlite]
"""
import sys, json, sqlite3, pathlib
import numpy as np, pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(sys.argv[1])
SRC = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / 'results/v6'
DB = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / 'data/market.sqlite'
END = '2015-12-31'

R = pd.read_csv(SRC / 'health-returns.csv', index_col=0, parse_dates=True).loc[:END]
con = sqlite3.connect(f'file:{DB.resolve()}?mode=ro', uri=True)
h = pd.read_sql_query("select date, close from bars where code='H00300' and adj='raw' and close>0 and date<=? order by date", con, params=(END,))
con.close()
csi = h.drop_duplicates('date', keep='last').set_index(pd.to_datetime(h.drop_duplicates('date', keep='last')['date']))['close']

W = R.loc['2006-01-01':END]
COLS = ['v6', '连续性版', 'K2A', '现行配置', 'A1', 'A2', 'BM-主', 'BM-同仓位']
W = W[COLS].dropna(how='any')
nav = (1 + W).cumprod()
dd = nav / nav.cummax() - 1
out = {'window': [str(W.index[0].date()), str(W.index[-1].date())], 'n_days': int(len(W))}

# 净值与回撤曲线（周末取样，供画图）
wk = nav.resample('W-FRI').last().dropna()
out['nav_weekly'] = {c: [round(float(x), 5) for x in wk[c]] for c in COLS}
out['dd_weekly'] = {c: [round(float(x), 5) for x in (wk[c] / wk[c].cummax() - 1)] for c in COLS}
out['weeks'] = [str(d.date()) for d in wk.index]

# 性格：年化、回撤、波动、上涨/下跌月份跟随（对 BM-主）
M = (1 + W).resample('ME').prod() - 1
up, dn = M['BM-主'] > 0, M['BM-主'] < 0
ann = lambda s: float((1 + s).prod() ** (252 / len(s)) - 1)
char = {}
for c in COLS:
    char[c] = {'年化': ann(W[c]), '最大回撤': float(dd[c].min()), '年化波动': float(W[c].std() * np.sqrt(252)),
               '上涨月份跟到': float(M.loc[up, c].mean() / M.loc[up, 'BM-主'].mean()),
               '下跌月份只跟': float(M.loc[dn, c].mean() / M.loc[dn, 'BM-主'].mean())}
out['character'] = char
out['months'] = {'up': int(up.sum()), 'down': int(dn.sum())}

# 两次急跌：从沪深300 全收益见顶起算 250 个交易日
crash = {}
for tag, (a, b) in {'2008': ('2007-01-01', '2008-12-31'), '2015': ('2015-01-01', '2015-12-31')}.items():
    peak = csi.loc[a:b].idxmax()
    seg = W.loc[peak:].iloc[:251]
    path = (1 + seg).cumprod() / (1 + seg.iloc[0])
    c300 = csi.reindex(seg.index).ffill(); c300 = c300 / c300.iloc[0]
    crash[tag] = {'peak': str(peak.date()), 'days': int(len(seg)),
                  'path': {c: [round(float(x), 5) for x in path[c]] for c in ['v6', 'K2A', 'BM-主', '现行配置']},
                  'csi300': [round(float(x), 5) for x in c300],
                  'low': {**{c: float((path[c].min()) - 1) for c in ['v6', 'K2A', 'BM-主', '现行配置']}, '沪深300': float(c300.min() - 1)},
                  'end': {**{c: float(path[c].iloc[-1] - 1) for c in ['v6', 'K2A', 'BM-主', '现行配置']}, '沪深300': float(c300.iloc[-1] - 1)}}
out['crash'] = crash

# 四种行情：按沪深300 全收益月末划分；超额 = v6 月收益 − 对照月收益，相加（百分点）
cm = csi.resample('ME').last()
r1, r12 = cm.pct_change(), cm.pct_change(12)
reg = pd.Series(np.where(r12 > 0, np.where(r1 > 0, '牛市', '回调'), np.where(r1 < 0, '熊市', '反弹')), index=cm.index)
reg = reg[r12.notna()].reindex(M.index)
regimes = {}
for name in ['牛市', '回调', '熊市', '反弹']:
    mask = reg == name
    row = {'月数': int(mask.sum())}
    for ref in ['BM-主', 'BM-同仓位', 'K2A']:
        ex = (M.loc[mask, 'v6'] - M.loc[mask, ref]) * 100
        row[ref] = {'合计': float(ex.sum()), '跑赢月份': float((ex > 0).mean()) if len(ex) else None}
    regimes[name] = row
out['regimes'] = regimes

# 任意起点：每个月第一个交易日买入，持有 1/3/5 年（252/756/1260 个交易日），比较年化
firsts = W.groupby(W.index.to_period('M')).head(1).index
anys = {}
for yrs, n in ((1, 252), (3, 756), (5, 1260)):
    res = {}
    starts = [d for d in firsts if W.index.get_loc(d) + n <= len(W)]
    for ref in ['BM-主', 'BM-同仓位', 'K2A', '现行配置', 'A1']:
        diffs = []
        for d in starts:
            i = W.index.get_loc(d); seg = W.iloc[i:i + n]
            a = (1 + seg['v6']).prod() ** (252 / n) - 1; b = (1 + seg[ref]).prod() ** (252 / n) - 1
            diffs.append((a - b) * 100)
        diffs = np.array(diffs)
        res[ref] = {'起点数': int(len(diffs)), '跑赢占比': float((diffs > 0).mean()), '中位': float(np.median(diffs)), '最差': float(diffs.min()),
                    '逐个': [round(float(x), 3) for x in diffs] if yrs == 3 else None}
    res['起点'] = [str(d.date()) for d in starts] if yrs == 3 else None
    anys[str(yrs)] = res
out['anystart'] = anys
json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
print(json.dumps({k: out[k] for k in ('window', 'months')}, ensure_ascii=False))
for c in COLS:
    print(c, {k: round(v, 3) for k, v in char[c].items()})
for t, v in crash.items():
    print(t, v['peak'], {k: round(x, 3) for k, x in v['low'].items()}, {k: round(x, 3) for k, x in v['end'].items()})
for k, v in regimes.items():
    print(k, v['月数'], {r: (round(v[r]['合计'], 1), round(v[r]['跑赢月份'], 2)) for r in ['BM-主', 'BM-同仓位', 'K2A']})
for y, v in anys.items():
    print(y, {r: (v[r]['起点数'], round(v[r]['跑赢占比'], 2), round(v[r]['中位'], 1), round(v[r]['最差'], 1)) for r in ['BM-主', 'BM-同仓位', 'K2A', '现行配置', 'A1']})
