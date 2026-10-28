# 示例取数（2026-10-28）：只读指数价格，演示 T1、T2 的规则怎么判断；不计算任何组合收益。
import pickle,pandas as pd,numpy as np
P,R,cash=pickle.load(open('data.pkl','rb')); bm=pickle.load(open('aux.pkl','rb'))[0]
P=P.drop(columns=['黄金'])
def cl(L): return (1+0.02/252)**L-1
def ret(d,L):
    k=P.index.get_loc(d); return P.iloc[k]/P.iloc[k-L]-1
me=P.index.to_series().groupby(P.index.to_period('M')).last()
rows=[]
for m in list(pd.period_range('2008-11','2009-07',freq='M'))+list(pd.period_range('2015-05','2015-09',freq='M')):
    d=me[m]; r={L:ret(d,L) for L in [20,60,120,250]}
    fu=(r[20]>cl(20))&(r[60]>cl(60)); fd=(r[20]<=cl(20))&(r[60]<=cl(60))
    row={'月末':d.date()}
    for L in [120,250]:
        e2=r[L]>cl(L); t1=(e2&~fd)|(~e2&fu)
        row[f'{L}E2']=int(e2.sum()); row[f'{L}T1']=int(t1.sum())
    rows.append(row)
print(pd.DataFrame(rows).to_string(index=False))
for d in ['2009-03-31','2015-07-31']:
    d=P.index[P.index.get_indexer([pd.Timestamp(d)],method='pad')[0]]
    print(d.date(),{L:round(100*ret(d,L)['沪深300'],1) for L in [20,60,120,250]}, {L:round(100*cl(L),1) for L in [20,60,120,250]})
# T2
px=(1+bm).cumprod()
ch=px.diff().abs()
er=(px-px.shift(60)).abs()/ch.rolling(60).sum()
pct=er.expanding(min_periods=250).apply(lambda x:(x[:-1]<x[-1]).mean() if len(x)>1 else np.nan,raw=True)
for d in ['2007-05-31','2008-10-31','2009-03-31','2009-06-30','2011-06-30','2012-06-29','2013-06-28','2015-06-30','2015-08-31']:
    d=px.index[px.index.get_indexer([pd.Timestamp(d)],method='pad')[0]]
    f=0.25+0.5*pct[d]; print(d.date(),'ER %.2f pct %.0f%% fast %.0f%% each fast %.1f%% slow %.1f%%'%(er[d],100*pct[d],100*f,50*f,50*(1-f)))
print('ER dist 2006-2015', er.loc['2006':'2015'].describe().round(2).to_dict())
