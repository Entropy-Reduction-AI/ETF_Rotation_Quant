import pickle, numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams.update({'font.family':['Noto Sans CJK SC'],'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,
 'axes.grid':True,'grid.alpha':.22,'font.size':11.5,'axes.edgecolor':'#9ca3af'})
INK,MUTED='#111827','#6b7280'
def title(ax,t,sub=None):
    ax.set_title(t,loc='left',fontsize=14.5,weight='bold',color=INK,pad=28 if sub else 12)
    if sub: ax.text(0,1.035,sub,transform=ax.transAxes,fontsize=10.5,color=MUTED,va='bottom')
def save(fig,n): fig.savefig(f'out/{n}.png',dpi=200,bbox_inches='tight',facecolor='white'); plt.close(fig)
mon=pickle.load(open('states_mon.pkl','rb')).dropna(subset=['state'])
order=['牛市','回调','熊市','反弹']; desc={'牛市':'大势向上\n这个月也涨','回调':'大势向上\n这个月在跌','熊市':'大势向下\n这个月也跌','反弹':'大势向下\n这个月在涨'}
g=mon.groupby('state'); n=g.size(); win=g.apply(lambda x:100*(x.E2>x.bm).mean())
T=100*g.timing.sum(); S=100*g.select.sum(); E=100*g.excess.sum()
# s1: contributions by state
fig,ax=plt.subplots(figsize=(11,5)); x=np.arange(4); w=.32
ax.bar(x-w/2,[T[k] for k in order],w,color='#9ca3af',label='拿现金带来的',zorder=2)
ax.bar(x+w/2,[S[k] for k in order],w,color='#1d4ed8',label='选标的带来的',zorder=2)
for i,k in enumerate(order):
    for xx,v in [(i-w/2,T[k]),(i+w/2,S[k])]: ax.text(xx,v+(2.5 if v>=0 else -2.5),f'{v:+.0f}',ha='center',va='bottom' if v>=0 else 'top',fontsize=10,color=INK)
    col='#15803d' if E[k]>0 else '#c2410c'
    ax.text(i,108,f'合计 {E[k]:+.0f}',ha='center',fontsize=12,weight='bold',color=col)
    ax.text(i,99,f'{n[k]} 个月 · 跑赢 {win[k]:.0f}%',ha='center',fontsize=9.5,color=MUTED)
ax.axhline(0,color=INK,lw=.8); ax.set_ylim(-45,118)
ax.set_xticks(x,[f'{k}\n{desc[k]}' for k in order]); ax.grid(axis='x',visible=False)
ax.set_ylabel('超额（百分点，按月相加）')
ax.legend(frameon=False,loc='upper center',bbox_to_anchor=(.5,-.2),ncol=2)
title(ax,'E2 的超额主要来自熊市防守；普通牛市里打平，反弹里输得最多',
      '设计期 2006–2015，按沪深300 的 12 个月和 1 个月涨跌把每个月分成四种状态。E2 正式版对基准的超额，拆成拿现金和选标的两部分。')
save(fig,'s1-states')
# s2: US share vs cap vs relative strength
h=pd.read_csv('P1-held.csv',index_col=0,parse_dates=True).loc['2006':'2015']
P=pickle.load(open('data.pkl','rb'))[0]
us=(h[['ndx100','spx']].sum(axis=1)).groupby(h.index.year).mean()*100
yr=lambda c:P[c].loc['2006-01-05':'2015-12-31'].dropna().groupby(lambda d:d.year).agg(lambda x:x.iloc[-1]/x.iloc[0]-1)
rel=(yr('纳指100')-yr('沪深300'))*100
fig,(a1,a2)=plt.subplots(2,1,figsize=(11,6),sharex=True,gridspec_kw=dict(height_ratios=[1,1.3],hspace=.12))
a1.bar(rel.index,rel.values,.6,color=['#16a34a' if v>0 else '#d1d5db' for v in rel.values],zorder=2)
for xx,v in rel.items():
    if np.isfinite(v): a1.text(xx,v+(3 if v>0 else -3),f'{v:+.0f}',ha='center',va='bottom' if v>0 else 'top',fontsize=9.5)
a1.axhline(0,color=INK,lw=.8); a1.set_ylabel('纳指100 − 沪深300\n当年收益差（百分点）',fontsize=10)
a1.set_ylim(-175,75)
a2.bar(us.index,us.values,.6,color='#16a34a',zorder=2)
for xx,v in us.items(): a2.text(xx,v+1,f'{v:.0f}%',ha='center',fontsize=10)
a2.axhline(43.9,color='#c2410c',ls='--',lw=1.4); a2.text(2005.6,45.5,'美股最多只能拿到约 44%（2 个名额 ÷ N）',color='#c2410c',fontsize=10.5)
a2.annotate('2010–2013 年，有 19–48% 的决策里\n纳指、标普排在第 1、2 名：美股名额已经用完，\n第 3 名起只能选别的',xy=(2011.5,20),xytext=(2005.7,27),fontsize=10.5,arrowprops=dict(arrowstyle='->',lw=1))
a2.set_ylim(0,55); a2.set_ylabel('E2 的美股仓位 %'); a2.set_xticks(us.index,[str(y) for y in us.index]); a2.grid(axis='x',visible=False)
title(a1,'美股再强，策略也拿不满：池子里美股只有 2 个名额',
      '上：当年纳指100 比沪深300 多（少）涨多少（人民币）。下：E2 正式版全年平均美股仓位。设计期 2006–2015。')
save(fig,'s2-us-cap')
print('ok')
