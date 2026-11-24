# PR359 独立取证（Reviewer evidence worker）

## PR 锚点

| 项 | 值 |
| --- | --- |
| PR | [#359](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/359) |
| 标题 | DJIA 与 DWRTF 价格日线缺口对照，931743 发布日未找到公告 |
| head（取证前/后） | `74ea30699d184c01971ee55a0abdbcc1e36d5d84`（未变） |
| base | `ea613920cd37176e03acb85e97f1ceb9c846e1bb`（`main`） |
| 改动范围 | 47 文件，+18969 / 0；`incoming/v6-us-gapfill/**`、`scripts/v6_us_gapfill_compare.py`、`operations/reviews/**`（本取证分支追加） |
| sqlite / config / src 策略 | **无**（`git diff main...74ea306` 无匹配） |

## 相对差约定

`abs(left - right) / abs(right)`；与库重叠时分母为库内 `adj='raw'` 收盘。停止门槛 **0.001（0.1%）** 仅用于**库重叠**对（与 Dev 脚本一致）。

独立复算命令：

```bash
python3 -I scripts/v6_us_gapfill_compare.py          # Dev 交付脚本，exit 0（Reviewer 实测）
python3 -I operations/reviews/pr359-independent-evidence.py  # Reviewer 独立复算，exit 0
```

## 独立重下载

| 序列 | URL | 原始 SHA256 | 与 PR 交付 |
| --- | --- | --- | --- |
| FRED DJIA | https://fred.stlouisfed.org/graph/fredgraph.csv?id=DJIA | `256b9f380c3b20aef06cf4e0846d1527897e6cd6c3db1d5b700b22da08577f69` | **字节一致** |
| CNBC DWRTF 重叠段 | https://ts-api.cnbc.com/harmony/app/bars/.DWRTF/1D/20170801000000/20171231235959/adjusted/GMT（需浏览器 UA） | `9afe71e0d4cab6b045fe422b8383e5476438278672a66007331829f51ec5a668` | **字节一致**；`adjusted=UNADJUSTED`，`companyName=DJUSslct REIT` |

归档复用（非本轮新下）：TradingView 长日线 `1b2e608e…`；官方约一年价格 `861189a9…`（路径见 PR body）。

## 库只读重叠（≥60 日）

| 代码 | `bars.source` | 窗 | 天数 | 最大相对差 |
| --- | --- | --- | ---: | ---: |
| DJIA | `eastmoney_index` | 2023-11-01 … 2024-02-01 | 63 | FRED 0；CNBC `1.436e-07`（2023-11-14） |
| DWRTF | `d37_r6` | 2017-08-01 … 2017-11-22 | 81 | CNBC 0（例：2017-08-01 均为 275.51） |

**`d37_r6` 与 TradingView 归档同源**；TradingView↔库 **不能**算独立核对。DWRTF 独立核对为 **CNBC↔库**。

## 要求窗两源对照（独立复算）

### DJIA 2024-02-01 … 2026-09-30

| 对照 | 出版方独立性 | 重叠 | 仅右 | 最大相对差 |
| --- | --- | ---: | --- | ---: |
| FRED / CNBC | SPDJI 再发布 vs LSEG/CNBC | 668 | 2024-12-25（CNBC） | `1.308e-07` |
| FRED / Yahoo | 印证，非第三算法 | 668 | 同上 | （脚本另有） |

新浪规范化收盘与 FRED **逐字相同**，按 Owner 规则 **不另算独立源**。

### DWRTF 2017-11-22 … 2026-09-30

| 对照 | 独立性 | 重叠 | 单边日 | 最大相对差 |
| --- | --- | ---: | --- | ---: |
| CNBC / TradingView（归档） | LSEG vs ICE（经 TV） | 2223 | CNBC 多 2024-12-25；TV 多 2023-04-06 | **0.000407526（0.04075%）**，2019-08-12 |
| CNBC / 官方价格（归档） | 2025-11-17 … 2026-09-30，218 日 | 218 | 无 | 0 |

## 异常日显式评估（非盲目 <0.1%）

1. **2019-08-12（DWRTF）**：CNBC 294.5800 vs TV 294.46 → 相对差 0.04075%。其余 2222 个共同交易日字符串级一致；>0.01% **仅此一日**。未达 0.1% 停止线；形态像两家对小数位/舍入差，**不构成价格 vs 总收益身份混淆**（CNBC 明确 UNADJUSTED；库重叠与官方短文件均为 0）。
2. **2024-12-25（CNBC DJIA/DWRTF）**：Reviewer 解析原始 JSON：OHLC 与 2024-12-24 **完全相同**（DWRTF 收盘均 294.9400）。圣诞假日；FRED/Yahoo/TV 无此日。PR 保留未删——**文档化伪交易日**，不抬高相对差（无共同日则不进 pairwise）。
3. **2023-04-06（仅 TV）**：CNBC 无；TV 259.56。单日缺口，未插值。

## 价格身份（DWRTF）

- CNBC：`UNADJUSTED`，Bloomberg 线称 DWRTF（Wayback 页在 PR `raw/`）。
- 库 `DWRTF`/`d37_r6`：与 CNBC 重叠 81 日 **相对差 0**。
- 未使用 DWRTFT / DWRTFN。

## ≥20 日抽样（各系列）

完整列表见 `operations/reviews/pr359-independent-evidence.json` → `date_samples`（DJIA gap/overlap、DWRTF gap/overlap 各 **24+** 点）。节选：

| 日期 | DJIA FRED | CNBC | sqlite（重叠窗） |
| --- | ---: | ---: | ---: |
| 2024-02-01 | 38519.84 | 38519.8400 | — |
| 2024-09-30 | 42330.15 | 42330.1500 | — |
| 2026-09-30 | 50906.05 | 50906.0500 | — |
| 2023-11-01 | 33274.58 | 33274.5800 | 33274.58 |
| 2024-02-01 | 38519.84 | 38519.8400 | 38519.84 |

| 日期 | DWRTF CNBC | TV 归档 | sqlite |
| --- | ---: | ---: | ---: |
| 2017-11-22 | （窗起点） | 同 PR 交付 | — |
| 2017-08-01 | 275.5100 | — | 275.51 |
| 2019-08-12 | 294.5800 | 294.46 | （无 sqlite） |
| 2025-11-17 | 293.1900 | 293.19 | — |

## 931743 正式发布日

| 来源 | URL / 文件 | 有关原文 |
| --- | --- | --- |
| 编制方案 PDF | https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/20231208180655-931743_Index_Methodology_cn.pdf | 「该指数以 **2018 年 12 月 28 日**为基日，以 1000 点为基点。」**无「发布」字样** |
| 概况单 PDF | …/931743factsheet.pdf | 字段「**发布日期 2012年12月21日**」「**基日 2018年12月28日**」 |
| 详情 API | https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info/931743 | `publishDate=2012-12-21`，`basicDate=2018-12-28`；`indexCnDesc` 无「于某日发布公告」 |

**正式发布公告：未找到**（与 PR `NOTE-931743.md` 一致）。概况单/接口「发布日期」**不能**替代「关于发布的公告」；编制方案 PDF 文件名时间戳 **不是**正文发布日。**未做 roster/config 改动。**

## 建议结论（供 Coordinator，非 GitHub 正式 review）

**建议：APPROVE（缺口原始价格取证包）**

依据：两独立出版方对照均 <0.1%；库重叠 63/81 日均 <0.1%；DWRTF 价格身份可由 CNBC UNADJUSTED + 库零差 + 官方短窗零差成立；独立重下 FRED 与 CNBC 重叠段与交付字节一致。

**随 PR 带走、不挡价格缺口本身的问题：**

1. 931743 **权威发布公告仍 未找到**；若名册逻辑依赖「正式发布日」而非基日，需 Orchestrator 决定 `2012-12-21` 字段 vs `2018-12-28` 基日如何用于 v6（本 PR 未改名册）。
2. DWRTF CNBC/TV **归档第二源**非本轮新下；2019-08-12 0.04% 单日差应在入库存档时知悉。
3. CNBC **2024-12-25** 伪交易日保留策略已文档化。

## 产物路径

- 报告：`operations/reviews/2026-11-24-pr359-independent-evidence.md`
- 机器可读：`operations/reviews/pr359-independent-evidence.json`
- 独立 raw：`/opt/cursor/artifacts/reviewer-pr359/raw/`