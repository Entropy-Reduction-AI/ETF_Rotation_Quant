"""画 tradable_all.py 的结果：检验段净值 + 前 6 各类平均仓位。用法：python tradable_all_chart.py <结果目录> <png>"""
import sys, json, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False, 'axes.spines.right': False, 'font.size': 11.5})
D = pd.read_csv(sys.argv[1] + '/tradable-all-daily.csv', parse_dates=['date']).set_index('date'); S = json.load(open(sys.argv[1] + '/tradable-all.json', encoding='utf-8'))
fig, (a, b) = plt.subplots(1, 2, figsize=(13, 5), gridspec_kw={'width_ratios': [1.7, 1]})
L = [('标普500全收益', '#93c5fd', 1.0), ('BM-同仓位', '#9ca3af', 1.4), ('全部可交易，前 3', '#d97706', 2.2), ('v6', '#2563eb', 2.4),
     ('全部可交易，等权全拿', '#0d9488', 1.4), ('全部可交易，前 6', '#c2410c', 2.2), ('沪深300全收益', '#fca5a5', 1.0)]
ends = {}
for k, c, lw in L:
    w = (100 * (1 + D[k]).cumprod()).resample('W').last().dropna(); a.plot(w.index, w, color=c, lw=lw); ends[k] = (w.iloc[-1], c)
last = -1e9; top = max(v for v, _ in ends.values())
for k, (v, c) in sorted(ends.items(), key=lambda x: x[1][0]):
    y = max(v, last + .045 * top); last = y
    a.text(D.index[-1] + pd.Timedelta(days=40), y, f'{k}：{v:.0f} 万', color=c, va='center', fontsize=10, weight='bold' if '可交易' in k or k == 'v6' else 'normal')
a.set_xlim(D.index[0], D.index[-1] + pd.Timedelta(days=1700)); a.set_xticks([pd.Timestamp(f'{y}-01-01') for y in range(2016, 2027, 2)]); a.set_xticklabels([str(y) for y in range(2016, 2027, 2)])
a.axhline(100, color='#9ca3af', lw=.6); a.grid(alpha=.2); a.set_ylabel('检验段 100 万变成多少万', color='#5d6676')
t = S['检验段']; a.set_title(f"所有能买到的基金一起轮动：前 3 每年 {t['全部可交易，前 3']['年化']:.1f}%、前 6 每年 {t['全部可交易，前 6']['年化']:.1f}%", fontsize=12.5, loc='left')
cat = S['前 6 持有']['各类平均仓位%']; ks = list(cat)[::-1]
col = {'A股': '#ef4444', '美股': '#2563eb', '原油油气': '#78350f', '港股与中概': '#f59e0b', '黄金': '#ca8a04', '其他海外': '#7c3aed', '商品': '#0d9488', '债券': '#64748b'}
b.barh(range(len(ks)), [cat[k] for k in ks], color=[col.get(k, '#999') for k in ks], height=.6)
for i, k in enumerate(ks):
    b.text(cat[k] + .5, i, f'{cat[k]:.1f}%', va='center', fontsize=10.5)
b.set_yticks(range(len(ks))); b.set_yticklabels(ks); b.set_xlim(0, max(cat.values()) * 1.25)
b.set_title('前 6：十年里平均放在哪类', fontsize=12.5, loc='left'); b.set_xlabel('平均仓位 %', color='#5d6676')
fig.tight_layout(); fig.savefig(sys.argv[2], dpi=130, bbox_inches='tight')
