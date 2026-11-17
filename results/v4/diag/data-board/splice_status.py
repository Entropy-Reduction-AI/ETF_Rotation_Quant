"""数据看板第 1 节的图：全市场口径（D36-3）每个容器的“上市前历史”状态，按大类。
只读已签收的 results/v51-diag/d37/s1-splice-roster.csv。
用法：python results/v4/diag/data-board/splice_status.py docs/assets/data-board
"""
import sys, csv, pathlib, collections
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
ROOT = pathlib.Path(__file__).resolve().parents[4]; OUT = pathlib.Path(sys.argv[1])
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
rows = list(csv.DictReader(open(ROOT / 'results/v51-diag/d37/s1-splice-roster.csv')))
SKIP = {'crude-oil', 'cross-border-commodity', 'theme-中信证券印度ETP指数'}
def state(x):
    if x['status'] == 'already': return '有自己的历史'
    if x['status'] == 'spliced': return '已接上指数'
    if x['container_id'].startswith(('us-xl', 'hk-hs')) or x['container_id'] in SKIP: return '无需接'
    return '在 Grok 第六轮'
ORDER = ['有自己的历史', '已接上指数', '在 Grok 第六轮', '无需接']
COL = {'有自己的历史': '#15803d', '已接上指数': '#4ade80', '在 Grok 第六轮': '#c2410c', '无需接': '#d1d5db'}
CLS = ['A股', '港股', '美股', '其他海外', '商品', '国债', '黄金']
cnt = collections.Counter((x['class'], state(x)) for x in rows)
fig, ax = plt.subplots(figsize=(12, 4.2))
left = [0] * len(CLS)
for st in ORDER:
    v = [cnt[(c, st)] for c in CLS]
    ax.barh(range(len(CLS)), v, left=left, color=COL[st], label=f'{st}（{sum(v)}）', edgecolor='white')
    for i, (l, n) in enumerate(zip(left, v)):
        if n: ax.text(l + n / 2, i, str(n), ha='center', va='center', fontsize=10.5, color='#151b26' if st != '在 Grok 第六轮' else 'white')
    left = [a + b for a, b in zip(left, v)]
for i, t in enumerate(left): ax.text(t + .6, i, f'共 {t}', va='center', color='#5d6676', fontsize=10.5)
ax.set_yticks(range(len(CLS))); ax.set_yticklabels(CLS); ax.invert_yaxis(); ax.set_xlim(0, 62)
ax.legend(frameon=False, ncol=4, loc='lower right', fontsize=10.5); ax.grid(axis='x', alpha=.2)
ax.set_xlabel('容器个数', color='#5d6676')
fig.text(.04, 1.07, '全市场 115 个容器：61 个已有上市前历史，36 个在 Grok 第六轮', fontsize=14.5, weight='bold', color='#151b26')
fig.text(.04, 1.0, '卡住的集中在美股和港股：要注册指数公司账号，云端收不到验证邮件', fontsize=10.5, color='#5d6676')
OUT.mkdir(parents=True, exist_ok=True); fig.savefig(OUT / 'd6-splice-status.png', dpi=150, bbox_inches='tight'); print(dict(cnt))
