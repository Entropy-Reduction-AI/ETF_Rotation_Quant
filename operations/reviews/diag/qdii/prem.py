import json,sqlite3,sys,pandas as pd,os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
c=sqlite3.connect(f'file:{ROOT / "data" / "market.sqlite"}?mode=ro',uri=True)
codes=sys.argv[1:] or [f[:6] for f in sorted(os.listdir('qdii_nav')) if f.endswith('.json')]
for code in codes:
    nav=pd.DataFrame(json.load(open(f'qdii_nav/{code}.json')))
    nav=nav.assign(date=nav.FSRQ,nav=pd.to_numeric(nav.DWJZ,errors='coerce'))[['date','nav','SGZT']].set_index('date')
    px=pd.read_sql("select date,close from bars where code=? and adj='raw'",c,params=(code,)).set_index('date')
    d=px.join(nav,how='inner').dropna(subset=['nav'])
    d['prem']=d.close/d.nav-1
    d.index=pd.to_datetime(d.index)
    y=d.prem.groupby(d.index.year).agg(['median','max','min'])
    st=d.SGZT.groupby(d.index.year).agg(lambda s:s.value_counts().index[0])
    print(f"== {code} n={len(d)}  全期中位 {d.prem.median():+.1%}  >3%占比 {(d.prem>.03).mean():.0%}  >10%占比 {(d.prem>.10).mean():.0%}")
    for yr in y.index: print(f"  {yr} 中位{y.loc[yr,'median']:+6.1%} 最高{y.loc[yr,'max']:+6.1%} 最低{y.loc[yr,'min']:+6.1%}  申购状态(众数) {st.loc[yr]}")
    big=d.prem.diff(5)
    print(f"  5日溢价最大收缩 {big.min():+.1%} @ {big.idxmin().date()}")
