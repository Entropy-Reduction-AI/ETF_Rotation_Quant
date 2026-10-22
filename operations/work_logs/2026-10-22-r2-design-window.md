# R2 续（二）：窗口前无效行丢弃，刻画后停止

## Metadata

- Project: ETF_Rotation_Quant
- Task: R2 续（二）：处理窗口前的无效行，跑完 R2
- Date: 2026-10-22
- Owner: project owner
- Route: direct-execute
- Source of truth: 本任务说明、`docs/prereg-v1-implementation-notes.md` G 节补充二、`docs/etf-rotation-prereg-v1.md` §13

## Goal / Summary

按 G 节补充二，无效价在 I-29 里当作没有真实 K 线。先定 `window_start`，只有 date ≥ window_start 的无效行才阻断全池；窗口前的无效行丢弃并写入 build-report。全量测试 293 项通过后，在冻结提交上打完数据包、建完面板、通过 check，并跑了设计期刻画。刻画判定分不开，已写 STOP。没有跑 design、oos、rolling，没有 `OOS_LOCK.json`。V1 不成立，转 R4。

代码冻结提交 `cb8fe7b09253208fba157195c2fefbf3eb76d2b3`。先合入 `origin/main` 的 `bff2c0d`（合并提交 `75327a4`），不 rebase，不 force push。

## Scope / Changes

- `src/data/ohlc_rules.py`：`invalid_points` 标出收盘或开高低为 0、负数、非有限数的字段。空着仍按缺口，不算无效。
- `src/data/quality.py`：`_annotate_container` 先用真实 K 线定窗口，再把窗口前的无效行放进 `discarded_invalid`，窗口内的无效行设 `blocks_pool`。来源不符、海外、基准、日历门禁未改。
- `src/indicators/build.py`：窗口前的无效行不进入指标；窗口内的无效行仍拒绝建面板。`discarded_invalid_rows` 写入 build-report。
- 单元测试两条：窗口前的 0 收盘被丢弃并记入报告，不阻断；窗口内的 0 收盘仍然阻断。
- 没有改 I-01～I-29 的原文、F 节、Params、`docs/prereg-v1-implementation-notes.md`。

## market.sqlite

本轮没有写库。SHA256 保持 `e013b960b9d77cbb78a10116e3c50b61bf0b81ad63247afeb67316fa54cee961`。`source_db_matches_commit` 为 true。

## 命令

工作目录 `/workspace`，解释器 `.venv/bin/python`。时刻为 Asia/Taipei。

| 命令 | 退出码 | 耗时 | 备注 |
| --- | --- | --- | --- |
| `mkdir -p outputs && .venv/bin/python -m unittest discover -s tests -t .` | 0 | 88.841s | Ran 293 tests，OK |
| `.venv/bin/python -m src.data package --end 2026-09-30` | 0 | 5.598s | 87 条序列；content SHA256 `14023c1450a4b85f40de5c045aa3397d2575a26b211ad6bd6b0ab926c4589a1d`。打包时刻 2026-10-22 16:29 |
| `.venv/bin/python -m src.data verify outputs/research-package-2026-09-30.sqlite` | 0 | 1.983s | 通过 |
| `.venv/bin/python -m src.indicators build --package outputs/research-package-2026-09-30.sqlite` | 0 | 70.751s | 116667 行、33 个容器。报告时刻 2026-10-22 16:30 |
| `.venv/bin/python -m src.research.prereg_v1.run check --panel outputs/panel-2026-09-30.sqlite` | 0 | 0.612s | 断档与报告一致 |
| `.venv/bin/python -m src.research.prereg_v1.run characterize --panel outputs/panel-2026-09-30.sqlite` | 0 | 0.612s | 分不开，写出 STOP |
| design / oos / rolling | 未执行 |  | STOP 之后不进回测 |

## 窗口与丢弃行

进入 V1 的 33 个容器里，21 个有设计期样本，12 个只进样本外。不进的是化工（I-29(4)，缺口延伸到 2026-09-30）、国债（I-29(4)，没有真实 K 线）、纳指科技、恒生科技（没有研究序列）。逐容器的 `window_start` 在预注册 §13.1。

`discarded_invalid_rows`：

| 容器 | 日期 | 字段 | 值 |
| --- | --- | --- | --- |
| T06 半导体 | 2013-06-28 | close | 0.0 |
| T10 软件/信创 | 2013-06-28 | close | 0.0 |

化工 2013-06-28 的收盘 0.0 在终点缺口内，`window_start` 为空，不记入丢弃表，也不阻断全池。

## 刻画

可进减非可进 −0.0027967007961813045，95% 区间 −0.007457688124801519 到 +0.0019274534975742613，44 个季度块，`separable = false`。没有查看 2016-01-01 之后的收益、信号或 R 倍数。

## 复核

在冻结提交 `cb8fe7b` 的干净 checkout 上重跑上述 package、verify、build、check、characterize。`characterize.json` 逐字节一致。没有 `design.json`。面板文件 SHA256 `65e9b335494a8b7737b247db40c1d531d7ab7ea6d2ae76f182887f645a04f0fc` 与面板 content SHA256 `400b7110a1b17a11dac818fdb578d0053e624ff2b3aea99f45168cda57f872d6` 都一致。数据包 content SHA256 一致；文件 SHA256 因打包时刻不同而是 `5361de7ec911fc25c24ed5de93eb98e5f1015461eef81686bcabba3e3e409562`。

`git grep -n OOS_LOCK -- results/` 无结果。

## Decision / Next Steps

V1 不成立，转 R4。合入 main 等复核和 Owner。不在这次跑样本外。
