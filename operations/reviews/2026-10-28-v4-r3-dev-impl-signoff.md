# v4-R3 · Dev 打分卡实现签收 · 2026-10-28

## Decision：`approve`

在 Dev PR [#63](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/63) 尖端 `15e305911880b5042edbaabfa7f5329c8dbb1fd1`（`cursor/v4-r3-scorecard-48e9`）上独立复跑验收命令与全量单测；`python -m src.v4.scorecard reference` 12 项 acceptance 与 [#60](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/60) / Owner 看板参考数一致；`--end 2016-01-01` 在打开 DB 前拒绝；改动面仅 v4 打分卡与测试，无 v4 候选组合 PnL、无 2016+ 组合落盘、无 LOCK / tag / main 合入 / 冻结 tip 改写。**不**因 D13-2 尚未预注册的「牛市/反弹超额不为负」而否决（P1 反弹 **−56.7** 与登记脚本一致，属预期）。

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R3 Dev 实现签收（阶段 ⑤ 打分卡 tooling）
- Date: 2026-10-28 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（本 PR 仅 `operations/reviews/**`）
- 签收对象（Dev）: PR #63 · base `18395878a4185055ea99191ba20e664f5099f9ad` → head `15e305911880b5042edbaabfa7f5329c8dbb1fd1`
- 先验数字门（main，不重审正文）: `operations/reviews/2026-10-28-v4-r3-scorecard-recompute.md` · Decision `numbers_ok_with_notes`
- P1 只读: `results/v3/design-period/9b421c0294a8509e5283aa871034ff0e8ed66c75/P1/`
- 数据段: 2006-01-05 → 2015-12-31（2428 交易日）

## A. 运行命令与日志

环境：`git lfs pull`（`data/market.sqlite`）；仓库根 `.venv`（`requirements.txt`）；`mkdir -p outputs`。

| 步骤 | 命令 | 日志 |
| --- | --- | --- |
| 参考验收 | `.venv/bin/python -m src.v4.scorecard reference` | `/opt/cursor/artifacts/v4-r3-dev-scorecard-reference.log` |
| 结束日拒绝 | 同上模块 `score … --end 2016-01-01`（P1 paths/held） | `/opt/cursor/artifacts/v4-r3-dev-score-end-reject.log`（**exit=2**） |
| v4 单测 | `.venv/bin/python -m unittest tests.v4.test_scorecard -v` | `/opt/cursor/artifacts/v4-r3-dev-test-scorecard.log` |
| 全量单测 | `.venv/bin/python -m unittest discover -s tests -t .` | `/opt/cursor/artifacts/v4-r3-dev-unittest-discover.log` |
| 独立脚本（交叉） | `.venv/bin/python results/v3/diag/2026-10-27-owner-board/reviewer_r3_scorecard.py` | `/opt/cursor/artifacts/v4-r3-reviewer-independent-rerun.log` |

签收时在 detached `15e3059` 上执行上述命令；本 review 分支基于 `origin/main` 仅追加本文档。

## B. 验收数字（`reference` · 与 #60 一致）

### B1 · 任意起点 5 年（E2 vs 对照）

| 指标 | 看板 / #60 | Dev `reference` |
| --- | --- | --- |
| 跑赢 **策略基准** | 63% | **63%** |
| 跑赢 **纳指100** | 32% | **32%** |

### B2 · 四市场状态（1 位小数；看板整数 = 再四舍五入）

| 状态 | 看板整数 | `excess_pp` |
| --- | --- | --- |
| 牛市 | +1 | **+0.6** |
| 回调 | +30 | **+29.9** |
| 熊市 | +95 | **+94.9** |
| 反弹 | −57 | **−56.7** |

### B3 · 跟涨 / 跟跌

| 指标 | 期望 | Dev |
| --- | --- | --- |
| 跟涨 | 0.86 | **0.86**（74 月） |
| 跟跌 | 0.52 | **0.52**（46 月） |

CLI 打印 12 条 `ok` acceptance checks；进程 **exit 0**。

## C. 门禁与范围

| 检查 | 结果 |
| --- | --- |
| `--end 2016-01-01` 拒绝 2015 之后组合 PnL | stderr 文案 + **exit 2**；单测 `test_refuses_an_end_date_after_2015` / `test_refuses_2016_returns_before_opening_the_database` 通过 |
| 全量 unittest | **476** ran，**0** failures，**1** skipped（`OK`） |
| PR diff 文件 | `src/v4/scorecard/**`、`tests/v4/test_scorecard.py`、`operations/work_logs/2026-10-28-v4-r3-scorecard.md`（7 files, +819） |
| v4 候选组合 / 2016+ 组合 PnL 落盘 | diff 内无；`core.py` 仅设计期常量与 `assert_design_end` |
| LOCK / tag / main / trial-ledger | 本签收 PR 未触碰；Dev PR 范围未含上述路径 |
| D13-2 反弹超额为负 | **备注**：预注册后置；不以 P1 −56.7 否决 #63 |

### C1 · 测试与 Reviewer 独立函数

`tests/v4/test_scorecard.py::P1Reference` 动态加载 `reviewer_r3_scorecard.py`，对 `anystart_independent` / `states_independent` 与 `reference_scorecard` 输出做 `assertAlmostEqual`（胜率 9 位小数；状态超额与 capture 相等）。Reviewer 脚本复跑 `decision_gates_ok: true`，`cross_check.anystart_matches_diag` / `states_excess_matches_diag` 均为 true。

### C2 · Notes（非否决）

1. **四态整数展示**：与 #60 相同——存 1 位小数，看板整数为展示舍入；`acceptance` 同时校验两者。
2. **`states.py` 登记脚本**：pandas 3.x 下 `mon.select` 与列名冲突已知；打分卡读 P1 CSV，不依赖 patch 后的 `states.py` stdout。
3. **测试侧加载 Reviewer 脚本**时可能写入 diag 目录临时 `*.pkl` 并触发 `ResourceWarning`（Reviewer 脚本内 `open` 未 context-manage）；测试 `finally` 会 unlink，不影响数字结论。

## D. Reviewer 纪律

- 未合并 main、未创建/移动/删除 tag、未写 `results/v3/LOCK`、未编辑 `trial-ledger.csv` / `market.sqlite`。
- 未将 Dev PR 数字当作先验真值；验收以 `reference` CLI + 全量单测 + 既有 `reviewer_r3_scorecard.py` 交叉为准。

## E. 建议后续（非本 Decision 阻塞项）

- Owner / Orchestrator：在 #63 合入 main 后按路线图继续 v4 后续轮次；D13-2 正式预注册时再定义「牛市/反弹超额不为负」的通过规则。
- Dev（可选 hygiene）：若希望 CI 无 ResourceWarning，可在 **登记** `reviewer_r3_scorecard.py` 另开极小 PR 用 context manager 写 pickle（非 #63 范围）。
