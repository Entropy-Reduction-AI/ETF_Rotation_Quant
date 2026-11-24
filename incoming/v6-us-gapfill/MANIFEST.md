# v6 美股价格缺口：DJIA 与 DWRTF 原始收盘

本包只放原始价格收盘和逐日对照。没有收益、没有入库、没有改 `config/` 或名册。库只读，查询仅限下面两个重叠窗里的 `adj='raw'` 收盘。

复算（不下载，只读已保存的原始文件和库）：

```bash
python3 -I scripts/v6_us_gapfill_compare.py
```

相对差公式，分母是右边那一列：

```text
abs(left - right) / abs(right)
```

和库比时，右边是库内收盘。门槛 0.1% = 0.001。超过则脚本退出码 2。本次退出码 0。没有删日期，没有插值。

## 来源身份

| 序列 | 本次新下载 | 出版方 | 不把它当成另一套的原因 |
| --- | --- | --- | --- |
| DJIA | FRED `DJIA` | 系列页写明 Source 为 S&P Dow Jones Indices LLC；单位 Index，非季调；注释为收盘点位 | 这是官方点位的再发布，不是另一套算法 |
| DJIA | CNBC `.DJI` | 响应 `companyName` 为 Dow Jones Industrial Average，`symbol` 599362，`adjusted` 为 UNADJUSTED。FT 页 `DJI:DJI` 的 issueID 同为 599362，页脚 Data Provided by LSEG | 与 FRED 不是同一个文件 |
| DJIA | Yahoo `^DJI` | 图接口 `longName` 为 Dow Jones Industrial Average | 与 CNBC 的差别停在浮点末位，不当成另一套算法 |
| DJIA | 新浪 `.DJI` | 接口没有写上游名称 | 交付窗内的规范化收盘与 FRED 逐字相同，不另算一套 |
| DWRTF | CNBC `.DWRTF` | `companyName` 为 DJUSslct REIT，`symbol` 585870，`adjusted` 为 UNADJUSTED。FT 页 `DWRTF:DJI` 的 xid 同为 585870，页脚同样是 LSEG | FT 与 CNBC 是同一 LSEG 品种，FT 不另算来源 |
| DWRTF | 未新下载 | 仓库里已有的 TradingView `DJ:DWRTF` 价格日线。2026-11-24 符号检索写明 `provider_id` 为 ice，名称 Dow Jones U.S. Select REIT Index (USD)。总收益代码是 `DWRTFT`，净总收益是 `DWRTFN`，都没有用 | 免费行情套接字返回 `permission denied` / `dj_indices_dly`，本轮没有重下 |
| DWRTF | 未新下载 | 仓库里已有的官方约一年 USD 价格文件，2025-11-17 至 2026-11-16 | 现场打开 spdji 导出为 HTTP 403，盖不住 2017 年 |

价格而不是全收益的核对：CNBC 在 2017-08-01 至 2017-11-22 的 81 天与库内 `DWRTF` / `d37_r6` 逐日相对差为 0（例如 2017-08-01 两边都是 275.51）。同一 CNBC 序列在 2025-11-17 至 2026-09-30 的 218 天与上述官方价格文件相对差为 0（2025-11-17 两边都是 293.19）。没有用 `DWRTFT`、`DJUSRE` 或 ETF。

库内重叠足够 60 天，没有往更早补：

| 代码 | 库来源 | 要求的重叠窗 | 库内天数 | 起 | 止 |
| --- | --- | --- | ---: | --- | --- |
| DJIA | eastmoney_index | 2023-11-01 至 2024-02-01 | 63 | 2023-11-01 | 2024-02-01 |
| DWRTF | d37_r6 | 2017-08-01 至 2017-11-22 | 81 | 2017-08-01 | 2017-11-22 |

TradingView 与库在这 81 天也逐日相对差为 0。库的 `d37_r6` 就是这条 TradingView 序列切到 2017-11-22，所以这一对不能当作独立核对。独立核对是 CNBC 对库。

## 要求覆盖

DJIA 要求 2024-02-01 至 2026-09-30，四套新下载都含首尾两天。

