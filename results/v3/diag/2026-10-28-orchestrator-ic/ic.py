# 诊断（2026-10-28）：回看期的截面 Rank IC。17 个指数（18 序列复现口径去掉黄金），月末决策，未来 20 个交易日收益。
# 只用 ≤2015-12-31 的指数价格；不计算任何组合收益。
import pickle,pandas as pd,numpy as np
P,R,cash=pickle.load(open('data.pkl','rb')); P=P.drop(columns=['黄金']); R=R.drop(columns=['黄金'])
P=P.loc[:'2015-12-31']; R=R.loc[:'2015-12-31']
me=P.index.to_series().groupby(P.index.to_period('M')).last()
dates=[d for d in me.values if pd.Timestamp(d)>=pd.Timestamp('2006-01-01')]
H=20
def score(k,L):
    r=P.iloc[k]/P.iloc[k-L]-1; v=R.iloc[k-L+1:k+1].std()*np.sqrt(L); return r/v
Ls=[5,10,20,40,60,90,120,180,250]
rows=[]
for d in dates:
    k=P.index.get_loc(pd.Timestamp(d))
    if k+H>=len(P) or k<250: continue
    fwd=P.iloc[k+H]/P.iloc[k]-1
    row={'date':pd.Timestamp(d)}
    blend=[]
    for L in Ls:
        s=score(k,L); ok=s.notna()&fwd.notna()
        row[L]=s[ok].rank().corr(fwd[ok].rank())
        if L in (20,60,120,250): blend.append(s.rank())
    b=pd.concat(blend,axis=1).mean(axis=1); ok=b.notna()&fwd.notna(); row['blend']=b[ok].rank().corr(fwd[ok].rank())
    rows.append(row)
ic=pd.DataFrame(rows).set_index('date')
pickle.dump(ic,open('ic.pkl','wb'))
summ=pd.DataFrame({'meanIC':ic.mean(),'t':ic.mean()/ic.std()*np.sqrt(ic.count()),'pos%':(ic>0).mean()*100,'n':ic.count()}).round(3)
print(summ.to_string())
yr=ic.groupby(ic.index.year).mean()
print((yr[[20,60,120,250,'blend']]).round(2).to_string())
for L in [20,60,120,250,'blend']:
    y=yr[L]; print(L,'yr autocorr',round(y.autocorr(),2))
# halves
for a,b in [('2006','2010'),('2011','2015')]:
    print(a,b,ic.loc[a:b].mean().round(3).to_dict())
