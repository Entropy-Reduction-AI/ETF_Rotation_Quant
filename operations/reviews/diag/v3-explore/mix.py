exec(open('/data/bt.py').read().split('def per')[0])
def per(r): return f"设计 {stats(r[:'2015-12-31'])} | 样本外 {stats(r['2016-01-01':])}"
ea=run(A,'ME',1,'ew',cost=0); eu=run(US,'ME',1,'ew',cost=0)
import pandas as pd
# monthly-rebalanced mix approx via monthly returns
ma=(1+ea).resample('ME').prod()-1; mu=(1+eu).resample('ME').prod()-1
for wa in [1,.7,.6,.5,.3,0]:
    print(f"A{int(wa*100)}/美{int(round((1-wa)*100))}", per(wa*ma+(1-wa)*mu))
