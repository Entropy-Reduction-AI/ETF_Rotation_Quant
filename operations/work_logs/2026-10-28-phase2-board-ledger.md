# 第二阶段看板流水（重写前原文）

## Metadata

- Project: ETF_Rotation_Quant
- Task: 把 2026-10-28 重写前的群看板原文移出现行看板
- Date: 2026-10-28
- Owner: project owner
- Route: direct-execute
- Source of truth: main `9fd6f67be6d1c194d170b048fe3667367a0ac0fe` 上的 `operations/planning/phase2-board.md`；命名见 `docs/manual/roadmap-and-naming.md`

## Goal / Summary

D13 把现行群看板改成「版本 × 阶段 × 轮次」。下面是重写前的全文，从该提交原样抄出，便于对照旧的 L1–L5 / G0–G5 流水。现行位置以 `operations/planning/phase2-board.md` 为准。

## 原文

# 第二阶段看板 · 三 bot 协作

Phase 2 看板。Manager、Dev、Reviewer 按已冻结的预注册 v3.1 执行。v3.1 已于 2026-10-25 冻结。tag `milestone/v3.1-prereg-freeze` → `1040035ee1d707368b58687994894189753843ac`。Reviewer PR #36 结论 `approve_with_follow_up`（B1/B2 已闭合；G2/G3 工程跟进不阻止本次冻结）。先前 PR #33 的 return 只评父提交 `a5bf56a`，记录保留，不是本次签收。D10 冻结后工程已合入（PR #39、#40；Reviewer `approve_with_follow_up`）。下一步是 Dev 正式设计期复跑，end≤2015-12-31。§4.5.6 缺价日到期离场仍是 rules-open，留给 Owner，不阻塞本次合入。G2 与 `milestone/v3-code-freeze` 仍未进入。不写 `results/v3/LOCK`。正式设计期报告交给 Owner 后本轮暂停。本文件只做协调。

备注：Manager 状态汇报固定五段：本周完成 / 能做什么不能做什么 / 设计期业务信号 / 风险卡点 / 需要 Owner 的事。

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning
- Status: active
- Owner: L. Loric
- Maintainer: ETF Rotation Manager
- Date: 2026-10-25
- 权威顺序: `AGENTS.md` > 已冻结预注册 > `operations/planning/2026-10-24-phase2-task-list.md` > 群聊。已冻结规则是预注册 v3.1（`milestone/v3.1-prereg-freeze` → `1040035ee1d707368b58687994894189753843ac`）。v3 仍以 `milestone/v3-prereg-freeze` 封存
- 任务清单: `operations/planning/2026-10-24-phase2-task-list.md`
- D9: `operations/planning/2026-10-24-d9-phase2-decisions.md`
- D10: 本文件「D10」节。全文 `operations/planning/2026-10-25-d10-v3.1-approval.md`（已在 main，PR #32）
- 预注册 v3: `docs/prereg/etf-multiasset-rotation-prereg-v3.md`
- 预注册 v3.1: `docs/prereg/etf-multiasset-rotation-prereg-v3.1.md`（已冻结）。`--ff-only` 合入 PR #32。规则修订提交变基后为 `c29758a70c4bb3b29a1a8fd3cebed4d249e4da92`（原 `c6205e0985161aeba2335af582a758f91911e7cb`）。所评父提交变基后为 `3a9415da1ac226a72e02c47c2b8fe25c0ee962c7`（原 `1c52b5b725b60471280dbbca4779d7f66e808315`）
- v3.1 复审: PR #36 已 MERGED。`operations/reviews/2026-10-25-v3.1-prereg-rereview.md`。结论 `approve_with_follow_up`。所评父提交原 `1c52b5b725b60471280dbbca4779d7f66e808315`，变基后等价 `3a9415da1ac226a72e02c47c2b8fe25c0ee962c7`。跟进项是 G2/G3 工程，不阻止本次冻结
- v3.1 先前退回: PR #33 已关闭，由 #36 取代。`operations/reviews/2026-10-25-v3.1-prereg-review.md` @ `fa825b7beccacda24004fdb52f48b3073fddf052`（该文件未合入 main）。结论 return。所评父提交 `a5bf56a06e4a7ba25b1615792cdbb902a4fde0eb`。不得当作本次签收
- v3.1 交接: `operations/planning/2026-10-25-v3.1-revision-handoff.md`（已在 main）。不是签收；签收是上面的复审
- 新会话: 先读 `docs/project-intake/owner-vision-and-principles.md`（已在 main）

## 硬规则

- 规则写在预注册里。实现可以迭代。未经 Owner，不改规则。
- G3 之前：不计算、不输出截止日晚于 2015-12-31 的组合收益。溢价模块可以用 2021 年起的数据做机制检验，仍然不输出任何 2016 年起的组合收益。
- `config/v3/universe.toml` 在 main 上的登记表 SHA256 现为 `fda394d57b9109225bda0d459975125364b5f1bb5d1793c9ad080ec55f789b19`（D10 冻结后工程重 emit，与 Reviewer 签收一致；上一版 L1 返工 `96592f553b9cc796922312b918ad3bc349766c84baab650032bc5c0a9a6aec8a`，再上一版 `693b7d4dff91dff4b9bac4a0c1241eb4692f6b3cbd444965440a265ffa32aaff`）。设计期回测 end≤2015-12-31 可以开始。本次合入没有打 tag，也没有写 `results/v3/LOCK`。
- 合入 main、新建 tag、删除已合入分支只由 Manager 执行（任务清单 §1，Owner 2026-10-24 常设授权）。Manager 可用 `--ff-only` 合入已通过评审的 `dev/v3-*`。D10（2026-10-25）已批准预注册 v3.1 的内容，并已冻结。Reviewer PR #36 结论 `approve_with_follow_up`（B1/B2 已闭合）。先前 PR #33 结论 return，所评父提交 `a5bf56a06e4a7ba25b1615792cdbb902a4fde0eb`，记录保留，不是本次签收。Manager 已 `--ff-only` 合入 PR #32 与 PR #36，并打 `milestone/v3.1-prereg-freeze` → `1040035ee1d707368b58687994894189753843ac`。合入是快进，没有强推或改写 main，没有移动或删除任何既有 tag。文本冻结当时不合入 #29、#31 两支 PR。防御与假期内容后来随 PR #39 进入 main；#29 与 #31 仍开着，本登记不关闭。`milestone/v3-code-freeze` 仍由 Manager 打，但 Owner 已看过正式设计期报告，且既有前置条件都满足之前不打；Owner 看过业务体检仍然必要。D10 执行顺序第 4 步另写：Owner 看过正式引擎设计期复跑结果之后，才进入代码冻结。G2 仍是未开始。不输出 2016 年起的组合收益，不写 `results/v3/LOCK`。模拟盘与真钱须 Owner 另作明确 G3 批准；「让 Manager 继续」不是 G3 批准。G3、G5、v3.1 冻结后再改规则、尝试预算 >60 仍须 Owner。不得删除或移动任何 tag，不得强推或改写 main。正式设计期报告交给 Owner 后本轮暂停。

## 门禁

