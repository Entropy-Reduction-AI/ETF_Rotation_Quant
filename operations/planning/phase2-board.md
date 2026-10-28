# 第二阶段看板

群看板。按 `docs/manual/roadmap-and-naming.md` 的**版本 × 阶段 × 轮次**登记现在的位置。业务结论在 Owner 看板，不在这里重算。

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning
- Status: active
- Owner: L. Loric
- Maintainer: ETF Rotation Manager
- Date: 2026-10-28
- 权威顺序: `AGENTS.md` > 已冻结预注册 > 本看板 > 群聊
- 命名: `docs/manual/roadmap-and-naming.md`（D13-4）
- 决定: `operations/planning/2026-10-28-d13-owner-decisions.md`
- v4 任务: `operations/planning/2026-10-28-v4-dev-plan.md`
- Owner 看板: `docs/owner/phase2-owner-board.md`
- 旧流水: `operations/work_logs/2026-10-28-phase2-board-ledger.md`（main `9fd6f67` 上本文件的原文）

## 现在的位置

v3.1 已停在 **⑦ 代码冻结**。tag `milestone/v3-code-freeze` → `b1f84d899f4a37914c1ce4ef0ab16484f0ef7cdb`（附注标签对象 `f1d3d0c170ecbd5eb3b463c26834bafd5dc40254`）。R3 签收 `approve`：`operations/reviews/2026-10-27-v3.1-code-freeze-r3.md`（PR #56，已在 main）。⑧ 一次性检验未批准（D11-5）。D13 收口把复核正文、两份只在分支上的记录和本看板改写进 main；收口记录是 `operations/work_logs/2026-10-28-v3.1-closeout.md`。

v4 进入开发。v4-R1、v4-R2、v4-R3 已授权，可以并行，目前都还没有开工分支。预注册（v4-R4）冻结之前不运行任何 v4 候选看收益。

| 版本 | ① 规则定稿 | ② 标的池 | ③ 交易引擎 | ④ 溢价控制 | ⑤ 打分卡 | ⑥ 业务体检 | ⑦ 代码冻结 | ⑧ 一次性检验 | ⑨ 结论 | ⑩ 模拟盘 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v3.1 | 完成 | 完成 | 完成 | 完成 | 完成 | 完成 | 完成 | 暂停 | — | — |
| v4 | v4-R4 未开始 | v4-R1 未开始 | v4-R2 未开始 | v4-R2 未开始 | v4-R3 未开始 | v4-R5 未开始 | — | — | — | — |

状态只用这五个词：未开始 / 进行中 / 待评审 / 已合入 / 阻塞。

## 硬边界

- 不运行任何 v4 候选规则来看组合收益。v4-R4 冻结前只做数据、代码和工具。
- 不计算、不落盘 2016-01-01 及以后的组合收益。涉及收益的探索统计只用 ≤2015-12-31。
- 不写 `results/v3/LOCK`。模拟盘和真钱须 Owner 另作明确批准。
- 不删除、不移动已有 tag。不强推、不改写 main。合入用 `--ff-only` 或 squash。
- 汇报五段：本轮完成 / 能做什么不能做什么 / 业务信号 / 风险卡点 / 需要 Owner 的事。

## v4 轮次

任务正文在 `operations/planning/2026-10-28-v4-dev-plan.md`。下表只登记状态。

| 轮次 | 阶段 | 状态 | 依据 | 完成判据 |
| --- | --- | --- | --- | --- |
| v4-R1 | ② 标的池 | 未开始 | D13-1、D13-5 | `results/v4/inventory/coverage.csv`；`data/market.sqlite` 的 SHA256；Reviewer 抽查。探索记录 `operations/work_logs/2026-10-28-v4-r1-data-exploration.md` |
| v4-R2 | ③ 交易引擎、④ 溢价控制 | 未开始 | D12-1、D13-5 | 成交限制、跨境成本、T1–T3 做成开关。开关全关时与 `milestone/v3-code-freeze` 的 v3.1 结果逐日一致 |
| v4-R3 | ⑤ 打分卡 | 未开始 | D13-2、D13-5 | 任意起点和四种市场状态工具，能复现已登记的 E2 参考数字；Reviewer 独立复算 |
| v4-R4 | ① 规则定稿 | 未开始 | D13-2、D13-5 | v4 预注册写完、复核通过、Owner 批准，再打 `milestone/v4-prereg-freeze`。等 R1 的覆盖表 |
| v4-R5 | ⑥ 业务体检 | 未开始 | D13-5 | 预注册冻结后，设计期 end≤2015-12-31 的体检报告。等 R1–R4 |

v4 候选是 T1–T4（旧称 D1–D4）。决定编号仍是 D13 这一类，不进路线图。

## v3.1 复核

代码冻结的签收是 R3。下面四份是冻结前的复核，本收口才进入 main。#49 的 `return` 保留，现行文本签收是 #53 的 `approve`。

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

| 标签 | 指向提交 | 含义 |
| --- | --- | --- |
| `milestone/v3-code-freeze` | `b1f84d899f4a37914c1ce4ef0ab16484f0ef7cdb` | v3.1 ⑦ 代码冻结 |
| `milestone/v3.1-prereg-freeze` | `1040035ee1d707368b58687994894189753843ac` | v3.1 ① 预注册冻结 |
| `milestone/v3-prereg-freeze` | `bfeb49cc65eb0ba419bc98348f1d643fac1211f6` | v3 ① 预注册冻结 |
| `milestone/phase1-archive` | `0dd93fa13e0aa79b09ef16ba80676c022004be02` | 第一阶段封存 |
| `milestone/v1-code-freeze` | `cb8fe7b09253208fba157195c2fefbf3eb76d2b3` | 2026-10-23 清理记录中的 V1 代码冻结，D13 补打 |
| `milestone/v1-r2-stop` | `ed1501cf2ec2eed6a025f39786fb83f1e432b491` | V1 STOP，D13 补打 |
| `milestone/v2-prereg-freeze` | `1ad86ac0150138b7284cca7566d421e63bf39032` | v2 预注册冻结，D13 补打 |
| `milestone/v2-oos-result` | `36e53ce0cc0a35c9d99d7461d01b6107b3ed1279` | v2 样本外产物，D13 补打 |
| `milestone/core-portfolio-live-config` | `745ecedca4bfef5f5af881182c1fbcb9c5a32cac` | D7 之后的生产配置，D13 补打 |

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

## 最近更新

2026-10-28（Asia/Taipei），Manager，D13 收口。现行看板改为版本 × 阶段 × 轮次。v3.1 停在 ⑦。v4-R1 至 v4-R3 未开始、已可并行。不写组合收益，不写 `results/v3/LOCK`，不改预注册，不改业务代码。
