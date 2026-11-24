# DJIA 与 DWRTF 的授权 raw 价格日线已追加

两条序列的最后日期都是 2026-09-30。DJIA 新增 667 行，DWRTF 新增 2223 行。2024-12-25 没有入库。

## Metadata

- Project: ETF_Rotation_Quant
- Task: v6 US raw index ingest
- Date: 2026-11-24
- Owner: project owner
- Route: direct-execute
- Source of truth: Owner 2026-11-24 21:21 Asia/Taipei 授权，以及 AGENTS.md

## Goal / Summary

Owner 2026-11-24 21:21（Asia/Taipei）授权把来源存档里的价格缺口写入 `data/market.sqlite`。本次只追加两条 `adj='raw'` 序列的新交易日，不覆盖已有行，不计算收益，不改配置、名册、931743 或 LOCK。

交易日沿用 `scripts/v6_us_gapfill_compare.py` 的定义：工作日，并且不在与 FRED 空白工作日对齐的 `NYSE_FULL_CLOSE` 里。实际条数由这份日历和库里的已有日期算出来，没有把名单截成事先给出的数字。计算结果与 Owner 的预期相同。

| 序列 | 全窗交易日 | 库里已有 | 新写入 | 新写入起止 | 写入前行数 | 写入后行数 |
| --- | ---: | --- | ---: | --- | ---: | ---: |
| DJIA | 668（2024-02-01 至 2026-09-30） | 2024-02-01 | 667 | 2024-02-02 至 2026-09-30 | 8515 | 9182 |
| DWRTF | 2224（2017-11-22 至 2026-09-30） | 2017-11-22 | 2223 | 2017-11-24 至 2026-09-30 | 4752 | 6975 |

全库 `bars`：1,200,716 → 1,203,606，增加 2,890。其余代码合计 1,187,449 行，行数指纹没有变。

## Scope / Changes

写入来源：

| 序列 | 来源标签 | 行数 | 起 | 止 | 收盘字段 |
| --- | --- | ---: | --- | --- | --- |
| DJIA | `v6_gapfill_fred` | 667 | 2024-02-02 | 2026-09-30 | FRED `DJIA` 收盘 |
| DWRTF | `v6_gapfill_cnbc` | 2222 | 2017-11-24 | 2026-09-30 | CNBC `.DWRTF` 未复权收盘 |
| DWRTF | `v6_gapfill_tv` | 1 | 2023-04-06 | 2023-04-06 | 已存档 TradingView 259.56 |

新行的开、高、低、量、额都是空。已有行仍是原来的来源：DJIA 为 `eastmoney_index`，DWRTF 为 `d37_r6`。2024-02-01 的 DJIA 收盘仍是 38519.84，2017-11-22 的 DWRTF 收盘仍是 275.66。

`bars_one_source` 不允许同一条 `(code, adj)` 再写入另一个 `source`。授权来源标签和这条触发器冲突，而且 DWRTF 的新日期里本来就要有 CNBC 与 TradingView 两个标签。写入事务里先卸下这条触发器、插入授权行、再用同一条 SQL 建回去。提交后的 `sqlite_master` 与写入前一致，备份库与现库的 schema 文本也一致。最早一行的来源没有改，之后若再插入第三种来源，触发器仍会拒绝。

两个日期标记写在 sidecar `operations/evidence/v6-us-raw-index-ingest/date-flags.csv`，没有给表加列。2019-08-12 的差异只记录数值，不写成因。

| 日期 | 标记 | 采用 | 对照 |
| --- | --- | --- | --- |
| 2023-04-06 | `single_source` | TradingView 259.56，`v6_gapfill_tv` | CNBC 没有这一天 |
| 2019-08-12 | `source_conflict` | CNBC 294.58（原始记号 294.5800），`v6_gapfill_cnbc` | TradingView 294.46；绝对差 0.12，相对差 4.075256401549e-04（约 0.0408%） |

2024-12-25 是伪交易日。CNBC 当天收盘与 2024-12-24 相同（DJIA 43297.0300，DWRTF 294.9400）。这一天不在交易日日历里，也没有写入库。

重叠窗在写入前核对过，收盘与库逐日相同：DJIA 与 FRED 为 2023-11-01 至 2024-02-01 的 63 天；DWRTF 与 CNBC 为 2017-08-01 至 2017-11-22 的 81 天。

## Validation

备份是写入前静默库的字节复制，SHA256 与当时的 live 文件、base `05e39c5650acb52e0de8632bcaef8e6d05fe5597` 的 Git LFS oid 相同。`*.sqlite` 被忽略，仓库里保留的是哈希记录；Reviewer 用 base 的 LFS 对象复现写入前的库。

| 项 | 值 |
| --- | --- |
| 备份路径 | `operations/evidence/v6-us-raw-index-ingest/market-before.sqlite` |
| 备份字节 | 348901376 |
| SHA256 写入前 | `79ba7780f7f5304d189bc49bd7dda9ff1e6325c88888165d71a0c9fae7c26a52` |
| SHA256 写入后 | `0245876256527dda58145c770d75f342e7514b74a8c2cf1213fecfb713bf72f8` |
| 已有行指纹 | `7cc298d9e8ed2f17ca565ac0b6f38710eeb85d3b4ae4e7f53ea228a422b2849c`（1,200,716 行） |
| 其他代码行数指纹 | `d0e0ab6ad834c9834091b662f7cf06683a39f138f6fb422faa5f644995391901`（1,187,449 行） |
| 写入时间 | 2026-11-24T21:45:53+08:00 |

写入后再次用备份库计算已有行指纹，与现库去掉 2,890 个新主键后的指纹相同。`PRAGMA integrity_check` 为 `ok`。没有 `-wal`、`-shm` 或 `-journal`。

月末对照覆盖 DJIA 32 个月末、DWRTF 107 个月末。抽样 DJIA 22 天、DWRTF 24 天，都包含各自的新起点、2026-09-30，以及 DWRTF 的两个标记日和伪日两侧的 2024-12-24、2024-12-26。库内收盘与采用来源的点位差为 0。DJIA 月末相对 FRED 的最大点位差：CNBC 1.153952969169e-07（2024-02-29），Yahoo 4.958229237174e-08（2024-04-30），新浪为 0。这是收盘点位差，不是收益。

```bash
python3 -I scripts/v6_us_raw_index_ingest.py
python3 -I scripts/v6_us_raw_index_read.py
python3 -m unittest tests.data.test_v6_us_raw_index_ingest tests.data.test_v6_us_gapfill_coverage
```

复查时入库状态为 `complete`，问题列表为空。9 个测试通过。两条序列的最后日期都是 2026-09-30，新写入的收盘里没有 2024-12-25。

## Decision / Next Steps

`config/`、`data/universe.csv`、`incoming/v6-us-gapfill/` 和两份旧的 DWRTF 价格文件没有改。原始下载的 SHA256 记在 `unchanged-inputs.sha256`。

本记录交给独立 Reviewer 复算。不合并。下游 R1b 复核要等本 PR 独立复核并合并之后；本次不开始 R1b。
