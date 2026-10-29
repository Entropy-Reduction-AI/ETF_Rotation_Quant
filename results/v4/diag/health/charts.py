# v4 体检报告的三张图。读 results/v4/r5 的设计期产物，只到 2015-12-31。输出到当前目录 out/。
import pandas as pd, numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams.update({'font.family':['Noto Sans CJK SC'],'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,
 'axes.grid':True,'grid.alpha':.22,'font.size':11.5,'axes.edgecolor':'#9ca3af'})
INK,MUTED='#111827','#6b7280'; E2,A1,A2='#1d4ed8','#d97706','#7c3aed'; GOOD,BAD='#15803d','#c2410c'
import pathlib; R=str(pathlib.Path(__file__).resolve().parents[3]/'results/v4/r5')+'/'
g=pd.read_csv(R+'gate-inputs.csv',index_col=0,parse_dates=True)
rd=lambda c:pd.read_csv(R+f'design/{c}/index/net.csv',index_col=0,parse_dates=True)['net']
ser={'E2 新口径':g.B0,'基准':g.benchmark.fillna(0),'A1 双动量':rd('A1'),'A2 五腿均线':rd('A2')}
col={'E2 新口径':E2,'基准':INK,'A1 双动量':A1,'A2 五腿均线':A2}
ser={k:v.loc['2006-01-01':] for k,v in ser.items()}
nav={k:(1+v).cumprod() for k,v in ser.items()}
# ---- chart 1: NAV + drawdown
fig,(ax,bx)=plt.subplots(2,1,figsize=(11,7.2),sharex=True,gridspec_kw={'height_ratios':[2.6,1],'hspace':.08})
off={'E2 新口径':0,'基准':0,'A1 双动量':0,'A2 五腿均线':0}
for k,n in nav.items():
    ax.plot(n.index,n.values,color=col[k],lw=2.4 if k=='E2 新口径' else 1.8,zorder=3 if k=='E2 新口径' else 2)
    yrs=len(n)/252; c=n.iloc[-1]**(1/yrs)-1
    ax.annotate(f'{k}  {n.iloc[-1]:.1f} 倍 · 年化 {c*100:.1f}%',(n.index[-1],n.iloc[-1]),xytext=(8,{'E2 新口径':-2,'基准':-6,'A1 双动量':4,'A2 五腿均线':0}[k]),textcoords='offset points',
                color=col[k],fontsize=11,weight='bold',va='center')
    dd=n/n.cummax()-1
    bx.plot(dd.index,dd.values*100,color=col[k],lw=1.5 if k!='E2 新口径' else 2)
ax.set_yscale('log'); ax.set_yticks([1,2,4,8]); ax.set_yticklabels(['1','2','4','8'])
ax.set_ylabel('净值（对数刻度，2006 年初 = 1）')
bx.text(.99,.06,'最大回撤：基准 −66% · A1 −43% · E2 新口径 −39% · A2 −13%',transform=bx.transAxes,ha='right',fontsize=10.5,color=INK,weight='bold')
bx.set_ylabel('从高点回撤（%）'); bx.set_ylim(-75,3)
bx.set_xlim(pd.Timestamp('2006-01-01'),pd.Timestamp('2018-06-30'))
ax.set_title('十年跑赢基准，回撤只有基准的六成；但简单的 A1 双动量跑得更好',loc='left',fontsize=14.5,weight='bold',color=INK,pad=28)
ax.text(0,1.035,'U-指数池，设计期 2006-01-01 → 2015-12-31，人民币、含分红、扣成本。A1、A2 是公开同行（只做对照）。',transform=ax.transAxes,fontsize=10.5,color=MUTED,va='bottom')
fig.savefig('out/h1-nav.png',dpi=200,bbox_inches='tight',facecolor='white'); plt.close()
# ---- chart 2: yearly excess
y=pd.DataFrame({k:(1+v).groupby(v.index.year).prod()-1 for k,v in ser.items()})
ex=(y['E2 新口径']-y['基准'])*100; exa=(y['A1 双动量']-y['基准'])*100
print(ex.round(1).to_dict()); print(exa.round(1).to_dict())
fig,ax=plt.subplots(figsize=(11,4.6))
x=np.arange(len(ex)); w=.38
ax.bar(x-w/2,ex.values,w,color=E2,zorder=2,label='E2 新口径 − 基准')
ax.bar(x+w/2,exa.values,w,color=A1,zorder=2,label='A1 双动量 − 基准',alpha=.85)
for i,v in enumerate(ex.values):
    ax.text(i-w/2,v+(1.5 if v>0 else -1.5),f'{v:+.0f}'.replace('-','−'),ha='center',va='bottom' if v>0 else 'top',fontsize=10,color=INK,weight='bold')
