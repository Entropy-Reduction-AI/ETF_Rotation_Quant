import pickle,pandas as pd,numpy as np,matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams['font.family']=['Noto Sans SC']; plt.rcParams['axes.unicode_minus']=False
plt.rcParams['svg.fonttype']='path'
plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.25,'font.size':12})
net,bm,pm,held,p,cls,Y,cc=pickle.load(open('/data/v3brief_res.pkl','rb')); n2,cnt,cap=pickle.load(open('/data/v3brief_res2.pkl','rb'))
res=pickle.load(open('/data/explore/res1.pkl','rb')); full=pickle.load(open('/data/explore/res5.pkl','rb'))['full']
# Fig1 where the money was
grp={'A股宽基':'A股','A股行业':'A股','A股红利':'A股','港股':'港股','美股宽基':'美股','美股和全球主题':'美股','现金':'现金'}
w=held.T.groupby(lambda k: grp.get(cls.get(k,'?'),'美股')).sum().T
w=w.loc[:'2015'].groupby(w.loc[:'2015'].index.year).mean()[['A股','港股','美股','现金']]*100
c=cnt.loc[:'2015'].groupby(cnt.loc[:'2015'].index.year).mean()
fig,ax=plt.subplots(figsize=(11,4.6),dpi=150); x=np.arange(len(w)); b=np.zeros(len(w))
for k,col in zip(w.columns,['#1d4ed8','#a855f7','#16a34a','#d1d5db']):
    ax.bar(x,w[k],.62,bottom=b,color=col,label=k); b+=w[k].values
ax.axhline(70,color='#111827',ls='--',lw=1.3); ax.text(-.55,72,'基准：A股 70%',ha='left',fontsize=10.5,color='#111827',bbox=dict(fc='white',ec='none',pad=1))
for i,v in enumerate(c.values): ax.text(i,102,f'{v:.0f} 个',ha='center',fontsize=10.5,color='#374151')
ax.text(-.6,109,'当年可选标的数 →',fontsize=10,color='#6b7280')
ax.set_xticks(x,w.index); ax.set_ylim(0,115); ax.set_yticks([0,25,50,75,100]); ax.set_ylabel('平均仓位 %')
ax.legend(ncol=4,frameon=False,loc='upper center',bbox_to_anchor=(.5,-.09),fontsize=10.5)
ax.set_title('2006–2011 能选的标的只有 4–6 个 → 常年近一半现金，A股远低于基准',loc='left',fontsize=13.5,weight='bold',pad=22)
fig.tight_layout(); fig.savefig('/data/dash2/money.svg'); plt.close()
# Fig2 NAV linear
fig,ax=plt.subplots(figsize=(11,4.8),dpi=150)
for s,lab,col,ls,lw in [(bm,'基准（70% 沪深300 + 15% 纳指 + 15% 标普）','#111827','-',2),(n2,'v3：正式规则实际回测（已剔除 2012 数据错误）','#9ca3af','-',2),(full,'E1：v3 规则不变，只补全标的池（探索）','#2563eb','-',2.4)]:
    n=(1+s.loc['2006-01-05':'2015-12-31']).cumprod(); ax.plot(n.iloc[::3],color=col,ls=ls,lw=lw,label=lab)
    ax.text(n.index[-1]+pd.Timedelta(days=40),n.iloc[-1],f'{n.iloc[-1]:.1f}',color=col,va='center',fontsize=12,weight='bold')
ax.set_ylabel('1 元变成多少'); ax.set_xlim(pd.Timestamp('2006-01-01'),pd.Timestamp('2016-09-01'))
ax.legend(frameon=False,loc='upper left',fontsize=10.5)
ax.set_title('只修“池子”这一处：同一套规则从跑输变成跑赢（设计期 2006–2015）',loc='left',fontsize=13.5,weight='bold')
fig.tight_layout(); fig.savefig('/data/dash2/nav-e1.svg'); plt.close()
print(w.round(0).to_string()); print((1+full).prod(),(1+n2.loc[:'2015']).prod(),(1+bm.loc[:'2015']).prod())
