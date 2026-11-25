# 来源与命令

观察日：2026-11-25（Asia/Taipei）。下载发生在当天 UTC 03:36–03:45 左右。

生成表：

```bash
python3 -I scripts/build_census_tables.py
```

脚本只使用标准库。它不打印指数水平、价格、净值、收益率或回报。

## 已提交的原始利率文件

这些 CSV 含有利率数值，只作日期覆盖的原始凭证。普查正文不引用数值。

| 文件 | SHA256 | 字节 |
| --- | --- | --- |
| raw/ecb/estr-wt.csv | 6d948d22a80a08a072e34a52813045cc938a1770c615db647ee06498aede665d | 568475 |
| raw/ecb/preestr-wt.csv | c2b6d258fc43ba729f684b478843bddc484d0af7c7f8dd948b39b613ebbe2cc1 | 364439 |
| raw/ecb/eonia-rate.csv | e3dab718d57b468346ac7639480d47800fc73215cc6575fb840308dc14481cd8 | 2543761 |
| raw/ecb/yc-aaa-10y.csv | 0413399fc8fb4f5a2e4414eb6d1b64f910d994abe76f69696cbf48bc35b94300 | 3187080 |
| raw/ecb/yc-all-10y.csv | e8844aee3391b8d72d098dec3559af98c64da0d858d205b6c785d538e60893a2 | 3219905 |
| raw/bbk/de10y.csv | 793cb4218b3d651e9571a7f39a26623eb4918380c9aef77ecdc07cd76f582f1e | 200225 |
| raw/mof/jgbcme_all.csv | 56e7dcc459fd46d94de920ecbb76a3df3c9832f157c5fac5c61410e2eec06548 | 1197657 |
| raw/mof/jgbcme.csv | 563752534fe82fe77d1d2f65f495fadbd3d7ab1663c7ac444235a33e636a1fbd | 1753 |

下面的 URL 是下载地址。

- €STR：`https://data-api.ecb.europa.eu/service/data/EST/B.EU000A2X2A25.WT?format=csvdata`
- 预发布 €STR：`https://data-api.ecb.europa.eu/service/data/MMSR/B.U2._X._Z.S12._Z.U.BO.WT.D76.MA._Z._Z.EUR._Z?format=csvdata`
- EONIA 利率：`https://data-api.ecb.europa.eu/service/data/EON/D.EONIA_TO.RATE?format=csvdata`。说明页 `https://data.ecb.europa.eu/data/datasets/EON/data-information`
- AAA 10 年即期：`https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y?format=csvdata`
- 全部欧元区债 10 年即期：`https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_C.SV_C_YM.SR_10Y?format=csvdata`
- 曲线说明：`https://www.ecb.europa.eu/stats/financial_markets_and_interest_rates/euro_area_yield_curves/html/index.en.html`
- 德国 10 年期联邦债券：`https://api.statistiken.bundesbank.de/rest/data/BBSSY/D.REN.EUR.A630.000000WT1010.A?format=csv&lang=en`，页面 `https://www.bundesbank.de/en/statistics/money-and-capital-markets/interest-rates-and-yields/daily-yields-of-current-federal-securities-772220`
- 日本国债历史：`https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv`
- 日本国债当月：`https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv`
- 定义：`https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/qa.htm`

## 用过但未提交的标识来源

这些页面或文件含有表现、净值、权重或价格，或者只是整站 HTML。标识已经抽进 `tables/`。不把原页面提交进仓库。

| 用途 | URL | 本地文件 SHA256（未提交） |
| --- | --- | --- |
| STOXX 代码、发布日、基准日 | `https://www.stoxx.com/documents/stoxxnet/Documents/Resources/Data_Vendor_Codes/vendor_codes_sheet.csv` | 54bd39122c489604aa3016d6981cc6960654d3b3dd28f7cb825b8a8633a02310（6554775 字节） |
| 20 个超级行业与 3 个遗留行业的定义 | `https://www.stoxx.com/document/Indices/Common/Indexguide/stoxx_index_guide.pdf`（2026 年 11 月版，第 7.4、7.5、7.8 节） | 未单独记录；文本抽取后只引用了方法句子 |
| ICB 20 个超级行业名称 | `https://www.stoxx.com/documents/stoxxnet/Documents/Resources/Methodology/Sector_Classification_ICB/New_ICB_category_table_Dec_2019.xlsx`，入口页 `https://www.stoxx.com/sector-classification-changes` | 未提交 |
| iShares 筛选器 | `https://www.ishares.com/varnish-api/blk-product-screener-server/api/v1/product-screener/product-data?country=de&language=de&siteName=de-ishares-v2&userType=individual` | 含净值与回报字段，未提交 |
| iShares 产品页 | `https://www.ishares.com` + 筛选器里的 `productPageUrl` | 含历史净值图，未提交 |
| TOPIX 事实表 2026-10-30 | `https://www.jpx.co.jp/english/markets/indices/factsheets/files/e_001_fac2_TOPIX.pdf` | 含表现与权重，未提交 |
| TOPIX-17 一览 | `https://www.jpx.co.jp/english/markets/indices/factsheets/files/e_000_fac2_sector.pdf` | 未提交 |
| 行业与 TOPIX-17 计算 | `https://www.jpx.co.jp/english/markets/indices/line-up/files/e_cal2_13_sector.pdf` | 方法文本，未提交 |
| JPX ETF 上市表 | `https://www.jpx.co.jp/english/equities/products/etfs/issues/01.html` | 未提交 |
| NEXT FUNDS | `https://nextfunds.jp/en/lineup/<code>/`，code 为 1306、1615、1617–1633 | 页面含场内价格与净值，未提交 |
| 日本银行无担保隔夜 | `https://www.boj.or.jp/en/statistics/market/short/mutan/index.htm` | 只有逐日 xlsx 和格式表，没有完整历史，未提交 |
| 欧洲央行政策利率页 | `https://www.ecb.europa.eu/stats/policy_and_exchange_rates/key_ecb_interest_rates/html/index.en.html` | 未找到 CSV，未提交 |

指数许可与学术数据入口（说明水平历史不是匿名免费文件）：`https://www.stoxx.com/index-licensing`，`https://www.stoxx.com/academic-data`。
