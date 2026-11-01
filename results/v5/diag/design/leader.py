"""诊断：“集中押最强的大市场”在我们的数据里能不能和运气分开。只用 ≤2015-12-31 的中国数据，计入诊断次数 1。
事先写下的判定（跑之前定）：
  算机制：领头市场下个月跑赢三个市场平均，十年可信度 ≥ 2 倍，前后两段都为正，去掉最好的一段领先期仍为正。
  分不开：以上任何一条不满足；或者十年里独立的领先期太少（少于约 10 段），结论只靠几次判断。
市场：沪深300、恒生、标普500（人民币）。回看期 3、6、12 个月。
用法：python results/v5/diag/design/leader.py results/v5/diag/design
"""
import sys, pathlib, math, json
ROOT = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
from src.v3.engine.spec import load_spec
from src.v3.engine.sessions import decision_dates
from src.v4.r5.design import Markets
out = pathlib.Path(sys.argv[1]); spec = load_spec()
m = Markets(spec).get('index', t4=False, allow_substitute=True)
MK = ['csi300', 'hsi', 'spx']; ret = m.signal.loc[:'2015-12-31', MK + [m.cash_id]]
lr = np.log1p(ret.where(ret > -1).fillna(0.0))
fwd = np.expm1(lr[::-1].rolling(21, min_periods=21).sum()[::-1].shift(-1))
ds = [pd.Timestamp(d).normalize() for d in decision_dates(pd.DatetimeIndex(m.dates), 'month')]
ds = [d for d in ds if pd.Timestamp('2006-01-01') <= d <= pd.Timestamp('2015-11-30')]
res = {}
for L in (60, 120, 250):
    back = np.expm1(lr.rolling(L, min_periods=L).sum())
    rows = []
    for t in ds:
        b = back.loc[t, MK]; f = fwd.loc[t, MK]
        if b.isna().any() or f.isna().any(): continue
        lead = b.idxmax(); rows.append(dict(t=t, lead=lead, x=f[lead] - f.mean()))
    d = pd.DataFrame(rows).set_index('t')
    spell = (d.lead != d.lead.shift()).cumsum(); sp = d.groupby(spell).agg(lead=('lead', 'first'), start=('lead', lambda s: s.index[0].date()), n=('x', 'size'), x=('x', 'sum'))
    cred = lambda s: round(s.mean() / s.std() * math.sqrt(len(s)), 2) if len(s) > 2 else None
    best = sp.x.idxmax(); drop = d[spell != best].x
    res[f'{L}天'] = dict(领先期段数=len(sp), 每月平均超额=round(d.x.mean() * 100, 2), 可信度=cred(d.x),
                        前五年=round(d.loc[:'2010'].x.mean() * 100, 2), 后五年=round(d.loc['2011':].x.mean() * 100, 2),
                        去掉最好一段=round(drop.mean() * 100, 2), 最好一段=f"{sp.loc[best,'lead']} 自 {sp.loc[best,'start']}，{sp.loc[best,'n']} 个月，合计 {sp.loc[best,'x']*100:.1f}%",
                        领先占比=d.lead.value_counts(normalize=True).round(2).to_dict())
    sp.to_csv(out / f'leader-spells-{L}.csv')
(out / 'leader.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str)); print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
