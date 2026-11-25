# 欧洲 / 日本数据覆盖普查（只记日期与来源）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: evidence
- Status: census, not a market selection
- Date: 2026-11-25
- Time zone: Asia/Taipei
- Task: D42-5 / D42-9 市场候选的覆盖普查。不选市场，不算收益，不给信号。

这是一份覆盖表。欧洲不是一个主权，德国债和欧元区曲线分开记。指数的基准日不是免费日频文件的第一天。ETF 的净值不是指数历史。

## 结论

免费、可核对的日频文件只出现在利率上，而且只能数到文件里的首尾日期和行数，不能据此说交易日缺口为零。股票指数和 ETF 的代码、发布日、基准日、上市日多数能从指数公司或基金公司页面核对；它们的日频行情首尾和缺口，这次没有免费的完整日期清单，标为未找到或未核实。

欧洲现行 20 个超级行业里，德国 iShares 产品名单上对得上名称的有 16 个。另外 4 个（Consumer Products and Services、Energy、Food Beverage and Tobacco、Personal Care Drug and Grocery Stores）没有同名 ETF。Oil & Gas、Food & Beverage、Personal & Household Goods 仍有 ETF，但它们是 2020 年 9 月以前的遗留超级行业，不能当成上面 4 个新行业的替代。同一张 iShares 页面上，基金目标写的是价格收益（Preisindex），对照指数又写成 Capped TR 或 Capped NET。两套字符串没有并成一个 STOXX 代码。

## 观察日与计数边界

- 观察与下载日：2026-11-25（Asia/Taipei）。HTTP 响应时间在 UTC 2026-11-25 03:36–03:45 一带。
- 利率文件内部的最后日期早于或等于这个观察日，见利率表。那不是“缺口为零”。
- 交易日缺口：没有把日期清单和一份独立的假期日历对齐。全部标未核实。文件内部已经标成缺失的行，单独计数，不叫做交易日缺口。
- 机器表：`tables/europe_indexes.csv`、`tables/europe_etfs.csv`、`tables/japan_etfs_nomura.csv`、`tables/japan_etfs_jpx.csv`、`tables/rates_coverage.csv`。
- 生成：`python3 -I scripts/build_census_tables.py`。脚本只打印代码、日期、行数和状态码。

计数：

| 类 | 行数 | 已核实 | 未核实或未找到 |
| --- | --- | --- | --- |
| 欧洲指数（基准 + 20 个现行超级行业 + 3 个遗留行业，EUR 的 Price / Net / Gross） | 72 | 代码、ISIN、发布日、基准日、收益类型、日历名称 | 免费日频水平文件、首尾日期、交易日缺口、成交量 |
| 欧洲 iShares 份额（德国个人投资者筛选器，名称含 STOXX 与 600） | 27 | ISIN、成立日、份额类型、页面上的对照指数字符串、上市地与上市日 | 行情首尾、缺口、成交量；对照指数字符串与 STOXX 代码的对应 |
| 日本 TOPIX-17 ETF（NEXT FUNDS） | 17 | 代码、ISIN、对照指数名称、上市日（基金页与 JPX 上市表一致） | 行情首尾、缺口、成交量；指数本身的 vendor code |
| 利率文件 | 7 条已下载 | 文件内首尾日期与行数 | 相对 TARGET2 / 交易所日历的缺口；日本无担保隔夜与 TONA 的完整日频文件 |

## 欧洲指数

来源是 STOXX 2026-11-25 可下载的 vendor code sheet（方法指南 2026 年 11 月版第 7.4 节指定用这张表查基准日）。指南第 7.5 节写明：2020 年 9 月评估起，STOXX Europe 600 按 ICB 分成 20 个超级行业。指南第 7.8 节写明 Food and Beverage、Personal and Household Goods、Oil and Gas 以原名和原代码继续作为遗留指数。这三只不是 20 个现行超级行业的别名。

