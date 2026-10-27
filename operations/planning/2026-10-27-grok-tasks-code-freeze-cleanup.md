# 给 bot 团队的任务：v3.1 代码冻结与项目清理（2026-10-27）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning（任务派发）
- Status: active
- Owner: L. Loric
- Maintainer: Orchestrator
- Date: 2026-10-27
- 依据：`operations/planning/2026-10-27-d11-owner-decisions.md`（D11-4、D11-5、D11-6）

下面整段可以直接复制给 Grok 群（Manager / Dev / Reviewer）。

---

```text
【任务】v3.1 代码冻结 + 项目清理（Owner 2026-10-27 授权，决定记录 D11）

先读：
1. operations/planning/2026-10-27-d11-owner-decisions.md（本次全部决定）
2. docs/prereg/etf-multiasset-rotation-prereg-v3.1-addendum-1.md（补充文本，待 Reviewer 核对）
3. 分支 claude/owner-board-v2 上的 PR（看板、UI/UX 规范、诊断记录）

授权范围：
- 批准：v3.1 代码冻结；分支清理；标签只做清点。
- 不批准：一次性检验（G3）。不写 results/v3/LOCK，不计算 2016-01-01 以后的任何组合收益。
- 纪律不变：不删除、不移动任何 tag；不强推、不改写 main；合入只用 --ff-only。

========== 第 1 部分：代码冻结前的 4 件事 ==========

【Dev】
D1 修“试过多少次”的计数
  目标：src/v3/eval/sharpe.py 的 trial_count() = ledger 中 v3 与 v3.1 配置行数 + 28 + 31（Orchestrator 诊断）。
  改动面：trial_count() 及其测试。31 写成具名常量，注明来源 D11-3。
  验证：现有 ledger（10 行）下返回 69；无 ledger 时返回 59。
  完成判据：Reviewer 签收。

D2 更新 6 个过时的测试
  目标：这 6 个测试原先假定“没有 ledger”或“trial_count()==28”；改成在临时目录里构造 ledger，不依赖仓库里的真实 ledger，也不删除真实 ledger。
  验证：在正式 ledger 存在的情况下，全量 unittest 0 失败。
  完成判据：Reviewer 签收。

D3 休市/停牌日离场卖单的边界测试
  目标：按 addendum-1 的 A1 补齐单测：计划卖出日无有效价 → 不成交、顺延到下一个有效价日；顺延期间遇常规调仓 → 常规调仓优先、清除挂单；连续 5 日无价 → 退出排名。
  改动面：只加测试；只有测试暴露的实现与 A1 不符时才改实现，并在工作记录里写明。
  完成判据：Reviewer 签收。

D4 记录涨跌停与 QDII 停牌（只统计，不改规则）
  目标：对设计期（≤2015-12-31）可交易池的每次买入和离场，标记计划成交日是否“收盘涨停（买）/收盘跌停（卖）/无价”。输出统计表到 results/v3/diag/。
  说明：已知 2015-06-29、2015-08-24 有离场卖出日收盘跌停。是否改成交假设，由 Owner 在 v4 研究里决定；本次只统计。

【Reviewer】
R1 核对 addendum-1（A1 闭合语义、A2 影子方案 C1、A3 计数 31），给出 approve / return。
R2 签收 D1–D3；确认全量测试 0 失败、数据指纹不变。
R3 代码冻结签收：全量测试 0 失败 + addendum-1 已合入 + D1–D3 已签收 → 给出冻结结论。

【Manager】
M1 合入顺序（全部 --ff-only，按序进行，每步先 rebase 到最新 main）：
  a. PR #44（设计期复跑）、PR #45（数字核对）
  b. 分支 claude/owner-board-v2（看板、UI/UX 规范、D11、addendum-1、诊断记录）——Reviewer approve 之后
  c. D1–D3 的开发分支
M2 Reviewer 给出冻结结论后，打附注标签 milestone/v3-code-freeze，指向 main 上的冻结提交；标签说明写：“v3.1 代码冻结（D11-4）；一次性检验未批准（D11-5）”。
M3 关闭被取代的 PR：#46（UI/UX 已并入 docs/reference/owner-facing-uiux-principles.md，D11-7）、#42（被新看板取代）。#29、#31：内容已随 #39 进入 main，确认后关闭。#1：确认是否仍需要，需要则单独评审，不需要则关闭。关闭时在 PR 里留言写明原因和取代它的位置。

========== 第 2 部分：项目清理 ==========

【Manager】
C1 分支清理（Owner 已授权删除“已合入或已被取代”的分支）
  先列清单，再删。每个分支写：名称、指向提交、是否已合入 main、对应 PR、处理方式。
  - 已合入 main 的 cursor/* 和 dev/*：删除。
  - 未合入但已被取代的（对应 PR 已关闭且内容另有去处）：先打 keep/<原分支名> 标签留档，再删除分支。
  - 有疑问的：不删，列入“待 Owner”。
  - claude/owner-board-v2：合入 main 之后删除。
  清单与执行结果写入 operations/work_logs/2026-10-27-branch-tag-cleanup.md。

C2 标签清点（只清点，不删除、不移动）
  列出全部标签：名称、类型（附注/轻量）、指向提交、该提交是否在 main 上、用途。
  已知现有：milestone/phase1-archive、milestone/v3-prereg-freeze、milestone/v3.1-prereg-freeze。
  如果认为有标签应删除或重命名，只写成“建议”，交 Owner 决定。

========== 完成后 ==========
Manager 在群里按固定五段汇报：本周完成 / 能做什么不能做什么 / 设计期业务信号 / 风险卡点 / 需要 Owner 的事。
需要 Owner 的事只列真正要他选的，每条写清：发生了什么、影响多大、选项和建议。
```
