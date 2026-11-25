# Owner 页面（artifact）原始文件

## Metadata

- Project: ETF_Rotation_Quant
- Document type: index
- Status: active
- Owner: L. Loric
- Maintainer: Orchestrator
- Last updated: 2026-11-24（v6 预注册初稿第 2.2 版：附表 A、B，讲故事层）

## Purpose

这里存放面向 Owner 的 11 个 Claude artifact 页面的原始 HTML，每个页面一个文件夹，入口是 `index.html`。这些页面由 `docs/owner/*.md` 生成（v6 预注册由 `docs/prereg/etf-multiasset-rotation-prereg-v6.md` 生成）：内容以 md 为准，页面只负责版式。

本地直接用浏览器打开 `index.html` 就能看。图片引用的是仓库里的 `docs/assets/**`，没有另存副本。页面之间的跳转链接指向线上 artifact。

## 页面

| 页面 | 文件夹 | 源文档 | 线上 artifact |
| --- | --- | --- | --- |
| v6 预注册（已冻结） | `v6-prereg/` | `docs/prereg/etf-multiasset-rotation-prereg-v6.md` | https://claude.ai/artifact/VASWvP9wCzDvXmsQqzLFBh |
| v6 体检报告（设计期，骨架） | `v6-health/` | `docs/owner/v6-health-check.md` | https://claude.ai/artifact/NRgYVyimeFrzdhRetr48Fq |
| v6 预演预测表 | `v6-preflight/` | `docs/owner/v6-preflight-forecast.md` | https://claude.ai/artifact/4uzHh1NzeLVAEovbyLqqby |
| Owner 看板 | `board/` | `docs/owner/owner-board.md` | https://claude.ai/artifact/17bW2rKeeBheRFfhnjsrSU |
| 第二阶段复盘 | `retro/` | `docs/owner/phase2-retrospective.md` | https://claude.ai/artifact/B7ZyN3R4t8eic353W6ZV2t |
| 一次性检验报告 | `oneshot/` | `docs/owner/v5-oneshot-report.md` | https://claude.ai/artifact/9bm28gpZgkUjY47Gc1J9Kh |
| v5.1 体检报告 | `v51-health/` | `docs/owner/v5.1-health-check.md` | https://claude.ai/artifact/SApPN56B3cTtuJPbQK44vz |
| v5 研究备忘 | `v5-memo/` | `docs/owner/v5-research-memo.md` | https://claude.ai/artifact/3dhMbsA9Tna7CLsWPuaDwK |
| v4 体检报告 | `v4-health/` | `docs/owner/v4-health-check.md` | https://claude.ai/artifact/DpJNEma9D9uELPsLkWbRBx |
| v4 研究备忘 | `v4-memo/` | `docs/owner/v4-research-memo.md` | https://claude.ai/artifact/CgZds7DELqDLudyFjhSQDM |
| 数据与容器看板 | `data-board/` | `docs/owner/data-board.md` | https://claude.ai/artifact/RLaBJBbwPWysF7kR1dGqz4 |

## 新页面和改版的顺序（Owner 2026-11-17）

面向 Owner、需要长期保留的文档，一律先做成 artifact 页面，再同步到仓库：

1. 写或改 `docs/owner/*.md`，按上面的生成器出页面，过发布门，发布 artifact（新页面在 `scripts/owner_pages/build.py` 的 `PAGES`、`check2.py`、`audit.py` 里登记）。
2. 把 artifact 链接写进 `scripts/owner_pages/links.json` 和本页的表。
3. 用仓库模式重建，把这一页的 HTML 副本放进 `docs/artifact/<页面>/`，和 md 一起提交。以后每次改版都重复 1–3，三处保持一致。

## 怎么改

不要手改这里的 HTML，下次重建会被覆盖。要改的话分两种情况：

- **内容**：改 `docs/owner/*.md`。
- **版式**：改 `scripts/owner_pages/` 下的生成器（`build.py` → `story_layer.pre` → `polish.py` → `story.py` → `story_layer.post`，样式在 `base.css` 和各模块的 `CSS`）。
- **焦点**：每节的问、每个元素的看点、节尾接力写在 md 里（标记见 `docs/reference/owner-page-story-patterns.md` 第 2 版），不要写进生成器。

改完以后，在仓库根目录运行下面的命令重建页面，并过发布门：

```bash
# 重建仓库里的这份（图片指向 docs/assets）
OWNER_PAGE_REPO=1 python scripts/owner_pages/build.py . docs/artifact scripts/owner_pages/links.json
# 发布门
for f in docs/artifact/*/index.html; do python scripts/owner_page_lint.py "$f"; done   # 0 个 ERROR
python scripts/owner_pages/check2.py . docs/artifact      # 逐行核对内容
python scripts/owner_pages/audit.py docs/artifact         # 找没有视觉重点的表、卡片、段落
python scripts/owner_pages/story_check.py docs/artifact/v6-prereg/index.html --digest /tmp/连读稿.md   # 讲故事层：0 个 ERROR
PAGES_DIR=docs/artifact python scripts/owner_pages/el.py out.png 'board|.hero|0'   # 元素截图
```

发布 artifact 时，不设 `OWNER_PAGE_REPO`，并把输出目录换成一个临时目录。这样图片会复制到每个页面的 `assets/` 里，再用 `index.html` + `assets/` 发布。规范见 `docs/reference/owner-facing-uiux-principles.md`，执行清单见 `.pi/skills/owner-page-uiux/SKILL.md`。
