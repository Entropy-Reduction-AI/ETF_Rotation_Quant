# v5 数据填充（别的市场 + 境内期权）· 签收 · 2026-11-02

## Metadata

- Project: ETF_Rotation_Quant
- Document type: review（data-fill 签收）
- Date: 2026-11-02（Asia/Taipei）
- Author: ETF Rotation Reviewer（独立复核）
- Route: review-only（仅 `operations/reviews/**`；未改 raw 数据、业务代码、`results/*/LOCK`、tag、`data/market.sqlite`；未 merge）
- 目标 PR: [#186](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/186) · 分支 `cursor/v5-data-fill`
- 复核 head: `b448a2856ccc4dca2709fc0bc619c79842ae7c63`
- 范围: fetch-only 原始行情；2016+ 可存、不供 v5 设计期（见各 `SCOPE.txt`）

## Decision（对 #186）

**approve_with_follow_up**

manifest SHA256 与行数全部一致；缺数与 partial 在状态表、`blocked-attempts.csv` 中如实登记，未发现 substitute fill 或 silent 换源。独立复取 SSE 风险日与中金所结算日与 Dev `spot-checks.csv` 一致。合并后建议在 Yahoo chart 限流缓解时重试 A 段其余 ticker（见 Follow-ups）。

---

## SHA256 重算摘要

Reviewer 在本机对两份 manifest 所列**全部数据文件**重算 SHA256，并核对 `row_count` 与文件行数（不含表头）。

| manifest | 行数 | SHA256 | row_count |
| --- | --- | --- | --- |
| `results/v5/other-market/raw/manifest.csv` | 2 | **2/2 一致** | **2/2 一致** |
| `data/options/raw/manifest.csv` | 29 | **29/29 一致** | **29/29 一致** |

**合计: 31/31 pass，0 mismatch。**

---

## A · other-market 状态表审计

对照 #186 PR 描述「状态」表与目录内 artifact：

| 产品 | PR 状态 | Reviewer | 说明 |
| --- | --- | --- | --- |
| SPY | got | **一致** | `last_date=2026-09-30`，8475 行；`close_ne_adjclose=yes`，8466 行 close≠adjclose（重算确认） |
| DTB3 | got | **一致** | H.15 压缩包 `RIFSGFSM03_N.B`；1954-01-04→2026-09-30，18978 行；末行 2026-09-30 = 4.03 |
| QQQ…GLD、XLB…XLC、^VIX | missing | **一致** | 仅 `SPY.csv`/`DTB3.csv` 入库；31 个 missing ticker 均在 `blocked-attempts.csv`（HTTP 429 或 FRED 超时）；**无**伪造 CSV |
| DTB3 来源说明 | got（H.15 非 FRED graph） | **诚实** | `blocked-attempts.csv` 写明 FRED graph 超时、api 需 key；入库系列为 Board H.15 3-month T-bill secondary market（discount），与 FRED **DTB3** 同义，非 silent 换无关序列 |

`missing-days.csv` 仅表头（SPY/DTB3 未单独列 weekday gap 表；`coverage.csv` 与 manifest 端点一致）。

---

## B · options 状态表审计（摘要）

| 块 | PR 状态 | Reviewer |
| --- | --- | --- |
| SSE 510050/300/500/588000/588080 风险 | got | `session-coverage.csv` 五品种 `missing_sessions=0`；`missing-days.csv` 无数据行 |
| SSE 合约 OHLCV | partial | 有 `unmapped.csv`、SCOPE 说明无结算/持仓；未 invented null 合约 |
| SZSE 风险 159919/922/915/901 | got | session 表四品种 `missing_sessions=0` |
| SZSE OHLCV | partial | `blocked-attempts` 记录 null payload、无 OHLCV 列；`szse/ohlcv/unmapped.csv` 存在 |
| CFFEX IO/MO/HO | got | session 表缺 0；manifest 行数与文件一致 |
| iVX sh000188 | partial | 296 行，2016-12-05→2018-02-14；`blocked-attempts` 记录 404/502/partial，**未**延伸到 2026-09-30 |

---

## Spot-check 结果

### Dev 表复核

已读 `results/v5/other-market/raw/spot-checks.csv` 与 `data/options/raw/spot-checks.csv`；存储值与表内 `stored`/`result` 字段一致（SPY 2026-09-30 行与 `SPY.csv` 末行一致）。

### Reviewer 独立复取（本 run）

| 来源 | 日期 | 方法 | 结果 |
| --- | --- | --- | --- |
| SSE 风险（全市场 query） | 2025-09-22 | `query.sse.com.cn` 同日 URL 重拉 JSON | **652 行**，与 Dev spot-check **match** |
| CFFEX 日结算 IO/MO/HO | 2025-04-23 | 重下 `20250423_1.csv`，GBK 解析 | live **246+254+214=714**，与 stored 分文件计数及 Dev spot-check **match** |
| SPY | 2026-09-30 | Nasdaq historical API（本环境） | API 返回 `rCode 400`（日期参数/网关限制），**未**作为 fail；已审计 Dev 方法与 `SPY.csv` 末行 OHLCV |
| DTB3 | 2026-09-30 | 读 stored | **4.03**；Dev 对 2026-10 H.15 日值与同源序列的 spot 在 cutoff 之后，不 contradict 截止日 |

---

## 边界核对（Reviewer 门禁）

| 项 | 状态 |
| --- | --- |
| `git diff main...b448a285` 无 `src/`、无 `results/*/LOCK`、无 tag、无 `data/market.sqlite` | ✅ |
| 仅 `.gitignore` 增加 `!/data/options/**` + raw 数据与 metadata CSV | ✅ |
| 未跑策略 / 未算组合 PnL | ✅ |
| missing Yahoo 未用他源 substitute 填 A | ✅ |

---

## Follow-ups（非 merge blocker）

| 优先级 | 项 | 建议 |
| --- | --- | --- |
| P2 | Yahoo chart HTTP 429（31 ticker + ^VIX） | 限流缓解后按 `blocked-attempts.csv` URL 重试；仍失败则保持 missing + 更新 blocked 行 |
| P3 | iVX 2015→2016-12 缺口 | 若有新公开源再开独立 fetch round；**禁止** silent 延伸当前 Sina 296 行 |
| P3 | SPY 第二源 spot | Owner 可选：在可访问 Nasdaq/Stooq 的环境补一条 2026-09-30 独立 spot 写入后续 review |

---

## Blockers

**无。** 若 SHA 重算或 silent substitute 出现则应为 `request_changes`；本次未触发。
