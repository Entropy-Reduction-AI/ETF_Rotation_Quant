import pickle,sys; sys.path.insert(0,'.')
exec(open('v5.py').read().split("P0=bt.P.copy()")[0])
import bt as B
src=open('bt.py').read()
# instrument: log weights after each day's trades
src=src.replace("        if d>=pd.Timestamp(start): nav.append(r-c); dates.append(d)",
                "        if d>=pd.Timestamp(start): nav.append(r-c); dates.append(d); LOG.append(dict(w))")
ns={}; exec(src,ns)
P0=ns['P'].copy()
avail={'中证500':'2007-01-15','中证红利':'2008-05-26','中证1000':'2014-10-17','黄金':'2100-01-01'}
for c in ['能源','原材料','工业','可选消费','主要消费','医药','金融地产','信息技术','通信','公用事业']: avail[c]='2011-08-02'
Pm=P0.copy()
for c,d in avail.items(): Pm.loc[:pd.Timestamp(d)-pd.Timedelta(days=1),c]=np.nan
LBS=[20,60,120,250]; cashL={Lb:(1.02**(Lb/252)-1) for Lb in LBS}
def sel_factory(Pv,Rv,N):
    def f(d):
        k=ns['cal'].get_loc(d); w={'cash':0.0}
        for Lb in LBS:
            if k<Lb: w['cash']+=1/len(LBS); continue
            Rr=Pv.iloc[k]/Pv.iloc[k-Lb]-1; v=Rv.iloc[k-Lb+1:k+1].std()*np.sqrt(Lb); s=Rr/v
            ok=Rr[(Rr>cashL[Lb])&s.notna()&Pv.iloc[k-Lb:k+1].notna().all()].index
            top=s.loc[ok].sort_values(ascending=False).head(N).index
            for a in top: w[a]=w.get(a,0)+1/N/len(LBS)
            w['cash']+=(N-len(top))/N/len(LBS)
        return w
    return f
out={}
for name,Pv,stop in [('v3',Pm,None),('E1',P0,None),('E2',P0,0.10)]:
    ns['P']=Pv; frames=[]
    for N in [3,5,8]:
        for fq in ['M','W']:
            ns['LOG']=[]; s=ns['run'](sel_factory(Pv,ns['R'],N),freq=fq,stop=stop)
            frames.append(pd.DataFrame(ns['LOG'],index=s.index).fillna(0))
    W=sum(f.reindex(columns=sorted(set().union(*[f.columns for f in frames])),fill_value=0) for f in frames)/6
    out[name]=W
ns['P']=P0
avail_cnt=Pm.loc['2006':'2015'].notna().sum(axis=1)
out['avail_v3']=avail_cnt; out['avail_full']=P0.loc['2006':'2015'].notna().sum(axis=1)
pickle.dump(out,open('weights.pkl','wb'))
A=['沪深300','中证500','中证1000','中证红利','能源','原材料','工业','可选消费','主要消费','医药','金融地产','信息技术','通信','公用事业']
for k in ['v3','E1','E2']:
    W=out[k]; g=pd.DataFrame({'A股':W.reindex(columns=A,fill_value=0).sum(axis=1),'港股':W.get('恒生指数',0),'美股':W.get('纳指100',0)+W.get('标普500',0),'现金':W['cash']})
    print(k); print((g.groupby(g.index.year).mean()*100).round(0).T.to_string())
print(out['avail_v3'].groupby(out['avail_v3'].index.year).mean().round(1).to_dict())
print('hs300 weight 2006 v3', round(out['v3'].loc['2006','沪深300'].mean(),3))
