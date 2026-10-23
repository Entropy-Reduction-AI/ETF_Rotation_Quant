import sys, numpy as np, pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.research.prereg_v1.panel import read_table, validate_panel
panel=validate_panel(read_table(str(ROOT / 'outputs/panel-2026-09-30.sqlite'),'panel'))
d=panel[(panel.date<='2015-12-31')&(panel.data_hole==0)]
px=d.pivot(index='date',columns='container',values='close').sort_index()
m=px.resample('ME').last()
r=m.pct_change()
A=['沪深300','中证500','中证1000','创业板','AI/算力','有色','煤炭','军工','医药','消费','白酒','农业','银行','券商','地产','红利']
O=['纳指100','标普500']
ra=r[A].mean(axis=1,skipna=True); ro=r[O].mean(axis=1)
ra=ra.iloc[1:]; ro=ro.reindex(ra.index).fillna(0)
cash=0.02/12
def stats(x,name,sw=None):
    nav=(1+x).cumprod(); yrs=len(x)/12
    cagr=nav.iloc[-1]**(1/yrs)-1; dd=(nav/nav.cummax()-1).min()
    print(f"{name:28s} 年化 {cagr:+.1%}  最大回撤 {dd:+.1%}  年化波动 {x.std()*12**.5:.1%}" + (f"  切换次数 {sw}" if sw is not None else ""))
def valve(x,out,back):
    # month-end drawdown from high of the A-leg NAV; out -> cash; back when rebound from lowest month-end > back
    nav=(1+x).cumprod(); state=1; hi=1; lo=None; res=[]; sw=0; idx=x.index
    v=1.0
    for i,t in enumerate(idx):
        res.append(x.iloc[i] if state else cash)
        n=nav.iloc[i]
        if state:
            hi=max(hi,n)
            if n/hi-1<-out: state=0; lo=n; sw+=1
        else:
            lo=min(lo,n)
            if n/lo-1>back: state=1; hi=n; sw+=1
    return pd.Series(res,index=idx),sw
print('设计期', ra.index[0].date(),'→',ra.index[-1].date())
stats(ra,'A股等权')
for o,b in [(25,10),(20,10),(30,10),(25,15)]:
    s,sw=valve(ra,o/100,b/100); stats(s,f'A股等权+阀{o}/{b}',sw)
for w in [0.3,0.5]:
    stats((1-w)*ra+w*ro,f'A股{1-w:.0%}+海外{w:.0%}')
    s,sw=valve(ra,0.25,0.10); stats((1-w)*s+w*ro,f'A股{1-w:.0%}(阀25/10)+海外{w:.0%}',sw)
stats(ro,'海外(纳指/标普等权,本币)')
print('A股与海外月收益相关', round(ra.corr(ro),2))
for y in [2008,2015]:
    pass
nav=(1+ra).cumprod(); print('A股等权 2008 年收益', round(((1+ra[ra.index.year==2008]).prod()-1),3))