这 72 行的共同字段：货币 EUR；加权方式 FreeFloat MarketCap Weighted；发布日历名称 STOXX Europe Calendar。ESMA 字段只有基准的三只（SXXP / SXXR / SXXGR）是 `Yes (significant)`，其余 69 行是 `No`。这是表上的字段，不是本普查对监管身份的判断。

免费日频指数水平：vendor sheet 只有标识，没有水平。指数许可页、学术数据申请页和日终数据页没有给出可匿名下载的完整日频水平文件。事实表含有表现图，本次没有用它当历史。所以这 72 行的日频首尾、缺口、成交量都是未找到或未核实。基准日和发布日不能当成覆盖区间。

旧行业的价格和净收益，发布日多为 1998-06-15、基准日 1991-12-31；全收益发布日 2010-01-18、基准日 2000-12-31。全收益更短，不能用价格指数的基准日代替。2020-09-21 才发布的四只新超级行业，价格、净收益、全收益的发布日和基准日都是 2020-09-21 与 2010-09-17。

指南第 7.5 节还描述了一套 30%/15% 上限的超级行业指数，并说它们是单独的指数。vendor sheet 里这 72 个名称都没有 Capped 或 30-15。上限版的代码未在这张表上用这两个词找到，标未核实，不把下面的代码说成上限版。

| 角色 | 官方名称 | Price 代码 / 发布日 / 基准日 | Net 代码 | Gross 代码 / 发布日 / 基准日 |
| --- | --- | --- | --- | --- |
| 基准 | STOXX Europe 600 | SXXP / 1998-06-15 / 1991-12-31 | SXXR | SXXGR / 2010-01-18 / 2000-12-31 |
| 现行 | Automobiles & Parts | SXAP / 1998-06-15 / 1991-12-31 | SXAR | SXAGR / 2010-01-18 / 2000-12-31 |
| 现行 | Banks | SX7P / 1998-06-15 / 1991-12-31 | SX7R | SX7GR / 2010-01-18 / 2000-12-31 |
| 现行 | Basic Resources | SXPP / 1998-06-15 / 1991-12-31 | SXPR | SXPGR / 2010-01-18 / 2000-12-31 |
| 现行 | Chemicals | SX4P / 1998-06-15 / 1991-12-31 | SX4R | SX4GR / 2010-01-18 / 2000-12-31 |
| 现行 | Construction & Materials | SXOP / 1998-06-15 / 1991-12-31 | SXOR | SXOGR / 2010-01-18 / 2000-12-31 |
| 现行 | Consumer Products and Services | S600CPP / 2020-09-21 / 2010-09-17 | S600CPR | S600CPGR / 2020-09-21 / 2010-09-17 |
| 现行 | Energy | S600ENP / 2020-09-21 / 2010-09-17 | S600ENR | S600ENGR / 2020-09-21 / 2010-09-17 |
| 现行 | Financial Services | SXFP / 1998-06-15 / 1991-12-31 | SXFR | SXFGR / 2010-01-18 / 2000-12-31 |
| 现行 | Food Beverage and Tobacco | S600FOP / 2020-09-21 / 2010-09-17 | S600FOR | S600FOGR / 2020-09-21 / 2010-09-17 |
| 现行 | Health Care | SXDP / 1998-06-15 / 1991-12-31 | SXDR | SXDGR / 2010-01-18 / 2000-12-31 |
| 现行 | Industrial Goods & Services | SXNP / 1998-06-15 / 1991-12-31 | SXNR | SXNGR / 2010-01-18 / 2000-12-31 |
| 现行 | Insurance | SXIP / 1998-06-15 / 1991-12-31 | SXIR | SXIGR / 2010-01-18 / 2000-12-31 |
| 现行 | Media | SXMP / 1998-06-15 / 1991-12-31 | SXMR | SXMGR / 2010-01-18 / 2000-12-31 |
| 现行 | Personal Care Drug and Grocery Stores | S600PDP / 2020-09-21 / 2010-09-17 | S600PDR | S600PDGR / 2020-09-21 / 2010-09-17 |
| 现行 | Real Estate | SX86P / 2008-09-22 / 2000-12-29 | SX86R | SX86GR / 2010-01-18 / 2008-09-19 |
| 现行 | Retail | SXRP / 2004-09-20 / 1991-12-31 | SXRR | SXRGR / 2010-01-18 / 2000-12-31 |
| 现行 | Technology | SX8P / 1998-06-15 / 1991-12-31 | SX8R | SX8GR / 2010-01-18 / 2000-12-31 |
| 现行 | Telecommunications | SXKP / 1998-06-15 / 1991-12-31 | SXKR | SXKGR / 2010-01-18 / 2000-12-31 |
| 现行 | Travel & Leisure | SXTP / 2004-09-20 / 1991-12-31 | SXTR | SXTGR / 2010-01-18 / 2000-12-31 |
| 现行 | Utilities | SX6P / 1998-06-15 / 1991-12-31 | SX6R | SX6GR / 2010-01-18 / 2000-12-31 |
| 遗留 | Food & Beverage | SX3P / 1998-06-15 / 1991-12-31 | SX3R | SX3GR / 2010-01-18 / 2000-12-31 |
| 遗留 | Oil & Gas | SXEP / 1998-06-15 / 1991-12-31 | SXER | SXEGR / 2010-01-18 / 2000-12-31 |
| 遗留 | Personal & Household Goods | SXQP / 2004-09-20 / 1991-12-31 | SXQR | SXQGR / 2010-01-18 / 2000-12-31 |

