# v5 数据填充（美股 31 代码 follow-up）· 签收 · 2026-11-03

## Metadata

- Project: ETF_Rotation_Quant
- Document type: review（data-fill 签收）
- Date: 2026-11-03（Asia/Taipei）
- Author: ETF Rotation Reviewer（独立复核）
- Route: review-only（仅 `operations/reviews/**`；未改 raw 数据、业务代码、`results/*/LOCK`、tag、`data/market.sqlite`；未 merge）
- 目标 PR: [#191](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/191) · 分支 `cursor/v5-data-fill-us`
- 复核 head: `de2753ffdc5df7a64c93e0d4e473a8df49331dd4`
- 范围: `results/v5/other-market/raw/` 内 Yahoo 补齐 QQQ…XLC 与 ^VIX；listing→2026-09-30；manifest / status / coverage 元数据

## Decision（对 #191）

**approve**

manifest 所列 33 个数据文件 SHA256 与 `row_count` 全部重算一致；31 个新代码均为 Yahoo 单次拉取、无 Stooq、无同 ticker splice；SPY/DTB3 与 merge 前 `main` 上字节级未变。相对 SPY 交易日历在各 ticker 自身 `[first_date, last_date]` 内 `missing_vs_spy=0`（Reviewer 独立重算确认）。^VIX 相对 SPY 多 2 个 NYSE 休市日 bar，已在 `missing-days.csv` 登记。独立 Yahoo chart 复取 6 个 spot 日与 stored CSV 及 Dev `spot-checks.csv` 一致（≤$0.01 / 浮点等价）。PR diff 未触及 `src/`、LOCK、tag、`data/market.sqlite`。

---

## Checklist 对照

| # | 项 | Reviewer |
| --- | --- | --- |
| 1 | 重算 manifest SHA256 | **33/33 pass**（含 SPY、DTB3 与 31 新文件） |
| 2 | 31 代码齐全；source=Yahoo；无 Stooq splice；SPY+DTB3 SHA 不变 | **pass**（`status.csv` 33 行均为 got；`fetch-log.csv` 31 次 yahoo/200/ok；无 stooq 字符串） |
| 3 | `last_date` ≤ 2026-09-30；listing  plausible；行数 | **pass**（manifest 与 CSV 首末行一致；row_count 33/33 匹配） |
| 4 | missing vs SPY；^VIX 额外 bar | **pass**（0 missing；^VIX extra **2026-05-25**、**2026-09-07** 与 `missing-days.csv` 一致） |
| 5 | spot ≥3 日 | **pass**（见下表；6 日独立 Yahoo + Dev 表审计） |
| 6 | 边界 | **pass**（diff 仅 `results/v5/other-market/raw/**`） |

---

## SHA256 重算摘要

Reviewer 对 `manifest.csv` 全部 `path` 重算 SHA256，并核对 `row_count`（数据行 = 文件行数 − 1）。

| 集合 | 行数 | SHA256 | row_count |
| --- | --- | --- | --- |
| `results/v5/other-market/raw/manifest.csv` | 33 | **33/33 一致** | **33/33 一致** |

SPY / DTB3 与 `git show main:results/v5/other-market/raw/{SPY,DTB3}.csv` 的 SHA256 相同：

- SPY: `de2e444406c3a062b93a1ed227c455144fdb175e08e27ee1e10d280789a75b2d`
- DTB3: `29fe11e20522b4d293cdbbbfd37f2862264692519a251e712747a8532ee95a00`

---

## 状态表审计（相对 Dev 声称）

| 声称 | Reviewer |
| --- | --- |
| 31 Yahoo got · 0 Stooq · 0 missing | **一致**（31 个 CSV 存在；`status.csv` 无 missing/still-missing） |
| manifest 33 行 | **一致** |
| vs SPY 各 range 0 missing | **一致**（独立重算 + `coverage.csv`） |
| ^VIX 2 extra holiday bars | **一致** |
| spot seed 20261102 EWZ/XLK/SHY | **一致**（CSV 与 Dev spot 表；Reviewer 另拉 Yahoo 见下） |

---

## Spot-check 结果

### Dev 表 ↔ 存储

已读 `spot-checks.csv`；SPY / EWZ / XLK / SHY 的 `stored` 字段与对应 CSV 行一致（DTB3 行针对 cutoff 之后 H.15，不 contradict 截止日）。

### Reviewer 独立复取（Yahoo chart v8，本 run）

容差：close/adjclose 与 stored 差 ≤ $0.01（浮点显示等价）。

| 代码 | 日期 | stored close / adjclose | live（Yahoo） | 结果 |
| --- | --- | --- | --- | --- |
| EWZ | 2025-12-10 | 32.77 / 31.362036 | 32.77 / 31.362036 | match |
| XLK | 2026-09-25 | 196.27 / 196.27 | 196.27 / 196.27 | match |
| SHY | 2026-06-30 | 82.11 / 81.136665 | 82.11 / 81.136665 | match |
| QQQ | 2024-06-03 | 453.13 / 447.249512 | 453.13 / 447.249573 | match（adj 浮点末位） |
| ^VIX | 2026-09-30 | 16.34 / 16.34 | 16.34 / 16.34 | match |
| SPY | 2026-09-30 | 762.63 / 762.63 | 762.63 / 762.63 | match |

Nasdaq historical API 对本环境仍返回 `rCode 400`（与 #186 签收相同限制）；未作为 fail。

---

## 边界核对

| 项 | 状态 |
| --- | --- |
| `git diff main...de2753ff` 无 `src/`、无 LOCK、无 tag、无 `data/market.sqlite` | ✅ |
| 仅 other-market raw + metadata CSV | ✅ |
| 未跑策略 / 未算组合 PnL | ✅ |
| 无 Stooq / 无同 ticker 拼接 | ✅ |

---

## Follow-ups（非 merge blocker）

| 优先级 | 项 | 说明 |
| --- | --- | --- |
| P3 | ^VIX 休市日 bar | 下游若需严格 SPY 日历对齐，可按 `missing-days.csv` 过滤；**不要求**本 PR 改 raw |
| P3 | GLD / ^VIX `close_ne_adjclose=no` | manifest 如实标注；消费侧按 `adjustment_policy` 理解 |

---

## Blockers

**无。**
