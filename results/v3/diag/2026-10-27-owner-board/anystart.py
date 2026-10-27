# 任意起点检验（2026-10-27）：E2 正式版（P1）对基准与单一指数，每个月初为起点，持有 1/2/3/5 年比较年化。只用 ≤2015-12-31。
import pickle,pandas as pd
P,R,cash=pickle.load(open('data.pkl','rb')); bm=pickle.load(open('aux.pkl','rb'))[0]
e2=pd.read_csv('P1-paths.csv',index_col=0,parse_dates=True)['executed'].loc['2006-01-05':'2015-12-31']
idx=e2.index; nav=lambda r:(1+r.reindex(idx).fillna(0)).cumprod()
S={'E2':nav(e2),'基准':nav(bm)}
for k in ['沪深300','标普500','纳指100']:
    s=P[k].reindex(idx).ffill(); S[k]=s/s.iloc[0]
starts=pd.Series(idx,index=idx).groupby([idx.year,idx.month]).first().values
out={}
for H in [1,2,3,5]:
    rows=[]
    for s in starts:
        e=pd.Timestamp(s)+pd.DateOffset(years=H)
        if e>idx[-1]: break
        ee=idx[idx<=e][-1]; rows.append({'start':s,**{k:(v.loc[ee]/v.loc[s])**(1/H)-1 for k,v in S.items()}})
    out[H]=pd.DataFrame(rows).set_index('start')
pickle.dump(out,open('anystart.pkl','wb'))
