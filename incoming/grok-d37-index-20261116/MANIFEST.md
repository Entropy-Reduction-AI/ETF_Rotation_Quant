# D37 第六轮部分提交 MANIFEST

- 日期：2026-11-18 01:17（Asia/Taipei，UTC+8；本批更新：IXY 的 TradingView 进行中文件已抄到 2006-04-28；FT 长日线已入包但尚未入库）
- 分支：`grok/d37-r6-partial`（追加提交用同一分支）
- 路径：`incoming/grok-d37-index-20261116/`
- 本包用途：给 Orchestrator 看进度、更新数据看板。
- 入库：仍等 36 条全部完成后再由 Dev 统一做；Reviewer 签收后，再请 Manager 合并。本 PR **不要合并**，也不要开 `cursor/d37-r6` 入库分支。

派单共 36 条（Priority A 30 + Priority B 6）。下方「已完成」指本包已有可交的日线 CSV（官方或已允许的二级源），且至少覆盖所需窗口的大部分，不是入库通过。另有 6 条官方身份已确认、但免费导出只有约一年且尚无可用的长二级日线，记在「部分完成」，不计入 30/36。S35 与 DWRTF 已有官方约一年 + TradingView 长日线（重叠 251/251 精确吻合），计入已完成。36 条现在都至少有一段日线。

## 已完成（30 / 36）

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
| theme-标普500信息科技指数 | `theme-标普500信息科技指数-tradingview.csv` | 3547 | 2012-09-25 → 2026-11-16 | `4e04cba0c5f50cd53d2b54e0b2dc3fd3529386f31dd656d9e0877fa881304bb7` | TV `S5INFT`。官方 spdji 仍 403。表中若干周中缺口按原样保留 |
| theme-标普生物科技精选行业指数 | `theme-标普生物科技精选行业指数-tradingview.csv` | 3153 | 2014-05-06 → 2026-11-16 | `e642543a54a6e214317d03462e8d297c02d2f79e6b175568b3713fe7d01b1683` | TV `SPSIBI`。官方 spdji 仍 403 |
| theme-道琼斯美国石油开发与生产指数 | `theme-道琼斯美国石油开发与生产指数-tradingview.csv` | 5166 | 2006-05-05 → 2026-11-16 | `c0da503c67117d8e70c6e1ffc02cf741318bdf911336507b7268b6e30e1675b0` | TV `DJSOEP`；页面名为 Dow Jones U.S. Select Oil Exploration & Production Index。官方 spdji 仍 403 |
| theme-标普石油天然气勘探及生产精选行业指数 | `theme-标普石油天然气勘探及生产精选行业指数-tradingview.csv` | 5126 | 2006-06-23 → 2026-11-16 | `aba06667e82696bcb1f79ed2ceb6b1914c54f1627b2971373f31fcfcee3b5038` | TV `SPSIOP`。官方 spdji 仍 403 |
| theme-恒生中国企业指数 | `theme-恒生中国企业指数-official-past-month.csv` | 21 | 2026-10-20 → 2026-11-17 | `3baea34e5fa7e30d67925e37ec71782802b52fd1e4598c7b901f69e40d6e229a` | 官方 INdex360 免费 Past month 价格收益，id 00014.00。2026-11-16 Day Close 7981.54 与东方财富、TradingView 过去 20 日全部精确吻合（max \|rel\|=0）。含已收盘的 2026-11-17（7904.37）。发布日冲突见下，未裁切二级源 |
| theme-恒生中国企业指数 | `theme-恒生中国企业指数-eastmoney.csv` | 7956 | 1994-08-08 → 2026-11-16 | `2a8cdfc18e3a7926f3522d4a5cf97e16954e89fa93e237b404c96ab7b4d83b20` | 东方财富二级源。与官方过去一月 20/20 精确吻合 |
| theme-恒生中国企业指数 | `theme-恒生中国企业指数-tradingview.csv` | 5780 | 2003-05-28 → 2026-11-16 | `db4a33a2b41856044aee60e9f9a98bae312feea51a6610f90318ea8c44ea2ae1` | TV `HSI:HSCEI`，页面名为 Hang Seng China Enterprises Index。免费表从 2003-05-28 起，缺官方发布日 1994-08-08 至 2003-05-27。与东方财富重叠 5777 日，median \|rel\|=0，max \|rel\|≈0.494993%（2007-09-25），9 日超过 0.01%。2026-11-17 延迟 bar 已剔除 |

