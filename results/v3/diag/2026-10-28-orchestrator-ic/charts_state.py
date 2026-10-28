# 图（2026-10-28）：只用当时已有数据判断的市场状态。读 pit_state.pkl（pit_state.py 产出），基准指数价格，≤2015。
import pickle,pandas as pd,numpy as np,matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Patch
plt.rcParams.update({'font.family':['Noto Sans CJK SC'],'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,
 'axes.grid':True,'grid.alpha':.22,'font.size':11.5,'axes.edgecolor':'#9ca3af'})
INK,MUTED='#111827','#6b7280'
d=pickle.load(open('pit_state.pkl','rb'))
C={'牛市':'#16a34a','回调':'#fbbf24','熊市':'#dc2626','反弹':'#60a5fa'}
fig,axs=plt.subplots(3,1,figsize=(11,6.4),sharex=True,gridspec_kw=dict(height_ratios=[3,.55,1.6],hspace=.22))
ax=axs[0]; ax.plot(d.index,d.px/d.px.iloc[0],color=INK,lw=1.8); ax.set_ylabel('基准（起点=1）')
ax.annotate('2007-10 见顶',xy=(pd.Timestamp('2007-10-31'),d.px.loc['2007-10-31']/d.px.iloc[0]),xytext=(pd.Timestamp('2008-08-01'),3.2),fontsize=10,color=MUTED,arrowprops=dict(arrowstyle='->',color=MUTED))
ax.annotate('2008-11 见底',xy=(pd.Timestamp('2008-11-28'),d.px.loc['2008-11-28']/d.px.iloc[0]),xytext=(pd.Timestamp('2009-06-01'),1.0),fontsize=10,color=MUTED,arrowprops=dict(arrowstyle='->',color=MUTED))
ax=axs[1]; ax.grid(False); ax.set_yticks([])
for t,s in d.dst.items():
    if isinstance(s,str): ax.bar(t,1,width=29,color=C[s],align='edge')
ax.set_ylim(0,1); ax.set_ylabel('方向',rotation=0,ha='right',va='center')
ax.text(pd.Timestamp('2006-02-01'),.35,'历史不足',fontsize=9.5,color=MUTED)
ax.legend(handles=[Patch(color=c,label=k) for k,c in C.items()],ncol=5,frameon=False,fontsize=9.5,loc='lower right',bbox_to_anchor=(1,.98),handlelength=1)
ax=axs[2]
ax.fill_between(d.index,d.pct*100,step='post',color='#a78bfa',alpha=.5,lw=0)
ax.axhline(50,color=MUTED,lw=1,ls='--'); ax.text(d.index[-1],52,'中间',fontsize=9.5,color=MUTED,ha='right')
ax.set_ylim(0,100); ax.set_ylabel('单边程度\n（历史百分位）',fontsize=10.5)
ax.text(pd.Timestamp('2006-02-01'),40,'历史不足，\nT2 先按各 1/4',fontsize=9.5,color=MUTED)
axs[0].set_title('只用当时已有的数据：方向能认出 07 年牛、08 年熊，但都晚几个月',loc='left',fontsize=14.5,weight='bold',color=INK,pad=28)
axs[0].text(0,1.03,'方向：过去 12 个月和过去 1 个月的涨跌（每个月末判断）。单边程度：过去 60 天净涨跌 ÷ 每天涨跌之和，再和此前的历史比。基准指数，设计期。',transform=axs[0].transAxes,fontsize=9.8,color=MUTED,va='bottom')
fig.savefig('out/r5-pit-state.png',dpi=200,bbox_inches='tight',facecolor='white')
