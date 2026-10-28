# 诊断（2026-10-28）：时间序列一侧——“跑赢现金”这道门槛，对下个月有没有预测力。只用 ≤2015 指数价格。
import pickle,pandas as pd,numpy as np
P,R,cash=pickle.load(open('data.pkl','rb')); P=P.drop(columns=['黄金']).loc[:'2015-12-31']
me=P.index.to_series().groupby(P.index.to_period('M')).last()
dates=[pd.Timestamp(d) for d in me.values if pd.Timestamp(d)>=pd.Timestamp('2006-01-01')]
H=20; cl=lambda L:(1+0.02/252)**L-1
out={}
for L in [5,10,20,40,60,90,120,180,250]:
    diff=[]; hit=[]
    for d in dates:
        k=P.index.get_loc(d)
        if k+H>=len(P): continue
        r=P.iloc[k]/P.iloc[k-L]-1; f=P.iloc[k+H]/P.iloc[k]-1; ok=r.notna()&f.notna()
        pas=r[ok]>cl(L)
        if pas.sum()>0 and (~pas).sum()>0: diff.append(f[ok][pas].mean()-f[ok][~pas].mean())
        hit.append(((f[ok]>cl(H))==pas).mean())
    diff=np.array(diff)
    out[L]=dict(passed_minus_failed_pct=round(diff.mean()*100,2),t=round(diff.mean()/diff.std()*np.sqrt(len(diff)),2),hit=round(np.mean(hit)*100,1),n=len(diff))
print(pd.DataFrame(out).T.to_string())
