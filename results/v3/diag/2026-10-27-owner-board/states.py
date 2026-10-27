# 市场状态分析（2026-10-27）：E2 正式版（P1）按沪深300 的快慢动量划分四种状态，超额拆成“拿现金”和“选标的”两部分。只用 ≤2015-12-31，只读已有结果。
import pickle,pandas as pd,numpy as np,sqlite3
bm=pickle.load(open('aux.pkl','rb'))[0].loc['2006-01-05':'2015-12-31']
r=pd.read_csv('P1-paths.csv',index_col=0,parse_dates=True)['executed'].loc['2006-01-05':'2015-12-31']
h=pd.read_csv('P1-held.csv',index_col=0,parse_dates=True)
cash_w=h['cash'].shift(1).reindex(r.index).fillna(1.0)   # 当天持有的现金比例（前一日收盘后的权重）
rc=0.02/252
con=sqlite3.connect('/home/claude/etf_rotation_quant/data/market.sqlite')
hs=pd.read_sql("select date,close from bars where code='H00300' and date<='2015-12-31' order by date",con,index_col='date',parse_dates=['date'])['close']
mh=hs.resample('ME').last()
slow=mh.pct_change(12); fast=mh.pct_change(1)
state=pd.Series(np.select([(slow>0)&(fast>0),(slow>0)&(fast<=0),(slow<=0)&(fast<=0)],['牛市','回调','熊市'],'反弹'),index=mh.index).where(slow.notna())
# 每日：拿现金效应 = 现金比例×(现金收益−基准)；选标的效应 = 其余
timing=cash_w*(rc-bm.reindex(r.index).fillna(0))
excess=r-bm.reindex(r.index).fillna(0)
select=excess-timing
d=pd.DataFrame({'excess':excess,'timing':timing,'select':select,'cash':cash_w})
mon=d[['excess','timing','select']].resample('ME').sum(); mon['cash']=d['cash'].resample('ME').mean()
mon['state']=state.reindex(mon.index)
mE=(1+r).resample('ME').prod()-1; mB=(1+bm).resample('ME').prod()-1
mon['E2']=mE; mon['bm']=mB
pickle.dump(mon,open('states_mon.pkl','wb'))
g=mon.dropna(subset=['state']).groupby('state')
out=pd.DataFrame({'月数':g.size(),'跑赢月份%':g.apply(lambda x:100*(x.E2>x.bm).mean()),'超额合计':100*g.excess.sum(),'拿现金':100*g.timing.sum(),'选标的':100*g.select.sum(),'平均现金%':100*g.cash.mean(),'基准月均%':100*g.bm.mean()}).loc[['牛市','回调','熊市','反弹']]
print(out.round(1).to_string()); print('total',round(100*mon.excess.sum(),1),round(100*mon.timing.sum(),1),round(100*mon.select.sum(),1))
# up/down capture vs bm monthly
up=mB>0; dn=mB<0
print('up capture',round(mE[up].mean()/mB[up].mean(),2),'down capture',round(mE[dn].mean()/mB[dn].mean(),2))
print(mon.groupby(mon.index.year)[['excess','timing','select']].sum().mul(100).round(0).to_string())
