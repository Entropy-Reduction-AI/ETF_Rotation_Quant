# 设计期：板块离 252 日最高收盘的距离（George-Hwang 52 周高点）与之后 20 日对等权超额；季度块自助
import sys, numpy as np, pandas as pd
sys.path.insert(0,'/data/ETF_Rotation_Quant')
from src.research.prereg_v1.panel import read_table, validate_panel
panel=validate_panel(read_table('/data/ETF_Rotation_Quant/outputs/panel-2026-09-30.sqlite','panel'))
d=panel[panel.date<='2015-12-31']
px=d.pivot(index='date',columns='container',values='close').sort_index()
hole=d.pivot(index='date',columns='container',values='data_hole').reindex_like(px)
px=px.where(hole.eq(0))
near=px/px.rolling(252,min_periods=200).max()
atr_ratio=(px.pct_change().abs().rolling(20).mean()/px.pct_change().abs().rolling(120).mean())
fwd=px.shift(-20)/px-1; ex=fwd.sub(fwd.mean(axis=1),axis=0)
ex=ex.iloc[:-20]
def test(sig,name,q=0.2):
    s=sig.reindex(ex.index)
    rk=s.rank(axis=1,pct=True)
    top=ex.where(rk>=1-q); rest=ex.where(rk<1-q)
    blk=ex.index.to_period('Q')
    a=top.stack().groupby(level=0).sum(); na=top.stack().groupby(level=0).count()
    b=rest.stack().groupby(level=0).sum(); nb=rest.stack().groupby(level=0).count()
    df=pd.DataFrame(dict(a=a,na=na,b=b,nb=nb)).fillna(0); df['q']=df.index.to_period('Q')
    g=df.groupby('q').sum()
    diff=g.a.sum()/g.na.sum()-g.b.sum()/g.nb.sum()
    rng=np.random.default_rng(0); bs=[]
    for _ in range(2000):
        i=rng.integers(0,len(g),len(g)); x=g.iloc[i]; bs.append(x.a.sum()/x.na.sum()-x.b.sum()/x.nb.sum())
    lo,hi=np.percentile(bs,[2.5,97.5])
    print(f"{name:30s} 前20%−其余 {diff:+.3%}  95% [{lo:+.3%}, {hi:+.3%}]  块 {len(g)}")
test(near,'离52周高点最近')
test(-atr_ratio,'波动收缩(20日/120日最小)')
test(near.where(atr_ratio<1),'近高点且波动收缩')
test(px/px.shift(20),'近1月涨幅(对照)')
