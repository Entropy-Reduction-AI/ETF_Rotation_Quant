# v4 体检报告第 2 版用到的数字。只读 results/v4/r5 的设计期产物，只到 2015-12-31。
import sys, os, json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0,str(ROOT))
import pandas as pd, numpy as np
from src.v4.scorecard.gate import _segment_excess, state_points, _excess, SEGMENTS
R=ROOT/'results/v4/r5'
g=pd.read_csv(R/'gate-inputs.csv',index_col=0,parse_dates=True)
bm=g.benchmark
st=pd.read_csv(R/'month-states.csv',index_col=0,parse_dates=True)['state']
def rd(c,p): return pd.read_csv(R/f'design/{c}/{p}/net.csv',index_col=0,parse_dates=True)['net']
def cagr(r): r=r.dropna(); n=(1+r).prod(); return n**(252/len(r))-1
def mdd(r): n=(1+r.dropna()).cumprod(); return (n/n.cummax()-1).min()
out={'runs':{},'gate':{},'yearly':{},'eras':{},'win_by_state':{}}
for d in sorted(os.listdir(R/'design')):
  for p in ['index','tradable']:
    f=R/f'design/{d}/{p}/net.csv'
    if f.exists():
      r=rd(d,p).loc['2006':]; out['runs'][f'{d}/{p}']=[round(cagr(r)*100,2),round(mdd(r)*100,1)]
b=bm.loc['2006':].fillna(0); out['runs']['BM']=[round(cagr(b)*100,2),round(mdd(b)*100,1)]
for p in ['index','tradable']:
  for c in ['B0','T1','T2','T3','T4','A1','A2']:
    s=rd(c,p)
    ann={k:_segment_excess(s,bm,a,e) for k,a,e in SEGMENTS}
    pts=state_points(_excess(s,bm),st)
    out['gate'][f'{c}/{p}']={'s1':round(ann['s1']*100,1),'s2':round(ann['s2']*100,1),**{k:round(v,1) for k,v in pts.items()}}
    y=(1+s).groupby(s.index.year).prod()-1
    out['yearly'][f'{c}/{p}']={int(k):round(v*100,1) for k,v in y.items()}
    out['eras'][f'{c}/{p}']=[round(cagr(s.loc['2006':'2010'])*100,1),round(cagr(s.loc['2011':'2015'])*100,1)]
yb=(1+bm.fillna(0)).groupby(bm.index.year).prod()-1; out['yearly']['BM']={int(k):round(v*100,1) for k,v in yb.items()}
out['eras']['BM']=[round(cagr(bm.fillna(0).loc['2006':'2010'])*100,1),round(cagr(bm.fillna(0).loc['2011':'2015'])*100,1)]
# 每种行情里跑赢基准的月份占比
mb=(1+bm.fillna(0)).resample('ME').prod()-1
for p in ['index','tradable']:
  m=(1+rd('B0',p)).resample('ME').prod()-1
  df=pd.DataFrame({'x':m-mb}).join(st.rename('s'),how='inner')
  out['win_by_state'][p]={k:round(float((v.x>0).mean()*100)) for k,v in df.groupby('s')}
json.dump(out,open(sys.argv[1] if len(sys.argv)>1 else 'numbers.json','w'),ensure_ascii=False,indent=1)
