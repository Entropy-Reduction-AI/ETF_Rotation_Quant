# D37 round 5 · v5.1 方案 B 诊断 · Reviewer 签收 · 2026-11-06

## Metadata

- Project: ETF_Rotation_Quant
- Document type: review（诊断独立复算；**不计入**任何过关判据）
- Date: 2026-11-06（Asia/Taipei）
- Author: ETF Rotation Reviewer（Cloud Agent）
- Dev PR: [#284](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/284)（**OPEN**，base 当前 `main` @ `87089f9a4f0b968e30101a82917f89fa74f7ffb2`，head **`770b22b2779309f70936b59ff210905922676d3f`**，`cursor/d37-r5`）
- 合并基线：`git merge-base main origin/pr-284-head` = **`a0ede094c5e5d604d1d9b5cb1c08da0d64641b40`**（与 Manager 记录的 #280+#282 后 `main` 一致；其后 `main` 仅因文档/资源补丁前移至 `87089f9a`，**不**视为 Must-fix）
- Companion PR: 本分支 → `main`（**未**合并 #284）
- 机器可读: `operations/reviews/diag/v51/d37-r5-recalc.json`；脚本 `operations/reviews/diag/v51/d37-r5-verify.py`

## Decision

**approve**

本工作 **不** 重判策略优劣。Must-fix（产物缺项、统计不可复现、库 SHA 非预期、设计期净值被改写、与宣称引擎不符）均为 **0**。

| 级别 | 数量 |
| --- | --- |
| Must-fix | **0** |
| Should-fix | **0** |
| Note | **3**（§8） |

---

## 1 · 身份与合并可读性（#284）

| 项 | Reviewer 结果 |
| --- | --- |
| 状态 | **OPEN**，未合并（`gh pr view 284`） |
| head SHA | `770b22b2779309f70936b59ff210905922676d3f` |
| 分支名 | `cursor/d37-r5` |
| base OID（审查时 API） | `87089f9a4f0b968e30101a82917f89fa74f7ffb2`（当前 `main`） |
| 与 #284 的 merge-base | `a0ede094c5e5d604d1d9b5cb1c08da0d64641b40`（Manager 所称「从 a0ede094 打开」✅） |
| `git merge-tree` 粗读 | 无冲突标记；**可读作「可干净合并」**（与 Manager 一致；**不**把未 rebase 到最新 `main` 记为 Must-fix） |

---

## 2 · 行情库 `data/market.sqlite` SHA256

在 **已 `git lfs pull` 的 #284 worktree** 上对实体文件 `sha256sum`：

| 对象 | SHA256 |
| --- | --- |
| #284 head worktree 解析后 blob | `d0b947d90b444eb1d874a04df6bcb1974cbea4422b489f214a56c0a658abf0d9` |
| `results/v51-diag/d37/db-sha256.txt` AFTER d37-round4 | 同上 ✅ |
| LFS 指针 oid（未 pull 前） | 同上 ✅ |

**结论**：与 round4 登记库一致；无静默换库。

---

## 3 · 产物完备性（四格 B）

以下目录在 **#284 @ 770b22b** 上均存在，且含 **`stats.json`、`market_days.csv`、`markets.csv`、`vs-v0.csv`、`daily.csv`、`trades.csv`、`sells.csv`**：

- `results/v51-diag/d37/S0/设计期/B/`
- `results/v51-diag/d37/S0/别的市场/B/`
- `results/v51-diag/d37/S0/检验段/B/`
- `results/v51-diag/d37/S1/检验段/B/`

**设计期**另含 **`markets-window.csv`**（与 Dev 说明一致：全表 `markets.csv` 仍含 2005 年 242 日现金预热；窗口统计单独给出）。

---

## 4 · S0 设计期 B：与已签收路径一致

`S0/设计期/B/daily.csv`：**#284 与当前 `main` 上已有 r4 产物 SHA256 相同**（`58d95367…`），**未**发现与设计期净值被重跑或替换。

`results/v51-diag/d37/plan-b-s12.txt`：**已**写明 2015-07-27 创业板涨跌停机制、`run_book` 与 S12 `simulate` 的差异、两日净收益差与累计差（与 round4 已接受叙述一致）。**不**将「与 S12 非 bitmatch」记为 Must-fix。

---

## 5 · 独立复算（四格 B；口径同 V0–V4）

对每格自 `daily.csv` 取 **与 `write_stats` / `diag_stats` 相同窗口**（设计期 `2006-01-01`→`2015-12-31`；其余为全日历），用 `performance` + `trade_cost` 复算 CAGR、最大回撤、成交次数与成本；并与同段 `V0/stats.json` 做差，对照 `vs-v0.csv`。

**结论**：四格 **与 Dev `stats.json` 一致**（浮点容差见脚本）；**`vs-v0.csv` 的 B−V0 与独立复算一致**。

### 5.1 Reviewer 独立 B 与相对 V0（表内为百分点 / 每年笔数 / 成本占比）

| 格 | B 年化 | B 最大回撤 | B 成交/年 | B 成本/年 | Δ年化 vs V0 | Δ最大回撤 vs V0 | Δ成交/年 vs V0 | Δ成本/年 vs V0 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| S0 设计期 | 26.86% | −31.99% | 61.2 | 4.31% | −3.28pp | −6.14pp | +11.5 | +1.06pp |
| S0 别的市场 | 0.94% | −47.74% | 65.6 | 6.79% | −0.36pp | −2.87pp | +4.4 | +0.92pp |
| S0 检验段 | −3.62% | −55.12% | 76.9 | 7.50% | −0.15pp | −0.80pp | +7.0 | +0.88pp |
| S1 检验段 | 6.20% | −32.29% | 76.4 | 7.18% | +4.54pp | +9.53pp | +25.2 | +2.01pp |

（Δ最大回撤为 **B−V0**；若两值皆为负，代数值更大表示回撤更浅。）

### 5.2 额外表格（存在性 + 与 stats 一致）

- **`market_days.csv`**：各格均有；例：`S0/检验段/B` 同时持有 0/1/2/3 个市场之天数分布与 `stats.json` 内 `plan_b.market_days` 一致（脚本未逐格展开，属抽查 + 结构一致）。
- **`markets.csv`**：各格均有平均权重与贡献列。
- **`vs-v0.csv`**：与 §5.1 独立 B−V0 **逐行一致**。

---

## 6 · 引擎路径（确认任务）

| 格 | `stats.json["execution"]` | Reviewer 代码核对 |
| --- | --- | --- |
| S0 设计期 / S0 检验段 / S1 检验段 | `run_book` | `src/v51/d37_plan_b.py`：`run_s0_design` / `run_s0_inspection` / `run_s1_inspection` 均经 `_run_cn_version` → `run_book` |
| S0 别的市场 | `gpool.simulate` | `run_other` → `gpool.run_v51` → **`simulate`**（`src/v51/gpool.py` `run_v51`） |

**G 池参数**：`_base_params` / manifest 中 **`limits: False`**（无日线涨跌停规则）；`run_v51` 内 **`simulate` + `fees_for(...)`**，与「同段 V0 别的市场」同一成交栈。

**若强行把中国 `run_book` 套在 G 池**：`run_book` 路径服务 **中国 market + 涨跌停/费用开关**；与 G 池 manifest（limits off、标的与费用表不同）**不是**无差别替换 — Dev 在 `plan-b-s12.txt` / `bm-g-note.txt` 的说明与代码 **一致**。

**结论**：记为 **已核实 Note**（ Manager 所述路径成立），**不**升级为 Must-fix。

---

## 7 · 复现

```bash
git fetch origin main pull/284/head:refs/remotes/origin/pr-284-head
git worktree add /tmp/d37-r5-pr284 origin/pr-284-head
cd /tmp/d37-r5-pr284 && git lfs pull -I data/market.sqlite

cd /path/to/ETF_Rotation_Quant
DEV_WORKTREE=/tmp/d37-r5-pr284 .venv/bin/python operations/reviews/diag/v51/d37-r5-verify.py
```

---

## 8 · Note

1. **#284 base** 为审查时的 **`main` @ `87089f9a`**；与 Dev 打开时相比 **`main` 已前移**（ trade-notes 等资源），合并基线仍为 **`a0ede094`**；**不**要求 Dev 为签收目的重 rebase。
2. **设计期 B** 沿用已接受净值；第五轮仅补分布与 V0 对照文件，符合 Owner 指示。
3. **G 池**无涨跌停、走 `simulate`，与 `run_book` 中国路径分离，属已记录的设计，非 silent substitution。

---

## 9 · 纪律

Reviewer **未** merge #284；**未** 向 `cursor/d37-r5` push；**未** 改 `results/v5/LOCK` 或 LOCK-addendum 正文；**未** 移动 tag 或改写 `main`。
