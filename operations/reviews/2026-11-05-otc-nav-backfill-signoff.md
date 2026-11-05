# OTC 场外净值续接（2016→2026-09-30）· 签收 · 2026-11-05

## Metadata

- Project: ETF_Rotation_Quant
- Document type: review（data-fill 签收）
- Date: 2026-11-05（Asia/Taipei）
- Author: ETF Rotation Reviewer（lwx0218）
- Route: review-only（本 PR 仅 `operations/reviews/**`；未 merge 目标 PR；未改 `data/market.sqlite` / LOCK / 策略）
- 目标 PR: [#259](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/259) · 分支 `cursor/otc-nav-backfill-2016-e9d5`
- 复核 head: `a05ce628c2fdbbef0bf133675ff6c64dc3cdc346`（相对 `main` 自 `3a6ac5e0` 分出）
- 范围: append-only `data/market.sqlite` 中 `v4_series.kind='otc_nav'` 自接缝 `2015-12-31` 续至 `2026-09-30`；来源 `eastmoney_pingzhongdata`、方法 `equity_return_compound`；证据 `results/data/otc-backfill-2016/` + 作业脚本 `src/v4/data/otc_backfill_2016.py`

## Decision（对 #259）

**approve**

Reviewer 在 LFS 实库上独立复算：63 只 roster 与补数前「最后 `otc_nav` 日 = 2015-12-31」的 SQL 完全一致；63 只全部 `final_date=2026-09-30`、接缝复权净值零偏差；追加 164 550 行且接缝及以前 `otc_nav` _guard 哈希与补数前库相同。5×3 天天基金 lsjz 抽查（复跑 `spotcheck_rows`）与 Dev `spotcheck.csv` 一致，最大复权相对差约 4×10⁻⁵。载体只读 `carrier_use` 在补数后 CSV 与现库逐行一致，补数前 CSV 与 `main` 库一致；`trunc_days` 合计由 23 615 降为 0，`otc_days` 未变。`stale-carriers` 3 行复算一致。整库 SHA256 与 `SHA256.txt` / LFS OID 一致。PR diff 未触及 LOCK、oneshot、载体规则或 2016+ 组合 PnL。

---

## MF / SF 签收表

| ID | 必须项（Owner / 任务） | Reviewer |
| --- | --- | --- |
| MF-1 |  roster：凡 `otc_nav` 止于 2015-12-31 的基金全部列入并续接；短于 2026-09-30 须解释 | **pass** — 补数前库 `HAVING MAX(date)='2015-12-31'` → **63** 只，与 `roster.csv` 集合一致；63/63 `reaches_end=yes`、无 `liquidated`/`renamed` 行 |
| MF-2 | 63 = 57 + 6 LOF（场内 bars 已长、场外仍停接缝）计数逻辑 | **pass** — 6 只 LOF（160416、160717、161831、162411、164705、164906）均在 roster；补数后 6 只 `otc_nav` MAX = 2026-09-30 |
| MF-3 | 接缝 2015-12-31 复权净值与库内一致（`equity_return_compound`） | **pass** — roster 63/63 `seam_close_db = seam_close_fresh`；Reviewer SQL 抽检 `seam_bad=0` |
| MF-4 | 5 基金 × 3 日 vs 天天基金；复权连续 | **pass** — 复跑 `spotcheck_rows`（000942、001469、001133、050025、160416 × 2016-06-30 / 2020-12-31 / 2026-09-30）与 `spotcheck.csv` **0** 处不一致；`max adjusted_rel_diff ≈ 3.99×10⁻⁵` |
| MF-5 | 全载体序列 `last_date < 2026-09-30` 清单（stale-carriers） | **pass** — `stale_carriers()` 复算 **3** 行与 CSV 一致（526090 无库内序列；161229 bars/backward 止于 2026-09-29） |
| MF-6 | 只读复算 `otc-carrier-use-2016plus` before/after | **pass** — `main` 库 ↔ `otc-carrier-use-2016plus-before.csv`；补数后库 ↔ `otc-carrier-use-2016plus.csv`；18 容器、`otc_days`/`otc_carrier`/`from`/`to` 与 Dev 一致，`trunc_days` 仅因续接降为 0 |
| MF-7 | `data/market.sqlite` SHA256、append-only、接缝前 `otc_nav` 不变 | **pass** — 见下节 |
| MF-8 | 无策略 / LOCK / oneshot / 载体规则 / 2016+ PnL 改动 | **pass** — `git diff main...a05ce628` 仅 sqlite、backfill 脚本与测试、`results/data/otc-backfill-2016/`、work_log |
| SF-1 | `runs.run_id=26` 登记作业 | **pass** — `kind=backfill`, `status=ok`, args 含 `append_only` / `portfolio_returns:false` |
| SF-2 | 单元测试 `test_otc_backfill_2016.py` | **pass** — Reviewer `.venv/bin/python -m unittest discover -s tests/v4/data -p test_otc_backfill_2016.py -t .` → 6 OK |

---

## 验证笔记

### 1. Roster 与行数

- 补数前 LFS 库（OID `167d4e39…`，298 328 064 B）：`v4_series` **593 481** 行。
- 补数后 LFS 库（OID `1fe4925e…`，332 390 400 B）：`v4_series` **758 031** 行；Δ = **164 550** = roster `inserted` 之和。
- 补数后 `still_at_seam`（仍有基金 MAX=`2015-12-31`）= **0**。
- QDII 公布日较稀（如 539001 追加 2 508 行）仍 `final_date=2026-09-30`，属交易日 vs 公布日差异，非未续接。

### 2. Spot-check（天天基金 lsjz）

- 方法：历史净值表单日查询；页面复权 = 库内上一公布日复权 × (1 + 日增长率/100)（与 Dev `summary.json` `spot_method` 一致）。
- Reviewer **2026-11-05** 在线复取 15 点，与 committed `spotcheck.csv` 字段级一致。

### 3. 载体使用（2016+ 窗口，只读）

| 阶段 | 对照 | 结果 |
| --- | --- | --- |
| 补数前 | `carrier_use(/tmp/market_before.sqlite)` vs `otc-carrier-use-2016plus-before.csv` | 18 行完全一致 |
| 补数后 | `carrier_use(补数后库)` vs `otc-carrier-use-2016plus.csv` | 18 行完全一致 |
| 语义 | `trunc_days` 合计 | before **23 615** → after **0**；四个中证全指行业容器 `otc_days=2611` 且不再截断 |

### 4. Stale carriers

| vehicle_class | code | last_date | note |
| --- | --- | --- | --- |
| QDII | 526090 | （无序列） | 登记载体，库内无行情 |
| listed | 161229 | 2026-09-29 | bars + backward 均早一日 |

### 5. SHA256 与 append-only

| 对象 | Dev / 文件 | Reviewer 重算 |
| --- | --- | --- |
| 整库 before | `167d4e39ffab4302e6f55d2b3436b3400ea28b2282cd7f9b9bda644d87c1acf3` | ✅ LFS `main` OID 一致 |
| 整库 after | `1fe4925e7993eb18d93a5cf359185242a98f7114583f7225033a9ec119ec288f` | ✅ LFS `a05ce628` OID + `sha256sum` 一致 |
| `PRAGMA integrity_check` | ok | ✅ 两库均 ok |
| 接缝及以前 `otc_nav` _guard（7 列 `repr` 行哈希） | `21e626f8921e6e7a6cbf8fcc91e4f1f49ea719e4ac94569b2ba7783cc8684793`，82 362 行 | ✅ before / after **相同** |
| 其他 kind 行数 | bars / fund_nav / listing 未变（脚本 _guard） | ✅ 补数后 `kind!='otc_nav'` 计数与 before 一致（Reviewer：`other_kinds` 逻辑与 Dev summary 一致） |

### 6. PR 边界（`main...a05ce628`）

- 变更文件：`data/market.sqlite`（LFS）、`src/v4/data/otc_backfill_2016.py`、`tests/v4/data/test_otc_backfill_2016.py`、`results/data/otc-backfill-2016/*`、`operations/work_logs/2026-11-04-otc-nav-backfill-2016.md`。
- 未出现：`results/*/LOCK`、oneshot、组合回测输出、载体规则配置变更。

---

## SHA256 接受

Reviewer **接受** #259 对 `data/market.sqlite` 的 after 哈希 **`1fe4925e7993eb18d93a5cf359185242a98f7114583f7225033a9ec119ec288f`**（332 390 400 B），并以接缝前 `_guard` 哈希不变作为 append-only 证据。合入 #259 后，项目应以该 OID 更新库内 SHA256 登记（若 README / 数据变更流程有并列记录，由 Dev/Orchestrator 按既有纪律同步）。

---

## Blockers

**无。**

---

## Follow-ups（非 merge blocker）

| 优先级 | 项 | 说明 |
| --- | --- | --- |
| P3 | 161229 止于 2026-09-29 | 已列 `stale-carriers`；若容器依赖该 LOF 且需对齐截止日，另开 data round，不在本 backfill 范围 |
| P3 | 526090 无序列 | 登记载体无库内 bars/净值；与本次 63 只 OTC 续接无关 |

---

## 关联

- Dev PR: [#259](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/259)（Reviewer **未** merge）
- 本签收 PR: （见 Cloud Agent 打开的 review PR）
