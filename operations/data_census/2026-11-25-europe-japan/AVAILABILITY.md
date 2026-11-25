# 成交量与 eb.rexx 德国国债的可得性

## Metadata

- Project: ETF_Rotation_Quant
- Document type: evidence
- Status: partial, not a market selection
- Date: 2026-11-25
- Time zone: Asia/Taipei

两件事放在一起。TradingView 成交量只记录别人交来的前端核验，这一步没有再打开 TradingView。eb.rexx 来自 iShares 公开页。不写价格、成交量数值、净值数字或分红金额。

## 结论

TradingView 的 20 个公开 Xetra symbol 页都在，代码对得上。日频成交量历史没有取得。导出要不要登录或付费，未核实。不能把这写成「20 只没有数据」或「已被付费挡住」。

eb.rexx 德国国债在德国个人投资者筛选器里有 6 只分红份额。页面没有有效久期或修正久期的数字，所以不能按久期指出最接近 10 年的那一只。期限桶不是久期。EXHA 的 1.5–10.5 年桶和 EXHD 的 5.5–10.5 年桶都包含 10 年。

## TradingView 每日成交量

来源是交来的前端核验，不是这次重新抓取。20 个公开 symbol 页都逐只打开过，标题含对应的 `XETR:` 代码。这只说明页面在，不说明有每日成交量历史。

只对 `XETR:EXSA` 打开了图。界面可以选 `1D`。日频选项不等于历史成交量已经导出。没有取得任何成交量日线，所以没有首尾日期，也没有行数。没有交易所日历，缺口不可核实。

浏览器已经提示有登录态。为了不使用那个账号，没有打开导出或付费流程，也没有下载。因此统一导出是否要求登录或付费，未核实。没有观察到统一的登录门或付费门，也不能把这一限制从 EXSA 外推成另外 19 只的导出门禁。

| 代码 | 公开页 | 每日成交量历史 | 日期首尾 | 行数 | 缺口 |
| --- | --- | --- | --- | --- | --- |
| EXSA | https://www.tradingview.com/symbols/XETR-EXSA/ | 未取得。图上有 1D。导出门禁未核实 | 未取得 | 未取得 | 不可核实 |
| EXV5 | https://www.tradingview.com/symbols/XETR-EXV5/ | 未取得。未打开该只的导出 | 未取得 | 未取得 | 不可核实 |
| EXV1 | https://www.tradingview.com/symbols/XETR-EXV1/ | 未取得。未打开该只的导出 | 未取得 | 未取得 | 不可核实 |
| EXV6 | https://www.tradingview.com/symbols/XETR-EXV6/ | 未取得。未打开该只的导出 | 未取得 | 未取得 | 不可核实 |
| EXV7 | https://www.tradingview.com/symbols/XETR-EXV7/ | 未取得。未打开该只的导出 | 未取得 | 未取得 | 不可核实 |
| EXV8 | https://www.tradingview.com/symbols/XETR-EXV8/ | 未取得。未打开该只的导出 | 未取得 | 未取得 | 不可核实 |
| EXH2 | https://www.tradingview.com/symbols/XETR-EXH2/ | 未取得。未打开该只的导出 | 未取得 | 未取得 | 不可核实 |
| EXH4 | https://www.tradingview.com/symbols/XETR-EXH4/ | 未取得。未打开该只的导出 | 未取得 | 未取得 | 不可核实 |
| EXV4 | https://www.tradingview.com/symbols/XETR-EXV4/ | 未取得。未打开该只的导出 | 未取得 | 未取得 | 不可核实 |
| EXH5 | https://www.tradingview.com/symbols/XETR-EXH5/ | 未取得。未打开该只的导出 | 未取得 | 未取得 | 不可核实 |
| EXH6 | https://www.tradingview.com/symbols/XETR-EXH6/ | 未取得。未打开该只的导出 | 未取得 | 未取得 | 不可核实 |
| EXI5 | https://www.tradingview.com/symbols/XETR-EXI5/ | 未取得。未打开该只的导出 | 未取得 | 未取得 | 不可核实 |
| EXH8 | https://www.tradingview.com/symbols/XETR-EXH8/ | 未取得。未打开该只的导出 | 未取得 | 未取得 | 不可核实 |
| EXV3 | https://www.tradingview.com/symbols/XETR-EXV3/ | 未取得。未打开该只的导出 | 未取得 | 未取得 | 不可核实 |
| EXV2 | https://www.tradingview.com/symbols/XETR-EXV2/ | 未取得。未打开该只的导出 | 未取得 | 未取得 | 不可核实 |
| EXV9 | https://www.tradingview.com/symbols/XETR-EXV9/ | 未取得。未打开该只的导出 | 未取得 | 未取得 | 不可核实 |
| EXH9 | https://www.tradingview.com/symbols/XETR-EXH9/ | 未取得。未打开该只的导出 | 未取得 | 未取得 | 不可核实 |
| EXH1 | https://www.tradingview.com/symbols/XETR-EXH1/ | 未取得。未打开该只的导出 | 未取得 | 未取得 | 不可核实 |
| EXH3 | https://www.tradingview.com/symbols/XETR-EXH3/ | 未取得。未打开该只的导出 | 未取得 | 未取得 | 不可核实 |
| EXH7 | https://www.tradingview.com/symbols/XETR-EXH7/ | 未取得。未打开该只的导出 | 未取得 | 未取得 | 不可核实 |

