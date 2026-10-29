# v4-R1e 场内 QDII/LOF 普查摘要（Manager）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: work log
- Status: complete
- Owner: project owner
- Task: v4-R1e D19-4 Manager 核查汇总 + 2006–2015 可选容器清单
- Date: 2026-10-29（Asia/Taipei）
- Route: direct-execute
- Source of truth: `operations/planning/2026-10-29-v4-r1e-plan.md`；Dev `operations/work_logs/2026-10-29-v4-r1e-census.md`；Reviewer `operations/reviews/2026-10-29-v4-r1e-census-spotcheck.md`；`results/v4/inventory/r1e/*`
- Main tip（合入 #105/#106 后）: `4c5c16563c3ba9a192377c3aa07c49aa27d5914a`
- 分组全表: `operations/work_logs/2026-10-29-v4-r1e-grouping-table.md`（同源 `results/v4/inventory/r1e/grouping.csv`）

## 目标

按计划 Manager 三项中的前两项与第三项日期清单：交易所名单只数、对照差额、补数结果；分组见另表；列出 D17/R1e 使设计期（≤2015-12-31）新增可用的可选容器与日期。**不算**组合收益、排名、IC；**不算** 2016-01-01 及以后收益汇总；不改 `src/`，不改库，不打标签。

## 头条计数（对照 Dev / Reviewer）

| 口径 | Dev 声明 | Manager 核自 inventory | 一致 |
| --- | ---: | ---: | --- |
| 交易所普查（场内 QDII ETF/LOF） | 198 | `census.csv` 198 行；`summary.json` `exchange_total=198` | 是 |
| 原 v3 执行层 | 104（含 2 只改挂） | `diff.csv`：keep 102 + move 2 = **104** | 是 |
| D19-1 原排除现纳入 | 15 | `include_previously_excluded` **15** | 是 |
| v3 无、本次新增 | 79 | `add` **79** | 是 |
| 指数/商品分组 | 87 | `grouping.csv` **87** 组；成员合计 **198** | 是 |
| 登记表容器 | 87→118 | `config/v3/universe.toml` `id` **118**；`coverage.csv` 容器 **118** | 是 |
| 后复权有序列 | 189 | `fill.csv` hfq `in_db` **189**；`unfillable` **9**（含窗口外 526090） | 是 |
| 单位净值有序列 | 197 | `fill.csv` nav 有非空 `first` 的 **197** 只；526090 行为 `in_db` 但 `first` 空、`inserted=0`（窗口后无序列） | 是 |
| 不复权有序列 | 196 | 缺 **520900** raw、**526090** → **196** | 是 |
| sqlite SHA256 | `f5ac9944…` | `summary.json` / Reviewer：`f5ac99449cb966bc32edda103d5f2769bd2313db2f5fdbbc49757ba155a91451` | 是 |
| `bars` 行数 | 1039193 | Reviewer spot-check 同数 | 是 |
| `PRAGMA integrity_check` | ok | Reviewer **ok** | 是 |

差额恒等式：198 = 104 + 15 + 79。

## 补不到 / 开放 follow-up（无 blocker）

来源：`gaps.csv`、`summary.json` `unfillable`、Reviewer `approve_with_follow_up`。

| 代码 | 缺口 | 说明 |
| --- | --- | --- |
| 513820、513910、159501、159687、159688、159822、160125、160644 | hfq 东财断连未写入 | 8 只；库内部分仍有腾讯 raw（如 160125、160644、159822） |
| 520900 | raw 断连 | hfq 已写入；无其它 raw 源可留 |
| 526090 | 窗口外 | 上市 2026-10-16 > 补数截止 2026-09-30，不补 |
| 160126、160141、160213、161620、163813、164212、501226 | 未入池 | 东财有码、交易所现行名单无、概况页无上市日（正确 omitted） |

## 点名合并（登记口径）

| 代码 | 容器 `target_id` | 依据 |
| --- | --- | --- |
| 159518、513350、162411 | `theme-标普石油天然气勘探及生产精选行业指数` | 英文正式名 S&P Oil & Gas Exploration & Production Select Industry Index（R1e 合并；D17 曾因中文名分拆） |
| 520870、159100 | `theme-巴西IBOVESPA指数` | Ibovespa / IBOVESPA |
| 160719、161116、164701 | `gold` | 跨境黄金 LOF → 商品 |
| 160216、161815、165513 | `cross-border-commodity` | 跨境商品配置 |
| 501225 | `theme-PHLX Semiconductor Sector Index` | 主动；基准最大权重 PHLX 70% |

## 2006–2015 新增可选容器（只列日期，不算收益）

