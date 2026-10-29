# v4-R5 设计期简报

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R5 步骤 5 · 设计期简报（Manager 打包 Dev / Reviewer 已公布数字）
- Date: 2026-10-29
- Owner: L. Loric
- Route: direct-execute
- Source of truth: `operations/reviews/2026-10-29-v4-r5-design-gate-signoff.md`；`operations/reviews/diag/v4/v4-r5-gate-scorecard-recompute.json`；`operations/work_logs/2026-10-29-v4-r5-design-runs.md`；`operations/planning/2026-10-29-v4-r5-plan.md`
- 读者: Orchestrator（面向 Owner 的五段由 Orchestrator 另写）
- 基线: `origin/main` `cbd94df42c1016737fb2c078d8f83e78222eae03`

## Goal / Summary

这是设计期读数的打包。窗口止于 **2015-12-31**。最终版按 E2 新口径 **B0**（U-指数为主）。Reviewer Decision：**approve**。T1–T4 没有一条同时通过三条过关规则，`final` 与 `B0` 的日净值逐日相同。

本文件转载 Dev 工作记录和 Reviewer 签收里已经写出的数字。策略好坏、优劣句子、面向 Owner 的五段，留在 Orchestrator 的体检。本简报不改规则，不重跑，不写 `results/v4/LOCK`，不移动标签，不含 2016-01-01 及以后的组合收益汇总。

主线（rebase-merge 之后的 `main`）：

| 步 | PR | `main` 上的提交 |
| --- | --- | --- |
| D22 统一后复权 + #121 抽查 | #120、#121 | 已在更早的 `main` 上；抽查签收提交 `89e4997` |
| 设计期运行 | #122 | `09fe9add4ce806f07c88ec64693106df3ff72802` |
| 过关表与 §7.5 签收 | #123 | `cbd94df42c1016737fb2c078d8f83e78222eae03` |

## Scope / 边界

- 设计期上界 **2015-12-31**。账本 41 行，`segment` 都是 `design`，参数里的 `end` 都是 `2015-12-31`。运行代码 `git_sha` 全部是 `18b5a82f0e874bcaa32cb4c26b001f8311d42819`。
- 过关只用 U-指数。U-可交易另行报告，两套池的数字不互相代替。
- §7.5 的四态和任意起点用签收里的 **scorecard** 列（含拿现金 / 选标的）。§6.2 过关表的 `pp_*` 只用于过关，两套口径量级接近，字段不逐格相等。
- 2016–20、2021–26 两段按预注册留空。本简报没有这两段的组合收益。
- 仓库中没有 `results/v4/LOCK`。标签 `milestone/v4-prereg-freeze` 仍指向 `6bcba53e36e74ec81dd21fb7ee7b8cea695038fb`（附注对象 `830320d03712df3a4098f352be8932e0553b5eeb`）。本简报没有移动它。`milestone/v4-code-freeze` 尚未登记。
- 下一步：Orchestrator 写面向 Owner 的五段体检，Owner 再阅读。在那之前不打代码冻结标签。

## D22 · 统一后复权

D22-1 已接上：研究和回测只读一条后复权，顺序是东财后复权 → 腾讯后复权（含按比例延长的尾部）→ D21 还原。`bars.adj=hfq` 仍只放东财（D22-3）。160125、160644 没有东财 `bars.adj=hfq`，入口选用腾讯；还原仍在 `backward_rebuild`，`selected=0`。冲突日没有改选用序列。

D22-2 的冲突日清单是非阻塞项，交给 Orchestrator，见 `operations/planning/2026-10-29-v4-r5-orchestrator-handoff.md`。文件：`results/v4/inventory/r5/hfq-return-conflicts.csv`（SHA256 `eff7f0ea783cfc8a99bb217d850599b8be9924b41a6b965ff87c9365859a94a1`）。抽查签收：160125 有 14 天，绝对差最大 2.931582 个百分点（2013-01-14）；160644 有 2 天，绝对差最大 0.306743 个百分点（2020-12-03）。这是两条价格序列的单日差，不是组合收益。

## E2 新口径与 T1–T4

产物目录：`results/v4/r5/design/<运行>/<池>/`。年化是 Dev 工作记录的全日历四舍五入（2005-01-04 → 2015-12-31）；「自 2006」从 2006-01-01 起。完整小数在同目录 `summary.json`。Reviewer C7：U-指数 B0–T4 的全日历 CAGR、自 2006 CAGR、最大回撤与各 `summary.json` 一致。