| 门禁 | 内容 | 谁批准 | 状态 |
| --- | --- | --- | --- |
| G0 | 第一阶段封存、合同修订、D9 与预注册草稿入库 | Owner | 已完成 |
| G1 | 预注册已冻结。`milestone/v3-prereg-freeze` → `bfeb49cc65eb0ba419bc98348f1d643fac1211f6` | Owner | 已完成（2026-10-24/25） |
| G2 | 代码冻结：各开发线评审通过、全量测试 0 失败。Reviewer 批准后，Manager 打 `milestone/v3-code-freeze`。打 tag 前两条都要满足：Owner 已看过业务体检（第 6 项，未开始）；Owner 已看过 Orchestrator 设计期复诊结果。后者是更强门禁。此前不进入代码冻结 | Reviewer | 未开始 |
| G3 | 跑全期（含 2016 后），写 `results/v3/LOCK` | Owner 批准，Reviewer 执行 | 未开始 |
| G4 | 按 v3 §6、§7.3 出结论 | Reviewer | 未开始 |
| G5 | 是否进入前向模拟盘、是否上真钱 | Owner | 未开始 |
| v3.1 文本 | 已完成。`milestone/v3.1-prereg-freeze` → `1040035ee1d707368b58687994894189753843ac`。Reviewer PR #36 结论 `approve_with_follow_up`。所评父提交原 `1c52b5b725b60471280dbbca4779d7f66e808315`，变基后等价 `3a9415da1ac226a72e02c47c2b8fe25c0ee962c7`。规则修订提交原 `c6205e0985161aeba2335af582a758f91911e7cb`，变基后 `c29758a70c4bb3b29a1a8fd3cebed4d249e4da92`。B1/B2 已闭合。G2/G3 工程跟进不阻止本次冻结。PR #33 的 return 只评 `a5bf56a`，不是本次签收。PR #32、#36 已 `--ff-only` 合入。不合入 #29、#31 | Owner 已批准内容；Reviewer 复审 | 已完成 |

G2 仍是未开始。不进入代码冻结，也不打 `milestone/v3-code-freeze`，直到 Owner 已看过正式设计期报告，且既有前置条件都满足（含 Orchestrator 设计期复诊结果与业务体检）。D10 文档执行顺序第 4 步写的是：Owner 看过正式引擎复跑结果，然后代码冻结，然后一次性检验（Owner 批准）。本看板只登记该句，G2 保持未开始。「让 Manager 继续」不是 G3 批准。不输出 2016 年起的组合收益，不写 `results/v3/LOCK`。现行顺序见「D10」节：v3.1 文本已冻结（`milestone/v3.1-prereg-freeze` → `1040035ee1d707368b58687994894189753843ac`；Reviewer PR #36 `approve_with_follow_up`；先前 PR #33 只评父提交 `a5bf56a`，不是本次签收）。D10 冻结后工程已合入：官方回溯并保留发布日口径开关、防御与假期数据、§4.5 单只离场、溢价接入执行链。PR #39 `--ff-only` 尖端 `26aba1cfa3365a0c6a72e5b0466de8517fd09d76`；Reviewer PR #40 结论 `approve_with_follow_up`，尖端 `b2a65c132a564f86e98b241ccab285ef67984916`。下一步是 Dev 正式设计期复跑，end≤2015-12-31。§4.5.6 缺价日到期离场仍是 rules-open，留给 Owner，不阻塞本次合入，也不写成已冻结规则。PR #29、#31 仍开着，不关闭；防御与假期内容已随 #39 进入 main。正式设计期报告交给 Owner 后本轮暂停。`CBA00601` 仍无新容器授权，不放入池；名称对不上 v3 §3.2 的升级仍在「阻塞 / 待 Owner 决定」；D10 与 v3.1 文本都未点名该代码。L5 仍等待 G2 与 G3，此前不开分支、不跑全期。

## G1 预注册修订与冻结

已完成（2026-10-24/25）。预注册状态行：已冻结（G1，2026-10-24，Owner 批准）。

- 冻结提交: `bfeb49cc65eb0ba419bc98348f1d643fac1211f6`（`prereg: freeze v3 at G1`）
- tag: `milestone/v3-prereg-freeze` → 该提交
- main: Manager 授权提交 `52a3aa861e4428cc1fcb343b5adcafb023782098`（父提交即冻结提交）
- `review/v3-prereg` 已 `--ff-only` 合入后删除
- 冻结时测试: 351 跑，350 过，0 失败，1 跳过
- 评审文件: `operations/reviews/2026-10-24-v3-prereg-review.md`（起点 `6f07a0f`；Owner 决定写入 `89d18be`）
- 过程 PR: https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/15 （分支已删除）
- v3 冻结后，改 §3–§7 的规则、门槛、候选或预算即新版本，须 Owner。Owner 已于 2026-10-25 以 D10 批准 v3.1（补全标的池 + 单只 10% 离场），并已冻结。见「D10」节。B1–B7 的决定见下方。登记表已随 L1 冻结在 main。

## D10 · 预注册 v3.1（Owner 2026-10-25，Asia/Taipei）

Owner 批准预注册 v3.1。内容是：补全标的池（官方回溯历史在可得处可用）+ 单只 10% 离场。其他规则不变。2026-10-25 已冻结。tag `milestone/v3.1-prereg-freeze` → `1040035ee1d707368b58687994894189753843ac`。Reviewer PR #36 结论 `approve_with_follow_up`（B1/B2 已闭合；G2/G3 工程跟进不阻止冻结）。先前 PR #33 退回记录保留，所评只是父提交 `a5bf56a06e4a7ba25b1615792cdbb902a4fde0eb`，不是本次签收。本段登记的是文本冻结当时：不改预注册正文，不写 `results/v3/LOCK`，不打 `milestone/v3-code-freeze`，当时不合入 PR #29、#31。冻结后工程已另行 `--ff-only` 合入，见下表「冻结之后的 Dev」。

