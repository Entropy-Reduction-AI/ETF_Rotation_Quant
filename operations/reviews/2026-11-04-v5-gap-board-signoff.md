# v5 数据看板 · 免费来源缺口登记 · 签收 · 2026-11-04

## Metadata

- Project: ETF_Rotation_Quant
- Document type: review（Owner 文档核对签收）
- Date: 2026-11-04（Asia/Taipei）
- Author: ETF Rotation Reviewer（独立复核）
- Route: review-only（仅 `operations/reviews/**`；未改 raw、未算收益、未写 sqlite/LOCK/tag；未 merge 目标 PR）
- 目标 PR: [#209](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/209) · 分支 `cursor/v5-data-fill-gap-board`
- 复核 head: `25cd82cf0cc52c0d7bc74c8cb8ea37a3699c9267`
- 范围: `docs/owner/data-board.md` 第 5 节 + 新增 `docs/owner/free-source-gaps.md`；证据链指向 [#201](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/201) 的 `data/options/raw/r2/`

## Decision（对 #209）

**approve**

`git diff origin/main...25cd82cf` 仅 2 个 Owner 文档（+97 / −1 行）。三处缺口与 #201 `SCOPE.txt` C1/C2、`r2/blocked-attempts.csv`、`r2/session-coverage.csv` 一致，状态均为 `won't-pursue-free`（看板用语「免费来源拿不到，不再追」）。已试来源叙述与 blocked 行及第一轮 `data/options/raw/blocked-attempts.csv` 的 `szse-sina-null` 可对齐；未把 blocked 写成 got，上交所日持仓 partial 正确排除在本页之外。文风符合 Owner 看板「结论先行、详情链出」；有两处压缩表述，记 follow-up note，非 blocker。

---

## 签收清单

| # | 项 | Reviewer |
| --- | --- | --- |
| 1 | 三缺口与 #201 / r2 SCOPE + blocked-attempts + session-coverage 一致；状态为 won't-pursue-free | **pass**（见下表） |
| 2 | 已试来源与 r2 证据可对齐；无夸大 got | **pass** |
| 3 | diff 仅 Owner 文档（`docs/owner/**`） | **pass** — 2 files only |
| 4 | 文风对齐 Owner 看板原则 | **pass**（见 Style notes） |

### 三缺口 ↔ r2 证据

| Owner 登记 | #201 块 | SCOPE / session-coverage | blocked-attempts（r2） |
| --- | --- | --- | --- |
| 深交所期权日线 2019-12→2022-12（159919 / 159915 / 159922） | C1 blocked | `szse-ohlcv-gap` 三品种 `sessions_with_rows=0`（720 / 55 / 55）；请求止 2022-12-09 vs SCOPE 截止 2022-12-11 为同段空洞 | `szse-ohlcv-gap-sina` null；`history-api` no_kline；东财 connection_closed；腾讯 param_error；网易/10jqka 502 |
| 两所每日结算价 | C2 blocked | `sse-daily-settlement` 五标的 + `szse-daily-settlement` 四标的均为 0 行 | `sse-historical-settlement` field_null（844603 bars）；`sse-szse-daily-settlement-and-szse-oi` current_snapshot_only |
| 深交所历史持仓量 | C2 partial 中的 SZSE 部分 | `szse-open-interest` 四标的 0 行；note 为当日 `option_drhy` 仅合约总持仓 | 同上 combined 行；与 SSE OI got（yunhq）区分清楚 |

---

## 边界核对

| 项 | 状态 |
| --- | --- |
| diff 不含 `data/`、`src/`、`results/*/LOCK`、tag、`data/market.sqlite` | ✅ |
| 未覆盖或改写 #201 raw artifact | ✅ |
| 未跑策略 / 未算组合 PnL | ✅ |
| 证据路径指向 PR #201 r2 目录（本 PR 只登记 Owner 结论） | ✅ |

---

## Style notes（非 blocker）

| 项 | 说明 |
| --- | --- |
| 看板第 5 节「已试」列 | 摘要级（如「网易」）；`free-source-gaps.md` §1 展开同花顺、搜狐。符合「看板索引、详情单页」。 |
| 日期窗口 | 看板写 `2019-12 → 2022-12`；详情页与 `session-coverage` 用精确起止。同一段缺口，无新声称。 |
| §3 缺口前导语 | 「期权还有三处…见第 5 节」放在 §3 末，不混入 6 条池子陷阱，读者路径清晰。 |

---

## Blockers

**无。** 若三缺口与 r2 矛盾、diff 触及 raw/sqlite、或将 blocked 误标为 got，应为 `return_to_planning`；本次未触发。

---

## Follow-ups（非 merge blocker）

| 优先级 | 项 | 说明 |
| --- | --- | --- |
| P3 | Owner 发布 | #209 合入后 Orchestrator 按既有流程同步对外看板（若与仓库副本分离）。 |
| P2 | 付费或机构源 | 三处仍为 won't-pursue-**free**；若 Owner 日后授权非免费源，须新 round + 预登记，不得 silent 回填。 |
