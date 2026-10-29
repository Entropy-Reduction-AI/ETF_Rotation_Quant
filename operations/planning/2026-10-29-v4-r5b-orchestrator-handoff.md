# v4-R5b · Orchestrator 交接

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R5b D24 签收之后的开放项与体检交接
- Date: 2026-10-29
- Owner: L. Loric
- Route: direct-execute
- Source of truth: `operations/reviews/2026-10-29-v4-r5b-tradable-signoff.md`；`operations/planning/2026-10-29-v4-r5b-plan.md`；`operations/reports/v4-r5-design-period-brief.md`

## Goal / Summary

D24 U-可交易修复已经做完，Reviewer Decision 是 `approve_with_follow_up`。设计期简报里的 U-可交易数字已换成修复之后的读数，U-指数数字保持不动。数据看板已按新库重跑。

下一步：Orchestrator 做体检。体检之后，由 Manager 写面向 Owner 的五段汇报。`milestone/v4-code-freeze` 在里程碑索引里只是草案；Manager 在本收尾 PR rebase-merge 之后再打标签。本交接不改规则，不写 `results/v4/LOCK`，不移动标签，不含 2016-01-01 及以后的组合收益。

上一份交接 `operations/planning/2026-10-29-v4-r5-orchestrator-handoff.md` 里「Orchestrator 写五段」的分工，以本文件为准。

## 1. 已完成

| 项 | 指针 |
| --- | --- |
| 修复 | PR #126，rebase-merge `82f97453`。工作记录 `operations/work_logs/2026-10-29-v4-r5b-tradable-fix.md` |
| 签收 | PR #127，rebase-merge `4a541df328361e967dcc87acb2b01892f4fcaae9`。`operations/reviews/2026-10-29-v4-r5b-tradable-signoff.md` |
| 签收时的 Dev 尖端 | `b92d9eacd9805b92fff29578ebd7192584ef5e20`（签收写明；合入后的 main 是 `82f97453`） |
| 简报 | `operations/reports/v4-r5-design-period-brief.md`（同一文件增加 R5b / D24） |
| 数据看板 | `docs/owner/data-board.md`；`results/v4/diag/data-board/out/summary.json` |

B0 U-可交易（全日历，2005-01-04 → 2015-12-31）：年化 **9.62%**，最大回撤 **−31.70%**。`net_sha256` `c49e507d357de0433417a416aaf74bb895ce40d774fcfae73f18e29b7e4331f2`。Reviewer 复算与 Dev 公布一致。

## 2. 关键指纹

| 项 | 值 |
| --- | --- |
| `data/market.sqlite` | `79ae5a47e1a6eb0977a18f13efb21211d24b48e393ad567f615130d89c8f00cd`（297,672,704 字节）。相对 D22 的 `1adb6d43…` 只增加了场外插入 |
| 过关表 `results/v4/r5/candidate-gate.csv` | `32058828326f5155ce9b9a678746d2f55d7a4a023b3d20a883e01676383c1b42` |
| U-指数 B0 / final `net_sha256` | `6f92c0388825e210623400e9743ff6672f244b143f0d6b4b3f56223bd4eeb87f`。签收：20 条 U-指数 `net_sha256` 相对 v4-R5 设计期基线逐条不变 |
| 账本 `results/v4/trial-ledger.csv` | 41 行；SHA256 `63e54caf8b12ac678b1f3bc608f1178967806a1789426b78bf3d45aa41f710dc`；21 行含 `fix: D24-1` |
| 最终版 | 仍是 B0。T1–T4 没有一条同时通过三条过关规则 |
| `results/v4/LOCK` | 不存在 |
| 标签 | 未移动。`milestone/v4-code-freeze` 未创建，见 `docs/manual/milestones.md` 草案 |

设计期上界是 **2015-12-31**。

## 3. 仍然开着（Orchestrator 裁定，本交接不决定）

### 3.1 创业板指第 2 档联接

Dev 没有插入 050021、110026、161022。Reviewer 确认这三只不在 `v4_listing` 里，因此 U-指数净值哈希没有因为这次 defer 而改变。

若把它们当作第 2 档并写入研究序列，U-指数日收益会变。是否接受这件事，由 Orchestrator 定。Manager 不选。

### 3.2 050002：pingzhong 连乘与 lsjz 累计净值

050002（博时沪深300）是 D22 之前就有的基金，不是 D24 新插入。Reviewer 用 `api.fund.eastmoney.com/f10/lsjz` 的累计净值日收益对照库内 `otc_nav`：2015-12-29 单日绝对差约 **1.7 个百分点**。其余抽查的四只在更小的量级。签收把它记成预存路径差异，不视为 D24 回归。是否改源、是否只作登记说明，由 Orchestrator 定。

### 3.3 D22-2 后复权冲突日（仍开着）

清单和分工仍见 `operations/planning/2026-10-29-v4-r5-orchestrator-handoff.md` 第 1 节。文件 `results/v4/inventory/r5/hfq-return-conflicts.csv`，SHA256 `eff7f0ea783cfc8a99bb217d850599b8be9924b41a6b965ff87c9365859a94a1`。本包没有改选用序列。

### 3.4 数据看板的「能买到」

重跑之后，年末可排名 / 可买个数与 D22 那版相同（2015 年末 40 / 30）。脚本的可买日来自容器登记表里的上市或成立日，不读取这次只写入 `v4_listing` 的场外基金，也不套 3,000 万成交额。变的是库指纹和 `v4_series` 行数（565,739 → 590,427）。执行层每年真正进排名的容器数以签收第 2 节为准，比看板可买个数少。

## 4. 留给体检的空格

这些空格沿用 R5 简报，不是新的研究任务：优劣对照的三句话；两个年代的累计超额、持仓市场权重、四个回看期 IC；2016–20 与 2021–26。U-可交易 B0 的四种行情、任意起点（含 A1、A2）和两个年代已经写进简报，数字只到 2015-12-31。

Owner 看板 `docs/owner/phase2-owner-board.md` 本包没有改。

## Decision / Next Steps

1. Orchestrator 阅读简报和本交接，做体检。
2. 体检之后，Manager 写五段汇报。
3. 本收尾 PR rebase-merge 之后，Manager 按 `docs/manual/milestones.md` 的草案打 `milestone/v4-code-freeze`，打在合入后的 `main` 上。本文件不创建该标签。
4. 创业板指联接和 050002 源路径仍等 Orchestrator，不挡上面两步的阅读；若裁定要改库或改 U-指数，另开一轮，并接受哈希变化。