设计窗口截止 **2015-12-31**。日期取自 `census.csv` `list_date` 与 `fill.csv` / `coverage.csv` 序列起点（取可核对的最早场内序列日）。**未**套 §3.2 可交易首日（第 60 交易日）与近 20 日成交额 ≥3000 万——那是载体表口径（见 R1c），本清单只回答「D17/R1e 之后，哪些容器在设计期已有入库历史」。

### A. 因 D17 / R1e **新出现**的容器（设计期内已有成员）

| 容器 id | 最早场内成员 | 上市日 | 序列起点（hfq / nav） | 来源 |
| --- | --- | --- | --- | --- |
| `cross-border-commodity` | 161815 银华抗通胀 | 2010-12-20 | hfq/nav 2010-12-20 | R1e · D19-1 原排除现纳入（另 165513@2012-01-13、160216@2015-04-07） |
| `theme-标普石油天然气勘探及生产精选行业指数` | 162411 | 2012-06-08 | hfq 2012-06-08；nav 2011-09-29（D17 补净值） | D17 纳入；R1e 与 159518/513350 合并为同一容器 |
| `theme-S&P 500 Energy Sector Index(NTR)` | 163208 诺安油气能源 | 2015-02-17 | hfq/nav 2015-02-17 | R1e · D19-1 原排除现纳入 |

### B. 原有容器，因 R1e **扩进**设计期成员（可选深度变化）

| 容器 id | 新成员（R1e） | 上市日 | 序列说明 |
| --- | --- | --- | --- |
| `gold` | 161116、160719、164701 | 2011-11-08 / 2012-02-10 / 2012-03-01 | 三只跨境黄金 LOF；hfq/nav 均自上市日起。容器原有 518880 等 A 股黄金路径（coverage 首日 2013-07-29），LOF 把场内可选起点提前到 **2011-11-08** |
| `hsi` | 160125 南方香港优选 | 2011-11-01 | **nav/raw 自 2011-11-01**；**hfq 东财断连未写入**（follow-up）。容器原有 159920/513600/513660/164705 等 |

### C. 设计期内已有、但 **非** D17/R1e 新纳入的海外容器（对照，不计入「新增」）

`ndx100`（最早 513100@2013-05-15）、`spx`（513500@2014-01-15）、`theme-恒生中国企业指数`（160717@2010-10-28）、`theme-标普全球石油指数`（160416@2012-05-02）、`theme-法兰克福DAX指数`（513030@2014-09-05）、`theme-中证海外中国互联网指数`（164906@2015-07-10）。均为 `diff` keep。

### D. 紧贴窗口但未进入 2006–2015 的相关纳入

| 代码 | 上市日 | 容器 | 说明 |
| --- | --- | --- | --- |
| 161229 | 2016-01-04 | `theme-MSCI China Value Weighted Index` | R1e 纳入；**晚于**设计期截止日一天，不列入上表 |

### 清单是否完整？

- **容器 id + 上市日 / 入库序列起点**：完整。依据 `census.csv`（198 只均有 `list_date`）、`diff.csv` 动作、`grouping.csv`、`fill.csv`、`coverage.csv`。
- **逐年「当天可用载体」表（§3.2 流动性/60 日）**：**未做**。QDII/LOF 尚未按 R1c 载体表同口径跑代表日；160125 缺 hfq 时能否进第 1 档待 Orchestrator。本文件不发明可交易首日。
- **收益 / CAGR / MDD**：**不做**（硬规则）。

## 验证

- 头条表与 `summary.json`、`diff.csv` 动作计数、Reviewer 证据总表交叉一致。
- 分组成员并集 = 普查 198；无孤儿代码。
- 未读取或汇总任何组合净值路径收益。

## 完成判据

- 核查汇总数字已与 Dev/Reviewer 对齐。
- 分组表另文落地。
- 2006–2015 新增可选容器三条 + 两条扩容 + 对照/边界已写清；缺的是 §3.2 逐日载体，不是名单日期。

## 五段

- **本轮完成：** R1e 普查 Manager 摘要；分组表；设计期新增可选容器日期清单。
- **能做什么不能做什么：** 能把 198/104/15/79/87/118 与库指纹交给 Owner/Orchestrator；不能当载体可交易证明，也不能当收益结论。
- **业务信号：** 设计期海外/商品可选面因 D17+R1e 明确多出跨境商品、标普油气 E&P、标普能源（NTR）三只容器，并提前黄金 LOF 与恒生 160125 的入库历史。
- **风险卡点：** 8 只 hfq 断连（含 160125、ndx100 组内 159501）；520900 raw；MF-6 粘性文案仍待 Orchestrator。
- **需要 Owner 的事：** 无。Follow-up 补数或书面接受缺口属冻结前数据项，不阻塞本摘要。
