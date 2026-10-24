# 第二阶段任务清单 · 三 bot 协作（2026-10-24）

## Metadata
- Project: ETF_Rotation_Quant · Document type: planning · Status: active
- Owner: L. Loric · 起草: orchestrator（Notion AI）
- 权威顺序: `AGENTS.md` > 预注册 `docs/prereg/etf-multiasset-rotation-prereg-v3.md` > 本清单 > 群聊
- 决定依据: D9（`operations/planning/2026-10-24-d9-phase2-decisions.md`）

## 0. 给群组的一段话
目标：按预注册 v3 建一套多资产动态 topN 轮动（含现金）的回测系统，按 v3 §6 的五条判据给出结论，并按 v3 §12 的格式交付报告。规则写在预注册里，**你们可以自由迭代实现，但不能改规则**。仓库是唯一真相来源，群聊只用于协调。

## 1. 角色与权限
| 角色 | 负责 | 可以 | 不可以 |
|---|---|---|---|
| **ETF Rotation Manager** | 拆任务、派活、追进度；维护看板 `operations/planning/phase2-board.md` 和尝试记录汇总；每天在群里发一次状态；按 §5 向 Owner 升级 | 修改看板和工作记录；重新分配开发线；暂停某条线 | 写业务代码；判定结果；改预注册；替 Owner 批准门禁 |
| **ETF Rotation Dev** | 取数、写代码、跑回测；可开多个并行环境，每条开发线一个分支 `dev/v3-<线名>` | 在自己的分支和自己负责的文件里自由迭代；写 `operations/work_logs/` | 判定通过；写或删 `results/v3/LOCK`；改预注册 §0–§10；修改第一阶段文件 |
| **ETF Rotation Reviewer** | 独立复核每次合入；保管冻结与 LOCK；最后按判据出结论 | 写 `operations/reviews/`；在 `operations/reviews/diag/v3/` 写**自己的**复算脚本；给出 approve / approve_with_follow_up / return_to_planning | 改业务代码；复用 Dev 的计算代码做复算；放宽判据 |
| Owner | 只在门禁 G1、G3、G5 拍板 | — | — |

**合入 main、打 tag 由 Owner 安排执行**，三个 bot 都不自行合入、不打 tag。需要合入时，由 Manager 在群里提请 Owner。

**tag 与分支纪律（硬规则）**：任何 bot 都**不得删除或移动任何 tag**（含 `milestone/*`），也不得删除、强推或改写 `main` 及他人的分支。仓库未对 tag 设保护规则，这条只靠纪律执行。以往的 tag 删除都是 Owner 明确要求清理时才执行的；今后也只有 Owner 在群里明确点名要求时才可以删除，执行后写入工作记录（tag 名 + 原指向提交）。

**独立性要求**：Reviewer 与 Dev 应使用不同的底层模型。做不到时，Reviewer 必须用独立实现（不同的代码、尽量不同的库）复算关键数字，并在评审里写明用了什么方法。

## 2. 门禁
| 门禁 | 内容 | 谁批准 |
|---|---|---|
| G0 | 已完成：第一阶段封存、合同修订、D9 与预注册草稿入库 | Owner |
| G1 | 预注册冻结：打 `milestone/v3-prereg-freeze` | Owner |
| G2 | 代码冻结：所有开发线评审通过、全量测试 0 失败，打 `milestone/v3-code-freeze` | Reviewer |
| G3 | 跑全期（含 2016 后）：写 `results/v3/LOCK` | Owner 批准，Reviewer 执行 |
| G4 | 结论：Reviewer 按 v3 §6、§7.3 出结论 | Reviewer |
| G5 | 是否进入前向模拟盘、是否上真钱 | Owner |

G2 之前只允许运行 end ≤ 2015-12-31 的回测；溢价模块可以用 2021 年以后的数据（它属于 U-可交易的机制检验，见 v3 §5.5），但不得计算或输出任何 2016 年以后的组合收益。

## 3. 开发线
每条线写四件事：目标、改动面、验证、完成判据。可并行的线标在"依赖"里。

### L1 数据层（Dev）
- **目标**：补齐 v3 §3.2 所有容器的研究序列和执行 ETF 数据。
- **改动面**：`config/v3/universe.toml`（容器登记：代码、全收益或价格口径、指数发布日、基日、执行 ETF 列表及上市日、数据来源）；`src/v3/data/`；`incoming/`（原件 + MANIFEST + 哈希）；写入 `data/market.sqlite`，登记 run_id 和写入前后的 SHA256。
- **需要补的数据**：中证全指一级行业 10 个；科创50；恒生指数、恒生科技；上金所 Au9999；大商所豆粕期货价格指数；原油期货超额收益指数；中债 5 年、10 年国债财富指数；所有场内 QDII ETF/LOF 的名单、上市日、单位净值、收盘价、成交额、申购状态（2021 年起）；U-可交易各执行 ETF 的日线和成交额。
- **验证**：Reviewer 抽查 10% 的序列与一手来源核对；每个容器的发布日要有原件或官网出处。
- **完成判据**：`config/v3/universe.toml` 每个容器字段齐全；数据覆盖报告 `results/v3/inventory/coverage.csv`；Reviewer approve。

