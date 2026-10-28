# v4-R1c · 取数 spot-check · 2026-10-28

## Decision：`approve_with_follow_up`

在 Dev PR [#82](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/82) 尖端 `a348365f50eab51875f2bf8d36a50a77fa64f4d3`（base `63f41fa3`）上独立复核：写入后 `market.sqlite` SHA、`PRAGMA integrity_check`、`bars` 行数、124 只 `eastmoney_fhsp` 后复权 3×5 抽查、相近替身登记、310318 2008 日增长率对照、完整性清单 10 条样本复查均与 Dev 叙述一致。**不**将 `integrity-findings.csv` 中空白的 `manager_class` 记为 Dev 缺陷（D15-9 / Manager 分类）。Follow-up 见文末（既有腾讯后复权截断、159922 事件连续性、工作日志 v4 测试条数表述）。

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R1c 取数 spot-check（D15 · ② 标的池）
- Date: 2026-10-28 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（本 PR 仅 `operations/reviews/**`）
- 签收对象（Dev）: PR #82 · head `a348365f50eab51875f2bf8d36a50a77fa64f4d3`
- Dev work log: `operations/work_logs/2026-10-28-v4-r1c-ingest.md`
- D15: `operations/planning/2026-10-28-d15-decisions.md`（D15-2/3/5/8/9）
- 载体表: `operations/work_logs/2026-10-28-v4-r1c-vehicle-table.md`（main via #79）
- Review branch: `review/v4-r1c-spotcheck-d775`（基于 Dev tip，仅追加评审产物）

## 证据总表

| 检查项 | 方法 | 结论 |
| --- | --- | --- |
| 库文件 SHA | `git lfs pull` + `sha256sum data/market.sqlite` | **43bf125532da01fb6f0056db77f2ab05b3da3f0bdc5f32fa33502bafffd922fc**（245170176 B）与 Dev **一致** |
| 写入前 SHA（R1b） | 工作日志登记 | `af4c5a376d…045b78`（Reviewer 未重拉旧库；仅核对 PR 为增量写入） |
| `PRAGMA integrity_check` | 只读 URI 打开 PR 库 | **ok** |
| `bars` 行数 | `SELECT COUNT(*) FROM bars` | **787005**（与 Dev / R1b 一致） |
| `-wal` / `-shm` | 文件系统 | **无**（LFS 单文件） |
| v4 单测 | `unittest discover -s tests/v4` | **52** OK |
| v3 单测 | `unittest discover -s tests/v3` | **136** OK |
| 组合 PnL / 2016+ 收益汇总 | 硬规则 + PR diff | **未**运行；清单仅含允许的单日 `move=` 字段 |
| LOCK / tag / 合 main | PR diff | **无** LOCK；**无** tag 移动；Reviewer **未**合 main |

## 1. Sqlite / registry 卫生

Reviewer 在 Dev tip 执行 `git lfs pull -I data/market.sqlite` 后打开库文件。

- `integrity_check`: **ok**
- Post-write SHA256: **43bf1255…d922fc**（match Dev claim: **yes**）
- `bars`: **787005**
- 新后复权：`v4_series` 中 `source=eastmoney_fhsp` **124** 代码、**171520** 行；与 `source=tencent_etf_hfq` 的代码集合 **交集 0**（未覆盖既有腾讯后复权）
- 抽查 510300：仅 `tencent_etf_hfq` **3488** 行 backward（pre-existing 未覆盖）

## 2. 新 adj / hfq · 3 序列 × 5 检查

载体优先三只：`159940`、`159944`（Dev 优先补全），另加重试写入样本 `159892`。

| 代码 | (a) source/method | (b) raw=adj | (c) 未覆盖旧 backward | (d) 起止覆盖 | (e) 无公司行为/连续 | 得分 |
| --- | --- | --- | --- | --- | --- | --- |
| 159940 | `eastmoney_fhsp` / `no_corporate_action_factor_1` | 2785 行收盘差 **0**；例 2015-04-17 raw=adj=1.012；2026-09-30 =1.22 | 仅 fhsp 一源 | 2015-04-17 → 2026-09-30 | `v4_corp_action` **0** 行 | 5/5 |
| 159944 | 同上 | 2708 行差 **0**；例 2015-07-06 =0.784；2015-12-02 =0.879 | 仅 fhsp | 2015-07-06 → 2026-09-30 | corp **0** | 5/5 |
| 159892 | 同上 | 1204 行差 **0**；例 2021-10-19 =1.001；2022-03-16 =0.532 | 仅 fhsp | 2021-10-19 → 2026-09-30 | corp **0** | 5/5 |

**合计：15/15。**

方法：对每只代码 SQL 联查 `bars.close>0` 与 `v4_series.kind=backward AND source=eastmoney_fhsp`，逐日 `abs(raw-adj)<1e-9`；读 `method`/`source` 元数据；查 `v4_corp_action`。

## 3. 相近替身（D15-2 / D15-3）

- DB `v4_near_sub`：**2** 行 — `161211` → 容器 `allshare-financials-re`、相近指数 `H00992`；`510880` → `csi-dividend`、`H00922`
- 与 `results/v4/inventory/near-substitute.csv` 及载体表 D15-2/3 **一致**
- 载体表拒绝项 **未**写入 `v4_near_sub`（Reviewer 仅见上述 2 条）

## 4. 310318（D15-8）

- `v4_carrier_block`: `310318` / `enhanced_never_carrier` ✓
- `results/v4/inventory/r1c-310318-crosscheck.csv`：**246** 重叠日；`max(abs(diff))=5e-7`；**0** 天 >5bp
- Reviewer **未**重拉新浪 API；独立复算 CSV 统计与 Dev 一致。增强型不作载体结论 **成立**。

## 5. 完整性清单 · 独立样本 10 条

自 `integrity-findings.csv`（**2389** 行）按 Dev 报告类别抽样，**不**填 `manager_class`，**不**据此改池。

| # | 代码 | check | 日期 | 复查方法 | 结论 |
| --- | --- | --- | --- | --- | --- |
| 1 | 931160 | missing_trade_days | 2019-01-02 | `v4_series` 无该日 raw 行 | **true positive** |
| 2 | 159303 | missing_trade_days | 2025-08-19 | `bars` 无行 | **true positive** |
| 3 | 510300 | list_date_unknown | 2012-05-28 | `MIN(date)` 正收盘 = 2012-05-28 | **true positive** |
| 4 | 159327 | large_move_hfq_smoothed | 2026-07-20 | raw Δ=-68.6%，backward Δ=-5.7% | **true positive** |
| 5 | 159952 | large_move | 2024-10-08 | raw Δ=+20.03% | **true positive** |
| 6 | 161229 | ended_before_cutoff | 2026-09-29 | raw 最后正收盘 2026-09-29 | **true positive** |
| 7 | 160125 | ended_before_cutoff | 2019-07-03 | backward 止于 2019-07-03，raw 至 2026-09-30 | **true positive** |
| 8 | 159922 | adj_discontinuous | 2024-12-02 | raw Δ=-61.5%，backward Δ=+1.6% | **true positive** |
| 9 | HSTECH | missing_trade_days | 2020-10-13 | 研究序列无该日 | **true positive** |
| 10 | 159516 | large_move_hfq_smoothed | 2026-03-30 | raw Δ=-48.7%，backward Δ=+2.7% | **true positive** |

**10/10 true positive**（0 false positive，0 inconclusive）。

清单计数与 Dev 一致：missing_trade_days 2268；list_date_unknown 67；large_move_hfq_smoothed 38；large_move 10；ended_before_cutoff 5；adj_discontinuous 1。

## 6. 范围

- PR diff：**无** `results/v3/LOCK`、**无** tag/milestone 移动
- 新增产物为 R1c 清单、spot-check CSV、310318 对照；**无**组合收益或 IC
- CLI `r1c` 路径仍拒绝 returns/backtest/pnl（v4 测试覆盖）

## Dev 缺陷 vs Manager/Orchestrator follow-up

| 类型 | 项 | 说明 |
| --- | --- | --- |
| **Dev 缺陷** | （本 spot-check 未发现阻塞项） | — |
| **Follow-up（非 Dev）** | `manager_class` 空白 | D15-9：Manager 分类；非本 PR 缺陷 |
| **Follow-up（非 Dev）** | 160125/161831/164705 腾讯后复权早于 cutoff 结束 | 清单已标记；需 Orchestrator/数据策略，非 R1c 写入逻辑错误 |
| **Follow-up（非 Dev）** | 159922 @ 2024-12-02 后复权不连续 | 清单已标记；事件/数据源口径待 Manager |
| **Follow-up（文档）** | 工作日志写 v4 测试 **45**，Reviewer `discover -s tests/v4` 得 **52**；`tests/v4/data/test_r1c.py` alone **12** | 建议 Dev 更新验证节表述，**不**阻塞合并 |

## 诊断 artifact

| 产物 | 路径 |
| --- | --- |
| JSON | `operations/reviews/diag/v4/2026-10-28-v4-r1c-spotcheck.json` |

## Review PR

- Review 签收 PR：（本 PR，创建后补 URL）
- Dev 取数 PR：https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/82
