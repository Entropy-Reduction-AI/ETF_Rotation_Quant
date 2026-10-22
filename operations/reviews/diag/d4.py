# 设计期：A 股 16 容器等权（日度），比较 满仓 / 慢阀 25/10（月末）/ Faber 10 月 / Qullamaggie 10-20 日线（日度）
import sys, numpy as np, pandas as pd
sys.path.insert(0,'/data/ETF_Rotation_Quant')
from src.research.prereg_v1.panel import read_table, validate_panel
panel=validate_panel(read_table('/data/ETF_Rotation_Quant/outputs/panel-2026-09-30.sqlite','panel'))
d=panel[(panel.date<='2015-12-31')]
A=['沪深300','中证500','中证1000','创业板','AI/算力','有色','煤炭','军工','医药','消费','白酒','农业','银行','券商','地产','红利']
px=d.pivot(index='date',columns='container',values='close').sort_index()[A]
hole=d.pivot(index='date',columns='container',values='data_hole').reindex_like(px)
r=px.where(hole.eq(0)).pct_change(fill_method=None).mean(axis=1).fillna(0)
nav=(1+r).cumprod(); cash=0.02/252; cost=0.001  # 每次切换单边 0.05%×2
def run(inpos,name):
    pos=inpos.shift(1).fillna(1).astype(float)         # 信号当日收盘定，次日生效
    sw=pos.diff().abs().fillna(0)
    x=pos*r+(1-pos)*cash-sw*cost
    n=(1+x).cumprod(); yrs=len(x)/252
    by=x.groupby(x.index.year).apply(lambda s:(1+s).prod()-1)
    print(f"{name:22s} 年化 {n.iloc[-1]**(1/yrs)-1:+.1%} 回撤 {(n/n.cummax()-1).min():+.1%} 在场 {pos.mean():.0%} 切换/年 {sw.sum()/yrs:.1f} | 2008 {by[2008]:+.0%} 2009 {by[2009]:+.0%} 2015 {by[2015]:+.0%}")
run(pd.Series(1,index=r.index),'满仓')
# 慢阀：月末
me=nav.resample('ME').last(); st=[];s=1;hi=me.iloc[0];lo=None
for v in me:
    if s:
        hi=max(hi,v)
        if v/hi-1<-0.25: s=0; lo=v
    else:
        lo=min(lo,v)
        if v/lo-1>0.10: s=1; hi=v
    st.append(s)
run(pd.Series(st,index=me.index).reindex(r.index,method='ffill').fillna(1),'慢阀 25/10')
f=(me>me.rolling(10).mean()).astype(int); f[me.rolling(10).mean().isna()]=1
run(f.reindex(r.index,method='ffill').fillna(1),'Faber 10 月均线')
e10=nav.ewm(span=10,adjust=False).mean(); e20=nav.ewm(span=20,adjust=False).mean()
q=((e10>e20)&(e10.diff()>0)&(e20.diff()>0)).astype(int)
run(q,'Qulla 10/20 日线')
run((e10>e20).astype(int),'10>20 日线(宽松)')