> 说明：上表中四条标普/道琼斯 TradingView 二级源（S5INFT、SPSIBI、DJSOEP、SPSIOP）写于官方站点仍 403 之时。2026-11-17 22:28 起桌面浏览器已能打开官方 spdji（HTTP 200）；本批尚未补下这四条的官方长历史。


### 官方约一年 + TradingView 长日线（重叠精确吻合）

TradingView 均为免费 Supercharts Table 视图抄表（已登录免费账号）；**未使用** Plus / Download chart data。与官方约一年 XLS 重叠均为 251/251 日、median |rel|=0、max |rel|=0。2026-11-17 延迟 bar 已从交付文件剔除。

| 容器 | 文件 | 行数 | 区间 | SHA256 | 备注 |
|---|---|---|---|---|---|
| theme-标普500医疗保健等权重指数 | `theme-标普500医疗保健等权重指数-tradingview.csv` | 5038 | 2006-11-02 → 2026-11-16 | `c53cf6dbd729914c36e1a7cf4de853f6410e66cbaa74ab65ed16c599f2565c76` | TV `SP:S35`，页面名 “S&P 500 EQUAL WEIGHTED Health Care”。官方发布日 2006-06-20，免费表缺 2006-06-20 至 2006-11-01。官方约一年文件仍保留作对照 |
| theme-道琼斯美国精选REIT指数 | `theme-道琼斯美国精选REIT指数-tradingview.csv` | 7008 | 1998-12-31 → 2026-11-16 | `1b2e608ee868c15da254503c13a5aa091be0057ef65fac399c3d29af09f6b548` | TV `DJ:DWRTF`，页面名 “Dow Jones U.S. Select REIT Index (USD)”，与官方发布日对齐。未使用 `DJ:DJUSRE`。官方约一年文件仍保留作对照 |

## 部分完成：官方身份已确认，但免费日线只有约一年（6）

官方 www.spglobal.com/spdji 在 2026-11-17 22:28（Asia/Taipei）从桌面浏览器打开成功（HTTP 200，首页截图 `screenshots/spdji-homepage-loaded-20261117.png`），不再是此前的 Akamai 403。Graph View → Export **无需登录**即可下载，但免费 XLS 日线最长大约一年：即使选择 10 Year，导出文件与 1 Year 相同。Table View 的 Daily 导出只是最新收盘快照，不是时间序列。2026-11-18 已用机器人邮箱完成官网免费注册并登录（页眉 “Hi Karin”；截图 `screenshots/spdji-register-success-logged-in-home.png`、`screenshots/spdji-logged-in-chart-range-10y.png`、`screenshots/spdji-logged-in-export-10y.png`）。登录后对消费精选（SP5CSSUP）选择 Graph View **10 YEAR**（页面没有 Max/All）再 Export，导出文件仍只有 251 个交易日（2025-11-17 4280.43 → 2026-11-16 4745.26），XLS 的 SHA256 `1168c83e484b9a2555b1381405866a80fcc9131fe1d4249a9f2182146b13aa84` 与此前未登录下载的 `theme-标普500消费精选指数-official-usd-pr-daily-20251117-20261116.xls` **完全相同**。图上能看到大约 2017–2026 的走势（10 Yr Return 10.87% annualized，as of Nov 16, 2026），但导出文件没有更长历史。对照文件留在包内：`official-SP5CSSUP-SP500-Consumer-Select-15-60-USD-PR-graph-10y-selected-2025-11-17_2026-11-16.xls`（同一份字节）及其二次转换 csv，以及 Table View 最新收盘快照 `official-SP5CSSUP-SP500-Consumer-Select-15-60-USD-PR-table-daily-latest-close-asof-2026-11-16.xls`（不是时间序列）。免费网站账号不能加长官方日线。未使用付费 SPICE。

