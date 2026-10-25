# 第二阶段看板 · 三 bot 协作

Phase 2 看板。Manager、Dev、Reviewer 按预注册 v3 执行；本文件只做协调。

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
- `config/v3/universe.toml` 已在 main 冻结，SHA256 `693b7d4dff91dff4b9bac4a0c1241eb4692f6b3cbd444965440a265ffa32aaff`。设计期回测 end≤2015-12-31 可以开始。本次 L1 合入没有跑回测，也没有改 tag。
- 合入 main、新建 tag、删除已合入分支只由 Manager 执行（任务清单 §1，Owner 2026-10-24 常设授权）。Manager 可用 `--ff-only` 合入已通过评审的 `dev/v3-*`，并在 G2 条件满足时打 `milestone/v3-code-freeze`。G3、G5、预注册 v3.1、尝试预算 >60 仍须 Owner。不得删除或移动任何 tag，不得强推或改写 main。

## 门禁

| 门禁 | 内容 | 谁批准 | 状态 |
| --- | --- | --- | --- |
| G0 | 第一阶段封存、合同修订、D9 与预注册草稿入库 | Owner | 已完成 |
| G1 | 预注册已冻结。`milestone/v3-prereg-freeze` → `bfeb49cc65eb0ba419bc98348f1d643fac1211f6` | Owner | 已完成（2026-10-24/25） |
| G2 | 代码冻结：各开发线评审通过、全量测试 0 失败。Reviewer 批准后，Manager 打 `milestone/v3-code-freeze` | Reviewer | 未开始 |
| G3 | 跑全期（含 2016 后），写 `results/v3/LOCK` | Owner 批准，Reviewer 执行 | 未开始 |
| G4 | 按 v3 §6、§7.3 出结论 | Reviewer | 未开始 |
| G5 | 是否进入前向模拟盘、是否上真钱 | Owner | 未开始 |

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
| L1 数据层 | 已合入 | Dev | —（分支已删） | 无 | 2026-10-24 | ff-only 合入 `review/v3-L1-sign`。main `98117155`。PR #16、#17 已合入。无回测，无 tag 变更 |
| L2 回测引擎 | 已合入 | Dev | —（分支已删） | L1 已合入 | 2026-10-25 | ff-only 合入 `cursor/review-v3-l2-d546`。main `2b8ee0e`。PR #18、#19 已合入。无 tag，无 LOCK，无 2016+ 组合收益 |
| L3 溢价模块 | 已合入 | Dev | —（分支已删） | L1 QDII 数据 | 2026-10-25 | ff-only 合入 `cursor/v3-l3-review-2249`。main `4cecfad`。PR #20、#21 已合入。无 tag，无 LOCK，无 2016+ 组合收益 |
| L4 评估层 | 进行中 | Dev 实现 / Reviewer 复算 | `dev/v3-L4` | L2 | 2026-10-25 | 从 main `4cecfad` 开出。§6 判据 + §7 滚动前推/过拟合/稳健性；设计期 end≤2015。未合入 main，无 tag，无 LOCK |
| L5 运行与报告 | 未开始 | Dev 运行 / Reviewer 判定 | n/a（待 G2/G3） | G2 + G3 | — | G2、G3 之前不开分支、不跑全期 |

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
- 不阻塞的后续（本合入未做）: 执行器接入 `allocate_container` / `adjust_weights`；§5.5 污染检验段比较；§7.1 归属 L4

### L4 评估层

- 目标要点: 实现 v3 §6 五条判据，以及 §7 的滚动前推、回测过拟合概率、稳健性检验。
- 改动面: `src/v3/eval/`、`tests/v3/`。
- 验证: 随机对照在随机游走上的排名接近均匀；全是噪声的候选集上回测过拟合概率接近 0.5；紧缩夏普比率用公开示例核对。
- 完成判据: Reviewer 用独立实现复算设计期的 ①②③，数值一致。

- [ ] §6 五条判据
- [ ] §7 滚动前推、回测过拟合概率、稳健性（只报告）
- [ ] 随机游走、噪声候选集、公开示例三项核对
- [ ] 设计期 ①②③ 交 Reviewer 独立复算

进行中。分支 `dev/v3-L4` 从 main `4cecfad` 开出。§6 判据 + §7 滚动前推/过拟合/稳健性；设计期 end≤2015。未合入 main，无 tag，无 LOCK。依赖 L2。

### L5 运行与报告

- 目标要点: 跑全期，按 v3 §12 交付报告。
- 改动面: `results/v3/`、`docs/research/v3-report.md`、`docs/assets/v3/`。README 只在顶部加一行链接。
- 验证: Reviewer 独立复算记分卡的全部数值；尝试记录完整。
- 完成判据: Reviewer 出结论（G4），写入预注册 §11。

- [ ] 等到 G2 与 G3。此前不开分支、不跑全期
- [ ] 跑全期并留下 `results/v3/`
- [ ] 按 §12 写报告与图：一页结论、判据记分卡、6 类图、归因、逐年收益、尝试记录摘要、四项数据陷阱
- [ ] Reviewer 复算记分卡、检查尝试记录，结论写入预注册 §11

依赖 G2 与 G3。分支在这两道门通过前为 n/a。

## 阻塞 / 待 Owner 决定

无。B1–B7 已由 Owner 于 2026-10-24 决定，写入冻结预注册与 `operations/reviews/2026-10-24-v3-prereg-review.md`（`89d18be`）。Manager 不代决 v3.1、G3、G5，也不代决尝试预算超过 60。

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

2026-10-25，Manager，L4 改为进行中：`dev/v3-L4` 从 main `4cecfad` 开出。§6 判据 + §7 滚动前推/过拟合/稳健性；设计期 end≤2015。未合入 main，无 tag，无 LOCK。
