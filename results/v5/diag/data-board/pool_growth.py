"""数据看板第 1 节的图：v5 池子（不含 T4 的美股行业、港股分类，不含现金）每年末有多少容器
“有数据”、多少“已上市”，按 v5 大类堆叠。只统计起止日，不含任何收益。
用法：python results/v5/diag/data-board/pool_growth.py docs/assets/data-board/d1-pool-growth.png
"""
import sys, pathlib
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parents[4]
plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'axes.grid': True, 'grid.alpha': .22, 'font.size': 11.5,
                     'axes.edgecolor': '#9ca3af'})
INK, MUTED = '#151b26', '#5d6676'
SERIES = [('A股', 'A 股', '#2563eb'), ('港股', '港股', '#0d9488'), ('美股', '美股', '#7c3aed'),
          ('其他海外', '其他海外', '#d97706'), ('防守与商品', '国债、黄金、商品', '#9ca3af')]


def counts():
    c = pd.read_csv(ROOT / 'results/v4/diag/data-board/out/containers.csv')
    listing = [col for col in c.columns if col.startswith('上市日') or col == 'buy_first'][0]
    cls = pd.read_csv(ROOT / 'config/v5/classes.csv').set_index('container_id')['class']
    c['cls'] = c['id'].map(cls)
    v = c[~c['id'].str.match(r'^(us-|hk-)') & (c['cls'] != '现金')].copy()
    v['grp'] = v['cls'].where(v['cls'].isin(['A股', '港股', '美股', '其他海外']), '防守与商品')
    v['listed'] = pd.to_datetime(v[listing])
    v['data'] = pd.concat([pd.to_datetime(v['research_first']), v['listed']], axis=1).min(axis=1)
    years = list(range(2006, 2027))
    ends = [pd.Timestamp(f'{y}-12-31') if y < 2026 else pd.Timestamp('2026-09-30') for y in years]
    out = {}
    for col in ('data', 'listed'):
        out[col] = pd.DataFrame({g: [((v['grp'] == g) & (v[col] <= e)).sum() for e in ends] for g, _, _ in SERIES},
                                index=years)
    return out


def main(dst):
    d = counts()
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6), sharey=True)
    titles = {'data': '有数据的（可以排名）', 'listed': '已上市的（当年能买）'}
    for ax, key in zip(axes, ('data', 'listed')):
        t = d[key]
        bottom = pd.Series(0, index=t.index)
        for g, _, colr in SERIES:
            ax.bar(t.index, t[g], bottom=bottom, color=colr, width=.8, edgecolor='white', linewidth=.8, zorder=2)
            bottom = bottom + t[g]
        for y in (2006, 2015, 2026):
            ax.text(y, bottom[y] + 2, f'{bottom[y]}', ha='center', va='bottom', fontsize=11, weight='bold', color=INK)
        ax.axvline(2015.5, color=MUTED, lw=1, ls='--', zorder=1)
        ax.text(2015.3, 108, '设计期', ha='right', va='top', fontsize=10, color=MUTED)
        ax.text(2015.7, 108, '检验段', ha='left', va='top', fontsize=10, color=MUTED)
        ax.set_title(titles[key], loc='left', fontsize=12.5, weight='bold', color=INK, pad=8)
        ax.set_xticks([2006, 2010, 2015, 2020, 2026]); ax.set_xticklabels(['2006', '2010', '2015', '2020', '2026.9'])
        ax.set_ylim(0, 112); ax.grid(axis='x', visible=False)
    axes[0].set_ylabel('容器个数（年末）', color=MUTED)
    h = [plt.Rectangle((0, 0), 1, 1, color=c) for _, _, c in SERIES]
    fig.legend(h, [n for _, n, _ in SERIES], loc='lower center', ncol=5, frameon=False, bbox_to_anchor=(.5, -.06), fontsize=11)
    fig.tight_layout(rect=(0, .05, 1, 1))
    fig.savefig(dst, dpi=200, bbox_inches='tight', facecolor='white'); plt.close(fig)
    return d


if __name__ == '__main__':
    d = main(sys.argv[1])
    for k, t in d.items():
        print(k, t.sum(axis=1).loc[[2006, 2010, 2015, 2026]].to_dict())
