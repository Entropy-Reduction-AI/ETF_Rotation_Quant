import sqlite3, json, urllib.request, pickle, numpy as np, pandas as pd, os
DB='/data/g3/data/market.sqlite'; con=sqlite3.connect(DB)
def ser(code):
    d=pd.read_sql("select date,close from bars where code=? order by date",con,params=(code,))
    d['date']=pd.to_datetime(d['date']); return d.set_index('date')['close'].astype(float)
cal=ser('H00300').loc['2005-01-01':'2015-12-31'].index
fx=ser('USDCNY')
if not os.path.exists('/data/explore/gld.pkl'):
    u="https://query1.finance.yahoo.com/v8/finance/chart/GLD?period1=1104537600&period2=1451606400&interval=1d&events=div"
    r=json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=30))['chart']['result'][0]
    g=pd.Series(r['indicators']['adjclose'][0]['adjclose'],index=pd.to_datetime(r['timestamp'],unit='s').normalize()); pickle.dump(g,open('/data/explore/gld.pkl','wb'))
gld=pickle.load(open('/data/explore/gld.pkl','rb'))
names={'H00300':'沪深300','H00905':'中证500','H00852':'中证1000','H00922':'中证红利',
 'H00986':'能源','H00987':'原材料','H00988':'工业','H00989':'可选消费','H00990':'主要消费','H00991':'医药','H00992':'金融地产','H00993':'信息技术','H00994':'通信','H00995':'公用事业'}
L={}
for c,n in names.items(): L[n]=ser(c)
def usd(s):  # US close of D-1 (US) used on A-share day D, times fx
    s=s.copy(); s.index=s.index+pd.Timedelta(days=1)
    s=s.reindex(cal,method='ffill'); f=fx.reindex(cal,method='ffill'); return s*f
L['恒生指数']=usd(ser('HSI').shift(0))  # HK same-day, approx via fx
L['纳指100']=usd(ser('XNDX')); L['标普500']=usd(ser('^SP500TR')); L['黄金']=usd(gld)
P=pd.DataFrame({k:v.reindex(cal,method='ffill') for k,v in L.items()})
# drop leading ffill before series start
for k,v in L.items(): P.loc[P.index<v.dropna().index[0],k]=np.nan
# 修正：休市日价格为 0（如 2012-10-30/31 飓风桑迪），视为缺失并沿用前值
P=P.mask(P<=0)
for k in P: 
    f=P[k].first_valid_index(); P.loc[f:,k]=P.loc[f:,k].ffill()
R=P.pct_change(fill_method=None)
cash=pd.Series(0.02/252,index=cal)
pickle.dump((P,R,cash),open('/data/explore/data.pkl','wb'))
print(P.apply(lambda s:s.first_valid_index()).to_string())
