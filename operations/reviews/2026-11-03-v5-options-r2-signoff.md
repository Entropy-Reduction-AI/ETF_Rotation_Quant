# v5 期权数据填充第二轮（r2/）· 签收 · 2026-11-03

## Metadata

- Project: ETF_Rotation_Quant
- Document type: review（data-fill 签收）
- Date: 2026-11-03（Asia/Taipei）
- Author: ETF Rotation Reviewer（独立复核）
- Route: review-only（仅 `operations/reviews/**`；未改 raw 数据、业务代码、`results/*/LOCK`、tag、`data/market.sqlite`；未 merge）
- 目标 PR: [#201](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/201) · 分支 `cursor/v5-data-fill-options-r2`
- 复核 head: `e2626fe7c88ddd6ed234ecd9deadae6552ee43f1`
- 范围: 仅追加 `data/options/raw/r2/`；2016+ 可存、不供 v5 设计期（见 `r2/SCOPE.txt`）

## Decision（对 #201）

**approve**

`manifest.csv` 所列 24 个 artifact 的 SHA256 与 `row_count` 全部重算一致；`git diff origin/main...HEAD` 仅新增 `data/options/raw/r2/**`，既有 `data/options/raw/`（含根目录 `manifest.csv`）字节级未变。Dev `spot-checks.csv` 33 条均为 `match`，Reviewer 对存储值的回读审计无矛盾。独立 spot（种子 `20261103-REV`）覆盖 SHIBOR、上交所 2015 收盘修正、HYTZ 调整回源、深交所单位交叉核对，与 stored 一致。C1/C2 blocked、OI partial、94 合约缺单位、iVX 不回补等在 `SCOPE.txt`、`blocked-attempts.csv`、`session-coverage.csv` 中诚实登记，未发现 silent substitute 或 SHA 虚假声称。

---

## SHA256 重算摘要

Reviewer 对 `data/options/raw/r2/manifest.csv` 全部 24 行逐文件重算 SHA256，并核对 `row_count`（CSV 为数据行不含表头；`.md`/`.txt` 为行数；`.xlsx` 用 sheet 数据行计数，与派生 CSV 行数一致）。

| 项 | 结果 |
| --- | --- |
| SHA256 | **24/24 一致** |
| row_count | **24/24 一致** |

**合计: 24/24 pass，0 mismatch。**

---

## 边界核对

| 项 | 状态 |
| --- | --- |
| diff 仅 `data/options/raw/r2/**`（25 files，+897339 行级增量） | ✅ |
| 无 `src/`、`results/*/LOCK`、tag、`data/market.sqlite` | ✅ |
| `origin/main` 与 HEAD 的 `data/options/raw/manifest.csv` SHA 相同 | ✅ |
| 未覆盖既有期权 raw OHLCV / 风险 / CFFEX 等 | ✅ |
| 未跑策略 / 未算组合 PnL | ✅ |

---

## 状态表审计（对照 #201 与目录 artifact）

| 块 | PR / SCOPE 声称 | Reviewer |
| --- | --- | --- |
| C1 深交所 OHLCV 缺口 | blocked，无新 OHLCV | **一致** — `session-coverage.csv` 三品种 `sessions_with_rows=0`；`blocked-attempts.csv` 5 行缺口尝试 + 说明 |
| C2 日结算价 | blocked | **一致** — `session-coverage.csv` 各品种 settlement `sessions_with_rows=0`；独立 yunhq 样本合约 `settlement` 非空 0；blocked 行 field_null / current_snapshot_only |
| C2 日持仓量 | partial | **一致** — SSE OI 五标的 + unmapped 行数与 manifest 一致；510050 `missing_sessions=2`（2015-03-24、2016-03-31）；`open-interest-failures.csv` 2 合约；SZSE OI 历史 `sessions_with_rows=0` |
| C3 2015 收盘为 0 | got | **一致** — `close-corrections-2015.csv` 232 行，`status=fixed`，表内 `new_close_within_sina_high_low=yes` 232/232 |
| C4 合约单位 / 调整 | partial | **一致** — listings/adjustments/multipliers 行数与 manifest 一致；`session-coverage` SSE unit `missing_sessions=94`；blocked 行 `sse-adjustment-unit-gap` 举例 A 码改名无 HYTZ |
| C5 SHIBOR | got | **一致** — 2930 行，2015-01-04→2026-09-30，八期限 |
| C6 重复行 | got（QC 统计，未改 raw） | **一致** — `QC.md` 与 SCOPE 引用一致 |
| C7 iVX | got（不回补） | **一致** — blocked `ivx-more-backfill` result=not_attempted |

---

## Spot-check 结果

### Dev 表复核（`data/options/raw/r2/spot-checks.csv`）

| 项 | 结果 |
| --- | --- |
| 行数 | 33（与 manifest `row_count` 一致） |
| `result` 列 | **33/33 `match`** |
| SHIBOR 24 条 vs `rates/shibor.csv` | **0 mismatch** |
| SSE 收盘 3 条 vs `close-corrections-2015.csv` 的 `new_value` | **一致** |
| SSE 调整日计数 3 条 vs `sse/adjustments.csv` 按 `adjust_date` 聚合 | **一致** |

注：Dev 方法字段中部分 SSE 收盘行注明新浪与 yunhq **成交量不一致**（如 2017-07-14），但 **close 仍为 match**；与「收盘修正」范围一致，非 silent 改 volume。

### Reviewer 独立复取（种子 `20261103-REV` → `Random` int `1236770363`）

| 类别 | 抽样 | 方法 | 结果 |
| --- | --- | --- | --- |
| SHIBOR | 2015-11-25、2018-04-12、2025-10-16 × 8 期限 | stored vs 中国货币网 `ShiborHis` 同日 API | **24/24 match**（本环境东财 `RPT_IMP_INTRESTRATEN` 返回空，未作为 fail；以中国货币网为独立主源） |
| SSE 2015 收盘修正 | 3 合约（如 10000006/13/46） | `new_value` vs yunhq dayk；vs 既有新浪 OHLCV high/low | **3/3 yunhq close match**；**3/3 落在新浪 H/L 内** |
| SSE 调整 | 2017-11-28（独立抽 1 日） | 同日 HYTZ `commonQuery` 行数 vs stored | **100 = 100 match** |
| 深交所单位 | 3 合约（如 159915C2612M003600） | `live-contract-snapshot.csv` vs `listings.csv` `contract_unit` | **3/3 match（均为 10000）** |

Reviewer 诊断 JSON：`/opt/cursor/artifacts/r2-reviewer-spot.json`（本 run 落盘，不入库）。

---

## Blockers

**无。** 若 SHA 重算失败、覆盖既有 raw、或对 blocked 项伪造 got，应为 `return_to_planning`；本次未触发。

---

## Follow-ups（非 merge blocker，交后续 R3 / 独立 round）

| 优先级 | 项 | 说明 |
| --- | --- | --- |
| P2 | C1 深交所缺口 OHLCV | 保持 blocked 直至有可用公开日序列；禁止 invented bars |
| P2 | C2 日结算价 + 深交所日 OI 历史 | 当前快照文件日期晚于 cutoff，已在 SCOPE 标明；勿误当日表为历史 |
| P2 | C4 上交所 94 合约缺单位 | 风险 feed A 码与 HYTZ 空集；R3 专任务，禁止默认 10000 填 |
| P3 | SSE OI 缺 2 个交易日 | 510050 2015-03-24、2016-03-31；已在 session-coverage 登记 |
