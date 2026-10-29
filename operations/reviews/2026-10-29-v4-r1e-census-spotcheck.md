# v4-R1e · 场内 QDII/LOF 普查与补数 · spot-check · 2026-10-29

## Decision：`approve_with_follow_up`

在 Dev PR [#105](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/105) 尖端 `ab358cbf3a0f333077d79d10f9fb493f42027beb`（base main `65bcfca40de27c25f7889aa8208a112acf1461ab`）上，Reviewer **独立**对照 `results/v4/inventory/r1e/`、`config/v4/universe.toml`、`incoming/2026-10-29-v4-r1e/` 原件与 LFS 实库 `data/market.sqlite`：**198 只交易所普查、D19-1 纳入/分组与登记表改写与 Dev 声明一致**；后复权/净值 spot-check **3×5** 与 Dev 冻结东财 payload **逐日一致**；`PRAGMA integrity_check` **ok**、库 SHA 与 summary **一致**；**未发现** look-ahead 或普查名单与登记表自相矛盾。**Follow-up（非阻塞合入 #105）**：8 只 hfq 东财断连、520900 不复权断连、526090 窗口外上市——需在冻结前按 `gaps.csv` / `r1e retry` 补取或书面接受缺口。**未**跑 v4 候选 PnL、**未**汇总 2016+ 组合收益、**未**改 prereg/LOCK/tag。

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R1e D19-4 普查 + 只插入补数 spot-check
- Date: 2026-10-29 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（Review PR 仅追加本文件）
- Dev: PR #105 · head `ab358cbf3a0f333077d79d10f9fb493f42027beb`
- Specs: `operations/planning/2026-10-29-v4-r1e-plan.md`；`operations/planning/2026-10-29-d19-qdii-lof-census.md`；`docs/prereg/etf-multiasset-rotation-prereg-v4.md` §3.1 v2.2；`docs/manual/data-principles.md`
- Dev work log: `operations/work_logs/2026-10-29-v4-r1e-census.md`
- Review branch: `cursor/review-v4-r1e-census-spotcheck-d315`（基于 Dev tip）

## 证据总表

| 检查项 | 方法 | 结论 |
| --- | --- | --- |
| 普查只数 | `wc -l census.csv`；`summary.json` | **198** 只（+ 表头 199 行）；与 Dev **一致** |
| diff 动作 | `diff.csv` `d19_action` 计数 | keep **102** + move **2** = 104 原执行层；add **79**；include_previously_excluded **15**；move **2** |
| 分组键 | `grouping.csv` 行数 | **87** 个 index/商品组（登记表 **118** 个 `maps_to` 容器含非 QDII 既有项，与 work log 口径一致） |
| 库 SHA256 | `git lfs pull` + `sha256sum data/market.sqlite` | **f5ac99449cb966bc32edda103d5f2769bd2313db2f5fdbbc49757ba155a91451**（290242560 B）与 `summary.json` **一致** |
| `PRAGMA integrity_check` | 只读连接 | **ok** |
| `bars` / `fund_nav` 行数 | `SELECT COUNT(*)` | **1039193** / **236540**（Dev 声明 787005→1039193） |
| 同日重复 | `GROUP BY code,date` on bars/fund_nav | hfq / nav **无** duplicate 日 |
| 只插入纪律 | `bars` PK + `bars_no_update` 触发器；fill `inserted`/`kept` | 513100 等 **raw/nav already、hfq in_db**；501225 **841** hfq 新行、**841** raw 仍为 `tencent_etf` **未拼接** |
| 全量单测 | `mkdir -p outputs && .venv/bin/python -m unittest discover -s tests -t .` | **584** ran，**OK**（**1** skipped） |
| 组合 PnL / 2016+ | 硬规则 | **未**运行 |

## 名单 spot-check（10/10）

对照 `census.csv`、`diff.csv`、`config/v4/universe.toml`；交易所 membership 交叉 `incoming/2026-10-29-v4-r1e/raw/sse/*.json.gz`（SSE）与 census 内 `source_url`（SZSE）。东财概况页作类型/基准辅证。

| # | 代码 | 样本类型 | 交易所普查 | 登记表 `maps_to` / 容器 | D19 / §3.1 | Reviewer |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **513100** | 原 v3 纳入 · keep | SSE `fund-list-00-1.json.gz` 命中；`census` listed | `ndx100` | 被动 NDX · 同指数并入 ndx100 | **pass** |
| 2 | **501225** | 原排除 · 现纳入 | SSE `fund-list-10-1.json.gz` 命中；active；基准 PHLX 70% | `theme-PHLX Semiconductor Sector Index` | D19-1 主动纳入；最大权重基准成组 | **pass** · [概况](https://fundf10.eastmoney.com/jbgk_501225.html) |
| 3 | **513020** | v3 无 · add | SSE 名单命中；`d19_action=add` | `theme-中证港股通科技指数` | 被动 · 指数名成组 | **pass** |
| 4 | **160719** | 原排除 · 现纳入 | SZSE 1105 逻辑在 census；`commodity=gold` | `gold` | 跨境黄金 LOF → 商品容器 | **pass** · [概况](https://fundf10.eastmoney.com/jbgk_160719.html) |
| 5 | **162411** | 原纳入 · **move** | census listed；中文名与 159518 不同 | `theme-标普石油天然气勘探及生产精选行业指数` | 英文 **S&P Oil & Gas E&P Select Industry** 合并 | **pass** |
| 6 | **159100** | 原纳入 · **move** | census listed | `theme-巴西IBOVESPA指数`（自旧「伊博维斯帕」容器并入） | 与 520870 同 **Ibovespa Index** | **pass** |
| 7 | **501300** | 原排除 · 现纳入 | SSE LOF；active 90% 巴克莱综合债 | `theme-巴克莱资本美国综合债券指数` | D19-1 + benchmark_max_weight | **pass** |
| 8 | **513350** | 原纳入 · keep | census；SPSIOP | 同 #5 石油天然气 E&P 容器 | mandated_code 合并 | **pass** |
| 9 | **510900** | 原纳入 · keep | census；HSCEI | `theme-恒生中国企业指数` | learned_index_name | **pass** |
| 10 | **160126** | **负对照** · 应不纳入 | **不在** `census.csv`；`gaps.csv` 交易所现行名单无 | **无** qdii 行 | 东财有码无上市日 · 不写入池 | **pass**（正确 omitted）· [概况](https://fundf10.eastmoney.com/jbgk_160126.html) |

## 分组 spot-check（5/5）

来源 `grouping.csv` + 点名 `universe.toml` `maps_to`。

| # | 组（英文键 / 容器 id） | 代码 | 合并规则 | Reviewer |
| --- | --- | --- | --- | --- |
| a | **S&P Oil & Gas Exploration & Production Select Industry Index** → `theme-标普石油天然气勘探及生产精选行业指数` | 162411、159518、513350 | `mandated` / `mandated_code`；中文跟踪名不一致时用 **英文正式名** | **pass** |
| b | **Ibovespa Index** → `theme-巴西IBOVESPA指数` | 159100、520870 | `mandated_code`；159100 自旧容器 **move** | **pass** |
| c | **PHLX Semiconductor Sector Index** → `theme-PHLX Semiconductor Sector Index` | 501225 | 主动 · **benchmark 最大权重** 70% PHLX | **pass** |
| d | **gold**（cross_border_commodity） | 160719、161116、164701 | 跨境黄金 LOF 归 **商品** `gold`，非主题指数 | **pass** |
| e | **hstech**（ crowded ） | 513010、513130、… 共 **14** 只（见 grouping 行） | `learned_index_name` **HSTECH** → 容器 id `hstech` | **pass** |

（另 spot：**ndx100** 组含 **13** 只，含仍缺 hfq 的 **159501**——见 gaps，分组本身 **pass**。）

## 行情 spot-check（3×5）

交易日取 **2026-09-22、09-23、09-24、09-29、09-30**（**09-25** 全库 hfq 为 0 行，属 A 股休市，**不**计入五 day）。Reviewer 用 `incoming/.../kline/{code}-hfq.json.gz` **原始 JSON SHA256**（= `fill.csv` `sha256`）+ `parse_eastmoney_klines` 对比 sqlite `bars`（`adj=hfq`, `source=eastmoney_etf_hfq`）。Reviewer 环境 live `push2his` **Empty reply/RemoteDisconnected**（与 Dev gaps 同类），故 **以 PR 冻结 payload 为准**。

### 后复权（3 代码 × 5 日）

| 代码 | 2026-09-22 | 2026-09-23 | 2026-09-24 | 2026-09-29 | 2026-09-30 | payload SHA 对 fill.csv |
| --- | --- | --- | --- | --- | --- | --- |
| **501225** | match 3.683 | match 3.850 | match 3.795 | match 4.014 | match 4.175 | **pass** `5931469a…` |
| **501300** | match 0.915 | match 0.915 | match 0.912 | match 0.909 | match 0.913 | **pass** `27184dee…` |
| **160719** | match 1.900 | match 1.905 | match 1.882 | match 1.828 | match 1.844 | **pass** `0b596062…` |

### 净值（501300 · pingzhong 插入样本 · 5 日）

| 日期 | sqlite `unit_nav` / source | `pingzhong/501300.js.gz` 解析 | |
| --- | --- | --- | --- |
| 2026-09-22 | 0.9245 / eastmoney_f10_lsjz | 0.9245 | **pass** |
| 2026-09-23 | 0.9192 | 0.9192 | **pass** |
| 2026-09-24 | 0.9163 | 0.9163 | **pass** |
| 2026-09-29 | 0.9142 | 0.9142 | **pass** |
| 2026-09-30 | 0.9121 | 0.9121 | **pass** |

（160719 近期 nav 为既有 `eastmoney_f10_lsjz`；hfq 五日与东财 payload 已全部 match。）

## 东财 hfq 断连（8 只 · 至少 2 只独立复现）

| 代码 | sqlite hfq 行数 | 原件 `kline/*-hfq.json.gz` | Reviewer live push2his | 结论 |
| --- | --- | --- | --- | --- |
| **159501** | **0**（raw 801 行 tencent） | **无** | 2026-09-29/30 **Empty reply** | **真缺口**，非写错价 |
| **160125** | **0**（raw 3360 tencent） | **无** | 同上 **RemoteDisconnected** | **真缺口** |
| 513820 | 0 | 无 | Empty reply | 与 gaps 一致 |
| 513910 | 0 | 无 | （未逐日重试；summary 同 RemoteDisconnected） | 一致 |

## Blockers / Follow-ups

| 类型 | 项 | 说明 |
| --- | --- | --- |
| **Blocker** | （本 spot-check 无） | — |
| **Follow-up** | 8 只 hfq 断连 | 513820、513910、159501、159687、159688、159822、160125、160644；`r1e retry` 或换日补取；**ndx100** 组 159501 缺 hfq 影响该载体序列完整性 |
| **Follow-up** | 520900 raw | gaps：hfq 已有，不复权东财断连且无其它 raw 源 |
| **Follow-up** | 526090 | 上市 2026-10-16 **晚于** 补数截止 2026-09-30；窗口内不补 **合理** |
| **Follow-up** | 7 只东财有码无交易所上市日 | 160126 等；**未**入池 **正确**；若未来上市需新 round |
| **说明** | Live 东财 | Reviewer VM 上 push2his 不稳定；bar 结论以 **incoming 原件 + sqlite** 为准 |

## 合入顺序

1. **先**合 Dev PR **#105**（普查 + 库 + 登记表）。
2. **再**合本 Review PR（仅 `operations/reviews/2026-10-29-v4-r1e-census-spotcheck.md`）。

## 链接

- Dev PR：https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/105
- Review PR：https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/106 · head `f7ee41d`
