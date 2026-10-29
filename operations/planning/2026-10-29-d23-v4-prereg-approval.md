# D23 · Owner 批准 v4 预注册；新建数据与容器看板（2026-10-29）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning（决定记录）
- Status: active
- Owner: L. Loric
- Maintainer: Orchestrator
- Date: 2026-10-29（Asia/Taipei）

## 决定

| 编号 | 决定 | 说明 |
| --- | --- | --- |
| D23-1 | **Owner 批准 v4 预注册第 2.3 版**（`docs/prereg/etf-multiasset-rotation-prereg-v4.md`） | Reviewer 已全部签收（R1、R1b、R1e、R1f）。Manager 合入后打 `milestone/v4-prereg-freeze`，指向含本记录与预注册定稿的 main 提交。之后改规则 = v4.1，须 Owner |
| D23-2 | 冻结后按 `operations/planning/2026-10-29-v4-r5-plan.md` 在设计期（≤ 2015-12-31）运行 v4 | 不做一次性检验，不写 LOCK（D20-4） |
| D23-3 | 新建《数据与容器看板》：`docs/owner/data-board.md`，并发布为 Claude 页面 | Owner 要求：池子里有什么、每一样从哪年起能买到、数据靠不靠得住；持续更新。数字由 `results/v4/diag/data-board/build_data_board.py` 生成，只统计起止日、覆盖和状态，不算任何收益。每一轮数据工作合入后，Manager 重跑脚本，Orchestrator 重新发布页面 |
