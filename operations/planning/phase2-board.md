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
- 三个 bot 不合入 main，不创建、不删除、不移动任何 tag。合入与 tag 由 Owner 安排。

## 门禁

| 门禁 | 内容 | 谁批准 | 状态 |
| --- | --- | --- | --- |
| G0 | 第一阶段封存、合同修订、D9 与预注册草稿入库 | Owner | 已完成 |
| G1 | 预注册冻结。修订在 `review/v3-prereg`；Owner 确认后打 `milestone/v3-prereg-freeze` | Owner | 待批准 |
| G2 | 代码冻结：各开发线评审通过、全量测试 0 失败，打 `milestone/v3-code-freeze` | Reviewer | 未开始 |
| G3 | 跑全期（含 2016 后），写 `results/v3/LOCK` | Owner 批准，Reviewer 执行 | 未开始 |
| G4 | 按 v3 §6、§7.3 出结论 | Reviewer | 未开始 |
| G5 | 是否进入前向模拟盘、是否上真钱 | Owner | 未开始 |

## G1 前：预注册修订轨

Owner 开工说明。G1 冻结之前走这条轨。

- 分支: `review/v3-prereg`
- 流转: Reviewer 提出 → Dev 回应 → Manager 推进
- 歧义、实现细节、边界情况: 取更保守的读法，改预注册，并在评审文件记下「问题 → 决定 → 理由」
- 若改动改变 §3–§7 的规则、门槛、候选或预算: 列入下方「待 Owner 决定」，写明选项和推荐；不单独拍板
- 修订结束后，Manager 向 Owner 提交 G1 请求: 分支、最新 SHA、变更摘要、待 Owner 决定清单
- G1 之前: Dev 可以在 `dev/v3-L1` 上开始取数（L1 与规则无关），不得运行任何回测结果

评审落点: `operations/reviews/2026-10-24-v3-prereg-review.md`。

## 开发线

状态只用这五个词: 未开始 / 进行中 / 待评审 / 已合入 / 阻塞。

| 线 | 状态 | 负责人 | 分支 | 依赖 | 最近更新 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| L1 数据层 | 进行中 | Dev | `dev/v3-L1` | 无 | 2026-10-24 | G1 前可取数，禁止跑回测结果 |
| L2 回测引擎 | 未开始 | Dev | `dev/v3-L2` | L1 登记表（可并行开发） | — | 默认 end≤2015-12-31。先复述理解，Reviewer 确认后再写代码 |
| L3 溢价模块 | 未开始 | Dev | `dev/v3-L3` | L1 QDII 数据 | — | 可与 L2 并行。2021 年起数据只做机制检验 |
| L4 评估层 | 未开始 | Dev 实现 / Reviewer 复算 | `dev/v3-L4` | L2 | — | — |
| L5 运行与报告 | 未开始 | Dev 运行 / Reviewer 判定 | n/a（待 G2/G3） | G2 + G3 | — | G2、G3 之前不开分支、不跑全期 |

## 子任务

每条线四件事: 目标要点、改动面、验证、完成判据。条目从任务清单摘出，细则以清单和预注册为准。

### 开工第一步

- [x] Manager: 本看板 `operations/planning/phase2-board.md` 入库（本提交）
- [ ] Dev: 用不超过 10 行复述 L1 与 L2 的理解；Reviewer 确认前不写代码
- [ ] Reviewer: 预注册 v3 的歧义与缺口写入 `operations/reviews/2026-10-24-v3-prereg-review.md`

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
- [ ] 覆盖报告与 SHA256 登记后送审

G1 前只取数。不跑回测结果。

### L2 回测引擎

- 目标要点: 实现 v3 §4 的打分、绝对过滤、持仓、合成、成本；臂 A、B、S1、S2；池 U-指数、U-可交易。
- 改动面: `src/v3/engine/`、`config/v3/arms.toml`、`tests/v3/`。
- 验证: ① 未来函数：改 t 日之后的数据，t 日及之前的权重不变；② 随机游走上策略相对随机对照无显著优势；③ BM-主复现第一阶段 `results/report/`，差距 ≤ 0.1 个百分点；④ 人工核对 3 个决策日的成本与换手。
- 完成判据: 测试全过；Reviewer 用独立脚本复算 A 臂设计期（≤2015）年化与最大回撤，差距 ≤ 0.1 个百分点。

- [ ] Dev 复述 L1+L2 理解（≤10 行）；Reviewer 确认后再编码
- [ ] 打分、绝对过滤、持仓、合成、成本
- [ ] 四臂与两个池
- [ ] 每跑一个配置，向 `results/v3/trial-ledger.csv` 追加一行
- [ ] 运行器默认 end ≤ 2015-12-31；跑全期必须带预注册冻结 SHA；检测到 `results/v3/LOCK` 后拒绝再跑
- [ ] 四项测试通过后送审

依赖 L1 登记表，可与取数并行开发。默认样本截止 2015-12-31。

### L3 溢价模块

- 目标要点: 实现 v3 §5 的常态线、四种状态、风险预算、同指数选代码。
- 改动面: `src/v3/premium/`、`tests/v3/`。
- 验证: 同口径复现 `operations/reviews/diag/v3-explore/prem_episodes.py` 的事件日期；人工核对 2025-04、2026-03 两个时点的状态。
- 完成判据: 测试全过；Reviewer approve。

- [ ] 常态线、四种状态、风险预算（单只与合计上限以预注册为准）、同指数选代码
- [ ] 事件清单日期与探索脚本一致
- [ ] 两个时点人工核对后送审

依赖 L1 的 QDII 数据。可与 L2 并行。2021 年起的数据只用于机制检验，不输出组合收益。

### L4 评估层

- 目标要点: 实现 v3 §6 五条判据，以及 §7 的滚动前推、回测过拟合概率、稳健性检验。
- 改动面: `src/v3/eval/`、`tests/v3/`。
- 验证: 随机对照在随机游走上的排名接近均匀；全是噪声的候选集上回测过拟合概率接近 0.5；紧缩夏普比率用公开示例核对。
- 完成判据: Reviewer 用独立实现复算设计期的 ①②③，数值一致。

- [ ] §6 五条判据
- [ ] §7 滚动前推、回测过拟合概率、稳健性（只报告）
- [ ] 随机游走、噪声候选集、公开示例三项核对
- [ ] 设计期 ①②③ 交 Reviewer 独立复算

依赖 L2。

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

无。

改动预注册 §3–§7 的规则、门槛、候选或预算时，写在这里：事项、选项、推荐。Manager 不代 Owner 决定。

## 最近更新

2026-10-24，Manager，Phase 2 kickoff。
