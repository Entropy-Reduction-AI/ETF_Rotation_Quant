# 分解（2026-10-27 登记）：E2 的四个回看期分组各自单独运行（规则同 E2，仅保留一个回看期，10% 离场）。不是候选规则。
import pickle,sys; sys.path.insert(0,'.')
exec(open('v5.py').read().split("P0=bt.P.copy()")[0])
import bt as B
def sel1(N,Lb):
    def f(d):
        k=B.cal.get_loc(d)
        if k<250: return {'cash':1.0}
        Rr=B.P.iloc[k]/B.P.iloc[k-Lb]-1; v=B.R.iloc[k-Lb+1:k+1].std()*np.sqrt(Lb); s=Rr/v
        ok=Rr[(Rr>cashL[Lb])&s.notna()&B.P.iloc[k-Lb:k+1].notna().all()].index
        top=s.loc[ok].sort_values(ascending=False).head(N).index
        w={a:1/N for a in top}; w['cash']=(N-len(top))/N; return w
    return f
out={}
for Lb in LBS:
    out[Lb]=pd.concat([run(sel1(N,Lb),freq=fq,stop=0.10) for N in [3,5,8] for fq in ['M','W']],axis=1).mean(axis=1)
pickle.dump(out,open('lbdecomp.pkl','wb'))
bm=B.bm.loc['2006-01-05':'2015-12-31']
yb=bm.groupby(bm.index.year).apply(lambda x:(1+x).prod()-1)
tab={}
for Lb,v in out.items():
    st=stats(v); y=v.groupby(v.index.year).apply(lambda x:(1+x).prod()-1); tab[f'{Lb}d']=y
    print(Lb,'ann %.1f mdd %.1f'%(st['ann']*100,st['mdd']*100))
t=pd.DataFrame(tab); t['基准']=yb; print((t*100).round(0).to_string())
