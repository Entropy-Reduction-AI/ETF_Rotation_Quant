# PR361 入库独立复核（Reviewer · 非 GitHub formal review）

## 锚点

| 项 | 值 |
| --- | --- |
| PR | [#361](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/361) |
| **签收 head** | `ce058680fabec19b12982bffce37e891808d4641` |
| base（359+360 已并） | `05e39c5650acb52e0de8632bcaef8e6d05fe5597` |
| 改动 | 18 files；`data/market.sqlite` LFS + ingest 脚本/证据；**无** `config/`、`universe` 名册、`src/` 策略 |

## LFS / 备份

| 项 | 独立结果 |
| --- | --- |
| base `data/market.sqlite` oid | `79ba7780f7f5304d189bc49bd7dda9ff1e6325c88888165d71a0c9fae7c26a52`（字节校验一致） |
| after oid | `0245876256527dda58145c770d75f342e7514b74a8c2cf1213fecfb713bf72f8`（字节校验一致） |
| `market-before.sqlite`（gitignore） | **仓库内不可检索**；`backup.txt` 写明与 base LFS oid 相同，**权威 preimage = base commit LFS 对象**（Reviewer 用 `.git/lfs/objects/79/ba/79ba7780…` 实库比对） |

## `sqlite_master`（含 `bars_one_source`）

- before/after：**表/索引/trigger/view 名称集合相同**；各对象 `sql` **逐字一致**（含 `bars_one_source`）。
- 代码（`scripts/v6_us_raw_index_ingest.py`）在写入事务内 **DROP → 插入授权行 → 用同一 SQL 建回** trigger；提交后 schema 与 before 一致（独立 diff 为 0）。

## 行级 preimage（非作者 fingerprint）

| 检查 | 结果 |
| --- | --- |
| before `bars` 行数 | 1,200,716 |
| after `bars` 行数 | 1,203,606（+2,890） |
| 同 `(code,adj,date)` 交集且 **全列相等** | **1,200,716** |
| 交集内变更 | **0** |
| 新增 | **2,890**（DJIA raw **667**，DWRTF raw **2223**） |
| `(code,adj,date)` 重复键 | **0** |
| `calendar` / `universe` / `meta` 行数 | 与 before 相同 |

边界未改：

| 键 | source | close |
| --- | --- | --- |
| DJIA 2024-02-01 | `eastmoney_index` | 38519.84 |
| DWRTF 2017-11-22 | `d37_r6` | 275.66 |

`2024-12-25` 上 DJIA/DWRTF 行数：**0**。

## 来源与 Owner 标记（sidecar + DB）

标记在 `operations/evidence/v6-us-raw-index-ingest/date-flags.csv`（**非 DB 列**）：

| 日期 | 标记 | 入库采用 |
| --- | --- | --- |
| 2023-04-06 | `single_source` | `v6_gapfill_tv` 259.56 |
| 2019-08-12 | `source_conflict` | `v6_gapfill_cnbc` 294.58（对照 TV 294.46；**不推测成因**） |

DB 内 DWRTF raw 同时存在历史 `d37_r6` 与新 `v6_gapfill_*` **按日期分段**；属写入时卸 trigger 的授权拼接，**非**同一 `(code,date,adj)` 双行。

## 点位对照（独立，对归档 **raw**，非 Dev 测试）

复算：`python3 -I operations/reviews/pr361-ingest-verify.py` → `pr361-ingest-verify.json`

- DJIA 新增：`v6_gapfill_fred` vs `incoming/v6-us-gapfill/raw/fred-DJIA.csv`，2024-02-02…2026-09-30，**月末 + ≥24 抽样 + 全日新增行**：**0 差**
- DWRTF 新增：CNBC 归档对 `normalized/dwrtf-cnbc.csv`；`2023-04-06` 对 TV 归档 259.56；**月末 107 + 抽样**：**0 差**

（收盘价点位差，**不是**收益。）

## 建议结论（Coordinator）

**APPROVE PR361 入库** — 独立阻塞项：**无**（以上表为据；非“测试绿=通过”替代）。

未执行：R1b / appendix 脚本；正式 GitHub review/comment/merge。

## 本 companion PR NET

`operations/reviews/2026-11-24-pr361-us-gapfill-ingest-signoff.md`  
`operations/reviews/pr361-ingest-verify.py`  
`operations/reviews/pr361-ingest-verify.json`