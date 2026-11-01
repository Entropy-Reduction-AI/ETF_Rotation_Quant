# D30 · 预注册增加设计评审；v5 按设计缺陷修正（2026-11-01）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning（决定记录）
- Status: active
- Owner: L. Loric
- Maintainer: Orchestrator
- Date: 2026-11-01（Asia/Taipei）
- 依据：《v5 研究备忘》第 10.3 版第 7 节（四处结构硬伤）；Owner 2026-11-01：“可以写。”“先按 A 改”；并指出资深研究员应在测试前就能从策略本身判断组合的样子，v5 的缺陷在策略设计时就存在。

## 决定

| 编号 | 决定 |
| --- | --- |
| D30-1 | 每个研究版本的预注册在冻结前必须有“设计评审”一节：跑前五问 + 事前画像。只用规则文字和信号层面的描述统计，不算组合收益，不消耗尝试次数。Reviewer 冻结前逐条核对，答不清不冻结。细则 `docs/reference/strategy-design-review.md`；`AGENTS.md` 研究纪律新增一条 |
| D30-2 | 修改 D27-1：除修程序错误外，v5 允许**一次**设计缺陷修正 v5.1。条件：修正只来自设计评审（五问），不来自收益；事前画像在冻结前写下；原版结果不撤回，尝试次数照算。v5.1 = E2 新口径 + 每类上限 ⌈N/2⌉，预注册 `docs/prereg/etf-multiasset-rotation-prereg-v5.1.md`。入围仍按 v5 §6.3 对 B0；不入围则照常封板，v5.1 带着别的市场证据作为 v6 的第一个候选 |
| D30-3 | 面向 Owner：《v5 研究备忘》第 1 节改为 v5.1 的策略核心、资深研究员的事前评估方法、为什么能跟随市场变化；第 2–9 节作为 v5 原版留档 |

D30-1 只改 PROJECT:OWNED 分区，不动 HARNESS:MANAGED 分区。v5.1 预注册 §7 的三处（上限取值、预算 53 行、原版不做别的市场检验）待 Owner 在 R1 之后批准。