| 项 | 登记 |
| --- | --- |
| 决定 | D10，2026-10-25（Asia/Taipei）。v3.1 = 补全标的池（指数公司自己发布的回溯历史，可得则用，各容器一视同仁）+ 单只从持有期高点回撤 10% 离场，下一交易日收盘卖出，权重进现金。打分、N、频率、空位放现金、五条判据、预算 60，以及 v3.1 文本未改的条款，沿用 v3 |
| 全文 | `operations/planning/2026-10-25-d10-v3.1-approval.md`（已在 main，PR #32）。尝试次数如何加上 Orchestrator 的 29 个诊断变体，以该记录和 v3.1 §6 为准 |
| 文本 | PR https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/32 已 MERGED（`--ff-only`）。所评父提交原 `1c52b5b725b60471280dbbca4779d7f66e808315`，变基到当时 main `1784cff7d30c0f2b33295be781f894738a3baa95` 之后为 `3a9415da1ac226a72e02c47c2b8fe25c0ee962c7`。规则修订提交原 `c6205e0985161aeba2335af582a758f91911e7cb`，变基后 `c29758a70c4bb3b29a1a8fd3cebed4d249e4da92`（修订 B1/B2，并写入交接）。此前登记的 head `a5bf56a06e4a7ba25b1615792cdbb902a4fde0eb` 是 PR #33 所评父提交，保留为退回记录。范围是文档、SVG 和诊断脚本，无业务代码。规则文件 `docs/prereg/etf-multiasset-rotation-prereg-v3.1.md` 已在 main。状态：已冻结 |
| 交接 | `operations/planning/2026-10-25-v3.1-revision-handoff.md` 已在 main。该文件不是签收。签收是 PR #36 |
| 门 | 已通过。Reviewer PR #36 结论 `approve_with_follow_up`。B1/B2 已闭合。G2/G3 工程跟进不阻止本次冻结。Manager 已 `--ff-only` 合入 #32 与 #36，并打 `milestone/v3.1-prereg-freeze` → `1040035ee1d707368b58687994894189753843ac`（附注标签对象 `e3b55a7b8ce967a43341a3c9d02e6a0a42e2b508`）。先前 PR #33 结论 return 只评 `a5bf56a06e4a7ba25b1615792cdbb902a4fde0eb`，不是本次签收。不合入 #29、#31。没有强推或改写 main，没有移动或删除任何既有 tag |
| 评审 | 签收：PR https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/36 已 MERGED。评审文件 `operations/reviews/2026-10-25-v3.1-prereg-rereview.md`。结论 `approve_with_follow_up`。所评父提交原 `1c52b5b725b60471280dbbca4779d7f66e808315`，变基后等价 `3a9415da1ac226a72e02c47c2b8fe25c0ee962c7`。先前 PR https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/33 已关闭，由 #36 取代。#33 所评父提交 `a5bf56a06e4a7ba25b1615792cdbb902a4fde0eb`，结论 return，评审文件未合入 main |
| 评审阻塞 | B1/B2 已由 Reviewer 在 PR #36 判为闭合，可冻结规则。原阻塞保留为历史：B1 是 §3.1 U-指数「发布日起计入」与 §3.3 官方回溯进入池、R、s；B2 是 §4.5 每个 (N, 频率) 独立离场，与 §4.4 A 臂六组合成后的单一成交路径。跟进项是 G2/G3 工程，不阻止本次冻结，也不改下方 2026-10-24 Owner 决定表。若以后出现新的规则级阻塞，成批退回 Orchestrator。工程返工由 Manager 协调 |
| 连续执行 | Owner/Orchestrator 2026-10-25 锁定的 Manager 路径。第 (1)–(3) 步已完成：复审 `approve_with_follow_up`，`--ff-only` 合入 #32 与 #36，已打 `milestone/v3.1-prereg-freeze`。没有强推或改写 main，没有移动或删除任何既有 tag。(4) 冻结后工程已合入并已签收：官方回溯并保留发布日口径开关；防御与假期数据随 PR #39 进入 main（PR #29、#31 仍开着，不关闭）；v3.1 §4.5 单只离场；溢价接入执行链。Reviewer PR #40 结论 `approve_with_follow_up`。§4.5.6 缺价日到期离场仍是 rules-open，留给 Owner。下一步是正式引擎重跑设计期，end≤2015-12-31。(5) 把业务体检、共同口径复现/差异桥接、测试与覆盖、尝试预算、未决事项交给 Owner，然后本轮暂停。E2（A 臂、U-指数，设计期年化约 26.0%）是探索结果，不改规则去凑这个数 |
| 批准之后 | 已执行。`--ff-only` 合入 #32（变基尖端 `3a9415da1ac226a72e02c47c2b8fe25c0ee962c7`）与 #36（`1040035ee1d707368b58687994894189753843ac`）。tag `milestone/v3.1-prereg-freeze` → `1040035ee1d707368b58687994894189753843ac`。分支 `cursor/v3.1-owner-context`、`cursor/v3.1-prereg-rereview-705f` 已删除。不合入 #29、#31、#33 |
| 冻结之后的 Dev | 已合入。PR https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/39 `--ff-only`，变基后尖端 `26aba1cfa3365a0c6a72e5b0466de8517fd09d76`（原 `dae20a48d9ef8a8ce8df0e718fe9766874bf62a2`；其父 `dc75ca78698f30bb59e7adbbe5bce154e7b97392`）。四线：官方回溯并保留发布日口径开关；防御与假期数据；v3.1 §4.5 单只离场；溢价接入执行链。Reviewer 已签收 PR https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/40 ，结论 `approve_with_follow_up`，尖端 `b2a65c132a564f86e98b241ccab285ef67984916`。评审文件 `operations/reviews/2026-10-25-v3.1-d10-post-freeze.md`。分支 `cursor/d10-post-freeze-engineering-4c8c`、`cursor/review-d10-post-freeze-d36c` 已删除。下一步：Dev 正式设计期复跑，end≤2015-12-31。然后才把业务体检、共同口径复现/差异桥接、测试与覆盖、尝试预算、未决事项交给 Owner，本轮暂停。E2 约 26.0% 仍是探索结果，不改规则去凑。本登记不写新的组合收益。PR #29、#31 仍开着 |
| 缺价离场 | rules-open，留给 Owner。跟进项是 §4.5.6 缺价日到期离场挂单。Reviewer 登记：代码拒绝 0 与非有限价成交，挂单留到下一有效价，并有单测；这不等于已冻结的缺价与离场交互规则。不阻塞本次合入。本看板不把该实现写成已闭合规则。下一步仍是 Dev 正式设计期复跑，end≤2015-12-31 |
| 新会话 | 先读 `docs/project-intake/owner-vision-and-principles.md`。该文件已在 main |
| PR #29 | 仍 OPEN，本登记不关闭。防御与假期内容已随 PR #39 进入 main（变基后提交 `dc75ca78698f30bb59e7adbbe5bce154e7b97392`，不是 #29 尖端）。分支 `dev/v3-data-defensive-holiday` 仍指向 `c80aa56804c8927b762ada71b232c08a24b42fc5`。PR https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/29 |
| PR #31 | 仍 OPEN，本登记不关闭。它签的是 #29 分支，不是 PR #39。D10 工程包的签收是 PR #40（`approve_with_follow_up`）。分支 `cursor/v3-data-defensive-holiday-review-5690` @ `3ca5bb01f773ec338530e1d8eabb0a2b64233970`。PR https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/31 |
| G2 | 未开始。`milestone/v3-code-freeze` 仍不进入，直到 Owner 已看过正式设计期报告，且既有前置条件都满足（含 Orchestrator 设计期复诊结果与业务体检）。D10 执行顺序第 4 步的原文是：Owner 看过正式引擎复跑结果，然后代码冻结，然后一次性检验（Owner 批准）。本登记只记录该句，不把 G2 标成进行中或已完成。不输出 2016 年起的组合收益，不写 `results/v3/LOCK`。模拟盘与真钱须 Owner 另作明确 G3 批准。「让 Manager 继续」不是 G3 批准。正式设计期报告交给 Owner 后本轮暂停 |

## 开发线

状态只用这五个词: 未开始 / 进行中 / 待评审 / 已合入 / 阻塞。

| 线 | 状态 | 负责人 | 分支 | 依赖 | 最近更新 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| L1 数据层 | 已合入 | Dev | —（分支已删） | 无 | 2026-10-25 | ff-only 合入 `cursor/v3-l1-rework-review-37d1`。main `05d8476`。PR #25、#26 已合入。无 tag，无 LOCK |
| L2 回测引擎 | 已合入 | Dev | —（分支已删） | L1 已合入 | 2026-10-25 | ff-only 合入 `cursor/review-v3-l2-d546`。main `2b8ee0e`。PR #18、#19 已合入。无 tag，无 LOCK，无 2016+ 组合收益 |
| L3 溢价模块 | 已合入 | Dev | —（分支已删） | L1 QDII 数据 | 2026-10-25 | ff-only 合入 `cursor/v3-l3-review-2249`。main `4cecfad`。PR #20、#21 已合入。无 tag，无 LOCK，无 2016+ 组合收益。`allocate_container` / `adjust_weights` 已随 D10 冻结后工程合入（PR #39）。此处不改 L3 原签收 |
| L4 评估层 | 已合入 | Dev | —（分支已删） | L2 | 2026-10-25 | ff-only 合入 `cursor/v3-l4-review-4337`。main `2f29d40`。PR #22、#23 已合入。无 tag，无 LOCK，无 2016+ 组合收益。非有限收益、覆盖缺口与「B 不差于 A」解释改为 G2 前置，未开始 |
| D10 冻结后工程 | 已合入 | Dev；Reviewer 已签收 | —（分支已删） | v3.1 文本已冻结 | 2026-10-25 | PR #39 `--ff-only` 尖端 `26aba1c`。签收 PR #40 `approve_with_follow_up`，尖端 `b2a65c1`。无新 tag，无 LOCK，无新的组合收益。§4.5.6 缺价离场仍 rules-open，留给 Owner。下一步：Dev 正式设计期，end≤2015-12-31 |
| L5 运行与报告 | 未开始 | Dev 运行 / Reviewer 判定 | n/a（待 G2/G3） | G2 + G3 | 2026-10-25 | 仍等待 G2 + G3。此前不开分支、不跑全期 |

## 子任务

每条线四件事: 目标要点、改动面、验证、完成判据。条目从任务清单摘出，细则以清单和预注册为准。

### 开工第一步

- [x] Manager: 本看板 `operations/planning/phase2-board.md` 入库（本提交）
- [x] Dev: L1/L2 复述 ≤10 行；Reviewer 已确认，可开 `dev/v3-L1`
- [x] Reviewer: 评审文件已落地（见上）

### L1 数据层

