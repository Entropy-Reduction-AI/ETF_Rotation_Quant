# 申万一级行业指数（2021 版）官方日线

下载日期：2026-11-22；打包日期：2026-11-23 Asia/Taipei。本包未做收益计算，未写入 `data/market.sqlite`，不开仓、不合并入库。

本包只包含**已经取到的 2021 版 31 个一级行业股价指数**日线，以及官方新旧分类对照。2014 版 28 个一级行业的官方**指数代码**仍未找到，因此 2014 日线未下载，不在本包内。

请求范围：日线开盘、最高、最低、收盘和成交额，从最早一天到现在；官方载荷里的成交量一并保留。空值原样保留，未补造。官方 JSON 载荷因体积未放入本包，SHA256 记在下表，源文件仍在本机预备目录。

## 来源（官方，无需登录）

- 日线 API：`https://www.swsresearch.com/institute-sw/api/index_publish/trend/?swindexcode={code}&period=DAY`
- 2021 版一级行业指数代码：官方 `GET /institute-sw/api/index_publish/history_home/` 与 `/api/index_publish/details/index_spread/`，并与官方全部行业分类下载中的 31 个一级行业名称对齐
- 新旧分类对照：`https://www.swsresearch.com/swindex/pdf/SwClass2021/2014to2021.xlsx`（《申万行业分类标准2021版修订对照表》）
- 编制说明 5.0：`https://www.swsresearch.com/swindex/pdf/80100350.pdf`
- 2021 分类标准：官方 `SwClass.rar` / `SwClassStd2021.pdf`

## 指数版本与发布日期（能核实的部分）

- 指数版本：申万行业分类标准（2021 版）一级行业；日线标记为**股价系列指数**。已读过的 编制说明 5.0 与 2021 版公告中，未见官方全收益系列。
- 编制说明 5.0 §4.2：申银万国股价系列指数（含行业分类指数）「基期设定在 1999 年 12 月 31 日，基点为 1000 点。」这是系列基期，不是逐指数发布日。官方 `trend` API 中 16 条序列的首日是 **1999-12-30**、开盘/最高/最低/收盘均为 1000.0——与 1999-12-31 基期不一致，如实记录，不以 API 首日改写基期。
- 2021-11-23 官方《2021版申万行业指数切换公告》：「自 **2021年12月13日** 起发布2021版申万行业指数。」这是 2021 版的**家族口径发布用语**，公告未给出逐指数发布日表。本包**不把**家族口径日期或 API 首日当作逐指数发布日。
- 2014-01-20 官方公告：2014 版《申银万国行业指数》「将于 **2014年2月21日** 正式实施。」同样是家族口径，未列出 28 个指数代码。

## 指数名单与日线条数、起止日期、SHA256

字段来自官方 API：`swindexcode,bargaindate,openindex,maxindex,minindex,closeindex,bargainamount,bargainsum`（成交量 `bargainamount`、成交额 `bargainsum`）。

