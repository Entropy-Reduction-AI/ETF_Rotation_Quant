"""D38 第 29 行补充：高 TRIN 的 t 值，以及它和“母指数跌破均线”是不是同一件事（看过 V1 后加的拆分）。"""
import sys, numpy as np, pandas as pd, pathlib
sys.argv=['x','/tmp']
src=open('scripts/preflight/volume_signals.py').read().split("res = {}")[0]; g={'__file__':'/home/claude/etf_rotation_quant/scripts/preflight/volume_signals.py'}; exec(src,g)
for name,args in (('US',(g['US'],False,'SPX',False,'1999-01-01')),('A',(g['AS'],True,'H00300',True,'2005-01-01'))):
    PX,AM,par=g['universe'](*args)
    me=PX.resample('ME').last(); mr=me.pct_change(); amt=AM.resample('ME').sum(min_count=5)
    adv,dec=mr>0,mr<0
    trin=((adv.sum(axis=1)/dec.sum(axis=1).replace(0,np.nan))/((amt*adv).sum(axis=1)/(amt*dec).sum(axis=1).replace(0,np.nan))).replace([np.inf,-np.inf],np.nan)
    pme=par.resample('ME').last(); pm=pme.pct_change(); below=pme<pme.rolling(10).mean()
    d=pd.DataFrame({'trin':trin,'nx':pm.shift(-1),'below':below}).dropna()
    q=d['trin'].quantile(2/3); hi=d['trin']>=q
    a,b=d.loc[hi,'nx'],d.loc[~hi,'nx']
    t=(a.mean()-b.mean())/np.sqrt(a.var()/len(a)+b.var()/len(b))
    print(name,'高TRIN下月',round(a.mean()*1200,1),'其余',round(b.mean()*1200,1),'t',round(t,2),'高TRIN月里母在均线下',round(d.loc[hi,'below'].mean(),2),'全部',round(d['below'].mean(),2))
    for st in (True,False):
        x=d[d.below==st]; h=x['trin']>=q
        print('  母在均线','下' if st else '上','高TRIN',round(x.loc[h,'nx'].mean()*1200,1),int(h.sum()),'其余',round(x.loc[~h,'nx'].mean()*1200,1),int((~h).sum()))
