import sys; sys.path.insert(0,'/data/explore'); from bt import *
exec(open('v1.py').read().split("res={}")[0].split("from bt import *")[1])
res={}
res['③ 20/60日 N=3 满仓']=run(topn(3,[20,60],absf=False))
for st in [0.08,0.10,0.12,0.15]:
    res[f'④ +止损{int(st*100)}%（次日执行）']=run(topn(3,[20,60],absf=False),stop=st)
res['④ N=5 +止损10%']=run(topn(5,[20,60],absf=False),stop=0.10)
res['④ 20/60/120 N=3 +止损10%']=run(topn(3,[20,60,120],absf=False),stop=0.10)
res['④ 成本0.3% 止损10%']=run(topn(3,[20,60],absf=False),stop=0.10,cost=0.003)
res['v3近似+止损10%']=run(topn(5,[20,60,120,250]),stop=0.10)
pickle.dump(res,open('res2.pkl','wb'))
print(pd.DataFrame({k:stats(v) for k,v in res.items()}).T.round(3).to_string())
# yearly
yy=pd.DataFrame({k:v.groupby(v.index.year).apply(lambda r:(1+r).prod()-1) for k,v in res.items() if k in ['③ 20/60日 N=3 满仓','④ +止损10%（次日执行）']})
b=bm.loc['2006':'2015']; yy['BM']=b.groupby(b.index.year).apply(lambda r:(1+r).prod()-1)
print(yy.round(3).to_string())
# BM decomposition 2006-2008 + full
for a,bk in [('2006','2006'),('2007','2007'),('2008','2008'),('2009','2009'),('2006','2015')]:
    seg=R.loc[a:bk]; tot=lambda x:(1+x.fillna(0)).prod()-1
    print(a,bk,'HS300',round(tot(seg['沪深300']),3),'NDX',round(tot(seg['纳指100']),3),'SPX',round(tot(seg['标普500']),3),'BM',round(tot(bm.loc[a:bk]),3),
      'contrib approx A=.7*',round(.7*tot(seg['沪深300']),3),'US=',round(.15*tot(seg['纳指100'])+.15*tot(seg['标普500']),3))