## eb.rexx Government Germany

名单来自德国个人投资者产品筛选器，2026-11-25 15:52（Asia/Taipei）匿名读取。筛选器页面是 https://www.ishares.com/de/privatanleger/de/produkte/produktliste 。名称含 eb.rexx 的只有下面 6 只，份额类型都是分红（ausschüttend）。其他份额没有出现在这次筛选结果里，不能据此说全世界没有别的份额。

产品页在同一时刻匿名打开。`navData` 的首尾和条数来自页面里的日期数组。有效久期、修正久期只有名词解释，没有数字。因此不能按久期选出最接近 10 年的基金。

名称和指数说明里的年份是剩余期限桶，不是久期。页面上另有一个标成 Restlaufzeit 的当日加权平均剩余期限。那也不是有效久期，本文不抄那个数字。

EXHA 的指数规则是剩余期限 1.5–10.5 年，这个桶包含 10 年。EXHD 的桶是 5.5–10.5 年，也包含 10 年。不能说只有 EXHD 包含 10 年。EXX6 的规则是剩余期限至少 10.5 年。

EXHD 的产品页把成立日和 `navData` 起点都写成 2003-06-11。同一只在筛选器里的成立日字段是 2005-09-28。两处原样保留，不猜哪个对、为什么不同。下表的净值起点用产品页的 `navData`。

| 代码 | ISIN | 剩余期限桶（指数规则，不是久期） | navData 首尾（条数） | 产品页 |
| --- | --- | --- | --- | --- |
| EXVM | DE000A0Q4RZ9 | 1 个月至 1 年 | 2008-07-29 / 2026-11-24（4645） | https://www.ishares.com/de/privatanleger/de/produkte/251779/ishares-ebrexx-government-germany-0-1yr-ucits-etf-de-fund |
| EXHB | DE0006289473 | 1.5–2.5 年 | 2003-06-11 / 2026-11-24（5952） | https://www.ishares.com/de/privatanleger/de/produkte/251774/ishares-ebrexx-government-germany-1525yr-ucits-etf-de-fund |
| EXHC | DE0006289481 | 2.5–5.5 年 | 2003-06-11 / 2026-11-24（5952） | https://www.ishares.com/de/privatanleger/de/produkte/251776/ishares-ebrexx-government-germany-2555yr-ucits-etf-de-fund |
| EXHA | DE0006289465 | 1.5–10.5 年，且只取最大、最流动的 25 只 | 2003-02-04 / 2026-11-24（6040） | https://www.ishares.com/de/privatanleger/de/produkte/251773/ishares-ebrexx-government-germany-ucits-etf-de-fund |
| EXHD | DE0006289499 | 5.5–10.5 年 | 2003-06-11 / 2026-11-24（5952） | https://www.ishares.com/de/privatanleger/de/produkte/251777/ishares-ebrexx-government-germany-55105yr-ucits-etf-de-fund |
| EXX6 | DE000A0D8Q31 | 至少 10.5 年 | 2005-09-28 / 2026-11-24（5364） | https://www.ishares.com/de/privatanleger/de/produkte/251775/ishares-ebrexx-government-germany-105yr-ucits-etf-de-fund |

## 还没核实的部分

- 20 只的 TradingView 成交量日线都没有取得。日期、行数、缺口都未核实。导出是否要登录或付费也未核实。
- eb.rexx 的有效久期和修正久期没有数字，最接近 10 年的基金无法按久期指定。
- EXHD 的成立日在筛选器和产品页上不一致，原因未核实。