| 代码 | 名称 | 系列 | 条数 | 起止日期 | CSV SHA256 | 官方 JSON SHA256 |
|---|---|---|---:|---|---|---|
| 801010 | 农林牧渔 | 股价 | 6496 | 1999-12-30–2026-11-20 | `f5dd2dcca682094006ef354e0f34a83a3a111bbb5f2d188e8ccf8ab6a9ea32bc` | `eb2e42cb9e52026ee38139d6a0b7577a180d846ece5a76a994160a3e480e2e7c` |
| 801030 | 基础化工 | 股价 | 6496 | 1999-12-30–2026-11-20 | `007c5e358654e324f503630e812fa857790b5d4b713ac3c5f8f7d319e6a8c96a` | `c4fbe70c24c05533f49ed1c64860478b2c8c414f6edc44f51e2a252645d2affe` |
| 801040 | 钢铁 | 股价 | 6496 | 1999-12-30–2026-11-20 | `fa1899f97d89b2d94fb3ff2ba2f3d672532b3a6379dad0e2c1d5f36d886c7415` | `d59894dd6e67b2577328cc181fd58bbc10f5545b0140bd54106c98af2c115162` |
| 801050 | 有色金属 | 股价 | 6496 | 1999-12-30–2026-11-20 | `4dff132b77c8710cbcb1d3f15039f0dafc21fab2e6d7c22eb270cf84bd5ff74a` | `1b08befe2ea8305cc10d9a4385d4afabf6c175f833b0baef634e6ca17ce8e7b1` |
| 801080 | 电子 | 股价 | 6496 | 1999-12-30–2026-11-20 | `226a13354c6185b9f874c0d86fec4691f83f06ae9ac643bad3b1b1c3a26b55a8` | `db7a2c45a06fd0fd724e23496860e652897518157f98636f25328a30e77d0d75` |
| 801110 | 家用电器 | 股价 | 6496 | 1999-12-30–2026-11-20 | `c0d05934428adef182322d73b342d2541a7f88c1ed77bae58090896738c4ed82` | `badc9b2aa646fff67650e93075cae69362227980d16979f79b2e9cb4bdb02c24` |
| 801120 | 食品饮料 | 股价 | 6496 | 1999-12-30–2026-11-20 | `3999a3811915d7c217af586209b1d217182a174670c1c0e1e4d55d85ae268dcc` | `ad96e2dfaad0c97f6c1331612bf38a18423dec0f478db3e8b04679367e7c6b50` |
| 801130 | 纺织服饰 | 股价 | 6496 | 1999-12-30–2026-11-20 | `b6b095ec0ebb24c4bf153140d9a4e7010064edc283326c93919cb10553da7d79` | `ede4f9cded27a1648592d83f4e3431c26117911e40f58c500eafca886e1f646d` |
| 801140 | 轻工制造 | 股价 | 6496 | 1999-12-30–2026-11-20 | `3daf3f7e5679604c2a65c14745e15c0bab0779c80134b5a3f5b99d08aa21e593` | `2fb3a599cc423a866412547c96d00a9b3f278567605bafe2b0f075237697eb41` |
| 801150 | 医药生物 | 股价 | 6496 | 1999-12-30–2026-11-20 | `dd8fc2f6246d97f61d65bd75b52a5bc281d435bcd2a0d96c0c72586551eb979e` | `175e0e61394cb086121cc02fcbd039a5da9c0d3590f310963c0a9c89c86e1fc8` |
| 801160 | 公用事业 | 股价 | 6496 | 1999-12-30–2026-11-20 | `8d70d22b9292338ff228aae2523294df92e50e7280241fedf250f980354338ea` | `ae399b64ffd7a97ae7770673d7a5bf3d50620ee0c443ff64786d626ffe378406` |
| 801170 | 交通运输 | 股价 | 6496 | 1999-12-30–2026-11-20 | `624a502202e8b9c4c50cdd3c6c021db09c272600767373689ed90e2544417941` | `02722f0e5ca6421b553a541bb30d916c149a336e6216d8603c12a8823f1640fe` |
| 801180 | 房地产 | 股价 | 6496 | 1999-12-30–2026-11-20 | `e69ce7efd2bba90f15c29c337098d8a2e0f781dc44047c025b4866ebe555a660` | `e2c14cba32f7f9fab12fec801096f983f9a02bcde7abe30e783729dc190cf919` |
| 801200 | 商贸零售 | 股价 | 6496 | 1999-12-30–2026-11-20 | `431d6e7537dcd26eefb866e89fd76ef6f303c2debecf5222140389e5b4378cd5` | `b804360b269e77339e0efcfb5e34208126de3579af2e1224022f8bc5d5b82e04` |
| 801210 | 社会服务 | 股价 | 6496 | 1999-12-30–2026-11-20 | `29358f113b97a6f5306f8506a928c29319de428d216b14de7242128d83504ebd` | `72b844b9b7637bb6f5afaedc807d156867f93cd27a2ebb4404395f23c594ddff` |
| 801230 | 综合 | 股价 | 6496 | 1999-12-30–2026-11-20 | `595a9d846881c089ff0cefb8e91bd7b9cf53c5b0ef0cbe5195f11a19f905bd88` | `8031c7f4549cc71ba3fc4c48580d3671344c3fcccfc7ef848812ad1e5b77ff78` |
| 801710 | 建筑材料 | 股价 | 3082 | 2014-02-21–2026-11-20 | `9c7a7bc98c102202d9c4a1e38e5651b9c0ef971f55c0a679d127d459f96d10d5` | `ebcb3b3a8e46042ed19422e2082afb3aacf85b61c6447c74e0f96a6cddd2f994` |
| 801720 | 建筑装饰 | 股价 | 3082 | 2014-02-21–2026-11-20 | `b9e7f7f37c14cc5d9b41740adb44fa5ecee4a875eb0653fbf6717a1eb3db53e9` | `7ad6b934616b5a9319680397a45976fb848e96a20a5209a61df79e9d6dabcb4c` |
| 801730 | 电力设备 | 股价 | 3082 | 2014-02-21–2026-11-20 | `70575a191a9a45efdf97b746a67d0c275f494ef09395efb4f5a6b44e0f635439` | `b757c59e369cbb3dd2faad9cd33ecbc6daab29a946b52273a364421c0e6ca94b` |
| 801740 | 国防军工 | 股价 | 3082 | 2014-02-21–2026-11-20 | `b572570147796131435f754d586d12a24779413fe846ac22d5054f7b70e36c82` | `00af78a4068c106b4b0ad5331508118d6484410d39b70828b5af2a0dd1221c18` |
| 801750 | 计算机 | 股价 | 3082 | 2014-02-21–2026-11-20 | `77a5efeef93e5803cb4a7e7661fa8aa27ab11316b3d782d3a6f53b8e73554e9e` | `4f7c34aad3c87743611ae6ce361a4aee527b4ef44c2bffb5add27a63681ce677` |
| 801760 | 传媒 | 股价 | 3082 | 2014-02-21–2026-11-20 | `4e2ef0c784484ad7ec0a4ec7ced9e945e6333f597d0ab2edc12d00782759f03b` | `a09ae45dc54e09a1883133656af749dead186406f38256dfb012132bb36a6c15` |
| 801770 | 通信 | 股价 | 3082 | 2014-02-21–2026-11-20 | `47d390e0f13c00b5728e9816c56c2c122b4956f29cb1e24aab1d5c78405c49f9` | `c283e11d7054e833df5e6d2be8d5558fa177995b37b2bde2571120b0d0cdf32f` |
| 801780 | 银行 | 股价 | 3082 | 2014-02-21–2026-11-20 | `69113ebc1002f4b1d3e2bc33150429423369545e2e8009e49f5c3d3ab07c4840` | `1ff28f53e9742ca5b6396b06b781ce5f121121d1c20f102846a16d04f889370e` |
| 801790 | 非银金融 | 股价 | 3082 | 2014-02-21–2026-11-20 | `8d8905cfda20e0f5a659d7445cf8795a04382539b724ed833fbbbff10c0290b5` | `5bdae6c75be00d91c542f2f3ee7d2d06da149e7a40cc13a09928e93757323e1a` |
| 801880 | 汽车 | 股价 | 3082 | 2014-02-21–2026-11-20 | `10c357aabfcd51c1febc784b05dc295c8c3cdd39fa54cbf492468b3ac3b4ad9c` | `30e2728002e5832f4e3cd8999ed2ce6f587965f6b77452b3c27b9b68d29fdfbd` |
| 801890 | 机械设备 | 股价 | 3082 | 2014-02-21–2026-11-20 | `10431c03bd00c99ed79eb56b5dc78e4fb50d28594a6538835da94b023062cf11` | `2a23ca67936b579e816d382bb98abccb2ad627c92746276f72e15e8ce3a19623` |
| 801950 | 煤炭 | 股价 | 3089 | 2014-02-21–2026-11-20 | `7ad78ab009d2b7f1a911a53ab3e91dc86c21b30609d3a2166d9248212e8849e8` | `18c2501255ec1bf83b3a137b9d52184c3b64b911b5df9d37440a098ab6785f2f` |
| 801960 | 石油石化 | 股价 | 1188 | 2021-12-13–2026-11-20 | `4c0221e0ff9200418196980ecd5850c17d8ed008cf18299d33b8670c9c5369bf` | `151dca0d8ae73765c26a1b139387c98c450ec70a930ec4911be34eaa5a204450` |
| 801970 | 环保 | 股价 | 1188 | 2021-12-13–2026-11-20 | `c86ce45b3a68c219aa1d976778196d4a2a993365eb8d6de88b88aef5c52babae` | `8289481b5ef4229a83fb96fa895468e88871aae14f760a9a1085583ce02fdf4c` |
| 801980 | 美容护理 | 股价 | 1188 | 2021-12-13–2026-11-20 | `01c3ebf870d4bd49dac8bd2c83dd7a5c6a4d208cc594ce6c1841d390933b5d3e` | `ba5018ba960b1baac4ea326d1b96ce466f63bf492809022d5c5ec06356ac55cd` |

