# v5 长历史指数（^GSPC / ^HSI / ^N225）· 签收 · 2026-11-03

## Metadata

- Project: ETF_Rotation_Quant
- Document type: review（data-fill 签收）
- Date: 2026-11-03（Asia/Taipei）
- Author: ETF Rotation Reviewer（独立复核）
- Route: review-only（仅 `operations/reviews/**`；未改 raw 数据、业务代码、`results/*/LOCK`、tag、`data/market.sqlite`；未 merge）
- 目标 PR: [#197](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/197) · 分支 `cursor/v5-data-fill-long-history`
- 复核 head: `418e90c4514b14194b9c67c43b019f0773fe327b`
- 范围: `data/research/long-history/raw/` — Yahoo chart 价格指数日线、manifest / spot-checks / session-coverage / blocked-attempts / SCOPE.txt；`.gitignore` 放行该路径

## Decision（对 #197）

**approve**

manifest 所列 3 个 CSV 的 SHA256 与 `row_count` 全部重算一致；来源均为 Yahoo chart v8 单次拉取、无 Stooq、无 Yahoo+Stooq/CNBC splice。入库列为 `date,open,high,low,close,volume`（价格指数 close；无 adjclose 列）。Reviewer 对 9 个随机日独立拉 Yahoo，`adjclose` 与 `close` 一致且与 stored close 对齐。Dev `spot-checks.csv` 7 行与 stored CSV 一致。Reviewer 种子 `20261103-REV` 独立 CNBC 抽查 6 日 + 日经官方 CSV 1 日，容差 ≤0.05 指数点全部通过。`SCOPE.txt` / `session-coverage.csv` / `blocked-attempts.csv` 对缺失交易日、CNBC 周六未补、HSI 1986 前未补、remaining_missing_days 等声明与文件内容一致。设计窗口声明（^GSPC ≤2003-06-30；^HSI/^N225 ≤2015-12-31）在 SCOPE 中明确，文件含更长历史未截断。PR diff 相对 `main` 仅 long-history raw/元数据与 `.gitignore` 放行；无 `src/`、LOCK、tag、`data/market.sqlite`。

---

## Checklist 对照

| # | 项 | Reviewer |
| --- | --- | --- |
| 1 | 重算 manifest SHA256 / row_count | **3/3 pass** |
| 2 | 来源 Yahoo chart OHLC 价格指数；adjclose≡close；无 Stooq / 无 splice | **pass**（manifest URL 均为 `finance.yahoo.com`；9 日 Yahoo 复取；`blocked-attempts` 仅记录 Stooq probe 未使用） |
| 3 | 独立 spot ≥3 日/指数；第二来源 CNBC / 日经 CSV；≤0.05 | **pass**（种子 `20261103-REV`：6 CNBC + 1 日经；另审计 Dev 7 行） |
| 4 | Dev spot-checks ↔ stored CSV | **7/7 pass** |
| 5 | STATUS / 缺失与边界声明诚实 | **pass**（见下表；4 个 declared missing session 均不在 CSV） |
| 6 | git diff 边界 | **pass**（仅 `data/research/long-history/**` + `.gitignore`） |

---

## SHA256 重算摘要

Reviewer 对 `manifest.csv` 全部 `path` 重算 SHA256，并核对 `row_count`（数据行 = 文件行数 − 1）。

| ticker | path | SHA256（与 manifest 一致） | row_count |
| --- | --- | --- | --- |
| ^GSPC | `data/research/long-history/raw/^GSPC.csv` | `6bf79b2d43eb90152ea406f87fe0101850606528b496761377aa70e36202bce6` | 24827 |
| ^HSI | `data/research/long-history/raw/^HSI.csv` | `7eca9ed8df20868dd4b8915842637aa8c471dde3fb4b7c1b7813a34f5b86efd5` | 9832 |
| ^N225 | `data/research/long-history/raw/^N225.csv` | `78ce1eb4f7990d626a3f3dcd080a65b71e9b24a2e700f8d2a774c1f1959f09ed` | 15198 |

---

## 状态表审计（相对 Dev 声称）

| 声称（SCOPE / session-coverage / blocked-attempts） | Reviewer |
| --- | --- |
| 同一代码仅 Yahoo；三支 got；无 Stooq splice | **一致** |
| ^GSPC remaining_missing_days = 0；CNBC 周六 781 日未进文件 | **一致**（summary `remaining_missing_days=0`，`saturday_sessions_not_in_file=781`） |
| ^HSI 自 1986-12-31；CNBC 1982–1986 未抄；remaining_missing_days = 1（2012-03-19） | **一致**（首行 1986-12-31；`2012-03-19` 不在 CSV） |
| ^N225 remaining_missing_days = 3（2009-09-01、2010-07-20、2010-09-15）；CNBC 周六 983 日未进文件 | **一致**（三日均不在 CSV；summary `saturday_sessions_not_in_file=983`） |
| 与 CNBC 重叠 close 差 >0.05 的天数：^GSPC 235、^HSI 541、^N225 1 | **未独立重算全量**；与 session-coverage summary 字段一致，且未改 Yahoo 值 |
| 设计窗口：^GSPC ≤2003-06-30；^HSI/^N225 ≤2015-12-31（文件可更长） | **一致**（SCOPE.txt §设计期使用窗口） |

---

## Spot-check 结果

### Dev 表 ↔ 存储

已读 `spot-checks.csv`（Dev 种子 `20261103`）；7 行 `stored_close` 与对应 CSV 行一致。

### Reviewer 独立复取（种子 `20261103-REV`）

容差：与第二来源收盘差 ≤ **0.05 指数点**。

| 代码 | 日期 | stored close | 第二来源 | 第二来源 close | abs_diff | 结果 |
| --- | --- | --- | --- | --- | --- | --- |
| ^GSPC | 1941-09-05 | 10.210000 | CNBC `.SPX` | 10.21 | 0.000 | match |
| ^GSPC | 1950-08-07 | 18.410000 | CNBC `.SPX` | 18.41 | 0.000 | match |
| ^HSI | 1997-09-12 | 14470.500000 | CNBC `.HSI` | 14470.46 | 0.040 | within_0.05 |
| ^HSI | 1987-09-08 | 3601.500000 | CNBC `.HSI` | 3601.54 | 0.040 | within_0.05 |
| ^N225 | 1974-11-06 | 3578.080078 | CNBC `.N225` | 3578.08 | 0.00008 | match |
| ^N225 | 1986-12-19 | 18930.029297 | CNBC `.N225` | 18930.03 | 0.00070 | match |
| ^N225 | 2023-06-09 | 32265.169922 | 日经官方 daily CSV | 32265.17 | 0.00008 | match |

另：Dev 日经行 **2025-07-30** Reviewer 复取官方 CSV close **40654.70**，与 stored **40654.699219** 一致（差 0.000781）。

### Yahoo chart（来源一致性，本 run）

9 个随机日（每指数 3 日，同种子）：`adjclose` 与 `close` 相等；stored close 与 Yahoo quote close 一致（浮点显示等价）。

---

## 边界核对

| 项 | 状态 |
| --- | --- |
| `git diff main...418e90c` 无 `src/`、无 LOCK、无 tag、无 `data/market.sqlite` | ✅ |
| 仅 long-history raw + 元数据 CSV/SCOPE + `.gitignore` 放行 | ✅ |
| 未跑策略 / 未算组合 PnL / 未写 market.sqlite | ✅ |
| 无 Stooq / 无同 ticker 拼接 | ✅ |

---

## Follow-ups（非 merge blocker）

| 优先级 | 项 | 说明 |
| --- | --- | --- |
| P3 | CNBC 与 Yahoo 大量 >0.05 差异日 | 已登记于 session-coverage；消费设计窗口内信号时需知悉第二来源偏差 |
| P3 | ^HSI 2012-03-19 等 4 个 Yahoo 缺 bar | 已诚实登记未回补；下游若需完整日历需另议 |
| P3 | ^GSPC 1928-11-06/07 单日日期分歧 | blocked-attempts 已记；未 cross-fill |

---

## Blockers

**无。**
