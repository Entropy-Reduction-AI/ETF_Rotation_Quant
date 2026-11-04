"""复核：设计稿第 3.1 版在 2003 年以前的长历史上（不在任何检验段里）。只看信号层面的仓位，不算收益。计入诊断次数 1。
跑之前写死（2026-11-03，Owner 同意“复核只判过不过，不再调规则；不过就退回等权”）：
数据：标普500（^GSPC）1955-01 → 2003-06-30，现金 = 美国 3 个月国库券 DTB3；恒生（^HSI）1987-01 → 2015-12-31，现金同 DTB3（港元 1983 年起挂钩美元）；
  日经（^N225）1987-01 → 2015-12-31，现金 = 日本银行无担保隔夜拆借利率（1998 年起日次，之前用月平均），补跑，只报告、不进判定（2026-11-04 加）。只有收盘价。
单一市场版本的第 3.1 版：每周最后一个交易日，风险仓位 = 0.5·[转负前沿 < 0.5] + 0.5·[水平 > 0 或 长尺子放缓]，其余拿现金。
两种权重只差这一处：响度加权（第 3.1 版）vs 等权（退路）。另列 12 个月涨幅高于现金就满仓（A1 式）作参照，不参与判定。
熊市 = 收盘从高点回落 ≥ 20%，到低点后反弹 ≥ 20% 结束（机械识别）；牛市 = 其余时间。
判定（汇总全部熊市和牛市）：响度加权“通过”须同时满足 ①牛市平均仓位 ≥ 等权 − 5 个百分点；②熊市平均仓位 ≤ 等权 + 5 个百分点；
  ③见底后回到半仓的天数中位数 ≤ 等权；④见顶后减到半仓的天数中位数 ≤ 等权 + 10 天。任一不满足即不通过，第 3.1 版改用等权。
另描述：牛市最后 6 个月的权重重心 vs 整段牛市（检验“牛市越往后越看短”）。
第三次运行（2026-11-04）：长尺子放缓改为“连续两个月都在放缓”（设计稿 3.1 的 E 修改，Owner 同意），三个市场都跑，只报告。参数 e2m。
用法：python results/v5/diag/design/longhist.py results/v5/diag/design [jp|e2m]
"""
import sys, pathlib, json, bisect
ROOT = pathlib.Path(__file__).resolve().parents[4]
import pandas as pd, numpy as np
out = pathlib.Path(sys.argv[1]); RAW = ROOT / 'data/research/long-history/raw'
G = sorted(set(np.round(np.geomspace(3, 250, 30)).astype(int))); LONG = [n for n in G if n >= 60]
dtb = pd.read_csv(ROOT / 'results/v5/other-market/raw/DTB3.csv', parse_dates=['date'], na_values=['.', '']).set_index('date')['DTB3']
dtb = dtb.where(dtb > -100).dropna()  # 原文件用 -9999 表示缺值
def pct_past(a):
    o = np.full(len(a), np.nan); h = []
    for i, x in enumerate(a):
        if np.isnan(x): continue
        if len(h) >= 250: o[i] = bisect.bisect_left(h, x) / len(h)
        bisect.insort(h, x)
    return o
def jp_rate():
    dd = pd.read_csv(RAW / 'FM01-STRDCLUCON.csv', parse_dates=['date']).set_index('date').iloc[:, 0]
    mm = pd.read_csv(RAW / 'FM02-STRACLUCON.csv'); mm.index = pd.to_datetime(mm.iloc[:, 0].astype(str)); mm = mm.iloc[:, 1]
    mm = mm[mm.index < dd.index[0]]
    return pd.concat([mm, dd]).sort_index().astype(float)
def states(px, cash=None):
    lr = np.log(px).diff().fillna(0)
    rate = (dtb if cash is None else cash).reindex(px.index, method='ffill').ffill() / 100
    gap = px.index.to_series().diff().dt.days.fillna(1).values
    cl = np.log1p(rate.shift(1).fillna(rate) * gap / 360)
    x = lr - cl; sig = lr.rolling(250).std().shift(1)
    V = pd.DataFrame({n: x.rolling(n).sum() / (sig * np.sqrt(n)) for n in G})
    Q = pd.DataFrame({n: pct_past(V[n].abs().rolling(n).mean().values) for n in G}, index=V.index)
    Wl = Q.div(Q.sum(axis=1), axis=0); eq = Q.isna().any(axis=1); Wl.loc[eq] = 1 / len(G)
    F = (V < 0).mean(axis=1).where(V.notna().all(axis=1))
    lm = V[LONG].mean(axis=1, skipna=False); E = (lm > lm.shift(20)) & ((lm.shift(20) > lm.shift(40)) if E2M else True)
    ctr = np.exp((Wl * np.log(G)).sum(axis=1)).where(~eq)
    m12 = (lr.rolling(252).sum() - cl.rolling(252).sum()) > 0
    return dict(loud=(Wl * V).sum(axis=1, min_count=len(G)), eq=V.mean(axis=1, skipna=False), F=F, E=E, ctr=ctr, m12=m12)
