# 数据看板 buy_first ↔ v4_listing 对齐 · 签收 · 2026-10-31

## Decision：`approve_with_follow_up`

在 Dev PR [#146](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/146) 尖端 `691fa9e03a8b6f9160fd9502680c6003433d1f3a`（base main `5e53096`，分支 `cursor/align-buy-first-listing-fa7f`）上，Reviewer **独立**核对 diff 范围、五处 spot-check 与 `theme-HSSCITI` 已知口径差。结论：**仅看板脚本/产物变更，无 `src/`**；五处新 `buy_first` 与 `build_candidates` 首次可持有日一致；HSSCITI 为看板（原始正收盘）与引擎（60 日 + 3,000 万）的** intentional** 分歧，不视为缺陷。

Follow-up（不阻塞 #146 合入）：**Manager** 在 Dev 合入后把 `docs/owner/data-board.md` 与重跑后的 `out/summary.json` / 池子增长图口径对齐（PR 正文已说明未改 Owner 文档）。

## Metadata

- Project: ETF_Rotation_Quant
- Task: buy_first 与引擎 v4_listing 同源 · Reviewer 签收（PR #146）
- Date: 2026-10-31 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（Review 分支仅追加本文件）
- 设计期上界（独立复算未跑组合 PnL）：spot 日期均 ≤2015-12-31；HSSCITI 对照用 `end=2026-09-30` 日历
- 库指纹：`data/market.sqlite` SHA256 `167d4e39ffab4302e6f55d2b3436b3400ea28b2282cd7f9b9bda644d87c1acf3`（`git lfs pull` 后只读）

## Diff 范围（PR #146）

| 路径 | 说明 |
| --- | --- |
| `results/v4/diag/data-board/build_data_board.py` | buy_first 与 `carriers.build_candidates` 第 2/3 档及场内 `raw_dates` 对齐 |
| `results/v4/diag/data-board/buy_first-diff.md` | 13 容器变化清单 |
| `results/v4/diag/data-board/out/containers.csv` | 重跑输出 |
| `results/v4/diag/data-board/out/summary.json` | 重跑输出（含 `buy_by_year`） |
| `docs/assets/data-board/d1-pool-growth.png` | 图更新 |

**未改动：** `src/`、策略/组合 PnL、LOCK、tag、milestone、`docs/owner/data-board.md`。

## Spot-check 五处（board buy_first = 引擎首次可持有日）

**方法：** 只读 `data/market.sqlite`；`load_containers()` + `sse_calendar(con, "2026-09-30")` + `build_candidates(..., us_spdr=US_SECTORS)`。对每个容器，取任一候选 `available` 第一次为真的上交所交易日（OR 全档候选）。未重跑看板脚本、未重算组合收益。

| 容器 | 代码 | board buy_first | 引擎首次可持有 | Match |
| --- | --- | --- | --- | --- |
| chinext | 050021 | 2011-06-10 | 2011-06-10 | Y |
| ndx100 | 160213 | 2010-04-29 | 2010-04-29 | Y |
| spx | 050025 | 2012-06-14 | 2012-06-14 | Y |
| allshare-healthcare | 001180 | 2015-05-06 | 2015-05-06 | Y |
| theme-纳斯达克生物科技指数 | 001092 | 2015-03-30 | 2015-03-30 | Y |

五处驱动载体均为 **tier-2 OTC**（与 `buy_first-diff.md` 叙述一致）。

## theme-HSSCITI（ intentional 分歧）

| 口径 | 日期 | 说明 |
| --- | --- | --- |
| 看板 buy_first | 2025-08-25 | 520840 原始 K 线第一根正收盘 |
| 引擎首次可持有 | 2025-11-25 | tier-1 520840 过 60 个交易日 + 近 20 日成交额中位数 ≥ 3,000 万 |

看板 deliberately 不套 v3 §3.3 流动性/上市滞后门槛；**不作为 buy_first 对齐失败**。

## 边界核对

| 项 | 结果 |
| --- | --- |
| 修改 `src/` | 否 |
| 策略 / B0 / 组合 PnL 重跑 | 否 |
| LOCK / tag / milestone | 未动 |
| 设计期 claims | 本签收仅 spot 日期与 HSSCITI；未宣称新的设计期绩效 |
| Dev diff 与 PR 正文一致 | 是（5 文件，与 `buy_first-diff.md` 一致） |

## 给 Manager

1. Dev #146 合入后更新 `docs/owner/data-board.md`（buy_first 口径、年末可买个数 2010/2012/2015/2026-09-30、HSSCITI 图注）。
2. 可选：将本次 spot5 复算片段沉淀为 `operations/reviews/diag/v4/` 小脚本（非阻塞）。
