# v3 防御资产与海外假日收益

## Metadata

- Project: ETF_Rotation_Quant
- Task: v3 长历史防御资产与海外假日零价
- Date: 2026-10-25
- Owner: project owner
- Route: direct-execute
- Source of truth: `docs/prereg/etf-multiasset-rotation-prereg-v3.md` §3；看板 `operations/planning/phase2-board.md` 于 main `4c6d4b0`

## Goal / Summary

补黄金和中债财富的研究序列，并让美国休市不再变成纳指暴跌。`config/v3/universe.toml` 只由 `python -m src.v3.data emit` 写出。没有手改 toml，没有合入 main，没有打 tag，没有写 `results/v3/LOCK`，没有强推。

分支 `dev/v3-data-defensive-holiday` 从 main `4c6d4b086d28bc58e1ec107210ce1b8125cea4c5` 开出。

## Scope / Changes

- `src/report/fx.py`：美元序列在对齐前丢掉非正收盘。休市占位 0 不再进入人民币点位。沿用的是 §3.3 的最近有效收盘，不是在评估层把无穷填成 0。
- `src/v3/data/defensive.py`：抓取上金所与中债财富，删掉海外来源里收盘 ≤ 0 的行，并在黄金出现超过 60 个日历日的断档时只保留后面那一段。
- `src/v3/data/parse.py`、`src/v3/data/emit_universe.py`：解析编制说明和行情表；名称正好是「中债-10年期国债指数」「中债-5年期国债指数」才写入对应容器。
- 原件在 `incoming/2026-10-25-v3-defensive/`，`MANIFEST.csv` 记 SHA256。
- 审计表 `results/v3/inventory/overseas-holiday-audit.csv`。

## 命令和退出码

| 命令 | 退出码 |
| --- | --- |
| `git fetch origin main` 后从 `4c6d4b0` 建分支 | 0 |
| `.venv/bin/python -m src.v3.data fetch-defensive` | 0 |
| 补 `<th>` 表头的 18 个交易日，并按触发器禁止 UPDATE 的规则用插入加删除改债券代码 | 0 |
| `.venv/bin/python -m src.v3.data emit` | 0 |
| `.venv/bin/python -m unittest discover -s tests -t .` | 见 Validation |
| `PRAGMA integrity_check` | `ok` |

## market.sqlite 与登记表 SHA256

| 文件 | 写入前 | 写入后 |
| --- | --- | --- |
| `data/market.sqlite` | `d0fd3a86785705a90688715d54120f063acf76c00fda7b5338817a47c1919b81` | `3e3e6f1d594586da2abf28db5fa88b05c1cc91fa29adf061fc699e1b8d4bc1d6` |
| `config/v3/universe.toml` | `96592f553b9cc796922312b918ad3bc349766c84baab650032bc5c0a9a6aec8a` | `04ff3572ebd82a5159eaccced0bed5bc3531b732a1b11025f86021ebd0454be0` |
| `results/v3/inventory/coverage.csv` | （emit 重写） | `577125a16c28830f38bb5bbd89ba72179efb848cbe8a725945762db9f4a039b2` |

库仍走 Git LFS。没有 `-wal` / `-shm`。

## 黄金

研究序列 `Au99.99`，来源 `sge_daily`，4402 行，2008-08-11 → 2026-09-30。`series_status = partial`。发布日、基日页面没有给出，登记为「取不到」。

- `https://www.sge.com.cn/graph/Dailyhq?instid=Au99.99`：2016-12-19 起。与库内 2024 年后日行情 240 个重叠日收盘差不超过 0.02，才追加。
- `https://www.sge.com.cn/sjzx/mrhqsj`：更早的文章。合约字段有的写 Au99.99，有的写 Au9999，按表头读收盘，不按列号。重叠日与 Dailyhq 一致，所以并进同一个代码。
- 列表第 374 页止于 2008-08-11，下一页是 2003-04-15，中间没有页。2003-01-02 → 2003-04-15 抓到过，没有留在 `bars` 里。留着的话，对齐后会把约五年的涨跌记成一个交易日。
- 2012-04-13、2016-04-12 的文章没有 Au99.99 / Au9999 行。前后交易日都在，按 §3.3 沿用最近收盘。

缺失 → 对判定的影响：2006-01-04 至 2008-08-10 黄金容器没有研究序列，设计期这一段不参与 U-指数。2008-08-11 之后可以。发布日取不到，引擎不按发布日截断；入库的点是交易所当日行情，不是事后回填的指数。

## 债券

编制说明（中债金融估值中心 PDF，`pdftotext -layout`）里的财富代码和基准日：

| 容器 | 中文名称 | 代码 | 基准日 | 行情 |
| --- | --- | --- | --- | --- |
| `cgb-10y` | 中债-10年期国债指数 | CBA04501 | 2007-12-29 | 4687 行，2008-01-02 → 2026-09-30 |
| `cgb-5y` | 中债-5年期国债指数 | CBA03101 | 2007-12-31 | 4687 行，2008-01-02 → 2026-09-30 |
| 不进池 | 中债-国债总指数 | CBA00601 | 2001-12-31 | 6190 行，2002-01-04 → 2026-09-30 |

