# v4-R1e 分组表（Manager）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: work log
- Status: complete
- Owner: project owner
- Task: v4-R1e D19-4 Manager 分组表
- Date: 2026-10-29（Asia/Taipei）
- Source: `results/v4/inventory/r1e/grouping.csv` @ main `4c5c165`
- 规则来源: 预注册第 2.2 版 §3.1；`group_rule` 列：`learned_index_name` / `index_code` / `mandated` / `mandated_code` / `benchmark_max_weight` / `cross_border_commodity` 等

## 口径

- **87** 个指数或商品组；成员合计 **198**（与普查 1:1）。
- `target_id` 为登记表容器 id（`maps_to`）。登记表总容器 **118**（含非本次 QDII 普查的既有 A 股等容器），见 census summary。
- 下表按 `target_id` 排序；成员为基金代码（空格分隔），只数在括号内。
- 不算收益。

## 分组总表

| 容器 id | 组名 / 键 | 规则 | 资产类 | n | 成员代码 |
| --- | --- | --- | --- | ---: | --- |
| `cross-border-commodity` | 跨境商品 (`cross-border-commodity`) | cross_border_commodity | 商品 | 3 | 160216 161815 165513 |
| `crude-oil` | 原油 (`crude-oil`) | cross_border_commodity | 商品 | 3 | 501018 160723 161129 |
| `gold` | 黄金 (`gold`) | cross_border_commodity | 商品 | 3 | 160719 161116 164701 |
| `hsi` | 恒生指数 (`HSI`) | learned_index_name | 美股和全球主题 | 7 | 513210 513600 513660 159920 160125 160924 164705 |
| `hstech` | 恒生科技指数 (`HSTECH`) | learned_index_name | 美股和全球主题 | 14 | 513010 513130 513180 513260 513380 513580 513890 520570 520590 520920 158042 159740 159741 159742 |
| `ndx100` | 纳斯达克100指数 (`NDX`) | learned_index_name | 美股和全球主题 | 13 | 513100 513110 513300 513390 513870 501312 159501 159513 159632 159659 159660 159696 159941 |
| `spx` | 标准普尔500指数 (`SPX`) | learned_index_name | 美股和全球主题 | 3 | 513500 513650 161125 |
| `spx` | SPXNTR (`SPXNTR`) | index_code | 美股和全球主题 | 2 | 159612 159655 |
| `theme-CES100` | 中华交易服务港股通精选100指数 (`CES100`) | learned_index_name | 美股和全球主题 | 1 | 513900 |
| `theme-H11146` | 中证港股通内地金融指数 (`H11146`) | learned_index_name | 美股和全球主题 | 2 | 513190 526090 |
| `theme-H50069` | 上证港股通指数 (`H50069`) | learned_index_name | 美股和全球主题 | 1 | 513990 |
| `theme-HSFML25` | 恒生中国（香港上市）30指数 (`HSFML25`) | learned_index_name | 美股和全球主题 | 1 | 520560 |
| `theme-HSISC` | 恒指港股通指数 (`HSISC`) | learned_index_name | 美股和全球主题 | 5 | 520770 520820 520940 520960 526070 |
| `theme-HSSC50` | 恒生港股通50指数 (`HSSC50`) | learned_index_name | 美股和全球主题 | 1 | 520950 |
| `theme-HSSCAMHI` | 恒生港股通汽车主题指数 (`HSSCAMHI`) | learned_index_name | 美股和全球主题 | 1 | 520730 |
| `theme-HSSCHKY` | 恒生港股通高股息率指数 (`HSSCHKY`) | learned_index_name | 美股和全球主题 | 1 | 513690 |
| `theme-HSSCITI` | 恒生港股通科技主题指数 (`HSSCITI`) | learned_index_name | 美股和全球主题 | 2 | 520670 520840 |
| `theme-HSSCNE` | 恒生港股通新经济指数 (`HSSCNE`) | learned_index_name | 美股和全球主题 | 1 | 513320 |
| `theme-HSSCPB` | 恒生港股通创新药精选指数 (`HSSCPB`) | learned_index_name | 美股和全球主题 | 2 | 520690 520880 |
| `theme-HSSCSOY` | 恒生港股通中国央企红利指数 (`HSSCSOY`) | learned_index_name | 美股和全球主题 | 1 | 513920 |
| `theme-HSSCT` | 恒生港股通中国科技指数 (`HSSCT`) | learned_index_name | 美股和全球主题 | 2 | 513160 520980 |
| `theme-MSCI China Value Weighted Index` | MSCI China Value Weighted Index (`MSCI China Value Weighted Index`) | benchmark_max_weight | 美股和全球主题 | 1 | 161229 |
| `theme-MSCI USA 50 Index` | MSCI USA 50 Index (`MSCI美国50指数`) | index_name | 美股和全球主题 | 2 | 513850 159577 |
| `theme-PHLX Semiconductor Sector Index` | PHLX Semiconductor Sector Index (`PHLX Semiconductor Sector Index`) | mandated | 美股和全球主题 | 1 | 501225 |
| `theme-S&P 500 Energy Sector Index(NTR)` | S&P 500 Energy Sector Index(NTR) (`S&P 500 Energy Sector Index(NTR)`) | benchmark_max_weight | 美股和全球主题 | 1 | 163208 |
| `theme-SPAHLVCP` | 标普港股通低波红利指数 (`SPAHLVCP`) | learned_index_name | 美股和全球主题 | 2 | 513630 520610 |
| `theme-iEdge Emerging Asia Select 50 Index` | 新交所新兴亚洲精选50指数 (`EMASIAUP`) | learned_index_name | 美股和全球主题 | 1 | 520580 |
| `theme-东京日经225指数` | 日经225指数 (`N225`) | learned_index_name | 美股和全球主题 | 4 | 513000 513520 513880 159866 |
| `theme-东证指数` | 东证指数 (`TPX`) | learned_index_name | 美股和全球主题 | 1 | 513800 |
| `theme-中信证券印度ETP指数` | 该基金无跟踪标的 (`中信证券印度ETP指数`) | benchmark_max_weight | 美股和全球主题 | 1 | 164824 |
| `theme-中证全球中国互联网人民币指数` | 中证全球中国互联网指数 (`中证全球中国互联网指数`) | index_name | 美股和全球主题 | 1 | 513220 |
| `theme-中证全球中国教育主题人民币指数` | 中证全球中国教育主题指数 (`中证全球中国教育主题指数`) | index_name | 美股和全球主题 | 1 | 513360 |
| `theme-中证国新港股通央企红利指数` | 中证国新港股通央企红利指数 (`中证国新港股通央企红利指数`) | index_name | 美股和全球主题 | 3 | 520660 520900 520990 |
| `theme-中证海外中国互联网30人民币指数` | 中证海外中国互联网30人民币指数 (`中证海外中国互联网30指数`) | benchmark_max_weight | 美股和全球主题 | 2 | 159605 159607 |
| `theme-中证海外中国互联网50人民币指数` | 中证海外中国互联网50指数 (`H30533`) | learned_index_name | 美股和全球主题 | 1 | 513050 |
| `theme-中证海外中国互联网指数` | 该基金无跟踪标的 (`中证海外中国互联网指数`) | benchmark_max_weight | 美股和全球主题 | 2 | 160644 164906 |
| `theme-中证港股通50指数` | 中证港股通50指数 (`中证港股通50指数`) | index_name | 美股和全球主题 | 1 | 513550 |
| `theme-中证港股通互联网指数` | 中证港股通互联网指数 (`中证港股通互联网指数`) | index_name | 美股和全球主题 | 8 | 513040 513720 513770 520630 520650 520740 520790 520910 |
| `theme-中证港股通信息技术综合指数` | 中证港股通信息技术综合指数 (`中证港股通信息技术综合指数`) | index_name | 美股和全球主题 | 7 | 513240 520710 520750 526000 526030 526050 526060 |
| `theme-中证港股通创新药指数` | 中证港股通创新药指数 (`中证港股通创新药指数`) | index_name | 美股和全球主题 | 3 | 513780 520700 520970 |
| `theme-中证港股通医疗主题指数` | 中证港股通医疗主题指数 (`中证港股通医疗主题指数`) | index_name | 美股和全球主题 | 4 | 513620 520510 520850 526010 |
| `theme-中证港股通医药卫生综合指数` | 中证港股通医药卫生综合指数 (`中证港股通医药卫生综合指数`) | index_name | 美股和全球主题 | 2 | 513200 513700 |
| `theme-中证港股通央企红利指数` | 中证港股通央企红利指数 (`中证港股通央企红利指数`) | index_name | 美股和全球主题 | 1 | 513910 |
| `theme-中证港股通汽车产业主题指数` | 中证港股通汽车产业主题指数 (`中证港股通汽车产业主题指数`) | index_name | 美股和全球主题 | 4 | 520600 520680 520720 520780 |
| `theme-中证港股通消费主题指数` | 中证港股通消费主题指数 (`中证港股通消费主题指数`) | index_name | 美股和全球主题 | 3 | 513070 513230 513590 |
| `theme-中证港股通科技指数` | 中证港股通科技指数 (`中证港股通科技指数`) | index_name | 美股和全球主题 | 7 | 513020 513150 513560 513860 513980 520530 520860 |
| `theme-中证港股通金融服务指数` | 中证香港300金融服务指数 (`H30106`) | learned_index_name | 美股和全球主题 | 1 | 513140 |
| `theme-中证港股通非银行金融主题指数` | 中证港股通非银行金融主题指数 (`中证港股通非银行金融主题指数`) | index_name | 美股和全球主题 | 1 | 513750 |
| `theme-中证港股通高股息投资港元指数` | 中证港股通高股息投资指数 (`中证港股通高股息投资指数`) | index_name | 美股和全球主题 | 4 | 513530 513820 513830 520810 |
| `theme-中证韩交所中韩半导体指数` | 中证韩交所中韩半导体指数 (`中证韩交所中韩半导体指数`) | index_name | 美股和全球主题 | 1 | 513310 |
| `theme-中证香港内地国有企业港元指数` | 中证香港内地国有企业指数 (`H11153`) | learned_index_name | 美股和全球主题 | 2 | 513810 159519 |
| `theme-中证香港创新药港币指数` | 中证香港创新药指数 (`中证香港创新药指数`) | index_name | 美股和全球主题 | 1 | 513120 |
| `theme-中证香港科技指数指数` | 中证香港科技指数指数 (`中证香港科技指数`) | benchmark_max_weight | 美股和全球主题 | 2 | 159747 159750 |
| `theme-中证香港证券投资主题指数` | 中证香港证券投资主题指数 (`中证香港证券投资主题指数`) | index_name | 美股和全球主题 | 1 | 513090 |
| `theme-富时亚太低碳精选指数` | GPCSP006 (`GPCSP006`) | index_code | 美股和全球主题 | 1 | 159687 |
| `theme-富时沙特阿拉伯指数` | FSSAULM (`FSSAULM`) | index_code | 美股和全球主题 | 1 | 159329 |
| `theme-富时沙特阿拉伯指数` | 富时沙特阿拉伯指数 (`WISAUNT`) | learned_index_name | 美股和全球主题 | 1 | 520830 |
| `theme-巴克莱资本美国综合债券指数` | 该基金无跟踪标的 (`巴克莱资本美国综合债券指数`) | benchmark_max_weight | 美股和全球主题 | 1 | 501300 |
| `theme-巴西IBOVESPA指数` | Ibovespa Index (`Ibovespa Index`) | mandated_code | 美股和全球主题 | 2 | 520870 159100 |
| `theme-恒生中国企业指数` | 恒生中国企业指数 (`HSCEI`) | learned_index_name | 美股和全球主题 | 4 | 510900 159850 160717 161831 |
| `theme-恒生中国央企指数` | 恒生中国央企 (`HSCSOE`) | learned_index_name | 美股和全球主题 | 1 | 513170 |
| `theme-恒生互联网科技业指数` | 恒生互联网科技业指数 (`HSIII`) | learned_index_name | 美股和全球主题 | 3 | 513330 159202 159688 |
| `theme-恒生创新药指数` | 恒生创新药指数 (`HSIDI`) | learned_index_name | 美股和全球主题 | 1 | 520500 |
| `theme-恒生医疗保健指数` | 恒生医疗保健指数 (`HSHCI`) | learned_index_name | 美股和全球主题 | 3 | 513060 159303 159557 |
| `theme-恒生消费指数` | 恒生消费指数 (`HSCGSI`) | learned_index_name | 美股和全球主题 | 4 | 513970 520520 520620 159699 |
| `theme-恒生港股通红利低波动指数` | 恒生港股通高股息低波动指数 (`HSHYLV`) | learned_index_name | 美股和全球主题 | 3 | 513950 520550 520890 |
| `theme-恒生生物科技指数` | 恒生生物科技指数 (`HSBIO`) | learned_index_name | 美股和全球主题 | 5 | 513930 520760 520930 159615 159892 |
| `theme-恒生生物科技指数` | 恒生香港上巿生物科技指数 (`HSHKBIO`) | learned_index_name | 美股和全球主题 | 1 | 513280 |
| `theme-恒生综合小型股指数` | 恒生综合小型股指数 (`恒生综合小型股指数`) | benchmark_max_weight | 美股和全球主题 | 1 | 161124 |
| `theme-新交所泛东南亚科技指数` | 新交所泛东南亚科技指数 (`ASIATECN`) | learned_index_name | 美股和全球主题 | 1 | 513730 |
| `theme-标普500信息科技指数` | 标普500信息科技指数 (`标普500信息科技指数`) | benchmark_max_weight | 美股和全球主题 | 1 | 161128 |
| `theme-标普500医疗保健等权重指数` | 标普500医疗保健等权重指数 (`标普500医疗保健等权重指数`) | benchmark_max_weight | 美股和全球主题 | 1 | 161126 |
| `theme-标普500消费精选指数` | SP5CSSUP (`SP5CSSUP`) | index_code | 美股和全球主题 | 1 | 159529 |
| `theme-标普中国新经济行业指数` | SPNCSCHN (`SPNCSCHN`) | index_code | 美股和全球主题 | 1 | 159822 |
| `theme-标普全球石油指数` | S&P Global Oil Index Net Total Return (`S&P Global Oil Index Net Total Return`) | benchmark_max_weight | 美股和全球主题 | 1 | 160416 |
| `theme-标普生物科技精选行业指数` | SPSIBI (`SPSIBI`) | index_code | 美股和全球主题 | 1 | 159502 |
| `theme-标普生物科技精选行业指数` | 标普生物科技精选行业指数 (`标普生物科技精选行业指数`) | benchmark_max_weight | 美股和全球主题 | 1 | 161127 |
| `theme-标普石油天然气勘探及生产精选行业指数` | S&P Oil & Gas Exploration & Production Select Industry Index (`S&P Oil & Gas Exploration & Production Select Industry Index`) | mandated_code | 美股和全球主题 | 3 | 513350 159518 162411 |
| `theme-标普美国品质消费股票指数` | 标普美国品质消费股票指数 (`标普美国品质消费股票指数`) | benchmark_max_weight | 美股和全球主题 | 1 | 162415 |
| `theme-法兰克福DAX指数` | DAX (`DAX`) | index_code | 美股和全球主题 | 1 | 159561 |
| `theme-法兰克福DAX指数` | 德国DAX指数 (`GDAXI`) | learned_index_name | 美股和全球主题 | 1 | 513030 |
| `theme-法国CAC40指数` | CAC40指数 (`FCHI`) | learned_index_name | 美股和全球主题 | 1 | 513080 |
| `theme-纳斯达克生物科技指数` | 纳斯达克生物科技指数 (`NBI`) | learned_index_name | 美股和全球主题 | 1 | 513290 |
| `theme-纳斯达克科技市值加权指数` | NDXTMC (`NDXTMC`) | index_code | 美股和全球主题 | 1 | 159509 |
| `theme-道琼斯工业平均指数` | 道琼斯工业平均指数 (`DJIA`) | learned_index_name | 美股和全球主题 | 1 | 513400 |
| `theme-道琼斯美国石油开发与生产指数` | 道琼斯美国石油开发与生产指数 (`的道琼斯美国石油开发与生产指数`) | benchmark_max_weight | 美股和全球主题 | 1 | 162719 |
| `theme-道琼斯美国精选REIT指数` | 道琼斯美国精选REIT指数 (`道琼斯美国精选REIT指数`) | benchmark_max_weight | 美股和全球主题 | 1 | 160140 |

## 大组摘录（n≥5）

| 容器 id | n | 成员 |
| --- | ---: | --- |
| `hstech` | 14 | 513010 513130 513180 513260 513380 513580 513890 520570 520590 520920 158042 159740 159741 159742 |
| `ndx100` | 13 | 513100 513110 513300 513390 513870 501312 159501 159513 159632 159659 159660 159696 159941 |
| `theme-中证港股通互联网指数` | 8 | 513040 513720 513770 520630 520650 520740 520790 520910 |
| `hsi` | 7 | 513210 513600 513660 159920 160125 160924 164705 |
| `theme-中证港股通信息技术综合指数` | 7 | 513240 520710 520750 526000 526030 526050 526060 |
| `theme-中证港股通科技指数` | 7 | 513020 513150 513560 513860 513980 520530 520860 |
| `theme-HSISC` | 5 | 520770 520820 520940 520960 526070 |
| `theme-恒生生物科技指数` | 5 | 513930 520760 520930 159615 159892 |

## 机器可读源

- CSV: `results/v4/inventory/r1e/grouping.csv`
- 差额动作: `results/v4/inventory/r1e/diff.csv`

