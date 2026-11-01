# v5 大类表草稿 · classes-draft 签收 · 2026-11-01

## Metadata

- Project: ETF_Rotation_Quant
- Document type: review（§3.2 大类表草稿签收）
- Date: 2026-11-01（Asia/Taipei）
- Author: ETF Rotation Reviewer（独立复核）
- Route: review-only（仅 `operations/reviews/**`；未改 `results/v5/inventory/classes-draft.csv`、业务代码、`config/v5/classes.csv`、`results/*/LOCK`、tag；未 merge）
- 目标 PR: [#156](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/156) · 分支 `claude/memo-t-and-classes`
- 目标 artifact: `results/v5/inventory/classes-draft.csv`
- 复核 head: `45d6a8af559fa4e8b2bcc3b6ce1f0be79c0e0d33`
- 依据: `docs/prereg/etf-multiasset-rotation-prereg-v5.md` §3.2（main 与 #156 一致）

## Decision（对 #156 / classes-draft.csv）

**approve**

117 行容器均可机械映射到 §3.2 八个大类之一；列结构与必填字段完整；六条原 `manual_rule` 行与 `basis` 中的投资范围/上市市场理由一致。重点复核 **theme-标普全球石油指数 → 美股**：公开免费来源显示美国为最大上市国别权重，未发现另一国别超过美国，无需按第 1 步改类。

---

## 行数与机械核对

| 检查项 | 结果 |
| --- | --- |
| 数据行数（不含表头） | **117** ✅ |
| 列名 | `container_id, class, basis, source_url` ✅ |
| 四列非空 | 117/117 ✅ |
| `container_id` 唯一 | 117 唯一 ✅ |
| `class` ∈ {A股, 港股, 美股, 其他海外, 商品, 国债, 黄金, 现金} | 117/117 ✅ |

**大类分布：** A股 17 · 港股 53 · 美股 29 · 其他海外 11 · 商品 3 · 国债 2 · 黄金 1 · 现金 1

**§3.2 四步抽样（非全表复述）：**

- 第 1 步（跟踪指数 + 上市市场权重）：宽基/行业/海外指数行均指向指数编制方或 closeweight 事实表（如 930796、930604、GPCSP006、ASIATECN 等），与 `class` 一致。
- 第 2 步（基准最大指数）：如 `theme-PHLX Semiconductor Sector Index` → 美股、`theme-巴克莱资本美国综合债券指数` → 其他海外、`cross-border-commodity` → 商品，与基准文字一致。
- 第 3 步（无指数、按投资范围）：如 `gold`、`crude-oil`、`cash` 与 §3.2 容器级例外（黄金不归商品、境内国债不归其他海外）一致。
- 第 4 步（`manual_rule`）：六行已由 Orchestrator 2026-11-01 按投资范围定类，见下表。

未发现空白 `class`、重复 `container_id` 或非法大类名。

---

## 六条原 manual_rule 复核

| container_id | class | Orchestrator 理由（摘要） | Reviewer 结论 |
| --- | --- | --- | --- |
| theme-MSCI China Value Weighted Index | 港股 | MSCI China 以香港上市为主；A 股纳入因子仅占一部分 | **一致**。MSCI China 系列以离岸/H 股为主，归港股符合 §3.2「成分主要在香港上市」口径。 |
| theme-iEdge Emerging Asia Select 50 Index | 其他海外 | 印度、印尼、马来西亚、泰国等新兴亚洲，非美股风险来源 | **一致**。与 SGX iEdge EM Asia 事实表投资范围一致；`source_url` 指向编制方 PDF。 |
| theme-中信证券印度ETP指数 | 其他海外 | 境外印度 ETP，风险来源印度 | **一致**。跟踪/基准为印度市场 ETP，归其他海外。 |
| theme-中证韩交所中韩半导体指数 | 其他海外 | 中证半导体 15 与 KRX 半导体 15 **等权**；打平时归非 A 股一侧 | **一致（tie-break 已披露）**。CSI 指数说明为两子指数等权合并；§3.2 第 1 步无单一最大市场时走第 4 步 + Orchestrator 决定，理由可审计。 |
| theme-标普中国新经济行业指数 | 港股 | A 股合计上限 15%，其余以香港为主 | **一致**。S&P 指数页写明 A-shares capped at **15%**；与海外中国互联网系列归港股一致。 |
| theme-标普全球石油指数 | 美股 | 全球石油**股票**（非原油商品）；美国大型石油公司为最大一组 | **一致**。见下节国别权重证据；**维持 美股**。 |

---

## 重点：theme-标普全球石油指数 → 美股

**容器与指数：** 跟踪 **S&P Global Oil Index**（净总收益系列 SPGOGUN / SPGOGUP）。指数为全球 120 只石油天然气上市公司，总市值加权、单只上限 10%（指数方法论，公开 PDF 镜像：[S&P Global Oil Index Methodology](https://cbonds.hk/download/indexdocs/indexdescrs/1875/)）。

**§3.2 第 1 步问：** 指数成分按**上市国别**汇总权重，美国是否为最大？

| 来源 | 时点 | 美国 | 次大国家/地区 | 结论 |
| --- | --- | --- | --- | --- |
| 华安标普全球石油（160416）2026 年**第一季度**报告 §5.2「分国家（地区）证券分布」（指数化投资，非收益） | 2026-03-31 | **52.47%** | 英国 12.44%、加拿大 11.68% | 美国 **> 任何单一国家** |
| 同上基金 2025 年**中期**报告 §5.2 | 2025-06-30 | **48.94%** | 英国 15.51%、加拿大 11.58% | 美国 **> 任何单一国家** |
| 指数编制方页面（`source_url`） | — | 提供 Country Breakdown 栏目；自动化抓取被站点安全策略拦截 | — | 未改判；以上基金报告与指数成分高度对齐（报告期指数投资占净值约 92%） |
| 天天基金基本概况 · **投资范围**（`source_url` 同链 Eastmoney） | 现行招募摘要 | 主要投资于指数成分；列举美国、英国、法国、意大利、加拿大、澳大利亚、香港等发达市场 | — | 与「全球石油股、非原油商品」及 **美股** 大类一致 |

**Reviewer 判定：** 美国为最大上市国别权重；**不**触发 §3.2 第 1 步「改归其他海外/港股」；**不归商品**（成分为股票指数，非 WTI/Brent 商品基准，与同行的 `theme-标普石油天然气勘探及生产精选行业指数`、`us-xle` 等美股能源股口径一致）。

---

## 其他发现（非 blocker）

| 项 | 说明 |
| --- | --- |
| S&P DJI 网页 Country Breakdown | 浏览器/API 访问触发 Security Controls；已用指数方法论 + 跟踪基金法定报告 §5.2 国别分布替代，仅看成分国别、不看收益。 |
| 中韩半导体 50/50 | 属 documented tie-break；若 Owner 希望 tie 时一律归 A 股，需改预注册或 Orchestrator 规则，**不在本次 CSV 机械错误范围内**。 |
| #156 其余改动 | 本签收范围以 `classes-draft.csv` 为主；memo t-value 措辞未逐句法审，**不**影响大类表 Decision。 |

---

## 边界核对（Reviewer 门禁）

| 项 | 状态 |
| --- | --- |
| 仅成分 / 基准 / 投资范围；未看任何容器或组合 **收益 / PnL** | ✅ |
| 未使用 2016+ 中国组合做策略结论 | ✅ |
| 未运行 v5 S0/C1/C2 或引擎 | ✅ |
| 未写 LOCK / 未动 tag / 未 merge #156 | ✅ |
| 未将 `classes-draft.csv` 复制为 `config/v5/classes.csv` | ✅ |

---

## 后续（非本 PR 义务）

| 角色 | 行动 |
| --- | --- |
| **Manager / Owner** | #156 与本签收 PR 分别合入策略由 Owner 定；合入 **≠** `milestone/v5-prereg-freeze`。 |
| **Dev** | freeze 后原样复制签收版 CSV → `config/v5/classes.csv`。 |
| **Reviewer（后续）** | `component_gate()` 与引擎实现签收（R1b follow-up）。 |

---

## 核对方法

| 维度 | 方法 |
| --- | --- |
| 机械 | Python `csv.DictReader` 全表 117 行；大类集合与 prereg §3.2 表对照 |
| 六 manual | 逐行读 `basis` + `source_url`；必要时公开指数/基金概况 |
| 石油 | 指数方法论 PDF + 华安 160416 2025 中期 / 2026 一季报告 §5.2 国别分布 + Eastmoney 投资范围 |
| 边界 | 未执行回测、未读持仓 PnL |
