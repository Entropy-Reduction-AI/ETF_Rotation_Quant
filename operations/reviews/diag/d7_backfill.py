import sys,csv,numpy as np,pandas as pd
sys.path.insert(0,'/data/ETF_Rotation_Quant')
from src.research.prereg_v1.panel import read_table, validate_panel
panel=validate_panel(read_table('/data/ETF_Rotation_Quant/outputs/panel-2026-09-30.sqlite','panel'))
A=['沪深300','中证500','中证1000','创业板','AI/算力','有色','煤炭','军工','医药','消费','白酒','农业','银行','券商','地产','红利']
u={r['theme']:r for r in csv.DictReader(open('data/universe.csv'))}
L={r['index_code']:r['launch_date'] for r in csv.DictReader(open('incoming/grok-pit-20261022/index_launch.csv'))}
d=panel[(panel.date<='2015-12-31')&(panel.data_hole==0)]
px=d.pivot(index='date',columns='container',values='close').sort_index()
m=px.resample('ME').last(); r=m.pct_change().iloc[1:]
launch={}
for a in A:
    code=u[a]['research_index_code']; ld=L.get(code,'')
    first=m[a].first_valid_index()
    launch[a]=pd.Timestamp(ld) if ld else None
    pre=((r.index< launch[a])&r[a].notna()).sum() if ld else None
    print(f"{a:6s} {code:8s} launch={ld or '?':10s} data_from={first.date()} premonths={pre}/{r[a].notna().sum()}")
cash=0.02/12
def valve(x,out=.25,back=.10):
    nav=(1+x).cumprod();st=1;hi=1;lo=None;res=[]
    for i in range(len(x)):
        res.append(x.iloc[i] if st else cash); n=nav.iloc[i]
        if st:
            hi=max(hi,n)
            if n/hi-1<-out: st=0;lo=n
        else:
            lo=min(lo,n)
            if n/lo-1>back: st=1;hi=n
    return pd.Series(res,index=x.index)
O=['纳指100','标普500']; ro=r[O].mean(axis=1).fillna(0)
def st(x,name):
    nav=(1+x).cumprod();c=nav.iloc[-1]**(12/len(x))-1;dd=(nav/nav.cummax()-1).min()
    print(f"{name:34s} 年化 {c:+.1%} 回撤 {dd:+.1%}")
for tag,mask in [('含回填(现口径)',None),('只用发布后',True)]:
    ra_=r[A].copy()
    if mask:
        for a in A:
            if launch[a] is not None: ra_.loc[ra_.index<launch[a],a]=np.nan
    n=ra_.notna().sum(axis=1)
    ra=ra_.mean(axis=1,skipna=True).fillna(0)
    st(ra,f'A股等权 {tag}'); st(valve(ra),f'A股+阀 {tag}'); st(.7*valve(ra)+.3*ro,f'70/30 {tag}')
    print('   每月可用容器数 2005末/2008末/2012末/2015末:',[int(n[n.index<=t].iloc[-1]) for t in ['2005-12-31','2008-12-31','2012-12-31','2015-12-31']])