| 运行 | 池 | 年化 | 自 2006 | 最大回撤 |
| --- | --- | ---: | ---: | ---: |
| B0 | index | 19.01% | 21.12% | −39.06% |
| B0 | tradable | 4.91% | 5.20% | −27.78% |
| T1 | index | 19.95% | 22.23% | −39.40% |
| T1 | tradable | 5.77% | 6.16% | −23.45% |
| T2 | index | 19.45% | 21.61% | −40.38% |
| T2 | tradable | 4.64% | 4.90% | −29.19% |
| T3 | index | 18.99% | 21.10% | −39.93% |
| T3 | tradable | 4.90% | 5.19% | −28.02% |
| T4 | index | 16.95% | 18.87% | −36.11% |
| T4 | tradable | 5.05% | 5.46% | −27.82% |

U-可交易 B0 与 U-指数差一截（签收 follow-up：CAGR ≈ 4.91%）。Dev 工作记录把它记成设计期载体覆盖限制。报告分池写。

## candidate_gate

文件：`results/v4/r5/candidate-gate.csv`。SHA256 `32058828326f5155ce9b9a678746d2f55d7a4a023b3d20a883e01676383c1b42`。

Reviewer 用独立实现复算，与该文件、以及入库 `candidate_gate()` 都逐列一致（浮点列 max abs diff = 0）。`any_candidate_pass` 为 false。最终版 = **B0**。`results/v4/r5/design/final/index/net.csv` 与 `B0/index/net.csv` 逐日相同；U-可交易的 final 与 B0 同样逐日相同（本简报核对了这两个文件字节一致）。

下表是签收 B 节的独立过关表（与 Dev 文件一致）。`pp_*` 是 100×Σ(日超额)，交易日贴月标签，不拆拿现金 / 选标的。

| arm | ann_excess_s1 | ann_excess_s2 | pp_bull | pp_correction | pp_bear | pp_rebound | pass_segments | pass_target | pass_bear | pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| B0 | 0.1484 | −0.0239 | −10.81 | 12.60 | 91.17 | −55.04 | — | — | — | — |
| T1 | 0.1910 | −0.0372 | −11.99 | 19.04 | 86.64 | −46.96 | False | True | True | False |
| T2 | 0.1495 | −0.0161 | −1.57 | 9.74 | 92.63 | −58.34 | True | False | True | False |
| T3 | 0.1504 | −0.0259 | −9.43 | 11.16 | 91.17 | −55.04 | False | True | True | False |
| T4 | 0.1070 | −0.0312 | −66.54 | 26.47 | 121.92 | −65.86 | False | False | True | False |

目标状态：T1 反弹，T2 回调，T3 / T4 牛市。签收写明：T2 过了两段年化，没有过回调目标态。

复算输入：`results/v4/r5/gate-inputs.csv`、`results/v4/r5/month-states.csv`。日收益末日均为 2015-12-31。

## §7.5 关键数字

口径：B0 / U-指数。签收标题窗口写 2006-01-05 → 2015-12-31；性格表里的全日历另从 2005-01-04 起，两格都照抄，不混用。四态与任意起点用 scorecard。引擎复跑 B0 U-指数与公布 `net.csv` 的最大绝对差约 5×10⁻¹⁴。

### 1. 性格（签收 C1）

| 指标 | 值 | 窗口 / 方法 |
| --- | ---: | --- |
| 年化 CAGR | **19.01%** | 全日历 2005-01-04 → 2015-12-31，`cagr(net)`，与 `summary.json` 一致 |
| 年化 CAGR | **21.12%** | 自 2006-01-01 |
| 最大回撤 | **−39.06%** | 全样本；峰 2015-06-12 → 谷 2015-08-26（75 个交易日）；到 2015-12-31 净值尚未回到该峰 |
| 年化波动 | **19.15%** | 日收益 × √252 |
| 月度收益标准差 | **6.55%** | 月度复合收益 |
| 下行波动（年化） | **13.75%** | 负月收益标准差 × √12 |
| Calmar | **0.49** | CAGR / \|最大回撤\| |
| 换手率（近似） | **≈14 次/年** | 复跑 Book 的 (buy+sell) 之和 / 样本年数。复算 JSON 的 `b0_index_turnover_per_year` 是 13.95 |

### 2. 四种行情（签收 C2，scorecard）

| 状态 | 月数 | 合计 excess_pp | 拿现金 cash_pp | 选标的 selection_pp | 看板整数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 牛市 | 53 | −10.2 | −55.3 | 45.1 | −10 |
| 回调 | 21 | 12.6 | 28.1 | −15.5 | 13 |
| 熊市 | 27 | 91.2 | 81.5 | 9.6 | 91 |
| 反弹 | 19 | −55.0 | −54.2 | −0.8 | −55 |

跟涨 **0.84** / 跟跌 **0.60**（相对 BM-主的月收益）。

签收说明的例子：过关表 B0 牛市 `pp_bull` ≈ −10.81，scorecard 牛市 excess_pp 是 −10.2。§7.5 用上表。

