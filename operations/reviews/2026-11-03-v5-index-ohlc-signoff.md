# v5 数据填充（中证价格指数 OHLC）· 签收 · 2026-11-03

## Metadata

- Project: ETF_Rotation_Quant
- Document type: review（data-fill 签收）
- Date: 2026-11-03（Asia/Taipei）
- Author: ETF Rotation Reviewer（独立复核）
- Route: review-only（仅 `operations/reviews/**`；未改 raw 数据、业务代码、`results/*/LOCK`、tag、`data/market.sqlite`；未 merge）
- 目标 PR: [#199](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/199) · 分支 `cursor/v5-data-fill-index-ohlc`
- 复核 head: `8372f8b028bb3d19bcb6261811b1c173622bedf9`
- 范围: `data/research/index-ohlc/` — 000300、000986–000995、000922 价格指数 OHLC；窗口 2005-01-01→2026-09-30；csindex 原响应 + 腾讯缺口探测；manifest / session-coverage / spot-checks / blocked-attempts / SCOPE

## Decision（对 #199）

**approve**

`manifest.csv` 全部 586 条 `path` 重算 SHA256 与 `row_count`（序列 CSV）一致；12 指数在 SZSE 日历 5282 个交易日上均为 `sessions_with_rows=5279`，共同缺口仅 2008-12-31、2009-12-31、2010-12-31 且未写入序列 CSV；`off_calendar` 与 `SCOPE.txt` 对 1 月 1 日及 2018-06-18 等特殊行的说明与 CSV 内容一致。Dev `spot-checks.csv` 中需对 primary OHLC 的行与 stored CSV 一致。Reviewer 以种子 `20261103-REV` 独立拉取腾讯 ifzq kline ≥4 组（含 000300），OHLC 差为 0。PR diff 为研究数据目录 + `.gitignore` 放行 `data/research/**`；未触及 `src/`、LOCK、tag、`data/market.sqlite`。

---

## Checklist 对照

| # | 项 | Reviewer |
| --- | --- | --- |
| 1 | 重算 manifest SHA256（12 序列 CSV + 关键元数据；全 manifest 可抽样/全量） | **586/586 pass**（含 12×`raw/000*.csv`、calendar/csindex/tencent-gap JSON、`session-coverage.csv` 等） |
| 2 | 12 指数 5279/5282；三缺口未补；off_calendar 诚实 | **pass**（见「会话覆盖」） |
| 3 | 独立 spot ≥3（种子 20261103-REV）；腾讯 kline；含 000300 | **pass**（见下表 4 组 match） |
| 4 | 审计 Dev spot-checks ↔ stored | **pass**（19 行含 primary OHLC 的 match/within_0.005/gap 行逻辑一致；0 矛盾） |
| 5 | diff 边界 | **pass**（591×`data/research/index-ohlc/**` + `.gitignore` 两行 un-ignore；无 sqlite/LOCK/tag/src） |

---

## SHA256 重算摘要

Reviewer 对 `data/research/index-ohlc/manifest.csv` **全部** `path` 重算 SHA256；对 12 个序列 CSV 核对 `row_count` = 数据行数（文件行数 − 1）。

| 集合 | manifest 行数 | SHA256 | 序列 row_count |
| --- | --- | --- | --- |
| 全 manifest | 586 | **586/586 一致** | **12/12 一致**（000300→5301；其余 11 代码→5302） |

12 序列 CSV SHA256（与 manifest 一致，便于下游 pin）：

| 代码 | row_count | sha256 |
| --- | --- | --- |
| 000300 | 5301 | `76162d0e6caeb2b94559083bf16cd751d927cdc8fc054a45369028610f73cb9d` |
| 000986 | 5302 | `e9615feca7b465c70a42c1328236cc129333b8a4ec2bf18bc4e3735495e7b75f` |
| 000987 | 5302 | `592f2497e38d5eee430f47b9a652d1f335d9cb525040e5c11b9d966a55bd87e9` |
| 000988 | 5302 | `ac080de0bd23fac0e0f2945b2180eb3b1919b3f4e031a9dc09cf05cfca11df8f` |
| 000989 | 5302 | `62f18a7d549650377c1ecf1b3a75b1c77b43a18611658596f47d40119376c65e` |
| 000990 | 5302 | `263456bf7fcb680e1cb19fe125a9f4ee789ce61176c3e4f73b06d78b846452d3` |
| 000991 | 5302 | `e09cb30a770b9c1d3b53498131b18ad675f1f2735da0307d5d7fa6694403f823` |
| 000992 | 5302 | `c19b844747df3f677ed80ad1a2fb5f0a5fbf0bc119dec4833522f3d5e1bf6d3c` |
| 000993 | 5302 | `1849b6bcbbbf0f8170880f21f675d39b392a77af6461ceefaaa48250222c2352` |
| 000994 | 5302 | `f678ce67f683acef023e49ff6931ec745734c032a2570f541877d0deccb7a442` |
| 000995 | 5302 | `dd4987d94eb8953e31eac651f41f412a5207ed946bc3d9aa6c3f243ab66a6e3d` |
| 000922 | 5302 | `27c931e0109973b97a7c0b23f753f05050b6bee7adf8a96c85fb33289f81b069` |

---

## 会话覆盖（5279/5282）

独立读取 12 个 `raw/{code}.csv` 与 `session-coverage.csv`：

| 项 | Reviewer |
| --- | --- |
| `calendar_sessions` | 12/12 = **5282**（2005-01-04→2026-09-30，SZSE monthList jybz=1） |
| `sessions_with_rows` | 12/12 = **5279** |
| `missing_ranges` | 12/12 = **2008-12-31;2009-12-31;2010-12-31** |
| 缺口是否出现在序列 CSV | **否**（三日期在 12 个 CSV 中均不存在） |
| 000300/000922 腾讯 gap 原响应 | `raw/tencent-gap/` 保留 bar；**未 splice** 进序列（与 Dev gap-absent spot 一致） |
| 000986–000995 腾讯三窗口 | `blocked-attempts.csv` + 空数组 JSON；**未 invented** |
| off_calendar | 000300：**22** 行（每年 1 月 1 日；Reviewer 抽查 2005-01-01 OHLC 与 2005-01-04 相同）；000986–000995、000922：**23** 行（另含 2018-06-18）；与 `SCOPE.txt` 一致 |

---

## Spot-check 结果

### Dev 表 ↔ 存储

对 `spot-checks.csv` 中 `open_primary` 非空且结果为 `match` / `within_0.005` / `gap-neighbor` 的行，primary OHLC 与 `raw/{code}.csv` 同行一致（**0 fail**）。`gap-absent` / `no_second_bar` 行按设计不要求 CSV 含该日。

### Reviewer 独立复取（腾讯 ifzq.gtimg.cn kline，种子 `20261103-REV`）

容差：OHLC 差 **0**（官网两位小数场景允许 ≤0.005 的 neighbor 行仅在 Dev 表已标注，Reviewer 独立组均为 exact 0）。

| 代码 | 日期 | stored O/H/L/C | 腾讯 O/H/L/C | 最大 abs diff | 结果 |
| --- | --- | --- | --- | --- | --- |
| 000300 | 2024-11-18 | 3982.10 / 4034.06 / 3931.19 / 3950.38 | 同左 | 0 | match |
| 000986 | 2017-03-30 | 2098.10 / 2105.09 / 2074.90 / 2084.03 | 同左 | 0 | match |
| 000993 | 2025-06-27 | 6122.82 / 6183.97 / 6056.21 / 6127.00 | 同左 | 0 | match |
| 000922 | 2025-04-29 | 5372.04 / 5400.12 / 5364.17 / 5377.23 | 同左 | 0 | match |

注：同种子另抽 `000988`·2016-07-07 前后窗口时腾讯 day 数组为空（历史覆盖限制），**未计为 fail**；有效独立 match 已 ≥4 且含 000300。

---

## 边界核对

| 项 | 状态 |
| --- | --- |
| `git diff main...8372f8b` 无 `src/`、无 LOCK、无 tag、无 `data/market.sqlite` | ✅ |
| 研究数据 + `.gitignore` un-ignore `data/research/**` | ✅ |
| 未算组合收益 / 未跑策略 | ✅ |
| 序列仅 csindex 落盘；腾讯未补三缺口日 | ✅ |

---

## Follow-ups（非 merge blocker）

| 优先级 | 项 | 说明 |
| --- | --- | --- |
| P3 | 三缺口交易日 | 消费侧若要对齐 5282 日历，须显式处理缺失或只读 `tencent-gap` 探测文件，**不要求**本 PR splice |
| P3 | off_calendar 行 | 下游按 `session-coverage.off_calendar_*` 过滤或保留研究用原样 |
| P3 | 腾讯早期 sector 覆盖 | 部分代码远古日期 kline 可能空；设计期应仍以 csindex 为准 |

---

## Blockers

**无。**