ISIN、Bloomberg、Reuters 在 `tables/europe_indexes.csv`。房地产全收益的基准日是 2008-09-19，和价格收益的 2000-12-29 不是同一天。

不要并进去的邻近指数：`STOXX Europe 600 Real Estate Cap`（S8730P，发布 2006-03-01）不是 SX86P。`Financials ex Banks` 和行业级 30-15 指数也不是这 20 个超级行业。

## 欧洲 ETF

来源：iShares 德国个人投资者产品筛选器（`de-ishares-v2`，2026-11-25）以及每个产品页。筛选器给出 ISIN、成立日、份额是分红（ausschüttend）还是累积（thesaurierend）。产品页给出对照指数（Vergleichsindex）、目标句子里的指数名称，以及各交易所的上市日。页面上有 “Historische NAVs / Historische Preise” 图表控件。本次没有下载这些序列，所以行情首尾和缺口未核实。成立日和上市日不是行情文件的第一行。

同一页上的两套指数字符串经常不一致。目标句子写 `(Preisindex)`，对照指数写 `(Capped) TR`、`(Capped) NET` 或 `(Capped) TR - Net`。vendor sheet 里的普通超级行业名称没有 Capped。本普查不把 ETF 配到某一个 STOXX 代码上。

Xetra 上分红份额的上市日，老的行业 ETF 多为 20110602，早于这个日期的是基金成立日，不是这条 Xetra 上市记录。每只基金还有伯尔尼或瑞士等其他上市，日期不同，见 CSV 的 listings 列。

