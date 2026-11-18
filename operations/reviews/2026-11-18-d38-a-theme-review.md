# D38 A 股主题 25 指数 · Reviewer 独立签收 · 2026-11-18

## Metadata

- Project: ETF_Rotation_Quant
- Document type: operations review（Reviewer 交付；**不合并** Dev PR）
- Date: 2026-11-18（Asia/Taipei）
- Author: ETF Rotation Reviewer（Cloud Agent）
- Dev PR: [#313](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/313)（**OPEN**，base `main` @ `e3372e13ab13bcffc17649bf0b348d50989e5da2`，head **`ca74943a723bfd94e042b59bc24204747fbf30c9`**）
- Companion PR: 本分支 `cursor/d38-a-theme-review-8094` → `main`（仅 `operations/reviews/**`）
- 机器可读: `operations/reviews/diag/d38-a-theme/d38-a-theme-recalc.json`；脚本 `operations/reviews/diag/d38-a-theme/d38-a-theme-verify.py`

## Decision

**`approve`**

25 个目标代码在名册中均有 `publish_date`；23 `spliced`、1 `already`（`000688`）、1 `frozen`（`H30187`，原因已写）。行情库 SHA256、append-only、本轮仅 `000015`/`930606` 新增 bar、看板第 1 节计数与 Dev 声称一致。Reviewer 独立东财重叠段中位相对差 ≤ 0.01%（8 个可比对码全部 0.0000%）。**未**重跑中国组合 PnL；**未**改 LOCK；**未**合并 #313。

| 级别 | 数量 |
| --- | --- |
| Must-fix | **0** |
| Should-fix | **0** |
| Note | **2**（§8） |

---

## 1 · 身份与范围

| 项 | Reviewer 结果 |
| --- | --- |
| Dev PR 状态 | **OPEN** @ `ca74943a723bfd94e042b59bc24204747fbf30c9` |
| base | `e3372e13ab13bcffc17649bf0b348d50989e5da2` |
| 本签收 PR | 仅审查产物；不含 `data/market.sqlite`、evidence 截图、名册或 ingest 代码 |
| D37-R6 / #312 | **未**检视、未触碰 |

---

## 2 · 行情库 SHA256

| 对象 | SHA256 | 一致 |
| --- | --- | --- |
| `main` 实文件（d38 前，Reviewer `sha256sum`） | `d0b947d90b444eb1d874a04df6bcb1974cbea4422b489f214a56c0a658abf0d9` | ✅ |
| #313 worktree 实文件（d38 后） | `c07297f8372c2b4dd8f79417306f4dda3b2b49db3cb2523a6ad306c13523588b` | ✅ |
| Dev `results/v51-diag/d37/db-sha256.txt` | 同上 before/after | ✅ |
| bar 行数 | 1,156,774 → 1,164,886（+8,112） | ✅ |

---

## 3 · append-only

Reviewer 对两库全部 `bars` 行做 `(code, date, adj)` 指纹比对：

| 检查项 | 结果 |
| --- | --- |
| 接缝前已有行被修改或删除 | **0** |
| 仅新增行所属 `code` | **`000015`、`930606`**（与 Dev 一致） |
| 新增行数 | **8,112**（5,301 + 2,811） |

---

## 4 · 名册与发布日（25 码）

| 检查项 | 结果 |
| --- | --- |
| `s1-splice-roster.csv` 中 25 个 `index_code` 均存在 | ✅ |
| 全部具备非空 `publish_date` | ✅ |
| `status` 汇总 | `spliced` 23；`already` 1（`000688` / `star50`）；`frozen` 1（`H30187`） |
| `operations/evidence/d38-a-theme/csi-*-note.json` 发布日 vs 名册 | **25/25** 一致（`screenshot_bytes` > 80k） |
| 独立 CSI API（抽查 `931743`） | 发布日 `2012-12-21`、基日 `2018-12-28` ✅ |

### 931743（发布日晚于基日）

官网与名册均为发布日 **2012-12-21**、基日 **2018-12-28**；截图与 API 一致。**不因发布早于基日而判失败。**

### 000688（池内已有）

`star50`：`already`；发布日 **2020-07-23** 已登记。库内 `000688` 在发布日前 **134** 行（基日 2019-12-31 段，#313 前既有）；本轮 **无** 新 bar（`db_row_deltas` 为空）。

### H30187（未接上）

名册 `frozen`：`bars_code` 空；原因写明东财「细分化工」为 `000813` 而非 `H30187`。Reviewer：**#313 前后 `H30187` bar 行数均为 5,279、均为 `csi` 来源，无 delta**；`000813` 在两库中均为 **0** 行。东财对 `H30187` **0** 条指数日线（重叠 0 天）。库内既有 `H30187` 序列为 #313 前既有，本轮未写、未删；容器状态与 Dev 叙述一致。

---

## 5 · 新写入序列（库内）

| 代码 | 发布日 | 行数 | 首交易日 | 发布日前 bar |
| --- | --- | ---: | --- | ---: |
| `000015` | 2005-01-04 | 5,301 | 2005-01-04 | **0** |
| `930606` | 2015-03-31 | 2,811 | 2015-03-31 | **0** |

其余 23 个 `spliced` 码本轮 **无** `bars` 行数变化（仅名册/证据更新或沿用既有序列）。

---

## 6 · TR/NTR vs 价格指数（universe.csv）

与名册 `reason` 一致：凡 `tr_code_candidates` 中全收益/净收益无第二条日线者，入库均为 **价格指数**（`bars_code` = 研究用 `research_index_code`）。未使用 `000813` 顶替 `H30187`。详见 JSON `universe_ingest`。

---

## 7 · 数据看板第 1 节

按 #313 上 `results/v4/diag/data-board/splice_status.py` 逻辑在名册上复算：

| 指标 | Reviewer |
| --- | ---: |
| 全市场容器 | **139** |
| 已有上市前历史（自己的历史 + 已接上） | **84** |
| 在 Grok 第六轮 | **36** |
| 未接上 | **1**（`theme-中证细分化工产业主题`） |

与 Dev PR 描述一致。

---

## 8 · 点位抽查（≥8 码；东财 vs 库，发布日后）

Reviewer 独立 `searchapi` + `push2his`（`DEV_WORKTREE` 内 `fetch_eastmoney`），与 #313 后库 `adj=raw` 收盘比对。

| 代码 | 发布日 | 重叠日 | 中位相对差 | 门槛 | 判定 |
| --- | --- | ---: | ---: | --- | --- |
| 931743 | 2012-12-21 | 778 | 0.0000% | ≤0.01% | ✅ |
| 000688 | 2020-07-23 | 1,503 | 0.0000% | ≤0.01% | ✅ |
| 000015 | 2005-01-04 | 5,279 | 0.0000% | ≤0.01% | ✅ |
| 930606 | 2015-03-31 | 1,643 | 0.0000% | ≤0.01% | ✅ |
| H30184 | 2013-07-15 | 3,215 | 0.0000% | ≤0.01% | ✅ |
| 000819 | 2012-05-09 | 3,501 | 0.0000% | ≤0.01% | ✅ |
| 930713 | 2015-07-31 | 2,714 | 0.0000% | ≤0.01% | ✅ |
| 399998 | 2015-02-13 | 2,826 | 0.0000% | ≤0.01% | ✅ |
| H30187 | — | 0 | — | 不适用 | frozen；无第二源 |

### Note（非 Must-fix）

1. 多个 **本轮前已在库** 的 `spliced` 码（如 `H30184`、`930713`）仍有发布日前的历史 bar；#313 遵守「不删不改既有行」，仅对新码 `000015`/`930606` 做到发布日起点。若 Owner 要全池统一清掉发布前 bar，需另开 scoped 任务。
2. `H30187` 库内 5,279 行系历史既有；本轮正确标 `frozen` 且未用 `000813` 顶替，但若化工容器要可打分，仍须将来单独处理数据源或换码。

---

## 9 · 复跑方法

```bash
git fetch origin main cursor/d38-a-theme
git worktree add /tmp/d38-pr313 origin/cursor/d38-a-theme
git lfs pull -I data/market.sqlite   # 在 main 检出与 worktree 内各跑一次

DEV_WORKTREE=/tmp/d38-pr313 \\
BEFORE_DB=$PWD/data/market.sqlite \\
AFTER_DB=/tmp/d38-pr313/data/market.sqlite \\
.venv/bin/python operations/reviews/diag/d38-a-theme/d38-a-theme-verify.py
```

---

## 10 · 文件清单

| 路径 | 说明 |
| --- | --- |
| `operations/reviews/2026-11-18-d38-a-theme-review.md` | 本签收 |
| `operations/reviews/diag/d38-a-theme/d38-a-theme-verify.py` | 复算脚本 |
| `operations/reviews/diag/d38-a-theme/d38-a-theme-recalc.json` | 机器可读结果 |