| 来源 | 原始行数 | 原始起止 | 要求窗行数 | 要求窗首尾都在 |
| --- | ---: | --- | ---: | --- |
| FRED | 2512 | 2016-11-25 至 2026-11-23 | 668 | 在 |
| Yahoo | 752 | 2023-10-02 至 2026-09-30 | 668 | 在 |
| 新浪 | 5762 | 2004-01-02 至 2026-11-23 | 668 | 在 |
| CNBC | 753 | 2023-10-02 至 2026-09-30 | 669 | 在 |

CNBC 多出来的一天是 2024-12-25。当天 OHLC 与 2024-12-24 完全相同（收盘 43297.0300）。FRED、Yahoo、新浪都没有这一天。文件里保留，没有删。

DWRTF 要求 2017-11-22 至 2026-09-30。

| 来源 | 原始行数 | 原始起止 | 要求窗行数 | 要求窗首尾都在 |
| --- | ---: | --- | --- | --- |
| CNBC，本轮下载 | 2304 | 2017-08-01 至 2026-09-30 | 2224 | 在 |
| TradingView，旧文件 | 7008 | 1998-12-31 至 2026-11-16 | 2224 | 在 |
| 官方价格，旧文件 | 251 | 2025-11-17 至 2026-11-16 | 218（裁到 2026-09-30） | 有 2026-09-30，没有 2017-11-22 |

## 两源最大相对差

要求窗内，分母为右边。

| 对照 | 重叠天数 | 只在左边 | 只在右边 | 最大相对差 | 最差日 | 左 | 右 | 超过 0.1% 的天数 |
| --- | ---: | --- | --- | ---: | --- | --- | --- | ---: |
| DJIA FRED / CNBC | 668 | 无 | 2024-12-25 | 1.3075431785816616e-07（0.000013075%） | 2024-04-26 | 38239.66 | 38239.6550 | 0 |
| DJIA Yahoo / CNBC | 668 | 无 | 2024-12-25 | 1.6863369773223392e-07（0.000016863%） | 2024-03-04 | 38989.828125 | 38989.8347 | 0 |
| DJIA 新浪 / CNBC | 668 | 无 | 2024-12-25 | 1.3075431785816616e-07 | 2024-04-26 | 38239.66 | 38239.6550 | 0 |
| DJIA FRED / Yahoo | 668 | 无 | 无 | 4.958228991333375e-08 | 2024-04-30 | 37815.92 | 37815.921875 | 0 |
| DWRTF CNBC / TradingView | 2223 | 2024-12-25 | 2023-04-06 | 0.00040752564015487523（0.040752564%） | 2019-08-12 | 294.5800 | 294.46 | 0 |

DWRTF 这一对里，相对差超过 0.01% 的只有 2019-08-12 一天，其余 2222 天在已保存的小数上相同。2023-04-06 只在 TradingView，收盘 259.56；CNBC 没有这一天。没有补。2024-12-25 的 CNBC 收盘 294.9400，与 2024-12-24 的 OHLC 相同。

官方旧文件对 CNBC，2025-11-17 至 2026-09-30：218 天，无单边日期，最大相对差 0。

## 与库重叠

| 对照 | 天数 | 最大相对差 | 最差日 | 左 | 右 |
| --- | ---: | ---: | --- | --- | --- |
| DJIA FRED / 库 | 63 | 0 | 全部为 0 |  |  |
| DJIA 新浪 / 库 | 63 | 0 | 全部为 0 |  |  |
| DJIA Yahoo / 库 | 63 | 5.634932136622701e-08 | 2023-11-01 | 33274.578125 | 33274.58 |
| DJIA CNBC / 库 | 63 | 1.4356388729030788e-07 | 2023-11-14 | 34827.6950 | 34827.7 |
| DWRTF CNBC / 库 | 81 | 0 | 全部为 0；2017-08-01 两边 275.51 | 275.5100 | 275.51 |
| DWRTF TradingView / 库 | 81 | 0 | 同一上游，见上 | 275.51 | 275.51 |

没有一对超过 0.1%。不需要因相对差停下来改数。

## 下载命令

在仓库根之外把响应存成下面的原始文件。CNBC 路径里的 `adjusted` 是接口拼法，响应里的 `adjusted` 字段是 `UNADJUSTED`。

