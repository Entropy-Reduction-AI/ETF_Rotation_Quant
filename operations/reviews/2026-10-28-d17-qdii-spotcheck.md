# D17 · QDII 净值补齐 + 8 只跟踪标的纳入 · spot-check · 2026-10-28

## Decision：`approve_with_follow_up`

在 Dev PR [#98](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/98) 尖端 `8ee0670f23c3e6a48175e447d891f274e020cc6b`（base `9b48e0706a801c5daeddd8212ee4323775aeb596`）上独立复核：**3×5 净值抽查与 pingzhong 原件一致**；**insert-only**（重叠日仍为 `eastmoney_f10_lsjz`，160717 在 2021-01-04 仍为 0.8097）；**8 只跟踪标的**与 `d17-track-check.csv`、jbgk 原件、`config/v3/universe.toml` 容器/执行层及 `config/v4/universe.toml` 同步一致；**501225 仍在排除表**。**未发现阻塞数据或纳入逻辑缺陷**。

Follow-up（非阻塞）：(1) 合入本 review 前须先合 Dev #98（本分支基于 Dev tip，仅追加评审文件）；(2) 附录 1 仍排除的 **11 只**基金净值起点仍晚于上市日一个月以上，见 `nav_starts_after_list_date` 新检查项，本次范围外；(3) `tests/v3/engine/test_v4_r2.py` 对冻结 P1 的复算跳过随 D17 输入变更，B0 重跑前勿把新路径写进 `FREEZE_P1`（Dev 工作日志已声明）。

## Metadata

- Project: ETF_Rotation_Quant
- Task: D17-1…3 QDII NAV backfill + 8 tracking inclusions
- Date: 2026-10-28 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（本 PR 仅 `operations/reviews/**`）
- 签收对象（Dev）: PR #98 · head `8ee0670f23c3e6a48175e447d891f274e020cc6b`
- Plan: `operations/planning/2026-10-28-d17-qdii-data.md`
- Dev work log: `operations/work_logs/2026-10-28-d17-qdii-data.md`
- Review branch: `review/d17-spotcheck`（基于 Dev tip，仅追加本文件）

## 证据总表

| 检查项 | 方法 | 结论 |
| --- | --- | --- |
| `data/market.sqlite` SHA256 | `sha256sum` | `adfab272ed09e087e1aba4d2798c69e676b476aa6dc80f2027b97e12efb3879b`（与 Dev 工作日志一致） |
| PRAGMA | `sqlite3 PRAGMA integrity_check` | `ok` |
| `bars` 行数 | `SELECT COUNT(*)` | **787005**（未改） |
| `-wal` / `-shm` | 目录列举 | **无** |
| pingzhong 原件 SHA | 24 码 vs `d17-nav-backfill.csv` | **24/24** 一致 |
| 重叠冲突 | inventory `conflicts` 列 | **24 码均为 0** |
| `nav_starts_after_list_date` | `integrity-findings.csv` | **11 行**（均为附录 1 排除、本次未补的基金；与 Dev 表一致） |
| v4 候选 / 2016+ 组合收益 | 硬规则 | **未**运行 |
| LOCK / tag / prereg / 合 main | Reviewer 纪律 | **未**改 LOCK、**未**动 tag、**未**改 prereg、**未**合 main |

## 1. NAV spot-check（3 基金 × 5 日）

抽查基金：**160717**、**160416**、**164906**（均属 D17 研究序列补数名单）。日期均 **早于 2021-01-04**，对应新插入段；对照 `incoming/2026-10-28-d17-qdii/raw/pingzhong/{code}.js.gz` 经 `parse_pingzhongdata` 与 `fund_nav` 同行。

| 代码 | 日期 | 单位净值 | 累计净值 | 库内 source | 结论 |
| --- | --- | --- | --- | --- | --- |
| 160717 | 2010-09-30 | 1.0 = 1.0 | 1.0 = 1.0 | eastmoney_pingzhongdata | OK |
| 160717 | 2012-06-15 | 0.6943 = 0.6943 | 0.6943 = 0.6943 | eastmoney_pingzhongdata | OK |
| 160717 | 2015-01-05 | 0.8765 = 0.8765 | 0.8765 = 0.8765 | eastmoney_pingzhongdata | OK |
| 160717 | 2018-07-20 | 0.7943 = 0.7943 | 0.7943 = 0.7943 | eastmoney_pingzhongdata | OK |
| 160717 | 2020-12-31 | 0.8077 = 0.8077 | 0.8077 = 0.8077 | eastmoney_pingzhongdata | OK |
| 160416 | 2012-03-29 | 1.0 = 1.0 | 1.0 = 1.0 | eastmoney_pingzhongdata | OK |
| 160416 | 2014-08-08 | 1.162 = 1.162 | 1.202 = 1.202 | eastmoney_pingzhongdata | OK |
| 160416 | 2016-01-04 | 0.777 = 0.777 | 0.817 = 0.817 | eastmoney_pingzhongdata | OK |
| 160416 | 2019-03-22 | 1.013 = 1.013 | 1.053 = 1.053 | eastmoney_pingzhongdata | OK |
| 160416 | 2020-12-31 | 0.808 = 0.808 | 0.848 = 0.848 | eastmoney_pingzhongdata | OK |
| 164906 | 2015-05-27 | 1.0 = 1.0 | 1.0 = 1.0 | eastmoney_pingzhongdata | OK |
| 164906 | 2016-12-13 | 0.965 = 0.965 | 0.965 = 0.965 | eastmoney_pingzhongdata | OK |
| 164906 | 2018-06-29 | 1.462 = 1.462 | 1.462 = 1.462 | eastmoney_pingzhongdata | OK |
| 164906 | 2019-11-14 | 1.269 = 1.269 | 1.269 = 1.269 | eastmoney_pingzhongdata | OK |
| 164906 | 2020-12-31 | 1.985 = 1.985 | 1.985 = 1.985 | eastmoney_pingzhongdata | OK |

（表中「=」左为 sqlite，右为 pingzhong 原件。）

**Insert-only**

- 160717 `2021-01-04`：单位/累计 **0.8097**，source **`eastmoney_f10_lsjz`**（未被 pingzhong 覆盖）。
- 三只抽查码：`date < 2021-01-04` 均为 `eastmoney_pingzhongdata`；`date >= 2021-01-04` 保留 f10 行数与 Dev 声明一致；**同码同日 duplicate 行数 = 0**。
- inventory 合计新插入 **27805** 行（含 162411 2250），与 Dev 工作日志一致。

## 2. 八只跟踪标的 + 附录 1 纳入

对照 `results/v4/inventory/d17-track-check.csv`、D17 jbgk gzip、`parse_jbgk` 输出与 `config/v3/universe.toml` / `config/v4/universe.toml`。

| 代码 | 跟踪标的（核对表） | jbgk 解析 | v3 执行层 track + 容器 | v4 `maps_to` / `tracked_index` | 结论 |
| --- | --- | --- | --- | --- | --- |
| 159518 | 标普石油天然气勘探及生产精选行业指数 | 一致 | 与 513350 同容器 `theme-标普石油天然气勘探及生产精选行业指数` | `theme-标普石油天然气勘探及生产精选行业指数` | **通过** |
| 513350 | 同上 | 一致 | 并入上容器 | 同上 | **通过** |
| 162411 | 标普石油天然气上游股票指数 | 一致 | 独立容器 `theme-标普石油天然气上游股票指数`（与 159518/513350 英文名相近但中文全称不同） | 同上 | **通过** |
| 159577 | MSCI USA 50 Index | 一致 | 与 513850 同容器 | `theme-MSCI USA 50 Index` | **通过** |
| 513850 | 同上 | 一致 | 并入上容器 | 同上 | **通过** |
| 159100 | 巴西伊博维斯帕指数 | 一致 | 独立容器（与 520870 中文全称不同） | `theme-巴西伊博维斯帕指数` | **通过** |
| 520870 | 巴西IBOVESPA指数 | 一致 | 独立容器 | `theme-巴西IBOVESPA指数` | **通过** |
| 520580 | iEdge Emerging Asia Select 50 Index | 一致 | 独立容器 | `theme-iEdge Emerging Asia Select 50 Index` | **通过** |

**501225**：仍在 v3 附录排除注释（跟踪标的不是单一指数 / 无跟踪标的），**未**纳入执行层或 v4 同步块。

## 3. 代码与测试（Reviewer 未改 Dev 代码）

- `tests/v4/data/test_r1c.py` 含 `NavStart`（`nav_starts_after_list_date`）用例：**通过**（`.venv` 下 23 项 fund_nav + r1c 相关测试 OK）。
- Dev 声明全量 unittest 553 通过、1 跳过（冻结 P1）；Reviewer **未**重跑全量套件（硬规则：不跑 2016+ 组合路径）；spot-check 与 targeted tests 已覆盖签收点。

## Blockers

**无。**

## Manager / Dev 提示

1. 先合 **#98**，再合本 review PR（base 应为 Dev 分支 `cursor/d17-qdii-data-791e`，避免 review 文件单独对 main 产生误解性 diff）。
2. D17-4：补数后由 Manager 列设计期新增可选容器（只列、不算收益）；11 只仍截断净值的排除基金留待后续任务，勿与本次 23+162411 混淆。
