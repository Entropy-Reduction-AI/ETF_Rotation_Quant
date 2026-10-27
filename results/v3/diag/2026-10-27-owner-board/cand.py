# 预先登记（2026-10-27，跑之前写定）：
# C1 快信号回场：120/250 日两组的准入 = 本组回看期跑赢现金 OR (20 日与 60 日都跑赢现金)。排名不变。E2 其余不变（10% 离场）。
# C2 准入统一看 60 日：四组各自排名，准入统一为 60 日收益跑赢现金。E2 其余不变。
import pickle,sys; sys.path.insert(0,'.')
exec(open('v5.py').read().split("P0=bt.P.copy()")[0])
import bt as B
def sel(N,mode):
    def f(d):
        k=B.cal.get_loc(d); w={'cash':0.0}
        if k<250: return {'cash':1.0}
        Pk=B.P.iloc[k]
        ret={Lb:Pk/B.P.iloc[k-Lb]-1 for Lb in LBS}
        full={Lb:B.P.iloc[k-Lb:k+1].notna().all() for Lb in LBS}
        fast=(ret[20]>cashL[20])&(ret[60]>cashL[60])&full[60]
        for Lb in LBS:
            v=B.R.iloc[k-Lb+1:k+1].std()*np.sqrt(Lb); s=ret[Lb]/v
            own=(ret[Lb]>cashL[Lb])&full[Lb]
            if mode=='C1': ok=own|(fast&full[Lb]) if Lb in (120,250) else own
            else: ok=(ret[60]>cashL[60])&full[Lb]
            ok=ok&s.notna()
            top=s.loc[ok[ok].index].sort_values(ascending=False).head(N).index
            for a in top: w[a]=w.get(a,0)+1/N/len(LBS)
            w['cash']+=(N-len(top))/N/len(LBS)
        return w
    return f
out={}
for mode in ['C1','C2']:
    out[mode]=pd.concat([run(sel(N,mode),freq=fq,stop=0.10) for N in [3,5,8] for fq in ['M','W']],axis=1).mean(axis=1)
pickle.dump(out,open('cand.pkl','wb'))
S=pickle.load(open('series.pkl','rb')); out['E2']=S['exit10']; out['E1']=S['E1']
bm=B.bm
def seg(v,a,b): return (1+v.loc[a:b]).prod()
for k in ['E1','E2','C1','C2']:
    v=out[k]; st=stats(v); y=v.groupby(v.index.year).apply(lambda x:(1+x).prod()-1)
    print(k,'ann %.1f mdd %.1f win3y %.0f%% | 2008 %.0f 2009 %.0f | 06-10 %.2f 11-15 %.2f'%(st['ann']*100,st['mdd']*100,st['win3y']*100,y[2008]*100,y[2009]*100,seg(v,'2006','2010'),seg(v,'2011','2015')))
    print('   yearly', (y*100).round(0).astype(int).to_dict())
print('bm yearly',((bm.loc['2006':'2015'].groupby(bm.loc['2006':'2015'].index.year).apply(lambda x:(1+x).prod()-1))*100).round(0).astype(int).to_dict())
