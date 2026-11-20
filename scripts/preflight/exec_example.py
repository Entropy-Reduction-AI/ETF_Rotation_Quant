"""预测表第 0 节的执行示例：按 D40 规则（前 3、美股 60%）逐步记录某个月末的计算过程（设计期数据，只导出过程，不改规则）。
用法：python scripts/preflight/exec_example.py <49_Industry_Portfolios.csv> <DTB3.csv> 2015-08-31 2013-04-30
"""
import sys, json, pathlib, warnings
warnings.filterwarnings('ignore')
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parents[1]
FFP, DTBP, DATES = sys.argv[1], sys.argv[2], sys.argv[3:]
import numpy as np, pandas as pd
G = {'__file__': str(HERE / 'a_official.py'), '__name__': 'x'}; sys.argv = ['x', FFP, DTBP]
exec(open(HERE / 'a_official.py').read().split("res = {'每年末")[0], G)
A, US_RMB, bond, cash, V, conf, US_PRIOR = G['A'], G['US_RMB'], G['bond'], G['cash'], G['V'], G['conf'], G['US_PRIOR']
votes_detail = V['votes']
def trace(lvl, parent, prior, want):
    cal = lvl.index; me_mask = np.r_[cal.month[1:] != cal.month[:-1], True]; me = lvl[me_mask]
    mom = me.shift(1) / me.shift(12) - 1; above = me > me.rolling(10).mean(); ma = me.rolling(10).mean(); mnx = me.pct_change().shift(-1)
    blvl = np.exp(np.log1p(bond.fillna(0)).cumsum()).where(bond.notna().cumsum() > 0); bme = blvl[me_mask]; babove = (bme > bme.rolling(10).mean()) & bme.notna()
    # 三票分开
    mep = me.copy(); mep.index = mep.index.to_period('M')
    v_ma = (mep[parent] < mep[parent].rolling(10).mean())
    b1 = (mep > mep.rolling(10).mean()).where(mep.rolling(10).count() == 10).mean(axis=1); b1q = b1.expanding(min_periods=24).quantile(1 / 3)
    t = V['TRIN'][parent].reindex(mep.index); tq = t.expanding(min_periods=24).quantile(2 / 3)
    hist = []; pend = None; out = {}
    for d in me.index:
        if pend is not None: hist.append(pend); pend = None
        per = d.to_period('M'); sc = mom.loc[d]; ok = sc.notna()
        vm, vb, vt = bool(v_ma.get(per, False)), bool(b1.get(per, np.nan) <= b1q.get(per, np.nan)) if pd.notna(b1q.get(per, np.nan)) else False, bool(t.get(per, np.nan) >= tq.get(per, np.nan)) if pd.notna(tq.get(per, np.nan)) else False
        nv = int(vm) + int(vb) + int(vt); stress = nv >= 2; p = conf(hist, prior=prior)
        elig = ok.copy()
        if not bool(above.loc[d, parent]): elig &= sc > 0
        raw = sc[ok].nlargest(3).index; pick = sc[elig].nlargest(3).index
        frac = p if stress else 1.0
        if str(d.date()) in want:
            out[str(d.date())] = dict(母指数=parent, 母指数月末点位=round(float(me.loc[d, parent]), 2), 母指数10个月均线=round(float(ma.loc[d, parent]), 2),
                                     母指数在均线上方=bool(above.loc[d, parent]),
                                     票_均线=vm, 宽度=round(float(b1.get(per)), 2) if pd.notna(b1.get(per)) else None, 宽度门槛_历史低三分之一=round(float(b1q.get(per)), 2) if pd.notna(b1q.get(per)) else None, 票_宽度=vb,
                                     TRIN=round(float(t.get(per)), 2) if pd.notna(t.get(per)) else None, TRIN门槛_历史高三分之一=round(float(tq.get(per)), 2) if pd.notna(tq.get(per)) else None, 票_TRIN=vt,
                                     票数=nv, 确认紧张=stress, 已知紧张月数=len(hist) + len(prior or []), **_pstat(list(prior or []) + hist), 把握p=round(p, 2),
                                     候选数=int(ok.sum()), 前6名分数={k: round(float(v) * 100, 1) for k, v in sc[ok].nlargest(6).items()},
                                     入选=list(pick), 每只仓位_占名额=round(frac / 3, 3), 股票仓位_占名额=round(frac * len(pick) / 3, 3),
                                     国债或现金_占名额=round(1 - frac * len(pick) / 3, 3), 国债在均线上方=bool(babove.loc[d]) if d in babove.index else None)
        if stress and len(raw):
            v = mnx.loc[d, raw]
            if v.notna().all(): pend = float(v.mean())
    return out
def _pstat(h):
    """把握 p 的三个输入：以往紧张月领头者下月的平均涨幅、波动（%），以及 t = 平均 ÷ 波动 × √月数。"""
    if len(h) < 2: return {}
    a = np.array(h); sd = a.std(ddof=1)
    return dict(紧张月领头者下月平均涨幅_pct=round(a.mean() * 100, 2), 波动_pct=round(sd * 100, 2), t=round(a.mean() / sd * len(a) ** 0.5, 2))
res = {'A 股名额（40%）': trace(A, 'csi300', None, DATES), '美股名额（60%）': trace(US_RMB, 'SPX', US_PRIOR, DATES)}
json.dump(res, open(ROOT / 'results/v6-preflight/exec-example.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
