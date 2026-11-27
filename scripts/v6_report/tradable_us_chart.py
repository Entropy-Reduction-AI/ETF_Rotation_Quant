import json, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt, sys
plt.rcParams.update({'font.family':['Noto Sans CJK SC'],'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'font.size':11.5})
D=pd.read_csv(sys.argv[1]+'/tradable-us-daily.csv',parse_dates=['date']).set_index('date').fillna(0); S=json.load(open(sys.argv[1]+'/tradable-us.json'))
fig,(a,b)=plt.subplots(1,2,figsize=(12.5,4.6),gridspec_kw={'width_ratios':[1.6,1]})
for k,c,lw,lab in [('美股指数版','#9ca3af',1.6,'指数（判定用）'),('美股可交易版','#2563eb',2.4,'真能买到的 QDII（场内价）')]:
    nav=100*(1+D[k]).cumprod(); w=nav.resample('W').last().dropna()
    a.plot(w.index,w,color=c,lw=lw); a.text(w.index[-1],w.iloc[-1],f'  {lab} {w.iloc[-1]:.0f} 万',color=c,va='center',fontsize=10.5,weight='bold' if '可交易' in k else 'normal')
a.set_xlim(D.index[0],D.index[-1]+pd.Timedelta(days=1500)); a.set_xticks([pd.Timestamp(f'{y}-01-01') for y in range(2016,2027,2)]); a.set_xticklabels([str(y) for y in range(2016,2027,2)]); a.grid(alpha=.2); a.set_ylabel('美股名额 100 万变成多少万',color='#5d6676')
u=S['美股名额（检验段）']; a.set_title(f"美股名额：指数每年 {u['指数版重放']['年化']:.1f}%，换成真能买到的每年 {u['可交易版']['年化']:.1f}%",fontsize=12.5,loc='left')
parts=[('换成能买到的\n（按净值）',u['拆开']['换成能买到的（按基金净值算）'],'#0d9488'),('溢价变化\n（场内价 − 净值）',u['拆开']['溢价变化（场内价 − 净值）'],'#d97706'),('合计',u['每年差（点）'],'#2563eb')]
for i,(n,v,c) in enumerate(parts):
    b.bar(i,v,color=c,width=.6); b.text(i,v+.1,f'+{v:.1f}',ha='center',va='bottom',fontsize=12,weight='bold',color=c)
b.set_xticks(range(3)); b.set_xticklabels([p[0] for p in parts]); b.axhline(0,color='#9ca3af',lw=.8); b.set_ylim(0,6.2)
b.set_title('每年多出的点数从哪来',fontsize=12.5,loc='left'); b.set_ylabel('美股名额每年 +几点',color='#5d6676')
fig.tight_layout(); fig.savefig(sys.argv[2],dpi=130,bbox_inches='tight')