权威文件是官方 `.xls`；同名 `.csv` 是从该 XLS 用 LibreOffice 抽出的 `date,close`，便于核对，不是另一来源。这 6 条都覆盖不了所需窗口，因此仍不算已完成。SPAHLVCP、SPGOGUP、SP5NENRS 在 TradingView 上仍无代码。消费精选、品质消费、中国新经济已另有 TradingView 二级日线，详见下表，但仍有缺口，不升为已完成。S35 与 DWRTF 已改入上文「已完成」。

| 容器 | 官方名称 / 代码 | 文件 | 行数 | 区间 | SHA256（xls / csv） | 发布日 | 备注 |
|---|---|---|---|---|---|---|---|
| theme-SPAHLVCP | S&P Access Hong Kong Low Volatility High Dividend Index **(CNY)** Price Return | `theme-SPAHLVCP-official-cny-pr-daily-20251117-20261117.xls` + `.csv` | 243 | 2025-11-17（1389.31）→ 2026-11-17（1290.50） | xls `41c3f7cd995d5d89c0db98735ac00051396d3b3cf4185da1a49b3d1eca64c94d` / csv `7f0d1baadf69b1cd0335cd3a0df1e3e4029626dc4716001c158648415994e373` | 2017-02-20（First Value 2011-01-31，未作发布日） | 切换到 CNY+PR 后，资料页默认代码仍显示港币 SPAHLVHP / SPAHLVHT，CNY 代码 SPAHLVCP 未再印出，但导出序列名完全一致。所需窗口自 2017-02-20 → 2023-12-08+30d，未覆盖 |
| theme-标普全球石油指数 | S&P Global Oil Index；USD PR **SPGOGUP**（不是 SGES） | `theme-标普全球石油指数-official-usd-pr-SPGOGUP-daily-20251117-20261116.xls` + `.csv` | 261 | 2025-11-17（2004.24）→ 2026-11-16（2650.65） | xls `d91456aa170e44c3fbc94b7b203a40397848fee909ae1fac59b665d872576539` / csv `1c9df0f7b097bc2c971d14633c5d84de12673287b0ee632804c8a0edf932196d` | 2011-07-08（First Value 2000-08-31，未作发布日） | TradingView 仍无 SPGOGUP。所需窗口自 2011-07-08 → 2012-05-02+30d，未覆盖 |
| theme-S&P 500 Energy Sector Index(NTR) | S&P 500 Energy (Sector) (Net TR)；NTR **SP5NENRS**（Reuters `.NTRGSPE`） | `theme-S&P 500 Energy Sector Index(NTR)-official-usd-ntr-daily-20251117-20261116.xls` + `.csv` | 251 | 2025-11-17（628.31）→ 2026-11-16（907.74） | xls `d4f5937c1cac74f9e88811342f31ec9a041194cae6874b157be26f2b350f3911` / csv `2e18ca92aaf0f27da40070ce9591bf40e333f3be8c87ffd6e52850d16644096e` | 1996-06-28（Quick Facts；NTR 图另有 “earliest possible launch date is not available” 的保守提示。First Value 1989-09-11，未作发布日） | 已确认是净总回报，不是价格收益。所需窗口自 1996-06-28 → 2015-02-17+30d，未覆盖 |
| theme-标普500消费精选指数 | S&P 500 Consumer Select 15/60 Index；USD PR **SP5CSSUP** / `.SP5CSSUP`（不是 SP500-25） | `theme-标普500消费精选指数-official-usd-pr-daily-20251117-20261116.xls` + `.csv` | 251 | 2025-11-17（4280.43）→ 2026-11-16（4745.26） | xls `1168c83e484b9a2555b1381405866a80fcc9131fe1d4249a9f2182146b13aa84` / csv `31a6f3660119e0977b2058ebd48bc3cfbb3e32ec9bab18cba6f4b5a063cf065e` | 2022-11-21（First Value 2012-03-16，未作发布日） | 官方中文名「标普500消费精选指数」。这就是官方名称，不是近称。所需窗口自 2022-11-21 → 2024-02-02+30d，未覆盖 |
| theme-标普美国品质消费股票指数 | Consumer Discretionary Select Sector Index；USD PR **IXY** / `.IXY`（官方 ticker 表已印出） | `theme-标普美国品质消费股票指数-official-usd-pr-daily-20251117-20261116.xls` + `.csv` | 251 | 2025-11-17（2310.67）→ 2026-11-16（2386.14） | xls `762b28798ff245d32a8e25c4ba41a4ab96193fc34d1eb07e1c2409aa7f0b6046` / csv `c57a3120cd39c674e00985bc0a9f1860fcc72f9a2b378e10a1218a4ec03a6fc6` | 1998-12-16（First Value 印的是 2003-07-01，晚于发布日，按页面原样记录，未作发布日） | 官方中文名「标普可选消费品精选行业指数」。英文页 H1 省略了 S&P 前缀。IXY 现为这只指数的官方价格收益代码，不是近称替代。不是 Quality 指数，也不是 S&P 500 Consumer Discretionary (Sector) 兄系。所需窗口自 1998-12-16 → 2016-04-06+30d，未覆盖 |
| theme-标普中国新经济行业指数 | S&P New China Sectors (A-shares Capped) Index；USD PR **SPNCSCUP**（默认港币 PR 为 SPNCSCHP） | `theme-标普中国新经济行业指数-official-usd-pr-SPNCSCUP-daily-20251117-20261116.xls` + `.csv` | 259 | 2025-11-17（1951.09）→ 2026-11-16（1457.47） | xls `c0a8013206ec237d3c6a4b83e0988a5b22a91251bc99ad0d50739280c2f265c0` / csv `30b34768c360f1c6457cc3921c25b4cd14f1a96bf937b728ef97b172572aaa27` | 2018-12-24（First Value 2010-12-31，未作发布日） | 只取 A 股上限版，未用无上限或 Ex-A-Share。页面默认头条是港币价格收益 1,470.99；本文件为切换到 USD 后的官方价格收益。NTR（SPNCSCHN / SPNCSCUN）未用。所需窗口自 2018-12-24 → 2020-10-23+30d，未覆盖 |


