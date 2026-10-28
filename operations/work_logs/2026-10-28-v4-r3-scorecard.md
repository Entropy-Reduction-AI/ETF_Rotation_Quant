# v4-R3 打分卡

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R3 打分卡（阶段 ⑤）
- Date: 2026-10-28
- Owner: project owner
- Route: direct-execute
- Source of truth: D13-2；`operations/planning/2026-10-28-v4-dev-plan.md`；`docs/research/2026-10-27-v4-research-memo.md` §2–§3；Reviewer `operations/reviews/2026-10-28-v4-r3-scorecard-recompute.md`（`numbers_ok_with_notes`）
- 基线: `origin/main` `18395878a4185055ea99191ba20e664f5099f9ad`（v3.1 closeout #61）。Reviewer 独立脚本在其祖先 `994839a`

## Goal / Summary

把任意起点和四种市场状态做成可复用的打分卡。验收用 v3.1 设计期 P1（正式引擎 E2），数字与登记脚本 `anystart.py` / `states.py` 以及已合入 main 的 `reviewer_r3_scorecard.py` 对齐。

状态超额以脚本打印的 **1 位小数** 为准。任务里的看板整数（牛市 +1、回调 +30、熊市 +95、反弹 −57）是对这些打印值再四舍五入，不是另一套算法。Reviewer 的结论是 `numbers_ok_with_notes`。

没有跑任何 v4 候选组合。没有计算 2016-01-01 及以后的组合收益。没有写 `results/v3/LOCK`，没有改 `trial-ledger.csv`，没有新建、移动或删除 tag，没有合并 main。

## Scope / Changes

- `src/v4/scorecard/`：任意起点、四种状态、跟涨/跟跌，以及 `python -m src.v4.scorecard reference|score`。
- `tests/v4/test_scorecard.py`：合成序列测规则；P1 锁住参考数，并调用 Reviewer 的 `anystart_independent` / `states_independent` 做交叉核对。
- 公式来自 `results/v3/diag/2026-10-27-owner-board/anystart.py`、`states.py`、`lab2.py` 和 `reviewer_r3_scorecard.py`。现金日收益用这些脚本里的 `0.02/252`，不用 511880 全收益。美股点位用 lab2 的「日期 +1 天再乘美元兑人民币」，查询停在评价结束日。

`reference` 只读 `results/v3/design-period/9b421c0294a8509e5283aa871034ff0e8ed66c75/P1/` 的 `paths.csv` 与 `held.csv`。`score` 接受另一份设计期文件，结束日晚于 2015-12-31 或文件里已有更晚的收益时直接拒绝。

## 复现数字

命令：`.venv/bin/python -m src.v4.scorecard reference`

窗口：2006-01-05 → 2015-12-31，2428 个交易日。验收 12 项全部通过。

### 任意起点

跑赢占比是四舍五入后的整数（`.5` 向偶数，与 Reviewer 的 `pct` 相同）。中位差和最差是年化超额的百分点。

| 持有 | 对照 | 起点数 | 跑赢% | 中位差 | 最差 | 最差起点 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 年 | 基准 | 108 | 63 | +4.6 | −43.0 | 2008-11-03 |
| 1 年 | 沪深300 | 108 | 56 | +3.8 | −72.1 | 2008-11-03 |
| 1 年 | 标普500 | 108 | 49 | −3.0 | −27.4 | 2010-07-01 |
| 1 年 | 纳指100 | 108 | 44 | −4.6 | −34.3 | 2010-02-01 |
| 2 年 | 基准 | 96 | 62 | +2.0 | −18.6 | 2008-11-03 |
| 2 年 | 沪深300 | 96 | 81 | +6.0 | −25.0 | 2008-11-03 |
| 2 年 | 标普500 | 96 | 48 | −0.8 | −20.1 | 2009-03-02 |
| 2 年 | 纳指100 | 96 | 45 | −7.9 | −28.8 | 2009-03-02 |
| 3 年 | 基准 | 84 | 64 | +1.4 | −11.0 | 2008-11-03 |
| 3 年 | 沪深300 | 84 | 83 | +7.5 | −11.9 | 2008-11-03 |
| 3 年 | 标普500 | 84 | 51 | +1.4 | −17.6 | 2010-07-01 |
| 3 年 | 纳指100 | 84 | 43 | −5.7 | −23.9 | 2009-04-01 |
| 5 年 | 基准 | 60 | **63** | +4.1 | −6.6 | 2008-11-03 |
| 5 年 | 沪深300 | 60 | 93 | +8.5 | −3.7 | 2008-11-03 |
| 5 年 | 标普500 | 60 | 50 | −0.4 | −14.7 | 2009-04-01 |
| 5 年 | 纳指100 | 60 | **32** | −4.8 | −19.8 | 2009-03-02 |

5 年对基准 63%、对纳指100 32%，与任务目标和 Reviewer §B1、§D 一致。基准列的中位差和最差与 `operations/work_logs/2026-10-27-orchestrator-v4-research-diagnostics.md` §1 一致。2 年对基准是 60/96 = 62.5%，打印为 62。

### 四种状态与跟涨跟跌

合计、拿现金、选标的是日超额相加后的百分点，1 位小数。看板整数是对这一位小数再四舍五入。

| 状态 | 月数 | 跑赢月份% | 拿现金 | 选标的 | 合计（1 位小数） | 看板整数 |
| --- | --- | --- | --- | --- | --- | --- |
| 牛市 | 53 | 54.7 | −25.9 | +26.5 | **+0.6** | **+1** |
| 回调 | 21 | 71.4 | +21.1 | +8.8 | **+29.9** | **+30** |
| 熊市 | 27 | 85.2 | +45.4 | +49.4 | **+94.9** | **+95** |
| 反弹 | 19 | 15.8 | −23.9 | −32.8 | **−56.7** | **−57** |

跟涨 **0.86**（基准上涨的 74 个月）。跟跌 **0.52**（基准下跌的 46 个月）。

这与 Reviewer §B2–§B3 的 1 位小数和 2 位小数一致，也与 `states.py` 在崩溃前打出的表一致。

### 登记脚本在 pandas 3.1 上的一处崩溃

`states.py` 打完上表之后，下一行用 `mon.select` 取列。pandas 3.1 的 `DataFrame.select` 是方法，会挡住同名列，于是抛 `AttributeError`。表本身已经打出，数字就是上面的 1 位小数。打分卡不改这份登记脚本，列名用 `["selection"]` 读取；跟涨、跟跌用同一文件里的月收益公式，并与 `reviewer_r3_scorecard.states_independent` 对照。

## Validation

- `.venv/bin/python -m unittest tests.v4.test_scorecard -v`：7 项通过。P1 与 Reviewer 纯函数的胜率差 `< 1e-9`，状态超额和跟涨/跟跌相等。
- `.venv/bin/python -m unittest discover -s tests -t .`：476 项，0 失败，1 跳过。
- `.venv/bin/python -m src.v4.scorecard reference`：验收通过，退出码 0。
- `.venv/bin/python -m src.v4.scorecard score ... --end 2016-01-01`：拒绝，退出码 2。没有打开更晚的组合收益。

交叉核对会调用 Reviewer 的 `build_lab2_pickle()`。该函数把 `data.pkl` / `aux.pkl` 写进诊断目录。测试在 `finally` 里删除，不入库。

## Decision / Next Steps

打分卡可以给以后的设计期结果用。D13-2 要求牛市和反弹的超额不为负；P1 参考数里反弹合计是 −56.7（看板 −57），所以这张卡会把现行 E2 标成反弹不及格。那是预注册要写的判据，本轮不改规则，也不跑 T1–T4。
