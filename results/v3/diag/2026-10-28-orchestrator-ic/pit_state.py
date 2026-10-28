# 诊断（2026-10-28）：只用当天以前的数据判断市场状态（T2 的口径）。只用基准指数价格，≤2015。
import pickle,pandas as pd,numpy as np
bm=pickle.load(open('aux.pkl','rb'))[0]
px=(1+bm).cumprod()
er=(px-px.shift(60)).abs()/px.diff().abs().rolling(60).sum()
dirn=np.sign(px/px.shift(60)-1)
pct=er.expanding(min_periods=250).apply(lambda x:(x[:-1]<x[-1]).mean(),raw=True)
me=px.index.to_series().groupby(px.index.to_period('M')).last()
d=pd.DataFrame({'px':px,'er':er,'pct':pct,'dir':dirn}).loc[me.values].loc['2006':'2015']
def lab(r):
    if r.pct>=0.5: return '单边涨' if r.dir>0 else '单边跌'
    return '震荡偏涨' if r.dir>0 else '震荡偏跌'
d['state']=d.apply(lab,axis=1)
d['fast']=0.25+0.5*d.pct
pickle.dump(d,open('pit_state.pkl','wb'))
print(d.state.value_counts().to_dict())
print(d.groupby(d.index.year).state.agg(lambda s:s.value_counts().to_dict()).to_string())
print(d.loc['2008-06':'2009-09',['er','pct','dir','state','fast']].round(2).to_string())
print('first pct date',pct.first_valid_index())
