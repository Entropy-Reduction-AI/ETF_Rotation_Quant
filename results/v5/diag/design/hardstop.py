"""探索（不计入判据 ⑤）：Owner 2026-11-04 问“会不会自己的前沿还没过半，就先跌了 8% 或 10%”。信号层面，≤2015，不算收益。
用 profile32 第二次运行（定稿 3.2）的每日持仓：每段持有（某只容器连续在持仓里的一段），从买入后的最高收盘算回撤，
记下回撤先到 −8%、−10% 的那天，和它自己 F ≥ 0.5（被替换）的那天，谁先发生；先到的那段，等 F 触发时又多跌了多少。
用法：python results/v5/diag/design/hardstop.py results/v5/diag/design
"""
import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
src = (ROOT / 'results/v5/diag/design/profile32.py').read_text()
src = src.replace("ROOT = pathlib.Path(__file__).resolve().parents[4]", f"ROOT = pathlib.Path('{ROOT}')").split("uni = {k:")[0]
out = pathlib.Path(sys.argv[1]); sys.argv = ['x', str(out)]; exec(src)
import pandas as pd, numpy as np
d = pd.read_csv(out / 'profile32-daily.csv', parse_dates=['t'])
px = {}; spells = []
held = d.set_index('t').picks.fillna('').str.split('|')
names = sorted({c for v in held for c in v if c})
for c in names:
    inn = held.apply(lambda v: c in v); p = np.exp(np.log1p(ret[c].fillna(0)).cumsum()).reindex(inn.index)
    F = state(c).F.reindex(inn.index)
    grp = (inn != inn.shift()).cumsum()
    for _, seg in inn[inn].groupby(grp[inn]):
        t0, t1 = seg.index[0], seg.index[-1]
        nx = inn.index[inn.index > t1][:1]; te = nx[0] if len(nx) else t1   # 离开持仓的那天（当天收盘决定卖）
        pp = p.loc[t0:te]; dd = pp / pp.cummax() - 1
        mk = d.set_index('t')
        why = 'F' if (len(nx) and pd.notna(F.get(te)) and F.get(te) >= 0.5) else ('市场退出' if len(nx) and mk.at[te, 'market'] == '无' else ('周度换掉' if len(nx) else '期末'))
        ft = pd.DatetimeIndex([te]) if why == 'F' else pd.DatetimeIndex([])
        r = dict(id=c, start=t0, end=te, 离开原因=why, days=len(seg), maxdd=float(dd.min()), F触发=ft[0] if len(ft) else None, F触发时回撤=float(dd.loc[ft[0]]) if len(ft) else None)
        for th in (0.08, 0.10):
            z = dd[dd <= -th].index[:1]; r[f'先到{int(th*100)}%'] = bool(len(z) and (not len(ft) or z[0] < ft[0])); r[f'到{int(th*100)}%日'] = z[0] if len(z) else None
        spells.append(r)
S = pd.DataFrame(spells); S.to_csv(out / 'hardstop-spells.csv', index=False)
res = dict(持有段数=len(S), 段内最大回撤中位=round(float(S.maxdd.median()), 3), 被F替换时回撤中位=round(float(S.F触发时回撤.dropna().median()), 3),
           被F替换时回撤最深=round(float(S.F触发时回撤.dropna().min()), 3),
           先跌到8的段=int(S['先到8%'].sum()), 先跌到10的段=int(S['先到10%'].sum()), 段内回撤超过10的段=int((S.maxdd <= -0.10).sum()), 段内回撤超过15的段=int((S.maxdd <= -0.15).sum()))
x = S[S['先到10%']].copy()
x['之后到被换走又多跌'] = [float(np.exp(np.log1p(ret[r.id].fillna(0)).cumsum()).loc[r['到10%日']:r.end].pipe(lambda q: q.min() / q.iloc[0] - 1)) for _, r in x.iterrows()]
res['离开原因'] = S.离开原因.value_counts().to_dict()
res['离开那天的回撤（中位，按原因）'] = S.assign(dl=[(np.exp(np.log1p(ret[r.id].fillna(0)).cumsum()).loc[r.start:r.end].pipe(lambda q: q.iloc[-1] / q.max() - 1)) for _, r in S.iterrows()]).groupby('离开原因').dl.median().round(3).to_dict()
res['先到10%的段：之后到卖出前又多跌（中位）'] = round(float(x['之后到被换走又多跌'].median()), 3) if len(x) else None
res['先到10%的明细'] = x[['id', 'start', '到10%日', 'end', '离开原因', 'maxdd', '之后到被换走又多跌']].astype(str).values.tolist()
(out / 'hardstop.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