| 基金名称里的行业 | Xetra 分红份额 | ISIN | 成立日 | Xetra 上市日 | 与 20 个现行超级行业 | 页面上的口径冲突 |
| --- | --- | --- | --- | --- | --- | --- |
| 基准 Europe 600（德国） | EXSA | DE0002635307 | 20040213 | 20050411 | 基准，不是行业 | 目标：Preisindex；对照：STOXX Europe 600 Index (EUR) |
| Automobiles & Parts | EXV5 | DE000A0Q4R28 | 20020708 | 20110602 | 名称对齐 | 目标 Preisindex；对照 (Capped) TR (EUR) |
| Banks | EXV1 | DE000A0F5UJ7 | 20010425 | 20110602 | 名称对齐 | 目标 Preisindex；对照 (Capped) NET |
| Basic Resources | EXV6 | DE000A0F5UK5 | 20020708 | 20110602 | 名称对齐 | 目标 Preisindex；对照 (Capped) TR -Net |
| Chemicals | EXV7 | DE000A0H08E0 | 20020708 | 20110602 | 名称对齐 | 目标 Preisindex；对照 (Capped) TR - Net |
| Construction & Materials | EXV8 | DE000A0H08F7 | 20020708 | 20110602 | 名称对齐 | 目标 Preisindex；对照 (Capped) TR |
| Financial Services | EXH2 | DE000A0H08G5 | 20020708 | 20110602 | 名称对齐 | 目标 Preisindex；对照 (Capped) TR -Net |
| Health Care | EXV4 | DE000A0Q4R36 | 20010425 | 20110602 | 名称对齐 | 目标 Preisindex；对照 (Capped) TR |
| Industrial Goods & Services | EXH4 | DE000A0H08J9 | 20020708 | 20110602 | 名称对齐 | 目标 Preisindex；对照 (Capped) TR -Net |
| Insurance | EXH5 | DE000A0H08K7 | 20020708 | 20110602 | 名称对齐 | 目标 Preisindex；对照 (Capped) TR |
| Media | EXH6 | DE000A0H08L5 | 20020708 | 20110602 | 名称对齐 | 目标 Preisindex；对照 (Capped) TR |
| Real Estate | EXI5 | DE000A0Q4R44 | 20060919 | 20110602 | 名称对齐 | 目标 Preisindex；对照 (TR) Index - Net，页面未写 Capped |
| Retail | EXH8 | DE000A0H08P6 | 20020708 | 20110602 | 名称对齐 | 目标 Preisindex；对照 (Capped) TR - Net |
| Technology | EXV3 | DE000A0H08Q4 | 20010425 | 20110602 | 名称对齐 | 目标 Preisindex；对照 (Capped) TR (EUR) |
| Telecommunications | EXV2 | DE000A0H08R2 | 20010425 | 20110602 | 名称对齐 | 目标 Preisindex；对照 (Capped) TR |
| Travel & Leisure | EXV9 | DE000A0H08S0 | 20020708 | 20110602 | 名称对齐 | 目标 Preisindex；对照 (Capped) TR - Net |
| Utilities | EXH9 | DE000A0Q4R02 | 20020708 | 20110602 | 名称对齐 | 目标 Preisindex；对照 (Capped) TR |
| Food & Beverage | EXH3 | DE000A0H08H3 | 20020708 | 20110602 | 遗留名称，不是 Food Beverage and Tobacco | 目标 Preisindex；对照 Food and Beverage (Capped) TR - Net |
| Oil & Gas | EXH1 | DE000A0H08M3 | 20020708 | 20110602 | 遗留名称，不是 Energy | 目标 Preisindex；对照 (Capped) TR |
| Personal & Household Goods | EXH7 | DE000A0H08N1 | 20020708 | 20110602 | 遗留名称，不是 Personal Care Drug and Grocery Stores | 目标 Preisindex；对照 (Capped) TR -Net |
| Consumer Products and Services | 未找到 |  |  |  | 筛选器无同名产品 |  |
| Energy | 未找到 |  |  |  | 筛选器无同名产品 |  |
| Food Beverage and Tobacco | 未找到 |  |  |  | 筛选器无同名产品 |  |
| Personal Care Drug and Grocery Stores | 未找到 |  |  |  | 筛选器无同名产品 |  |

另外的份额，不是上表的替代，细节在 CSV：

- 基准还有德国累积 EXIE（DE000A2QP4B6，成立 20230223，Xetra 20230227），以及爱尔兰分红 STT6（IE0004YCLDW1，成立 20260508）和爱尔兰累积 E600（IE000XSFZL82，成立 20260805）。后两只的对照指数字符串是 `Stoxx Europe 600 Net TR`，目标句子里没有抽出 Preisindex。
- 累积份额还有汽车 EXHG（20220406）、银行 T05B（20261014）、科技 STEC（20220406）。
- `iShares STOXX Europe 600 Top 20 UCITS ETF (DE)`（EXW3，DE0005933949）对照指数是 `STOXX Europe 600 Top 20 Net Index`，Xetra RIC 为 `STX50EX.DE`。名称、对照指数和 RIC 对不齐。不计入超级行业，也不当成 Europe 600 基准。