- 目标要点: 补齐 v3 §3.2 全部容器的研究序列和执行 ETF 数据。
- 改动面: `config/v3/universe.toml`（代码、口径、指数发布日、基日、执行 ETF 及上市日、来源）；`src/v3/data/`；`incoming/`（原件 + MANIFEST + 哈希）；`data/market.sqlite`（run_id，写入前后 SHA256）。
- 验证: Reviewer 抽查 10% 序列对照一手来源；每个容器的发布日有原件或官网出处。
- 完成判据: 登记表每个容器字段齐全；`results/v3/inventory/coverage.csv`；Reviewer approve。

- [ ] 中证全指一级行业 10 个
- [ ] 科创50
- [ ] 恒生指数、恒生科技
- [ ] 上金所 Au9999；大商所豆粕期货价格指数；原油期货超额收益指数
- [ ] 中债 5 年、10 年国债财富指数
- [ ] 全部场内 QDII ETF/LOF：名单、上市日、单位净值、收盘价、成交额、申购状态（2021 年起）
- [ ] U-可交易各执行 ETF 的日线和成交额
- [x] 覆盖报告与 SHA256 登记后送审

已合入 main（`--ff-only`，来源 `review/v3-L1-sign`）:

- main: `98117155785124a45e67c8a93cdbd6e329c4d37b`
- PR https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/16 与 https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/17 已合入
- 分支 `dev/v3-L1`、`review/v3-L1-sign` 已删除
- 交付提交 `8a1d45e`（含冻结 `bfeb49c`）
- main 上 `config/v3/universe.toml` SHA256 `693b7d4dff91dff4b9bac4a0c1241eb4692f6b3cbd444965440a265ffa32aaff`
- 数据库文件使用 Git LFS
- 覆盖: 研究 137（ok 131 / partial 1 / gap 5），执行 153（ok 151 / gap 2）
- 合入前测试（LFS pull 之后）: 351 跑，350 过，0 失败，1 跳过
- 无回测，无 tag 变更
- [ ] Dev 跟进（与 L2 分开）: MANIFEST 513580 漂移，只走 emit

已合入 main（`--ff-only`，来源 `cursor/v3-l1-rework-review-37d1`）:

- main: `05d84760ece060c757008cb359b791cef51c2995`
- PR https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/25 与 https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/26 已 MERGED
- 分支 `dev/v3-L1-rework`、`cursor/v3-l1-rework-review-37d1` 已删除
- 原基线 main `a86dba0`。rebase 到合入前 main `a3811b98a80bf5e364a3aae1ffa1526d9b60fa73` 后快进
- 交付：原 `7f055a18d7124e9dc91f884ffd53f37c3333ed1a`，rebase 后 `c5d5cb29bc51e61a0b3e1e31ac337c998464e95a`
- 签收：原 `adbc20c1f5e9238bf9d2d78d967ffd1ec31aa4ad`，rebase 后 `05d84760ece060c757008cb359b791cef51c2995`（评审 `operations/reviews/2026-10-25-v3-L1-rework.md`，approve_with_follow_up）
- emit 按跟踪指数归并容器（一容器 = 一底层指数）。容器 137→81
- `config/v3/universe.toml` SHA256 `96592f553b9cc796922312b918ad3bc349766c84baab650032bc5c0a9a6aec8a`
- 库与 sqlite 未改。合入前测试（LFS pull 之后）: 443 跑，0 失败，1 跳过
- 无 tag，无 `results/v3/LOCK`。此处只登记 Reviewer 结论，不作判定
- 非阻塞 follow-up（只登记、不判定）：全文件 5 个代码也在对应 S2 容器。字面「任意代码只一次」不完全一致；主臂唯一成立
- 第 6 项业务体检未开始。必含内容已按 2026-10-25 Owner 方向扩充。第 7、第 8 项的防御与假期内容已随 PR #39 进入 main；PR #29、#31 仍开着，不关闭。体检出具见「D10」节与第 6 项。范围仍 end≤2015-12-31

### L2 回测引擎

- 目标要点: 实现 v3 §4 的打分、绝对过滤、持仓、合成、成本；臂 A、B、S1、S2；池 U-指数、U-可交易。
- 改动面: `src/v3/engine/`、`config/v3/arms.toml`、`tests/v3/`。
- 验证: ① 未来函数：改 t 日之后的数据，t 日及之前的权重不变；② 随机游走上策略相对随机对照无显著优势；③ BM-主复现第一阶段 `results/report/`，差距 ≤ 0.1 个百分点；④ 人工核对 3 个决策日的成本与换手。
- 完成判据: 测试全过；Reviewer 用独立脚本复算 A 臂设计期（≤2015）年化与最大回撤，差距 ≤ 0.1 个百分点。

- [x] Dev 已复述 L1+L2 理解（≤10 行）；Reviewer 已确认
- [ ] 打分、绝对过滤、持仓、合成、成本
- [ ] 四臂与两个池
- [ ] 每跑一个配置，向 `results/v3/trial-ledger.csv` 追加一行
- [ ] 运行器默认 end ≤ 2015-12-31；跑全期必须带预注册冻结 SHA；检测到 `results/v3/LOCK` 后拒绝再跑
- [ ] 四项测试通过后送审

已合入 main（`--ff-only`，来源 `cursor/review-v3-l2-d546`）:

- main: `2b8ee0e02fe7eed374218994633de110d6ed6a1b`
- PR https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/18 与 https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/19 已合入
- 分支 `dev/v3-L2`、`cursor/review-v3-l2-d546` 已删除
- 交付提交 `5dc81ff`；签收 `2b8ee0e`（评审 `operations/reviews/2026-10-25-v3-L2.md`，approve）
- 基线 main `9811715`
- 合入前测试（LFS pull 之后）: 388 跑，0 失败，1 跳过
- A 臂设计期 CAGR/MDD gap 0.000 pp（判据 ≤ 0.1pp）。此处只登记 Reviewer 结论，不作判定
- 无 tag，无 `results/v3/LOCK`，无 2016 年起的组合收益
- MANIFEST 513580 漂移不在本线，仍是单独的 emit 跟进

### L3 溢价模块

- 目标要点: 实现 v3 §5 的常态线、四种状态、风险预算、同指数选代码。
- 改动面: `src/v3/premium/`、`tests/v3/`。
- 验证: 同口径复现 `operations/reviews/diag/v3-explore/prem_episodes.py` 的事件日期；人工核对 2025-04、2026-03 两个时点的状态。
- 完成判据: 测试全过；Reviewer approve。

- [ ] 常态线、四种状态、风险预算（单只与合计上限以预注册为准）、同指数选代码
- [ ] 事件清单日期与探索脚本一致
- [ ] 两个时点人工核对后送审

已合入 main（`--ff-only`，来源 `cursor/v3-l3-review-2249`）:

- main: `4cecfad77458daea0e780cce383bc3e659fa9f59`
- PR https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/20 与 https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/21 已合入
- 分支 `dev/v3-L3`、`cursor/v3-l3-review-2249` 已删除
- 交付提交 `f171e48`；签收 `4cecfad`（评审 `operations/reviews/2026-10-25-v3-L3.md`，approve）
- 基线 main `2b8ee0e`
- 合入前测试（LFS pull 之后）: 411 跑，0 失败，1 跳过
- 49 段事件清单与 15 项状态抽查为 Reviewer 结论。此处只登记，不作判定
- 无 tag，无 `results/v3/LOCK`，无 2016 年起的组合收益
- 合入当时不阻塞的后续（本合入未做）: 执行器接入 `allocate_container` / `adjust_weights`；§5.5 污染检验段比较；§7.1 归属 L4
- 2026-10-25 Owner/Orchestrator 复核后：`allocate_container` / `adjust_weights` 接入 U-可交易执行链改为 G2 前置，未开始。同日 D10 把它列为 v3.1 冻结之后的 Dev 工作。该项已随 D10 冻结后工程合入（PR #39）。见「D10」节。此处不改 L3 签收结论

### L4 评估层

