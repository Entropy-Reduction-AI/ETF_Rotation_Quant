# 第二阶段看板

群看板。按 `docs/manual/roadmap-and-naming.md` 的**版本 × 阶段 × 轮次**登记现在的位置。业务结论在 Owner 看板，不在这里重算。

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning
- Status: active
- Owner: L. Loric
- Maintainer: ETF Rotation Manager
- Date: 2026-10-29
- 权威顺序: `AGENTS.md` > 已冻结预注册 > 本看板 > 群聊
- 命名: `docs/manual/roadmap-and-naming.md`（D13-4）
- 决定: `operations/planning/2026-10-28-d13-owner-decisions.md`；D14：`operations/planning/2026-10-28-d14-owner-decisions.md`；D23：`operations/planning/2026-10-29-d23-v4-prereg-approval.md`
- v4 任务: `operations/planning/2026-10-28-v4-dev-plan.md`；v4-R5：`operations/planning/2026-10-29-v4-r5-plan.md`
- 设计期简报: `operations/reports/v4-r5-design-period-brief.md`
- Orchestrator 交接: `operations/planning/2026-10-29-v4-r5-orchestrator-handoff.md`
- 数据看板: `docs/owner/data-board.md`
- Owner 看板: `docs/owner/phase2-owner-board.md`（五段体检尚未改；由 Orchestrator 写）
- 收口主线: `cbd94df42c1016737fb2c078d8f83e78222eae03`（#123 签收 rebase-merge 之后的 `origin/main`）
- 旧流水: `operations/work_logs/2026-10-28-phase2-board-ledger.md`（main `9fd6f67` 上本文件的原文）

## 现在的位置

v3.1 已停在 **⑦ 代码冻结**。tag `milestone/v3-code-freeze` → `b1f84d899f4a37914c1ce4ef0ab16484f0ef7cdb`（附注标签对象 `f1d3d0c170ecbd5eb3b463c26834bafd5dc40254`）。R3 签收 `approve`：`operations/reviews/2026-10-27-v3.1-code-freeze-r3.md`（PR #56，已在 main）。⑧ 一次性检验未批准（D11-5）。D13 收口把复核正文、两份只在分支上的记录和本看板改写进 main；收口记录是 `operations/work_logs/2026-10-28-v3.1-closeout.md`。

v4 预注册已冻结：`milestone/v4-prereg-freeze` 指向 `6bcba53e36e74ec81dd21fb7ee7b8cea695038fb`（附注对象 `830320d03712df3a4098f352be8932e0553b5eeb`）。设计期运行在 #122（`09fe9add4ce806f07c88ec64693106df3ff72802`），过关与 §7.5 签收在 #123（`cbd94df42c1016737fb2c078d8f83e78222eae03`，Decision `approve`）。Manager 简报：`operations/reports/v4-r5-design-period-brief.md`。最终版 = E2 新口径 B0（T1–T4 没有一条同时通过三条规则）。面向 Owner 的五段还没写。D14 / v4-R1b 的收口原文在下方专节，日期仍是 2026-10-28。

| 版本 | ① 规则定稿 | ② 标的池 | ③ 交易引擎 | ④ 溢价控制 | ⑤ 打分卡 | ⑥ 业务体检 | ⑦ 代码冻结 | ⑧ 一次性检验 | ⑨ 结论 | ⑩ 模拟盘 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v3.1 | 完成 | 完成 | 完成 | 完成 | 完成 | 完成 | 完成 | 暂停 | — | — |
| v4 | 已冻结 | v4-R1、v4-R1b 已合入 | v4-R2 已合入 | v4-R2 已合入 | v4-R3 已合入 | v4-R5 进行中 | — | — | — | — |

状态只用这五个词：未开始 / 进行中 / 待评审 / 已合入 / 阻塞。

## 硬边界

- 设计期（end ≤ 2015-12-31）的 v4 运行已经在 main 上。本看板不重跑、不改规则。新的组合收益运行须另有授权。
- 不计算、不落盘 2016-01-01 及以后的组合收益。涉及收益的读数只用 ≤2015-12-31。
- 不写 `results/v3/LOCK`，也不写 `results/v4/LOCK`。模拟盘和真钱须 Owner 另作明确批准。一次性检验仍待研究封板（D20-4）。
- 不移动任何 tag。删除只按 Owner 的决定记录执行，并且先写入 `docs/manual/milestones.md`。`milestone/phase1-archive` 永不删除、不移动。`milestone/v4-prereg-freeze` 保持指向 `6bcba53`。不强推、不改写 main。
- 面向 Owner 的五段由 Orchestrator 写。本看板只登记进度和指针，不判定策略好坏。

