# D16-8 延长后复权尾部 42 行归类（Manager）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: work log
- Status: active
- Owner: project owner
- Task: D16-8 / v4-R1d Manager：三只延长后复权尾部 42 行填可以接受
- Date: 2026-10-28（Asia/Taipei）
- Route: direct-execute
- Source of truth: `operations/planning/2026-10-28-d16-decisions.md`（D16-8）；`operations/planning/2026-10-28-v4-r4b-plan.md` §3

## 目标

把完整性清单里三只延长后复权尾部新增、尚未分类的 42 行 `missing_trade_days` 填成可以接受，并让分类合计与清单一致。不改必须修，不改需要 Orchestrator 的 15 行。

## 依据

- D16-8：按原始收盘对应行的分类填「可以接受」。这些是同一套缺日，原始行已是可以接受。
- 基线：`origin/main` `2633613`（Owner D16、PR #87 合入之后）。
- 填之前的计数来自 v4-R1c 工作日志和 Reviewer #86：必须修 0 / 可以接受 2362 / 需要 Orchestrator 15 / 留空 42，合计 2419。

## 填入规则

只填 `manager_class` 为空、且同时满足下面条件的行：

- `check` = `missing_trade_days`
- `series_kind` = `backward`
- `source` = `tencent_etf_hfq`
- `code` 为 160125、161831、164705 之一
- 同一代码、同一检查、同一日期区间的 `raw` 行已经是可以接受
- 区间起点晚于该只后复权承接前的腾讯末日（160125 为 2019-07-03，161831 为 2020-12-31，164705 为 2020-11-30）

符合的行正好 42。除此之外没有空分类。

| code | 行数 | 日期范围 |
| --- | ---: | --- |
| 160125 | 35 | 2019-07-12 → 2024-12-19 |
| 161831 | 1 | 2021-01-04 |
| 164705 | 6 | 2020-12-01 → 2024-03-08 |

## 计数

| manager_class | 填之前 | 填之后 |
| --- | ---: | ---: |
| 必须修 | 0 | 0 |
| 可以接受 | 2362 | 2404 |
| 需要 Orchestrator | 15 | 15 |
| 留空 | 42 | 0 |
| 合计 | 2419 | 2419 |

填之后的交叉表：

| check | 必须修 | 可以接受 | 需要 Orchestrator | 留空 | 合计 |
| --- | ---: | ---: | ---: | ---: | ---: |
| ended_before_cutoff | 0 | 0 | 2 | 0 | 2 |
| large_move | 0 | 2 | 0 | 0 | 2 |
| large_move_hfq_smoothed | 0 | 38 | 0 | 0 | 38 |
| list_date_unknown | 0 | 62 | 5 | 0 | 67 |
| missing_trade_days | 0 | 2302 | 8 | 0 | 2310 |
| 合计 | 0 | 2404 | 15 | 0 | 2419 |

需要 Orchestrator 的 15 行（931160 七段、HSTECH、161229 的 raw 与 backward、510300、510500、510880、512100、515180）的代码、序列种类、检查和日期都没有改。

## 改动面

- `results/v4/inventory/integrity-findings.csv`：42 行 `manager_class` 从空改为可以接受。其余列、行序和已有分类未改。
- `operations/work_logs/2026-10-28-d15-9-classification-summary.md`：当前合计改成上表；D15-9 当时的 12 / 2362 / 15 留在文末。
- 本工作日志。

没有改 `src/`，没有改 `data/market.sqlite`，没有计算收益、排名或 IC，没有移动 tag，没有改写 `main`。

## 验证

对照填之前的清单：变化只有这 42 行的 `manager_class`。填之后空分类为 0；可以接受的 `missing_trade_days` 为 raw 1151 与 backward 1151，按代码和区间一一成对；必须修仍为 0；需要 Orchestrator 的 15 个键与填之前一致。合计 0 / 2404 / 15 / 0 = 2419。

## 完成判据

42 行延长后复权缺日已填可以接受；合计与清单一致；Orchestrator 15 与必须修 0 未改分类。