### 3. 任意起点（签收 C3；跑赢占比为四舍五入整数 %）

| 持有年 | 对照 | n | 跑赢% | 中位差 pp | 最差 pp | 最差起点 | 来源 |
| ---: | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | 基准 | 108 | 56 | 2.1 | −51.2 | 2008-11-03 | 签收 C3 |
| 1 | 沪深300 | 108 | 53 | 2.3 | −80.3 | 2008-11-03 | 签收 C3 |
| 1 | 标普500 | 108 | 46 | −4.5 | −28.6 | 2009-08-03 | 签收 C3 |
| 1 | 纳指100 | 108 | 43 | −7.6 | −36.5 | 2009-04-01 | 签收 C3 |
| 2 | 基准 | 96 | 51 | 0.5 | −23.0 | 2008-11-03 | 签收 C3 |
| 2 | 沪深300 | 96 | 71 | 5.3 | −29.4 | 2008-11-03 | 签收 C3 |
| 2 | 标普500 | 96 | 46 | −3.3 | −23.2 | 2009-03-02 | 复算 JSON |
| 2 | 纳指100 | 96 | 39 | −10.1 | −31.9 | 2009-03-02 | 复算 JSON |
| 3 | 基准 | 84 | 52 | 0.6 | −13.6 | 2008-11-03 | 签收 C3 |
| 3 | 沪深300 | 84 | 75 | 6.6 | −14.4 | 2008-11-03 | 签收 C3 |
| 3 | 标普500 | 84 | 45 | −3.0 | −18.4 | 2009-04-01 | 复算 JSON |
| 3 | 纳指100 | 84 | 32 | −8.0 | −26.7 | 2009-04-01 | 复算 JSON |
| 5 | 基准 | 60 | 53 | 1.6 | −7.8 | 2008-11-03 | 签收 C3 |
| 5 | 沪深300 | 60 | 88 | 6.0 | −4.9 | 2008-11-03 | 签收 C3 |
| 5 | 标普500 | 60 | 35 | −2.8 | −16.4 | 2009-08-03 | 签收 C3 |
| 5 | 纳指100 | 60 | 27 | −7.3 | −21.6 | 2009-03-02 | 签收 C3 |

「复算 JSON」四行在同一次 `scorecard_B0_index.any_start` 里，签收正文的表没有逐行印出。公开同行（A1 / A2）的任意起点，签收没有给，本简报不新算。

### 4. 优劣对照

签收没有写「强的行情 / 弱的行情 / 一句话」。本简报不补这三句。Orchestrator 写 Owner 体检时再用上面已有的数字。

### 5. 时代切片（签收 C5）

设计期只填前两段。

| 年代 | CAGR | 最大回撤 |
| --- | ---: | ---: |
| 2006-01-01 → 2010-12-31 | **37.12%** | −38.65% |
| 2011-01-01 → 2015-12-31 | **6.98%** | −39.06% |
| 2016–20 | 留空 | 留空 |
| 2021–26 | 留空 | 留空 |

签收没有给这两段的累计超额、持仓市场权重、四个回看期的 IC。本简报不补算。

### 6. 与冻结 P1 的对照（签收 C4，持有 5 年跑赢 %）

| 对照 | 冻结 P1（v3.1 引擎 E2） | v4 B0（E2 新口径） |
| --- | ---: | ---: |
| 基准 BM-主 | 63 | **53** |
| 沪深300 | 93 | **88** |
| 标普500 | 50 | **35** |
| 纳指100 | 32 | **27** |

签收把差异记成 v4 成交限制、汇率、载体与 U-指数池，并写明这不是过关表错误。本简报只转载这句话，不另作解释。

### 7. 适应性抽样（签收 C6）

相对 B0 index 全日历 **19.01%**：

| 运行 | 池 | 全日历 CAGR | 签收附注 |
| --- | --- | ---: | --- |
| lookback-15-50-100-200 | index | **17.69%** | |
| delay-1d | index | **18.60%** | 最大回撤更深，−42.3% |
| drop-best-1 | index | **19.50%** | |
| no-substitute | tradable | **4.67%** | |

完整 25 行在 Dev 工作记录，路径见下一节。本简报不重算。

## A1 / A2 与 §7.2

公开同行只报告，不参与 §6.2 过关。下表年化是 Dev 工作记录的全日历四舍五入。Reviewer 这份过关签收没有重印 A1 / A2 的年化。小数在 `results/v4/r5/design/A1/` 与 `A2/` 的 `summary.json`。

