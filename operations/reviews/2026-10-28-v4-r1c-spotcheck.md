# v4-R1c · 取数 spot-check · 2026-10-28

## Decision：`approve_with_follow_up`

在 Dev PR [#82](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/82) 尖端 `a348365f50eab51875f2bf8d36a50a77fa64f4d3`（base `63f41fa3`）上独立复核：写入后 `market.sqlite` SHA、`PRAGMA integrity_check`、`bars` 行数、124 只 `eastmoney_fhsp` 后复权 3×5、相近替身、310318 对照均与 Dev 一致。完整性清单 **2389** 行在 Dev 交付中 `manager_class` 留空（符合 D15-9）；Manager 事后分类 **must_fix 12 / accept 2362 / needs_Orchestrator 15**（分类 CSV PR 尚未开，Reviewer **未**写入 CSV）。独立样本 **10/10 true positive**，其中 **7/7 must_fix 符号** Dev 均在 `integrity-findings.csv` 中以正确 `check` 类型 surfaced — **非 Dev 漏报**。Decision 不因 must_fix 数据项改判 Dev 缺陷（属修数 / Orchestrator 口径）。Follow-up：Orchestrator 队列与 Dev 工作日志 v4 测试条数表述。

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

## 5. 完整性清单 · Manager D15-9 分类 + 独立样本 10

Dev 交付 `integrity-findings.csv`：**2389** 行，`manager_class` **空白**（Reviewer **未**填写）。

Manager 分类（#82 @ `a348365`，分类 CSV PR 待开；Reviewer 引用 Manager 口头/板计数，**不**写入仓库 CSV）：

| manager_class | 行数 |
| --- | ---: |
| must_fix | 12 |
| accept | 2362 |
| needs_Orchestrator | 15 |
| **合计** | **2389** |

**must_fix 符号（Manager 优先）**：159922、159952、160125、161831、164705、588050、588080（另 5 行在同符号/检查的其他 series 行上凑满 12 行）。

**Dev #82 是否正确 surface must_fix？** 对下表 7 个 must_fix 抽样行：均在 CSV 中有对应 `check` 行，且 DB 复查均为 **true positive** → **是**（清单职责完成；修数不在 R1c Dev 范围）。

**Orchestrator（非 Dev 缺陷，除非 inventory 漏报）**：931160 / HSTECH 缺失日补齐规则；161229 止于 2026-09-29；载体候选 `list_date_unknown`（510300、510500、510880、512100、515180 等）；`large_move` 场景下 factor=1 是否足够。

**accept（现阶段接受）**：bulk `missing_trade_days`、`large_move_hfq_smoothed`、非载体 `list_date_unknown`、XLE 2020-03-09 等。

### 独立样本 10（优先 must_fix 7 + 对照 3）

| # | 代码 | check | 日期 | Manager 分类 | Dev CSV 行 | DB 复查 | Dev surface OK |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 159922 | adj_discontinuous | 2024-12-02 | must_fix | ✓ backward | raw Δ=-61.5%，bw Δ=+1.6% **TP** | **是** |
| 2 | 159952 | large_move | 2024-10-08 | must_fix | ✓ raw + ✓ fhsp backward 双行 | raw Δ=+20.03% **TP** | **是** |
| 3 | 160125 | ended_before_cutoff | 2019-07-03 | must_fix | ✓ tencent hfq | bw 止于 2019-07-03，raw 至 2026-09-30 **TP** | **是** |
| 4 | 161831 | ended_before_cutoff | 2020-12-31 | must_fix | ✓ | bw 止于 2020-12-31 **TP** | **是** |
| 5 | 164705 | ended_before_cutoff | 2020-11-30 | must_fix | ✓ | bw 止于 2020-11-30 **TP** | **是** |
| 6 | 588050 | large_move | 2024-10-08 | must_fix | ✓ raw + ✓ hfq backward | raw Δ≈+20.02% **TP**（涨停缩放待 Orchestrator 验证） | **是** |
| 7 | 588080 | large_move | 2024-10-08 | must_fix | ✓ raw + ✓ hfq backward | raw Δ≈+20.02% **TP** | **是** |
| 8 | 931160 | missing_trade_days | 2019-01-02 | needs_Orchestrator | ✓ | 无正收盘 **TP** | **是** |
| 9 | 159327 | large_move_hfq_smoothed | 2026-07-20 | accept | ✓ | raw \|Δ\|>20%，bw 平滑 **TP** | **是** |
| 10 | XLE | large_move | 2020-03-09 | accept | ✓ | raw Δ=-20.14% **TP** | **是** |

**10/10 true positive**；**must_fix 子集 Dev inventory 7/7 正确 surface**。

清单 `check` 计数仍与 Dev 一致：missing_trade_days 2268；list_date_unknown 67；large_move_hfq_smoothed 38；large_move 10；ended_before_cutoff 5；adj_discontinuous 1。

## 6. 范围

- PR diff：**无** `results/v3/LOCK`、**无** tag/milestone 移动
- 新增产物为 R1c 清单、spot-check CSV、310318 对照；**无**组合收益或 IC
- CLI `r1c` 路径仍拒绝 returns/backtest/pnl（v4 测试覆盖）

## Dev 缺陷 vs Manager/Orchestrator follow-up

| 类型 | 项 | 说明 |
| --- | --- | --- |
| **Dev 缺陷** | （本 spot-check 未发现阻塞项） | R1c 清单与 must_fix 抽样 **无漏报/误报** |
| **must_fix（Manager，非 Dev 缺陷）** | 12 行 / 7 符号 | 159922 adj；160125/161831/164705 hfq 早停；159952/588050/588080 涨跌停缩放 — Dev 已 **flag**；修数后续 round |
| **needs_Orchestrator（15）** | 931160、HSTECH、161229、载体 list_date_unknown、factor=1 vs large_move 等 | 口径与池规则；**非** #82 inventory 错误 |
| **accept（2362）** | 缺失交易日 bulk、hfq-smoothed、非载体 list_date_unknown、XLE 等 | Manager 现阶段接受 |
| **Follow-up（文档）** | 工作日志 v4 测试 **45** vs discover **52** | 不阻塞 #82 |
| **Reviewer 纪律** | `manager_class` 空白 | **未**填写；待 Manager CSV PR |

## 诊断 artifact

| 产物 | 路径 |
| --- | --- |
| JSON | `operations/reviews/diag/v4/2026-10-28-v4-r1c-spotcheck.json` |

## Review PR

- Review 签收 PR：https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/83
- Dev 取数 PR：https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/82