## v4 轮次

任务正文在 `operations/planning/2026-10-28-v4-dev-plan.md`。下表只登记状态。

| 轮次 | 阶段 | 状态 | 依据 | 完成判据 |
| --- | --- | --- | --- | --- |
| v4-R1 | ② 标的池 | 已合入 | D13-1、D13-5。#65 取数，#66 抽查 `approve_with_follow_up`，#69 探索 | `results/v4/inventory/coverage.csv`；`data/market.sqlite` 的 SHA256；Reviewer 抽查。探索记录 `operations/work_logs/2026-10-28-v4-r1-data-exploration.md`。#66 的跟进留给 Orchestrator，本收口不新开任务 |
| v4-R1b | ② 标的池 | 已合入 | D14。#59 计划，#70 IC `numbers_ok`，#71 / #72 标签清理 `approve`，#73 取数，#74 抽查 `approve_with_follow_up`，#75 探索。主线 `3d5ce322899576c1dbb7d0e3d456b7c7c8eac1bd` | 见下方收口。取数后 `data/market.sqlite` SHA256 `af4c5a376d084cd6254187c1107c6179d0cfd9647c008bff84b4c26f52045b78` |
| v4-R2 | ③ 交易引擎、④ 溢价控制 | 已合入 | D12-1、D13-5。#67 实现，#68 `approve` | 成交限制、跨境成本、T1–T3 做成开关。开关全关时与 `milestone/v3-code-freeze` 的 v3.1 结果逐日一致 |
| v4-R3 | ⑤ 打分卡 | 已合入 | D13-2、D13-5。#63 实现，#60 `numbers_ok_with_notes`，#64 `approve` | 任意起点和四种市场状态工具，能复现已登记的 E2 参考数字；Reviewer 独立复算 |
| v4-R4 | ① 规则定稿 | 已合入 | D23-1。预注册第 2.3 版，`milestone/v4-prereg-freeze` → `6bcba53e36e74ec81dd21fb7ee7b8cea695038fb` | 索引：`docs/manual/milestones.md`；登记：`operations/work_logs/2026-10-29-v4-prereg-freeze-tag.md` |
| v4-R5 | ⑥ 业务体检 | 进行中 | D23-2。#122 设计期运行 `09fe9ad`；#123 签收 `approve`，`cbd94df`。过关：T1–T4 均未同时通过三条，最终版 = B0 | 简报 `operations/reports/v4-r5-design-period-brief.md` 已交。Owner 五段和 `milestone/v4-code-freeze` 还没做 |

v4 候选是 T1–T4（旧称 D1–D4）。决定编号仍是 D13、D14 这一类，不进路线图。R1c–R1f、R2b、R2c、R4b 的计划与签收仍在 `operations/planning/` 和 `operations/reviews/`，本表不另开一套轮次编号。

## v4-R5 设计期包（2026-10-29）

| 项 | 指针 |
| --- | --- |
| 简报 | `operations/reports/v4-r5-design-period-brief.md` |
| 签收 | `operations/reviews/2026-10-29-v4-r5-design-gate-signoff.md`（Decision `approve`） |
| 复算 JSON | `operations/reviews/diag/v4/v4-r5-gate-scorecard-recompute.json` |
| Dev 运行记录 | `operations/work_logs/2026-10-29-v4-r5-design-runs.md` |
| 过关表 | `results/v4/r5/candidate-gate.csv`（SHA256 `32058828326f5155ce9b9a678746d2f55d7a4a023b3d20a883e01676383c1b42`） |
| 交接 | `operations/planning/2026-10-29-v4-r5-orchestrator-handoff.md`（D22-2 冲突日 CSV；SF-5 原项已改） |
| 数据看板 | `docs/owner/data-board.md` 第 5 节。本看板不抄组合收益 |

账本 41 行。库指纹仍是 `1adb6d43…`。没有 `results/v4/LOCK`。没有 2016-01-01 及以后的组合收益汇总。标签未移动。

## D14 / v4-R1b 收口

下面这一节是 2026-10-28 的收口原文。当时的「下一闸门」已经过去：预注册已冻结，设计期已跑完并打包。现行位置以上面的表为准。

2026-10-28（Asia/Taipei）。主线 `3d5ce322899576c1dbb7d0e3d456b7c7c8eac1bd`。origin 上的标签只剩三个，对象 SHA 与清理前一致：`milestone/phase1-archive`、`milestone/v3.1-prereg-freeze` → `1040035ee1d707368b58687994894189753843ac`、`milestone/v3-code-freeze` → `b1f84d899f4a37914c1ce4ef0ab16484f0ef7cdb`。

