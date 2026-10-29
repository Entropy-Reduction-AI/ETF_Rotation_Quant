# v4-R5 · Orchestrator 交接（非阻塞）

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R5 设计期简报之后的开放项
- Date: 2026-10-29
- Owner: L. Loric
- Route: direct-execute
- Source of truth: `operations/reports/v4-r5-design-period-brief.md`；`operations/planning/2026-10-29-d22-canonical-hfq.md`；`operations/reviews/2026-10-29-v4-prereg-r1e.md`（R1f 的 SF-5）

## Goal / Summary

Manager 已把设计期数字写入 `operations/reports/v4-r5-design-period-brief.md`。下一步是 Orchestrator 写面向 Owner 的五段体检。下面只列仍然开着的非阻塞项。本交接不改规则，不重跑，不写 LOCK，不移动标签。

## 1. D22-2 后复权冲突日（开着，非阻塞）

清单：`results/v4/inventory/r5/hfq-return-conflicts.csv`

SHA256：`eff7f0ea783cfc8a99bb217d850599b8be9924b41a6b965ff87c9365859a94a1`

来源名册（无日收益）：`results/v4/inventory/r5/hfq-sources.csv`

统一入口已经按 D22-1 选用序列。160125、160644 走腾讯，还原没有被换上来。抽查签收记下 160125 有 14 个冲突日、160644 有 2 个。清单是单日价格差，不是组合收益。是否换源、是否登记例外，由 Orchestrator 定。Dev 工作记录还列出若干尚未展开日清单的双来源代码，抽查 follow-up 同样交给 Orchestrator，不阻塞这份设计期简报。

正文：`operations/work_logs/2026-10-29-v4-r5-d22-canonical-hfq.md`；抽查：`operations/reviews/2026-10-29-v4-r5-d22-hfq-spot.md`。

## 2. SF-5 Metadata L6（原项已改，本包不重开）

R1f 的 SF-5 是：预注册 Metadata 仍写「草案第 2 版」，与标题「第 2.3 版」不一致。

现行 `docs/prereg/etf-multiasset-rotation-prereg-v4.md` 的标题和状态行都是「第 2.3 版」，变更说明写「SF-5（本行状态）已改」。冻结提交 `6bcba53e36e74ec81dd21fb7ee7b8cea695038fb` 与当前 `main` 上的这份预注册正文没有差异。按这条定义，SF-5 不再开着。

`operations/planning/2026-10-28-d16-decisions.md` 和 `operations/planning/2026-10-28-v4-r4b-plan.md` 仍写「草案第 2 版」。那是 D16 / R4b 当时的计划原文，不是未关闭的 SF-5。本交接不改这两份历史计划。

状态行里还有一句「待 Owner 批准；尚未冻结」。D23 已经批准，标签 `milestone/v4-prereg-freeze` 指向 `6bcba53`。这句话留在冻结文本里。改预注册正文不在本包范围。Orchestrator 若要更正状态句，另开，并遵守冻结之后改规则 = v4.1。

## 3. 简报留给体检的空格

这些空格是因为签收没有给数字，不是新的研究任务：

- §7.5 优劣对照的三句话
- 2006–10、2011–15 的累计超额、持仓市场权重、四个回看期 IC
- 任意起点相对公开同行 A1 / A2
- 2016–20、2021–26 继续留空

Owner 看板 `docs/owner/phase2-owner-board.md` 本包没有改。五段体检由 Orchestrator 写。

## Decision / Next Steps

Orchestrator 阅读简报后写 Owner 五段。D22-2 的冲突日政策可以并行看，不挡住简报。代码冻结、LOCK、2016 及以后的组合收益，都不在这一步。
