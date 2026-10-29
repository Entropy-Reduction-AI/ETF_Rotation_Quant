# v4-R1f · 附表 A 公开同行 A1/A2 · 签收 · 2026-10-29

## Decision：`approve`

在 Dev PR [#113](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/113) 尖端 `c9ce424b41de33fd0caed4c51446acb010998496`（base main `3e44c48a9c45206d834363d392ef4fdfe70653ed`）上，Reviewer **独立手造序列复算** A1/A2 持仓与费用，并复跑 `tests/v4/test_peers.py` 与 `tests/v4/test_conclusion_template.py`。**未发现阻塞项。** Manager 应先合入 **#113**，再合入本 Review PR。

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R1f 附表 A 独立运行 + §7.5 结论报告空表
- Date: 2026-10-29 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（Review PR 仅追加本文件与 diag）
- Dev: PR #113 · branch `cursor/v4-r1f-peers-a1a2-c226` · head `c9ce424…`
- Work log（Dev）: `operations/work_logs/2026-10-29-v4-r1f-peers-a1a2.md`
- 范围: `git diff 3e44c48…c9ce424`（三点）— **12 文件、+1376 行**；仅 peers、结论模板、work log；无 `data/`、无 LOCK、无 prereg 改动

## A. 复跑命令（Reviewer 独立）

环境：仓库根 `.venv`；`mkdir -p outputs`。

| 步骤 | 命令 | 结果 |
| --- | --- | --- |
| 附表 A + 模板 | `.venv/bin/python -m unittest tests.v4.test_peers tests.v4.test_conclusion_template` | **17** 项 **OK**（0 fail） |
| 手造复算 | `.venv/bin/python operations/reviews/diag/v4/2026-10-29-v4-r1f-peers-recompute.py` | exit **0**；JSON 见下 |

日志：`/opt/cursor/artifacts/v4-r1f-reviewer-unittest.log`、`/opt/cursor/artifacts/v4-r1f-reviewer-recompute.log`

独立 JSON：`operations/reviews/diag/v4/2026-10-29-v4-r1f-peers-recompute.json`

## B. Owner brief 核对

| # | 项 | 独立方法 | 结果 |
| --- | --- | --- | --- |
| 1 | A1 双动量 / A2 十个月均线，四条独立运行 | `load_runs()`；`load_peer("A1"\|"A2", "index"\|"tradable")` | 四条顺序与池一致；规则 `dual-momentum` / `ten-month-ma` |
| 2 | 交易条件、费用、现金同 v4；无离场/溢价/T1–T4 | `config/v4/peers.toml` + `test_four_runs_share_v4_costs…`；AST 禁止 import exit/premium/sqlite | 六开关均 false；费率与 `arms.toml` Spec 一致；现金 2%/252 |
| 3 | 手造复算：信号/持仓连续、费用、涨停顺延、大跌不强制离场 | `2026-10-29-v4-r1f-peers-recompute.py`（非仅读 Dev 测试） | 见 §C |
| 4 | §7.5 空模板六节「待填」、无填好的收益 | `assets/templates/v4-conclusion-report.md` + `test_conclusion_template` | 六节标题齐全；**46** 处「待填」；无 `market.sqlite` / 无示例年化 |
| 5 | SF-6：月末 = 各自然月上交所最后交易日，与 `decision_dates(..., "month")` 一致 | `month_end_sessions` vs `decision_dates`（`calendar_closed=True`） | **一致**（见 JSON `sf6_alignment`） |
| 6 | 无真实 PnL；2016+ 拒绝；无 ledger；无 prereg 改 | `test_refuses_dates_after_the_design_window`；diff 范围 | `2016-01-04` → `RunnerError`；范围遵守 |

## C. 独立手造复算摘要（Reviewer）

复算脚本自建 `_calendar` / `_levels`，调用 `run_peer`，并用 `leg_cost` 交叉验证成交日费用。

### C1 · SF-6 与决策日

| 模式 | 2006 样例月末日 |
| --- | --- |
| 开放日历（默认） | 2006-01-31、2006-02-01、2006-04-28 |
| `calendar_closed=True` | 同上 + 2006-05-08 |
| `decision_dates(..., "month")` | 与 closed **相同** |

签收时 `SF6_STATUS` / `peers.toml` 标签仍为 **`pending-manager`**（Dev 确认中 patch 可能未 push）；**Manager 已确认定义，不阻塞本签收**（见 §D）。

### C2 · A1 关键日 `close_held`

| 场景 | 日 | spx | cgb-10y | cash | cost | 核对 |
| --- | --- | --- | --- | --- | --- | --- |
| 12 月后全仓国债 | 2006-02-10（成交） | 0 | **1.0** | 0 | **0.001** | = `leg_cost` 全仓换入国债 |
| 月中 −46% 不离场 | 2006-02-15 | **1.0** | — | — | **0** | signal 仍 spx=1；net ≈ −0.4615 |
| 涨停顺延买 csi300 | 2006-02-10 | — | — | **1.0** | 0 | 2006-02-15 csi300=**1.0**，cost=0.001 |

### C3 · A2 关键日 `close_held`

| 日 | spx | hsi | gold | cash | 说明 |
| --- | --- | --- | --- | --- | --- |
| 2005-11-10（成交） | 0.2 | 0.2 | 0.2 | 0.4 | 三 sleeve 入仓；cost=**0.0008** = `leg_cost` |
| 2006-01-20（决策） | **0.059**（漂移） | 0.2 | 0.2 | 余 | signal 已 spx=0，尚未减仓 |
| 2006-02-10（成交） | **0** | 0.2 | 0.2 | 余 | 跌破均线后下一 SESSION 才减 |

## D. Follow-up（非否决）

| 项 | 说明 |
| --- | --- |
| **`sf6` 标签** | 签收 head `c9ce424` 上 `config/v4/peers.toml` 与 `SF6_STATUS` 仍为 `pending-manager`。Manager 已确认 SF-6 定义；Dev 将改为 `confirmed` 时 Reviewer 不要求重签，合入前改标签即可。 |
| 真实序列 | 本签收仅手造路径；U-指数/U-可交易 **真实** 序列跑数另任务，不在 R1f 范围。 |

## E. Reviewer 纪律

未 merge #113、未 merge main、未移动 tag、未改 prereg、未写 LOCK、未算 v4 候选或 2016+ 组合 PnL、未改 Dev 业务代码（本 PR 仅 review 文档与 diag）。

## F. 合入顺序

1. Dev **#113**
2. 本 Review PR（`operations/reviews/2026-10-29-v4-r1f-peers-a1a2-signoff.md` + diag）

---

本人，ETF Rotation Reviewer，于 2026-10-29 对 Dev PR #113 @ `c9ce424b41de33fd0caed4c51446acb010998496` 签收：**`approve`**。
