# v4-R5b · D24 U-可交易修复 · 签收 · 2026-10-29

## Decision：`approve_with_follow_up`

在 Dev PR [#126](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/126) 尖端 `b92d9eacd9805b92fff29578ebd7192584ef5e20`（base main `149393b`）上，Reviewer **独立**完成 D24-4 必查五项：场外数据抽查、2005–2015 U-可交易年度普查、载体路径、B0 U-可交易复算、U-指数/过关表/账本/库指纹。结论：**实现与冻结预注册 §3.2 对齐**；U-指数 **20** 条 `net_sha256` 相对 v4-R5 设计期基线（`982c0cf…`）**逐条不变**；过关表 SHA 仍为 `32058828…`；ledger **41** 行、**21** 条 U-可交易/A1/A2 行均含 `fix: D24-1`。未发现 2016+ 组合 PnL、LOCK 或 tag 移动。

Follow-up（不阻塞 Dev #126）：**Manager** 按 plan 重跑数据看板（当前 `summary.json` 仍登记 D22 库 SHA）；**Orchestrator** 裁定 ChiNext 联接是否入第 2 档（Dev 已 defer，见 §5）。

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R5b D24 U-tradable fix Reviewer 签收（PR #126）
- Date: 2026-10-29 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（Review 分支仅追加本文件与 diag 脚本/JSON）
- Dev: PR #126 · branch `cursor/v4-r5b-d24-490e` · head `b92d9ea…`
- Plan: `operations/planning/2026-10-29-v4-r5b-plan.md`；D24：`operations/planning/2026-10-29-d24-v4-health-check.md`
- Dev work log: `operations/work_logs/2026-10-29-v4-r5b-tradable-fix.md`
- 设计期上界: **2015-12-31**

## 独立复算命令与产物

环境：仓库根 `.venv`；`git lfs pull` 后 `data/market.sqlite`；`mkdir -p outputs`。

| 步骤 | 命令 | 结果 |
| --- | --- | --- |
| D24 必查汇总 | `.venv/bin/python operations/reviews/diag/v4/v4-r5b-tradable-review.py` | exit **0**（约 9 min） |
| 过关表（U-指数，应不变） | `.venv/bin/python operations/reviews/diag/v4/v4-r5-gate-scorecard-recompute.py` | exit **0** |
| 回归 | `.venv/bin/python -m unittest discover -s tests/v4 -t . -q` | **OK**（147 项量级） |

日志：`/opt/cursor/artifacts/v4-r5b-tradable-review.log`  
JSON：`operations/reviews/diag/v4/v4-r5b-tradable-review.json`

---

## 1) 场外基金抽查（5 只）

成立日（`v4_listing.inception` vs Dev roster）：

| 代码 | 容器 | DB / roster 成立日 | 结论 |
| --- | --- | --- | --- |
| 050002 | csi300 | 2003-08-26 | 一致（D22 已有，非本次 INSERT） |
| 040046 | ndx100 | 2013-08-02 | 一致 |
| 050025 | spx | 2012-06-14 | 一致 |
| 000071 | hsi | 2012-08-21 | 一致 |
| 160416 | theme-标普全球石油指数 | 2012-03-29 | 一致 |

复权净值（2015-12-24→2015-12-31，5 个交易日）：Reviewer 用 `api.fund.eastmoney.com/f10/lsjz` 的 **累计净值 LJJZ** 日收益，与库内 `v4_series.kind='otc_nav'.close`（连乘口径）对照。

| 代码 | 最大 \|API−DB\| 日收益 | 说明 |
| --- | ---: | --- |
| 040046 | ≈ 2.7×10⁻⁷ | 与 Dev pingzhong/lsjz 路径一致 |
| 050025 | ≈ 2.1×10⁻³ | 舍入/源字段差异，可接受 |
| 000071 | ≈ 1.0×10⁻² | 同上量级 |
| 160416 | ≈ 7.3×10⁻⁴ | 同上 |
| **050002** | **≈ 1.70×10⁻²**（2015-12-29） | **预存 pingzhong 连乘序列**与 lsjz LJJZ 单日可差约 1.7pp；非 D24 新插入，建议 Manager 登记时注明源路径，**不视为 D24 回归** |

---

## 2) U-可交易年度普查（2005–2015）

**方法：** 对 B0、T1–T4、final、A1、A2 **独立复跑** U-可交易引擎（`prepare_market(..., pool='tradable')` + `execute`；A1/A2 用 `research_panel` + `run_peer`）。每年统计：

- **可交易容器数**：当年至少一日 `liquidity`（载体路径非空，含 3,000 万门槛等）为真的 **distinct 容器**；
- **平均现金权重**：`held[cash]` 日均；
- **权重前五**：非现金容器 **日均权重** Top 5；
- **看板对照**：`results/v4/diag/data-board/out/summary.json` 的 `buy_by_year` 五组之和；非 T4 运行 **减去** `us-*` 行业容器（plan D24-4）。

完整数字见 JSON `yearly_census`。**B0** 与看板对照摘要：

| 年 | 可交易容器数 | 看板 buy 合计（非 T4） | 平均现金权重 | 权重 Top1（约） |
| ---: | ---: | ---: | ---: | --- |
| 2005 | 1 | 1 | 96.5% | csi300 3.5% |
| 2006 | 1 | 1 | 80.3% | csi300 19.7% |
| 2007 | 2 | 2 | 67.5% | csi300 19.9% |
| 2008 | 2 | 2 | 90.6% | csi-dividend 5.5% |
| 2009 | 3 | 3 | 64.8% | csi300 15.4% |
| 2010 | 6 | 6 | 56.6% | csi500 14.7% |
| 2011 | 6 | 9 | 61.2% | ndx100 12.8% |
| 2012 | 10 | 11 | 43.7% | ndx100 16.2% |
| 2013 | 12 | 14 | 12.3% | spx 17.5% |
| 2014 | 12 | 17 | 8.1% | ndx100 14.2% |
| 2015 | 17 | 20 | 15.6% | cgb-5y 14.8% |

**差异说明（材料项）：**

- **看板 buy** = 年末「有上市/成立记录」的容器累计，**不含** 3,000 万成交额、后复权缺失、场外 NAV 未起、换载体路径等执行层门槛。
- **2011**（6 vs 9）：美股宽基/主题容器已在看板「可买」，但当年尚无满足第 1/2 档的载体或 NAV 序列（如 SPX/HSI 联接更晚）。
- **2012–2015**：差 1–3 个容器，典型为 **场内 ETF 未过 30M**、**chinext** 研究序列走拼接但可交易载体仍稀疏、或 **QDII/LOF** 仅部分日有有效载体。
- **T4 / 2015**：可交易 **27** vs 看板 **30**（含 US 行业）：行业 SPDR 需满足成交额与路径，看板只计 `official_launch`。

T1–T4、final 与 B0 **同口径**普查已写入 JSON；T4 2015 Top5 含多个 `us-*` 行业腿（符合 t4_pool）。

---

## 3) 载体路径五点抽查

`choose_path`（粘性）与 `choices_on`（同日无 prior）在下列日期 **一致**，与 Dev work log 相同。

| 容器 | 日期 | 载体 | 档 | 原因（Reviewer） |
| --- | --- | --- | ---: | --- |
| csi300 | 2006-06-30 | otc:050002 | 2 | 当日仅第 2 档 OTC 就绪；510300 尚未上市 |
| hsi | 2012-12-31 | otc:000071 | 2 | 000071 为当日唯一就绪候选（2012-08-21 成立） |
| ndx100 | 2013-12-31 | otc:160213 | 2 | 第 2 档按成立最早排序 → 160213（2010-04-29）优于 539001/040046 |
| gold | 2013-12-31 | otc:000216 | 2 | 518880 未过第 1 档；联接 000216/000217 就绪，取排序第一 |
| theme-标普全球石油指数 | 2012-12-31 | otc:160416 | 2 | 唯一就绪第 2 档 LOF（2012-03-29） |

---

## 4) 独立复算与指纹

### B0 U-可交易（E2 新口径 / final，全日历 ≤2015-12-31）

| 指标 | Dev 公布 | Reviewer 复算 | 一致 |
| --- | ---: | ---: | --- |
| CAGR | 9.617% | 9.617% | 是（\|Δ\| < 10⁻¹²） |
| 最大回撤 | −31.700% | −31.700% | 是 |
| `net_sha256` | `c49e507d…` | `c49e507d…` | 是 |

### U-指数（20 条 index 行）

- 各 case `summary.json` 的 `net_sha256` 与 `read_net`→`series_sha256` **一致**。
- 与 v4-R5 设计期基线 commit `982c0cf…` 逐 case 对比：**无 mismatch**（含 B0/final `6f92c038…`）。

### 过关表 / 库 / 账本

| 项 | 期望值 | Reviewer |
| --- | --- | --- |
| `candidate-gate.csv` SHA256 | `32058828326f5155ce9b9a678746d2f55d7a4a023b3d20a883e01676383c1b42` | **一致**；`v4-r5-gate-scorecard-recompute.py` 独立表仍 match |
| `data/market.sqlite` SHA256 | `79ae5a47e1a6eb0977a18f13efb21211d24b48e393ad567f615130d89c8f00cd` | **一致**（297672704 B；无 `-wal`/`-shm`） |
| `trial-ledger.csv` | 41 行 | **41**；**21** 条 `pool=tradable` 且 params 含 **`fix: D24-1`** |
| 最终版 | B0 | gate 复算仍 **无** T1–T4 过关 |

---

## 5) ChiNext 联接 defer（Orchestrator）

Dev 未插入 050021 / 110026 / 161022。Reviewer 确认 **`v4_listing` 中不存在** 上述代码 → **U-指数 net 序列未因 defer 被动改变**（见 §4 二十条 hash 不变）。**政策裁定留给 Orchestrator**（是否接受 U-指数研究序列变化），Reviewer 不表态。

---

## Blockers / Follow-ups

| 类型 | 项 | 负责人 |
| --- | --- | --- |
| Follow-up | 重跑 `build_data_board.py`，更新 `summary.json` 的 `db_sha256` 与 buy 图 | Manager（plan §5） |
| Follow-up | ChiNext 第 2 档联接与 U-指数研究序列是否纳入 | Orchestrator |
| Follow-up | 050002 pingzhong vs lsjz 日收益差（预存基金） | 数据登记说明（非 D24 blocker） |

## 边界确认

- 仅设计期 ≤2015-12-31；**未**跑一次性检验、**未**写 LOCK、**未**汇总 2016+ 组合收益。
- **未**移动 tag；**未** merge main；**未**改预注册正文。
