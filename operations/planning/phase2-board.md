# 第二阶段看板 · 三 bot 协作

Phase 2 看板。Manager、Dev、Reviewer 按预注册 v3 执行；本文件只做协调。

备注：Manager 状态汇报固定五段：本周完成 / 能做什么不能做什么 / 设计期业务信号 / 风险卡点 / 需要 Owner 的事。

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning
- Status: active
- Owner: L. Loric
- Maintainer: ETF Rotation Manager
- Date: 2026-10-24
- 权威顺序: `AGENTS.md` > `docs/prereg/etf-multiasset-rotation-prereg-v3.md` > `operations/planning/2026-10-24-phase2-task-list.md` > 群聊
- 任务清单: `operations/planning/2026-10-24-phase2-task-list.md`
- D9: `operations/planning/2026-10-24-d9-phase2-decisions.md`
- 预注册 v3: `docs/prereg/etf-multiasset-rotation-prereg-v3.md`

## 硬规则

- 规则写在预注册里。实现可以迭代。未经 Owner，不改规则。
- G3 之前：不计算、不输出截止日晚于 2015-12-31 的组合收益。溢价模块可以用 2021 年起的数据做机制检验，仍然不输出任何 2016 年起的组合收益。
- `config/v3/universe.toml` 在 main 上的登记表 SHA256 现为 `96592f553b9cc796922312b918ad3bc349766c84baab650032bc5c0a9a6aec8a`（L1 返工重签；上一版 `693b7d4dff91dff4b9bac4a0c1241eb4692f6b3cbd444965440a265ffa32aaff`）。设计期回测 end≤2015-12-31 可以开始。本次合入没有打 tag，也没有写 `results/v3/LOCK`。
- 合入 main、新建 tag、删除已合入分支只由 Manager 执行（任务清单 §1，Owner 2026-10-24 常设授权）。Manager 可用 `--ff-only` 合入已通过评审的 `dev/v3-*`。`milestone/v3-code-freeze` 仍由 Manager 打，但 Owner 已看过 Orchestrator 设计期复诊结果之前不打；Owner 看过业务体检仍然必要。G3、G5、预注册 v3.1、尝试预算 >60 仍须 Owner。不得删除或移动任何 tag，不得强推或改写 main。

## 门禁

| 门禁 | 内容 | 谁批准 | 状态 |
| --- | --- | --- | --- |
| G0 | 第一阶段封存、合同修订、D9 与预注册草稿入库 | Owner | 已完成 |
| G1 | 预注册已冻结。`milestone/v3-prereg-freeze` → `bfeb49cc65eb0ba419bc98348f1d643fac1211f6` | Owner | 已完成（2026-10-24/25） |
| G2 | 代码冻结：各开发线评审通过、全量测试 0 失败。Reviewer 批准后，Manager 打 `milestone/v3-code-freeze`。打 tag 前两条都要满足：Owner 已看过业务体检（第 6 项，未开始）；Owner 已看过 Orchestrator 设计期复诊结果。后者是更强门禁。此前不进入代码冻结 | Reviewer | 未开始 |
| G3 | 跑全期（含 2016 后），写 `results/v3/LOCK` | Owner 批准，Reviewer 执行 | 未开始 |
| G4 | 按 v3 §6、§7.3 出结论 | Reviewer | 未开始 |
| G5 | 是否进入前向模拟盘、是否上真钱 | Owner | 未开始 |

G2 仍是未开始。不进入代码冻结，也不打 `milestone/v3-code-freeze`，直到 Owner 已看过 Orchestrator 设计期复诊结果。Owner 须看过业务体检这一条仍然有效；更强的门是 Owner 已看过复诊。工作顺序见下方 G2 前置：先做第 7 项长历史防御资产和第 8 项假期类修复（均未开始），再清仍未开始的第 2–4 项（第 1 项 L1 返工已合入，不重开）。第 6 项业务体检未开始，必含内容已扩充。工作顺序 1–3 步完成前，不为冻结新增 Owner 决定。L5 仍等待 G2 与 G3，此前不开分支、不跑全期。

## G1 预注册修订与冻结

