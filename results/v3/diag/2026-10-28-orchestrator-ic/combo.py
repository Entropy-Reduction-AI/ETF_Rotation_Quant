# 示例（2026-10-28）：某一个调仓日，T1+T2 怎样一起决定持仓。只算当天的目标权重，不算收益。
import pickle,pandas as pd,numpy as np
P,R,cash=pickle.load(open('data.pkl','rb')); bm=pickle.load(open('aux.pkl','rb'))[0]
P=P.drop(columns=['黄金']); R=R.drop(columns=['黄金'])
cl=lambda L:(1+0.02/252)**L-1
px=(1+bm).cumprod(); er=(px-px.shift(60)).abs()/px.diff().abs().rolling(60).sum()
pct=er.expanding(min_periods=250).apply(lambda x:(x[:-1]<x[-1]).mean(),raw=True)
def weights(d,N,t1,t2):
    k=P.index.get_loc(d); r={};s={}
    for L in [20,60,120,250]:
        r[L]=P.iloc[k]/P.iloc[k-L]-1; s[L]=r[L]/(R.iloc[k-L+1:k+1].std()*np.sqrt(L))
    fu=(r[20]>cl(20))&(r[60]>cl(60)); fd=(r[20]<=cl(20))&(r[60]<=cl(60))
    if t2: f=0.25+0.5*pct[d]; size={20:f/2,60:f/2,120:(1-f)/2,250:(1-f)/2}
    else: size={L:.25 for L in s}
    w=pd.Series(0.0,index=list(P.columns)+['现金']); picks={}
    for L in [20,60,120,250]:
        el=r[L]>cl(L)
        if t1 and L in (120,250): el=(el&~fd)|(~el&fu)
        top=s[L][el&s[L].notna()].sort_values(ascending=False).head(N).index
        picks[L]=list(top)
        for a in top: w[a]+=size[L]/N
        w['现金']+=size[L]*(N-len(top))/N
    return w,size,picks
d=pd.Timestamp('2009-03-31'); N=5
for name,t1,t2 in [('E2',0,0),('T1',1,0),('T2',0,1),('T1+T2',1,1)]:
    w,size,picks=weights(d,N,t1,t2)
    print(name,{L:round(v*100,1) for L,v in size.items()})
    print('  picks',{L:p for L,p in picks.items()})
    print('  w',(w[w>0.0001]*100).round(1).sort_values(ascending=False).to_dict())