成交量：未核实。没有把 ETF 净值当成指数历史。

## 日本指数

TOPIX 事实表日期是 2026-10-30，计算说明是 JPX 的 TOPIX 与行业指数指南。

| 指数 | 收益类型 | 基准日 | 发布方式（文件原文） | 代码 | 免费日频文件 |
| --- | --- | --- | --- | --- | --- |
| TOPIX | Price | 1968-01-04，基点 100 | 实时（每秒） | 事实表 Vendor Code 表里有 Bloomberg / Refinitiv / QUICK 代码；pdftotext 列对齐未完全核实，不在此锁定 PR/TR/NTR | 未找到。行情经 Market Information System 与 Index Data Service 分发 |
| TOPIX | Total return 与 Net total return | 1989-01-04（事实表写明基点不是 100；具体基点留在原表，这里不抄水平） | 只有收盘 | 同上，列对齐未完全核实 | 未找到 |

事实表上能看见、但列对齐不算核对完成的代码碎片：Bloomberg 一侧有 TPX、TPXDDVD、TPXNTR；Refinitiv 一侧有 .TOPX、.TOPXDV、.TOPXDVNET；QUICK 一侧有 N151/T、S151/TSX、S151、#NR/TSE。以 PDF 原表为准。

TOPIX-17 是把 TOPIX 成分按证券代码委员会 33 个行业收成 17 类。计算指南写明：系列基准日 2002-12-30，基点 100；同时计算价格收益和全收益；价格收益约每 15 秒经 Market Information System 分发，全收益只分发收盘；日频指数数据走 Index Data Service，使用需要 JPXI 许可。各行业的 Quick / Bloomberg 代码在已读的事实表和计算指南里未找到。日频首尾和缺口未核实。33 个行业指数的基准日不同（一部分 1992-01-06，其余 1968-01-04），那是 33 行业，不是这 17 类。

| # | TOPIX-17 名称（计算指南） | 价格 / 全收益 | 基准日 | 对应 NEXT FUNDS（见下节） |
| --- | --- | --- | --- | --- |
| 1 | FOODS | 两种都有 | 2002-12-30 | 1617 |
| 2 | ENERGY RESOURCES | 两种都有 | 2002-12-30 | 1618 |
| 3 | CONSTRUCTION & MATERIALS | 两种都有 | 2002-12-30 | 1619 |
| 4 | RAW MATERIALS & CHEMICALS | 两种都有 | 2002-12-30 | 1620 |
| 5 | PHARMACEUTICAL | 两种都有 | 2002-12-30 | 1621 |
| 6 | AUTOMOBILES & TRANSPORTATION EQUIPMENT | 两种都有 | 2002-12-30 | 1622 |
| 7 | STEEL & NONFERROUS METALS | 两种都有 | 2002-12-30 | 1623 |
| 8 | MACHINERY | 两种都有 | 2002-12-30 | 1624 |
| 9 | ELECTRIC APPLIANCES & PRECISION INSTRUMENTS | 两种都有 | 2002-12-30 | 1625 |
| 10 | IT & SERVICES, OTHERS | 两种都有 | 2002-12-30 | 1626 |
| 11 | ELECTRIC POWER & GAS | 两种都有 | 2002-12-30 | 1627 |
| 12 | TRANSPORTATION & LOGISTICS | 两种都有 | 2002-12-30 | 1628 |
| 13 | COMMERCIAL & WHOLESALE TRADE | 两种都有 | 2002-12-30 | 1629 |
| 14 | RETAIL TRADE | 两种都有 | 2002-12-30 | 1630 |
| 15 | BANKS | 两种都有 | 2002-12-30 | 1631 |
| 16 | FINANCIALS (EX BANKS) | 两种都有 | 2002-12-30 | 1632 |
| 17 | REAL ESTATE | 两种都有 | 2002-12-30 | 1633 |

