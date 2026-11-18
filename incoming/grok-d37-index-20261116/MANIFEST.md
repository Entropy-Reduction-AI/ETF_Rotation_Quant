# D37 第六轮部分提交 MANIFEST

- 日期：2026-11-18 23:05（Asia/Taipei，UTC+8；本批更新：Dev remain pass 3。S5INFT 的 2001-01-02 至 2001-12-04 已由允许的公开 CNBC 日线补上，不是官方日线。正式计数仍是已完成 31/36、部分完成 5。PR #312 已开，本批将追加）
- 分支：`grok/d37-r6-partial`（追加提交用同一分支）
- 路径：`incoming/grok-d37-index-20261116/`
- 本包用途：给 Orchestrator 看进度、更新数据看板。
- 入库：仍等 36 条全部完成后再由 Dev 统一做；Reviewer 签收后，再请 Manager 合并。本 PR **不要合并**，也不要开 `cursor/d37-r6` 入库分支。

派单共 36 条（Priority A 30 + Priority B 6）。下方「已完成」指本包已有可交的日线 CSV（官方或已允许的二级源），且至少覆盖所需窗口的大部分，不是入库通过。另有 5 条官方身份已确认、但所需窗口仍未完整覆盖，记在「部分完成」，不计入 31/36。S35 与 DWRTF 已有官方约一年 + TradingView 长日线（重叠 251/251 精确吻合），计入已完成。SPGOGUP 已用 Wayback 官方日线覆盖所需窗口，改入已完成。Dev remain pass 2 和 pass 3 都不改变这个计数：仍是已完成 31/36，部分完成仍是 SPAHLVCP、能源净总回报 SP5NENRS、消费精选 SP5CSSUP、品质消费 IXY、中国新经济 SPNCSCUP。入库仍等整包完成。36 条现在都至少有一段日线。

## 已完成（31 / 36）

### 官方日线（或官方 FX）已取到

