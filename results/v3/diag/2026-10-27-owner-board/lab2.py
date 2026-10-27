# lab.py without GLD (Yahoo unreachable); gold column = NaN
import sqlite3, pickle, numpy as np, pandas as pd, sys
sys.path.insert(0,'/home/claude/etf_rotation_quant')
DB='/home/claude/etf_rotation_quant/data/market.sqlite'; con=sqlite3.connect(DB)
def ser(code):
    d=pd.read_sql("select date,close from bars where code=? order by date",con,params=(code,))
    d['date']=pd.to_datetime(d['date']); return d.set_index('date')['close'].astype(float)
cal=ser('H00300').loc['2005-01-01':'2015-12-31'].index
fx=ser('USDCNY')
names={'H00300':'沪深300','H00905':'中证500','H00852':'中证1000','H00922':'中证红利',
 'H00986':'能源','H00987':'原材料','H00988':'工业','H00989':'可选消费','H00990':'主要消费','H00991':'医药','H00992':'金融地产','H00993':'信息技术','H00994':'通信','H00995':'公用事业'}
L={}
for c,n in names.items(): L[n]=ser(c)
def usd(s):
    s=s.copy(); s.index=s.index+pd.Timedelta(days=1)
    s=s.reindex(cal,method='ffill'); f=fx.reindex(cal,method='ffill'); return s*f
L['恒生指数']=usd(ser('HSI')); L['纳指100']=usd(ser('XNDX')); L['标普500']=usd(ser('^SP500TR'))
P=pd.DataFrame({k:v.reindex(cal,method='ffill') for k,v in L.items()})
for k,v in L.items(): P.loc[P.index<v.dropna().index[0],k]=np.nan
P['黄金']=np.nan
P=P.mask(P<=0)
for k in P:
    f=P[k].first_valid_index()
    if f is not None: P.loc[f:,k]=P.loc[f:,k].ffill()
R=P.pct_change(fill_method=None)
cash=pd.Series(0.02/252,index=cal)
pickle.dump((P,R,cash),open('data.pkl','wb'))
from pathlib import Path
from src.v3.engine.benchmark import bm_main
bm=bm_main(Path(DB)); pickle.dump((bm,),open('aux.pkl','wb'))
print(P.apply(lambda s:s.first_valid_index()).to_string()); print('bm',bm.index[0],bm.index[-1],len(bm))