| 事项 | PR | 结论 |
| --- | --- | --- |
| D14、数据原则、v4-R1b 计划、备忘第 6 版 | #59 | 已合入 |
| Orchestrator 17 指数 Rank IC 基线复算 | #70 | `numbers_ok`（0.093 / 0.028 / −0.004 / 0.049 / 0.069） |
| D14-2 里程碑索引与标签纪律；删除列出的 9 个标签 | #71 | 已合入。记录 `operations/work_logs/2026-10-28-tag-cleanup.md` |
| 标签清理独立核对 | #72 | `approve` |
| 场内后复权、场外指数基金、2005 汇率 | #73 | 已合入。写入后 SHA256 `af4c5a376d084cd6254187c1107c6179d0cfd9647c008bff84b4c26f52045b78` |
| 取数抽查 | #74 | `approve_with_follow_up` |
| Manager 探索（场外覆盖、后复权名额、新池 IC） | #75 | 已合入。记录 `operations/work_logs/2026-10-28-v4-r1b-exploration.md` |

五段：

- **本轮完成：** D14 / v4-R1b 在本看板关闭。取数、抽查、标签清理、IC 基线和新池探索都已在主线上。
- **能做什么不能做什么：** 能按设计期记录读覆盖、名额差和 Rank IC。不能把这些数字当成组合收益，不能跑 v4 候选，不能计算 2016-01-01 及以后的组合收益。
- **业务信号：** 不在这里重述，也不由 Manager 判定。正文在探索记录。
- **风险卡点：** 下面 8 条口径还没定。#74 另有一条已登记的 HSF 官方历史来源，同样留给 Orchestrator。
- **需要 Owner 的事：** 没有新的批准项。不把这 8 条送上 Owner 看板。

### 跟进（Orchestrator，不是 Owner 闸门）

这 8 条来自探索记录的「待 Orchestrator」。影响和备选以那份记录为准。本收口不把它们派给 Dev 或 Reviewer。

1. 跟踪差对的是全收益指数。000300、000905、000922 没有入库。
2. 161211 跟踪沪深300金融地产，该指数不在库里。2010–2014 年中证全指金融地产被记成「只有场外」。
3. 510880 跟踪上证红利，没有算作中证红利的场内 ETF。
4. 后复权名额表没有剔除没有后复权序列的名字。主表只替换了 10 只美股 ETF。
5. 124 只场内 ETF 没有后复权，没有用原始收盘补上。其中包括 159940、159944。
6. IC 没有把 35 只场外基金加成额外名字。
7. 港股仍是港币价格。美股仍用 2006-01-04 起的美元中间价，没有改用 v4 补上的 2005 年中间价。
8. 310318 的复权净值在 2008 年大波动日几乎不跟指数。年化跟踪差 22%，日相关 0.69。

#74 已登记的跟进：HSF 没有免费官方日线，官方历史来源留给 Orchestrator。抽查没有因此否决 #73。

### 下一闸门

等 Owner 或 Orchestrator 给出 v4-R4 之前的路径。给出之前：不新开 Dev 或 Reviewer 任务，不起草 v4 预注册，不打 `milestone/v4-prereg-freeze`，不运行 v4 候选看组合收益，不计算 2016-01-01 及以后的组合收益。

## v3.1 复核

代码冻结的签收是 R3。下面四份是冻结前的复核，D13 收口才进入 main。#49 的 `return` 保留，现行文本签收是 #53 的 `approve`。

| 文件 | 来源提交 | 结论 |
| --- | --- | --- |
| `operations/reviews/2026-10-27-v3.1-addendum-1-r1.md` | #49 `32db80312d279095ac38f4d79ed31f0b4c4509ca` | `return` |
| `operations/reviews/2026-10-27-v3.1-addendum-1-r1-rereview.md` | #53 `8be58f00be56089d716058a0905d1dc9c7d5c08d` | `approve` |
| `operations/reviews/2026-10-27-v3.1-d11-d1-d4-r2.md` | #51 `672aa127e68d8ed3a8504d53cf499c330dfa7970` | `approve_with_follow_up`（D3 当时 provisional） |
| `operations/reviews/2026-10-27-v3.1-d12-b1-b2-r2.md` | #55 `01c875e344a97f87a1bbb5f595dad2dd1bc1abd4` | `approve` |
| `operations/reviews/2026-10-27-v3.1-code-freeze-r3.md` | #56，合入前已在 main | `approve` |