已完成（2026-10-24/25）。预注册状态行：已冻结（G1，2026-10-24，Owner 批准）。

- 冻结提交: `bfeb49cc65eb0ba419bc98348f1d643fac1211f6`（`prereg: freeze v3 at G1`）
- tag: `milestone/v3-prereg-freeze` → 该提交
- main: Manager 授权提交 `52a3aa861e4428cc1fcb343b5adcafb023782098`（父提交即冻结提交）
- `review/v3-prereg` 已 `--ff-only` 合入后删除
- 冻结时测试: 351 跑，350 过，0 失败，1 跳过
- 评审文件: `operations/reviews/2026-10-24-v3-prereg-review.md`（起点 `6f07a0f`；Owner 决定写入 `89d18be`）
- 过程 PR: https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/15 （分支已删除）
- 此后改 §3–§7 的规则、门槛、候选或预算即 v3.1，须 Owner。B1–B7 的决定见下方，已无待决项。登记表已随 L1 冻结在 main。

## 开发线

状态只用这五个词: 未开始 / 进行中 / 待评审 / 已合入 / 阻塞。

| 线 | 状态 | 负责人 | 分支 | 依赖 | 最近更新 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| L1 数据层 | 已合入 | Dev | —（分支已删） | 无 | 2026-10-25 | ff-only 合入 `cursor/v3-l1-rework-review-37d1`。main `05d8476`。PR #25、#26 已合入。无 tag，无 LOCK |
| L2 回测引擎 | 已合入 | Dev | —（分支已删） | L1 已合入 | 2026-10-25 | ff-only 合入 `cursor/review-v3-l2-d546`。main `2b8ee0e`。PR #18、#19 已合入。无 tag，无 LOCK，无 2016+ 组合收益 |
| L3 溢价模块 | 已合入 | Dev | —（分支已删） | L1 QDII 数据 | 2026-10-25 | ff-only 合入 `cursor/v3-l3-review-2249`。main `4cecfad`。PR #20、#21 已合入。无 tag，无 LOCK，无 2016+ 组合收益。`allocate_container` / `adjust_weights` 接入未开始，见 G2 前置第 2 项 |
| L4 评估层 | 已合入 | Dev | —（分支已删） | L2 | 2026-10-25 | ff-only 合入 `cursor/v3-l4-review-4337`。main `2f29d40`。PR #22、#23 已合入。无 tag，无 LOCK，无 2016+ 组合收益。非有限收益、覆盖缺口与「B 不差于 A」解释改为 G2 前置，未开始 |
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
- 第 6 项业务体检未开始。必含内容已按 2026-10-25 Owner 方向扩充。出具排在 G2 阻塞工作顺序第 1–3 步之后，再由 Orchestrator 做设计期复诊。范围仍 end≤2015-12-31

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
- 2026-10-25 Owner/Orchestrator 复核后：`allocate_container` / `adjust_weights` 接入 U-可交易执行链改为 G2 前置，未开始。同日优先级重排后，它落在工作顺序第 3 步（第 7、第 8 项之后）。见下方专节。此处不改 L3 签收结论

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

## G2 前置（Owner/Orchestrator 2026-10-25；同日诊断与阻塞工作顺序重排）

来源：Owner 2026-10-25（Asia/Taipei）对 main `2f29d4066709b8f8958164bba7c9098cba2803e9` 的 Orchestrator 复核；同日 Owner 方向把设计期诊断与 G2 阻塞工作顺序写入本看板。登记时 main 尖端 `cff054b696e39a19884a08ab176e3bc7f402f280`。第 1 项 L1 返工已合入，不重开。第 2–4 项与第 6–8 项未开始。第 5 项看板 PR #14 已合入。

诊断（Orchestrator 事实，Manager 只登记，不判定）：

- 2011-08 之前只有 4–6 个可选标的
- 设计期全程缺少黄金、债券、商品
- 多资产轮动在设计期几乎无法检验

G2 阻塞工作顺序（Owner 2026-10-25）：