查询是中债指数页的财富指标、待偿期总值（`CFZS`，`qxlxt=00`）。时间戳按台北时间落日：`1010073600000` 是 2002-01-04。

名称不是「中债-10年期国债指数」或「中债-5年期国债指数」的，不写入容器。国债总财富因此只出现在 toml 末尾注释。看板第 7 项：对不上就停手，不新开容器，不改预注册。3–5 年、7–10 年这类分段指数也没有拿来顶替。

编制说明写了基准日，以及每个银行间交易日约 18:00 发布。没有单列首次发布日，所以 `publish_date` 仍是「取不到」。

缺失 → 对判定的影响：10 年、5 年容器从 2008-01-02 起有财富指数，2006 和 2007 仍没有，这两年债券不参与 U-指数。发布日取不到时引擎不截断；若 2008 年以后的点里含发布前回填，会进入 R 和 s。国债总财富自 2002-01-04 在库，但不进入排名。要把它放进池，需要 Owner 改预注册（v3.1）。

## 这次没有补上的序列

- 创业板指：中证身份原件没有「创业板指」这个全称。库里已有腾讯 `399006` / `399606`（2010-06-02 起），没有带发布日的身份原件，不用它们当研究序列。缺失 → `chinext` 仍不进 U-指数。执行 ETF 159915 的行情还在。
- 美股人民币全收益：没有找到纳指 100、标普 500 的人民币全收益发布序列。没有把 `XNDX` 或 `^SP500TR` 乘 `USDCNY` 存成新序列。读取时的人民币换算仍是 BM-主那条：A 股交易日 D 用严格早于 D 的美元收盘，再乘 D 当天或之前的中间价。缺失 → 登记表口径仍是 `total_return_usd`。中间价从 2006-01-04 起，更早没有人民币全收益。
- 豆粕、原油超额收益：这次没有新的发布文件，仍是「取不到」。

覆盖：研究 81 条，`ok` 77，`partial` 1（黄金），`gap` 3（创业板指、豆粕、原油）。

## 海外假日

事实：`XNDX` 在 2012-10-29 的收盘、最高、最低都是 0。纽约证券交易所因飓风桑迪于 2012-10-29 和 2012-10-30 休市。库里没有 2012-10-30 这根 K 线。对齐规则用「日期严格早于 D 的最后一根」，于是 A 股 2012-10-30 用了这根 0，人民币日收益是 −100%；下一根有效收盘在 A 股 2012-11-01，收益是 +inf。看板写的约 −16.5% 不是这条对齐算出来的数；存进去的收盘就是 0。

处理：删掉这 1 行（`incoming/2026-10-25-v3-defensive/overseas-zero-close.json`）。`cny_from_usd` 以后再遇到非正收盘也会丢掉，再沿用最近一个正收盘。修完后，同一窗口的人民币收益都是有限数：2012-10-30 为 +0.057%（美元收盘沿用 2012-10-26，只剩中间价变动，`stale=1`），2012-11-01 为 −0.636%。

审计（来源 `nasdaq`、`yahoo`、`tencent_hk_index`、`stooq`、`eia`）：

- 删掉之后，这些来源不再有收盘 ≤ 0。
- 没有「日历间隔超过 4 天且涨跌绝对值 ≥ 15%」的日子。`overseas-holiday-audit.csv` 只有表头。
- `^SP500TR`、`NDX`、`SPX`、`N225`、`BRENT`、`HSI`、`HSTECH` 本来就没有 0 收盘。桑迪那两天标普全收益没有 K 线，对齐后是平盘，不是暴跌。
- 仍能看到的大涨跌是普通交易日，例如 `XNDX` 2008-10-13 约 +12.6%，`HSTECH` 2022-03-16 约 +22.2%，`BRENT` 2020-04-21 约 −24.4%。没有改这些收盘。
- `XNDX` 很多日子最高、最低是 0，收盘是正数。收益只用收盘。没有把最高、最低填成收盘。
- 港股和上金所走 `total_return_close`，非正收盘本来就会跳过。漏洞在美元全收益这条，它以前把原始 K 线直接送进对齐。
- A 股里中证序列原有的 0 收盘没有删。那是另一件事。
- 评估层没有把 NaN 或 inf 填成 0。

## Validation

全量 `unittest discover`：448 项里 1 项失败、1 项跳过。失败的是 `tests/v3/engine/test_l2.py` 把登记表 SHA 钉在上一次 emit。已改成这次 emit 的 SHA 后再跑该项，通过。其余 446 项在改 SHA 之前已经通过。BM-主设计期对照仍在通过之列：删掉的那根收盘不是正数，基准查询本来就要求 `close > 0`。

## Decision / Next Steps

Reviewer 核对 emit 后的 `universe.toml`（SHA 见上）以及黄金、两只国债财富的起止日。国债总财富在库、不在池。创业板指和美股人民币发布序列仍缺。`allocate_container` / `adjust_weights` 和设计期业务简报不在这次。
