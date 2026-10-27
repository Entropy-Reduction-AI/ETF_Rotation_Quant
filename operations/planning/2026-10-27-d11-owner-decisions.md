# D11 · Owner 决定（2026-10-27）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning（决定记录）
- Status: active
- Owner: L. Loric
- Maintainer: Orchestrator
- Date: 2026-10-27（Asia/Taipei）
- 依据：Owner 在 2026-10-27 对 Owner 看板第 1、4 节的答复（“三个问题都按你的建议做”），以及同日的补充意见
- 相关：`docs/owner/phase2-owner-board.md`；`operations/work_logs/2026-10-27-orchestrator-2009-reentry-diagnosis.md`；`docs/prereg/etf-multiasset-rotation-prereg-v3.1-addendum-1.md`

## 决定

| 编号 | 决定 | 说明 |
| --- | --- | --- |
| D11-1 | 休市、停牌或无有效价那天的离场卖单：**等到下一个有有效价格的交易日再卖** | 即 v3.1 §4.5.6 的闭合语义，等同当前代码实现。写入补充文本 addendum-1 |
| D11-2 | v3.1 判定规则不改；**C1 快信号回场作为影子方案**，一次性检验时同时计算并报告，不参与判定，看到结果后也不切换 | 写入 addendum-1。C2 不进影子 |
| D11-3 | Orchestrator 诊断变体计数 **29 → 31**（加入 C1、C2） | 判据 ⑤ 尝试次数 = ledger 配置行 + 28 + 31 |
| D11-4 | **批准 v3.1 进入代码冻结**，作为基线留档 | 前置条件不变：4 件小事闭合、Reviewer 签收后，由 Manager 打 `milestone/v3-code-freeze` |
| D11-5 | **不批准一次性检验** | Owner 认为策略完成度约 60%，先做 v4 研究（动态周期、时代风格、检验方式）。2016 年以后的组合收益继续不计算 |
| D11-6 | 冻结同时由 bot 团队做一次项目清理（分支和标签） | 任务与边界见 `operations/planning/2026-10-27-grok-tasks-code-freeze-cleanup.md` |
| D11-7 | UI/UX 统一以 `docs/reference/owner-facing-uiux-principles.md` 为准，吸收 PR #46 的方法框架；PR #46 关闭 | |
| D11-8 | Owner 看板在仓库维护（并发布为 Claude 页面），Notion 页面不再同步 | |
| D11-9 | 项目愿景按 Owner 的意思更新：**在动态周期内，选择 Top N 强势 ETF 轮动持有，获得超额收益，跑赢基准；同时控制回撤** | 已同步到看板和 `docs/project-intake/owner-vision-and-principles.md` |

## 待 Owner 后续确认（不在本次决定内）

- 涨停买不进、跌停卖不出、QDII 因溢价临时停牌时的成交假设（见 v4 研究备忘第 1 节）。
- 2026-10-27 新增的 4 个分解诊断（四个回看期单独运行）是否计入诊断计数（31 → 35）。
- v4 研究方向与候选集合。

## 不变的边界

- 不删除、不移动任何已有 tag；不强推、不改写 `main`。
- 不写 `results/v3/LOCK`；不计算 2016-01-01 以后的组合收益。
