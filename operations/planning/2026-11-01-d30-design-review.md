# D30 · 预注册增加设计评审（2026-11-01）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning（决定记录）
- Status: active
- Owner: L. Loric
- Maintainer: Orchestrator
- Date: 2026-11-01（Asia/Taipei）
- 依据：《v5 研究备忘》第 10.3 版第 7 节（四处结构硬伤）；Owner 2026-11-01：“可以写。”并指出资深研究员应在测试前就能从策略本身判断组合的样子。

## 决定

| 编号 | 决定 |
| --- | --- |
| D30-1 | 每个研究版本的预注册在冻结前必须有“设计评审”一节：跑前五问 + 事前画像。只用规则文字和信号层面的描述统计，不算组合收益，不消耗尝试次数。Reviewer 冻结前逐条核对，答不清不冻结。细则 `docs/reference/strategy-design-review.md`；`AGENTS.md` 研究纪律新增一条 |
| D30-2 | （待 Owner 选择）v5 怎么改：见 2026-11-01 Orchestrator 给 Owner 的选项 |

只改 PROJECT:OWNED 分区，不动 HARNESS:MANAGED 分区。这是 Owner 明确批准的治理层修改，单独成 PR。
