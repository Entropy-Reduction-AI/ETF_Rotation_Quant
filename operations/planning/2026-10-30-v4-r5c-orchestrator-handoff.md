# v4-R5c · Orchestrator 交接

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R5c D25 签收之后的体检第 3 版交接
- Date: 2026-10-30
- Owner: L. Loric
- Route: direct-execute
- Source of truth: `operations/reviews/2026-10-30-v4-r5c-d25-signoff.md`；`operations/planning/2026-10-30-v4-r5c-plan.md`；`operations/reports/v4-r5-design-period-brief.md`

## Goal / Summary

D25 的两处程序修复和创业板指第 2 档入库已经做完，Reviewer Decision 是 `approve_with_follow_up`。设计期简报里两个池的数字都已换成 D25 重跑之后的读数。数据看板已按新库重跑。体检报告第 3 版用的数字和图在 `results/v4/diag/health/`。

下一步：Orchestrator 写体检报告第 3 版。体检之后，由 Manager 写面向 Owner 的五段汇报。`milestone/v4-code-freeze` 保持指向 `476abd7`，不移动。`milestone/v4-code-freeze-2` 等本收尾 PR rebase-merge 之后再打。本交接不改规则，不写 `results/v4/LOCK`，不移动标签，不含 2016-01-01 及以后的组合收益。

上一份交接 `operations/planning/2026-10-29-v4-r5b-orchestrator-handoff.md` 里的现行数字，以本文件和简报为准。

## 1. 已完成

| 项 | 指针 |
| --- | --- |
| 修复与重跑 | PR #132，rebase-merge `9c3e41c`（代码提交 `e3e0544`）。工作记录 `operations/work_logs/2026-10-30-v4-r5c-index-fill.md` |
| 签收 | PR #133，rebase-merge `dff13f20d817abd2461603d4fcd09ac42c598647`。`operations/reviews/2026-10-30-v4-r5c-d25-signoff.md` |
| 签收时的 Dev 尖端 | `02f2fc393517516868f001b6af129c8c6a6b9c89`（签收写明；合入后的重跑提交是 `9c3e41c`） |
| 简报 | `operations/reports/v4-r5-design-period-brief.md` |
| 数据看板 | `docs/owner/data-board.md`；`results/v4/diag/data-board/out/summary.json` |
| 体检输入 | `results/v4/diag/health/numbers.json`；`results/v4/diag/health/out/h1-nav.png` 至 `h5-robust.png` |

最终版仍是 **B0**。T1–T4 没有一条同时通过三条过关规则。

| 池 | 读数 | 窗口 |
| --- | --- | --- |
| B0 U-指数 | 全日历年化 **22.36%**；自 2006 **24.88%**；最大回撤 **−35.28%** | ≤2015-12-31 |
| B0 U-可交易 | 全日历年化 **9.97%**；自 2006 **10.87%**；最大回撤 **−31.70%** | ≤2015-12-31 |

`net_sha256`：U-指数 `77fc2f7bdeae577f6329924fa590a5813414a65d626b4c9cf393c16cc3015482`；U-可交易 `afd24150b7217488e5ac99f907fe33ebbe5c5f8a79b817c19cd71059697dd923`。`final` 与 `B0` 两个池的 `net.csv` 都逐字节相同。

相对诊断（约 24.6% / −35.3%）：自 2006 年化 **+0.28** 个百分点，最大回撤 **+0.02** 个百分点。都小于 0.5 个百分点。2008 年债券平均权重 8.41% + 7.90% = 16.31%。

A1 U-可交易 2006–2007：月末 24 次，20 次沪深300，4 次现金（2006-01、2006-02、2007-11、2007-12），0 次标普500。

## 2. 关键指纹

| 项 | 值 |
| --- | --- |
| `data/market.sqlite` | `550c1aee17a099dfc206876503ef436456bc5e87441db6947692abd3d6868c6c`（298,328,064 字节） |
| 过关表 `results/v4/r5/candidate-gate.csv` | `52fc1c9d653c27236df258cd0789ada7e4c4b27a842b2e82b004380bde445d74` |
| 账本 `results/v4/trial-ledger.csv` | 41 行；SHA256 `7a7620aa2cc34c207e3b32360a0f55f4246659945365e228c68c7847294b623d`；登记的 `git_sha` 都是 `c700ca095057baa524be01f6566d342c43976bea` |
| 修复标记 | `D25-1` ×20，`D25-3` ×17，`D25-2` ×2，`D24-1` ×2 |
| `results/v4/LOCK` | 不存在 |
| 标签 | 未移动。`milestone/v4-code-freeze` 仍指向 `476abd7cb63395506c6a9bb5fdad0f7b16827f66`。`milestone/v4-prereg-freeze` 仍指向 `6bcba53e36e74ec81dd21fb7ee7b8cea695038fb` |

