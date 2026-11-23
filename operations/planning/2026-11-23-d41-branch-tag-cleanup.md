# D41 · 分支归档与清理、补打第二阶段归档标签（2026-11-23）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning（决定记录）
- Status: active（待 Manager、Cloud Agent 执行；执行结果写进工作记录）
- Owner: L. Loric
- Maintainer: Orchestrator（Claude）
- Date: 2026-11-23（Asia/Taipei）
- 授权：Owner 2026-11-23 在对话中明确要求“做一次 branch 和 tag 的 archive 和清理”，并对三项选择答复“1 删，2 同意，3A”
- 依据：`AGENTS.md`“tag 与分支纪律”“分支”两节；`docs/manual/roadmap-and-naming.md`（每个阶段结束打一个 `milestone/phase<N>-archive`；不再用 `keep/*`，PR 页面本身保留提交）；先例 `operations/work_logs/2026-11-16-branch-cleanup.md`、D14-2
- 清单：`operations/work_logs/2026-11-23-branch-cleanup-list.csv`（282 条，逐条写明原指向提交与理由）
- 执行记录：`operations/work_logs/2026-11-23-branch-cleanup.md`

---

## 决定

| 编号 | 决定 |
| --- | --- |
| D41-1 | **删除 279 条已经没有独立内容的远程分支**：275 条 PR 已合入（其中 248 条为 squash / rebase 合入，分支尖端等于合入时的 PR 尖端；3 条合入后又多的提交已由后续 PR 整体合入 main，逐个核对过）；3 条 PR 已关闭且内容已被取代（#335、#336、#300）；1 条没有 PR、补丁都已在 main（`cursor/d38-forecast-3.21-base-1e07`）。提交仍留在各自 PR 页面上，不丢证据 |
| D41-2 | **关闭 3 个过时的开着的 PR，并删除其分支**：#145（v5 预注册草案第 1 版，已被 main 上的 v5 预注册取代）、#165（v5 原版设计期结果，原版 2026-11-01 淘汰）——两者 2026-11-16 的记录已写“关闭不合入”，当时没有真正关闭；#338（v6 预注册初稿 R1 复核）挂在已关闭的分支上，两份 Reviewer 文件原样由 #350 补进 main，#350 合并后关闭 #338 并删除其分支 |
| D41-3 | **补打 `milestone/phase2-archive`**，附注标签，指向 `8875fe57e`（PR #294 合入后的 main，v6 预演 D38 的第一个 PR #295 之前）。第二阶段（v3 → v5.1，第 3 次尝试）2026-11-05 按 D36 关闭时漏打；这个点包含第二阶段收尾的全部工作：D35 场内口径重算、D36-2 换手深挖、D37 诊断各轮、Owner 页面改版。现有 9 个标签全部保留，不移动、不删除、不改写 |

不在本次范围：开着的 #312（Grok 第六轮，按 D40-8 另行收尾）、#339（v6 预注册，等冻结）、#346–#350（在用）。`main` 不改写。

## 执行顺序

1. 本决定与清单合入 main（删除之前先登记）。
2. Manager：合并 #350，关闭 #338、#145、#165（关闭，不合并）。
3. Manager：按清单逐条核对“远程分支当前指向 = 清单里的原提交”，相同才删；不同或已不存在的跳过并记下。`cursor/v6-prereg-r1-reviews-745d` 最后删。
4. Cloud Agent：按 Owner 指令在 `8875fe57e` 上新建附注标签 `milestone/phase2-archive`；新建前确认 origin 上没有同名标签；不动任何既有标签。
5. Manager：在 `docs/manual/milestones.md` 末尾补 `milestone/phase2-archive` 一节（标签对象 SHA、指向提交、附注、处置“保留”）；在执行记录里写删除结果、跳过的分支、`git ls-remote --heads origin` 与 `--tags origin` 的核对结果。
6. Reviewer：独立核对执行记录（删除的都在清单里、清单外没有误删、9 个既有标签的对象 SHA 不变、新标签指向 `8875fe57e`），结论放在 reviews-only PR。
