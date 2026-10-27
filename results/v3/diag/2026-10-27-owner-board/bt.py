import pickle, numpy as np, pandas as pd, sys
P,R,cash=pickle.load(open('data.pkl','rb'))
bm=pickle.load(open('aux.pkl','rb'))[0]
R=R.fillna(np.nan)
cal=P.index; me=pd.Series(cal,index=cal).groupby([cal.year,cal.month]).last().values
def run(sel, start='2006-01-05', end='2015-12-31', cost=0.001, stop=None, freq='M'):
    """sel(d)-> dict weights at decision day d (close). executed close d+1."""
    idx=cal; pos={i:k for k,i in enumerate(idx)}
    dec=set(me) if freq=='M' else set(pd.Series(idx,index=idx).groupby([idx.year,idx.isocalendar().week.values]).last().values)
    w={}; pending=None; tosell=[]; nav=[]; dates=[]; peak={}; stopped=set()
    for k,d in enumerate(idx):
        if d<pd.Timestamp('2005-12-01'): continue
        # earn today's return on current weights
        r=sum(wt*(cash[d] if a=='cash' else (0 if np.isnan(R.at[d,a]) else R.at[d,a])) for a,wt in w.items())
        # drift
        if w:
            g={a:wt*(1+(cash[d] if a=='cash' else (0 if np.isnan(R.at[d,a]) else R.at[d,a]))) for a,wt in w.items()}
            s=sum(g.values()); w={a:v/s for a,v in g.items()}
        c=0
        if pending is not None:
            new=pending; pending=None
            c=cost*sum(abs(new.get(a,0)-w.get(a,0)) for a in set(new)|set(w) if a!='cash')
            w=new; peak={a:P.at[d,a] for a in w if a!='cash'}; stopped=set(); tosell=[]
        for a in list(tosell):
            if a in w:
                nw=dict(w); nw['cash']=nw.get('cash',0)+nw.pop(a); c+=cost*w[a]; w=nw
        tosell=[]
        if stop is not None and w:
            for a in [a for a in w if a!='cash']:
                if np.isnan(P.at[d,a]): continue
                peak[a]=max(peak[a],P.at[d,a])
                if P.at[d,a]<peak[a]*(1-stop) and a not in stopped:
                    stopped.add(a); tosell.append(a)
        if d>=pd.Timestamp(start): nav.append(r-c); dates.append(d)
        if d in dec: pending=sel(d)
    return pd.Series(nav,index=dates)
def mom(d,Lb):
    k=cal.get_loc(d)
    if k<Lb: return None
    return P.iloc[k]/P.iloc[k-Lb]-1
def score(d,lbs,riskadj=False):
    k=cal.get_loc(d); out=[]
    for Lb in lbs:
        m=mom(d,Lb)
        if m is None: return None
        if riskadj:
            v=R.iloc[k-Lb+1:k+1].std()*np.sqrt(Lb); m=m/v
        out.append(m)
    return pd.concat(out,axis=1)
def stats(s):
    n=(1+s).cumprod(); b=bm.reindex(s.index).fillna(0); nb=(1+b).cumprod()
    ann=n.iloc[-1]**(252/len(s))-1; annb=nb.iloc[-1]**(252/len(s))-1
    mdd=(n/n.cummax()-1).min()
    # rolling 3y windows monthly start
    starts=s.index.to_series().groupby([s.index.year,s.index.month]).first().values; win=[]
    for st in starts:
        e=st+pd.DateOffset(years=3)
        if e>s.index[-1]: break
        a=n.loc[st:e]; bb=nb.loc[st:e]; win.append(a.iloc[-1]/a.iloc[0]-bb.iloc[-1]/bb.iloc[0])
    win=np.array(win)
    yr=s.groupby(s.index.year).apply(lambda r:(1+r).prod()-1)-b.groupby(b.index.year).apply(lambda r:(1+r).prod()-1)
    return dict(ann=ann,annbm=annb,ex=ann-annb,mdd=mdd,win3y=(win>0).mean(),yrs_beat=(yr>0).sum())