成分行业的对照在计算指南原文里，不在这张表重复。指数代码：未找到。

## 日本 ETF

NEXT FUNDS 英文产品页与 JPX 上市 ETF 表交叉。17 只 TOPIX-17 的上市日两边都是 2008-03-25（基金页写 2008年03月25日，JPX 写 Mar. 25, 2008），交易所是东京证券交易所，管理公司是 Nomura。对照指数名称是对应的 Total Return Index。基金每年 7 月 15 日分配一次，所以场内价格不是全收益指数本身。行情首尾、缺口、成交量未核实。没有把净值当成指数。

JPX 表对 1623 写成 `TOPIX-17 STEEL & NONFERROUS Total Return Index`，基金页是 `TOPIX-17 STEEL & NONFERROUS METALS Total Return Index`。代码同为 1623。1626 在 JPX 表少一个空格（`SERVICES,OTHERS`）。字符串不完全相同，没有改写成一个官方代码。

| 代码 | ISIN | 官方名称 | 页面写的对照指数 | 上市日 | 分配 |
| --- | --- | --- | --- | --- | --- |
| 1617 | JP3046560003 | NEXT FUNDS TOPIX-17 FOODS ETF | TOPIX-17 FOODS Total Return Index | 2008-03-25 | 每年 7 月 15 日 |
| 1618 | JP3046570002 | NEXT FUNDS TOPIX-17 ENERGY RESOURCES ETF | TOPIX-17 ENERGY RESOURCES Total Return Index | 2008-03-25 | 每年 7 月 15 日 |
| 1619 | JP3046580001 | NEXT FUNDS TOPIX-17 CONSTRUCTION & MATERIALS ETF | TOPIX-17 CONSTRUCTION & MATERIALS Total Return Index | 2008-03-25 | 每年 7 月 15 日 |
| 1620 | JP3046590000 | NEXT FUNDS TOPIX-17 RAW MATERIALS & CHEMICALS ETF | TOPIX-17 RAW MATERIALS & CHEMICALS Total Return Index | 2008-03-25 | 每年 7 月 15 日 |
| 1621 | JP3046600007 | NEXT FUNDS TOPIX-17 PHARMACEUTICAL ETF | TOPIX-17 PHARMACEUTICAL Total Return Index | 2008-03-25 | 每年 7 月 15 日 |
| 1622 | JP3046610006 | NEXT FUNDS TOPIX-17 AUTOMOBILES & TRANSPORTATION EQUIPMENT ETF | TOPIX-17 AUTOMOBILES & TRANSPORTATION EQUIPMENT Total Return Index | 2008-03-25 | 每年 7 月 15 日 |
| 1623 | JP3046620005 | NEXT FUNDS TOPIX-17 STEEL & NONFERROUS METALS ETF | TOPIX-17 STEEL & NONFERROUS METALS Total Return Index | 2008-03-25 | 每年 7 月 15 日 |
| 1624 | JP3046630004 | NEXT FUNDS TOPIX-17 MACHINERY ETF | TOPIX-17 MACHINERY Total Return Index | 2008-03-25 | 每年 7 月 15 日 |
| 1625 | JP3046640003 | NEXT FUNDS TOPIX-17 ELECTRIC APPLIANCES & PRECISION INSTRUMENTS ETF | TOPIX-17 ELECTRIC APPLIANCES & PRECISION INSTRUMENTS Total Return Index | 2008-03-25 | 每年 7 月 15 日 |
| 1626 | JP3046650002 | NEXT FUNDS TOPIX-17 IT & SERVICES, OTHERS ETF | TOPIX-17 IT & SERVICES, OTHERS Total Return Index | 2008-03-25 | 每年 7 月 15 日 |
| 1627 | JP3046660001 | NEXT FUNDS TOPIX-17 ELECTRIC POWER & GAS ETF | TOPIX-17 ELECTRIC POWER & GAS Total Return Index | 2008-03-25 | 每年 7 月 15 日 |
| 1628 | JP3046670000 | NEXT FUNDS TOPIX-17 TRANSPORTATION & LOGISTICS ETF | TOPIX-17 TRANSPORTATION & LOGISTICS Total Return Index | 2008-03-25 | 每年 7 月 15 日 |
| 1629 | JP3046680009 | NEXT FUNDS TOPIX-17 COMMERCIAL & WHOLESALE TRADE ETF | TOPIX-17 COMMERCIAL & WHOLESALE TRADE Total Return Index | 2008-03-25 | 每年 7 月 15 日 |
| 1630 | JP3046690008 | NEXT FUNDS TOPIX-17 RETAIL TRADE ETF | TOPIX-17 RETAIL TRADE Total Return Index | 2008-03-25 | 每年 7 月 15 日 |
| 1631 | JP3046700005 | NEXT FUNDS TOPIX-17 BANKS ETF | TOPIX-17 BANKS Total Return Index | 2008-03-25 | 每年 7 月 15 日 |
| 1632 | JP3046710004 | NEXT FUNDS TOPIX-17 FINANCIALS (EX BANKS) ETF | TOPIX-17 FINANCIALS (EX BANKS) Total Return Index | 2008-03-25 | 每年 7 月 15 日 |
| 1633 | JP3046720003 | NEXT FUNDS TOPIX-17 REAL ESTATE ETF | TOPIX-17 REAL ESTATE Total Return Index | 2008-03-25 | 每年 7 月 15 日 |

