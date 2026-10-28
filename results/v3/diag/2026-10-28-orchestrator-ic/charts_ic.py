# IC 图（2026-10-28）：读 ic.pkl（ic.py 产出），只用 ≤2015 指数价格。
import pickle,pandas as pd,numpy as np,matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams.update({'font.family':['Noto Sans CJK SC'],'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,
 'axes.grid':True,'grid.alpha':.22,'font.size':11.5,'axes.edgecolor':'#9ca3af'})
INK,MUTED,SEL,OTH,BL='#111827','#6b7280','#2563eb','#cbd5e1','#16a34a'
ic=pickle.load(open('ic.pkl','rb'))
Ls=[5,10,20,40,60,90,120,180,250]; lab={5:'1周',10:'2周',20:'1月',40:'2月',60:'3月',90:'4.5月',120:'6月',180:'9月',250:'12月'}
fig,axs=plt.subplots(1,2,figsize=(11,4.6),gridspec_kw=dict(width_ratios=[10,6],wspace=.22))
ax=axs[0]; m=ic.mean()
xs=list(range(len(Ls)))+[len(Ls)+.6]; vals=[m[L] for L in Ls]+[m['blend']]
cols=[SEL if L in (20,60,120,250) else OTH for L in Ls]+[BL]
ax.bar(xs,vals,.7,color=cols,zorder=2)
for x,v in zip(xs,vals): ax.text(x,v+(.004 if v>=0 else -.004),f'{v:.2f}'.replace('-','−'),ha='center',va='bottom' if v>=0 else 'top',fontsize=10,color=INK)
ax.set_xticks(xs,[lab[L] for L in Ls]+['四个\n平均'],fontsize=10); ax.axhline(0,color=INK,lw=.8); ax.set_ylim(-.03,.12); ax.grid(axis='x',visible=False)
ax.set_ylabel('平均 IC'); ax.set_title('每种长度的平均 IC：都不高，忽高忽低',loc='left',fontsize=12,weight='bold',color=INK)
ax.text(.02,.93,'■ E2 用的四个长度',transform=ax.transAxes,fontsize=9.5,color=SEL,weight='bold'); ax.text(.3,.93,'■ 没用的邻近长度',transform=ax.transAxes,fontsize=9.5,color='#94a3b8',weight='bold'); ax.text(.58,.93,'■ 四个平均',transform=ax.transAxes,fontsize=9.5,color=BL,weight='bold')
ax=axs[1]
H1=ic.loc['2006':'2010'].mean(); H2=ic.loc['2011':'2015'].mean()
keys=[20,60,120,250,'blend']; names=['1月','3月','6月','12月','四个\n平均']; x=np.arange(5); w=.36
ax.bar(x-w/2,[H1[k] for k in keys],w*.95,color='#93c5fd',label='2006–10',zorder=2); ax.bar(x+w/2,[H2[k] for k in keys],w*.95,color='#1d4ed8',label='2011–15',zorder=2)
for i,k in enumerate(keys):
    for dx,v in [(-w/2,H1[k]),(w/2,H2[k])]: ax.text(i+dx,v+(.004 if v>=0 else -.004),f'{v:.2f}'.replace('-','−'),ha='center',va='bottom' if v>=0 else 'top',fontsize=9,color=INK)
ax.set_xticks(x,names,fontsize=10); ax.axhline(0,color=INK,lw=.8); ax.set_ylim(-.03,.14); ax.grid(axis='x',visible=False)
ax.legend(frameon=False,fontsize=9.5,loc='upper right'); ax.set_title('前后两段：3、6 个月各有一段归零',loc='left',fontsize=12,weight='bold',color=INK)
fig.suptitle('四个平均，和事后最好的 1 个月差不多，但不用事先猜中',x=.125,ha='left',y=1.06,fontsize=14.5,weight='bold',color=INK)
fig.text(.125,.975,'IC = 每个月末按得分给 17 个指数排名，和它们下个月实际涨幅排名的相关性。1 是全排对，0 是和随机一样。设计期 2006–2015。',fontsize=10.5,color=MUTED)
fig.savefig('out/r4-ic.png',dpi=200,bbox_inches='tight',facecolor='white')
