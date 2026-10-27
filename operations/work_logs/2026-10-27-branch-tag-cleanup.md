# 分支与标签清理（D11 C1/C2）

## Metadata

- Project: ETF_Rotation_Quant
- Task: D11 C1 分支清理与 C2 标签清点
- Date: 2026-10-27
- Owner: project owner
- Route: direct-execute
- Source of truth: AGENTS.md「分支」；Owner 任务 C1/C2；`operations/planning/2026-10-27-grok-tasks-code-freeze-cleanup.md`。清理时 `origin/main` 为 `8bc35ef903effdd7e67fe94dddd200f2b9785330`。

## Goal / Summary

清点 origin 上的全部标签和分支。已合入 `main`、并且不是仍开着的复核 PR 基线的分支，直接删除。PR 已关闭、内容已有去处、提交本身不在 `main` 上的三支，先打附注标签 `keep/<原分支名>`，再删分支。有疑问的留在「待 Owner」。

既有标签没有删除，也没有移动。`main` 没有改写。没有强推。没有写 `results/v3/LOCK`。没有计算 2016-01-01 及以后的组合收益。本记录是文档提交，不合入动作不在本次。

合入判定：这批 PR 在 GitHub 上是 squash（合并提交只有一个父提交，分支尖端不是该父提交）。因此 `git merge-base --is-ancestor <分支尖端> origin/main` 对清理前的非 main 分支全部为否。一支算作已合入，需要同时满足：尖端 SHA 等于该 PR 记录的 head SHA，并且要么 `git merge-tree --write-tree origin/main <分支>` 的结果树与 `origin/main` 相同，要么 `git cherry origin/main <分支>` 显示该提交的补丁已经在 `main` 的历史上。尖端在 PR 合并之后没有再前进。

## C1 清理前清单

清理前 `git ls-remote --heads origin` 共 20 个分支（含 `main`）。