- 目标要点: 实现 v3 §6 五条判据，以及 §7 的滚动前推、回测过拟合概率、稳健性检验。
- 改动面: `src/v3/eval/`、`tests/v3/`。
- 验证: 随机对照在随机游走上的排名接近均匀；全是噪声的候选集上回测过拟合概率接近 0.5；紧缩夏普比率用公开示例核对。
- 完成判据: Reviewer 用独立实现复算设计期的 ①②③，数值一致。

- [ ] §6 五条判据
- [ ] §7 滚动前推、回测过拟合概率、稳健性（只报告）
- [ ] 随机游走、噪声候选集、公开示例三项核对
- [ ] 设计期 ①②③ 交 Reviewer 独立复算

已合入 main（`--ff-only`，来源 `cursor/v3-l4-review-4337`）:

- main: `2f29d4066709b8f8958164bba7c9098cba2803e9`
- PR https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/22 与 https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/23 已合入
- 分支 `dev/v3-L4`（原指向 `9ad9e6afbcf99353202776ca5e0e12c0171cab6f`）、`cursor/v3-l4-review-4337`（原指向 `2f29d4066709b8f8958164bba7c9098cba2803e9`）已删除
- 交付提交 `9ad9e6a`；签收 `2f29d40`（评审 `operations/reviews/2026-10-25-v3-L4.md`，approve_with_follow_up）
- 基线 main `4cecfad`
- 合入前测试（评审记录）: 439 跑，0 失败，1 跳过（L4 28）
- 设计期 ①②③ 为 Reviewer 工程核对。此处只登记，不作判定
- 无 tag，无 `results/v3/LOCK`，无 2016 年起的组合收益
- 合入当时不阻塞的后续（本合入未做，只登记、不判定）: (1) `criterion_2` 原始 pnl 含 NaN/inf、`book.net` 为 NaN；(2) 2006–2010 段未覆盖全段；(3) G3 全池 1,000 次随机对照；(4) B 臂相对 A 不自动判定
- 2026-10-25 Owner/Orchestrator 复核后：非有限日收益、2006–2010 覆盖，以及「B 不差于 A」的解释，改为 G2 前置，未开始。见下方专节。此处不改 L4 签收结论

### L5 运行与报告

- 目标要点: 跑全期，按 v3 §12 交付报告。
- 改动面: `results/v3/`、`docs/research/v3-report.md`、`docs/assets/v3/`。README 只在顶部加一行链接。
- 验证: Reviewer 独立复算记分卡的全部数值；尝试记录完整。
- 完成判据: Reviewer 出结论（G4），写入预注册 §11。

- [ ] 等到 G2 与 G3。此前不开分支、不跑全期
- [ ] 跑全期并留下 `results/v3/`
- [ ] 按 §12 写报告与图：一页结论、判据记分卡、6 类图、归因、逐年收益、尝试记录摘要、四项数据陷阱
- [ ] Reviewer 复算记分卡、检查尝试记录，结论写入预注册 §11

依赖 G2 与 G3。2026-10-25 优先级重排后仍然如此：L5 继续等待 G2 与 G3。G2 在 Owner 看过设计期复诊结果之前不进入。分支在这两道门通过前为 n/a。

## G2 前置（Owner/Orchestrator 2026-10-25；同日诊断与阻塞工作顺序重排；同日 D10 改写冻结后的开发顺序）

来源：Owner 2026-10-25（Asia/Taipei）对 main `2f29d4066709b8f8958164bba7c9098cba2803e9` 的 Orchestrator 复核；同日 Owner 方向把设计期诊断与 G2 阻塞工作顺序写入本看板。该次登记时 main 尖端 `cff054b696e39a19884a08ab176e3bc7f402f280`。

2026-10-25 D10 之后，派活以「D10」节为准。v3.1 已冻结（PR #36 `approve_with_follow_up`；PR #33 的 return 只评 `a5bf56a`，不是本次签收）。冻结后工程已合入并已签收（PR #39、#40，`approve_with_follow_up`）。下一步是 Dev 正式设计期复跑，end≤2015-12-31。§4.5.6 缺价离场仍 rules-open，留给 Owner。下列原登记保留：第 1 项 L1 返工已合入，不重开。第 7、第 8 项的内容已随 #39 在 main；PR #29、#31 仍开着，不关闭。第 2 项溢价接入与第 8 项假期修复已在该工程包内。第 3、第 4、第 6 项未开始。第 5 项看板 PR #14 已合入。

诊断（Orchestrator 事实，Manager 只登记，不判定）：

- 2011-08 之前只有 4–6 个可选标的
- 设计期全程缺少黄金、债券、商品
- 多资产轮动在设计期几乎无法检验

G2 阻塞工作顺序（Owner 2026-10-25 原序，保留备查。同日 D10 之后，派活以「D10」节为准）：

1. 第 7 项长历史防御资产。内容已随 PR #39 进入 main，并由 PR #40 按工程包签收（`approve_with_follow_up`）。PR #29 仍开着，不关闭。#31 不是这次签收。
2. 第 8 项：2012-10-30 美国休市被当成 NDX 单日暴跌，以及海外底层同类假期/零缺口审计。与第 7 项同一交付，已随 PR #39 进入 main。PR #29、#31 仍开着，不关闭。
3. 宇宙去重与溢价控制接线，并保持既有第 2–4 项。第 1 项 L1 返工（按底层指数归并）已合入，不重开。非阻塞 follow-up（5 个代码也出现在对应 S2 容器）仍只登记，不升为阻塞。第 2 项 `allocate_container` / `adjust_weights` 接入 U-可交易已随 PR #39 合入。第 3 项剩余的数据工作，以及第 4 项「B 不差于 A」解释，仍未开始。
4. D10 已登记。它批准的是 v3.1 规则，不是进入代码冻结。G2 仍未开始。代码冻结仍等到 Owner 已看过正式设计期报告，且既有前置条件都满足（含 Orchestrator 设计期复诊结果与业务体检）。D10 执行顺序第 4 步写明：正式引擎复跑之后，Owner 看过复跑结果，然后才是代码冻结。设计期业务体检未开始。Owner 看过业务体检仍然必要。「让 Manager 继续」不是 G3 批准。

代码冻结：G2 仍是未开始。不打 `milestone/v3-code-freeze`，直到 Owner 已看过正式设计期报告，且既有前置条件都满足（含 Orchestrator 设计期复诊结果与业务体检）。D10 执行顺序第 4 步的原文是：Owner 看过正式引擎复跑结果，然后代码冻结，然后一次性检验（Owner 批准）。此处只登记该句。「让 Manager 继续」不是 G3 批准。不输出 2016 年起的组合收益，不写 `results/v3/LOCK`。第 7、第 8 项的内容已随 PR #39 在 main；PR #29、#31 仍开着，不关闭。冻结后工程已合入，Reviewer PR #40 已签收，见「D10」节。下一步是 Dev 正式设计期复跑，end≤2015-12-31。正式设计期报告交给 Owner 后本轮暂停。L5 仍等待 G2 与 G3。本登记不新打 tag，不改业务代码，不改预注册正文。

