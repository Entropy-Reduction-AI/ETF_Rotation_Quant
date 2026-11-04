# v5 上交所 A 类缺单位派生（derived/）· 签收 · 2026-11-04

## Metadata

- Project: ETF_Rotation_Quant
- Document type: review（data-fill 签收）
- Date: 2026-11-04（Asia/Taipei）
- Author: ETF Rotation Reviewer（独立复核）
- Route: review-only（仅 `operations/reviews/**`；未改 raw、业务代码、`results/*/LOCK`、tag、`data/market.sqlite`；未 merge）
- 目标 PR: [#213](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/213) · 分支 `cursor/v5-data-fill-multipliers-derived`
- 复核 head: `c21d00f8cdd44e703bbebd45244e5d8c94dc4927`
- 范围: 新增 `data/options/derived/**` 与 `tests/data/test_option_multipliers_derived.py`；不改 `data/options/raw/**`

## Decision（对 #213）

**approve**

`multipliers-derived.csv` 92 行均可由表内 prior_unit、prev_close、dividend_amount 按上交所除息公式（流通股份变动=0）重算为 **10129**，且 `flag=derived`、事件键均为 `510050-2021-11-29`。`data/options/derived/manifest.csv` 四文件 SHA256 与行数 **4/4 重算一致**。Reviewer 以种子 `20261104-REV` 从 r2 `sse/adjustments.csv` 独立抽取 3 张已公布单位的 A 类合约，用同一公式复算单位，与 `contract_unit` **3/3 exact**；前收另用 yunhq 当日 close 复取，与 Dev 表内前收 **3/3 一致**。`blocked-attempts.csv` 诚实登记 2 张 M 标准新挂、不填 10000。`git diff origin/main...c21d00f` **未触及** `data/options/raw/**`。单元测试 `tests.data.test_option_multipliers_derived` **4/4 OK**（在复核 head 检出上运行）。

---

## 签收清单

| # | 项 | Reviewer 结论 |
| --- | --- | --- |
| 1 | 重算 derived 与 manifest SHA | ✅ 92/92 公式行；manifest **4/4** SHA256 + line_count |
| 2 | 独立 3 合约复算 vs 交易所公布单位 | ✅ 见下表；前收 yunhq 独立复取 |
| 3 | 92 行追溯 510050 2021-11-29；flag=derived；2×M blocked | ✅ 与 `contracts.csv` A 类集合一致；blocked 2 行 |
| 4 | `tests.data.test_option_multipliers_derived` | ✅ 4 tests OK |
| 5 | diff 不改 raw | ✅ 仅 `data/options/derived/**` + 测试 |

---

## 独立三合约复算（种子 `20261104-REV`）

排序键：`sha256("20261104-REV:" + contract_id)` 升序取前 3。公布单位与原单位来自 r2 `data/options/raw/r2/sse/adjustments.csv` 同行；每股现金红利来自该除息日 `spot-checks.csv` 的 `published-event` 行（与基金公告/天天基金一致）；前收为除息前一日 yunhq `sh1/dayk` close（Reviewer 运行时复取，与表内 stored 一致）。

| contract_id | ex_div_date | prior_unit | prev_close | dividend_amount | 公布单位 | 重算单位 | 结论 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `510300C2302A03800` | 2023-01-16 | 10000 | 4.144 | 0.0640 | 10157 | 10157 | exact |
| `510300P2102A05500` | 2021-01-18 | 10000 | 5.526 | 0.0720 | 10132 | 10132 | exact |
| `510300C2401A03400` | 2024-01-18 | 10000 | 3.292 | 0.0690 | 10214 | 10214 | exact |

公式：`round_half_up(prior_unit × prev_close / (prev_close − dividend_amount))`（ROUND_HALF_UP 到整数）。

机器可读明细：`/opt/cursor/artifacts/v5-multipliers-derived-reviewer-recalc.json`（本 run 落盘，不入库）。

---

## SHA256 重算（derived manifest）

| path | line_count | SHA256 一致 |
| --- | ---: | --- |
| `data/options/derived/README.md` | 69 | ✅ |
| `data/options/derived/multipliers-derived.csv` | 93 | ✅ |
| `data/options/derived/spot-checks.csv` | 24 | ✅ |
| `data/options/derived/blocked-attempts.csv` | 3 | ✅ |

r2 调整表 blob（Reviewer 读取路径）：`data/options/raw/r2/sse/adjustments.csv` → `a7d0cd439834eba195655a0c62b39bdbbc92350398e555a2290fb16469de747e`（与 `data/options/raw/r2/manifest.csv` 一致）。

---

## 边界核对

| 项 | 状态 |
| --- | --- |
| 未改 `data/options/raw/**` | ✅ |
| 未写 sqlite / LOCK / tag；未算组合收益 | ✅ |
| 92 行同一除息事件 `510050-2021-11-29` | ✅ |
| 2×M：`510050C2201M02900`、`510050P2201M02900`，reason=`not_ex_div_adjustment` | ✅ |

---

## Blockers

**无。** 若公式复算与公布单位不一致、manifest SHA 虚假、或 silent 改 raw，应为 `return_to_planning`；本次未触发。

---

## Follow-ups（非 merge blocker）

| 优先级 | 项 | 说明 |
| --- | --- | --- |
| P3 | `data/options/derived/README.md` 边界段 raw blob SHA 字面量 | 文内 `sse/adjustments.csv` / `multipliers.csv` 的 SHA 与当前 r2 `manifest.csv` 不一致；应以 r2 manifest 为准改文案，不影响派生数本身 |

---

## 测试记录

在 head `c21d00f` 检出：

```text
Ran 4 tests in 0.081s — OK
```

日志：`/opt/cursor/artifacts/v5-multipliers-derived-test-run.log`