| 容器 | 文件 | 行数 | 区间 | SHA256 | 备注 |
|---|---|---|---|---|---|
| soymeal | `soymeal.csv` | 2333 | 2017-04-10 → 2026-11-16 | `78be98365127211ddc2eb25de0266ffc8dc2e964a4b8e9686a7ba404f6d92469` | DCE 豆粕期货价格指数；官方发布日 2017-04-10 |
| theme-巴西IBOVESPA指数 | `theme-巴西IBOVESPA指数-fx.csv` | 8126 | 1994-07-01 → 2026-11-16 | `a94c013a62e0187941d8edce8f3fd5620f5e1dc963c4dd443056f28d09aa045d` | 官方 BCB SGS series 1（BRL FX）；指数日线原已具备 |
| theme-东证指数 | `theme-东证指数.csv` | 2624 | 2016-01-04 → 2026-09-30 | `5a7b5be2edd8760d3d2f96abd603793813ba5feaa3a39508acb059a4c2e4bfb2` | 官方 JPX 统计月报 3-1，JPY price-return；公开档案自 2016 起；`publish_date` 未核对；无基日回填 |
| theme-MSCI China Value Weighted Index | `theme-MSCI China Value Weighted Index.csv` | 3871 | 2012-01-16 → 2026-11-16 | `fca66609e41d2544f7e0501e9573d50460e3f755a8c56d46b7cc80315b47c82c` | 官方日线（Price, USD）；与 4 年表单重叠 1044 日，max \|Δ\|=0 |
| theme-MSCI USA 50 Index | `theme-MSCI USA 50 Index.csv` | 1159 | 2022-06-08 → 2026-11-16 | `250c6679fbc329e3bec11e189ecf7c50a1547f74fc5ddde5bf17502689c1d1ad` | 官方日线（Price, USD） |
| chinext | `chinext.csv` + `chinext-eastmoney.csv` | 3996 / 3996 | 2010-06-01 → 2026-11-16 | 官方 `195eeece26573879e344bbd534fc4b8e5c97432d90b719472fc984d9b49c5296` | SZSE 起始计算日 2010-06-01 = publish_date（基日 2010-05-31=1000 已剔除）。双源重叠 3996 日，median \|rel\|≈0.000125%，max \|rel\|≈0.00766%，0 日超过 0.01%。Dev 无需重下 |
| theme-法兰克福DAX指数 | `theme-法兰克福DAX指数.csv` | 6954 | 1999-06-21 → 2026-11-16 | `b8c65b5908752c965a8260e5d34367cbe9b775291733c3615d9cd61c52085b97` | 官方价格收益为 **DAXK**（ISIN DE0008467440）。`publish_date` 未核对。公开延迟序列自 Xetra 1999-06-21 起 |
| theme-标普全球石油指数 | `d37-remain-20261118/theme-SPGOGUP-usspindices-wayback-usd-pr-daily-20110708-20141215.csv` | 895 | 2011-07-08 → 2014-12-15 | `43534668fced8de43b7cec9eb250ce5e025eebbd9da2c9ea882e84bf3f0bc990` | 官方 us.spindices.com「S&P Global Oil Index」页嵌入的 `indexLevels`（indexId 5475707，USD Price Return，代码 SPGOGUP；未用同页 TR SPGOGUT），取自 [Wayback 2015-01-26 快照](https://web.archive.org/web/20150126100537id_/http://us.spindices.com/indices/equity/sp-global-oil-index)。发布日 2011-07-08（First Value 2000-08-31，未作发布日）。所需窗口 2011-07-08 → 2012-05-02+30d 已覆盖。指定窗口内只缺 2013-01-01、2014-01-01 两个元旦。同快照与已有 FT 在 2014-12-16 至 2015-01-23 重叠 28/28，四舍五入到两位精确一致。另有未裁切的 2005-01-24 起序列，那是发布日前的回补，不作为所需窗口。官方约一年 XLS 与 FT 长序列仍保留作对照 |

**不要**把 `theme-法兰克福DAX指数-eastmoney.csv` 当作 DAXK 的第二源：那是头条绩效 DAX（DE0008469008，2026-11-16 约为 26598.64），不是价格收益。文件留在包内仅作对照，见 `theme-法兰克福DAX指数-eastmoney-NOTE.txt`。

### 恒生 Priority A（12）：二级日线已取，官方过去一月 20/20 对上

官方 INdex360 免费历史目前仍只有 Past month（20 个交易日，截至 2026-11-16）。东方财富日线与这 20 日 Day Close 精确吻合（max \|rel\|=0）。入库前请按官方发布日裁切；东方财富这 12 条末行含 **2026-11-17（当天、未确认）**，入库前应剔除。

| 容器 | 东方财富日起 | 备注 |
|---|---|---|
| theme-HSFML25 | 2017-07-19 | INdex360 发布日用 2017-07-19；目录或为 2003-01-20，冲突未决 |
| theme-HSISC | 2024-03-08 | |
| theme-HSSC50 | 2025-01-13 | |
| theme-HSSCAMHI | 2024-05-31 | |
| theme-HSSCHKY | 2019-11-18 | |
| theme-HSSCITI | 2023-12-01 | |
| theme-HSSCPB | 2023-12-01 | |
| theme-HSSCSOY | 2023-12-01 | |
| theme-HSSCT | 2020-03-30 | |
| theme-恒生中国央企指数 | 2023-12-01 | |
| theme-恒生创新药指数 | 2023-12-01 | |
| theme-恒生生物科技指数 | 2019-12-16 | EM/Yahoo 代码为 HSHKBIO；目录首值 2013-12-31、发布日 2021-10-19，入库前按发布日裁切 |

每条同时有 `theme-<id>-eastmoney.csv` 与 `theme-<id>-official-past-month.csv`。

### 允许的二级日线（官方免费日线仍缺）

TradingView 均为免费 Supercharts Table 视图抄表；**未使用** Plus / Download chart data。SGX 两条 Owner 已同意暂时采用（复述误差见下，允许日后改正）。

| 容器 | 文件 | 行数 | 区间 | SHA256 | 备注 |
|---|---|---|---|---|---|
| theme-iEdge Emerging Asia Select 50 Index | `theme-iEdge Emerging Asia Select 50 Index.csv` | 583 | 2024-07-24 → 2026-11-16 | `065892f219678e362fdeda9d85c380348da38e77036f77c475904edecf37633e` | TV `EMASIAUP`。官方发布日 2024-07-19；7/22–7/23 缺失。官方复述相对误差 −0.2912%、−0.5405%、−0.1253%（高于 0.01% 入库中位数门槛） |
| theme-新交所泛东南亚科技指数 | `theme-新交所泛东南亚科技指数.csv` | 926 | 2023-03-10 → 2026-11-16 | `b9082a02a4c4ac97ea6cfd1b4d0e924fba7339de4dc36df863454f3c965ad6c0` | TV `ASIATECP`。官方发布日 2022-11-18，此前缺口未补 |
| theme-富时亚太低碳精选指数 | `theme-富时亚太低碳精选指数-tradingview.csv` | 1157 | 2022-06-06 → 2026-11-16 | `e3a40183a9e4b5d69de0d15dbb02ce2944434b0194d7c4d23e7a3edad84e2d6a` | TV `GPCSP006`。官方发布日 2022-05-27，免费表缺 2022-05-27–06-05 |
| theme-富时沙特阿拉伯指数 | `theme-富时沙特阿拉伯指数-tradingview-FISAULM-SAR.csv` | 1550 | 2019-02-18 → 2026-11-16 | `8c559a08038f630db34172010d558c5c59dbbea8164502fc19dd81bf6a844400` | TV `FISAULM`（SAR）。官方价格指数 `publish_date` 未核对（不用 Net Tax 说明书的 2019-03-18） |
| theme-富时沙特阿拉伯指数 | `theme-富时沙特阿拉伯指数-tradingview-FISAULMU-USD.csv` | 1591 | 2018-11-27 → 2026-11-16 | `a23e46a14194c5bfb0a4508d0c89ae35034200978fa563dd6267b25608256fb2` | TV `FISAULMU`（USD）。与 FISAULM 重叠 1543 日，max \|rel\|≈0.43%（2022-09-28） |
| theme-标普500信息科技指数 | `theme-标普500信息科技指数-tradingview.csv` | 3547 | 2012-09-25 → 2026-11-16 | `4e04cba0c5f50cd53d2b54e0b2dc3fd3529386f31dd656d9e0877fa881304bb7` | TV `S5INFT`。官方发布日 **1996-06-28**（First Value 1989-09-11，未作发布日），官方代码 USD PR **S5INFT**（Reuters `.SPLRCT`）。官方约一年 XLS 252 行 2025-11-17→2026-11-17，与 TV 重叠 251/252（TV 无 2026-11-17）；中位数相对误差约 0.00015%，2 日高于 0.01%，最大 2026-06-26 约 1.196%（官方 6509.39 vs TV 6431.52）。所需窗口自发布日 → 2016-12-27+30d。Dev remain pass 2：1996-06-28 至 2012-09-24 的大部分已由允许的公开 FT `SP500-45:IOM`（不是 IXT）补上，文件 `d37-remain-20261118-pass2/theme-S5INFT-ft-SP500-45-usd-pr-daily-19960628-20120924.csv`，3864 行，159.84 → 502.22，SHA256 `c95ed3b892ea0c50db70f6ba35e8e5ac7ec1937c60a9f6a463b1c1b144b0f6fa`。与官方约一年重叠 252/252 精确。Dev remain pass 3：2001-01-02 至 2001-12-04 已由允许的公开 CNBC 日线补上（Reuters `.SPLRCT`，issue_id 603229，与 FT 用的 xid 相同；不是官方日线，未用 IXT）。文件 `d37-remain-20261118-pass3/theme-S5INFT-cnbc-SPLRCT-usd-pr-daily-20010102-20011204.csv`，230 行，2001-01-02 444.9235 → 2001-12-04 366.8393，SHA256 `9463cf2e4c271bb95222ed5634853a6885a439275f78299fdb84892fd3eba75f`。该窗口另有 11 个工作日是纽交所假日和 2001-09-11 至 2001-09-14 停市。官方约一年重叠 252/252 精确。与 FT 接缝在两位小数上吻合。仍记在已完成 |
| theme-标普生物科技精选行业指数 | `theme-标普生物科技精选行业指数-tradingview.csv` | 3153 | 2014-05-06 → 2026-11-16 | `e642543a54a6e214317d03462e8d297c02d2f79e6b175568b3713fe7d01b1683` | TV `SPSIBI`。官方发布日 **2006-01-27**（First Value 1999-12-17，未作发布日），官方代码 USD PR **SPSIBI**（Reuters `.SPBIO`）。官方约一年 XLS 252 行 2025-11-17→2026-11-17，与 TV 重叠 251/252；中位数约 0.00010%，1 日略高于 0.01%（2026-03-06 约 0.0146%）。所需窗口自发布日 → 2016-12-27+30d。Dev remain pass 2：2006-01-27 至 2014-05-05 已由官方 Wayback us.spindices.com 嵌入的 `indexLevels` 补上（indexId 2331，USD PRICE RETURN，代码 SPSIBI；同页 TR SPSIBITR 未抽取），快照 20141221042442。文件 `d37-remain-20261118-pass2/theme-SPSIBI-usspindices-wayback-usd-pr-daily-20060127-20140505.csv`，2081 行，2006-01-27 1238.8078683824 → 2014-05-05 3362.11236409174，SHA256 `356b3fb9a3c977b0ad2d4298324d5259b745c864df9dbf74ed458a12adc7a324`。Manager 独立核对：日期与 JSON 2081/2081 一致；29 个值只差浮点表示（最大绝对差 5e-12），四舍五入到两位后全部精确。与已有 TV 2014-05-06 至 2014-12-19 重叠 160/160，`round(official, 2)` 精确。未裁切的 2004-12-20 起文件是发布前回补，不用于所需窗口 |
| theme-道琼斯美国石油开发与生产指数 | `theme-道琼斯美国石油开发与生产指数-tradingview.csv` | 5166 | 2006-05-05 → 2026-11-16 | `c0da503c67117d8e70c6e1ffc02cf741318bdf911336507b7268b6e30e1675b0` | TV `DJSOEP`；官方名称 Dow Jones U.S. Select Oil Exploration & Production Index。官方发布日 **2006-04-28**（First Value 1991-12-31，未作发布日），官方代码 USD PR **DJSOEP**（Reuters `.DJSOEP`）。官方约一年 XLS 252 行 2025-11-17→2026-11-17，与 TV 重叠 251/251 精确吻合（TV 无 2026-11-17）。所需窗口自发布日至 2017-03-17+30d。Dev remain pass 2：2006-04-28 至 2006-05-04 已由允许的公开 FT `DJSOEP:DJI` 补上。文件 `d37-remain-20261118-pass2/theme-DJSOEP-ft-usd-pr-daily-20060428-20060504.csv`，5 个交易日 6355.52 → 6438.07，SHA256 `d4236d5699019de1eca1c73b403f123eefe1ddce2e54c8869b2ed0e320813b3f`。TV 接缝 2006-05-05 6523.51 精确。官方约一年重叠 251/251 精确（官方一年多一个 2026-04-24，FT 一年文件没有这一天） |
| theme-标普石油天然气勘探及生产精选行业指数 | `theme-标普石油天然气勘探及生产精选行业指数-tradingview.csv` | 5126 | 2006-06-23 → 2026-11-16 | `aba06667e82696bcb1f79ed2ceb6b1914c54f1627b2971373f31fcfcee3b5038` | TV `SPSIOP`。官方发布日 **2006-06-19**（First Value 1999-12-17，未作发布日），官方代码 USD PR **SPSIOP**（Reuters `.SPSIOP`）。官方约一年 XLS 252 行 2025-11-17→2026-11-17，与 TV 重叠 251/252；中位数约 0.00015%，1 日高于 0.01%：2026-03-09 约 3.285%（官方 6226.42 vs TV 6430.97）。所需窗口自发布日至 2012-06-08+30d。Dev remain pass 2：2006-06-19 至 2006-06-22 已由 FT `SPSIOP:IOM` 补上。文件 `d37-remain-20261118-pass2/theme-SPSIOP-ft-usd-pr-daily-20060619-20060622.csv`，4 个交易日 5070.13 → 5187.6，SHA256 `f6e2fc0ef13500a7b627f8047ef78715eba6ca0ca1a32d0d982ec48d1781fc88`。TV 接缝 2006-06-23 5448.80 精确。官方约一年重叠 252/252 精确，含 2026-03-09 官方/FT 6226.42（TV 仍是 6430.97，这一天不能当官方用） |
| theme-恒生中国企业指数 | `theme-恒生中国企业指数-official-past-month.csv` | 21 | 2026-10-20 → 2026-11-17 | `3baea34e5fa7e30d67925e37ec71782802b52fd1e4598c7b901f69e40d6e229a` | 官方 INdex360 免费 Past month 价格收益，id 00014.00。2026-11-16 Day Close 7981.54 与东方财富、TradingView 过去 20 日全部精确吻合（max \|rel\|=0）。含已收盘的 2026-11-17（7904.37）。发布日冲突见下，未裁切二级源 |
| theme-恒生中国企业指数 | `theme-恒生中国企业指数-eastmoney.csv` | 7956 | 1994-08-08 → 2026-11-16 | `2a8cdfc18e3a7926f3522d4a5cf97e16954e89fa93e237b404c96ab7b4d83b20` | 东方财富二级源。与官方过去一月 20/20 精确吻合 |
| theme-恒生中国企业指数 | `theme-恒生中国企业指数-tradingview.csv` | 5780 | 2003-05-28 → 2026-11-16 | `db4a33a2b41856044aee60e9f9a98bae312feea51a6610f90318ea8c44ea2ae1` | TV `HSI:HSCEI`，页面名为 Hang Seng China Enterprises Index。免费表从 2003-05-28 起，缺官方发布日 1994-08-08 至 2003-05-27。与东方财富重叠 5777 日，median \|rel\|=0，max \|rel\|≈0.494993%（2007-09-25），9 日超过 0.01%。2026-11-17 延迟 bar 已剔除 |

> 说明：这四条的官方约一年 USD PR 对照已于 2026-11-18 11:37（Asia/Taipei）取到（Graph View → Export，无需新登录；页眉已是 Hi Karin；未用 SPICE）。免费导出仍只有约一年（252 行，2025-11-17→2026-11-17），盖不住所需窗口。官方发布日已从页面截图，不再写「未核对」。权威文件是官方 `.xls`；同名 `.csv` 是 LibreOffice 抽出的 `date,close`，不是另一来源。截图 `screenshots/official-<TICKER>-overview.png` 与 `official-<TICKER>-graph-1y.png` 是同一张图（概览页已含 1 Year Graph View 和 Export）。发布日与代码见 `official-<TICKER>-launch.png`、`official-<TICKER>-tickers.png`。

官方约一年文件（均为 252 行，2025-11-17 → 2026-11-17）：

| 容器 | 文件 | SHA256（xls / csv） | 官方页与代码 |
|---|---|---|---|
| theme-标普500信息科技指数 | `theme-标普500信息科技指数-official-usd-pr-daily-20251117-20261117.xls` + `.csv` | xls `9a66b9eb3116132de29f55fb1a2c0888937d2fd3dbc51f6db49de68b08ae6bb8` / csv `f8603abdf608dca7d62c615edeaf4608985c88a9e23f6e8267d08c6294a260bd` | https://www.spglobal.com/spdji/en/indices/equity/sp-500-information-technology-sector/ ；页名 S&P 500 Information Technology；XLS 序列名 S&P 500 Information Technology (Sector)；USD PR S5INFT |
| theme-标普生物科技精选行业指数 | `theme-标普生物科技精选行业指数-official-usd-pr-daily-20251117-20261117.xls` + `.csv` | xls `80e490492eda20fc5d8ca46f7050b95e9fb29d4a6ddcb97d1d42f6cad2f20ee1` / csv `bd38dd5ac4d449e5f1aea1d71ba9e242bc54a6478bce0335476457572622aae0` | https://www.spglobal.com/spdji/en/indices/equity/sp-biotechnology-select-industry-index/ ；USD PR SPSIBI |
| theme-道琼斯美国石油开发与生产指数 | `theme-道琼斯美国石油开发与生产指数-official-usd-pr-daily-20251117-20261117.xls` + `.csv` | xls `b7becfd4a83ad28c7ec7146018251abee25b6e9cf9480a0e4e88b97c6407baf2` / csv `21692108deceec9c63b3c315e7163724f8bf2807d80b37b57ea2e25e1b635c4a` | https://www.spglobal.com/spdji/en/indices/equity/dow-jones-us-select-oil-exploration-production-index/ ；USD PR DJSOEP |
| theme-标普石油天然气勘探及生产精选行业指数 | `theme-标普石油天然气勘探及生产精选行业指数-official-usd-pr-daily-20251117-20261117.xls` + `.csv` | xls `55b023b4f7f59605e16c99376613c6423a861432995039a36ee4eae3ee074c2a` / csv `a9f23ea3ac9ade2e69b05bdf27684d304c7dcfbcbbb195ac217b3b41b63c3944` | https://www.spglobal.com/spdji/en/indices/equity/sp-oil-gas-exploration-production-select-industry-index/ （由官方 Index Finder 按 SPSIOP 找到后核对）；USD PR SPSIOP；不是 DJSOEP |


### 官方约一年 + TradingView 长日线（重叠精确吻合）

TradingView 均为免费 Supercharts Table 视图抄表（已登录免费账号）；**未使用** Plus / Download chart data。与官方约一年 XLS 重叠均为 251/251 日、median |rel|=0、max |rel|=0。2026-11-17 延迟 bar 已从交付文件剔除。

| 容器 | 文件 | 行数 | 区间 | SHA256 | 备注 |
|---|---|---|---|---|---|
| theme-标普500医疗保健等权重指数 | `theme-标普500医疗保健等权重指数-tradingview.csv` | 5038 | 2006-11-02 → 2026-11-16 | `c53cf6dbd729914c36e1a7cf4de853f6410e66cbaa74ab65ed16c599f2565c76` | TV `SP:S35`，页面名 “S&P 500 EQUAL WEIGHTED Health Care”。官方发布日 2006-06-20，免费表缺 2006-06-20 至 2006-11-01。官方约一年文件仍保留作对照 |
| theme-道琼斯美国精选REIT指数 | `theme-道琼斯美国精选REIT指数-tradingview.csv` | 7008 | 1998-12-31 → 2026-11-16 | `1b2e608ee868c15da254503c13a5aa091be0057ef65fac399c3d29af09f6b548` | TV `DJ:DWRTF`，页面名 “Dow Jones U.S. Select REIT Index (USD)”，与官方发布日对齐。未使用 `DJ:DJUSRE`。官方约一年文件仍保留作对照 |

## 部分完成：官方身份已确认，但所需窗口仍未完整覆盖（5）

官方 www.spglobal.com/spdji 在 2026-11-17 22:28（Asia/Taipei）从桌面浏览器打开成功（HTTP 200，首页截图 `screenshots/spdji-homepage-loaded-20261117.png`），不再是此前的 Akamai 403。Graph View → Export **无需登录**即可下载，但免费 XLS 日线最长大约一年：即使选择 10 Year，导出文件与 1 Year 相同。Table View 的 Daily 导出只是最新收盘快照，不是时间序列。2026-11-18 已用机器人邮箱完成官网免费注册并登录（页眉 “Hi Karin”；截图 `screenshots/spdji-register-success-logged-in-home.png`、`screenshots/spdji-logged-in-chart-range-10y.png`、`screenshots/spdji-logged-in-export-10y.png`）。登录后对消费精选（SP5CSSUP）选择 Graph View **10 YEAR**（页面没有 Max/All）再 Export，导出文件仍只有 251 个交易日（2025-11-17 4280.43 → 2026-11-16 4745.26），XLS 的 SHA256 `1168c83e484b9a2555b1381405866a80fcc9131fe1d4249a9f2182146b13aa84` 与此前未登录下载的 `theme-标普500消费精选指数-official-usd-pr-daily-20251117-20261116.xls` **完全相同**。图上能看到大约 2017–2026 的走势（10 Yr Return 10.87% annualized，as of Nov 16, 2026），但导出文件没有更长历史。对照文件留在包内：`official-SP5CSSUP-SP500-Consumer-Select-15-60-USD-PR-graph-10y-selected-2025-11-17_2026-11-16.xls`（同一份字节）及其二次转换 csv，以及 Table View 最新收盘快照 `official-SP5CSSUP-SP500-Consumer-Select-15-60-USD-PR-table-daily-latest-close-asof-2026-11-16.xls`（不是时间序列）。免费网站账号不能加长官方日线。未使用付费 SPICE。

权威文件是官方 `.xls`；同名 `.csv` 是从该 XLS 用 LibreOffice 抽出的 `date,close`，便于核对，不是另一来源。这 5 条都覆盖不了所需窗口，因此仍不算已完成。SPAHLVCP、SP5NENRS 在 TradingView 上仍无代码。SPGOGUP 已用 Wayback 官方日线覆盖所需窗口，改入上文「已完成」。消费精选、品质消费、中国新经济已另有 TradingView 二级日线，详见下表，但仍有缺口，不升为已完成。S35 与 DWRTF 已改入上文「已完成」。

| 容器 | 官方名称 / 代码 | 文件 | 行数 | 区间 | SHA256（xls / csv） | 发布日 | 备注 |
|---|---|---|---|---|---|---|---|
| theme-SPAHLVCP | S&P Access Hong Kong Low Volatility High Dividend Index **(CNY)** Price Return | `theme-SPAHLVCP-official-cny-pr-daily-20251117-20261117.xls` + `.csv` | 243 | 2025-11-17（1389.31）→ 2026-11-17（1290.50） | xls `41c3f7cd995d5d89c0db98735ac00051396d3b3cf4185da1a49b3d1eca64c94d` / csv `7f0d1baadf69b1cd0335cd3a0df1e3e4029626dc4716001c158648415994e373` | 2017-02-20（First Value 2011-01-31，未作发布日） | 切换到 CNY+PR 后，资料页默认代码仍显示港币 SPAHLVHP / SPAHLVHT，CNY 代码 SPAHLVCP 未再印出，但导出序列名完全一致。所需窗口自 2017-02-20 → 2023-12-08+30d，未覆盖 |
| theme-S&P 500 Energy Sector Index(NTR) | S&P 500 Energy (Sector) (Net TR)；NTR **SP5NENRS**（Reuters `.NTRGSPE`） | `theme-S&P 500 Energy Sector Index(NTR)-official-usd-ntr-daily-20251117-20261116.xls` + `.csv` | 251 | 2025-11-17（628.31）→ 2026-11-16（907.74） | xls `d4f5937c1cac74f9e88811342f31ec9a041194cae6874b157be26f2b350f3911` / csv `2e18ca92aaf0f27da40070ce9591bf40e333f3be8c87ffd6e52850d16644096e` | 1996-06-28（Quick Facts；NTR 图另有 “earliest possible launch date is not available” 的保守提示。First Value 1989-09-11，未作发布日） | 已确认是净总回报，不是价格收益。所需窗口自 1996-06-28 → 2015-02-17+30d，未覆盖 |
| theme-标普500消费精选指数 | S&P 500 Consumer Select 15/60 Index；USD PR **SP5CSSUP** / `.SP5CSSUP`（不是 SP500-25） | `theme-标普500消费精选指数-official-usd-pr-daily-20251117-20261116.xls` + `.csv` | 251 | 2025-11-17（4280.43）→ 2026-11-16（4745.26） | xls `1168c83e484b9a2555b1381405866a80fcc9131fe1d4249a9f2182146b13aa84` / csv `31a6f3660119e0977b2058ebd48bc3cfbb3e32ec9bab18cba6f4b5a063cf065e` | 2022-11-21（First Value 2012-03-16，未作发布日） | 官方中文名「标普500消费精选指数」。这就是官方名称，不是近称。所需窗口自 2022-11-21 → 2024-02-02+30d，未覆盖 |
| theme-标普美国品质消费股票指数 | Consumer Discretionary Select Sector Index；USD PR **IXY** / `.IXY`（官方 ticker 表已印出） | `theme-标普美国品质消费股票指数-official-usd-pr-daily-20251117-20261116.xls` + `.csv` | 251 | 2025-11-17（2310.67）→ 2026-11-16（2386.14） | xls `762b28798ff245d32a8e25c4ba41a4ab96193fc34d1eb07e1c2409aa7f0b6046` / csv `c57a3120cd39c674e00985bc0a9f1860fcc72f9a2b378e10a1218a4ec03a6fc6` | 1998-12-16（First Value 印的是 2003-07-01，晚于发布日，按页面原样记录，未作发布日） | 官方中文名「标普可选消费品精选行业指数」。英文页 H1 省略了 S&P 前缀。IXY 现为这只指数的官方价格收益代码，不是近称替代。不是 Quality 指数，也不是 S&P 500 Consumer Discretionary (Sector) 兄系。所需窗口自 1998-12-16 → 2016-04-06+30d，未覆盖 |
| theme-标普中国新经济行业指数 | S&P New China Sectors (A-shares Capped) Index；USD PR **SPNCSCUP**（默认港币 PR 为 SPNCSCHP） | `theme-标普中国新经济行业指数-official-usd-pr-SPNCSCUP-daily-20251117-20261116.xls` + `.csv` | 259 | 2025-11-17（1951.09）→ 2026-11-16（1457.47） | xls `c0a8013206ec237d3c6a4b83e0988a5b22a91251bc99ad0d50739280c2f265c0` / csv `30b34768c360f1c6457cc3921c25b4cd14f1a96bf937b728ef97b172572aaa27` | 2018-12-24（First Value 2010-12-31，未作发布日） | 只取 A 股上限版，未用无上限或 Ex-A-Share。页面默认头条是港币价格收益 1,470.99；本文件为切换到 USD 后的官方价格收益。NTR（SPNCSCHN / SPNCSCUN）未用。所需窗口自 2018-12-24 → 2020-10-23+30d，未覆盖。Dev remain pass 2：发布日 2018-12-24 已从官方 Quick Facts 确认，不是从 TV 起始日推断。2018-12-24 至 2020-05-13 的第二套独立日线仍未找到；FT 仍从 2020-05-14 2004.75 起。仍留在部分完成。未用无上限、Ex-A-Share 或 NTR |


### TradingView 补充（这 3 条仍算部分完成）

TradingView 均为免费 Supercharts Table 视图抄表（已登录免费账号 wmcmz8h）；**未使用** Plus / Download chart data。2026-11-17 延迟 bar 已从交付或进行中交付文件剔除。

| 容器 | 文件 | 行数 | 区间 | SHA256 | 备注 |
|---|---|---|---|---|---|
| theme-标普500消费精选指数 | `theme-标普500消费精选指数-tradingview.csv` | 770 | 2023-10-23（3040.69）→ 2026-11-16（4745.26） | `9b5cc311ffa6c8cfca0d409f1d712d368e5c3503441fa4c08d6776845a6dcbc5` | TV `SP:SP5CSSUP`，页面名 “S&P 500 Consumer Select 15/60 Index (USD)”。与官方约一年重叠 **251/251 精确吻合**。免费表始于 2023-10-23（Change ∅），发布日 2022-11-21 至 2023-10-22 约 240 个工作日仍缺，所需窗口只覆盖后段。周中缺口为美国假期，另有与其他 SP 代码相同的 2025-01-09。2026-11-17 延迟 bar 4747.96 只留在 `-full.csv` |
| theme-标普美国品质消费股票指数 | `theme-标普美国品质消费股票指数-tradingview-partial-inprogress.csv`（进行中，不是交付文件） | 5022 | 2006-04-28（340.63）→ 2026-11-16（2386.14） | `335c6de6ca73cf8de92ff4c4044f192d745d973c465f8347a3f1c57b44943259` | TV `SP:IXY`，页面名 “Consumer Discretionary Select Sector Index”，身份正确。已从 2012-12-27 往前抄到 2006-04-28；2008-08-15 与 2012-12-27 接缝均逐行一致，旧段未改写。仍未到发布日 1998-12-16，表上还有更早行，但尚未抄完，也未截到最早一行，故仍不写交付名 `…-tradingview.csv`。与官方约一年重叠仍是 236/251（缺的 15 日在免费表上可见，不是抄漏）。与 FT 重叠 5021/5022，中位数 0，2 日略高于 0.01%（2010-03-11 约 0.056%，2008-07-01 约 0.014%）。2007-01-02 在 TV 与 FT 都没有，未编造 |
| theme-标普中国新经济行业指数 | `theme-标普中国新经济行业指数-tradingview.csv` | 1784 | 2018-12-24（1551.58）→ 2026-06-26（1463.21） | `676509555eef750001bf385bb3782e59181cb6b78bf262d405052df4bf418893` | TV `SP:SPNCSCUP`，页面名 “S&P New China Sectors (A-shares Capped) Index (USD)”。从官方发布日起始。免费表最新一行仍是 2026-06-26（再次截图确认），之后未编造。2021-05-12→2022-12-30 小步长重抄 261 行全部已在文件中且完全一致（0 个新日期），因此未改写交付文件。2021–2022 缺口在表上可见（如 2021-11-30 下接 12-08，截图 `SP-SPNCSCUP-table-2021-nov-dec.png`）。与官方重叠 158 日，median \|rel\|=0，4 日略高于 0.01%，max \|rel\|≈0.020748%。所需窗口内（至 2020 年底）只有元旦缺口 |

## 正在做

- 官网免费注册已完成并已登录，但 10 Year 官方日线导出仍只有约一年。免费账号加长官方历史这条路已经关闭；SPICE 付费仍不用。
- Dev 已查完先前指定的四个 FT 缺口窗口，文件在 `d37-remain-20261118/`。Manager 已核对 SHA256、行数和与 FT 的重叠。SPGOGUP 已用 Wayback 官方日线补上，改入已完成。另外三条仍没有：SP5NENRS 1996-06-28 至 1998-12-30、SPAHLVCP 发布日至 2017-08-03、消费精选 2022-11-21/22/23。没有用近称、价格收益或基期 1000 替代。尚未入库，也未开 `cursor/d37-r6`。
- TradingView `SP:IXY` 进行中文件已抄到 2006-04-28（5022 行），接缝完好；表上还有更早行。先停止连续翻表，因为 FT 已从发布日 1998-12-16 覆盖到 2026-11-16，并与官方一年 251/251 精确吻合。
- Dev remain pass 2 的文件在 `d37-remain-20261118-pass2/`。SPSIBI 所需窗口头、DJSOEP 与 SPSIOP 发布日后几天已补上，这三条仍在已完成。S5INFT 大部分已补上，2001 缺口当时仍缺；pass 3 已用公开 CNBC 日线补上，仍在已完成。SPNCSCUP 发布日已从官方 Quick Facts 确认为 2018-12-24，第二套独立日线仍无，留在部分完成。能源净总回报、SPAHLVCP、消费精选这三段没有新填充。
- Dev remain pass 3 的文件在 `d37-remain-20261118-pass3/`。S5INFT 的 2001 缺口已由公开 CNBC 日线补上，不是官方日线，仍在已完成。SPAHLVCP 2017-02-20 至 2017-08-03、中国新经济 2018-12-24 至 2020-05-13、能源净总回报 1996-06-28 至 1998-12-30、消费精选 2022-11-21/22/23 本批仍未补上，未编造。
- 下一步：Manager 继续补官方富时、新交所和恒生完整日线。上面四段仍卡在部分完成。
- 部分提交 PR 已开：[#312](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/312)，分支 `grok/d37-r6-partial`。本批 `d37-remain-20261118-pass3/` 将追加到同一 PR。不要合并，也不要入库。入库仍等整包完成。

每做完一批，追加提交到同一分支，并更新本文件。

## 卡住（及卡在哪一步）

### 完全还没有交付日线（0 / 36）

36 条现在都至少有一段官方或已允许的二级日线。没有完全空白的容器。

### 官方约 1 年已取、所需窗口未覆盖（5）

| 容器 | 卡在哪一步 |
|---|---|
| theme-SPAHLVCP、theme-S&P 500 Energy Sector Index(NTR) | 免费 Graph View 导出上限约一年；登录免费账号也不能加长。TradingView 无这两只代码。Dev 本批仍未找到允许的日线。SPAHLVCP 仍从 FT 2017-08-04 1231.02 起（官方重叠 243/243，但 2025-11-28 差 0.1766%，窗口内多 13 个日期，不能当官方用；发布日 2017-02-20 至 2017-08-03 的 CNY PR 仍缺；未用港币代码或 ETF）。Dev remain pass 3：三份官方 Wayback 页已打开，只是介绍页或空壳，没有嵌入官方日线；widget API 没有归档。SP5NENRS/NTRGSPE 仍从 FT 1998-12-31 100.00 起（官方 NTR 251/251，max \|rel\|=0.00157%）。Dev remain pass 3：CNBC `.NTRGSPE` 返回 0 根；1996-06-28 至 1998-12-30 仍无净总回报日线，未用价格收益替代。SPICE 付费未用 |
| theme-标普500消费精选指数 | TradingView 已取 2023-10-23→2026-11-16，与官方 251/251 精确吻合。FT `SP5CSSUP:IOM` 从 2022-11-25 3033.79 补到 2023-10-20（与官方 251/251 精确）。Dev remain pass 3：CNBC 第一根已是 2022-11-25 3033.7884，2022-11-21/22/23 仍没有收盘；未把基期 1000（基日 2012-03-16）写成上市日收盘，未编造。暂不入库 |
| theme-标普美国品质消费股票指数 | TradingView 进行中文件已抄到 2006-04-28，仍未到发布日，也未截到免费表最早一行。FT `IXY:PSE` 已覆盖 1998-12-16→2026-11-16（7022 行），官方重叠 251/251 精确。TV 2021–2026 的表内缺口仍在。暂不入库 |
| theme-标普中国新经济行业指数 | TradingView 已从发布日抄到 2026-06-26；所需窗口内基本干净。FT `SPNCSCUP:IOM` 从 2020-05-14 起到 2026-11-16，可补 2021–2022 表内缺口和 2026-06-26 之后，但 2026-09-28 与官方差 0.4636%，不能当官方序列直接用。Dev remain pass 2：发布日 2018-12-24 已从官方 Quick Facts 确认，不是从 TV 起始日推断。Dev remain pass 3：2018-12-24 至 2020-05-13 的第二套独立日线仍未找到。官方 2025-11-14 Wayback 页没有嵌入 `indexLevels`；CNBC/FT 仍从 2020-05-14 起（FT 第一根 2004.75）。未用无上限、Ex-A-Share 或 NTR，未编造。仍留在部分完成，暂不入库 |

### 已有二级日线、但官方免费日线仍缺

| 问题 | 卡在哪一步 |
|---|---|
| 官方 SGX 价格收益日线（EMASIAUP、ASIATECP） | PR 产品页 404；官方免费 Prices & Chart 只有 NTR（EMASIAUN / ASIATECN）且无 CSV；historical-data 为商业订单，未用 |
| 官方 FTSE 价格收益日线（GPCSP006、FISAULM 族） | 匿名 factsheet / Historic Values 可用，但 Historic Values 目前只有月末或 Net Tax 兄系（如 GPCSP007），不能当作日线价格入库 |
| 官方恒生 INdex360 完整日线 | 免费历史仍只有 Past month。12 条 Priority A 官方文件截至 2026-11-16（20 日）；HSCEI 官方文件截至 2026-11-17（21 日）。完整历史未开放 |
| theme-恒生中国企业指数 官方发布日 | INdex360 Overview → Profile 显示 Launch Date **19 Jul 2017**（Base Value 2000）。官方目录 發佈日为 **08-08-1994**（首个指数点 03-01-2000）。两者都是官方来源，冲突未决；`publish_date` 暂记未核对，避免按 2017-07-19 误裁二级源。与 HSFML25 同类（INdex360 也显示 19 Jul 2017） |
| 已有 TV 二级源的 4 条标普/道琼斯（S5INFT、SPSIBI、DJSOEP、SPSIOP） | 四条仍在已完成：所需窗口的大部分已经盖住。Dev remain pass 2：SPSIBI 2006-01-27 至 2014-05-05 已由官方 Wayback `indexLevels`（indexId 2331，USD PRICE RETURN，快照 20141221042442）补上，2081 行，SHA256 `356b3fb9a3c977b0ad2d4298324d5259b745c864df9dbf74ed458a12adc7a324`；与 TV 2014-05-06 至 2014-12-19 重叠 160/160，四舍五入到两位精确；未裁切的 2004-12-20 起文件是发布前回补，不用于所需窗口。DJSOEP 2006-04-28 至 2006-05-04 已由 FT `DJSOEP:DJI` 补上，5 个交易日 6355.52 → 6438.07，TV 接缝 2006-05-05 6523.51 精确，官方约一年 251/251 精确（官方一年多 2026-04-24）。SPSIOP 2006-06-19 至 2006-06-22 已由 FT `SPSIOP:IOM` 补上，4 个交易日 5070.13 → 5187.6，TV 接缝 2006-06-23 5448.80 精确，官方约一年 252/252 精确，含 2026-03-09 官方/FT 6226.42（TV 仍是 6430.97，不能当官方）。S5INFT 1996-06-28 至 2012-09-24 的大部分已由 FT `SP500-45:IOM` 补上，3864 行 159.84 → 502.22。Dev remain pass 3：2001-01-02 至 2001-12-04 已由允许的公开 CNBC 日线补上（Reuters `.SPLRCT`，issue_id 603229，不是官方日线，未用 IXT），230 行，444.9235 → 366.8393，SHA256 `9463cf2e4c271bb95222ed5634853a6885a439275f78299fdb84892fd3eba75f`。另 11 个工作日是纽交所假日和 2001-09-11 至 2001-09-14 停市。官方约一年重叠 252/252 精确。与 FT 接缝在两位小数上吻合。SPICE 未用 |
| 东证指数 `publish_date` | 事实说明书基准日 1968-01-04 已记录，发布日未核对 |
| DAXK `publish_date` | 未核对 |

## 本包有意不作为交付 / 入库的文件

- `_tv_raw_*`、`_bcb_sgs1_raw/`：抄表或下载的工作文件，不入库。
- 带 `-full` 后缀的 CSV：未裁或含未确认当日 bar 的副本，不入库。
- `theme-标普美国品质消费股票指数-tradingview-partial-inprogress.csv` 及其 `-full`、`-smallsteps`、`-smallsteps-full`，以及 `-before-pre2012-extend` / `-before-pre2008-extend` 备份：IXY 未抄完的进行中文件，不作为交付、不入库。当前进行中文件从 2006-04-28 起。
- `theme-标普中国新经济行业指数-tradingview-before-2021-2022-fill.csv`：补漏前备份，与当前交付文件相同，不单独入库。

- `official-SP5CSSUP-SP500-Consumer-Select-15-60-USD-PR-graph-10y-selected-2025-11-17_2026-11-16.xls` 及其 `.csv`：登录后 10 Year 导出对照，XLS 与已有官方约一年文件字节相同，不是新序列；csv 为二次转换，不是第二源。
- `official-SP5CSSUP-SP500-Consumer-Select-15-60-USD-PR-table-daily-latest-close-asof-2026-11-16.xls`：Table View 最新收盘快照，不是日线序列。
- `theme-法兰克福DAX指数-eastmoney.csv`：头条绩效 DAX，不是 DAXK 第二源。
- FTSE Net Tax 月末或兄系文件（如 GPCSP007）：只作说明书对照，不当日线价格。
- `theme-MSCI China Value Weighted Index-official-price-monthly-from-launch-20120116.csv`：更长窗口会变成月线，且可能含发布日前回测，不用于日线入库。

- `d37-remain-20261118/theme-SPGOGUP-usspindices-wayback-usd-pr-daily-20050124-20150123.csv`：同一官方快照的未裁切序列（2005-01-24 起），含发布日 2011-07-08 前的回补，不作为所需窗口、不入库。
- `d37-remain-20261118/theme-SPGOGUP-usspindices-wayback-usd-pr-daily-20110708-20150123.csv`：同一官方来源延伸到 2015-01-23，只作与 FT 重叠核对，不是第二源，不单独入库。
- `d37-remain-20261118-pass2/theme-SPSIBI-usspindices-wayback-usd-pr-daily-20041220-20141219.csv`：同一官方快照的未裁切序列，含发布日 2006-01-27 前的回补，不作为所需窗口、不入库。
- `d37-remain-20261118-pass2/` 里带 `-incl-tv-seam` 的 CSV、S5INFT 的 OHLC 副本，以及 `raw/`：接缝或原始证据，不单独入库。
- `d37-remain-20261118-pass3/theme-S5INFT-cnbc-SPLRCT-usd-pr-daily-20001215-20011231.csv` 与同目录 OHLC：接缝或原始副本，不单独入库。SPAHLVCP 的 Wayback 页和各未补窗口的 raw 只作阴性证据。

证据文件（截图、`sources.csv`、官方 PDF/XLS、各 `*-NOTE.txt`、`theme-东证指数-pdfs/`、`d37-remain-20261118/`、`d37-remain-20261118-pass2/`、`d37-remain-20261118-pass3/` 的 raw 与 README）与交付 CSV 一并存于本目录，供核对，不单独入库。
