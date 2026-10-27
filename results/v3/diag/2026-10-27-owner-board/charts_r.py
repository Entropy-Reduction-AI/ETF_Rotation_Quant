import pickle, numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
plt.rcParams.update({'font.family':['Noto Sans CJK SC'],'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,
 'axes.grid':True,'grid.alpha':.22,'font.size':11.5,'axes.edgecolor':'#9ca3af'})
INK,MUTED='#111827','#6b7280'
def title(ax,t,sub=None):
    ax.set_title(t,loc='left',fontsize=14.5,weight='bold',color=INK,pad=28 if sub else 12)
    if sub: ax.text(0,1.035,sub,transform=ax.transAxes,fontsize=10.5,color=MUTED,va='bottom')
def save(fig,n): fig.savefig(f'out/{n}.png',dpi=200,bbox_inches='tight',facecolor='white'); plt.close(fig)
A=pickle.load(open('anystart.pkl','rb'))
# r1: win rate by horizon x comparator
comps=['基准','沪深300','标普500','纳指100']; cols=['#111827','#dc2626','#16a34a','#7c3aed']
fig,ax=plt.subplots(figsize=(11,4.6)); Hs=[1,2,3,5]; w=.19
for j,(k,c) in enumerate(zip(comps,cols)):
    v=[100*((A[H]['E2']-A[H][k])>0).mean() for H in Hs]
    xs=np.arange(4)+(j-1.5)*w; ax.bar(xs,v,w*.92,color=c,label=f'对 {k}',zorder=2)
    for x,y in zip(xs,v): ax.text(x,y+1.5,f'{y:.0f}',ha='center',fontsize=9.5,color=INK)
ax.axhline(50,color=MUTED,ls='--',lw=1); ax.text(3.62,51.5,'一半',fontsize=9.5,color=MUTED)
ax.set_xticks(range(4),[f'持有 {H} 年' for H in Hs]); ax.set_ylim(0,105); ax.set_ylabel('跑赢的起点占比 %'); ax.grid(axis='x',visible=False)
ax.legend(ncol=4,frameon=False,loc='upper center',bbox_to_anchor=(.5,-.1))
title(ax,'任意一个月买入：E2 约三分之二的时候跑赢基准，但多数时候跑不赢纳指100',
      '设计期 2006–2015，每个月初作为一个起点，持有 1/2/3/5 年后比较年化。E2 为正式引擎结果；指数均为人民币全收益。')
save(fig,'r1-anystart')
# r2: 3y excess by start month vs 基准 and 纳指
d=A[3]; fig,axs=plt.subplots(2,1,figsize=(11,5.6),sharex=True,gridspec_kw=dict(hspace=.25))
for ax,k,lab in [(axs[0],'基准','对基准'),(axs[1],'纳指100','对纳指100')]:
    ex=(d['E2']-d[k])*100
    ax.bar(ex.index,ex.values,width=25,color=['#16a34a' if v>0 else '#ea580c' for v in ex.values],zorder=2)
    ax.axhline(0,color=INK,lw=.8); ax.set_ylabel(f'{lab}\n年化差（百分点）',fontsize=10.5)
    ax.text(0.99,.92,f'跑赢 {100*(ex>0).mean():.0f}% 的起点',transform=ax.transAxes,ha='right',fontsize=10.5,weight='bold',color=INK,bbox=dict(fc='white',ec='none'))
axs[0].text(pd.Timestamp('2007-03-01'),36,'2006–07 年买入：大幅领先',fontsize=10.5,weight='bold',color='#15803d')
axs[0].text(pd.Timestamp('2009-03-01'),14,'2008 年底以后买入：和基准有输有赢',fontsize=10.5,weight='bold',color='#c2410c')
title(axs[0],'同一个策略，什么时候买入决定了结果：好看的十年曲线主要靠 2006–07 年',
      '每根柱子 = 从那个月初买入、持有 3 年，E2 比对照多（少）的年化百分点。设计期 2006–2015。')
save(fig,'r2-start-dependence')
# r3: lookback by year heatmap
L=pickle.load(open('lbdecomp.pkl','rb')); bmS=pickle.load(open('aux.pkl','rb'))[0].loc['2006-01-05':'2015-12-31']
yb=bmS.groupby(bmS.index.year).apply(lambda x:(1+x).prod()-1)
t=pd.DataFrame({f'{Lb}':v.groupby(v.index.year).apply(lambda x:(1+x).prod()-1) for Lb,v in L.items()})
ex=(t.sub(yb,axis=0)*100).T
names=['1 个月（20 日）','3 个月（60 日）','6 个月（120 日）','12 个月（250 日）']
fig,ax=plt.subplots(figsize=(11,3.6)); ax.grid(False)
im=ax.imshow(ex.values,cmap='RdYlGn',norm=TwoSlopeNorm(0,-30,70),aspect='auto')
for i in range(ex.shape[0]):
    for j in range(ex.shape[1]):
        v=ex.values[i,j]; best=v==ex.values[:,j].max()
        ax.text(j,i,f'{v:+.0f}',ha='center',va='center',fontsize=10.5,weight='bold' if best else 'normal',color=INK)
        if best: ax.add_patch(plt.Rectangle((j-.48,i-.46),.96,.92,fill=False,ec=INK,lw=1.8))
ax.set_xticks(range(ex.shape[1]),ex.columns); ax.set_yticks(range(4),names)
for s in ax.spines.values(): s.set_visible(False)
title(ax,'没有哪一种时间长度一直最好：每年最好的那组（黑框）在换',
      '把 E2 拆成只用一种时间长度的四个版本，每年比基准多（少）赚的百分点。18 个序列复现口径，设计期。')
save(fig,'r3-lookback-years')
print('ok')
