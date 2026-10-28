# v4-R3 · Owner 看板 scorecard 参考数独立复算 · 2026-10-28

## Decision：`numbers_ok_with_notes`

Acceptance 门禁（任意起点 5 年、四态超额整数、跟涨/跟跌）与 `anystart.py` / `states.py` 在 **1 位小数** 下的输出一致；看板整数（如牛市 **+1**）为对 `states.py` 打印值四舍五入后的展示（脚本实际 **+0.6**）。独立实现与登记脚本交叉核对通过。备注见 §C。

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R3（D13 / scorecard tooling acceptance 参考数）
- Date: 2026-10-28 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（`operations/reviews/**` + diag 复核脚本；未改业务代码、未写 LOCK、未动 tag / `trial-ledger.csv` / `market.sqlite` 内容）
- P1 来源（只读）: `results/v3/design-period/9b421c0294a8509e5283aa871034ff0e8ed66c75/P1/`
- 登记脚本: `results/v3/diag/2026-10-27-owner-board/`（`anystart.py`、`states.py`、`lab2.py` 逻辑）
- 独立复核: `results/v3/diag/2026-10-27-owner-board/reviewer_r3_scorecard.py`
- 数据段: 2006-01-05 → 2015-12-31（无 2016+ 组合 PnL）

## A. 运行命令与产物

```bash
git lfs pull   # data/market.sqlite
cd /workspace
/workspace/.venv/bin/python results/v3/diag/2026-10-27-owner-board/reviewer_r3_scorecard.py
```

| 产物 | 路径 |
| --- | --- |
| LFS 拉取 | `/opt/cursor/artifacts/v4-r3-git-lfs-pull.log` |
| 复核脚本完整 JSON | `/opt/cursor/artifacts/v4-r3-reviewer-script.log`（同内容写入 `results/v3/diag/2026-10-27-owner-board/reviewer_r3_scorecard.json`，运行后本地生成） |
| 登记 `anystart.py` 胜率 | `/opt/cursor/artifacts/v4-r3-anystart-diag.log` |
| 登记 `states.py` 表（DB 路径 sed 为仓库根） | `/opt/cursor/artifacts/v4-r3-states-diag.log` |

`data/market.sqlite` SHA256（LFS 实体）: `3e3e6f1d594586da2abf28db5fa88b05c1cc91fa29adf061fc699e1b8d4bc1d6`

## B. 期望 vs 复算（Decision 门禁）

### B1 · 任意起点（持有 **5** 年，E2=P1 executed vs 对照）

| 指标 | 看板 / 计划期望 | 独立复算 | 登记 `anystart.py` |
| --- | --- | --- | --- |
| 跑赢 **策略基准**（BM-主） | 63% | **63%** | 63% |
| 跑赢 **纳指100**（人民币全收益） | 32% | **32%** | 32% |

### B2 · 四市场状态（H00300：过去 12m + 当月 → 牛/回调/熊/反弹；超额 = 日超额按月 **相加**，百分点）

| 状态 | 看板整数 | 独立 + `states.py`（1 位小数） |
| --- | --- | --- |
| 牛市 | +1 | **+0.6** |
| 回调 | +30 | **+29.9** |
| 熊市 | +95 | **+94.9** |
| 反弹 | −57 | **−56.7** |

### B3 · 跟涨 / 跟跌（相对 **基准** 月度收益）

| 指标 | 期望 | 复算 |
| --- | --- | --- |
| 跟涨 | 0.86 | **0.86** |
| 跟跌 | 0.52 | **0.52** |

## C. Notes（`numbers_ok_with_notes`）

1. **四态超额整数**：Orchestrator 看板/work_log 用整数百分点（`operations/work_logs/2026-10-27-orchestrator-market-state-and-pool.md`）；`states.py` 对 `100×Σ日超额` 用 `.round(1)` 打印。当前数据下整数 = 对脚本值四舍五入（0.6→1，29.9→30，94.9→95，−56.7→−57），**不是**第二套算法。Scorecard 应用同一来源时建议存 1 位小数或注明展示舍入。
2. **`states.py` DB 路径**：硬编码 `/home/claude/etf_rotation_quant/...`；Reviewer 用 `sed` 替换为仓库根再跑 stdout 解析（不改变仓库内登记脚本）。
3. **双重路径**：`reviewer_r3_scorecard.py` 内联 `lab2` 面板 + `bm_main`、从 P1 CSV 读 executed/cash，独立算任意起点与四态；并与 `anystart.pkl` / patched `states.py` 交叉，`cross_check.anystart_matches_diag` 与 `states_excess_matches_diag` 均为 true。

## D. 附表 · 任意起点 1/2/3/5 年跑赢占比（%，E2 vs 对照）

与 `operations/work_logs/2026-10-27-orchestrator-v4-research-diagnostics.md` §1 一致。

| 持有期 | 基准 | 沪深300 | 标普500 | 纳指100 |
| --- | --- | --- | --- | --- |
| 1 年 | 63 | 56 | 49 | 44 |
| 2 年 | 62 | 81 | 48 | 45 |
| 3 年 | 64 | 83 | 51 | 43 |
| 5 年 | 63 | 93 | 50 | 32 |

## E. Reviewer 纪律

- 未合并 main、未创建/移动/删除 tag、未写 `results/v3/LOCK`、未编辑 `trial-ledger.csv`。
- 未运行 v4 候选组合规则；未计算 2016-01-01+ 组合 PnL。
- 未将 Dev 未来 v4-R3 PR 作为真值；复算仅依赖登记 P1 产物 + `market.sqlite` + 看板 diag 脚本逻辑。