### L2 回测引擎（Dev；依赖：L1 的登记表，可先用现有数据并行开发）
- **目标**：实现 v3 §4 的打分、绝对过滤、持仓、合成、成本；A、B、S1、S2 四个臂；U-指数和 U-可交易两个池。
- **改动面**：`src/v3/engine/`、`config/v3/arms.toml`、`tests/v3/`。
- **必须包含**：每跑一个配置自动追加一行到 `results/v3/trial-ledger.csv`；运行器默认 end ≤ 2015-12-31，跑全期必须带预注册冻结 SHA，且检测到 `results/v3/LOCK` 后拒绝再跑。
- **验证（测试）**：① 未来函数测试：改动 t 日之后的数据，t 日及之前的权重不变；② 随机游走测试：纯随机数据上，策略相对随机对照没有显著优势；③ BM-主 复现第一阶段 `results/report/` 的数字，差距 ≤ 0.1 个百分点；④ 成本和换手人工核对 3 个决策日。
- **完成判据**：测试全过；Reviewer 用独立脚本复算 A 臂设计期（≤2015）年化、最大回撤，差距 ≤ 0.1 个百分点。

### L3 溢价模块（Dev；依赖：L1 的 QDII 数据；可与 L2 并行）
- **目标**：实现 v3 §5（常态线、四种状态、风险预算、同指数选代码）。
- **改动面**：`src/v3/premium/`、`tests/v3/`。
- **验证**：复现 `operations/reviews/diag/v3-explore/prem_episodes.py` 的事件清单（同口径下事件日期一致）；人工核对 2025-04、2026-03 两个时点的状态判定。
- **完成判据**：测试全过；Reviewer approve。

### L4 评估层（Dev 实现，Reviewer 独立复算；依赖：L2）
- **目标**：实现 v3 §6 的五条判据和 §7 的滚动前推、回测过拟合概率、稳健性检验。
- **改动面**：`src/v3/eval/`、`tests/v3/`。
- **验证**：随机对照在随机游走数据上排名应接近均匀分布；回测过拟合概率在"全是噪声"的候选集上应接近 0.5；紧缩夏普比率用公开示例数据核对。
- **完成判据**：Reviewer 用独立实现复算 ①②③ 在设计期的数值，一致。

### L5 运行与报告（Dev 运行，Reviewer 判定；依赖：G2、G3）
- **目标**：跑全期，按 v3 §12 出报告。
- **改动面**：`results/v3/`、`docs/research/v3-report.md`、`docs/assets/v3/`。README 只在顶部加一行链接，不改第一阶段内容。
- **验证**：Reviewer 独立复算记分卡全部数值；检查尝试记录完整。
- **完成判据**：Reviewer 出结论（G4），写入预注册 §11。

## 4. 自主迭代的边界
| 可以自由迭代 | 必须停下来 |
|---|---|
| 数据清洗、补数据、换数据源（须登记来源） | 修改预注册 §3–§7 的任何规则、门槛或候选集合（= v3.1，须 Owner 批准，重新登记尝试次数） |
| bug 修正（写进工作记录；如果改变了已报告的数字，Reviewer 要单独签字） | 看了任何检验结果后，想调整参数或"再试一个变体" |
| 性能、工程、测试、报告排版 | 尝试记录超出预算（60 个配置） |
| 在 ≤2015 数据上调试代码 | 任何需要运行 2016 年以后组合收益的操作（G3 之前） |
| 在自己的 `dev/v3-<线名>` 分支上提交、变基 | 删除或移动任何 tag；删除或改写 main 和他人的分支（只有 Owner 明确要求时才可以） |

## 5. Manager 的运转方式
- **看板** `operations/planning/phase2-board.md`：每条线的状态（未开始 / 进行中 / 待评审 / 已合入 / 阻塞）、负责人、分支、最近一次更新。
- **每日状态**（群里一条）：完成了什么、正在做什么、阻塞、需要 Owner 决定的事（没有就写"无"）。
- **只向 Owner 升级四类事**：门禁 G0、G1、G3、G5；预注册需要修改；同一问题评审来回 3 轮仍未通过；数据源拿不到且没有替代。
- **停止条件**：尝试预算用完；连续 3 天无进展；Reviewer 判定 return_to_planning。

## 6. 合入规则
- 分支 `dev/v3-<线名>`；Reviewer 评审写入 `operations/reviews/2026-MM-DD-v3-<线名>.md`；评审通过且全量测试 0 失败后，由 Manager 提请 Owner 安排用 `--ff-only` 合入 main 并删除该开发分支（沿用 D6；删除的只是已合入的 `dev/v3-*` 分支）。合入过程中**不删除、不移动任何 tag**。
- 每条线只改自己"改动面"里的文件；跨线改动先由 Manager 协调。
- 不修改第一阶段文件：`src/portfolio/`、`src/research/`、`src/report/`、`config/portfolio.toml`、`results/` 下除 `results/v3/` 以外的已有文件、`docs/prereg/` 下 v1、v2。

## 7. 最终交付
按预注册 v3 §12：一页结论、判据记分卡、6 类图、归因、逐年收益表、尝试记录摘要、四项数据陷阱声明。

