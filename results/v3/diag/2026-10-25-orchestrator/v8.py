exec(open('v5.py').read().split("P0=bt.P.copy()")[0])
for st in [0.08,0.12]:
    v=pd.concat([run(v3sel(N),freq=fq,stop=st) for N in [3,5,8] for fq in ['M','W']],axis=1).mean(axis=1)
    y=v.groupby(v.index.year).apply(lambda x:(1+x).prod()-1)
    print(st,{a:round(float(b),3) for a,b in stats(v).items()},'0610',round((1+y.loc[2006:2010]).prod(),3),'1115',round((1+y.loc[2011:2015]).prod(),3))
