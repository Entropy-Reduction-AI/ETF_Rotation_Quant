# 未取得的数据

## 中证全指的中证一级行业权重

这一项跳过。下面的地址没有返回中证一级行业权重。成份股权重文件不是行业权重，没有拿来凑数。

| URL | 状态码 | 时间（Asia/Shanghai） | 说明 |
| --- | --- | --- | --- |
| `https://www.csindex.com.cn/csindex-home/index/indexIndustryWeight?indexCode=000985` | 404 | 2026-10-23T23:20:00+08:00 | 没有行业权重 |
| `https://www.csindex.com.cn/csindex-home/index-weight/industryWeight?indexCode=000985` | 404 | 2026-10-23T23:20:01+08:00 | 没有行业权重 |
| `https://www.csindex.com.cn/csindex-home/perf/industry-weight?indexCode=000985` | 404 | 2026-10-23T23:20:04+08:00 | 没有行业权重 |
| `https://www.csindex.com.cn/csindex-home/index-list/query-index-industry?indexCode=000985` | 404 | 2026-10-23T23:20:05+08:00 | 没有行业权重 |
| `https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/closeweight/000985closeweight.xls` | 200 | 2026-10-23T23:20:06+08:00 | HTTP 200，文件是 000985 成份股权重（2026-09-30），没有中证一级行业列，未采用 |
| `https://www.csindex.com.cn/csindex-home/index-details/download-index-weight?indexCode=000985` | 404 | 2026-10-23T23:20:12+08:00 | 没有行业权重 |
| `https://www.csindex.com.cn/csindex-home/index/weight/query?indexCode=000985` | 404 | 2026-10-23T23:20:13+08:00 | 没有行业权重 |

## 汇率没有改用备选源

中国外汇交易中心 `CcprHisNew` 在 2005-01-04 至 2005-12-31 返回 total=0。已入库的 USDCNY 从 2006-01-04 起，来源 chinamoney。没有改用 FRED DEXCHUS，也没有把 2005 年按固定汇率补上。

## XNDX 已从官方导出取得

Nasdaq quote API `https://api.nasdaq.com/api/quote/XNDX/historical` 返回 HTTP 200，正文业务码 Symbol not exists。官方导出 `https://indexes.nasdaqomx.com/Index/ExportHistory/XNDX` 返回 2005-01-04 至 2026-09-30 的指数点位，已入库。Yahoo `^XNDX` 图表没有历史序列，没有用它。

