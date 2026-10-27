import pickle,sys; sys.path.insert(0,'.')
exec(open('v5.py').read().split("P0=bt.P.copy()")[0])
P0=bt.P.copy()
avail={'中证500':'2007-01-15','中证红利':'2008-05-26','中证1000':'2014-10-17','黄金':'2100-01-01'}
for c in ['能源','原材料','工业','可选消费','主要消费','医药','金融地产','信息技术','通信','公用事业']: avail[c]='2011-08-02'
Pm=P0.copy()
for c,d in avail.items(): Pm.loc[:pd.Timestamp(d)-pd.Timedelta(days=1),c]=np.nan
out={}
bt.P=Pm; out['v3']=arm()
bt.P=P0; out['E1']=arm()
for st in [0.08,0.10,0.12,0.15]:
    out[f'exit{int(st*100)}']=pd.concat([run(v3sel(N),freq=fq,stop=st) for N in [3,5,8] for fq in ['M','W']],axis=1).mean(axis=1)
f=out['E1']; c=0.02/252; vol=f.rolling(20).std()*np.sqrt(252)
e=(0.20/vol).clip(upper=1).shift(2).fillna(1); out['E3']=e*f+(1-e)*c-0.001*e.diff().abs().fillna(0)
pickle.dump(out,open('series.pkl','wb'))
for k,v in out.items():
    s=stats(v); y=v.groupby(v.index.year).apply(lambda x:(1+x).prod()-1)
    print(k,{a:round(float(b),3) for a,b in s.items()},'0610',round((1+y.loc[2006:2010]).prod(),2),'1115',round((1+y.loc[2011:2015]).prod(),2))
