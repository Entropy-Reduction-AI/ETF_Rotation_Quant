# PR361 入库独立复核（Reviewer · 非 GitHub formal review）

## 锚点

| 项 | 值 |
| --- | --- |
| PR | [#361](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/361) |
| **签收 head** | `ce058680fabec19b12982bffce37e891808d4641` |
| base（359+360 已并） | `05e39c5650acb52e0de8632bcaef8e6d05fe5597` |
| 改动 | 18 files；`data/market.sqlite` LFS + ingest 脚本/证据；**无** `config/`、`universe` 名册、`src/` 策略 |

## LFS / 备份（诚实边界）

| 项 | 独立结果 |
| --- | --- |
| base `data/market.sqlite` oid | `79ba7780f7f5304d189bc49bd7dda9ff1e6325c88888165d71a0c9fae7c26a52`（Reviewer 对 LFS 对象文件 SHA256 一致） |
| after oid | `0245876256527dda58145c770d75f342e7514b74a8c2cf1213fecfb713bf72f8`（同上） |
| `market-before.sqlite`（gitignore） | **仓库内不可检索**；无法证明 Dev 本机备份字节与运行时刻完全一致 |
| 实际用于比对的 before 库 | **base commit 的 LFS preimage**（`.git/lfs/objects/79/ba/79ba7780…`）；与 evidence 中 oid 一致时可重建 cited before，**不等于**「已验收本地 `cp` 文件」 |

## 自动断言（`pr361-ingest-verify.py`）

复算：`python3 -I operations/reviews/pr361-ingest-verify.py` → `pr361-ingest-verify.json`；**非** Dev 单测绿条替代。

| 类别 | 观测 / 断言 |
| --- | --- |
| `PRAGMA integrity_check` | before / after 均为 `ok` |
| LFS SHA256 | 与上表 oid 一致 |
| `bars` 行数 | before **1,200,716**；after **1,203,606**（+**2,890**） |
| preimage 交集 | 全列相等 **1,200,716**；变更 **0** |
| 新增 | DJIA raw **667**（`v6_gapfill_fred`）；DWRTF raw **2223**（`v6_gapfill_cnbc` **2222** + `v6_gapfill_tv` **1**） |
| 序列 raw 计数 | DJIA **8515→9182**；DWRTF **4752→6975** |
| `sqlite_master` | 表/索引/trigger/view 名称集相同；**sql 逐字 diff 0**（含 `bars_one_source`） |
| `calendar` / `universe` / `meta` | **全行内容 SHA256** before=after（非仅行数） |
| 边界行 | DJIA `2024-02-01` `eastmoney_index` 38519.84；DWRTF `2017-11-22` `d37_r6` 275.66 — 未改 |
| `2024-12-25` | DJIA/DWRTF 行数 **0** |
| DJIA/DWRTF raw `MAX(date)` | 均为 **2026-09-30** |
| 其他 raw 码 `MAX(date)` | **EURCNY/JPYCNY** 仍为 **2026-11-06**（before/after 相同；非本 PR 延伸） |
| 非 DJIA/DWRTF 的 max 漂移 | **0** 个 code |

## 点位对照（独立 **original raw**，不用 Dev normalizer 作签收依据）

| 序列 | 参考源 | 范围 | 核对方式 |
| --- | --- | --- | --- |
| DJIA 新增 | `incoming/v6-us-gapfill/raw/fred-DJIA.csv` | 2024-02-02…2026-09-30，**667 日全量** | DB `close` vs FRED；**0 差** |
| DWRTF 新增 | CNBC 归档 `incoming/v6-us-gapfill/raw/cnbc-dwrtf/*.json`（`tradeTime[:8]`→日期，与 gapfill compare 一致） | 2017-11-24…2026-09-30，**2223 日全量** | DB vs JSON raw；**0 差** |
| `2023-04-06` | TV 归档 CSV `theme-道琼斯美国精选REIT指数-tradingview.csv` | 单日 | `v6_gapfill_tv` 259.56 |
| `2019-08-12` | sidecar `source_conflict` | 单日 | 入库 **294.58** `v6_gapfill_cnbc`（TV 294.46 仅对照，不推测成因） |
| 月末 | 新增日集合上派生 | DJIA **32** / DWRTF **107** | 月末子集点位 **0 差** |
| 抽样 | 首/中/尾 + 步进 | 见 JSON `sample_checks` | 含在上述全量核对内 |

**说明**：`normalized/dwrtf-cnbc.csv` 仅在 JSON 中作 **diagnostic**（`dev_normalized_vs_reviewer_cnbc_raw`）；与 Reviewer 自解析 CNBC JSON **0 不一致**，但签收链路以 **JSON→DB** 为准。

## sidecar

`operations/evidence/v6-us-raw-index-ingest/date-flags.csv`（PR361 树内 `git show ce058680:…`）两行与 DB 采用价一致；SHA256 见 JSON `sidecar_date_flags`。

## 建议结论（Coordinator）

脚本 `verdict_hint`：**`APPROVE_INGEST`**（`blockers`: **[]**，以上断言为据）。

未执行：R1b / appendix；未发 GitHub formal review/comment/merge。

## 本 companion PR NET（仅 3 个 reviews 路径）

- `operations/reviews/2026-11-24-pr361-us-gapfill-ingest-signoff.md`
- `operations/reviews/pr361-ingest-verify.py`
- `operations/reviews/pr361-ingest-verify.json`