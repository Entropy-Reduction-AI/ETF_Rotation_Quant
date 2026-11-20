# D37-R6 fetch targets (36)

Delivery: this folder only. No DB writes, no git branch.

CSV per container: date, close (native currency, raw levels, no FX).
Need: official launch date (screenshot; else 未核对), source URL, download time Asia/Taipei.
Window needed: launch date → first listed fund + 30 trading days.
Ingest threshold is Dev's job; here we still try to get official daily + a second source when official is missing.

Priority A: first_list >= 2016-01-01 (30)
Priority B last: first_list < 2016-01-01 (6) — chinext, theme-S&P 500 Energy Sector Index(NTR), theme-恒生中国企业指数, theme-标普全球石油指数, theme-标普石油天然气勘探及生产精选行业指数, theme-法兰克福DAX指数

## G1 Hang Seng (INdex360 official daily = second source; East Money already has one)

| priority | container_id | index_code | first_list |
| A | theme-HSFML25 | HSFML25 | 2025-10-13 |
| A | theme-HSISC | HSISC | 2025-06-09 |
| A | theme-HSSC50 | HSSC50 | 2025-11-25 |
| A | theme-HSSCAMHI | HSSCAM | 2026-05-15 |
| A | theme-HSSCHKY | HSSCHKY | 2021-05-20 |
| A | theme-HSSCITI | HSSCITI | 2025-08-19 |
| A | theme-HSSCPB | HSSCPB | 2025-07-07 |
| A | theme-HSSCSOY | HSSCSOY | 2024-01-05 |
| A | theme-HSSCT | HSSCT | 2022-02-09 |
| A | theme-恒生中国央企指数 | HSCSOE | 2024-04-19 |
| A | theme-恒生创新药指数 | HSIDI | 2024-12-27 |
| A | theme-恒生生物科技指数 | HSBIO | 2021-10-19 |
| B | theme-恒生中国企业指数 | HSCEI | 2010-10-28 |

## G2 S&P DJI (Export → Historical after free register)

| priority | container_id | index_code | first_list |
| A | theme-标普500信息科技指数 | SP500-45 | 2016-12-27 |
| A | theme-标普500医疗保健等权重指数 | SP5HEW | 2016-12-14 |
| A | theme-标普500消费精选指数 | SP500-25 | 2024-02-02 |
| A | theme-标普生物科技精选行业指数 | SPSIBI | 2016-12-27 |
| A | theme-道琼斯美国石油开发与生产指数 | DJSOEP | 2017-03-17 |
| A | theme-道琼斯美国精选REIT指数 | DJUSRE | 2017-11-24 |
| A | theme-标普美国品质消费股票指数 |  | 2016-04-06 |
| A | theme-标普中国新经济行业指数 |  | 2020-10-23 |
| A | theme-SPAHLVCP | SPAHLVCP | 2023-12-08 |
| B | theme-S&P 500 Energy Sector Index(NTR) |  | 2015-02-17 |
| B | theme-标普全球石油指数 |  | 2012-05-02 |
| B | theme-标普石油天然气勘探及生产精选行业指数 |  | 2012-06-08 |

## G3 other

| priority | container_id | index_code | first_list | note |
| A | theme-MSCI China Value Weighted Index |  | 2016-01-04 | msci.com EOD after register |
| A | theme-MSCI USA 50 Index |  | 2023-11-17 | msci.com EOD after register |
| A | theme-富时亚太低碳精选指数 |  | 2022-12-30 | lseg.com/ftse-russell |
| A | theme-富时沙特阿拉伯指数 |  | 2024-07-16 | lseg.com/ftse-russell |
| A | theme-iEdge Emerging Asia Select 50 Index |  | 2025-02-20 | SGX |
| A | theme-新交所泛东南亚科技指数 | ASIATECN | 2023-12-01 | SGX |
| A | theme-东证指数 | TPX | 2019-06-25 | JPX monthly tables, JPY |
| A | theme-巴西IBOVESPA指数 | BVSP | 2025-11-13 | dailies already OK; need BRL FX only |
| B | theme-法兰克福DAX指数 |  | 2014-09-05 | stoxx.com or dax-indices.com |

## G4 domestic

| priority | container_id | index_code | first_list | note |
| A | soymeal |  | 2019-12-05 | DCE 豆粕期货价格指数 only; not East Money 豆粕加权 |
| B | chinext | 399006 | 2011-12-09 | cnindex or SZSE; do not use tencent series in DB |