1. **L1 返工** — 已合入。`--ff-only` 合入评审尖端 `cursor/v3-l1-rework-review-37d1` @ `05d84760ece060c757008cb359b791cef51c2995`（rebase 到当时 main `a3811b98a80bf5e364a3aae1ffa1526d9b60fa73`；交付原 `7f055a18d7124e9dc91f884ffd53f37c3333ed1a` → `c5d5cb29bc51e61a0b3e1e31ac337c998464e95a`，评审原 `adbc20c1f5e9238bf9d2d78d967ffd1ec31aa4ad` → `05d8476`）。PR https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/25 与 https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/26 已 MERGED。分支 `dev/v3-L1-rework`、`cursor/v3-l1-rework-review-37d1` 已删除。容器 137→81；`universe.toml` SHA256 `96592f553b9cc796922312b918ad3bc349766c84baab650032bc5c0a9a6aec8a`。无 tag，无 `results/v3/LOCK`。非阻塞 follow-up（只登记、不判定）：全文件 5 个代码也在对应 S2 容器。字面「任意代码只一次」不完全一致；主臂唯一成立。
2. **L3 遗留 1** — 已合入。`allocate_container` / `adjust_weights` 接入 U-可交易执行链在 PR #39。签收是 PR #40，不是 L3 原签收的改写。见「D10」节。
3. **数据** — 官方回溯与发布日口径开关、长历史黄金与中债 5/10 年财富、2012-10-29 纳指零价删除，已随 PR #39 在 main。PR #29 仍开着。本项仍留：2006–2010 覆盖；创业板指与美股人民币全收益的发布序列仍缺失，Dev 已在 PR #29 写明。Dev 在同一 PR 报告 `ndx100` 2012-11-01 不再是 +inf、2012-10-30 人民币收益不再是 −100%，评估层没有把非有限收益填 0。此处只登记该报告，不把本项改为完成，也不判定。补不齐则写明「缺失 → 对判定的影响」。
4. **「B 不差于 A」（§7.1）解释** — 未开始。工作顺序第 3 步。写入 G2 签收文件，预注册正文不改。须在 G3 前写定：① 的 36/60 月两个比例都 ≥ A；③ 通过段数 ≥ A 且最差一段超额 ≥ A。负责人：Reviewer 起草进 G2 签收，Manager 登记。
5. **看板 PR #14** — 已合入。https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/14 。不打 tag，不写 LOCK。
6. **业务体检（G2 前必须，Owner 要看）** — 未开始。
   - 时机：未开始。D10 未取消「Owner 须看过业务体检」。冻结后工程与 Reviewer 签收已完成。下一步是 Dev 正式设计期复跑（end≤2015-12-31），然后才出具体检。体检本身仍未开始。E2 约 26.0% 是探索结果，不改规则去凑。#29 与 #31 仍开着。正式设计期报告交给 Owner 后本轮暂停
   - 负责人：Dev 出具 `operations/reports/v3-design-period-brief.md`（附图）
   - 范围：设计期 end≤2015-12-31；不得含 2016 年起组合收益；数字只作参考不作判定
   - 内容（大白话）：A 臂 vs BM-主净值图 + 逐年收益；持仓面积图（大类/主要容器）+ 平均现金占比 + 年换手；仓位效应与选择效应拆分；各期可选标的数量；2008 与 2015 的持仓，以及这两段大跌期间的持仓与回撤；相对 BM-主归因（时期/大类）；判据①③④设计期数字（仅参考）
   - 完成后：Manager 提请 Owner。Owner 看过业务体检仍然必要。代码冻结仍等到 Owner 已看过 Orchestrator 设计期复诊结果。D10 执行顺序第 4 步另要求 Owner 看过正式引擎复跑结果，见「D10」节
7. **长历史防御资产** — 内容已随 PR #39 在 main，PR #40 按工程包签收（`approve_with_follow_up`）。PR #29 仍 OPEN，不关闭。#31 不是这次签收。
   - 分支 `dev/v3-data-defensive-holiday` @ `c80aa56804c8927b762ada71b232c08a24b42fc5`。基线 main `4c6d4b086d28bc58e1ec107210ce1b8125cea4c5`（`4c6d4b0`）
   - PR https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/29
   - 内容已在 main（PR #39 的 `dc75ca78698f30bb59e7adbbe5bce154e7b97392`）。PR #29 本身仍 OPEN。无新 tag，无 `results/v3/LOCK`。与第 8 项同一交付。工作记录：`operations/work_logs/2026-10-25-v3-data-defensive-holiday.md`
   - PR #29 开出时的派活原文：纳入黄金（例如上金所 Au9999）与中债国债总财富。按当时预注册 §3 发布日规则机械纳入：发布日前的数据不得用于 R 或 s。登记表更新只走 `python -m src.v3.data emit`，不得手改 `config/v3/universe.toml`。emit 之后由 Reviewer 签收。本项不改预注册正文。D10 把冻结后的数据工作改为官方回溯历史可用，并保留发布日口径开关。v3.1 已冻结。该对齐已随 PR #39 进入 main。PR #29 仍开着
   - 预注册 §3.2 现写的债券容器是 10 年国债、5 年国债（中债财富指数），商品里的黄金是上金所 Au9999。名称落在这些冻结容器上则机械补序列。对不上、因而要新容器或改规则时停手，由 Manager 升级 Owner（v3.1）
   - Dev 登记的事实（只登记，不判定）：
     - 黄金 `Au99.99` 为 partial，自 2008-08-11 起
     - `CBA04501`、`CBA03101` 自 2008-01-02 起
     - `CBA00601` 自 2002-01-04 起在库，不在池内。名称对不上 §3.2。按上一条既有规则升级 Owner，见「阻塞 / 待 Owner 决定」
     - #29 分支上 `config/v3/universe.toml` SHA256 `04ff3572ebd82a5159eaccced0bed5bc3531b732a1b11025f86021ebd0454be0`。main 上现为 D10 重 emit 的 `fda394d57b9109225bda0d459975125364b5f1bb5d1793c9ad080ec55f789b19`（Reviewer 签收一致）。L1 返工旧值 `96592f553b9cc796922312b918ad3bc349766c84baab650032bc5c0a9a6aec8a` 不再是 main 现行值
     - `data/market.sqlite` 写入后 SHA256 `3e3e6f1d594586da2abf28db5fa88b05c1cc91fa29adf061fc699e1b8d4bc1d6`
     - 创业板指、美股人民币全收益的发布序列仍缺失。Dev 已在 PR #29 写明
   - 溢价接线已随 PR #39 合入。设计期业务体检仍未开始，出具见第 6 项
8. **海外假期 / 零缺口** — 内容已随 PR #39 在 main。PR #29、#31 仍 OPEN，不关闭。#29 尖端仍是 `c80aa56804c8927b762ada71b232c08a24b42fc5`。签收工程包的是 PR #40，不是 #31。
   - 先前登记的现象仍保留：2012-10-30 美国休市被当成 NDX 暴跌（单日 -16.5%）。修法仍沿用已冻结的 §3.3：容器当日无有效收盘价时，用最近一个有效收盘价（例如美股或港股休市）。不改预注册
   - Dev 登记的事实（只登记，不判定）：纳指假期收盘 0 在 2012-10-29 已删除。海外底层非正收盘审计只此一行
   - 内容已在 main（随 PR #39）。无新 tag，无 `results/v3/LOCK`。PR #29 仍 OPEN
   - 第 3 项仍单独登记：Dev 报告 `ndx100` 2012-11-01 不再是 +inf。本项不把第 3 项改为完成。第 3 项其余工作状态仍是未开始

## 阻塞 / 待 Owner 决定

D10 已由 Owner 于 2026-10-25 批准内容，并已冻结，见「D10」节。Manager 只登记。Reviewer PR #36 结论 `approve_with_follow_up`（B1/B2 已闭合；G2/G3 工程跟进不阻止冻结）。先前 PR #33 对父提交 `a5bf56a06e4a7ba25b1615792cdbb902a4fde0eb` 的结论是 return，记录保留，不是本次签收。#33 已关闭。现行状态：v3.1 已冻结。`milestone/v3.1-prereg-freeze` → `1040035ee1d707368b58687994894189753843ac`。D10 冻结后工程已合入（PR #39、#40，`approve_with_follow_up`）。PR #29、#31 仍开着，不关闭。新的 rules-open 是 §4.5.6 缺价日到期离场，留给 Owner。`CBA00601` 仍无新容器授权，不放入池。Manager 不代决 G3、G5、v3.1 冻结后再改规则，也不代决尝试预算超过 60。「让 Manager 继续」不是 G3 批准。G2 与 `milestone/v3-code-freeze` 仍未进入。不写 `results/v3/LOCK`。正式设计期报告交给 Owner 后本轮暂停。

先前退回项仍记在下面，不删除。Reviewer 已在 PR #36 把 B1/B2 判为闭合。下方表格 B1–B7 仍是 2026-10-24 的 Owner 决定。本登记不改那张表。

