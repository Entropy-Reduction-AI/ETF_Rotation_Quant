# D13 · Owner 决定（2026-10-28）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning（决定记录）
- Status: active
- Owner: L. Loric
- Maintainer: Orchestrator
- Date: 2026-10-28（Asia/Taipei）
- 依据：Owner 对《v4 研究备忘》第 2 版第 7 节的答复（两个选择按建议），以及分工、进度和命名的要求
- 相关：`docs/research/2026-10-27-v4-research-memo.md`；`docs/manual/roadmap-and-naming.md`；`operations/planning/2026-10-28-v4-dev-plan.md`

## 决定

| 编号 | 决定 | 说明 |
| --- | --- | --- |
| D13-1 | **美股行业数据**：以美国本土行业 ETF 为主（Select Sector SPDR，1998-12 起 9 只），标普500 行业全收益指数作核对 | 备忘选择 5-A |
| D13-2 | **“顺应市场”写进 v4 判据**：牛市、回调、熊市、反弹四种状态的超额分别报告，牛市和反弹的超额都不能为负 | 备忘选择 6-A；具体写法在 v4 预注册 |
| D13-3 | **分工**：Orchestrator 把握方向、写预注册、做少量验证；大量取数和数据整理交 Dev；Reviewer 抽查和复算；Manager 除追踪进度外，承担数据探索和小范围的策略探索 | 边界见 `docs/manual/roadmap-and-naming.md`；`AGENTS.md` 执行者一节同步修改 |
| D13-4 | **统一路线图与命名**：版本 → 阶段 ①–⑩ → 轮次 → 任务；决定 D 编号与候选编号不进路线图；v4 候选改名 T1–T4 | `docs/manual/roadmap-and-naming.md` |
| D13-5 | **v4 进入开发**：按 v4-R1 至 v4-R5 推进；R1–R3 是基础建设，可以并行；预注册（v4-R4）冻结之前不运行任何候选看收益 | `operations/planning/2026-10-28-v4-dev-plan.md` |
| D13-6 | **v3.1 收尾**：合入 4 个复核 PR（#49、#51、#53、#55）后删除已合入的分支；#31 的签收正文和 `dev/v3-design-period-brief` 的推迟记录先合入或打 `keep/` 再删；按 2026-10-23 清理记录补打 5 个缺失的 `milestone/*` 标签 | 补打的是“创建”，不是移动或删除；指向记录中的原提交 |