基准和容易混淆的相邻产品，不从上面 17 只里替换：

| 代码 | ISIN | 名称 | 对照指数（页面原文） | 上市日 | 说明 |
| --- | --- | --- | --- | --- | --- |
| 1306 | JP3027630007 | NEXT FUNDS TOPIX Exchange Traded Fund | TOPIX Total Return Index | 2001-07-13 | JPX 表同日、同一对照指数。每年 7 月 10 日分配 |
| 1615 | JP3040170007 | NEXT FUNDS TOPIX Banks Exchange Traded Fund | TOPIX Banks Total Return Index | 2002-04-03 | 不是 1631。对照的是 TOPIX Banks，不是 TOPIX-17 BANKS |

JPX 上市表里，对照指数写成 `TOPIX Total Return Index` 的还有别人的 ETF（1305、1473、1475、2524、2625、630A 等），对照指数只写成 `TOPIX` 的有 1308、1348、2557。这些是候选，不是选定的工具。全表在 `tables/japan_etfs_jpx.csv`。TOPIX-17 这 17 个代码在该表里只有 Nomura 一行。

## 利率

欧洲没有单一主权债。下面四组不要合成一条“欧洲国债”。

| 序列 | 它是什么 | 免费/付费 | 文件内第一天 | 文件内最后一天 | 行数 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- |
| ECB 全部欧元区国债收益率曲线，10 年即期 | `YC.B.U2.EUR.4F.G_N_C.SV_C_YM.SR_10Y`。标题：All euro area yield curve - 10-year spot rate。欧元区中央政府欧元债，含全部信用档，不是德国单券 | 免费 API | 2004-09-06 | 2026-11-23 | 5680，状态均为 A，频率标记 B | 未核实。页面写明日频从 2004-09-06 起，与文件第一天一致，仍不能推出中间无缺口 |
| ECB AAA 欧元区国债收益率曲线，10 年即期 | `YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y`。标题：AAA yield curve - 10-year spot rate。只含 AAA 档欧元区中央政府债 | 免费 API | 2004-09-06 | 2026-11-23 | 5680，状态均为 A | 未核实 |
| 德国联邦银行：当前 10 年期联邦债券日收益率 | `BBSSY.D.REN.EUR.A630.000000WT1010.A`。页面原文 Daily yield of the current 10 year federal bond。单位 PROZENT。这是当前这只 10 年期联邦债券的收益率，不是欧元区曲线，也未在页面上写成恒定期限合成利率 | 免费 CSV | 2001-10-01 | 2026-11-24 | 日期行 9186；其中有值 6388；标成 `.` 且说明 No value available 的 2798。文件更新时间 2026-11-24 12:26:29 | 未核实。2798 是文件自己标的空值，没有对照德国交易日历 |
| 日本财务省国债利率，10 年列 | 问答页：按收盘（15:00）JSDA 参考统计价格计算的半年复利、恒定期限利率，下一营业日 09:30 公布 | 免费 CSV | 10 年列有值从 1986/7/5 起。文件从 1974/9/24 就有行，更早的 10 年列是 `-` | 历史总表最后一天 2026/10/30。当月文件 `jgbcme.csv` 的 10 年列覆盖 2026/11/2 至 2026/11/24，共 15 行有值 | 历史总表 13330 行；10 年列有值 9969；为 `-` 或空 3361 | 未核实。两份文件没有接成一条再对交易所日历 |