API 首日分组（**不是**发布日）：16 条自 1999-12-30（各 6496 条）；12 条自 2014-02-21（其中 11 条 3082 条，801950 煤炭 3089 条）；3 条自 2021-12-13（801960 石油石化、801970 环保、801980 美容护理，各 1188 条）。全部 31 条最后一天都是 **2026-11-20**。

801950 煤炭比同日起步的其他 11 条多 7 个交易日：官方载荷中多出 2016-04-18、2016-04-19、2016-07-04、2017-04-05、2017-07-21、2021-08-06、2021-10-08、2021-10-22，并缺少 2015-11-27。日期无重复。本包按官方载荷原样保留，未删未补。

## 新旧分类对照

官方工作簿 `correspondence/2014to2021.xlsx`。表中的 2014 列为官方**行业代码**（例如 210000），**不是** `trend/` 所用的 2014 指数代码（801xxx）。2014 指数代码仍缺失，对照表没有编造映射。

## 尚未取到（不在本包）

- 2014 版 28 个一级行业官方**指数代码**，以及相应官方日线。尚待线索：`http://www.swsindex.com/pdf/SwIdxCls.xlsx`（2021-11-23 公告所链，显示名「申万行业指数分类标准2021版说明.xlsx」）。本机最近一次取用返回 **HTTP 500 / TLS EOF**，不是登录墙；www.swsresearch.com 镜像 404；未见 Wayback HTTP 200 快照。
- 逐指数发布日表。本包只记录上面的家族口径日期。
- 申万行业指数全收益系列：已读官方文档中未见。