### TradingView 补充（这 3 条仍算部分完成）

TradingView 均为免费 Supercharts Table 视图抄表（已登录免费账号 wmcmz8h）；**未使用** Plus / Download chart data。2026-11-17 延迟 bar 已从交付或进行中交付文件剔除。

| 容器 | 文件 | 行数 | 区间 | SHA256 | 备注 |
|---|---|---|---|---|---|
| theme-标普500消费精选指数 | `theme-标普500消费精选指数-tradingview.csv` | 770 | 2023-10-23（3040.69）→ 2026-11-16（4745.26） | `9b5cc311ffa6c8cfca0d409f1d712d368e5c3503441fa4c08d6776845a6dcbc5` | TV `SP:SP5CSSUP`，页面名 “S&P 500 Consumer Select 15/60 Index (USD)”。与官方约一年重叠 **251/251 精确吻合**。免费表始于 2023-10-23（Change ∅），发布日 2022-11-21 至 2023-10-22 约 240 个工作日仍缺，所需窗口只覆盖后段。周中缺口为美国假期，另有与其他 SP 代码相同的 2025-01-09。2026-11-17 延迟 bar 4747.96 只留在 `-full.csv` |
| theme-标普美国品质消费股票指数 | `theme-标普美国品质消费股票指数-tradingview-partial-inprogress.csv`（进行中，不是交付文件） | 5022 | 2006-04-28（340.63）→ 2026-11-16（2386.14） | `335c6de6ca73cf8de92ff4c4044f192d745d973c465f8347a3f1c57b44943259` | TV `SP:IXY`，页面名 “Consumer Discretionary Select Sector Index”，身份正确。已从 2012-12-27 往前抄到 2006-04-28；2008-08-15 与 2012-12-27 接缝均逐行一致，旧段未改写。仍未到发布日 1998-12-16，表上还有更早行，但尚未抄完，也未截到最早一行，故仍不写交付名 `…-tradingview.csv`。与官方约一年重叠仍是 236/251（缺的 15 日在免费表上可见，不是抄漏）。与 FT 重叠 5021/5022，中位数 0，2 日略高于 0.01%（2010-03-11 约 0.056%，2008-07-01 约 0.014%）。2007-01-02 在 TV 与 FT 都没有，未编造 |
| theme-标普中国新经济行业指数 | `theme-标普中国新经济行业指数-tradingview.csv` | 1784 | 2018-12-24（1551.58）→ 2026-06-26（1463.21） | `676509555eef750001bf385bb3782e59181cb6b78bf262d405052df4bf418893` | TV `SP:SPNCSCUP`，页面名 “S&P New China Sectors (A-shares Capped) Index (USD)”。从官方发布日起始。免费表最新一行仍是 2026-06-26（再次截图确认），之后未编造。2021-05-12→2022-12-30 小步长重抄 261 行全部已在文件中且完全一致（0 个新日期），因此未改写交付文件。2021–2022 缺口在表上可见（如 2021-11-30 下接 12-08，截图 `SP-SPNCSCUP-table-2021-nov-dec.png`）。与官方重叠 158 日，median \|rel\|=0，4 日略高于 0.01%，max \|rel\|≈0.020748%。所需窗口内（至 2020 年底）只有元旦缺口 |

