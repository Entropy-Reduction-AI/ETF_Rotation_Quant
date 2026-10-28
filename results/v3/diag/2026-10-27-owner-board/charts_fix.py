import pickle, numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams.update({'font.family':['Noto Sans CJK SC'],'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,
 'axes.grid':True,'grid.alpha':.22,'font.size':11.5,'axes.edgecolor':'#9ca3af'})
INK,MUTED='#111827','#6b7280'
def title(ax,t,sub=None):
    ax.set_title(t,loc='left',fontsize=14.5,weight='bold',color=INK,pad=28 if sub else 12)
    if sub: ax.text(0,1.035,sub,transform=ax.transAxes,fontsize=10.5,color=MUTED,va='bottom')
def save(fig,n): fig.savefig(f'out/{n}.png',dpi=200,bbox_inches='tight',facecolor='white'); plt.close(fig)
# ---- b6 简化版：上=沪深300，下=每月防守仓位
H=pd.read_csv('P1-held.csv',index_col=0,parse_dates=True)
dfn=H[['cash','cgb-5y','cgb-10y','gold']].sum(axis=1)
m=(dfn.loc['2008-07':'2009-12'].resample('ME').mean()*100)
P=pickle.load(open('data.pkl','rb'))[0]['沪深300'].loc['2008-07-01':'2009-12-31']
fig,(a1,a2)=plt.subplots(2,1,figsize=(11,6.2),gridspec_kw=dict(height_ratios=[1,1.25],hspace=.18))
a1.plot(P.index,P/P.iloc[0],color=INK,lw=2.2)
lo=P.idxmin(); a1.plot([lo],[P.min()/P.iloc[0]],'o',color='#c2410c',ms=7)
a1.annotate('2008-11-04 见底',xy=(lo,P.min()/P.iloc[0]),xytext=(lo-pd.Timedelta(days=60),0.42),fontsize=10.5,color='#c2410c',weight='bold')
a1.axvspan(pd.Timestamp('2009-01-01'),pd.Timestamp('2009-06-30'),color='#fde68a',alpha=.35,lw=0)
a1.text(pd.Timestamp('2009-01-08'),1.38,'2009 上半年：沪深300 +55% 的反弹',fontsize=10.5,color='#92400e')
a1.set_ylabel('沪深300\n（7 月初 = 1）',fontsize=10); a1.set_xlim(pd.Timestamp('2008-06-15'),pd.Timestamp('2010-01-15')); a1.set_ylim(0.3,(P/P.iloc[0]).max()*1.08)
x=m.index-pd.Timedelta(days=14)
cols=['#f59e0b' if pd.Timestamp('2009-01-01')<=d<=pd.Timestamp('2009-06-30') else '#9ca3af' for d in m.index]
a2.bar(x,m.values,width=22,color=cols,zorder=2)
for xx,v in zip(x,m.values): a2.text(xx,v+2,f'{v:.0f}',ha='center',fontsize=9.5,color=INK)
a2.set_ylim(0,112); a2.set_ylabel('防守仓位 %\n（现金+国债+黄金）',fontsize=10); a2.set_xlim(a1.get_xlim())
a2.text(pd.Timestamp('2009-01-08'),95,'上半年平均 43%：反弹已经开始，钱还没回来',fontsize=10.5,weight='bold',color='#92400e')
title(a1,'2009 年少赚的 39 个百分点，全在上半年：见底之后，钱迟迟没回到场内',
      '上：沪深300 走势。下：E2 正式版每月平均有多少钱放在现金、国债和黄金里（越高 = 越没在场）。')
save(fig,'b6-2009')
# ---- b5 新版：每年能选几个
yrs=[2006,2007,2008,2009,2010,2011,2012,2013,2014,2015]
idx=[17,17,19,19,20,20,22,22,22,22]; trd=[0,1,1,1,1,1,5,9,12,14]
fig,ax=plt.subplots(figsize=(11,4.6)); xx=np.arange(len(yrs)); w=.38
ax.bar(xx-w/2,idx,w,color='#1d4ed8',label='指数池：用指数数据，假设每个指数都能买',zorder=2)
ax.bar(xx+w/2,trd,w,color='#f59e0b',label='可交易池：只算当年已经上市、跟踪同一指数的 ETF',zorder=2)
for i,(a,b) in enumerate(zip(idx,trd)):
    ax.text(i-w/2,a+.4,str(a),ha='center',fontsize=10,color='#1d4ed8',weight='bold'); ax.text(i+w/2,b+.4,str(b),ha='center',fontsize=10,color='#b45309',weight='bold')
ax.set_xticks(xx,[str(y) for y in yrs]); ax.set_ylim(0,26); ax.set_ylabel('当年年中能选的个数'); ax.grid(axis='x',visible=False)
ax.legend(frameon=False,loc='upper center',bbox_to_anchor=(.5,-.1),ncol=1,fontsize=10)
ax.annotate('沪深300 ETF 2012 年才上市',xy=(6+w/2,5),xytext=(3.4,8.5),fontsize=10.5,arrowprops=dict(arrowstyle='->',lw=1))
title(ax,'E2 补全的是指数数据，不是 ETF：2012 年以前，跟踪这些指数的 ETF 几乎都还没上市',
      '同一套 E2 规则，两种“能选什么”。设计期 2006–2015，按每年 6 月底统计。')
save(fig,'b5-tradable')
print('ok')