| 运行 | 池 | 年化 | 最大回撤 | 净值序列 SHA256（`summary.json` 的 `net_sha256`） |
| --- | --- | ---: | ---: | --- |
| A1 | index | 24.47% | −42.86% | `3c371162360d276d6418b5d57a17b037abd5a99ac17e5b1933fd66854478634e` |
| A1 | tradable | 20.02% | −42.86% | `a2bca03c142db76b36af7b7789ec9e4fcd0b2fbc71a4c1270189e9d7cb83f13b` |
| A2 | index | 8.21% | −13.07% | `cf3091d5dfdae739a0f175c1d96c7910bd5ee1bbdb22c1f9fce7eecaa1b7685a` |
| A2 | tradable | 6.39% | −9.53% | `08552fc62e19634f03245958ee714f3d5cf81e3bc620df0a66ff6637228c090c` |

§7.2 稳健性 25 行（全日历年化、最大回撤、去掉的容器）在 `operations/work_logs/2026-10-29-v4-r5-design-runs.md` 的步骤 4 表。目录：`results/v4/r5/design/<运行>/<池>/`。签收抽到的四格见上一节。Dev 还写了两条逐日相同：U-可交易 `us-div-90` 与 B0 逐日相同；U-可交易 `drop-best-2` 与 `drop-best-1` 逐日相同。

## 完整性指纹

本简报核对了工作区里下列 CSV / toml 的 SHA256，与 Dev 工作记录和 Reviewer JSON 一致。`data/market.sqlite` 在本工作区是 Git LFS 指针（`GIT_LFS_SKIP_SMUDGE`），指针 oid 为 `1adb6d43384be3336a3f58e993dd31ed3d75e705935aa2ff16c575a30fc00e27`，与 D22 / 签收登记的内容哈希相同。本简报没有重新拉取 292618240 字节的实文件，也没有重算组合收益。

| 路径 | SHA256 |
| --- | --- |
| `data/market.sqlite`（LFS oid / 登记的内容哈希） | `1adb6d43384be3336a3f58e993dd31ed3d75e705935aa2ff16c575a30fc00e27` |
| `config/v3/universe.toml` | `3fb37205f6ebb852906ec68bde5751bdbe331cf2ba491e6d1685b7bc24879477` |
| `config/v4/universe.toml` | `1226175884c7d4f8fc735a3d718f51e4560af57676216b604c9386476556ddb0` |
| `results/v4/trial-ledger.csv` | `37a43abe5586ff4f24640a02f419e8296a03d05c285337fddec6489b402bf2a3` |
| `results/v4/r5/candidate-gate.csv` | `32058828326f5155ce9b9a678746d2f55d7a4a023b3d20a883e01676383c1b42` |
| `results/v4/r5/gate-inputs.csv` | `d99711c1585bdfb782263521c9aa63eee1c9338c68f36bf9382af540178d83db` |
| `results/v4/r5/month-states.csv` | `f1724bcd7aa51a250ddecdd3ee9541745fe2562d45d31c81c74638cab1353cbb` |
| `results/v4/r5/design/B0/index/net.csv`（含表头的文件哈希） | `eb24b980dea31a9f9786a9c77f17b711ac44f37d9b81dc734d92a199ed8c8afc` |
| B0 index `net_sha256`（无表头序列；`summary.json` / 签收 `series_sha256`） | `6f92c0388825e210623400e9743ff6672f244b143f0d6b4b3f56223bd4eeb87f` |
| B0 / final tradable `net_sha256` | `ac820be2d101779cf53c12c2c986b9a6e0db67ed5b95218a7e89b41f4bbae6e0` |

`net_sha256` 是无表头的 `date,net` 行串。对外写文件指纹时用 `sha256sum net.csv`（上表含表头那一行）。签收 follow-up 第 2 条。

| 项 | 读数 |
| --- | --- |
| 账本行数 | 41 |
| 账本 `git_sha` | 全部 `18b5a82f0e874bcaa32cb4c26b001f8311d42819` |
| 日收益末日 | B0–T4 与 gate inputs 都是 2015-12-31；本简报另看了 A1 / A2 / final 的 `summary.json`，`end` 也是 2015-12-31，`n` = 2671 |
| `results/v4/LOCK` | 不存在 |
| `milestone/v4-prereg-freeze` | 附注对象 `830320d03712df3a4098f352be8932e0553b5eeb`，指向 `6bcba53e36e74ec81dd21fb7ee7b8cea695038fb`。本简报只读，未移动 |

## Decision / Next Steps

设计期读数已按签收打包。没有 `LOCK`。没有 2016-01-01 及以后的组合收益汇总。本文件只含设计期读数。等 Orchestrator 写面向 Owner 的五段，再交 Owner。代码冻结不在这一步。

未在签收里、因而本简报留空的格子：优劣对照的三句话；年代累计超额、持仓权重、回看期 IC；任意起点相对 A1 / A2；2016–20 与 2021–26。
