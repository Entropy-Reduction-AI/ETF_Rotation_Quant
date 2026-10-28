import pickle, numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams.update({'font.family':['Noto Sans CJK SC'],'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,
 'axes.grid':True,'grid.alpha':.22,'font.size':11.5,'axes.edgecolor':'#9ca3af'})
INK,MUTED='#111827','#6b7280'; FAST,SLOW='#2563eb','#d97706'
L=pickle.load(open('lbdecomp.pkl','rb')); bmS=pickle.load(open('aux.pkl','rb'))[0].loc['2006-01-05':'2015-12-31']
yb=bmS.groupby(bmS.index.year).apply(lambda x:(1+x).prod()-1)
t=pd.DataFrame({Lb:v.groupby(v.index.year).apply(lambda x:(1+x).prod()-1) for Lb,v in L.items()})
ex=t.sub(yb,axis=0)*100
d=(ex[20]+ex[60])/2-(ex[120]+ex[250])/2
print(d.round(1).to_dict())
fig,ax=plt.subplots(figsize=(11,4.4))
c=[FAST if v>0 else SLOW for v in d.values]
ax.bar(d.index,d.values,.62,color=c,zorder=2)
for x,v in d.items(): ax.text(x,v+(1.2 if v>0 else -1.2),f'{v:+.0f}'.replace('-','−'),ha='center',va='bottom' if v>0 else 'top',fontsize=10.5,color=INK,weight='bold' if abs(v)>15 else 'normal')
ax.axhline(0,color=INK,lw=.9)
ax.axvspan(2009.6,2013.4,color='#fef3c7',zorder=0,lw=0)
ax.text(2011.5,13,'2010–2013 平稳年份\n慢的连续 4 年小幅领先',ha='center',fontsize=10.5,color='#92400e',weight='bold')
ax.text(2009,d[2009]+7,'2009 见底反弹',ha='center',fontsize=10.5,color=FAST,weight='bold')
ax.text(2015,d[2015]+7,'2015 暴涨暴跌',ha='center',fontsize=10.5,color=FAST,weight='bold')
ax.set_xticks(d.index); ax.set_ylim(-15,50); ax.grid(axis='x',visible=False)
ax.set_ylabel('快的比慢的多赚（百分点）')
ax.text(2005.55,46,'▲ 快的赢（1、3 个月两组）',color=FAST,fontsize=10.5,weight='bold')
ax.text(2005.55,-13.5,'▼ 慢的赢（6、12 个月两组）',color=SLOW,fontsize=10.5,weight='bold')
ax.set_title('急变的年份快的大赢，平稳的年份慢的小赢',loc='left',fontsize=14.5,weight='bold',color=INK,pad=28)
ax.text(0,1.035,'每根柱子 = 只用快的两组 − 只用慢的两组，当年收益差（百分点）。18 个序列复现口径，设计期 2006–2015。',transform=ax.transAxes,fontsize=10.5,color=MUTED,va='bottom')
fig.savefig('out/r3-fast-vs-slow.png',dpi=200,bbox_inches='tight',facecolor='white')
