# v5 大类草稿与看板上市日列名

## Metadata

- Project: ETF_Rotation_Quant
- Task: Dev 两项并行：`config/v5/classes.csv` 草稿；数据看板列名改为「上市日（不含流动性门槛）」
- Date: 2026-11-01
- Owner: project owner
- Route: direct-execute
- Source of truth: PR #145 分支 `claude/v5-prereg-draft` 上的 `docs/prereg/etf-multiasset-rotation-prereg-v5.md` §3.2（未改该 PR）；`config/v3/universe.toml`；`config/v4/universe.toml`；数据看板脚本

## 目标

按草案 §3.2 给 v4 池每个容器一个大类，只看跟踪指数或业绩比较基准。看板 `buy_first` 列改成「上市日（不含流动性门槛）」，并写明它和引擎「首次可持有日」的差别。

## 范围

池子与数据看板同一份：`config/v3/universe.toml` 里 `arm = main` 的 102 个容器，加上 `config/v4/universe.toml` 里已入库的 11 个美股行业 SPDR 和 4 个恒生分类价格指数，共 117 个。2016 年以后才出现的容器留在表里。

没有放进表的行：

- v3 的 S2 臂 16 个容器。那是次要臂，不在看板的 v4 池里。
- `config/v4/universe.toml` 里的 `otc-*`、`qdii-*`。它们是载体，已经按跟踪指数并进 v3 容器。
- 汇率、取不到的序列、标普 500 行业全收益的空序列，以及 `sp500-60`。`sp500-60` 是房地产价格指数的取数记录，池内对应容器是 `us-xlre`。
- T4 的 15 个容器写进了草稿。草案 §3.1 说 B0 不加这 15 个；§3.2 和这次任务要求覆盖整个 v4 池，所以先分类，不拿它们跑规则。

分类只使用指数基本信息、成分交易所权重、基金概况里的跟踪标的或业绩比较基准。中证权重文件日期是 2026-09-30，新交所事实表是 2026-08-31，富时事实表是 2026-09-30。这些文件里若印有收益，没有用来分类，也没有抄进仓库。没有跑任何 v5 规则，没有算组合收益，没有写 LOCK，没有动标签，没有改 #145，没有改 `src/`，没有改 `docs/owner/data-board.md`。

## 分类结果

`config/v5/classes.csv` 111 行：A 股 17、港股 51、美股 28、其他海外 8、商品 3、国债 2、黄金 1、现金 1。

`config/v5/classes-unclassified.csv` 6 行，留给 Orchestrator 裁定：

| 容器 | 原因 |
| --- | --- |
| theme-中证韩交所中韩半导体指数 | 中证半导体15与 KRX 半导体15等权重，内地和韩国各 50%，没有唯一最大市场 |
| theme-iEdge Emerging Asia Select 50 Index | 可在当地或美国上市；前十不足以判定哪一个上市市场权重大 |
| theme-标普中国新经济行业指数 | A 股在调整日上限 15%，香港、美国、新加坡之间的权重没有公布 |
| theme-标普全球石油指数 | 全球石油股票指数，不是原油期货；国家权重这次没有取到 |
| theme-MSCI China Value Weighted Index | 基准是价值加权指数，样本跨 A 股、H 股和 ADR；没有该指数自己的上市市场权重 |
| theme-中信证券印度ETP指数 | 基准是海外上市、跟踪印度的 ETP，ETP 上市地和底层股票上市地都没有权重 |

需要复核时优先看这几行已分类、但不靠指数名称就能看出来的结果：

- 中证全球中国教育主题：2026-09-30 沪深权重 57.04%，归 A 股。
- 三条海外中国互联网和中证全球中国互联网：香港权重大于美国，归港股。
- 新交所泛东南亚科技：2026-08-31 事实表前十里美国上市已占 43.07%，其余任一上市地即使加上表外全部剩余权重仍更低，归美股。
- 富时亚太低碳精选：国家/市场权重里日本 36.80% 最大，归其他海外。
- 标普 500 能源、标普油气勘探及生产、道琼斯美国石油开发与生产、能源 SPDR：股票指数，归美股，不归商品。
- 巴克莱美国综合债券：海外债券，归其他海外，不归国债。

## 看板

`results/v4/diag/data-board/build_data_board.py` 把输出列 `buy_first` 改名为「上市日（不含流动性门槛）」。`summary.json` 增加 `listing_date_note`。图 `docs/assets/data-board/d1-pool-growth.png` 的右图标题和脚注使用同一名称，并写了 theme-HSSCITI：看板 2025-08-25（520840），引擎首次可持有日 2025-11-25。

重跑后 117 行日期与改名前的 `buy_first` 逐行相同。`theme-HSSCITI` 仍是 2025-08-25。年末个数仍是 2015 年合计 33、截至 2026-09-30 合计 108。库指纹仍是 `167d4e39ffab4302e6f55d2b3436b3400ea28b2282cd7f9b9bda644d87c1acf3`。`buy_by_year` 这个键名保留，含义改为按新列累计。

## 验证

1. 池内 117 个容器恰好落在两张表之一，没有重复，`source_url` 都以 `http` 开头。
2. 看板重跑后，除列名和说明字段外，容器起止日与改名前一致。
3. 没有执行 v5 策略，没有计算收益。

## 下一步

Reviewer 按草案 §3.2 逐行核对 `classes.csv`。6 个未分类容器等 Orchestrator 裁定后才能定稿。本表是草稿，不是冻结稿。