```bash
curl -fsSL -o fred-DJIA.csv "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DJIA"
curl -fsSL -o fred-DJIA-series-page.html "https://fred.stlouisfed.org/series/DJIA"
curl -fsSL -A "Mozilla/5.0" -o yahoo-DJI-chart.json \
  "https://query2.finance.yahoo.com/v8/finance/chart/%5EDJI?period1=1696118400&period2=1790812800&interval=1d&includeAdjustedClose=true&events=history"
curl -fsSL -o sina-DJI-daily.json \
  "https://stock.finance.sina.com.cn/usstock/api/json.php/US_MinKService.getDailyK?symbol=.DJI"
curl -fsSL -o ft-DJI-DJI-summary.html \
  "https://markets.ft.com/data/indices/tearsheet/summary?s=DJI:DJI"
curl -fsSL -o ft-DWRTF-DJI-summary.html \
  "https://markets.ft.com/data/indices/tearsheet/summary?s=DWRTF:DJI"
curl -fsSL -o wayback-spdji-DWRTF-20250212.html.gz \
  "https://web.archive.org/web/20250212182349id_/https://www.spglobal.com/spdji/en/indices/equity/dow-jones-us-select-reit-index/"
```

Yahoo 的 `period1` 1696118400 是 2023-10-01 00:00 UTC，`period2` 1790812800 是 2026-10-01 00:00 UTC。交易日按 America/New_York 从柱时间取出。CNBC 的日期取 `tradeTime` 前 8 位，不把 UTC 日界再平移。

CNBC 按段下载，URL 形如 `https://ts-api.cnbc.com/harmony/app/bars/{symbol}/1D/{start}/{end}/adjusted/GMT`。

| 文件 | symbol | start | end |
| --- | --- | --- | --- |
| `cnbc_dji_20231001_20231231.json` | `.DJI` | 20231001000000 | 20231231235959 |
| `cnbc_dji_20240101_20241231.json` | `.DJI` | 20240101000000 | 20241231235959 |
| `cnbc_dji_20250101_20251231.json` | `.DJI` | 20250101000000 | 20251231235959 |
| `cnbc_dji_20260101_20260930.json` | `.DJI` | 20260101000000 | 20260930235959 |
| `cnbc_dwrtf_20170801_20171231.json` | `.DWRTF` | 20170801000000 | 20171231235959 |
| `cnbc_dwrtf_20180101_20181231.json` 至 `cnbc_dwrtf_20250101_20251231.json` | `.DWRTF` | 该年 0101000000 | 该年 1231235959 |
| `cnbc_dwrtf_20260101_20260930.json` | `.DWRTF` | 20260101000000 | 20260930235959 |

中证三份见 `NOTE-931743.md`。

本轮试过、没有当作日线来源的：spdji 页面和导出 HTTP 403；Yahoo `^DWRTF` 的 chart 接口只有报价、没有历史柱，v7 下载 HTTP 401；Stooq 校验返回 ip mismatch；TradingView 免费套接字 `permission denied`；新浪、东财、腾讯没有 DWRTF 日线；Nasdaq 历史接口报 Symbol not exists；MarketWatch / WSJ HTTP 401。

## 原始文件 SHA256

