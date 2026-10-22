# 满仓叠加：底仓 = 设计期全部容器等权（日度），交易仓位从底仓里挪出来，止损后钱回底仓而不是现金
import sys, numpy as np, pandas as pd
sys.path.insert(0,'/data/ETF_Rotation_Quant')
from src.research.prereg_v1.panel import read_table, validate_panel
from src.research.prereg_v1.config import DESIGN_END, Params
from src.research.prereg_v1.engine import simulate
panel=validate_panel(read_table('/data/ETF_Rotation_Quant/outputs/panel-2026-09-30.sqlite','panel'))
E=pd.Timestamp(DESIGN_END); d=panel[panel.date<=E]; p=Params(); start=d.date.min()
px=d.pivot(index='date',columns='container',values='close').sort_index()
hole=d.pivot(index='date',columns='container',values='data_hole').reindex_like(px)
r=px.where(hole.eq(0)).pct_change(fill_method=None)
ew=r.mean(axis=1).fillna(0)
def overlay(res):
    h=res.holdings.reindex(r.index).fillna(0).shift(1).fillna(0)   # 前一日收盘持仓 → 今日收益
    tilt=(h*(r.sub(ew,axis=0)).fillna(0)).sum(axis=1)
    return tilt
def ann(x): return x.mean()*252
res=simulate(d,p,start,E)
print('holdings 行和范围', res.holdings.sum(axis=1).describe()[['mean','max']].round(3).to_dict())
t=overlay(res); print(f'V1 叠加到满仓底仓：年化超额 {ann(t):+.2%}')
pool=d[(d.date>=start)&(d.date<E)&d.atr20.gt(0)&d.close.notna()&d.data_hole.eq(0)][['date','container','close','atr20']].reset_index(drop=True)
n=len(res.trades)+len(res.skipped); rng=np.random.default_rng(1); outs=[]
for k in range(60):
    s=pool.iloc[rng.choice(len(pool),size=n,replace=False)].copy()
    s['branch'],s['state'],s['rs_1m'],s['z_month']='随机','',np.nan,np.nan
    s['stop_level']=s.close-p.stop_atr*s.atr20; s['priority']=rng.random(len(s))
    s=s.sort_values(['date','priority']).reset_index(drop=True)
    outs.append(ann(overlay(simulate(d,p,start,E,signals=s))))
o=np.array(outs); print(f'随机入场叠加 60 次：年化超额中位 {np.median(o):+.2%}，5%~95% {np.percentile(o,5):+.2%} ~ {np.percentile(o,95):+.2%}；V1 百分位 {(o<ann(t)).mean():.2f}')