- 评审阻塞 B1（PR #36 已判闭合）：§3.1 U-指数「发布日起计入」与 §3.3 官方回溯进入池、R、s（E1 完整宇宙语义）。
- 评审阻塞 B2（PR #36 已判闭合）：§4.5 每个 (N, 频率) 独立离场，与 §4.4 A 臂六组合成后的单一成交路径（E2 验收语义）。
- 规则未闭合（PR #40 跟进，不阻塞本次合入）：§4.5.6 缺价日到期离场挂单。留给 Owner。当前实现对 0 与非有限价不成交、挂单留到下一有效价。本看板不把该实现写成已冻结规则。

仍待 Owner 的名称问题，不是代码冻结：中债国债总财富 `CBA00601` 自 2002-01-04 起已在库，名称对不上预注册 v3 §3.2 的两只债券容器（10 年国债、5 年国债，中债财富指数）。Dev 未放入池。第 7 项已写明：对不上、因而要新容器或改规则时停手，由 Manager 升级 Owner。v3.1 文本未点名该代码。D10 批准的是官方回溯与单只 10% 离场。本看板不把 `CBA00601` 放进池。放进池需要规则点名。B1–B7 已由 Owner 于 2026-10-24 决定，写入冻结预注册与 `operations/reviews/2026-10-24-v3-prereg-review.md`（`89d18be`）。

G2 前的事项见「G2 前置」与「D10」。第 1 项已合入，不重开。第 7、第 8 项的内容已随 PR #39 在 main；PR #29 仍指向 `c80aa56804c8927b762ada71b232c08a24b42fc5`，#29 与 #31 仍开着，不关闭。冻结后工程（官方回溯与发布日开关、防御与假期数据、§4.5 单只离场、溢价接入执行链）已合入，Reviewer PR #40 结论 `approve_with_follow_up`。下一步是 Dev 正式设计期复跑，end≤2015-12-31。第 6 项业务体检未开始。代码冻结仍等到 Owner 看过正式设计期报告，且既有前置条件都满足。D10 执行顺序第 4 步写明，还要等 Owner 看过正式引擎复跑结果。Owner 看过业务体检仍然必要。「让 Manager 继续」不是 G3 批准。这些满足之前，G2 保持未开始。正式设计期报告交给 Owner 后本轮暂停。不写 `results/v3/LOCK`。

| # | Owner 决定 |
| --- | --- |
| B1 | 修改后的 (b)。G1 只冻结规则文字。`config/v3/universe.toml` 由 L1 按 §3 机械生成；每条含代码、发布日、口径、来源。Reviewer 逐条核对并记录 SHA 之后，才允许任何回测（含设计期）。冻结后只允许附录 1 的机械更新 |
| B2 | (a)。附录给出纳入程序和排除表：排除多资产 QDII、债券基金、货币基金、REITs；跨境商品归入商品大类。名单更新不计尝试，留下 inventory |
| B3 | (b)。写入 trial-ledger 的每一行都计入 60，也计入判据⑤。诊断走 debug 通道，debug 的 end 只允许 ≤ 2015-12-31 |
| B4 | (a)。①②③⑤ 的正式通过与否只在 G3 全期跑完之后判定。G2 之前的设计期数字只作工程核对 |
| B5 | (a)。U-可交易上①的 60 个月中位超额 ≤ 0，或②的分位 > 20%，则结论降一级 |
| B6 | (b)，并在附录抄录名单。引用 `config/portfolio.toml` 于 `milestone/phase1-archive`（`0dd93fa`） |
| B7 | (a)。与第一阶段 BM-主实现使用同一汇率序列 |

## 最近更新

2026-10-25（Asia/Taipei），Manager。登记 D10 冻结后工程已合入。状态：已合入。Reviewer 已签收，结论 `approve_with_follow_up`。合入前 main `bbce6b553985a008647ab6ddb4cb2875117593d9`（PR #41 已 MERGED，未重开）。PR #39 从 `dae20a48d9ef8a8ce8df0e718fe9766874bf62a2` 变基后 `--ff-only` 尖端 `26aba1cfa3365a0c6a72e5b0466de8517fd09d76`（父提交 `dc75ca78698f30bb59e7adbbe5bce154e7b97392`）。变基后的树相对原提交只多了 PR #41 的五份文档。只强推了功能分支 `cursor/d10-post-freeze-engineering-4c8c`，没有强推或改写 main。PR #40 只重放评审提交，`--ff-only` 尖端 `b2a65c132a564f86e98b241ccab285ef67984916`。评审文件 `operations/reviews/2026-10-25-v3.1-d10-post-freeze.md` 与 `operations/reviews/diag/v3/2026-10-25-d10-sha-verify.py` 已在 main。跟进项 §4.5.6 缺价日到期离场仍是 rules-open，留给 Owner，不阻塞本次合入，也不写成已冻结规则。下一步：Dev 跑正式设计期，end≤2015-12-31。本登记不写组合收益，不判定。`config/v3/universe.toml` SHA256 `fda394d57b9109225bda0d459975125364b5f1bb5d1793c9ad080ec55f789b19`（与 Reviewer 签收一致，本机 `sha256sum` 核对）。`data/market.sqlite` SHA256 沿用 Reviewer 签收 `3e3e6f1d594586da2abf28db5fa88b05c1cc91fa29adf061fc699e1b8d4bc1d6`（LFS；本登记未另跑回测）。PR #29、#31 仍 OPEN。#39 吸收了防御与假期内容，#29 尖端仍是 `c80aa56804c8927b762ada71b232c08a24b42fc5`。不关闭这两支。分支 `cursor/d10-post-freeze-engineering-4c8c`、`cursor/review-d10-post-freeze-d36c` 已删除。tag `milestone/v3.1-prereg-freeze` 仍指向 `1040035ee1d707368b58687994894189753843ac`（附注标签对象 `e3b55a7b8ce967a43341a3c9d02e6a0a42e2b508`）。没有 `milestone/v3-code-freeze`。没有 `results/v3/LOCK`。G2 仍未开始。

此前同日登记（v3.1 文本冻结。现行状态见上一条与「D10」节）：2026-10-25（Asia/Taipei），Manager。登记 v3.1 预注册冻结。状态：已冻结。`--ff-only` 合入 PR #32（变基尖端 `3a9415da1ac226a72e02c47c2b8fe25c0ee962c7`，所评父提交原 `1c52b5b725b60471280dbbca4779d7f66e808315`）与 PR #36（`1040035ee1d707368b58687994894189753843ac`）。规则修订提交原 `c6205e0985161aeba2335af582a758f91911e7cb`，变基后 `c29758a70c4bb3b29a1a8fd3cebed4d249e4da92`。Reviewer PR #36 结论 `approve_with_follow_up`；B1/B2 已闭合；G2/G3 工程跟进不阻止本次冻结。评审文件 `operations/reviews/2026-10-25-v3.1-prereg-rereview.md`。tag `milestone/v3.1-prereg-freeze`（附注标签对象 `e3b55a7b8ce967a43341a3c9d02e6a0a42e2b508`）→ `1040035ee1d707368b58687994894189753843ac`。合入前 main `1784cff7d30c0f2b33295be781f894738a3baa95`。没有强推或改写 main，没有移动或删除任何既有 tag。分支 `cursor/v3.1-owner-context`、`cursor/v3.1-prereg-rereview-705f` 已删除。`cursor/v31-rereview-board-07c4` 在合入时已不在远端。PR #33 已关闭，由 #36 取代，未当作签收。冻结后的 Dev 现已解除阻塞，尚未开工：官方回溯并保留发布日口径开关；假期与数据修复在冻结后门禁下与 #29、#31 对齐；v3.1 §4.5 单只离场；溢价接入执行链。然后 Reviewer 独立签收，再由正式引擎重跑设计期（end≤2015-12-31）。正式设计期报告交给 Owner 后本轮暂停。本登记仍不合入 #29、#31。G2 与 `milestone/v3-code-freeze` 仍未进入。不写 `results/v3/LOCK`。无 `src/` 业务代码变更。登记时冻结尖端 main 为 `1040035ee1d707368b58687994894189753843ac`。

