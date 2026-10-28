# T1/T2 示例图（2026-10-28）：只用指数价格和入选个数，不含组合收益。
import pickle,pandas as pd,numpy as np,matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
plt.rcParams.update({'font.family':['Noto Sans CJK SC'],'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,
 'axes.grid':True,'grid.alpha':.22,'font.size':11.5,'axes.edgecolor':'#9ca3af'})
INK,MUTED='#111827','#6b7280'; FAST,SLOW,E2C='#2563eb','#d97706','#9ca3af'
def save(fig,n): fig.savefig(f'out/{n}.png',dpi=200,bbox_inches='tight',facecolor='white'); plt.close(fig)
# --- t0: 四组怎么分钱
fig,ax=plt.subplots(figsize=(11,4.2)); ax.axis('off'); ax.set_xlim(0,100); ax.set_ylim(0,3.4)
rows=[('E2 现在：固定各 1/4',[25,25,25,25],2.3),('T2 · 市场单边时（例：2009-06）',[31,31,19,19],1.2),('T2 · 市场震荡时（例：2012-06）',[13,13,37,37],0.1)]
names=['1 个月组','3 个月组','6 个月组','12 个月组']; cols=[FAST,FAST,SLOW,SLOW]
for lab,ws,y in rows:
    ax.text(0,y+0.88,lab,fontsize=11.5,weight='bold',color=INK)
    x=0
    for w,n,c in zip(ws,names,cols):
        ax.add_patch(FancyBboxPatch((x+.3,y),w-.6,.72,boxstyle='round,pad=0,rounding_size=.6',fc=c,ec='white',alpha=.9))
        ax.text(x+w/2,y+.36,f'{n}  {w}%' if w>=18 else f'{w}%',ha='center',va='center',color='white',fontsize=10.5,weight='bold')
        x+=w
ax.set_title('四组 = 把钱分成四份，每份按一种时间长度单独选、单独持有',loc='left',fontsize=14.5,weight='bold',color=INK,pad=28)
ax.text(0,1.02,'蓝 = 快的两组（看 1、3 个月），橙 = 慢的两组（看 6、12 个月）。T2 改的是每份多大；T1 改的是慢的两份能买谁（下图）。',transform=ax.transAxes,fontsize=10.5,color=MUTED,va='bottom')
save(fig,'t0-four-groups')
# --- t1: 12 个月组能买几只
P,R,cash=pickle.load(open('data.pkl','rb')); P=P.drop(columns=['黄金'])
def cl(L): return (1+0.02/252)**L-1
def ret(k,L): return P.iloc[k]/P.iloc[k-L]-1
me=P.index.to_series().groupby(P.index.to_period('M')).last()
def counts(a,b):
    out=[]
    for m in pd.period_range(a,b,freq='M'):
        k=P.index.get_loc(me[m]); r={L:ret(k,L) for L in [20,60,250]}
        fu=(r[20]>cl(20))&(r[60]>cl(60)); fd=(r[20]<=cl(20))&(r[60]<=cl(60)); e2=r[250]>cl(250)
        out.append((m.strftime('%Y-%m'),int(e2.sum()),int(((e2&~fd)|(~e2&fu)).sum())))
    return out
fig,axs=plt.subplots(1,2,figsize=(11,4.4),gridspec_kw=dict(width_ratios=[9,5],wspace=.12),sharey=True)
for ax,(a,b,t) in zip(axs,[('2008-11','2009-07','2009：见底反弹'),('2015-05','2015-09','2015：见顶急跌')]):
    c=counts(a,b); x=np.arange(len(c)); w=.38
    ax.bar(x-w/2,[v[1] for v in c],w*.95,color=E2C,label='E2',zorder=2); ax.bar(x+w/2,[v[2] for v in c],w*.95,color=FAST,label='T1',zorder=2)
    for i,v in enumerate(c):
        ax.text(i-w/2,v[1]+.3,v[1],ha='center',fontsize=9.5,color=INK); ax.text(i+w/2,v[2]+.3,v[2],ha='center',fontsize=9.5,color=INK)
    ax.set_xticks(x,[v[0][2:] for v in c],fontsize=10); ax.grid(axis='x',visible=False); ax.set_title(t,fontsize=12,weight='bold',color=INK,loc='left'); ax.set_ylim(0,21); ax.set_yticks([0,5,10,15,17])
axs[0].set_ylabel('12 个月组能买的个数（共 17）')
axs[0].text(6.2,19.3,'E2 要等到 6 月',fontsize=10.5,color='#4b5563',weight='bold')
axs[0].text(1.6,19.3,'T1 1 月底就回来',fontsize=10.5,color=FAST,weight='bold')
axs[1].text(1.6,19.3,'T1 7、8 月就退出',fontsize=10.5,color=FAST,weight='bold')
axs[0].legend(frameon=False,loc='center left',bbox_to_anchor=(0,.62))
fig.suptitle('T1 让 12 个月组在转折点提前几个月回来，也提前退出',x=.125,ha='left',y=1.07,fontsize=14.5,weight='bold',color=INK)
fig.text(.125,.985,'每个月末，12 个月组里“有资格买”的标的个数。17 个指数（不含黄金），只看入选资格，不是收益。',fontsize=10.5,color=MUTED)
save(fig,'t1-example')
print('ok')
