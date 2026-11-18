"""数据看板第 1 节的图：全市场口径（D36-3）每个容器的“上市前历史”状态，按大类。
只读已签收的 results/v51-diag/d37/s1-splice-roster.csv。
用法：python results/v4/diag/data-board/splice_status.py docs/assets/data-board
"""
import sys, csv, pathlib, collections
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT = pathlib.Path(__file__).resolve().parents[4]; OUT = pathlib.Path(sys.argv[1])
_fonts = {font.name for font in font_manager.fontManager.ttflist}
_font = next((name for name in ('Noto Sans CJK SC', 'WenQuanYi Micro Hei', 'Droid Sans Fallback') if name in _fonts), 'sans-serif')
plt.rcParams.update({'font.family': [_font], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'font.size': 11.5, 'axes.edgecolor': '#9ca3af'})
rows = list(csv.DictReader(open(ROOT / 'results/v51-diag/d37/s1-splice-roster.csv')))
SKIP = {'crude-oil', 'cross-border-commodity', 'theme-中信证券印度ETP指数'}
# 第六轮派单时就已经冻结的容器。后加的 A 股主题没接上时单独计，不并进这一格。
GROK = {
    'chinext', 'soymeal', 'theme-HSFML25', 'theme-HSISC', 'theme-HSSC50', 'theme-HSSCAMHI',
    'theme-HSSCHKY', 'theme-HSSCITI', 'theme-HSSCPB', 'theme-HSSCSOY', 'theme-HSSCT',
    'theme-MSCI China Value Weighted Index', 'theme-MSCI USA 50 Index',
    'theme-S&P 500 Energy Sector Index(NTR)', 'theme-SPAHLVCP', 'theme-iEdge Emerging Asia Select 50 Index',
    'theme-东证指数', 'theme-富时亚太低碳精选指数', 'theme-富时沙特阿拉伯指数', 'theme-巴西IBOVESPA指数',
    'theme-恒生中国企业指数', 'theme-恒生中国央企指数', 'theme-恒生创新药指数', 'theme-恒生生物科技指数',
    'theme-新交所泛东南亚科技指数', 'theme-标普500信息科技指数', 'theme-标普500医疗保健等权重指数',
    'theme-标普500消费精选指数', 'theme-标普中国新经济行业指数', 'theme-标普全球石油指数',
    'theme-标普生物科技精选行业指数', 'theme-标普石油天然气勘探及生产精选行业指数',
    'theme-标普美国品质消费股票指数', 'theme-法兰克福DAX指数', 'theme-道琼斯美国石油开发与生产指数',
    'theme-道琼斯美国精选REIT指数',
}
def state(x):
    if x['status'] == 'already': return '有自己的历史'
    if x['status'] == 'spliced': return '已接上指数'
    if x['container_id'].startswith(('us-xl', 'hk-hs')) or x['container_id'] in SKIP: return '无需接'
    if x['container_id'] in GROK: return '在 Grok 第六轮'
    return '未接上'
ORDER = ['有自己的历史', '已接上指数', '在 Grok 第六轮', '未接上', '无需接']
COL = {'有自己的历史': '#15803d', '已接上指数': '#4ade80', '在 Grok 第六轮': '#c2410c', '未接上': '#fdba74', '无需接': '#d1d5db'}
DARK = {'在 Grok 第六轮'}
CLS = ['A股', '港股', '美股', '其他海外', '商品', '国债', '黄金']
cnt = collections.Counter((x['class'], state(x)) for x in rows)
ORDER = [st for st in ORDER if sum(cnt[(c, st)] for c in CLS)]
fig, ax = plt.subplots(figsize=(12, 4.2))
left = [0] * len(CLS)
for st in ORDER:
    v = [cnt[(c, st)] for c in CLS]
    ax.barh(range(len(CLS)), v, left=left, color=COL[st], label=f'{st}（{sum(v)}）', edgecolor='white')
    for i, (l, n) in enumerate(zip(left, v)):
        if n: ax.text(l + n / 2, i, str(n), ha='center', va='center', fontsize=10.5, color='white' if st in DARK else '#151b26')
    left = [a + b for a, b in zip(left, v)]
for i, t in enumerate(left): ax.text(t + .6, i, f'共 {t}', va='center', color='#5d6676', fontsize=10.5)
have = sum(cnt[(c, st)] for c in CLS for st in ('有自己的历史', '已接上指数'))
grok = sum(cnt[(c, '在 Grok 第六轮')] for c in CLS)
ax.set_yticks(range(len(CLS))); ax.set_yticklabels(CLS); ax.invert_yaxis(); ax.set_xlim(0, max(left) + 8)
ax.legend(frameon=False, ncol=min(3, len(ORDER)), loc='upper center', bbox_to_anchor=(0.5, -0.28), fontsize=10.5); ax.grid(axis='x', alpha=.2)
ax.set_xlabel('容器个数', color='#5d6676')
fig.text(.04, 1.07, f'全市场 {len(rows)} 个容器：{have} 个已有上市前历史，{grok} 个在 Grok 第六轮', fontsize=14.5, weight='bold', color='#151b26')
fig.text(.04, 1.0, '卡住的集中在美股和港股：要注册指数公司账号，云端收不到验证邮件', fontsize=10.5, color='#5d6676')
OUT.mkdir(parents=True, exist_ok=True); fig.savefig(OUT / 'd6-splice-status.png', dpi=150, bbox_inches='tight'); print(dict(cnt))
