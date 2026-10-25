exec(open('v5.py').read().split("P0=bt.P.copy()")[0])
out={}
for st in [0.10,0.15]:
    rs=[run(v3sel(N),freq=fq,stop=st) for N in [3,5,8] for fq in ['M','W']]; out[st]=pd.concat(rs,axis=1).mean(axis=1)
pickle.dump(out,open('res6.pkl','wb'))
f=pickle.load(open('res5.pkl','rb'))['full']; out['none']=f
for k,v in out.items():
    n=(1+v).cumprod(); print(k,{a:round(float(b),3) for a,b in stats(v).items()}, '2015crash',round(n.loc['2015-09-15']/n.loc['2015-06-12']-1,3),'0708',round(n.loc['2008-11-04']/n.loc['2007-10-16']-1,3))
    print(v.groupby(v.index.year).apply(lambda x:(1+x).prod()-1).round(3).to_dict())
