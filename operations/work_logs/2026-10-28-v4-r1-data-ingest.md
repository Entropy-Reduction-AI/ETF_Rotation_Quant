# v4-R1 数据采集

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R1 数据采集（② 标的池，D13-1）
- Date: 2026-10-28
- Owner: project owner
- Route: direct-execute
- Source of truth: `operations/planning/2026-10-28-v4-dev-plan.md`；`operations/planning/2026-10-28-d13-owner-decisions.md`

## Goal / Summary

只新增容器和行情。没有运行 v4 候选，没有计算 2016-01-01 及之后的组合收益，也没有把价格复权。

`data/market.sqlite` 写入前 SHA256 `3e3e6f1d594586da2abf28db5fa88b05c1cc91fa29adf061fc699e1b8d4bc1d6`。写入后 SHA256 `a130af9eab11368d71488ee48f83bb71952d17eb5abd1d5bcc00d1cd6993f1e6`（129429504 字节）。`PRAGMA integrity_check` 为 `ok`。没有 `-wal` / `-shm`。

哨兵序列在写入前后一致：`H00300` 5283 行、`USDCNY` 5043 行、`510300` 3488 行、`HSI` 6592 行、`^SP500TR` 6726 行。原有 bars 668746 行未改。`universe` 仍是 39 行，`cash_dividends` 仍是 104 行。`config/v3/universe.toml` 和 `data/universe.csv` 没有改。新容器在 `config/v4/universe.toml`。

作业 `run_id` 16 在汇率请求被 403 拒绝时记为 `error`（当时 ETF 和港股分类指数已经提交）。修正请求后 `run_id` 17 为 `ok`，补上 `HKDCNY` 并写出覆盖表。时区：交易日按来源的交易日原样存储；`fetched_at` 为 UTC。截止日与库内研究序列对齐，都是 2026-09-30。

## Scope / Changes

- `src/v4/data/`：Yahoo 未复权日线、分红、拆分；中国货币网 `CcprHisNew`；腾讯港股指数。已有 `code` 不更新。
- `data/market.sqlite`：新 `bars` 与新表 `v4_event`。不写 `cash_dividends`。
- `results/v4/inventory/coverage.csv`：每条序列一行，含 SHA256。
- `results/v4/inventory/spotcheck.csv`：`XLB`、`HSF`、`HKDCNY` 各 5 个日期。
- `results/v4/inventory/crosscheck.csv`：`XLB`、`XLK`、`XLF` 对 CNBC 的 2026 年 5 个收盘价。
- `config/v4/universe.toml`：新增容器。`status=unavailable` 的序列没有行情行。

序列内容 SHA256 的算法在 `src/v4/data/parse.py` 的 `series_sha256`：按日期升序，`date,open,high,low,close,volume`，空值为空串，浮点 `.10g`，UTF-8，行末换行。复核：`.venv/bin/python -m src.v4.data hash CODE`。

## 已入库

价格都是未复权收盘。ETF 跟踪有权重上限的 Select Sector 指数，不是无上限的标普 500 行业指数。

| 代码 | 口径 | 起 | 止 | 行数 |
| --- | --- | --- | --- | --- |
| XLB XLE XLF XLI XLK XLP XLU XLV XLY | 价格，USD | 1998-12-22 | 2026-09-30 | 各 6985 |
| XLRE | 价格，USD | 2015-10-08 | 2026-09-30 | 2760 |
| XLC | 价格，USD | 2018-06-19 | 2026-09-30 | 2082 |
| SP500-60 | 价格，不是全收益 | 2001-10-09 | 2026-09-30 | 6284 |
| HSF HSU HSC | 价格，HKD | 1992-04-01 | 2026-09-30 | 8515 / 8514 / 8514 |
| HSP | 价格，HKD | 1993-01-04 | 2026-09-30 | 8325 |
| HSFGTR HSUGTR HSPGTR | 全收益，HKD | 2021-04-23 | 2026-09-30 | 各 1339 |
| HSCGTR | 全收益，HKD | 2021-04-22 | 2026-09-30 | 1340 |
| HKDCNY | 中间价，1 港元兑人民币 | 2006-01-04 | 2026-09-30 | 5043 |

