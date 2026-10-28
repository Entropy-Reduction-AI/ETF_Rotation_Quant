# D15-9 完整性归类交叉表（配套）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: work log
- Status: active
- Owner: project owner
- Task: D15-9 Manager 完整性归类配套摘要
- Date: 2026-10-28（Asia/Taipei）
- Route: direct-execute
- Source of truth: `operations/work_logs/2026-10-28-d16-8-hfq-tail-classify.md`（当前合计）；`operations/work_logs/2026-10-28-d15-9-integrity-classify.md`（D15-9 当时）
- Updated: 2026-10-28（D16-8 当前合计）

Manager 分类表的交叉表与分组说明。清单本身只保留 `FINDING_COLUMNS`（含 `manager_class`，不含 `manager_note`）。当前合计以 `operations/work_logs/2026-10-28-d16-8-hfq-tail-classify.md` 为准；D15-9 当时的 12 / 2362 / 15 仍留在文末，不改写。

- #82 取数尖端：`a348365f50eab51875f2bf8d36a50a77fa64f4d3`
- #83 复核合入（D15-9 基线）：`0bf91bd521c8003827b710e10287870799595bef`
- 当前清单基线：`origin/main` `2633613`（D16 / PR #87 之后）
- 源文件: `results/v4/inventory/integrity-findings.csv`（2419 行）
- 口径: D15-9，加上 D16-8 只补 42 行留空；未算收益/排名/IC；未改 `src/`

## 交叉表（check × manager_class）

当前清单，D16-8 把 42 行留空填成可以接受之后。`adj_discontinuous` 以及必须修的 `large_move` / `ended_before_cutoff` 已在 v4-R1c 重扫后离开清单，本表不单列这些已消失的检查项。

| check | 必须修 | 可以接受 | 需要 Orchestrator | 留空 | 合计 |
| --- | ---: | ---: | ---: | ---: | ---: |
| ended_before_cutoff | 0 | 0 | 2 | 0 | 2 |
| large_move | 0 | 2 | 0 | 0 | 2 |
| large_move_hfq_smoothed | 0 | 38 | 0 | 0 | 38 |
| list_date_unknown | 0 | 62 | 5 | 0 | 67 |
| missing_trade_days | 0 | 2302 | 8 | 0 | 2310 |
| 合计 | 0 | 2404 | 15 | 0 | 2419 |

**总计**: 必须修 0 / 可以接受 2404 / 需要 Orchestrator 15 / 留空 0 = **2419**

填之前（#85 重扫后、本轮之前）：必须修 0 / 可以接受 2362 / 需要 Orchestrator 15 / 留空 42 = 2419。本轮只把这 42 行留空改成可以接受。必须修与需要 Orchestrator 的行没有改分类。D15-9 当时（#84，2389 行）的交叉表见文末。

## 必须修（D15-9 当时；当前清单为 0）

这 12 行已由 v4-R1c 修掉，重扫后不在当前清单里。D16-8 没有把它们改成别的分类，也没有把任何现存行改成必须修。下表只保留当时的登记。

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

共 **12** 行（当时）；涉及符号: 159922, 159952, 160125, 161831, 164705, 588050, 588080。v4-R1c 已处理，当前清单里必须修为 **0**。

## 需要 Orchestrator（逐条）

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

共 **15** 行；涉及符号: 161229, 510300, 510500, 510880, 512100, 515180, 931160, HSTECH。这 15 行归 Orchestrator。

### Orchestrator 政策题（汇总，非新行）

1. **研究序列缺日填补**：931160（2019 多段）与 HSTECH（2020-10-13 单日）是否超出「接受」需要正式填补/改日历规则。
2. **161229 停在 2026-09-29**：接受（cutoff−1）还是必须补 2026-09-30。
3. **载体候选上市日取不到**：510300 / 510500 / 510880 / 512100 / 515180 — 回补官方上市日，或允许用 `bars` 首正收盘替代（影响 §3.2 可交易首日）。
4. **因子=1 的 eastmoney_fhsp 后复权**：当同日 raw+hfq 都出现 large_move（159952/588050/588080）时，是否仍认因子=1 足够，还是要换来源重取（与必须修调查绑定）。

## 可以接受（按 check 一段说明）

### `large_move`（2 行 / 1 符号）

仅 XLE @ 2020-03-09：COVID 石油暴跌日，原始与后复权同向约 −20.1%，属已知市场事件；可接受。D15-9 时其余 large_move（159952 / 588050 / 588080）归必须修；v4-R1c 核实为涨停价后，那些行已不在当前清单。本轮没有改 XLE 的分类。

