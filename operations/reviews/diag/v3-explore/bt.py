import pandas as pd,numpy as np
df=pd.read_pickle('/data/px.pkl'); df=df[df.index>='2006-01-04']
A=[c for c in df if c not in('纳指100','标普500')]; US=['纳指100','标普500']
def stats(r):
    r=r.dropna(); n=(r.index[-1]-r.index[0]).days/365.25; nav=(1+r).cumprod()
    return f"{(nav.iloc[-1]**(1/n)-1)*100:6.1f}% {((nav/nav.cummax())-1).min()*100:6.1f}%"
def run(pool,freq,L,K,cost=0.0015,skip=0):
    p=df[pool]; d=p.resample(freq).last().index
    dates=[p.index[p.index<=x][-1] for x in d]; dates=sorted(set(dates))
    rets=p.pct_change(); out=pd.Series(0.0,index=p.index); w=None; prev=pd.Series(0.0,index=pool)
    lb=p.shift(skip)/p.shift(skip+L)-1
    for i,t in enumerate(dates[:-1]):
        sc=lb.loc[t].dropna()
        if K=='ew': sel=sc.index
        else: sel=sc.sort_values(ascending=False).index[:K]
        nw=pd.Series(0.0,index=pool); 
        if len(sel): nw[sel]=1/len(sel)
        to=(nw-prev).abs().sum()
        seg=rets.loc[(rets.index>t)&(rets.index<=dates[i+1]),pool].fillna(0)
        # buy-and-hold within period
        g=(1+seg).cumprod(); v=(g*nw).sum(axis=1) if nw.sum()>0 else pd.Series(1.0,index=seg.index); pr=v.pct_change().fillna(v.iloc[0]-1)
        pr.iloc[0]-=to*cost; out.loc[pr.index]=pr.values
        last=g.iloc[-1]*nw; prev=last/last.sum() if last.sum()>0 else nw
    return out[out.index>dates[0]]
def per(r):
    return f"设计 {stats(r[:'2015-12-31'])} | 样本外 {stats(r['2016-01-01':])} | 全程 {stats(r)}"
ew=run(A,'ME',1,'ew'); print('A股16等权月再平衡      ',per(ew))
for pool,name in [(A,'A16'),(A+US,'A16+美2')]:
  for freq,fl,Ls in [('ME','月',[1,3,6,12]),('W-FRI','周',[4,13,26])]:
    for L in Ls:
      for K in [3,5]:
        unit='月' if freq=='ME' else '周'
        r=run(pool,freq,{'ME':21,'W-FRI':5}[freq]*L,K)
        print(f"{name:7s} {fl}调 回看{L:2d}{unit} top{K}",per(r))