1. 最高 — 第 7 项长历史防御资产。Dev → Reviewer。
2. 第 8 项：2012-10-30 美国休市被当成 NDX 单日暴跌。修好后审计全部海外底层的同类假期/零缺口。Dev → Reviewer。
3. 宇宙去重与溢价控制接线，并保持既有第 2–4 项。第 1 项 L1 返工（按底层指数归并）已合入，不重开。非阻塞 follow-up（5 个代码也出现在对应 S2 容器）仍只登记，不升为阻塞。第 2 项 `allocate_container` / `adjust_weights` 接入 U-可交易仍未开始。第 3 项剩余的数据工作，以及第 4 项「B 不差于 A」解释，仍未开始。
4. 上述 1–3 步完成后：Manager 提请 Owner，Orchestrator 做设计期复诊。在此之前不为代码冻结新增 Owner 决定。

代码冻结：不得进入 `milestone/v3-code-freeze`，直到 Owner 已看过 Orchestrator 复诊结果。先前「Owner 须看过业务体检」仍然有效；更强的门是 Owner 已看过复诊。第 6 项不并入第 2–4 项的群内闭环。第 7、第 8 项与第 2–4 项先由 Dev → Reviewer 做完，再进入工作顺序第 4 步。G2 仍是未开始。L5 仍等待 G2 与 G3。本看板不打 tag，不写 `results/v3/LOCK`，不改业务代码，不改预注册正文。

1. **L1 返工** — 已合入。`--ff-only` 合入评审尖端 `cursor/v3-l1-rework-review-37d1` @ `05d84760ece060c757008cb359b791cef51c2995`（rebase 到当时 main `a3811b98a80bf5e364a3aae1ffa1526d9b60fa73`；交付原 `7f055a18d7124e9dc91f884ffd53f37c3333ed1a` → `c5d5cb29bc51e61a0b3e1e31ac337c998464e95a`，评审原 `adbc20c1f5e9238bf9d2d78d967ffd1ec31aa4ad` → `05d8476`）。PR https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/25 与 https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/26 已 MERGED。分支 `dev/v3-L1-rework`、`cursor/v3-l1-rework-review-37d1` 已删除。容器 137→81；`universe.toml` SHA256 `96592f553b9cc796922312b918ad3bc349766c84baab650032bc5c0a9a6aec8a`。无 tag，无 `results/v3/LOCK`。非阻塞 follow-up（只登记、不判定）：全文件 5 个代码也在对应 S2 容器。字面「任意代码只一次」不完全一致；主臂唯一成立。
2. **L3 遗留 1** — 未开始。工作顺序第 3 步。Dev：`allocate_container` / `adjust_weights` 接入 U-可交易执行链。
3. **数据** — 未开始。工作顺序第 3 步。长历史黄金、中债国债总财富在第 7 项；2012-10-30 假期误记在第 8 项。本项仍留：修 `ndx100` 2012-11-01 的 inf 及所有非有限日收益（数据层或引擎层保证有限值；禁止评估层填 0）。补齐 2006–2010 覆盖。补齐美股人民币全收益、创业板指。补不齐则写明「缺失 → 对判定的影响」。
4. **「B 不差于 A」（§7.1）解释** — 未开始。工作顺序第 3 步。写入 G2 签收文件，预注册正文不改。须在 G3 前写定：① 的 36/60 月两个比例都 ≥ A；③ 通过段数 ≥ A 且最差一段超额 ≥ A。负责人：Reviewer 起草进 G2 签收，Manager 登记。
5. **看板 PR #14** — 已合入。https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/14 。不打 tag，不写 LOCK。
6. **业务体检（G2 前必须，Owner 要看）** — 未开始。
   - 时机：工作顺序第 1–3 步完成之后，Dev 出具，随后 Orchestrator 做设计期复诊
   - 负责人：Dev 出具 `operations/reports/v3-design-period-brief.md`（附图）
   - 范围：设计期 end≤2015-12-31；不得含 2016 年起组合收益；数字只作参考不作判定
   - 内容（大白话）：A 臂 vs BM-主净值图 + 逐年收益；持仓面积图（大类/主要容器）+ 平均现金占比 + 年换手；仓位效应与选择效应拆分；各期可选标的数量；2008 与 2015 的持仓，以及这两段大跌期间的持仓与回撤；相对 BM-主归因（时期/大类）；判据①③④设计期数字（仅参考）
   - 完成后：Manager 提请 Owner。Orchestrator 做设计期复诊。Owner 看过业务体检仍然必要。代码冻结还要等 Owner 看过复诊结果
