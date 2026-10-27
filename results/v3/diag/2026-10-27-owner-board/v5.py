import sys; sys.path.insert(0,'.'); import bt; from bt import *
LBS=[20,60,120,250]; cashL={Lb:(1.02**(Lb/252)-1) for Lb in LBS}
def v3sel(N):
    def f(d):
        k=bt.cal.get_loc(d); w={'cash':0.0}
        for Lb in LBS:
            if k<Lb: w['cash']+=1/len(LBS); continue
            Pk=bt.P.iloc[k]; P0=bt.P.iloc[k-Lb]; Rr=Pk/P0-1
            v=bt.R.iloc[k-Lb+1:k+1].std()*np.sqrt(Lb); s=(Rr/v)
            ok=Rr[(Rr>cashL[Lb])&s.notna()&bt.P.iloc[k-Lb:k+1].notna().all()].index
            top=s.loc[ok].sort_values(ascending=False).head(N).index
            for a in top: w[a]=w.get(a,0)+1/N/len(LBS)
            w['cash']+=(N-len(top))/N/len(LBS)
        return w
    return f
def arm():
    rs=[run(v3sel(N),freq=fq) for N in [3,5,8] for fq in ['M','W']]
    return pd.concat(rs,axis=1).mean(axis=1)
P0=bt.P.copy()
avail={'中证500':'2007-01-15','中证红利':'2008-05-26','中证1000':'2014-10-17','黄金':'2100-01-01'}
for c in ['能源','原材料','工业','可选消费','主要消费','医药','金融地产','信息技术','通信','公用事业']: avail[c]='2011-08-02'
Pm=P0.copy()
for c,d in avail.items(): Pm.loc[:pd.Timestamp(d)-pd.Timedelta(days=1),c]=np.nan
out={}
bt.P=Pm; out['pub']=arm()
bt.P=P0; out['full']=arm()
Pn=P0.copy(); Pn['黄金']=np.nan; bt.P=Pn; out['full_nogold']=arm()
pickle.dump(out,open('res5.pkl','wb'))
for k,v in out.items():
    print(k,{a:round(float(b),3) for a,b in stats(v).items()}); print(v.groupby(v.index.year).apply(lambda x:(1+x).prod()-1).round(3).to_dict())