ax.axhline(0,color=INK,lw=.9); ax.set_xticks(x); ax.set_xticklabels(ex.index); ax.grid(axis='x',visible=False)
ax.axvspan(-.5,4.5,color='#eaf0fd',zorder=0,lw=0); ax.axvspan(4.5,9.5,color='#fdeee6',zorder=0,lw=0)
ax.text(2,80,'前五年 2006–10：每年平均多赚 14.8 个百分点',ha='center',fontsize=10.5,color=E2,weight='bold')
ax.text(7,80,'后五年 2011–15：每年平均少赚 2.4 个百分点',ha='center',fontsize=10.5,color=BAD,weight='bold')
ax.set_ylim(-92,90); ax.set_ylabel('当年收益 − 基准（百分点）')
ax.legend(loc='lower right',frameon=False,fontsize=10.5,ncol=1)
ax.set_title('超额几乎都来自 2006–2008 三年；2009 年反弹落后 46 个百分点（A1 也落后）',loc='left',fontsize=14.5,weight='bold',color=INK,pad=28)
ax.text(0,1.035,'每根柱子 = 当年收益减基准（百分点）。年度平均超额按过关表口径（S1、S2 的年化超额）。',transform=ax.transAxes,fontsize=10.5,color=MUTED,va='bottom')
fig.savefig('out/h2-yearly.png',dpi=200,bbox_inches='tight',facecolor='white'); plt.close()
# ---- chart 3: states decomposition
st=['牛市','回调','熊市','反弹']; n=[53,21,27,19]
cash=[-55.3,28.1,81.5,-54.2]; sel=[45.1,-15.5,9.6,-0.8]; tot=[-10.2,12.6,91.2,-55.0]
fig,ax=plt.subplots(figsize=(11,4.4))
yy=np.arange(4)[::-1]; h=.34
ax.barh(yy+h/2,cash,h,color='#64748b',label='拿现金带来的',zorder=2)
ax.barh(yy-h/2,sel,h,color=E2,label='选标的带来的',zorder=2)
for i in range(4):
    for v,dy in ((cash[i],h/2),(sel[i],-h/2)):
        ax.text(v+(1.5 if v>=0 else -1.5),yy[i]+dy,f'{v:+.0f}'.replace('-','−'),va='center',ha='left' if v>=0 else 'right',fontsize=10,color=INK)
    c=GOOD if tot[i]>0 else BAD
    ax.text(108,yy[i],f'合计 {tot[i]:+.0f}'.replace('-','−'),va='center',ha='left',fontsize=11.5,weight='bold',color=c)
ax.set_yticks(yy); ax.set_yticklabels([f'{s}（{k} 个月）' for s,k in zip(st,n)],fontsize=11.5)
ax.axvline(0,color=INK,lw=.9); ax.set_xlim(-75,130); ax.grid(axis='y',visible=False)
ax.set_xlabel('相对基准的累计超额（百分点，月度加总）')
ax.legend(loc='lower right',frameon=False,fontsize=10.5,bbox_to_anchor=(.82,0))
ax.set_title('躲熊市全靠拿现金；同样的现金，在牛市和反弹里拖后腿',loc='left',fontsize=14.5,weight='bold',color=INK,pad=28)
ax.text(0,1.035,'E2 新口径，U-指数池，2006–2015 的 120 个月按沪深300 全收益分成四种行情。数字来自 Reviewer 签收。',transform=ax.transAxes,fontsize=10.5,color=MUTED,va='bottom')
fig.savefig('out/h3-states.png',dpi=200,bbox_inches='tight',facecolor='white'); plt.close()