### `large_move_hfq_smoothed`（38 行 / 33 符号）

38 行原始收盘单日超 ±20% 而后复权连续（other_move 通常远小于 raw move），符合份额折算/公司行为被 hfq 抹平的模式；按数据原则保留后复权可用，暂接受。事件表未必有同日拆分记录，但不构成静默造价。

### `list_date_unknown`（62 行 / 62 符号）

非活跃载体候选的 62 只执行层代码，v3 已登记「上市日取不到」；按板策略暂接受并注明 registry unknown。活跃/§3.2 候选（510300 等 5 只）已升 Orchestrator。

### `missing_trade_days`（2302 行 / 53 符号）

场内 ETF 缺失交易日按区间计行；本批最大连续洞 ≤5 个交易日，约 75% 区间为单日（1728/2302）。可以接受的 raw 与 backward 现在按代码和区间一一成对（1151/1151）。D15-9 当时是 1109/1151，差的 42 条 backward 就是本轮填上的延长尾部。高频缺日符号（如 161229、160924、161124）洞仍稀疏，暂接受并记入清单；研究序列缺日仍是需要 Orchestrator，不在本桶。

D16-8 新计入的 42 行：160125（35）、161831（1）、164705（6），都是 `series_kind=backward`、`source=tencent_etf_hfq`。每一行都有同代码、同区间的原始收盘行，且该原始行已经是可以接受。这 42 行的连续洞最长 3 个交易日。

## 载体 / §3.2 相关符号速览

| code | findings 归类摘要 |
| --- | --- |
| 050002 | 本清单无 findings |
| 090010 | 本清单无 findings |
| 159922 | 本清单无 findings（v4-R1c 已修 adj_discontinuous） |
| 159936 | 可以接受:missing_trade_days×102 |
| 159940 | 可以接受:missing_trade_days×2 |
| 159944 | 可以接受:missing_trade_days×48 |
| 159952 | 可以接受:missing_trade_days×4 |
| 160119 | 本清单无 findings |
| 160125 | 可以接受:missing_trade_days×86 |
| 161211 | 本清单无 findings |
| 161229 | 可以接受:missing_trade_days×498; 需要 Orchestrator:ended_before_cutoff×2 |
| 161831 | 可以接受:missing_trade_days×46 |
| 164705 | 可以接受:missing_trade_days×110 |
| 510300 | 需要 Orchestrator:list_date_unknown×1 |
| 510500 | 需要 Orchestrator:list_date_unknown×1 |
| 510880 | 需要 Orchestrator:list_date_unknown×1 |
| 512100 | 可以接受:large_move_hfq_smoothed,missing_trade_days×3; 需要 Orchestrator:list_date_unknown×1 |
| 515180 | 需要 Orchestrator:list_date_unknown×1 |
| 588050 | 本清单无 findings（v4-R1c 已核涨停，large_move 已离开清单） |
| 588080 | 本清单无 findings（v4-R1c 已核涨停，large_move 已离开清单） |
| 931160 | 需要 Orchestrator:missing_trade_days×7 |
| HSTECH | 需要 Orchestrator:missing_trade_days×1 |
| XLE | 可以接受:large_move×2 |

## D15-9 当时（#84，2389 行）

下表是填分类当时的交叉表，含后来被 v4-R1c 修掉、已不在当前清单里的必须修 12。不是当前合计。

| check | 必须修 | 可以接受 | 需要 Orchestrator | 合计 |
| --- | ---: | ---: | ---: | ---: |
| adj_discontinuous | 1 | 0 | 0 | 1 |
| ended_before_cutoff | 3 | 0 | 2 | 5 |
| large_move | 8 | 2 | 0 | 10 |
| large_move_hfq_smoothed | 0 | 38 | 0 | 38 |
| list_date_unknown | 0 | 62 | 5 | 67 |
| missing_trade_days | 0 | 2260 | 8 | 2268 |
| 合计 | 12 | 2362 | 15 | 2389 |

## 产出

- `results/v4/inventory/integrity-findings.csv` — 2419 行；`manager_class` 已填，留空 0
- `operations/work_logs/2026-10-28-d16-8-hfq-tail-classify.md` — 当前合计与本轮 42 行
- `operations/work_logs/2026-10-28-d15-9-integrity-classify.md` — D15-9 当时的计数、必须修、Orchestrator
- 本文件 — 当前交叉表、分组说明，以及 D15-9 当时的交叉表
