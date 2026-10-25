import sys; sys.path.insert(0,'/data/explore'); from bt import *
cashL={Lb:(1.02**(Lb/252)-1) for Lb in [20,60,120,250]}
A=list(P.columns)
def topn(N,lbs,absf=True,slots=True,riskadj=True):
    def f(d):
        sc=score(d,lbs,riskadj)
        if sc is None: return {'cash':1.0}
        rr=score(d,lbs,False)
        s=sc.mean(axis=1).dropna()
        ok=s.index
        if absf: ok=[a for a in ok if (rr.loc[a]>[cashL[l] for l in lbs]).mean()>0.5]
        s=s.loc[list(ok)].sort_values(ascending=False).head(N)
        if len(s)==0: return {'cash':1.0}
        wt=1/N if slots else 1/len(s)
        w={a:wt for a in s.index}; w['cash']=1-wt*len(s); return w
    return f
def ew(d):
    k=cal.get_loc(d); av=[a for a in A if not np.isnan(P.iloc[k][a])]; return {a:1/len(av) for a in av}
res={}
res['等权持有全部']=run(ew)
res['v3 近似（N=5，空位放现金）']=run(topn(5,[20,60,120,250]))
res['① 不留空位（N=5）']=run(topn(5,[20,60,120,250],slots=False))
res['② 去掉绝对动量（N=5，始终满仓）']=run(topn(5,[20,60,120,250],absf=False))
res['② 去掉绝对动量（N=3）']=run(topn(3,[20,60,120,250],absf=False))
res['③ 只看近 1–3 个月（N=3，20/60 日）']=run(topn(3,[20,60],absf=False))
res['④ ③ + 单只回撤 10% 止损']=run(topn(3,[20,60],absf=False),stop=0.10)
res['④ ③ + 单只回撤 15% 止损']=run(topn(3,[20,60],absf=False),stop=0.15)
pickle.dump(res,open('/data/explore/res1.pkl','wb'))
rows={k:stats(v) for k,v in res.items()}
b=bm.loc['2006-01-05':'2015-12-31']; nb=(1+b).cumprod(); print('BM ann',nb.iloc[-1]**(252/len(b))-1,'mdd',(nb/nb.cummax()-1).min())
print(pd.DataFrame(rows).T.round(3).to_string())
