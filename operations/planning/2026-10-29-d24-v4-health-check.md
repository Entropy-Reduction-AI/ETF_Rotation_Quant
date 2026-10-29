# D24 · v4 设计期体检第 1 版；可交易池程序问题（2026-10-29）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning（决定记录）
- Status: active
- Owner: L. Loric
- Maintainer: Orchestrator
- Date: 2026-10-29（Asia/Taipei）
- 依据：`operations/reports/v4-r5-design-period-brief.md`；`operations/reviews/2026-10-29-v4-r5-design-gate-signoff.md`；`operations/planning/2026-10-29-v4-r5-orchestrator-handoff.md`；Orchestrator 逐日复跑（`results/v4/diag/health/tradable_probe.py`）
- 相关：`docs/owner/v4-health-check.md`；`operations/planning/2026-10-29-v4-r5b-plan.md`

## Orchestrator 发现：U-可交易的实现与预注册 §3.2 不一致

逐日复跑 E2 新口径（B0）的 U-可交易，与公布的 `net.csv` 最大差 5×10⁻¹⁴。持仓显示：2005–2015 只有 4 个容器曾经可交易（csi-dividend 2007-04-19 起、chinext 2012-03-14、csi300 2012-08-21、csi500 2014-02-26）；年平均现金权重 2005–2006 为 100%、2011 为 100%、2007 为 94%。

原因有两处：

1. **第 2 档没有扩大池子。** `load_market(..., pool="tradable")` 沿用 v3 的可交易序列（只认场内 ETF 的历史），`apply_market` 的 `_gate` 只能在此基础上再收窄。`build_candidates` 已经给 csi300 选出 050002（2003 年起有 `otc_nav`），但 csi300 在 U-可交易的 `signal` / `pnl` 要到 2012-05-29 才有值。
2. **载体候选只覆盖 16 个容器。** `_execution_etfs` 只承认 `EXACT_INDEX` 和 `OWN_TRACK` 里的容器（14 个 A 股 + chinext、star50），ndx100、spx、hsi、gold、cgb-5y 等 `index_names()` 为空，`build_candidates` 返回空列表。513100（2013-05）、513500（2013-12）、159920（2012-10）、518880（2013-07）等都进不了 U-可交易。`v4_listing` 的第 2 档也只有 35 行（沪深300、中证500、红利、金融地产）。

另外，附表 A 的 A1/A2 U-可交易用载体掩码 + 研究序列的收益，与 B0 的 U-可交易（载体自己的收益）口径不同，A1 U-可交易 20.0% 与 B0 U-可交易 4.9% 不可比。

## 决定

| 编号 | 决定 | 理由 |
| --- | --- | --- |
| D24-1 | U-可交易的全部设计期结果（B0、T1–T4、final、稳健性、A1/A2 的 tradable 行）**作废**，按 v3 §9.4 当程序错误处理：修复后全部重跑，原 ledger 行就地替换并注明原因，不新增行，不计入新的尝试 | 预注册 §3.2 写明第 2 档场外纯指数基金和全部容器的载体；实现没有做到，不是规则问题 |
| D24-2 | 过关结果有效：`candidate_gate()` 只用 U-指数，T1–T4 均未过关，v4 最终版 = E2 新口径。修复后 U-指数各行的日收益应逐日不变；若变，Dev 先停下报 Orchestrator | U-指数的研究序列不依赖 U-可交易的载体掩码 |
| D24-3 | `milestone/v4-code-freeze` 等 v4-R5b 完成、Reviewer 签收之后再打 | 冻结的代码应包含修复 |
| D24-4 | Reviewer 必查项新增：每次运行列出 U-可交易每年可交易的容器数和年平均现金权重，与数据看板 `buy_by_year`（按该运行是否含 T4 取范围）对照，差异逐条说明（3,000 万门槛、无后复权等） | 这次签收没有发现；数据看板正是为这种核对而建 |
| D24-5 | D22-2 后复权冲突日：维持 D22-1 的选用顺序（东财 → 腾讯 → 还原），160125（14 天，最大 2.93 个百分点，2013-01-14）、160644（2 天）只登记，不换源、不设例外 | 差异是单日价格差；冲突日不改变来源优先级 |
| D24-6 | 冻结的预注册正文状态行（“待 Owner 批准；尚未冻结”）不改；以 D23 为准 | 冻结后改正文 = v4.1 |
| D24-7 | 体检报告第 1 版发布（只含 U-指数池）；v4-R5b 之后出完整版，再请 Owner 校准期望备忘的三条线 | 期望线按 §7.6 在一次性检验之前定稿 |
| D24-8 | v5 研究备忘新增两条候选方向：④ 防守资产用债券；⑤ 趋势明确时更集中（来自 A1 对照的诊断）。只是候选，写 v5 预注册时再定，Owner 可划掉 | 公开同行第二层对照的用途：诊断复杂度是否带来价值 |