| SHA256 | 字节 | 路径 |
| --- | ---: | --- |
| `256b9f380c3b20aef06cf4e0846d1527897e6cd6c3db1d5b700b22da08577f69` | 51402 | `raw/fred-DJIA.csv` |
| `a79e480b8a5bc4487ec531ea18e4ae95e5c4ba0d13fcc9ca7a1db6a848bb22bf` | 78880 | `raw/fred-DJIA-series-page.html` |
| `1bff9ba20b048d55e892ca0f9ac1a86b0a3859fa0b7f3b1dd152468f89331017` | 69371 | `raw/yahoo-DJI-chart.json` |
| `f54229eef4753c84046a2c623c00abb3344537b891bdfdc5c161d2ac3defae04` | 644832 | `raw/sina-DJI-daily.json` |
| `48dacadd643046dda2d495478c8f46466fc61ed87141a50ed244dbb4ffdedcb0` | 80669 | `raw/ft-DJI-DJI-summary.html` |
| `8d8129b9533bd3c7b024ff02b68e3cd50111363124e266b64eb415d3615ac0fe` | 80756 | `raw/ft-DWRTF-DJI-summary.html` |
| `0d86712f27cce8cd51eba1628ff444f6e0b5e516804332e75224883d478176b9` | 86377 | `raw/wayback-spdji-DWRTF-20250212.html.gz` |
| `0244d43b98a1266e82277543e64e2588c49cc3994183b3137b923bc8658608e8` | 10490 | `raw/cnbc-dji/cnbc_dji_20231001_20231231.json` |
| `bfffa17fb29395e3d9cf6149a53deefa8d3e86ebcf0be98bb786b7915a30a949` | 41454 | `raw/cnbc-dji/cnbc_dji_20240101_20241231.json` |
| `b5f2ecf95be30615adaf7457c8e7c7bab180837ded6b261b5bc2f9862263bd74` | 40979 | `raw/cnbc-dji/cnbc_dji_20250101_20251231.json` |
| `43179fe1b2ff20023e38461f74df24e6423c6f07d035ceef8947e1f307cfdc45` | 30704 | `raw/cnbc-dji/cnbc_dji_20260101_20260930.json` |
| `9afe71e0d4cab6b045fe422b8383e5476438278672a66007331829f51ec5a668` | 15790 | `raw/cnbc-dwrtf/cnbc_dwrtf_20170801_20171231.json` |
| `4475a829da8254bd7f4f70abe1f7d4f0345f9353e7798eeb31f0af50e36938bd` | 37105 | `raw/cnbc-dwrtf/cnbc_dwrtf_20180101_20181231.json` |
| `77a55bd15ee575434f1b19e839467f5e96b6b71c4cd08d2db6dc608cc3f83379` | 37252 | `raw/cnbc-dwrtf/cnbc_dwrtf_20190101_20191231.json` |
| `256178c991983ab36f28207692aeb4a272c8f0e790de8c2b763e14552f0fc0e3` | 37399 | `raw/cnbc-dwrtf/cnbc_dwrtf_20200101_20201231.json` |
| `371fe3f3ad7370b1623176748a9aedb0707fdef1c6a486840a55817088658ccb` | 37252 | `raw/cnbc-dwrtf/cnbc_dwrtf_20210101_20211231.json` |
| `c9d4487a521c25e463a95878dcc92973cdd1b090c0f06fdc79bced8ec1bb1b06` | 37105 | `raw/cnbc-dwrtf/cnbc_dwrtf_20220101_20221231.json` |
| `2069d0ae0debc280e4d1482b9becf70e7d5f57979112bc778c5ad8fe98a1b7d1` | 36811 | `raw/cnbc-dwrtf/cnbc_dwrtf_20230101_20231231.json` |
| `423d5ffa72ae9c75db32d1cc4295665a01ff1b3112614f101b89c1ec0bb0ce48` | 37399 | `raw/cnbc-dwrtf/cnbc_dwrtf_20240101_20241231.json` |
| `965f2e3f5f7ab903956555d0a4487de6d7b25aaea4250242f26818e8cf7129f1` | 36958 | `raw/cnbc-dwrtf/cnbc_dwrtf_20250101_20251231.json` |
| `d531974b55507cbec5c5427d72110552da3f982c322f4ce2d1729f88c0f76f5c` | 27697 | `raw/cnbc-dwrtf/cnbc_dwrtf_20260101_20260930.json` |

旧文件，本轮没有改字节：

| SHA256 | 字节 | 路径 |
| --- | ---: | --- |
| `1b2e608ee868c15da254503c13a5aa091be0057ef65fac399c3d29af09f6b548` | 125832 | `incoming/grok-d37-index-20261116/theme-道琼斯美国精选REIT指数-tradingview.csv` |
| `861189a91ca208793d5555150a2ecad15d3fc7f50170eb2b985f43797967cb01` | 4513 | `incoming/grok-d37-index-20261116/theme-道琼斯美国精选REIT指数-official-usd-pr-daily-20251117-20261116.csv` |

规范化收盘在 `normalized/`。FRED 与新浪的规范化文件 SHA256 同为 `7f90b86ea1ca0c7cb922ce447d34423a2a1fef7dd6df8d7fe583399ec4d44410`（730 行）。逐日表在 `evidence/`。汇总 `evidence/comparison.json` 的 SHA256 是 `fa65657dc5e3f88bd63275fd75acb76eead659de264d3b570c934574fec2be8d`。

Wayback 页原文有 `<label>Bloomberg Ticker:</label> DWRTF`。这是 2025-02-12 的官方指数页快照，用来核对代码，不是日线。
