# D15-9 完整性归类（Manager）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: work log
- Status: active
- Owner: project owner
- Task: D15-9 Manager 完整性归类（v4-R1c 清单）
- Date: 2026-10-28（Asia/Taipei）
- Route: direct-execute
- Source of truth: `operations/planning/2026-10-28-d15-decisions.md`（D15-9）；Manager 分类表；`operations/reviews/2026-10-28-v4-r1c-spotcheck.md`

## 目标

把 #82 交付、#83 复核过的完整性清单每一行填上 `manager_class`。只归类，不修数，不算收益、排名或 IC。

## 依据

- #82 取数尖端 `a348365f50eab51875f2bf8d36a50a77fa64f4d3`（合入 `51535bd6ab20169ee856c656301049e8801fd440`，[PR #82](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/82)）。
- #83 复核尖端 `b3887c72b1e2797392161a1d5d80c1e1c77935f2`（合入 `0bf91bd521c8003827b710e10287870799595bef`，即本分支基线，[PR #83](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/83)）。
- Reviewer 未填写 `manager_class`。本记录把 Manager 已给的三类写入清单。

## 计数

`results/v4/inventory/integrity-findings.csv` 共 **2389** 行，与 #82 交付行数一致，原列与行序未改，只填原先留空的 `manager_class`。

| manager_class | 行数 |
| --- | ---: |
| 必须修 | 12 |
| 可以接受 | 2362 |
| 需要 Orchestrator | 15 |
| 合计 | 2389 |

交叉表（check × manager_class）见配套 `operations/work_logs/2026-10-28-d15-9-classification-summary.md`。

`src/v4/data/integrity.py` 的 `FINDING_COLUMNS` 止于 `manager_class`，没有 `manager_note`。逐条说明不写入 CSV，记在本日志和配套摘要。

## 必须修

共 **12** 行。符号：159922、159952、160125、161831、164705、588050、588080。

| code | series_kind | date | check | 一句话原因 |
| --- | --- | --- | --- | --- |
| 159922 | backward | 2024-12-02 | adj_discontinuous | 后复权事件日不连续 |
| 160125 | backward | 2019-07-03 | ended_before_cutoff | 原始收盘续到 2026-09-30，后复权停在 2019-07-03 |
| 161831 | backward | 2020-12-31 | ended_before_cutoff | 原始收盘续到 2026-09-30，后复权停在 2020-12-31 |
| 164705 | backward | 2020-11-30 | ended_before_cutoff | 原始收盘续到 2026-09-30，后复权停在 2020-11-30 |
| 159952 | backward | 2024-10-08 | large_move | 原始与后复权同日均超 ±20% 且无公司行为记录（move=0.200297） |
| 159952 | raw | 2024-10-08 | large_move | 原始与后复权同日均超 ±20% 且无公司行为记录（move=0.200297 other_move=0.200297） |
| 588050 | backward | 2024-09-30 | large_move | 原始与后复权同日均超 ±20% 且无公司行为记录（move=0.200371） |
| 588050 | raw | 2024-09-30 | large_move | 原始与后复权同日均超 ±20% 且无公司行为记录（move=0.200258 other_move=0.200371） |
| 588050 | backward | 2024-10-08 | large_move | 原始与后复权同日均超 ±20% 且无公司行为记录（move=0.200927） |
| 588050 | raw | 2024-10-08 | large_move | 原始与后复权同日均超 ±20% 且无公司行为记录（move=0.200215 other_move=0.200927） |
| 588080 | backward | 2024-10-08 | large_move | 原始与后复权同日均超 ±20% 且无公司行为记录（move=0.201563） |
| 588080 | raw | 2024-10-08 | large_move | 原始与后复权同日均超 ±20% 且无公司行为记录（move=0.200219 other_move=0.201563） |

**后续归 Dev。** 本记录只登记分类，不改 `src/`，不重写 `market.sqlite`。

## 需要 Orchestrator

共 **15** 行。符号：161229、510300、510500、510880、512100、515180、931160、HSTECH。