设计期上界是 **2015-12-31**。

## 3. 数据看板（Reviewer follow-up）

已重跑 `results/v4/diag/data-board/build_data_board.py`。`summary.json` 的 `db_sha256` 现在是 `550c1aee…`，`generated` 是 2026-10-30。

`v4_series` 从 590,427 行增到 **593,480** 行。增加的 3,053 行是六只创业板指第 2 档的 `otc_nav`（050021 的 1099、110026 的 1016、161022 的 559、160637 的 139、001592 的 120、001593 的 120）。

年末容器个数和 `buy_by_year` 没有变：2015 年末仍是可排名 40、可买 30；2006 年可买仍是 10。脚本的可买日来自容器登记表里的上市或成立日，不读取只写进 `v4_listing` 的场外基金，也不套 3,000 万成交额。创业板指在登记表里的场内成员仍是 159915（2011-12-09），所以「最早能买到」仍显示 2011-12，不是 050021 的 2011-06-10。这六只没有变成新的容器，年末个数因此不加 1。执行层每年真正进排名的容器数以签收第 2 节为准。

## 4. 体检第 3 版怎么用这包数字

`health_numbers.py` 写出 `results/v4/diag/health/numbers.json`。`runs` 里的年化是自 2006、两位百分数；最大回撤是一位百分数。所以 B0 U-指数在这个文件里是 24.88 和 −35.3，简报里的最大回撤是 −35.28%。过关超额在这个文件里是一位小数（B0 U-指数 S1 为 19.6），签收和过关表是 19.59% / 0.1959。写报告时，两位百分数和 `net_sha256` 以简报和 `summary.json` 为准；这个 JSON 用来对逐年、年代和稳健性差。

`charts.py` 的四种行情拆分常量已改成简报里的 1 位小数。柱上的整数是这些 1 位小数再四舍五入，合计标签是两个分项相加后再取整。U-指数牛市 −24.6 + 22.7 = −1.9，简报合计格是 −1.8，图上的合计会显示成 −2。写报告时用简报表，图只作示意。

图的范围仍是设计期。`h1-nav.png` 的横轴画到 2016 是刻度，序列本身停在 2015-12-31。A1、A2 两个池都画了。可交易池上 A1 自 2006 年化 23.7%，高于同图里的 E2 新口径 10.9%。图题只描述 E2 新口径。

## 5. 仍然开着

### 5.1 D22-2 后复权冲突日

清单和分工仍见 `operations/planning/2026-10-29-v4-r5-orchestrator-handoff.md`。文件 `results/v4/inventory/r5/hfq-return-conflicts.csv`，SHA256 `eff7f0ea783cfc8a99bb217d850599b8be9924b41a6b965ff87c9365859a94a1`。本包没有改选用序列。

### 5.2 050002

D25-4 已核对：序列没有改。2015-12-29 不是除息日。约 1.7 个百分点的差在 2015-12-28，是单位净值百分比和累计净值百分比的分母不同。对照表 `results/v4/inventory/r5c/050002-exdiv.csv`。是否改源，D25 的决定是不改。

### 5.3 创业板指第 2 档

D25-3 已入库，U-指数哈希变化已按计划接受。看板容器个数不因此加 1，见第 3 节。

## 6. 留给体检的空格

这些空格沿用简报，不是新的研究任务：优劣对照的三句话；两个年代的累计超额、持仓市场权重、四个回看期 IC；2016–20 与 2021–26。两个池的四种行情、任意起点（含 A1、A2）和两个年代已经写进简报，数字只到 2015-12-31。

Owner 看板 `docs/owner/phase2-owner-board.md` 本包没有改。已发布的体检报告 `docs/owner/v4-health-check.md` 仍是第 2 版，本包不改那一页。

## Decision / Next Steps

1. Orchestrator 阅读简报、本交接和 `results/v4/diag/health/`，写体检报告第 3 版。
2. 体检之后，Manager 写五段汇报。
3. 本收尾 PR rebase-merge 之后，Manager 按 `docs/manual/milestones.md` 的 D25-5 打 `milestone/v4-code-freeze-2`，打在合入后的 `main` 上。不移动 `milestone/v4-code-freeze`。本文件不创建该标签。
