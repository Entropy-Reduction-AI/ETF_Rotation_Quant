import json,sqlite3,pandas as pd,numpy as np
c=sqlite3.connect('/data/ETF_Rotation_Quant/data/market.sqlite')
S={}
for code in [r[0] for r in c.execute("select distinct code from fund_nav")]:
    n=pd.read_sql("select date,unit_nav nav from fund_nav where code=?",c,params=[code],index_col='date')
    p=pd.read_sql("select date,close from bars where adj='raw' and code=?",c,params=[code],index_col='date')
    S[code]=(p,n)
for code in ['159529','501225']:
    nav=pd.DataFrame([(r['FSRQ'],float(r['DWJZ'])) for r in json.load(open(f'{code}_nav.json')) if r['DWJZ']],columns=['date','nav']).set_index('date')
    px=pd.DataFrame([(r[0],float(r[2])) for r in json.load(open(f'{code}_px.json'))],columns=['date','close']).drop_duplicates('date').set_index('date')
    S[code]=(px,nav)
out=[];summ=[]
for code,(p,n) in S.items():
    d=p.join(n,how='outer').sort_index(); d.index=pd.to_datetime(d.index)
    d['navl']=d.nav.ffill().shift(1); d=d.dropna(subset=['close'])
    pr=(d.close/d.navl-1).dropna(); pr=pr[pr.index>='2021-01-01']
    if len(pr)<120: continue
    base=pr.rolling(250,min_periods=120).median().shift(1)
    dev=pr-base
    summ.append((code,round(pr.iloc[-1]*100,1),round(pr[-250:].median()*100,1),round(pr.max()*100,1),str(pr.idxmax().date()), round(base.iloc[-1]*100,1)))
    i=0; idx=pr.index
    while i<len(pr):
        if dev.iloc[i]>=0.10:
            j=i
            while j<len(pr) and dev.iloc[j]>0: j+=1
            seg=pr.iloc[i:j]; pk=seg.idxmax(); pkv=seg.max(); b=base.loc[pk]
            # revert: first date after peak where premium <= base + half of (peak-base)
            after=pr[pk:]; half=after[after<=b+(pkv-b)/2]
            rd=half.index[0] if len(half) else None
            start=pr.index[max(0,pr.index.get_loc(seg.index[0])-20)]
            r=dict(code=code,start=str(seg.index[0].date()),peak=str(pk.date()),peak_prem=round(pkv*100),base=round(b*100),
                   rise_days=int((pk-seg.index[0]).days), half_revert_days=(rd-pk).days if rd is not None else None)
            if rd is not None:
                r['px_chg']=round((d.close[rd]/d.close[pk]-1)*100,1); r['nav_chg']=round((d.navl[rd]/d.navl[pk]-1)*100,1)
            out.append(r); i=j
        else: i+=1
print(pd.DataFrame(summ,columns=['code','now%','1y中位%','max%','max日','基线%']).to_string(index=False))
print(pd.DataFrame(out).to_string(index=False))