## 正在做

- 官网免费注册已完成并已登录，但 10 Year 官方日线导出仍只有约一年。免费账号加长官方历史这条路已经关闭；SPICE 付费仍不用。
- Dev 已从 FT 公开历史价取到这 6 条的更长次级日线，放在 `d37-longhist-20261118/`。Manager 已核对 SHA256、行数和官方重叠，数字一致。按官方缺失时的公开报价次级源收下，误差记下；浏览器历史表有订阅墙，数据来自公开 AJAX，不视为官方。尚未入库，也未开 `cursor/d37-r6`。
- TradingView `SP:IXY` 进行中文件已抄到 2006-04-28（5022 行），接缝完好；表上还有更早行。先停止连续翻表，因为 FT 已从发布日 1998-12-16 覆盖到 2026-11-16，并与官方一年 251/251 精确吻合。
- 下一步：补 FT 也没有的窗口——SPGOGUP 2011-07-08 至 2014-12-15、SP5NENRS 1996-06-28 至 1998-12-30、SPAHLVCP 2017-02-20 至 2017-08-03、消费精选 2022-11-21/22/23。中国新经济发布日至 2020-05-13 仍靠已有 TV。
- 分支 `grok/d37-r6-partial` 及其 PR 仍未开：需要 Owner 在 1:1 完成 GitHub CLI 登录后才能把本包推上去。入库仍等全部完成。

每做完一批，追加提交到同一分支，并更新本文件。

## 卡住（及卡在哪一步）

### 完全还没有交付日线（0 / 36）

36 条现在都至少有一段官方或已允许的二级日线。没有完全空白的容器。

### 官方约 1 年已取、所需窗口未覆盖（6）