短端，欧元与欧洲央行，仍然不是德国国内利率：

| 序列 | 定义（页面或文件标题） | 访问 | 文件内首尾 | 行数 | 缺口 |
| --- | --- | --- | --- | --- | --- |
| €STR | `EST.B.EU000A2X2A25.WT`。Euro short-term rate, volume-weighted trimmed mean。单位百分比。频率 Daily - businessweek | 免费 API | 2019-10-01 至 2026-11-23 | 1831，状态均为 A | 未核实 |
| 预发布 €STR | `MMSR.B.U2._X._Z.S12._Z.U.BO.WT.D76.MA._Z._Z.EUR._Z`。Pre-Euro Short-Term Rate - Volume-weighted trimmed mean rate | 免费 API | 2017-03-15 至 2019-09-30 | 649，状态均为 A | 未核实。与 €STR 的日期首尾相邻，没有做日历衔接 |
| EONIA | `EON.D.EONIA_TO.RATE`。数据门户写明：门户界面不提供，只能走 API；本次 API 可下。数据集更新时间 2022-01-04 09:15 CET。文件标题写明隔夜利率按欧元短端利率加 8.5 个基点的固定点差计算。方法页写明 2019-03-14 的建议之后，自 2019-10-02（交易日 2019-10-01）起 EMMI 把 EONIA 改成 €STR 加固定点差，点差用 2018-04-17 至 2019-04-16 的日数据测算。频率说明为 TARGET2 营业日 | 免费 API，门户界面不可下 | 1999-01-04 至 2021-12-31 | 5890，状态均为 A | 未核实。没有另找到更晚的免费文件 |
| 欧洲央行政策利率 | 存款便利、主要再融资、边际贷款。页面有定义。这是政策利率，不是 €STR 那种成交利率 | 页面免费。该页没有找到 CSV | 未核实 | 未下载水平 | 未核实 |

日本短端：

| 候选 | 看到的内容 | 完整日频 |
| --- | --- | --- |
| 无担保隔夜拆借利率 | 日本银行逐日公布临时和最终 xlsx。`fcall.xlsx` 是发布格式表，不是历史序列 | 未找到完整历史文件。首尾未核实 |
| TONA 或短端市场利率总表 | 打开了短端市场页和 Short-term Money Market Rates 页，没有定位到可下载的 TONA 日频文件 | 未找到。不猜测起始日 |

成交量：€STR 数据集里另有成交量序列，本次只数了利率那一条的日期，没有读数值。日本国债文件没有成交量列。

## 原始文件

利率 CSV 留在 `raw/ecb/`、`raw/bbk/`、`raw/mof/`，哈希见 `PROVENANCE.md`。这些文件含有利率数值，普查正文不引用数值。

含有行情、净值或表现图的页面和事实表 PDF 只在本地用过，不纳入本次提交，避免把价格路径写进仓库。它们的 URL 在 `PROVENANCE.md`。

## 本次没有做的事

没有计算收益、信号、排名或价格图。没有读项目里已有的回测或 2016 年以后的结果。没有改正式数据库、配置、名单、预注册或规划文件。没有购买数据，也没有登录。缺口都标未核实，没有用首尾日期推断缺口为零。
