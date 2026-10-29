# v4-R5 · 设计期过关表 + §7.5 关键数字 · 签收 · 2026-10-29

## Decision：`approve`

在 Dev PR [#122](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/122) 尖端 `982c0cf3832f5d9c301d35eda810b9f874d11812`（base main `89e4997`）上，Reviewer **独立复算** §6.2 `candidate_gate()` 与 Manager §7.5 所需关键数字（最终版 = E2 新口径 **B0**，U-指数池为主）。过关表与 Dev 公布文件 **逐列一致**；四条候选 **均未** 同时通过三条规则；`final` 与 `B0` 日收益 **逐日相同**。未发现 2016+ 组合 PnL、LOCK 或 tag 移动。**未改** Dev 分支业务代码或 `results/v4/r5/` 产物。

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R5 步骤 3–5 Reviewer 复算（PR #122）
- Date: 2026-10-29 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（Review 分支仅追加本文件与 diag 脚本/JSON）
- Dev: PR #122 · branch `cursor/v4-r5-design-runs-8aa5` · head `982c0cf…`
- Work log（Dev）: `operations/work_logs/2026-10-29-v4-r5-design-runs.md`
- 设计期上界: **2015-12-31**（无一次性检验、无 LOCK）

## A. 独立复算命令与产物

环境：仓库根 `.venv`；`git lfs pull` 后 `data/market.sqlite`；`mkdir -p outputs`。

| 步骤 | 命令 | 结果 |
| --- | --- | --- |
| 过关 + §7.5 关键数 | `.venv/bin/python operations/reviews/diag/v4/v4-r5-gate-scorecard-recompute.py` | exit **0** |
| 回归（含 gate / r5） | `.venv/bin/python -m unittest discover -s tests -t . -q` | exit **0** |

日志：`/opt/cursor/artifacts/v4-r5-reviewer-recompute.log`  
独立 JSON：`operations/reviews/diag/v4/v4-r5-gate-scorecard-recompute.json`

## B. §6.2 过关表（独立实现）

**输入（Dev 公布，Reviewer 不当作过关真值）：**

- `results/v4/r5/gate-inputs.csv`（B0、T1–T4 与 BM-主 日收益）
- `results/v4/r5/month-states.csv`（`classify_months` 对 H00300 全收益）

**方法：** `operations/reviews/diag/v4/v4-r5-gate-scorecard-recompute.py` 内联 `independent_gate()`（与 R2c diag 同结构，未 import Dev 过关 CSV）；并与入库 `candidate_gate()` 交叉。

**结论：**

| 核对 | 结果 |
| --- | --- |
| 独立表 vs `candidate-gate.csv` | **match**（浮点列 max abs diff = 0） |
| 独立表 vs `src.v4.scorecard.gate.candidate_gate` | **match** |
| 任一 T1–T4 `pass == True` | **无**（`any_candidate_pass`: false） |
| 最终版 | **B0**（`final/index/net.csv` 与 `B0/index/net.csv` 逐日相同） |

**独立过关表（与 Dev 文件一致）：**

| arm | ann_excess_s1 | ann_excess_s2 | pp_bull | pp_correction | pp_bear | pp_rebound | pass_segments | pass_target | pass_bear | pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| B0 | 0.1484 | −0.0239 | −10.81 | 12.60 | 91.17 | −55.04 | — | — | — | — |
| T1 | 0.1910 | −0.0372 | −11.99 | 19.04 | 86.64 | −46.96 | False | True | True | **False** |
| T2 | 0.1495 | −0.0161 | −1.57 | 9.74 | 92.63 | −58.34 | True | False | True | **False** |
| T3 | 0.1504 | −0.0259 | −9.43 | 11.16 | 91.17 | −55.04 | False | True | True | **False** |
| T4 | 0.1070 | −0.0312 | −66.54 | 26.47 | 121.92 | −65.86 | False | False | True | **False** |

目标状态：T1 反弹，T2 回调，T3/T4 牛市。T2 过两段年化但未过回调目标态。

## C. §7.5 关键数字（B0 / U-指数 / 2006-01-05→2015-12-31）

**净值来源：** `read_net("B0","index")`；**引擎复跑** B0 U-指数 A 臂与公布 `net.csv` 最大绝对差 **≈ 5×10⁻¹⁴**（不修改 ledger）。  
**BM-主 / 四态 / 任意起点：** `src/v4/scorecard/core.py`（与 v3 Owner 看板诊断同公式）；四态拆 **拿现金 / 选标的** 需引擎 `held` 现金权重（复跑取得）。

### C1 · 性格（§7.5-1）

| 指标 | 值 | 方法/窗口 |
| --- | ---: | --- |
| 年化 CAGR（全日历 2005-01-04→2015-12-31） | **19.01%** | `cagr(net)`，与 `summary.json` 一致 |
| 年化 CAGR（自 2006-01-01） | **21.12%** | `cagr(net.loc["2006-01-01":])` |
| 最大回撤 | **−39.06%** | 全样本；峰 2015-06-12 → 谷 2015-08-26（75 交易日）；至 2015-12-31 **未恢复** 至该峰净值 |
| 年化波动 | **19.15%** | 日收益 × √252 |
| 月度收益标准差 | **6.55%** | 月度复合收益 |
| 下行波动（年化） | **13.75%** | 负月收益 std × √12 |
| Calmar | **0.49** | CAGR / \|max DD\| |
| 换手率（近似） | **≈14 次/年** | 复跑 Book `(buy+sell)` 之和 / 样本年数 |

### C2 · 四种行情（§7.5-2，H00300 状态 + 日超额拆分）

| 状态 | 月数 | 合计 excess_pp | 拿现金 cash_pp | 选标的 selection_pp | 看板整数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 牛市 | 53 | −10.2 | −55.3 | 45.1 | −10 |
| 回调 | 21 | 12.6 | 28.1 | −15.5 | 13 |
| 熊市 | 27 | 91.2 | 81.5 | 9.6 | 91 |
| 反弹 | 19 | −55.0 | −54.2 | −0.8 | −55 |

跟涨 **0.84** / 跟跌 **0.60**（相对 BM-主 月收益）。

**说明：** §6.2 过关表中的 `pp_*` 为 **100×Σ(日超额)**（交易日贴月标签，**不**拆拿现金/选标的）；§7.5 报告应使用上表 **scorecard** 口径。两者量级接近但不逐字段相等（例：过关表 B0 牛市 pp ≈ −10.81 vs scorecard −10.2）。

### C3 · 任意起点（§7.5-3，跑赢占比为四舍五入整数 %）

| 持有年 | 对照 | n | 跑赢% | 中位差 pp | 最差 pp | 最差起点 |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 基准 | 108 | 56 | 2.1 | −51.2 | 2008-11-03 |
| 1 | 沪深300 | 108 | 53 | 2.3 | −80.3 | 2008-11-03 |
| 1 | 标普500 | 108 | 46 | −4.5 | −28.6 | 2009-08-03 |
| 1 | 纳指100 | 108 | 43 | −7.6 | −36.5 | 2009-04-01 |
| 2 | 基准 | 96 | 51 | 0.5 | −23.0 | 2008-11-03 |
| 2 | 沪深300 | 96 | 71 | 5.3 | −29.4 | 2008-11-03 |
| 3 | 基准 | 84 | 52 | 0.6 | −13.6 | 2008-11-03 |
| 3 | 沪深300 | 84 | 75 | 6.6 | −14.4 | 2008-11-03 |
| 5 | 基准 | 60 | 53 | 1.6 | −7.8 | 2008-11-03 |
| 5 | 沪深300 | 60 | 88 | 6.0 | −4.9 | 2008-11-03 |
| 5 | 标普500 | 60 | 35 | −2.8 | −16.4 | 2009-08-03 |
| 5 | 纳指100 | 60 | 27 | −7.3 | −21.6 | 2009-03-02 |

### C4 · E2 新口径 B0 vs 冻结 P1（§6.1 对照，持有 5 年跑赢%）

| 对照 | 冻结 P1（v3.1 引擎 E2） | v4 B0（E2 新口径） |
| --- | ---: | ---: |
| 基准 BM-主 | 63 | **53** |
| 沪深300 | 93 | **88** |
| 标普500 | 50 | **35** |
| 纳指100 | 32 | **27** |

差异来自 v4 成交限制、汇率、载体与 U-指数池，**非** 过关表错误。

### C5 · 时代切片（§7.5-5 设计期仅 2006–10、2011–15）

| 年代 | CAGR | 最大回撤 |
| --- | ---: | ---: |
| 2006-01-01 → 2010-12-31 | **37.12%** | −38.65% |
| 2011-01-01 → 2015-12-31 | **6.98%** | −39.06% |

### C6 · 适应性（§7.5-6 / §7.2 抽样，全日历 CAGR）

相对 B0 index **19.01%**：`lookback-15-50-100-200` **17.69%**；`delay-1d` **18.60%**（MDD 更深 −42.3%）；`drop-best-1` **19.50%**；U-可交易 `no-substitute` **4.67%**。完整 25 项见 Dev work log 表。

### C7 · U-指数全日历 CAGR  spot-check（B0–T4）

自 `net.csv` 重算 CAGR / 自 2006 / MDD 与各 `summary.json` **一致**（浮点末位差 &lt; 1e-10）。Dev work log 四舍五入展示（如 B0 19.01%）与复算一致。

## D. 轻量完整性

| 项 | 期望 / 说明 | Reviewer |
| --- | --- | --- |
| `results/v4/trial-ledger.csv` 行数 | ≈41 | **41** |
| ledger `git_sha` | `18b5a82…`（运行代码） | **全部为** `18b5a82f0e874bcaa32cb4c26b001f8311d42819` |
| `data/market.sqlite` SHA256 | D22 `1adb6d43…` | **一致** |
| `candidate-gate.csv` SHA256 | `32058828…` | **一致** |
| `gate-inputs.csv` / `month-states.csv` | Dev 指纹 | SHA256 **一致**（见 JSON） |
| B0 index 日序列指纹 | `summary.json` `net_sha256` | **6f92c038…**（`series_sha256`，**非** 含表头 CSV 文件 hash） |
| 日收益末日 | 2015-12-31 | B0–T4、gate inputs **均为** 2015-12-31 |
| `results/v4/LOCK` | 不存在 | **不存在** |
| tag `milestone/v4-prereg-freeze` | Owner：勿移动 | Reviewer **未移动**；当前检出 `830320d03712df3a4098f352be8932e0553b5eeb`（与任务描述中的 `6bcba53` 短 hash 并存于历史记录，以远端 tag 为准） |

## E. Follow-ups（非阻塞）

1. **Manager §7.5 成稿**：四态与任意起点请用 **scorecard** 列（含拿现金/选标的）；过关表 `pp_*` 仅用于 §6.2。
2. **`net_sha256` 命名**：摘要字段为 **无表头** `date,net` 行串 SHA；若对外写「文件指纹」需另报 `sha256sum net.csv`。
3. **U-可交易 B0** 与 index 差异大（CAGR ≈ 4.91%）：设计期载体覆盖限制，已在 Dev work log 说明；报告需分池写清。

## F. Reviewer 纪律

- 未合并 main、未创建/移动/删除 tag、未写 LOCK、未改 `trial-ledger.csv` 或 `results/v4/r5/**` 运行产物。
- 未计算 2016-01-01 及以后组合收益汇总。