| 容器 | 卡在哪一步 |
|---|---|
| theme-SPAHLVCP、theme-标普全球石油指数、theme-S&P 500 Energy Sector Index(NTR) | 免费 Graph View 导出上限约一年；登录免费账号也不能加长。TradingView 无这三只代码。FT 已有更长次级日线（见 `d37-longhist-20261118/`）：SPAHLVCP 从 2017-08-04 起（官方重叠 243/243，但 2025-11-28 差 0.1766%，窗口内多 13 个日期，不能当官方用；发布日至 2017-08-03 仍缺）；SPGOGUP 从 2014-12-16 起（官方 261/261，max \|rel\|=0.00206%，所需 2011–2012 仍缺）；SP5NENRS/NTRGSPE 从 1998-12-31 起（官方 NTR 251/251，max \|rel\|=0.00157%，1996-06-28 至 1998-12-30 仍缺）。SPICE 付费未用 |
| theme-标普500消费精选指数 | TradingView 已取 2023-10-23→2026-11-16，与官方 251/251 精确吻合。FT `SP5CSSUP:IOM` 从 2022-11-25 补到 2023-10-20（与官方 251/251 精确），仍缺 2022-11-21/22/23。暂不入库 |
| theme-标普美国品质消费股票指数 | TradingView 进行中文件已抄到 2006-04-28，仍未到发布日，也未截到免费表最早一行。FT `IXY:PSE` 已覆盖 1998-12-16→2026-11-16（7022 行），官方重叠 251/251 精确。TV 2021–2026 的表内缺口仍在。暂不入库 |
| theme-标普中国新经济行业指数 | TradingView 已从发布日抄到 2026-06-26；所需窗口内基本干净。FT `SPNCSCUP:IOM` 从 2020-05-14 起到 2026-11-16，可补 2021–2022 表内缺口和 2026-06-26 之后，但 2026-09-28 与官方差 0.4636%，不能当官方序列直接用。2018-12-24 至 2020-05-13 仍靠 TV。暂不入库 |

### 已有二级日线、但官方免费日线仍缺

| 问题 | 卡在哪一步 |
|---|---|
| 官方 SGX 价格收益日线（EMASIAUP、ASIATECP） | PR 产品页 404；官方免费 Prices & Chart 只有 NTR（EMASIAUN / ASIATECN）且无 CSV；historical-data 为商业订单，未用 |
| 官方 FTSE 价格收益日线（GPCSP006、FISAULM 族） | 匿名 factsheet / Historic Values 可用，但 Historic Values 目前只有月末或 Net Tax 兄系（如 GPCSP007），不能当作日线价格入库 |
| 官方恒生 INdex360 完整日线 | 免费历史仍只有 Past month。12 条 Priority A 官方文件截至 2026-11-16（20 日）；HSCEI 官方文件截至 2026-11-17（21 日）。完整历史未开放 |
| theme-恒生中国企业指数 官方发布日 | INdex360 Overview → Profile 显示 Launch Date **19 Jul 2017**（Base Value 2000）。官方目录 發佈日为 **08-08-1994**（首个指数点 03-01-2000）。两者都是官方来源，冲突未决；`publish_date` 暂记未核对，避免按 2017-07-19 误裁二级源。与 HSFML25 同类（INdex360 也显示 19 Jul 2017） |
| 已有 TV 二级源的 4 条标普/道琼斯（S5INFT、SPSIBI、DJSOEP、SPSIOP） | 官方站点现已能打开，但本批尚未补下这些指数的官方约一年对照日线。登录免费账号后的 10 Year 导出已证实仍只有约一年，因此即使补下，也盖不住所需窗口（长历史仍靠已有 TradingView 二级源） |
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

证据文件（截图、`sources.csv`、官方 PDF/XLS、各 `*-NOTE.txt`、`theme-东证指数-pdfs/` 月报）与交付 CSV 一并存于本目录，供核对，不单独入库。
