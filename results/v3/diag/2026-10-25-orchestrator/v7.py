import pickle,numpy as np,pandas as pd,sys; sys.path.insert(0,'.'); from bt import stats
f=pickle.load(open('res5.pkl','rb'))['full']; c=0.02/252
for tgt in [0.15,0.20]:
    vol=f.rolling(20).std()*np.sqrt(252)
    e=(tgt/vol).clip(upper=1).shift(2).fillna(1)   # known at close t-1, trade at close t -> earns from t+1
    r=e*f+(1-e)*c-0.001*e.diff().abs().fillna(0)
    n=(1+r).cumprod(); s=stats(r)
    print(tgt,{a:round(float(b),3) for a,b in s.items()},'2015crash',round(n.loc['2015-09-15']/n.loc['2015-06-12']-1,3),'avgexp',round(e.mean(),2))
    pickle.dump(r,open(f'res7_{int(tgt*100)}.pkl','wb'))
