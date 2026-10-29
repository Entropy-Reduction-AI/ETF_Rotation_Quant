# v5 备忘示意图（2026-10-29）：全部是人造的示意路径，不是真实数据，不涉及任何回测。
import numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams.update({'font.family':['Noto Sans CJK SC'],'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,
 'axes.grid':True,'grid.alpha':.22,'font.size':11,'axes.edgecolor':'#9ca3af'})
INK,MUTED,BLUE,ORG,GRAY='#111827','#6b7280','#2563eb','#d97706','#9ca3af'
def save(fig,n): fig.savefig(f'out/{n}.png',dpi=200,bbox_inches='tight',facecolor='white'); plt.close(fig)
t=np.arange(0,12.01,1/21)
# 1 让赢家跑：A 一路涨，B 不动；每月拉回各 1/2 vs 不拉回
pa=np.exp(0.06*t); pb=np.ones_like(t)
wa_reb=np.empty_like(t); wa_run=pa/(pa+pb)
for i,x in enumerate(t):
    m=int(x); a0=np.exp(0.06*m); wa_reb[i]=0.5*pa[i]/a0/(0.5*pa[i]/a0+0.5)
# 2 小仓试错：进场后先给一半，站稳再补满；失败时只亏一半
s=np.linspace(0,60,61)
ok=np.r_[np.linspace(1,1.03,11),np.linspace(1.03,1.15,50)]
bad=np.r_[np.linspace(1,1.03,11),np.linspace(1.03,0.92,50)]
# 3 按波动调仓：波动突然变大，仓位自动变小
d=np.arange(0,120); vol=np.where(d<60,0.01,0.03); vol=np.convolve(vol,np.ones(10)/10,'same'); vol[:5]=0.01
pos=np.clip(0.01/vol,0,1)
fig,axs=plt.subplots(1,3,figsize=(12,3.9),gridspec_kw=dict(wspace=.32))
ax=axs[0]; ax.plot(t,wa_reb*100,color=GRAY,lw=2,label='现在：每月拉回各一半'); ax.plot(t,wa_run*100,color=BLUE,lw=2.2,label='让赢家跑：不拉回')
ax.set_ylim(40,70); ax.set_xlabel('月'); ax.set_ylabel('强者 A 的仓位 %'); ax.legend(frameon=False,fontsize=9,loc='upper left')
ax.set_title('① 让赢家跑',loc='left',fontsize=12.5,weight='bold',color=INK); ax.text(0,.02,'A 一直在涨、B 不动',transform=ax.transAxes,fontsize=9,color=MUTED)
ax=axs[1]
ax.plot(s,(ok-1)*np.r_[np.full(11,.5),np.full(50,1.0)]*100,color=BLUE,lw=2.2,label='做对：站稳后补满')
ax.plot(s,(bad-1)*np.full(61,.5)*100,color=ORG,lw=2.2,label='做错：只用了一半仓位')
ax.plot(s,(bad-1)*100,color=GRAY,lw=1.6,ls='--',label='做错但一次买满')
ax.axvline(10,color=MUTED,lw=.8,ls=':'); ax.text(10.5,9,'确认点',fontsize=9,color=MUTED)
ax.set_xlabel('进场后的交易日'); ax.set_ylabel('这笔交易对组合的贡献 %'); ax.legend(frameon=False,fontsize=9,loc='lower left')
ax.set_title('② 小仓试错',loc='left',fontsize=12.5,weight='bold',color=INK)
ax=axs[2]
vol2=np.r_[np.full(55,0.01),np.linspace(0.01,0.03,10),np.full(55,0.03)]; pos2=0.01/vol2
ax.axvspan(55,120,color='#fef3c7',lw=0); ax.text(58,92,'这段波动变成 3 倍',fontsize=9.5,color='#92400e')
ax.plot(d,np.full(120,100),color=GRAY,lw=2,label='现在：仓位不变')
ax.plot(d,pos2*100,color=BLUE,lw=2.2,label='按波动调仓')
ax.set_ylim(0,110); ax.set_xlabel('交易日'); ax.set_ylabel('这只资产的仓位（起点 = 100）'); ax.legend(frameon=False,fontsize=9,loc='lower left')
ax.set_title('③ 按波动调仓',loc='left',fontsize=12.5,weight='bold',color=INK)
fig.suptitle('三个方向都在做同一件事：错的时候代价小，对的时候拿得久',x=.125,ha='left',y=1.1,fontsize=14.5,weight='bold',color=INK)
fig.text(.125,1.0,'示意图，全部是人造的路径，不是回测，也不是真实数据。',fontsize=10.5,color=MUTED)
save(fig,'v5-mechanisms')
print('ok')