此前同日登记（修订已推送 / 待复审。现行状态见上一条与「D10」节）：2026-10-25（Asia/Taipei），Manager。登记 Owner/Orchestrator 同日连续执行指令，以及 PR #32 的 v3.1 修订。当时状态为修订已推送 / 待复审，仍未冻结。分支 `cursor/v3.1-owner-context` 现 head `1c52b5b725b60471280dbbca4779d7f66e808315`。规则修订提交 `c6205e0985161aeba2335af582a758f91911e7cb`（修订 B1/B2，并写入交接）。交接 `operations/planning/2026-10-25-v3.1-revision-handoff.md` 在 #32 分支上，本登记时未必已在 main。先前 Reviewer PR #33 @ `fa825b7beccacda24004fdb52f48b3073fddf052` 只评父提交 `a5bf56a06e4a7ba25b1615792cdbb902a4fde0eb`。退回记录保留，不得当作新 head 的签收。不合入 #32、#33、#29、#31。Reviewer 复审通过新 head 之前不打 `milestone/v3.1-prereg-freeze`。不能快进则停下协调：不强推，不改写 main，不移动、不删除任何 tag。Manager 路径：(1) Reviewer 复审新 head，对照交接里仍待澄清的歧义；(2) 规则级阻塞成批退回 Orchestrator，工程返工由 Manager 协调；(3) 通过后 `--ff-only` 合入 #32 并打 `milestone/v3.1-prereg-freeze`；(4) 然后 Dev：官方回溯并保留发布日口径开关、数据修复对齐、§4.5 单只离场、溢价接入；Reviewer 独立签收；正式引擎重跑设计期，end≤2015-12-31；(5) 业务体检、共同口径复现/差异桥接、测试与覆盖、尝试预算、未决事项交给 Owner，然后本轮暂停。E2 约 26.0% 是探索结果，不改规则去凑。硬停：Owner 看过正式设计期报告且既有前置条件满足之前，不打 `milestone/v3-code-freeze`；不输出 2016 年起组合收益；不写 `results/v3/LOCK`；模拟盘与真钱须 Owner 另作明确 G3 批准。「让 Manager 继续」不是 G3 批准。冻结后的 Dev 以及 #29、#31 在冻结前继续阻塞，不因本指令越过门禁。`CBA00601` 仍无新容器授权，不放入池。登记时 main 为 `35a9c2f97f6bc0b30e5fff4a5c089383628efab4`。无 tag，无 `results/v3/LOCK`，不改业务代码，不改预注册正文。

此前同日登记（Reviewer 退回；当时状态为退回 / 待补字。现行状态见本文件最近一条与「D10」节）：2026-10-25（Asia/Taipei），Manager。登记 Reviewer 对 D10 / PR #32 的结论：return（退回 / 待补字）。评审 PR https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/33 ，分支 `cursor/v3.1-prereg-review-7a9f` @ `fa825b7beccacda24004fdb52f48b3073fddf052`，基线 `cursor/v3.1-owner-context`。评审文件 `operations/reviews/2026-10-25-v3.1-prereg-review.md`。所评父提交 `a5bf56a06e4a7ba25b1615792cdbb902a4fde0eb`。Manager 只登记，不代决两条歧义，并升级 Owner / Orchestrator 在 v3.1 增量里落字。评审阻塞 B1：§3.1 U-指数「发布日起计入」与 §3.3 官方回溯进入池、R、s（E1 完整宇宙语义）。评审阻塞 B2：§4.5 每个 (N, 频率) 独立离场，与 §4.4 A 臂六组合成后的单一成交路径（E2 验收语义）。评审阻塞 B1、B2 只指这次 v3.1 文本退回；2026-10-24 Owner 决定表的 B1–B7 保持原样。v3.1 正文补字且 Reviewer 复签为 `approve` 或 `approve_with_follow_up` 之前：不对 PR #32 做 `--ff-only`，不打 `milestone/v3.1-prereg-freeze`。本登记不合入 #32、#33、#29。冻结后的 Dev 工作仍阻塞，直到冻结。G2 与 `milestone/v3-code-freeze` 仍未进入。登记时 main 为 `81a1e78414b7b44d213fbb847ff8ad0f84c4dea3`。无 tag，无 `results/v3/LOCK`，不改业务代码，不改预注册正文。

此前同日登记（D10 批准；当时 v3.1 文本待评审。现行状态见本文件最近一条与「D10」节）：2026-10-25（Asia/Taipei），Manager。登记 Owner 决定 D10。预注册 v3.1 = 补全标的池（官方回溯历史在可得处可用）+ 单只 10% 离场，其他规则不变。PR https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/32 ，分支 `cursor/v3.1-owner-context` @ `a5bf56a06e4a7ba25b1615792cdbb902a4fde0eb`，基线 main `1d8155bce361d6c09b248cd6497d83dc4bbd73d2`。范围是文档、SVG 和诊断脚本，无业务代码。Reviewer 核对 `docs/prereg/etf-multiasset-rotation-prereg-v3.1.md` 可执行、无歧义，状态待评审。批准后 Manager `--ff-only` 合入 #32，并打 `milestone/v3.1-prereg-freeze`（D10 已授权）。冻结后的 Dev 工作未开始：官方回溯历史 + 发布日口径开关；2012-10-30 假期修复；v3.1 §4.5 单只离场；溢价接入执行链；随后 Reviewer 签收；正式引擎重跑设计期，对照 Orchestrator E2（A 臂、U-指数，设计期年化约 26.0%）。新会话先读 `docs/project-intake/owner-vision-and-principles.md`（文件在 PR #32）。PR #29 防御资产与假期修复仍待评审，v3.1 冻结后再与 D10 对齐；本登记不合入 #29。G2 与 `milestone/v3-code-freeze` 仍未进入，直到 Owner 已看过 Orchestrator 设计期复诊结果；Owner 看过业务体检仍然必要。D10 执行顺序第 4 步另写：Owner 看过正式引擎复跑结果之后才是代码冻结。此处只登记该句。登记时 main 为 `1d8155bce361d6c09b248cd6497d83dc4bbd73d2`。无 tag，无 `results/v3/LOCK`，不改业务代码，不改预注册正文。

此前同日登记（防御资产与假期；现行顺序以本文件最近一条和「D10」节为准）：2026-10-25（Asia/Taipei），Manager。登记 Dev 交付 Owner 同日工作顺序①+②（第 7 项长历史防御资产、第 8 项假期/零缺口），状态改为待评审。分支 `dev/v3-data-defensive-holiday` @ `c80aa56804c8927b762ada71b232c08a24b42fc5`，基线 main `4c6d4b086d28bc58e1ec107210ce1b8125cea4c5`。PR https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/29 。未合入，无 tag，无 `results/v3/LOCK`。只登记、不判定：`Au99.99` partial，自 2008-08-11；`CBA04501` / `CBA03101` 自 2008-01-02；`CBA00601` 自 2002-01-04 在库、不在池内，名称对不上 §3.2，按第 7 项既有规则升级 Owner（v3.1，Manager 不代决）；纳指 2012-10-29 收盘 0 已删除；海外非正收盘审计只此一行；分支上 `universe.toml` SHA256 `04ff3572ebd82a5159eaccced0bed5bc3531b732a1b11025f86021ebd0454be0`（main 上仍是 `96592f553b9cc796922312b918ad3bc349766c84baab650032bc5c0a9a6aec8a`）；`data/market.sqlite` 写入后 SHA256 `3e3e6f1d594586da2abf28db5fa88b05c1cc91fa29adf061fc699e1b8d4bc1d6`；创业板指与美股人民币全收益发布序列仍缺失，已在该 PR 写明。Reviewer §3 签收未完成。溢价接线与设计期业务体检仍未开始，等签收并合入之后。G2 与 `milestone/v3-code-freeze` 仍等 Owner 看过 Orchestrator 设计期复诊；看过业务体检仍然必要。登记时本看板所在 main 为 `4c6d4b0`。L5 仍等待 G2 与 G3。