7. **长历史防御资产（最高优先级）** — 未开始。工作顺序第 1 步。负责人：Dev → Reviewer。
   - 纳入黄金（例如上金所 Au9999，自 2002）与中债国债总财富
   - 按预注册 §3 发布日规则机械纳入：发布日前的数据不得用于 R 或 s。登记表更新只走 `python -m src.v3.data emit`，不得手改 `config/v3/universe.toml`
   - emit 之后由 Reviewer 签收
   - 预注册 §3 现写的债券容器是 10 年国债、5 年国债（中债财富指数），商品里的黄金是上金所 Au9999。名称落在这些冻结容器上则机械补序列。对不上、因而要新容器或改规则时停手，由 Manager 升级 Owner（v3.1）。本项不改预注册正文
   - 与诊断事实对齐：设计期缺黄金、债券、商品。本项派活是黄金与中债国债总财富
8. **海外假期 / 零缺口** — 未开始。工作顺序第 2 步。负责人：Dev → Reviewer。
   - 事实：2012-10-30 美国休市被当成 NDX 暴跌（单日 -16.5%）
   - 先修这一处。修法沿用已冻结的 §3.3：容器当日无有效收盘价时，用最近一个有效收盘价（例如美股或港股休市）。不改预注册
   - 修好后审计全部海外底层，查同类假期/零缺口
   - 第 3 项的 `ndx100` 2012-11-01 inf 与全部非有限日收益仍单独登记，状态未开始

## 阻塞 / 待 Owner 决定

待 Owner 决定：无。工作顺序第 1–3 步完成之前，不为代码冻结新增 Owner 决定。这三步完成后，Manager 提请 Owner，由 Orchestrator 做设计期复诊。B1–B7 已由 Owner 于 2026-10-24 决定，写入冻结预注册与 `operations/reviews/2026-10-24-v3-prereg-review.md`（`89d18be`）。Manager 不代决 v3.1、G3、G5，也不代决尝试预算超过 60。

G2 前的事项见「G2 前置」。第 1 项已合入，不重开。第 7 项长历史防御资产、第 8 项假期/零缺口、第 2–4 项、第 6 项业务体检均为未开始。代码冻结还要等 Owner 看过复诊结果；Owner 看过业务体检仍然必要。这两条满足之前，G2 保持未开始。

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

2026-10-25（Asia/Taipei），Manager。登记 Owner 方向：Orchestrator 设计期诊断与 G2 阻塞工作顺序重排。诊断只作事实登记，不是判定：2011-08 之前可选标的只有 4–6 个；设计期全程缺少黄金、债券、商品；多资产轮动在设计期几乎无法检验。工作顺序：① 最高，第 7 项长历史防御资产（黄金，例如上金所 Au9999 自 2002；中债国债总财富），按 §3 发布日规则经 emit 机械纳入，Reviewer 签收，Dev → Reviewer，未开始；② 第 8 项，2012-10-30 美国休市被当成 NDX 单日 -16.5%，修好后审计全部海外底层的同类假期/零缺口，Dev → Reviewer，未开始；③ 宇宙去重与溢价接线沿用既有项，L1 返工已合入且不重开，第 2 项 L3 接入与第 3–4 项未开始；④ ①–③完成后 Manager 提请 Owner，Orchestrator 做设计期复诊。第 6 项业务体检未开始，须含仓位效应与选择效应拆分、各期可选标的数量、2008 与 2015 持仓；范围仍 ≤2015-12-31，不含 2016 年起组合收益。不进入 `milestone/v3-code-freeze`，直到 Owner 看过复诊结果；看过业务体检仍然必要。①–③完成前不为冻结新增 Owner 决定。登记时 main `cff054b696e39a19884a08ab176e3bc7f402f280`。L1 返工仍是已合入（main `05d84760ece060c757008cb359b791cef51c2995`）。无 tag，无 `results/v3/LOCK`。G2 仍是未开始。L5 仍等待 G2 与 G3。
