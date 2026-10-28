# D16-8 · 延长后复权尾部 42 行归类 · spot-check · 2026-10-28

## Decision：`approve_with_follow_up`

在 Manager PR [#90](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/90) 尖端 `c2db9a21cb47de1eb5b44d4ad26ebc61666ae881`（base `3780e28c3729bf925d08ad18afe81c01f1191a23`）上独立复核：**42 行留空→可以接受**、代码计数、合计与 Orchestrator 15 均与声明一致；**42/42** 与同代码同区间 raw 可以接受行成对，且区间均在 pre-extend 腾讯 hfq 末日之后。**未发现分类逻辑阻塞缺陷**。Follow-up：PR diff **误删** `operations/reviews/2026-10-28-v4-prereg-r1b.md`（与 D16-8 无关），合入前须恢复该 review artifact。

## Metadata

- Project: ETF_Rotation_Quant
- Task: D16-8 / v4-R1d Manager 42 行 hfq 尾部 accept 归类 spot-check
- Date: 2026-10-28 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（本 PR 仅 `operations/reviews/**`）
- 签收对象（Manager）: PR #90 · head `c2db9a21cb47de1eb5b44d4ad26ebc61666ae881`
- Manager work log: `operations/work_logs/2026-10-28-d16-8-hfq-tail-classify.md`
- Review branch: `review/d16-8-spotcheck`（基于 Manager tip，仅追加评审产物）

## 证据总表

| 检查项 | 方法 | 结论 |
| --- | --- | --- |
| PR diff 范围 | `git diff 3780e28..c2db9a2 --name-only` | **5** 文件；**无** `src/`、`data/`、`docs/prereg/**` |
| 意外 diff | 同上 | **删** `operations/reviews/2026-10-28-v4-prereg-r1b.md`（**非** D16-8 声明范围） |
| `integrity-findings.csv` 行数 | base vs head 逐行 diff | **2419** 行；**仅 42 行** `manager_class` 变化 |
| blank→可以接受 | 程序化对比 | **42**；无其它 `manager_class` 迁移 |
| 代码 × 行数 | 42 行子集 | **160125×35**、**161831×1**、**164705×6** |
| 检查/序列 | 42 行子集 | 全部 `missing_trade_days` · `backward` · `source=tencent_etf_hfq` |
| 合计 | head 直方图 | 必须修 **0** / 可以接受 **2404** / 需要 Orchestrator **15** / 留空 **0** = **2419** |
| Orchestrator 15 | `(code, series_kind, check, date, end_date)` vs base | **完全一致** |
| must_fix / 错翻 accept | base→head | must_fix **0**；无原 must_fix 或 Orchestrator 行改为可以接受 |
| raw 成对 | 42 行 `(code, check, date, end_date)` | **42/42** 存在同键 raw 且 `manager_class=可以接受` |
| hfq handoff 后 | `date` vs 腾讯末日 | **42/42** 严格晚于 160125→2019-07-03、161831→2020-12-31、164705→2020-11-30 |
| missing_trade_days accept 对偶 | head 计数 | raw **1151** / backward **1151** |
| v4 候选 PnL / 2016+ 组合收益 | 硬规则 | **未**运行 |
| LOCK / tag / 合 main | Reviewer 纪律 | **未**改 LOCK、**未**动 tag、**未**合 main |

## 1. Diff 完整性（Checklist §1）

相对 base `3780e28` 变更文件：

| 路径 | 与 D16-8 声明关系 |
| --- | --- |
| `results/v4/inventory/integrity-findings.csv` | **是**（42 行 `manager_class`） |
| `operations/work_logs/2026-10-28-d16-8-hfq-tail-classify.md` | **是**（新增） |
| `operations/work_logs/2026-10-28-d15-9-classification-summary.md` | **是**（当前合计更新） |
| `operations/work_logs/2026-10-28-d15-9-integrity-classify.md` | **是**（指针更新） |
| `operations/reviews/2026-10-28-v4-prereg-r1b.md` | **否**（整文件删除，140 行） |

CSV 除 `manager_class` 外 **零**列变化、**零**行增删。

## 2. 计数与合计（Checklist §2–§4）

**Base**（填之前）：必须修 0 / 可以接受 2362 / 需要 Orchestrator 15 / 留空 42 = 2419。

**Head**（Manager 填之后）：必须修 0 / 可以接受 2404 / 需要 Orchestrator 15 / 留空 0 = 2419。

**manager_class` 迁移**：仅 `{留空 → 可以接受}` ×42。

**Check × manager_class**（head，与 Manager 工作日志交叉表一致）：

| check | 必须修 | 可以接受 | 需要 Orchestrator | 留空 |
| --- | ---: | ---: | ---: | ---: |
| missing_trade_days | 0 | 2302 | 8 | 0 |
| list_date_unknown | 0 | 62 | 5 | 0 |
| large_move_hfq_smoothed | 0 | 38 | 0 | 0 |
| ended_before_cutoff | 0 | 0 | 2 | 0 |
| large_move | 0 | 2 | 0 | 0 |

## 3. Spot sample（Checklist §5，12 行）

| code | date | end_date | backward source | raw 同键 accept | date > hfq 末日 |
| --- | --- | --- | --- | --- | --- |
| 160125 | 2019-07-12 | 2019-07-12 | tencent_etf_hfq | yes | > 2019-07-03 |
| 160125 | 2020-04-21 | 2020-04-21 | tencent_etf_hfq | yes | > 2019-07-03 |
| 160125 | 2022-09-23 | 2022-09-23 | tencent_etf_hfq | yes | > 2019-07-03 |
| 160125 | 2023-11-28 | 2023-11-28 | tencent_etf_hfq | yes | > 2019-07-03 |
| 160125 | 2024-12-19 | 2024-12-19 | tencent_etf_hfq | yes | > 2019-07-03 |
| 161831 | 2021-01-04 | 2021-01-04 | tencent_etf_hfq | yes | > 2020-12-31 |
| 164705 | 2020-12-01 | 2020-12-01 | tencent_etf_hfq | yes | > 2020-11-30 |
| 164705 | 2021-10-28 | 2021-10-28 | tencent_etf_hfq | yes | > 2020-11-30 |
| 164705 | 2022-08-08 | 2022-08-08 | tencent_etf_hfq | yes | > 2020-11-30 |
| 164705 | 2022-11-23 | 2022-11-23 | tencent_etf_hfq | yes | > 2020-11-30 |
| 164705 | 2023-09-13 | 2023-09-13 | tencent_etf_hfq | yes | > 2020-11-30 |
| 164705 | 2024-03-08 | 2024-03-08 | tencent_etf_hfq | yes | > 2020-11-30 |

全量 42 行程序化复核：成对 **42/42**；handoff 日期 **42/42** pass。

## 4. Follow-up / Blockers

| 类型 | 项 | 说明 |
| --- | --- | --- |
| **Manager follow-up（合入前）** | 恢复 `operations/reviews/2026-10-28-v4-prereg-r1b.md` | 与 D16-8 无关的 review 删除；不应随 Manager PR 丢失 durable evidence |
| **Dev / 数据** | （本 spot-check 无） | 未改 `market.sqlite` 或 `src/` |
| **Orchestrator（15）** | 931160×7、HSTECH、161229×2、510300/510500/510880/512100/515180 | 分类未动；仍属 Orchestrator 桶 |

## 诊断 artifact

- `operations/reviews/diag/v4/2026-10-28-d16-8-hfq-tail-spotcheck.json`