#31 签收正文已入库：`operations/reviews/2026-10-25-v3-data-defensive-holiday.md`（`approve_with_follow_up`，所签是 #29 原分支 `c80aa568`）。机器可读核对在 `operations/reviews/diag/v3/2026-10-25-defensive-holiday-verify.json`。后来进入 main 的工程包签收仍是 PR #40，`operations/reviews/2026-10-25-v3.1-d10-post-freeze.md`。两份都留着，不互相取代。

设计期体检的推迟说明已入库：`operations/work_logs/2026-10-25-v3-design-period-brief-deferred.md`。正式设计期复跑和数字核对是后来的 PR #44、#45，记录在 `operations/work_logs/2026-10-25-v3.1-design-period-rerun.md` 与 `operations/reviews/2026-10-25-v3.1-design-period-report-check.md`。

## 里程碑

2026-10-28 收口时 origin 上的标签是下面三行。对象 SHA 与 D14-2 清理前一致，清理之后没有移动。2026-10-29 按 D23-1 新建了 `milestone/v4-prereg-freeze`。登记在 `docs/manual/milestones.md`。本简报包没有创建、移动或删除任何标签。

| 标签 | 标签对象 | 指向提交 | 含义 |
| --- | --- | --- | --- |
| `milestone/phase1-archive` | `4812115867d0e9176175bd45d21b2dae19c10979` | `0dd93fa13e0aa79b09ef16ba80676c022004be02` | 第一阶段封存。永不删除、不移动 |
| `milestone/v3.1-prereg-freeze` | `e3b55a7b8ce967a43341a3c9d02e6a0a42e2b508` | `1040035ee1d707368b58687994894189753843ac` | v3.1 ① 预注册冻结 |
| `milestone/v3-code-freeze` | `f1d3d0c170ecbd5eb3b463c26834bafd5dc40254` | `b1f84d899f4a37914c1ce4ef0ab16484f0ef7cdb` | v3.1 ⑦ 代码冻结 |
| `milestone/v4-prereg-freeze` | `830320d03712df3a4098f352be8932e0553b5eeb` | `6bcba53e36e74ec81dd21fb7ee7b8cea695038fb` | v4 ① 预注册冻结（D23-1，2026-10-29 新建） |

D14-2 删掉的 9 个仍登记在 `docs/manual/milestones.md`（清理前的 12 行）。执行记录是 `operations/work_logs/2026-10-28-tag-cleanup.md`，核对是 `operations/reviews/2026-10-28-v4-r1b-tag-cleanup-verify.md`（#72，`approve`）。

## 历史流水

2026-10-25 及以前的 L1–L5、G0–G5、D10 协调全文已从本文件移出，原样保存在 `operations/work_logs/2026-10-28-phase2-board-ledger.md`（来源提交 `9fd6f67be6d1c194d170b048fe3667367a0ac0fe`）。

相关工作记录：

- `operations/work_logs/2026-10-23-branch-cleanup.md`
- `operations/work_logs/2026-10-23-phase1-closeout.md`
- `operations/work_logs/2026-10-25-v3.1-d10-post-freeze.md`
- `operations/work_logs/2026-10-25-v3.1-design-period-rerun.md`
- `operations/work_logs/2026-10-27-branch-tag-cleanup.md`
- `operations/work_logs/2026-10-27-d11-d1-d4.md`
- `operations/work_logs/2026-10-27-d12-b1-b2-followups.md`
- `operations/work_logs/2026-10-28-v3.1-closeout.md`
- `operations/work_logs/2026-10-28-tag-cleanup.md`
- `operations/work_logs/2026-10-28-v4-r1-data-exploration.md`
- `operations/work_logs/2026-10-28-v4-r1b-ingest.md`
- `operations/work_logs/2026-10-28-v4-r1b-exploration.md`

## 最近更新

2026-10-29（Asia/Taipei），Manager。v4-R4 改为已冻结，v4-R5 改为进行中。设计期简报指向 `operations/reports/v4-r5-design-period-brief.md`，数据看板第 5 节加上 D22-2 指针。主线 `cbd94df42c1016737fb2c078d8f83e78222eae03`。不重跑，不改规则，不写 `results/v4/LOCK`，不写 2016 及以后的组合收益，不改 tag。Owner 五段留给 Orchestrator。

2026-10-28（Asia/Taipei），Manager，D14 / v4-R1b 收口。v4-R1、v4-R2、v4-R3、v4-R1b 改为已合入，主线 `3d5ce322899576c1dbb7d0e3d456b7c7c8eac1bd`。8 条口径跟进留给 Orchestrator，不送 Owner，不新开 Dev 或 Reviewer 任务。下一闸门是 v4-R4 之前的路径。不写组合收益，不写 `results/v3/LOCK`，不改 `src/`，不改 `data/`，不改 tag。