## 本包文件 SHA256

| 路径 | 字节 | SHA256 |
|---|---:|---|
| `correspondence/2014to2021-新旧对比版本1.csv` | 32367 | `495ac6f1f9982a7da4ddb54392906e4cdb2e541afe090340d8d63be66db6f40e` |
| `correspondence/2014to2021-新旧对比版本2.csv` | 26655 | `8bf34e357e8fda96ff5df58631411e65205c108835eedf564b9bd42c425880a2` |
| `correspondence/2014to2021.xlsx` | 71185 | `45f1d3e1cf324bd150ba4beaa22157c6893dbd797d096abf2c56e59e1f29de6e` |
| `dailies/801010-农林牧渔.trend.csv` | 566083 | `f5dd2dcca682094006ef354e0f34a83a3a111bbb5f2d188e8ccf8ab6a9ea32bc` |
| `dailies/801030-基础化工.trend.csv` | 573620 | `007c5e358654e324f503630e812fa857790b5d4b713ac3c5f8f7d319e6a8c96a` |
| `dailies/801040-钢铁.trend.csv` | 570470 | `fa1899f97d89b2d94fb3ff2ba2f3d672532b3a6379dad0e2c1d5f36d886c7415` |
| `dailies/801050-有色金属.trend.csv` | 572814 | `4dff132b77c8710cbcb1d3f15039f0dafc21fab2e6d7c22eb270cf84bd5ff74a` |
| `dailies/801080-电子.trend.csv` | 569420 | `226a13354c6185b9f874c0d86fec4691f83f06ae9ac643bad3b1b1c3a26b55a8` |
| `dailies/801110-家用电器.trend.csv` | 564937 | `c0d05934428adef182322d73b342d2541a7f88c1ed77bae58090896738c4ed82` |
| `dailies/801120-食品饮料.trend.csv` | 579545 | `3999a3811915d7c217af586209b1d217182a174670c1c0e1e4d55d85ae268dcc` |
| `dailies/801130-纺织服饰.trend.csv` | 565009 | `b6b095ec0ebb24c4bf153140d9a4e7010064edc283326c93919cb10553da7d79` |
| `dailies/801140-轻工制造.trend.csv` | 566052 | `3daf3f7e5679604c2a65c14745e15c0bab0779c80134b5a3f5b99d08aa21e593` |
| `dailies/801150-医药生物.trend.csv` | 574555 | `dd8fc2f6246d97f61d65bd75b52a5bc281d435bcd2a0d96c0c72586551eb979e` |
| `dailies/801160-公用事业.trend.csv` | 570009 | `8d70d22b9292338ff228aae2523294df92e50e7280241fedf250f980354338ea` |
| `dailies/801170-交通运输.trend.csv` | 572639 | `624a502202e8b9c4c50cdd3c6c021db09c272600767373689ed90e2544417941` |
| `dailies/801180-房地产.trend.csv` | 572761 | `e69ce7efd2bba90f15c29c337098d8a2e0f781dc44047c025b4866ebe555a660` |
| `dailies/801200-商贸零售.trend.csv` | 568619 | `431d6e7537dcd26eefb866e89fd76ef6f303c2debecf5222140389e5b4378cd5` |
| `dailies/801210-社会服务.trend.csv` | 569165 | `29358f113b97a6f5306f8506a928c29319de428d216b14de7242128d83504ebd` |
| `dailies/801230-综合.trend.csv` | 561957 | `595a9d846881c089ff0cefb8e91bd7b9cf53c5b0ef0cbe5195f11a19f905bd88` |
| `dailies/801710-建筑材料.trend.csv` | 270790 | `9c7a7bc98c102202d9c4a1e38e5651b9c0ef971f55c0a679d127d459f96d10d5` |
| `dailies/801720-建筑装饰.trend.csv` | 272004 | `b9e7f7f37c14cc5d9b41740adb44fa5ecee4a875eb0653fbf6717a1eb3db53e9` |
| `dailies/801730-电力设备.trend.csv` | 276655 | `70575a191a9a45efdf97b746a67d0c275f494ef09395efb4f5a6b44e0f635439` |
| `dailies/801740-国防军工.trend.csv` | 269754 | `b572570147796131435f754d586d12a24779413fe846ac22d5054f7b70e36c82` |
| `dailies/801750-计算机.trend.csv` | 274517 | `77a5efeef93e5803cb4a7e7661fa8aa27ab11316b3d782d3a6f53b8e73554e9e` |
| `dailies/801760-传媒.trend.csv` | 261819 | `4e2ef0c784484ad7ec0a4ec7ced9e945e6333f597d0ab2edc12d00782759f03b` |
| `dailies/801770-通信.trend.csv` | 272406 | `47d390e0f13c00b5728e9816c56c2c122b4956f29cb1e24aab1d5c78405c49f9` |
| `dailies/801780-银行.trend.csv` | 272224 | `69113ebc1002f4b1d3e2bc33150429423369545e2e8009e49f5c3d3ab07c4840` |
| `dailies/801790-非银金融.trend.csv` | 272134 | `8d8905cfda20e0f5a659d7445cf8795a04382539b724ed833fbbbff10c0290b5` |
| `dailies/801880-汽车.trend.csv` | 273214 | `10c357aabfcd51c1febc784b05dc295c8c3cdd39fa54cbf492468b3ac3b4ad9c` |
| `dailies/801890-机械设备.trend.csv` | 272043 | `10431c03bd00c99ed79eb56b5dc78e4fb50d28594a6538835da94b023062cf11` |
| `dailies/801950-煤炭.trend.csv` | 268897 | `7ad78ab009d2b7f1a911a53ab3e91dc86c21b30609d3a2166d9248212e8849e8` |
| `dailies/801960-石油石化.trend.csv` | 102526 | `4c0221e0ff9200418196980ecd5850c17d8ed008cf18299d33b8670c9c5369bf` |
| `dailies/801970-环保.trend.csv` | 102148 | `c86ce45b3a68c219aa1d976778196d4a2a993365eb8d6de88b88aef5c52babae` |
| `dailies/801980-美容护理.trend.csv` | 101507 | `01c3ebf870d4bd49dac8bd2c83dd7a5c6a4d208cc594ce6c1841d390933b5d3e` |
| `metadata/801010-农林牧渔.trend.meta.json` | 967 | `650e54d423eb172b2180908d004907bcfeea94a18b4d6026a0065515509c69b0` |
| `metadata/801030-基础化工.trend.meta.json` | 968 | `4bceadd96be54bb9439c4021c3459c204dbe662e2996bd9cf7dc65caf921e16e` |
| `metadata/801040-钢铁.trend.meta.json` | 951 | `c409a75043b338c392dcdd7893c71b634ec7d1bc6964f155311bfa0c738d5ef5` |
| `metadata/801050-有色金属.trend.meta.json` | 969 | `f7ce890f558a75ccab962bf3ea4d53231ae5d8d43ce01bedbd1e1ffd1e85bf73` |
| `metadata/801080-电子.trend.meta.json` | 957 | `49d207290846adaf120149f7ae3aae7e23b57459da44755c20b7e0e99d1cad94` |
| `metadata/801110-家用电器.trend.meta.json` | 974 | `6efa9c18d2b7319a336ae6c7cd9995ae7862fde79f7445d11bafdf080a22dd8b` |
| `metadata/801120-食品饮料.trend.meta.json` | 968 | `4da925fd87da3ba4a5a7e59087da542b5bd7dc9fe54355295f17816091874258` |
| `metadata/801130-纺织服饰.trend.meta.json` | 968 | `2f87480a16765c5674a4b6f7e7a89e36547c1da5594e2988b98c6b32ef22d09b` |
| `metadata/801140-轻工制造.trend.meta.json` | 974 | `ed998ac072365199e413587e99dac575a3916a834a0f732bf91e01eb0988f4a2` |
| `metadata/801150-医药生物.trend.meta.json` | 968 | `5c2b047a0218196ff4f2553100e4d793ee1042293873fa322d6d405427cb51dc` |
| `metadata/801160-公用事业.trend.meta.json` | 966 | `e8a0ad6721b44d91468388b200f832eef990963a1b422a988748411a80f75397` |
| `metadata/801170-交通运输.trend.meta.json` | 969 | `a5b1c15472904eb90f2c8091008fa6bc51c81368a4cd032a4ec7e9f85f69763e` |
| `metadata/801180-房地产.trend.meta.json` | 959 | `c5471e3226155bf9a1caf52ea8e4243efde8a186576b14e5569cde855dc14051` |
| `metadata/801200-商贸零售.trend.meta.json` | 967 | `d32a67b7c21abfe8861d01849f40b3880fa0b9093d59d5233dae79a8e13253ef` |
| `metadata/801210-社会服务.trend.meta.json` | 968 | `b39ae5e49404dda44bae881cd62e24549717cd71f13165f763dbd378729f1554` |
| `metadata/801230-综合.trend.meta.json` | 950 | `fd9350f1b08b07905fca68e43bbde5c1afdda63c7c18f39521149a4e224fc512` |
| `metadata/801710-建筑材料.trend.meta.json` | 977 | `04303ff372f735dbb7dbcb73f8bb9a7057dedcb49b7fadc9e4c0487131e8da22` |
| `metadata/801720-建筑装饰.trend.meta.json` | 975 | `e01a95d16c581e185b1f97065acbd0d10f86fc47450ff25797cabd275c4ba01d` |
| `metadata/801730-电力设备.trend.meta.json` | 976 | `2f9da5a8f39f08b9fc9b832d6f26c30f7d9a694567e6c7b2258ff42500f377d4` |
| `metadata/801740-国防军工.trend.meta.json` | 973 | `611527248beddbd2c6d09b9621d6bbcb939f9deba03cae7a9bef2d11dc7c611c` |
| `metadata/801750-计算机.trend.meta.json` | 966 | `21aa80dee129a6c3539444d2c068769849a2bc8958dac3bbe295931aaa736297` |
| `metadata/801760-传媒.trend.meta.json` | 956 | `c2016e0cbcede1af531a0a4856d84d772105f16327bfa04fb4895f0dc2ef89e6` |
| `metadata/801770-通信.trend.meta.json` | 956 | `29a8ee0905272354835b5759ec44c0337dc2d2e9196b7ffe6144c67732986a01` |
| `metadata/801780-银行.trend.meta.json` | 959 | `235ce2ceab7f59351288e081c487209c98ec82d3f45622566c28605c85121574` |
| `metadata/801790-非银金融.trend.meta.json` | 973 | `bf7c715e60fdcb19aa9776bcdc38d278368811d2b6c17a68cc71e590d1160dd2` |
| `metadata/801880-汽车.trend.meta.json` | 956 | `ba1d845904465be74eb8d93d8c7461eab13c1522c1f544ca0ef7b30b2368d4c8` |
| `metadata/801890-机械设备.trend.meta.json` | 975 | `d1229785df7925cf4ecc2aeefa3a568cc783dd67e544971a79ada7ff8f4ec512` |
| `metadata/801950-煤炭.trend.meta.json` | 950 | `9e10be8765d1a46f966e0250449fd6d4b79a6d1454b7741bc37428cb6b202d8b` |
| `metadata/801960-石油石化.trend.meta.json` | 974 | `c7d49a3c96f41f71e0f77825a692f6754889fb3bc9487931709677681af04ce6` |
| `metadata/801970-环保.trend.meta.json` | 957 | `7e09be8d7b7bb1242279e240e1b10122294a80b3a84e0222ed6424bc0ddfca1f` |
| `metadata/801980-美容护理.trend.meta.json` | 972 | `351d66c8049fc996211de3dc8f82790faab30efb8be6257c6b8585e0a3bfbb9b` |
| `metadata/dailies-summary.csv` | 9190 | `d86389f6251d49e461102545c233fdb72f2788147bf9286dd7c2ba443e882453` |
| `metadata/sws-2014-l1-official-classification-codes.csv` | 8937 | `aa313df09ffbc2e299c0b29ed2683d5db1d2eaa1823489318bc5c3cfc31bcd29` |
| `metadata/sws-2014-to-2021-l1-correspondence.csv` | 13088 | `ac2ce21935a155c3327feee6dfb2434bae95ece96b4c7bad19352753069d892a` |
| `metadata/sws-2021-l1-dailies-summary.csv` | 6865 | `c2fddba59eacb7fec6bd64111f3390471440d0528cb77f9b95bed3697fc06cce` |
| `metadata/sws-2021-l1-industry-names-from-all_trade_classification.txt` | 562 | `4b18a76da1cab4551c5657a9aae5349d54e886c40051820edd16cea2f88c04c7` |
| `metadata/sws-2021-l1-official-codes.csv` | 12050 | `e18cd5825caa706b5837dd1df58e3f1f2077499b343ef8246e5add4878b3caab` |
| `official-docs/80100350.pdf` | 818385 | `f3ed31c6eb0ed61bbbaa0de2057723d5a11b3da399a9df448c0ba6cc7ac61eea` |
| `official-docs/80100350.txt` | 87844 | `b2e522b3352d3277335a74812fa499f8c4d687c14424f7746e30dfad344c4d5a` |
| `official-docs/SwClass.rar` | 1509530 | `7cf486a6e6de70b2d014f5b17c4dff8afeb0eebb6731dcbacb3de8b2700b70a7` |
| `official-docs/SwClassCode_2021.xls` | 73728 | `923492f4bcf3c7056904385a0769e4dda561904a29ecd9243f942680cef68c81` |
| `official-docs/SwClassStd2021.pdf` | 1368337 | `18fb07fafda072dad39e274371660706e21678045ae8204931958db9906faa1a` |
| `official-docs/announcements/2007-06-25-DE3C8ED6.html` | 4232 | `3605e64e52610fb88daa0d51bfc487cf924ad6c4dd4e680dcdf1094746caa75b` |
| `official-docs/announcements/2007-06-25-DE3C8ED6.txt` | 2435 | `e2359387167daad2a9aa0a7d16792589c9f4c065e17f5205d80c4826619add01` |
| `official-docs/announcements/2008-05-23-C0F4B3F9.html` | 2931 | `cfa38e54468e0bae1ef43800e0db45849b32e3d3e80bb99cd904ae7883c4a2e0` |
| `official-docs/announcements/2008-05-23-C0F4B3F9.txt` | 1731 | `42209aab3792524ee6472f6346e03c5e1c5d90b184666ccd970171caff4a63d6` |
| `official-docs/announcements/2013-12-09-1DFCF28E.html` | 1523 | `6d3da358a905eda411de5f87fd1b1359ef06646f81bd87a9b5cdb2465e793bf0` |
| `official-docs/announcements/2013-12-09-1DFCF28E.txt` | 1477 | `b013f798fefdf31a44c937fe3509e90e3966977bc3f292332d2f232a518dd322` |
| `official-docs/announcements/2013-12-09-F23A10EC.html` | 1523 | `6d3da358a905eda411de5f87fd1b1359ef06646f81bd87a9b5cdb2465e793bf0` |
| `official-docs/announcements/2013-12-09-F23A10EC.txt` | 1477 | `b013f798fefdf31a44c937fe3509e90e3966977bc3f292332d2f232a518dd322` |
| `official-docs/announcements/2014-01-20-4CF22EFD.html` | 1557 | `f63980bd49956a72eea663a7a662ccb57e9012f70b5290a497713f380d07972c` |
| `official-docs/announcements/2014-01-20-4CF22EFD.txt` | 555 | `a85ec078d23d21876f79b25db2d7d2056954b43a7d08231f17ecdefaacf0981c` |
| `official-docs/announcements/2021-07-31-19CBFEC8.html` | 4460 | `b047625aaed212230954f2a000a781d77409d71ec14a48f3493042cf77070d1d` |
| `official-docs/announcements/2021-07-31-19CBFEC8.txt` | 745 | `a32a57bd32c5ed0cd55015d00915ef82b5de216cd23fc30dab213ebe08ab7aec` |
| `official-docs/announcements/2021-11-23-43CE85B9.html` | 1377 | `55fbc92156bb5d1b55cb98df67cd87671c368e306afbc8be114bcb5b18888b1a` |
| `official-docs/announcements/2021-11-23-43CE85B9.txt` | 315 | `588a47a6ff9d1de7d2cddb7910280d6d7859749b97a1b446baef90447b1482e8` |
| `official-docs/announcements/2021-11-23-8C619116.html` | 896 | `79cc840072086910838e7aab2adfeebe1ca40b62d9ed189f314e737ada3dc9dd` |
| `official-docs/announcements/2021-11-23-8C619116.txt` | 315 | `588a47a6ff9d1de7d2cddb7910280d6d7859749b97a1b446baef90447b1482e8` |
| `official-docs/swindex4.pdf` | 208952 | `d173d4a202386946b832632be72eecbcf758eb661a8b00e88bdb69d4267d6381` |
| `official-docs/swindex401.pdf` | 417215 | `2a4da6d333122eb0ddf8b73d8311176884cee86ceff1fae95b15fc63de8cf7b9` |
| `official-docs/sws.pdf` | 56314 | `ba6849a32f121f6a4c7f9e1a6560572d0acc005c90653139a58178e738c2d8e5` |
| `official-docs/申万系列指数之发布分析指标_201012.pdf` | 152531 | `6a25393e2e55e2511e5d9029f76cb903917f988ddaeb0ad2090d39c241cdf326` |

本包文件共 96 个（不含本 MANIFEST），合计 17611515 字节。打开本包的 PR 只放进 `incoming/grok-sw-l1-20261123/`，不写入 `data/market.sqlite`，不算收益，不合并。