| 分支 | 尖端 | 已合入 main | 关联 PR | 处理 |
| --- | --- | --- | --- | --- |
| `main` | `8bc35ef903effdd7e67fe94dddd200f2b9785330` | 是（自身） | — | 保留 |
| `claude/agents-orchestrator-def` | `3a0a5178c0dfd7b0b04bd0c0391766297be5b186` | 是。#52 squash `8c7633086545`，merge-tree 结果与 main 相同 | [#52](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/52) MERGED | 已删除 |
| `claude/owner-board-v2` | `81db9fe9390977a4b9b4b8eecb4d60913d9230cd` | 是。#48 squash `3bf2d7ec58e8`，merge-tree 结果与 main 相同 | [#48](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/48) MERGED；仍是 [#49](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/49)、[#53](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/53) 的基线 | 待 Owner |
| `cursor/d10-design-period-prep-cb97` | `64c1baf8b6f04dcd4cc5648b3e6b0e619883ca7d` | 是。#41 squash `bbce6b553985`，`git cherry` 为已包含 | [#41](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/41) MERGED | 已删除 |
| `cursor/d11-d1-d4-freeze-prep-7d28` | `85fb8a6be8094940817689c12c00f501e615084c` | 是。#50 squash `52401ae0fc0e`，`git cherry` 为已包含 | [#50](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/50) MERGED；仍是 [#51](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/51) 的基线 | 待 Owner |
| `cursor/d12-b1-b2-followups-e4fb` | `b61632dc9a14483d3995abf62b5a683d65ba0aa8` | 是。#54 squash `b1f84d899f4a`，merge-tree 结果与 main 相同 | [#54](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/54) MERGED；仍是 [#55](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/55) 的基线 | 待 Owner |
| `cursor/owner-progress-boundary-audit` | `6cba1c77d4c9309df6a2b3375c8654cd1b6162fa` | 否。补丁不在 main | [#42](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/42) CLOSED。M3：由 #48 看板取代 | 先打 keep 标签，再删除 |
| `cursor/rename-tz-asia-taipei-2e4c` | `3b9eec9c995c73cc5df9477648c0a13b55812372` | 是。#47 squash `2efb85c754c2`，merge-tree 结果与 main 相同 | [#47](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/47) MERGED | 已删除 |
| `cursor/task-complete-owner-experience` | `cbc80ca069e26f6398cc2dc2df899228260963a6` | 否。三笔补丁不在 main | [#46](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/46) CLOSED。M3：UI/UX 已进入 `docs/reference/owner-facing-uiux-principles.md`（#48） | 先打 keep 标签，再删除 |
| `cursor/v3-data-defensive-holiday-review-5690` | `3ca5bb01f773ec338530e1d8eabb0a2b64233970` | 否。代码父提交的补丁在 main，签收文件不在 main | [#31](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/31) CLOSED | 待 Owner |
| `cursor/v3.1-design-period-report-check-014d` | `51fdf1695ff3ea008e1055d7df37965ad8a93f1c` | 是。#45 squash `f5d40124ad83`，merge-tree 结果与 main 相同 | [#45](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/45) MERGED | 已删除 |
| `cursor/v3.1-design-period-rerun-2361` | `c6cae2bd98522390b0f598596d2bde6059976a3a` | 是。#44 squash `3a9c6b599bc9`，merge-tree 结果与 main 相同 | [#44](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/44) MERGED | 已删除 |
| `cursor/v3.1-prereg-review-7a9f` | `fa825b7beccacda24004fdb52f48b3073fddf052` | 否。父提交 `a5bf56a` 的补丁在 main；退回评审文件不在 main | [#33](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/33) CLOSED，由 [#36](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/36) 取代 | 先打 keep 标签，再删除 |
| `dev/v3-data-defensive-holiday` | `c80aa56804c8927b762ada71b232c08a24b42fc5` | 是（补丁等价）。与 main 上的祖先 `dc75ca78698f30bb59e7adbbe5bce154e7b97392` patch-id 相同 | [#29](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/29) CLOSED。M3：内容已随 #39 进入 main | 已删除 |
| `dev/v3-design-period-brief` | `b945fbf3c9958ecdb7f1dea455fdf7346f733bc1` | 否。`operations/work_logs/2026-10-25-v3-design-period-brief-deferred.md` 不在 main | 无 PR | 待 Owner |
| `review/v3.1-addendum-1-r1` | `32db80312d279095ac38f4d79ed31f0b4c4509ca` | 否。评审文件不在 main | [#49](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/49) OPEN | 保留 |
| `review/v3.1-addendum-1-r1-rereview` | `8be58f00be56089d716058a0905d1dc9c7d5c08d` | 否。评审文件不在 main | [#53](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/53) OPEN | 保留 |
| `review/v3.1-code-freeze-r3` | `0da3e850fe95ccbac7a9fa07edf8767ab831d5da` | 是。#56 squash 即当前 main `8bc35ef903ef`，merge-tree 结果与 main 相同 | [#56](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/56) MERGED | 已删除 |
| `review/v3.1-d11-d1-d4-r2` | `672aa127e68d8ed3a8504d53cf499c330dfa7970` | 否。评审文件不在 main | [#51](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/51) OPEN | 保留 |
| `review/v3.1-d12-b1-b2-r2` | `01c875e344a97f87a1bbb5f595dad2dd1bc1abd4` | 否。评审文件不在 main | [#55](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/55) OPEN | 保留 |

PR #1（`cursor/python-venv-cloud-notes-1df1`）在本次清点开始前已经不在 origin 上。M3 已关闭该 PR。本次没有对应分支可删。

## 已删除的分支

十条。命令是普通删除，没有 `--force`：

```text
git push origin --delete claude/agents-orchestrator-def cursor/d10-design-period-prep-cb97 cursor/rename-tz-asia-taipei-2e4c cursor/v3.1-design-period-rerun-2361 cursor/v3.1-design-period-report-check-014d review/v3.1-code-freeze-r3 dev/v3-data-defensive-holiday cursor/owner-progress-boundary-audit cursor/task-complete-owner-experience cursor/v3.1-prereg-review-7a9f
```

| 分支 | 删除前尖端 | 理由 |
| --- | --- | --- |
| `claude/agents-orchestrator-def` | `3a0a5178c0dfd7b0b04bd0c0391766297be5b186` | #52 已 squash 合入 |
| `cursor/d10-design-period-prep-cb97` | `64c1baf8b6f04dcd4cc5648b3e6b0e619883ca7d` | #41 已 squash 合入 |
| `cursor/rename-tz-asia-taipei-2e4c` | `3b9eec9c995c73cc5df9477648c0a13b55812372` | #47 已 squash 合入 |
| `cursor/v3.1-design-period-rerun-2361` | `c6cae2bd98522390b0f598596d2bde6059976a3a` | #44 已 squash 合入 |
| `cursor/v3.1-design-period-report-check-014d` | `51fdf1695ff3ea008e1055d7df37965ad8a93f1c` | #45 已 squash 合入 |
| `review/v3.1-code-freeze-r3` | `0da3e850fe95ccbac7a9fa07edf8767ab831d5da` | #56 已 squash 合入，合并结果就是当前 main |
| `dev/v3-data-defensive-holiday` | `c80aa56804c8927b762ada71b232c08a24b42fc5` | 与 main 祖先 `dc75ca78698f30bb59e7adbbe5bce154e7b97392` 补丁相同；#29 已关闭 |
| `cursor/owner-progress-boundary-audit` | `6cba1c77d4c9309df6a2b3375c8654cd1b6162fa` | #42 已关闭，由 #48 取代；先有 keep 标签 |
| `cursor/task-complete-owner-experience` | `cbc80ca069e26f6398cc2dc2df899228260963a6` | #46 已关闭，UI/UX 正文在 #48；先有 keep 标签 |
| `cursor/v3.1-prereg-review-7a9f` | `fa825b7beccacda24004fdb52f48b3073fddf052` | #33 已关闭，由 #36 取代；先有 keep 标签 |

删除之后再次 `git ls-remote --heads origin`，上面十个名字已经不在。`main` 仍是 `8bc35ef903effdd7e67fe94dddd200f2b9785330`。#49、#51、#53、#55 仍是 OPEN。#52 与 #56 仍是 MERGED。

## 本次新建的 keep 标签

三个都是附注标签。先推送标签，确认 origin 上能解析到尖端提交，再删分支。没有 `--force`。

| 标签 | 标签对象 | 指向提交 | 该提交在 main 上 | 用途 |
| --- | --- | --- | --- | --- |
| `keep/cursor/owner-progress-boundary-audit` | `08b76ccddfe2636214c2986f1967088be64b8288` | `6cba1c77d4c9309df6a2b3375c8654cd1b6162fa` | 否 | #42 看板快照与核查记录。取代它的看板在 #48 |
| `keep/cursor/task-complete-owner-experience` | `65cd8b74149ff9b0a7645427ac9637420dd1e465` | `cbc80ca069e26f6398cc2dc2df899228260963a6` | 否 | #46 的任务闭环与图表材料。UI/UX 原则已在 `docs/reference/owner-facing-uiux-principles.md` |
| `keep/cursor/v3.1-prereg-review-7a9f` | `156aef4316e695ddd3a98278fe6b0e9f5a9f2469` | `fa825b7beccacda24004fdb52f48b3073fddf052` | 否 | #33 的 v3.1 预注册退回。复审文件在 main：`operations/reviews/2026-10-25-v3.1-prereg-rereview.md` |

`operations/planning/phase2-board.md` 仍用分支名引用 `fa825b7`。该提交现在由 `keep/cursor/v3.1-prereg-review-7a9f` 留住。

## 待 Owner

这些分支本次没有删除。

| 分支 | 尖端 | 原因 |
| --- | --- | --- |
| `claude/owner-board-v2` | `81db9fe9390977a4b9b4b8eecb4d60913d9230cd` | #48 的内容已在 main。它仍是 OPEN 的 #49、#53 的基线。删基线时 GitHub 会关掉仍指向该基线的开放 PR。#53 写明不取代 #49。两份复核文件都不在 main，所以这两支复核不算已过时 |
| `cursor/d11-d1-d4-freeze-prep-7d28` | `85fb8a6be8094940817689c12c00f501e615084c` | #50 已合入。它仍是 OPEN 的 #51 的基线。#51 的签收文件不在 main |
| `cursor/d12-b1-b2-followups-e4fb` | `b61632dc9a14483d3995abf62b5a683d65ba0aa8` | #54 已合入，尖端等于 #54 的 head。它仍是 OPEN 的 #55 的基线。#55 的签收文件不在 main。本次 fetch 时，本地跟踪引用从 `cc6aed9` 非快进更新到这个尖端；本次没有向该分支推送 |
| `review/v3.1-addendum-1-r1` | `32db80312d279095ac38f4d79ed31f0b4c4509ca` | #49 仍 OPEN |
| `review/v3.1-addendum-1-r1-rereview` | `8be58f00be56089d716058a0905d1dc9c7d5c08d` | #53 仍 OPEN |
| `review/v3.1-d11-d1-d4-r2` | `672aa127e68d8ed3a8504d53cf499c330dfa7970` | #51 仍 OPEN |
| `review/v3.1-d12-b1-b2-r2` | `01c875e344a97f87a1bbb5f595dad2dd1bc1abd4` | #55 仍 OPEN |
| `cursor/v3-data-defensive-holiday-review-5690` | `3ca5bb01f773ec338530e1d8eabb0a2b64233970` | #31 已关闭，所签代码补丁在 main 的 `dc75ca7`。签收正文 `operations/reviews/2026-10-25-v3-data-defensive-holiday.md` 与 `operations/reviews/diag/v3/2026-10-25-defensive-holiday-verify.*` 不在 main。看板仍引用这个 SHA。内容是否另有去处，本次不能当作已经成立 |
| `dev/v3-design-period-brief` | `b945fbf3c9958ecdb7f1dea455fdf7346f733bc1` | 没有 PR。推迟说明不在 main。缺少「已关闭的 PR 且内容另有去处」这一条，所以不打 keep、不删 |

若要删前三支已合入的基线，需要先把 #49、#51、#53、#55 改指向 `main`，或由 Owner 明确关闭。本次没有改这些 PR 的基线，也没有关闭它们。

## C2 标签清点

清理后 origin 上有 7 个标签，全部是附注标签，没有轻量标签。四个 `milestone/*` 的标签对象 SHA 与清理前的 `git ls-remote --tags origin` 一致。

### 清理前已有

| 标签 | 类型 | 标签对象 | 指向提交 | 该提交在 main 上 | 用途 |
| --- | --- | --- | --- | --- | --- |
| `milestone/phase1-archive` | 附注 | `4812115867d0e9176175bd45d21b2dae19c10979` | `0dd93fa13e0aa79b09ef16ba80676c022004be02` | 是 | Phase 1 archive: closeout + external reading notes (D9-7) |
| `milestone/v3-prereg-freeze` | 附注 | `007c9accf9be2c423564b7b885ea1961124b7f32` | `bfeb49cc65eb0ba419bc98348f1d643fac1211f6` | 是 | G1: prereg v3 frozen (Owner approved 2026-10-24) |
| `milestone/v3.1-prereg-freeze` | 附注 | `e3b55a7b8ce967a43341a3c9d02e6a0a42e2b508` | `1040035ee1d707368b58687994894189753843ac` | 是 | D10 v3.1 prereg freeze。说明里登记了复审 `approve_with_follow_up`，并写明当时没有 `results/v3/LOCK`、没有 `milestone/v3-code-freeze` |
| `milestone/v3-code-freeze` | 附注 | `f1d3d0c170ecbd5eb3b463c26834bafd5dc40254` | `b1f84d899f4a37914c1ce4ef0ab16484f0ef7cdb` | 是 | v3.1 代码冻结 D11-4；一次性检验未批准 D11-5 |

这四个指向的提交都是 `origin/main` 的祖先。本次不建议删除或重命名它们。

### 本次新建

见上一节三枚 `keep/*`。用途是留档已删分支的尖端，不是里程碑，也不移动任何旧标签。

## 建议（仅 Owner，本次未执行）

`operations/work_logs/2026-10-23-branch-cleanup.md` 记录当时新建过五个附注标签。本次 `git ls-remote --tags origin` 没有它们。下面五个提交都还在，并且都是当前 `main` 的祖先：

| 记录中的标签 | 记录中的提交 | 该提交在 main 上 |
| --- | --- | --- |
| `milestone/v1-code-freeze` | `cb8fe7b09253208fba157195c2fefbf3eb76d2b3` | 是 |
| `milestone/v1-r2-stop` | `ed1501cf2ec2eed6a025f39786fb83f1e432b491` | 是 |
| `milestone/v2-prereg-freeze` | `1ad86ac0150138b7284cca7566d421e63bf39032` | 是 |
| `milestone/v2-oos-result` | `36e53ce0cc0a35c9d99d7461d01b6107b3ed1279` | 是 |
| `milestone/core-portfolio-live-config` | `745ecedca4bfef5f5af881182c1fbcb9c5a32cac` | 是 |

建议 Owner 确认这五个名字是有意不在 origin 上，还是要按上表提交重新补打附注标签。本次不补打。

## Validation

- 清理前、推送 keep 标签后、删除分支后，各做一次 `git ls-remote --tags origin`。四个 `milestone/*` 标签对象分别为 `4812115867d0e9176175bd45d21b2dae19c10979`、`007c9accf9be2c423564b7b885ea1961124b7f32`、`e3b55a7b8ce967a43341a3c9d02e6a0a42e2b508`、`f1d3d0c170ecbd5eb3b463c26834bafd5dc40254`，三次一致。
- keep 标签在删除分支之前已经出现在 origin，剥开后的提交分别是 `6cba1c77d4c9309df6a2b3375c8654cd1b6162fa`、`cbc80ca069e26f6398cc2dc2df899228260963a6`、`fa825b7beccacda24004fdb52f48b3073fddf052`。
- 删除分支之后、推送本记录之前，head 列表是：`main`、`claude/owner-board-v2`、`cursor/d11-d1-d4-freeze-prep-7d28`、`cursor/d12-b1-b2-followups-e4fb`、`cursor/v3-data-defensive-holiday-review-5690`、`dev/v3-design-period-brief`、`review/v3.1-addendum-1-r1`、`review/v3.1-addendum-1-r1-rereview`、`review/v3.1-d11-d1-d4-r2`、`review/v3.1-d12-b1-b2-r2`。随后多出来的 `cursor/branch-tag-cleanup-33ff` 是本记录自己的分支，不在删除名单里。
- `gh pr list --state open` 仍是 #55、#53、#51、#49。
- 工作区没有改 `results/v3/LOCK`，没有跑 2016-01-01 及以后的组合收益。

## Decision / Next Steps

分支删除和 keep 标签已经在 origin 上。本文件是待合入的文档 PR，不合并。

需要 Owner 决定的只有两件：

1. #49、#51、#53、#55 要继续开着，还是改指向 `main` 之后再删 `claude/owner-board-v2`、`cursor/d11-d1-d4-freeze-prep-7d28`、`cursor/d12-b1-b2-followups-e4fb`。建议维持现状，直到这四份复核文件进 main。
2. #31 的签收正文，以及 `dev/v3-design-period-brief` 的推迟记录，是否打 `keep/` 后删分支。建议先留着：两处正文都还只在各自分支上。