def bears(px):
    out, mode, ext, ext_t = [], 'up', px.iloc[0], px.index[0]; peak_t = None
    for t, p in px.items():
        if mode == 'up':
            if p > ext: ext, ext_t = p, t
            elif p <= ext * 0.8: mode, peak_t, peak, ext, ext_t = 'down', ext_t, ext, p, t
        else:
            if p < ext: ext, ext_t = p, t
            elif p >= ext * 1.2: out.append((peak_t, ext_t, round(ext / peak - 1, 3))); mode, ext, ext_t = 'up', p, t
    return out
res, rows = {}, []
JP = len(sys.argv) > 2 and sys.argv[2] == 'jp'; E2M = len(sys.argv) > 2 and sys.argv[2] == 'e2m'
SETS = (('标普500', '^GSPC.csv', '1955-01-01', '2003-06-30'), ('恒生', '^HSI.csv', '1987-01-01', '2015-12-31'), ('日经', '^N225.csv', '1987-01-01', '2015-12-31')) if E2M else (('日经', '^N225.csv', '1987-01-01', '2015-12-31'),) if JP else (('标普500', '^GSPC.csv', '1955-01-01', '2003-06-30'), ('恒生', '^HSI.csv', '1987-01-01', '2015-12-31'))
for name, f, a, b in SETS:
    px = pd.read_csv(RAW / f, parse_dates=['date']).set_index('date')['close'].loc[:b]
    S = states(px, jp_rate() if (JP or name == '日经') else None)
    wk = px.index.to_series().groupby(px.index.to_period('W')).max().values
    wk = pd.DatetimeIndex(wk); wk = wk[(wk >= pd.Timestamp(a)) & S['F'].reindex(wk).notna().values]
    W = {}
    for k in ('loud', 'eq'):
        H = S[k].reindex(wk); w = 0.5 * (S['F'].reindex(wk) < 0.5) + 0.5 * ((H > 0) | S['E'].reindex(wk).astype(bool))
        W[k] = w.reindex(px.index, method='ffill').loc[wk[0]:]
    W['a1'] = S['m12'].reindex(wk).astype(float).reindex(px.index, method='ffill').loc[wk[0]:]
    p = px.loc[wk[0]:]; bs = [x for x in bears(px.loc[:b]) if x[0] >= wk[0]]
    inbear = pd.Series(False, index=p.index)
    for pk, tr, dd in bs: inbear.loc[pk:tr] = True
    for k, w in W.items():
        r = dict(市场=name, 权重=k, 牛市平均仓位=round(float(w[~inbear].mean()) * 100, 1), 熊市平均仓位=round(float(w[inbear].mean()) * 100, 1),
                 每年档位变动=round(float((w.diff().abs() > 0).sum() / (len(w) / 252)), 1))
        dtop, dbot = [], []
        for pk, tr, dd in bs:
            x = w.loc[pk:]; z = x[x <= 0.5].index[:1]; dtop.append((z[0] - pk).days if len(z) else np.nan)
            x = w.loc[tr:]; z = x[x >= 0.5].index[:1]; dbot.append((z[0] - tr).days if len(z) else np.nan)
        r['见顶后减到半仓_天_中位'] = float(np.nanmedian(dtop)); r['见底后回到半仓_天_中位'] = float(np.nanmedian(dbot))
        r['逐次见顶'] = dtop; r['逐次见底'] = dbot; rows.append(r)
    late, whole = [], []
    prev_tr = wk[0]
    for pk, tr, dd in bs:
        seg = S['ctr'].loc[prev_tr:pk].dropna()
        if len(seg) > 250: late.append(float(seg.loc[pk - pd.Timedelta(days=182):].median())); whole.append(float(seg.median()))
        prev_tr = tr
    res[name] = dict(熊市=[(str(x[0].date()), str(x[1].date()), x[2]) for x in bs], 牛市末6个月重心=[round(v) for v in late], 整段牛市重心=[round(v) for v in whole])
d = pd.DataFrame(rows)
agg = {}
for k in ('loud', 'eq', 'a1'):
    x = d[d.权重 == k]
    tops = sum(x.逐次见顶, []); bots = sum(x.逐次见底, [])
    agg[k] = dict(牛市平均仓位=round(float(x.牛市平均仓位.mean()), 1), 熊市平均仓位=round(float(x.熊市平均仓位.mean()), 1),
                  见顶后减到半仓_天_中位=float(np.nanmedian(tops)), 见底后回到半仓_天_中位=float(np.nanmedian(bots)), 每年档位变动=round(float(x.每年档位变动.mean()), 1))
L, Q = agg['loud'], agg['eq']
ok = {'①牛市仓位': L['牛市平均仓位'] >= Q['牛市平均仓位'] - 5, '②熊市仓位': L['熊市平均仓位'] <= Q['熊市平均仓位'] + 5,
      '③见底回场': L['见底后回到半仓_天_中位'] <= Q['见底后回到半仓_天_中位'], '④见顶减仓': L['见顶后减到半仓_天_中位'] <= Q['见顶后减到半仓_天_中位'] + 10}
res['汇总'] = agg; res['判定'] = {k: bool(v) for k, v in ok.items()}; res['结论'] = '通过：保留响度加权' if all(ok.values()) else '不通过：改用等权'
TAG = '-jp' if JP else '-e2m' if E2M else ''
d.drop(columns=['逐次见顶', '逐次见底']).to_csv(out / f'longhist{TAG}.csv', index=False)
(out / f'longhist{TAG}.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
print(d.to_string()); print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
