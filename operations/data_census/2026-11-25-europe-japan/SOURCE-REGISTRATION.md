# 下载前的来源登记

## Metadata

- Project: ETF_Rotation_Quant
- Document type: evidence
- Status: registered before download
- Date: 2026-11-25
- Time zone: Asia/Taipei
- 身份核对：只做了 HTTP HEAD，没有取正文。核对时间 2026-11-25 17:18（Asia/Taipei，UTC 09:18:54）。

本文件提交并推送之后，才下载净值、分红金额和收益率。本提交里没有这些数值。

## 资格口径（不在这里重算）

D44-1 把断档改成有效年内次数为 0。按 #372 的逐年表，20 只有效年都没有 0 次，全部合格，不启用日本。#372 的旧规则结果（20 只全不合格，EXSA 断档 2005、2006）保留，不覆盖。这是已经看见日期筛查结果之后的规则修正，不是事前没改。

#371 的 STEP3 逐年表和 #372 的有效年次数，有 26 个重叠年份是 4 与 5 对调。两张表都保留，不把其中一张当成原始除息日的独立认证。下载后按本登记来源再数一次。

## 收益率和现金

| 用途 | 序列 | 代码 | 下载 URL | HEAD |
| --- | --- | --- | --- | --- |
| 德国国债 | 当前 10 年期联邦债券日收益率 | `BBSSY.D.REN.EUR.A630.000000WT1010.A` | https://api.statistiken.bundesbank.de/rest/data/BBSSY/D.REN.EUR.A630.000000WT1010.A?format=csv&lang=en | 200，`application/vnd.bbk.data+csv` |
| 说明页 | 同上 | 同上 | https://www.bundesbank.de/en/statistics/money-and-capital-markets/interest-rates-and-yields/daily-yields-of-current-federal-securities-772220 | 200 |
| 现金，至 2019-09-30 | EONIA 利率 | `EON.D.EONIA_TO.RATE` | https://data-api.ecb.europa.eu/service/data/EON/D.EONIA_TO.RATE?format=csvdata | 200，`text/csv` |
| 说明页 | EONIA | `EON` | https://data.ecb.europa.eu/data/datasets/EON/data-information | 200 |
| 现金，自 2019-10-01 | €STR，volume-weighted trimmed mean | `EST.B.EU000A2X2A25.WT` | https://data-api.ecb.europa.eu/service/data/EST/B.EU000A2X2A25.WT?format=csvdata | 200，`text/csv` |
| 说明页 | €STR | 同上 | https://data.ecb.europa.eu/data/datasets/EST/EST.B.EU000A2X2A25.WT | 200 |

不下载成交量。不执行债券财富指数公式。不选 eb.rexx 基金。

## 20 只的净值和分红金额

来源是各份额的 iShares 产品页。页面里的 `navData` 是每日净值，`performance.distributions.table.totalDistribution` 是分红金额，`exDate` 是除息日。HEAD 只确认 URL 仍返回 200，没有重读正文。代码和 ISIN 沿用已提交的 STEP3 表。

| 代码 | ISIN | 产品页 | HEAD |
| --- | --- | --- | --- |
| EXSA | DE0002635307 | https://www.ishares.com/de/privatanleger/de/produkte/251931/ishares-stoxx-europe-600-ucits-etf-de-fund | 200 |
| EXV5 | DE000A0Q4R28 | https://www.ishares.com/de/privatanleger/de/produkte/251932/ishares-stoxx-europe-600-automobiles-parts-ucits-etf-de-fund | 200 |
| EXV1 | DE000A0F5UJ7 | https://www.ishares.com/de/privatanleger/de/produkte/251934/ishares-stoxx-europe-600-banks-ucits-etf-de-fund | 200 |
| EXV6 | DE000A0F5UK5 | https://www.ishares.com/de/privatanleger/de/produkte/251936/ishares-stoxx-europe-600-basic-resources-ucits-etf-de-fund | 200 |
| EXV7 | DE000A0H08E0 | https://www.ishares.com/de/privatanleger/de/produkte/251938/ishares-stoxx-europe-600-chemicals-ucits-etf-de-fund | 200 |
| EXV8 | DE000A0H08F7 | https://www.ishares.com/de/privatanleger/de/produkte/251940/ishares-stoxx-europe-600-construction-materials-ucits-etf-de-fund | 200 |
| EXH2 | DE000A0H08G5 | https://www.ishares.com/de/privatanleger/de/produkte/251942/ishares-stoxx-europe-600-financial-services-ucits-etf-de-fund | 200 |
| EXV4 | DE000A0Q4R36 | https://www.ishares.com/de/privatanleger/de/produkte/251946/ishares-stoxx-europe-600-health-care-ucits-etf-de-fund | 200 |
| EXH4 | DE000A0H08J9 | https://www.ishares.com/de/privatanleger/de/produkte/251948/ishares-stoxx-europe-600-industrial-goods-services-ucits-etf-de-fund | 200 |
| EXH5 | DE000A0H08K7 | https://www.ishares.com/de/privatanleger/de/produkte/251950/ishares-stoxx-europe-600-insurance-ucits-etf-de-fund | 200 |
| EXH6 | DE000A0H08L5 | https://www.ishares.com/de/privatanleger/de/produkte/251952/ishares-stoxx-europe-600-media-ucits-etf-de-fund | 200 |
| EXI5 | DE000A0Q4R44 | https://www.ishares.com/de/privatanleger/de/produkte/251958/ishares-stoxx-europe-600-real-estate-ucits-etf-de-fund | 200 |
| EXH8 | DE000A0H08P6 | https://www.ishares.com/de/privatanleger/de/produkte/251959/ishares-stoxx-europe-600-retail-ucits-etf-de-fund | 200 |
| EXV3 | DE000A0H08Q4 | https://www.ishares.com/de/privatanleger/de/produkte/251961/ishares-stoxx-europe-600-technology-ucits-etf-de-fund | 200 |
| EXV2 | DE000A0H08R2 | https://www.ishares.com/de/privatanleger/de/produkte/251963/ishares-stoxx-europe-600-telecommunications-ucits-etf-de-fund | 200 |
| EXV9 | DE000A0H08S0 | https://www.ishares.com/de/privatanleger/de/produkte/251965/ishares-stoxx-europe-600-travel-leisure-ucits-etf-de-fund | 200 |
| EXH9 | DE000A0Q4R02 | https://www.ishares.com/de/privatanleger/de/produkte/251967/ishares-stoxx-europe-600-utilities-ucits-etf-de-fund | 200 |
| EXH1 | DE000A0H08M3 | https://www.ishares.com/de/privatanleger/de/produkte/251954/ishares-stoxx-europe-600-oil-gas-ucits-etf-de-fund | 200 |
| EXH3 | DE000A0H08H3 | https://www.ishares.com/de/privatanleger/de/produkte/251944/ishares-stoxx-europe-600-food-beverage-ucits-etf-de-fund | 200 |
| EXH7 | DE000A0H08N1 | https://www.ishares.com/de/privatanleger/de/produkte/251956/ishares-stoxx-europe-600-personal-household-goods-ucits-etf-de-fund | 200 |