| code | series_kind | date | end_date | check | 一句话原因 |
| --- | --- | --- | --- | --- | --- |
| 161229 | backward | 2026-09-29 | 2026-09-29 | ended_before_cutoff | 原始与后复权均停在 2026-09-29（cutoff 前 1 日）；接受 vs 必须补一天由 Orchestrator 定 |
| 161229 | raw | 2026-09-29 | 2026-09-29 | ended_before_cutoff | 原始与后复权均停在 2026-09-29（cutoff 前 1 日）；接受 vs 必须补一天由 Orchestrator 定 |
| 510300 | raw | 2012-05-28 | 2012-05-28 | list_date_unknown | v3 登记上市日取不到，且为 §3.2/载体候选；是否回补上市日或按 bars 首日替代需 Orchestrator |
| 510500 | raw | 2013-03-15 | 2013-03-15 | list_date_unknown | v3 登记上市日取不到，且为 §3.2/载体候选；是否回补上市日或按 bars 首日替代需 Orchestrator |
| 510880 | raw | 2007-01-18 | 2007-01-18 | list_date_unknown | v3 登记上市日取不到，且为 §3.2/载体候选；是否回补上市日或按 bars 首日替代需 Orchestrator |
| 512100 | raw | 2016-11-04 | 2016-11-04 | list_date_unknown | v3 登记上市日取不到，且为 §3.2/载体候选；是否回补上市日或按 bars 首日替代需 Orchestrator |
| 515180 | raw | 2019-12-20 | 2019-12-20 | list_date_unknown | v3 登记上市日取不到，且为 §3.2/载体候选；是否回补上市日或按 bars 首日替代需 Orchestrator |
| 931160 | raw | 2019-01-02 | 2019-01-04 | missing_trade_days | 研究指数 2019-01/02 多段空洞；是否补齐/改日历/剔除需 Orchestrator 定填补规则 |
| 931160 | raw | 2019-01-07 | 2019-01-11 | missing_trade_days | 研究指数 2019-01/02 多段空洞；是否补齐/改日历/剔除需 Orchestrator 定填补规则 |
| 931160 | raw | 2019-01-14 | 2019-01-18 | missing_trade_days | 研究指数 2019-01/02 多段空洞；是否补齐/改日历/剔除需 Orchestrator 定填补规则 |
| 931160 | raw | 2019-01-21 | 2019-01-25 | missing_trade_days | 研究指数 2019-01/02 多段空洞；是否补齐/改日历/剔除需 Orchestrator 定填补规则 |
| 931160 | raw | 2019-01-28 | 2019-02-01 | missing_trade_days | 研究指数 2019-01/02 多段空洞；是否补齐/改日历/剔除需 Orchestrator 定填补规则 |
| 931160 | raw | 2019-02-11 | 2019-02-15 | missing_trade_days | 研究指数 2019-01/02 多段空洞；是否补齐/改日历/剔除需 Orchestrator 定填补规则 |
| 931160 | raw | 2019-02-18 | 2019-02-21 | missing_trade_days | 研究指数 2019-01/02 多段空洞；是否补齐/改日历/剔除需 Orchestrator 定填补规则 |
| HSTECH | raw | 2020-10-13 | 2020-10-13 | missing_trade_days | HSTECH 单日缺失 2020-10-13；单日已知假期样 vs 是否要填补规则 → Orchestrator |

**这 15 行归 Orchestrator。** 政策题（不是新的清单行）：

1. **研究序列缺日填补**：931160（2019 多段）与 HSTECH（2020-10-13 单日）是否超出「可以接受」，需要正式填补或改日历规则。
2. **161229 停在 2026-09-29**：接受（cutoff 前 1 日）还是必须补 2026-09-30。
3. **载体候选上市日取不到**：510300 / 510500 / 510880 / 512100 / 515180 — 回补官方上市日，或允许用 `bars` 首个正收盘替代（影响 §3.2 可交易首日）。
4. **因子=1 的 eastmoney_fhsp 后复权**：当同日 raw 与后复权都出现 `large_move`（159952 / 588050 / 588080）时，是否仍认因子=1 足够，还是要换来源重取。这一问与必须修的调查绑在一起，口径仍由 Orchestrator 定。

## 可以接受

2362 行。按检查项的说明在配套摘要，这里只留口径：

- `large_move` 2 行：仅 XLE @ 2020-03-09，已知市场事件。
- `large_move_hfq_smoothed` 38 行：原始收盘单日超 ±20%，后复权连续，按份额折算/公司行为被后复权抹平接受。
- `list_date_unknown` 62 行：非活跃载体候选，v3 已登记上市日取不到。活跃/§3.2 候选 5 只已升 Orchestrator。
- `missing_trade_days` 2260 行：场内 ETF 缺日按区间计行，最大连续洞不超过 5 个交易日；研究序列缺日已升 Orchestrator。

## 改动面

- `results/v4/inventory/integrity-findings.csv`：2389 行 `manager_class` 已填。
- 本工作日志，以及配套 `operations/work_logs/2026-10-28-d15-9-classification-summary.md`。

没有改 `src/`，没有改 `data/market.sqlite`，没有改 `results/v4/inventory/integrity-2016-2026.md`（该文仍是 Dev 交付时「`manager_class` 留空」的说明）。没有移动 tag，没有改 `main`。

## 验证

对照 #82 合入后的清单与 Manager 分类表：2389 行、原列逐字段一致、行序一致；三类计数 12 / 2362 / 15；空分类 0。没有计算收益、排名或 IC。

## 下一步

- Dev：跟进必须修的 12 行（7 个符号）。
- Orchestrator：决定上面 15 行和 4 个政策题。
- 本 PR 不合入；合入由 Owner 指定的执行者按 `--ff-only` 处理。
