# v5 长历史 · 日本无担保隔夜拆借利率 · 签收 · 2026-11-04

## Metadata

- Project: ETF_Rotation_Quant
- Document type: review（data-fill 签收）
- Date: 2026-11-04（Asia/Taipei）
- Author: ETF Rotation Reviewer（独立复核）
- Route: review-only（仅 `operations/reviews/**`；未改 raw 数据、业务代码、`results/*/LOCK`、tag、`data/market.sqlite`；未 merge）
- 目标 PR: [#212](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/212) · 分支 `cursor/v5-data-fill-jp-call-rate-c623`
- 复核 head: `82616039d54ecb85a62506c5e5ba563309f0d536`
- 范围: `data/research/long-history/raw/` — 日本银行 FM02 月平均、FM01 日次；manifest / spot-checks / session-coverage / blocked-attempts / SCOPE.txt

## Decision（对 #212）

**approve**

manifest 所列 2 个利率 CSV 的 SHA256 与 `row_count` 全部重算一致。日次（FM01'STRDCLUCON，1998-01-05→2015-12-30）与月平均（FM02'STRACLUCON，1985-07→2015-12）分文件存放，未拼成一条序列；1985-01–1985-06 月平均与 1985–1997 日次在来源侧诚实缺失，未用公定步合等替代。入库末行均 ≤2015-12 设计窗口。`SCOPE.txt` 含港股长历史现金利率用 DTB3（港元 1983-10 挂钩美元）说明。Reviewer 种子 `20261103-REV`：月平均 3 点对照 OECD `IRSTCI`、日次 3 点对照东京短资公开月表「平均」列，容差通过；另审计 Dev `spot-checks.csv` 6/6 与存储一致。PR diff 相对 `main` 仅 long-history 元数据与两利率文件；无 `^GSPC`/`^HSI`/`^N225`（仍在 #197）、无 `src/`、LOCK、tag、`data/market.sqlite`。

---

## Checklist 对照

| # | 项 | Reviewer |
| --- | --- | --- |
| 1 | 重算 manifest 全部 path SHA256 + row_count | **2/2 pass** |
| 2 | 日次/月未拼接；1985-01–06 月均与 1985–1997 日次诚实缺失；入库 ≤2015-12 | **pass** |
| 3 | SCOPE 含港股 DTB3 说明 | **pass**（`SCOPE.txt` L8） |
| 4 | 独立 spot：月均 ≥2 vs OECD；日次 ≥2 vs 东京短资/日银同源 | **pass**（种子 `20261103-REV`：各 3 点；日次用东京短资，非日银同源复读） |
| 5 | 审计 Dev spot-checks；diff 仅 long-history 相关 | **6/6 pass**；diff **7 文件**，与 #212 一致 |
| 6 | 边界干净 | **pass** |

---

## SHA256 重算摘要

Reviewer 在 head `82616039` 上对 `manifest.csv` 全部 `path` 重算 SHA256，并核对 `row_count`（数据行 = 文件行数 − 1）。

| ticker | path | SHA256（与 manifest 一致） | row_count |
| --- | --- | --- | --- |
| FM02-STRACLUCON | `data/research/long-history/raw/FM02-STRACLUCON.csv` | `ae543c4b62d47682a5713850891dc8db94c7a0c0397f45abf7e6f78df4797a8d` | 366 |
| FM01-STRDCLUCON | `data/research/long-history/raw/FM01-STRDCLUCON.csv` | `7fab272c3198d44eb590781e5b77a5dd20afe23d1ddf219c2e625216df75369e` | 4420 |

首末观测：FM02 `1985-07`…`2015-12`；FM01 `1998-01-05`…`2015-12-30`。窗口外与重复：0 行；无重复 month/date。

---

## 序列与缺失声明审计

| 声称（SCOPE / session-coverage / blocked-attempts） | Reviewer |
| --- | --- |
| 月平均自 1985-07；缺 1985-01–1985-06 | **一致**（366 月；`session-coverage` summary gap_count=6） |
| 日次自 1998-01-05；1985–1997 无日次 | **一致**（blocked `not_in_source`） |
| 日次/月平均未拼一条 | **一致**（两 CSV、两 ticker；SCOPE L11） |
| NA 日历行未入库（2150，含 2015-12-31） | **一致**（blocked `dropped_na`；末 stored 日 2015-12-30） |
| 来源窗口后数据未写入 | **一致**（blocked `after_window_not_stored`） |
| 日文 CSV 同源核对、非第二来源 | **一致**（blocked `same_source`） |
| 东京短资索引 2013 起、2013 前无公开链 | **一致**（blocked `no_earlier_public_link`） |
| OECD 对齐：251 精确、114 ≤0.005pp、1 月 2013-02 差 0.007 | **一致**（Reviewer 重拉 OECD SDMX 复算分类） |

---

## Spot-check 结果

### Dev 表 ↔ 存储

已读 `spot-checks.csv`（Dev 种子 `20261103`）；6 行 `stored_close` 与对应 CSV `average_pct` 一致。

### Reviewer 独立对照（种子 `20261103-REV`）

**月平均 vs OECD JPN.M.IRSTCI**（容差 ≤ **0.01** 个百分点）

| 月份 | stored | OECD | abs_diff | 结果 |
| --- | --- | --- | --- | --- |
| 1989-12 | 6.44792 | 6.44792 | 0.000 | match |
| 1992-11 | 3.94572 | 3.94572 | 0.000 | match |
| 1999-04 | 0.03 | 0.03143 | 0.00143 | within_0.01 |

**日次 vs 东京短资**（公开月表最后一列「平均」；容差 ≤ **0.001** pp，与 Dev 一致）

| 日期 | stored | 东京短资 | abs_diff | 结果 |
| --- | --- | --- | --- | --- |
| 2013-02-05 | 0.082 | 0.082 | 0.000 | match |
| 2013-08-14 | 0.072 | 0.072 | 0.000 | match |
| 2014-05-23 | 0.068 | 0.068 | 0.000 | match |

Reviewer 另以相同解析复验 Dev 三笔日次（2013-09-04、2013-10-23、2015-08-05）：与东京短资均为 **0.000** 差。

独立 spot JSON：`/opt/cursor/artifacts/jp-call-rate-rev-spot.json`（本 run 写入，未入库）。

---

## 边界核对

| 项 | 状态 |
| --- | --- |
| `git diff main...82616039` 无 `src/`、无 LOCK、无 tag、无 `data/market.sqlite` | ✅ |
| 仅 `data/research/long-history/raw/**` 七文件（两 CSV + 五元数据） | ✅ |
| 未改 ^GSPC/^HSI/^N225（#197 未合入属预期） | ✅ |
| 未跑策略 / 未算组合 PnL / 未写 market.sqlite | ✅ |
| 无日次+月平均 splice / 无公定步合回填 | ✅ |

---

## Follow-ups（非 merge blocker）

| 优先级 | 项 | 说明 |
| --- | --- | --- |
| P3 | OECD vs BOJ 月平均 115 个月非零差 | 已登记 `session-coverage` alignment；消费信号时知悉第二来源舍入/口径 |
| P3 | 日次 spot 公开重叠仅 2013+ | 东京短资索引限制；1998–2012 日次仅 BOJ 来源链 |
| P3 | #197 指数长历史未与本 PR 同批 | 下游需 ^N225 等时依赖 #197 合入顺序 |

---

## Blockers

**无。**
