"""Owner 看板第 1 节的 v6 进度总览（版本 × 阶段，样式同第二阶段的 b0-roadmap.png）。
用法：python scripts/owner_pages/roadmap_v6.py docs/assets/owner-board/b10-v6-roadmap.png
状态文字照抄看板与预注册；阶段名称见 docs/manual/roadmap-and-naming.md。改状态时改下面的 CELLS 再重画。
"""
import sys
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

plt.rcParams.update({'font.family': ['Noto Sans CJK SC'], 'axes.unicode_minus': False})
INK, MUTED = '#151b26', '#5d6676'
STY = {  # 边框、底色、标题色
    'done': ('#16a34a', '#effaf2', '#15803d'), 'doing': ('#d97706', '#fff7ed', '#b45309'),
    'you': ('#7c3aed', '#f5f3ff', '#6d28d9'), 'todo': ('#d6d9df', '#f3f4f6', MUTED),
    'fail': ('#c2410c', '#fff1e8', '#c2410c')}
COLS = ['预演（D38）', '① 规则定稿', '② 标的池', '③ 交易引擎', '④ 溢价控制', '⑤ 打分卡', '⑥ 业务体检', '⑦ 代码冻结', '⑧ 一次性检验', '⑨ 结论', '⑩ 模拟盘']
CELLS = [
    ('done', '✓ 跑完', '登记 56 行；预测表\n3.22 版，每年 +1.2'),
    ('done', '已冻结', '11-25 打标签\nf066da8e'),
    ('done', '✓ 已定', '美股 15 个；A 股 40\n个参选（附表 A）'),
    ('done', '✓ 对上', '两条线独立实现，\n14 项里 12 项差 0'),
    ('done', '规则已定', '溢价比常态高 5 点\n换一只（§2）'),
    ('done', '判据已定', '四条判据 + 同仓位\n基准（§5）'),
    ('done', '第 1.5 版', '随机对照、急跌\n仓位都已补齐'),
    ('done', '✓ 已合入', '#375、#377\n11-26 合入'),
    ('done', '✓ 跑了一次', '#399；Reviewer\n独立复算一致'),
    ('fail', '不通过', '③④ 不过；比同仓\n位每年少 2.5 点'),
    ('todo', '不进', '按冻结稿关闭\nv6'),
]
out = sys.argv[1]
# 两行排：预演 + ①–⑤ 一行，⑥–⑩ 一行；页面主栏约 920px，单行 11 格字太小
W, H = 14.3, 7.1
fig = plt.figure(figsize=(W, H)); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis('off')
ax.text(0.25, H - 0.42, '进度总览：v6 × 阶段', fontsize=21, weight='bold', color=INK, va='center')
lx = W - 6.3
for k, lab in [('done', '完成'), ('fail', '不通过'), ('you', '需要你'), ('todo', '未开始')]:
    e, f, _ = STY[k]
    ax.add_patch(FancyBboxPatch((lx, H - 0.53), 0.22, 0.22, boxstyle='round,pad=0,rounding_size=0.03', ec=e, fc=f, lw=1.6))
    ax.text(lx + 0.32, H - 0.42, lab, fontsize=13.5, color=MUTED, va='center'); lx += 1.55
x0, cw, gap, ch = 1.85, 1.98, 0.06, 2.05
rows = [(H - 1.35, range(0, 6)), (H - 1.35 - ch - 0.75, range(6, 11))]
ax.add_patch(FancyBboxPatch((0.25, rows[1][0] - ch), 1.45, rows[0][0] - rows[1][0] + ch, boxstyle='round,pad=0,rounding_size=0.08', fc=INK, ec=INK))
ax.text(0.42, rows[0][0] - 0.4, 'v6', fontsize=28, weight='bold', color='white', va='center', family='DejaVu Sans Mono')
ax.text(0.42, rows[0][0] - 0.95, '第 4 次尝试\n\n两个名额\n每个选前 3\n\n按把握防守', fontsize=13, color='#d1d5db', va='top', linespacing=1.5)
for top, idx in rows:
    for j, i in enumerate(idx):
        name, (k, head, body) = COLS[i], CELLS[i]
        x = x0 + j * (cw + gap)
        ax.text(x + cw / 2, top + 0.3, name, fontsize=14.5, weight='bold', color=INK, ha='center', va='center')
        e, f, hc = STY[k]
        ax.add_patch(FancyBboxPatch((x, top - ch), cw, ch, boxstyle='round,pad=0,rounding_size=0.08', ec=e, fc=f, lw=2.4 if k != 'todo' else 1.2))
        ax.text(x + 0.14, top - 0.36, head, fontsize=15, weight='bold', color=hc, va='center')
        ax.text(x + 0.14, top - 0.74, body, fontsize=13, color=INK if k != 'todo' else MUTED, va='top', linespacing=1.55)
ax.text(0.25, 0.33, '“预演”是 D38 先算后做加的一步，在 ① 之前；②–⑤ 可以在 ① 冻结前并行准备，但不能看收益。\n第二阶段（v3.1 → v5.1）的进度总览见第 2 节留档。',
        fontsize=12, color=MUTED, va='center', linespacing=1.5)
fig.savefig(out, dpi=130)