分红在 `v4_event`（`kind=dividend`），11 只 ETF 都有，最早 1999-03-19。拆分：`XLB` `XLE` `XLK` `XLU` `XLY` 为 2025-12-05 的 2:1；`XLF` 为 2016-09-19 的 1231:1000。价格序列没有做拆分调整。

GICS：房地产在美东 2016-08-31 收盘后独立（MSCI/S&P 2015-03-13 公告）。通信服务在 GICS Direct 于美东 2018-09-28 收盘后生效；标普道琼斯指数在 2018-09-24 开盘实施（2018-09-04 公告）。`XLRE` 成立日 2015-10-07，首根 K 线 2015-10-08。`XLC` 成立日 2018-06-18，首根 K 线 2018-06-19。九只老 SPDR 的成立日按 1998-12-16，首根 K 线都是 1998-12-22。

`HKDCNY` 与库内 `USDCNY` 用同一个接口。解析核对：2006-01-04 的美元中间价仍是 8.0702，然后才写入港币。2005 年该接口 `total=0`。

## 取不到（交 Orchestrator）

1. **标普 500 的 11 个行业全收益指数**（`^SP500-10TR` … `^SP500-60TR`）没有日线。Yahoo 能解析名称和当日点位，`validRanges` 只有 `1d`/`5d`，按日期拉取为空。Stooq 是脚本挑战页，标普官网 403。影响：不能做 ≤2015 的 ETF 与官方行业全收益的对照。备选：向标普道琼斯买历史；或以后用已经入库的未复权收盘、分红和拆分自行还原 ETF 全收益（本次没有还原）。唯一入库的行业指数是房地产**价格**指数 `SP500-60`（`^SP500-60`），2016-08-31 之前不是拆分后的房地产行业。
2. **恒生综合行业指数 12 个**已按指数目录（2026-03-31）登记发布日和基日 2000-01-03，日线没有公开接口。Yahoo 404，腾讯无代码，恒生公司日线是付费订阅。目录、2026-08 事实表（行业指数 2006-09-11、回溯至基日）和数据产品手册（可选消费、必需消费、医疗保健写 2019-09-09）的发布日不一致，覆盖表采用目录日期。影响：不能按 12 个恒生行业分类与美股 11 个 GICS 行业对齐。已入库的替代是恒生指数四个分类指数（金融、公用、地产、工商）的价格，以及它们的总收益。价格从 1992/1993 起，早于官方首个点日 1984-01-13 和发布日 1985-01-02 的缺口来自腾讯，没有回补。总收益只从 2021-04 起，覆盖不了 2006–2015。四个分类指数比恒生综合行业粗，也不与 GICS 一一对应。
3. **HKD/CNY 早于 2006-01-04** 在这个中间价接口里没有。2006 年以前的港股价格不能用这条序列换人民币。

## Validation

- 单元测试 `tests/v4/data/test_ingest.py`：10 项通过。覆盖 Yahoo/货币网解析、序列 SHA256、拒绝改写已有代码、缺失的全收益指数不入库、拒绝 2026-10-01 之后的截止日、命令行拒绝 `returns`/`backtest`。
- CNBC 与 Yahoo 收盘：`XLB`、`XLK`、`XLF` 在 2026-01-05、2026-03-31、2026-06-30、2026-08-31、2026-09-30 共 15 对。绝对差最大约 6e-6，是小数位，不是另一个价格。
- 抽查表 `results/v4/inventory/spotcheck.csv`。例如 `XLB` 2026-09-30 收盘 48.70，`HSF` 2026-09-30 收盘 55364.46，`HKDCNY` 2006-01-04 中间价 1.0408。

## Decision / Next Steps

Reviewer 可以按 `spotcheck.csv` 的 3 个序列 × 5 个日期，用另一个来源核对收盘。分红和拆分在 `v4_event`。取不到的三条需要 Orchestrator 决定要不要换源，本次没有用替代序列冒充官方全收益或恒生综合行业指数。
