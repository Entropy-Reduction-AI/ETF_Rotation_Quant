import sqlite3,pandas as pd,numpy as np,csv
c=sqlite3.connect('data/market.sqlite')
u=list(csv.DictReader(open('results/report/universe.csv')))
A={r['容器']:r['研究序列代码'] for r in u if r['研究序列代码'] not in('XNDX','^SP500TR','511880')}
def s(code): return pd.read_sql("select date,close from bars where adj='raw' and code=? and close>0 order by date",c,params=[code],index_col='date',parse_dates=['date'])['close']
P={k:s(v) for k,v in A.items()}
fx=s('USDCNY')
for k,v in [('纳指100','XNDX'),('标普500','^SP500TR')]:
    x=s(v); f=fx.reindex(x.index.union(fx.index)).ffill().reindex(x.index); P[k]=(x*f).dropna()
df=pd.DataFrame(P).sort_index().ffill(limit=5)
df=df[df.index>='2005-01-04']
df.to_pickle('/data/px.pkl')
print(df.shape, {k:str(df[k].first_valid_index().date()) for k in df})
