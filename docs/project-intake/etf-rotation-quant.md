# ETF_Rotation_Quant 项目 intake

## Metadata

- Project: ETF_Rotation_Quant
- Document type: intake
- Status: active
- Owner: project owner
- Last updated: 2026-10-21
- Source of truth: AGENTS.md 与 Owner 初始化要求

## a. 要回答的问题

在 37 个主题容器上，预注册 V1 规则（一直满仓、只换标的；突破买入、失效位止损、移动止盈）在样本外扣掉成本后，能否跑赢等权组合，且回撤不更深。

验收按 V1 预注册 `docs/etf-rotation-prereg-v1.md` §9 的 5 条，不改。本次只引用，不补造五项内容；该文档待 R1 导入。初始化只做治理与说明，不复制代码或数据、不安装依赖、不跑研究。

## b. 轮次计划

按开发轮次，不按时间：

- **R1 搭建**：按 c 的清单迁移；测试 0 失败；数据和来源逐条一致；输出数据清单（34 个容器有研究序列，缺 T16 / T36 / T38，如实写明）。
- **R2 刻画 + 设计期**：只用设计期数据。形态状态没有区分度，或参数 ±20% 扰动下结果不稳 → V1 不成立，直接去 R4 收手版。冻结的规则须经评审后才能进 R3。
- **R3 冻结样本外**：只跑一次，再做逐年滚动检验；结果写进预注册 §13，§9 五条逐条判定。全过 → R4 成立版；不过 → Owner 选 v2（R5–R6）或 R4 收手版。
- **R4 信号**：成立版输出每日持仓 / 调仓 / 止损清单；收手版输出「等权持有 + 避风港 + 灾难阀」的持仓清单。
- **R5（可选）**：v2 预注册和设计期，规则同 R2，只有一次机会。
- **R6（可选）**：v2 样本外，规则同 R3，只有一次机会；不过就关闭研究线，用 R4 收手版。

## c. 迁移清单

R1 执行，本任务只记录。来源：`lwx0218/ETF_Opportunity_Ledger` main `fa70cb7`。本节是 Owner 指定的待迁移清单，不是已导入或已验证资产声明。

### 数据

- `data/market.sqlite`（R1 记录 SHA256）
- `data/universe.csv`

### 代码

- `src/data`
- `src/indicators`
- `src/research`（含 `prereg_v1`）

这三者之间互相依赖，不依赖其他包；此为 Owner 提供的迁移边界，依赖关系留待 R1 核验，本次不读取业务代码。

### 测试与依赖

- `tests/data`
- `tests/indicators`
- `tests/research`
- 它们用到的测试辅助文件（如 `tests/marketdb.py`）
- `requirements.txt`（R1 去掉非数据研究用途的依赖）

### 文档

- `docs/etf-rotation-prereg-v1.md`
- `docs/etf-dividend-enhancement-prereg.md`
- `docs/etf-characterization-z.md`
- `docs/etf-l1-retrospective.md`
- `docs/data-layer.md`
- `docs/indicators-layer.md`
- `docs/h00300-offline-restore.md`
- `docs/h00300-year-end-supplement.md`
- `docs/tencent-price-index-offline.md`

### 只登记、不迁移的参考

- `keep/incoming/grok-sources-20261016`
- `keep/incoming/grok-sources-20261019`
- `keep/incoming/grok-nav-shares-20261019`
- `keep/incoming/grok-nav-shares-followup-20261019`
- `keep/incoming/grok-t12-identity-20261019`

这五个标签里的数据包，本次不导入。R1 只在 V1 确实需要时才导入。

R1 同时把旧项目 AGENTS.md 里「Cursor Cloud specific instructions」中适用的环境说明补进新项目；本次不复制该部分，也不执行其中命令。

## d. 排除清单

明确不迁移：

- `src/ledger`、`src/jobs`、`src/web`、`src/home`、`src/observation`、`src/rotation`（例外：`src/rotation/etf_probe.py` 作为 `tests/indicators` 里 kell_states 对照的测试基准原样保留，R1 记录见 `operations/work_logs/2026-10-21-r1-migration.md`，不作为研究代码使用）。
- `deploy/`、`config/`、`prototypes/`、`ref/`。
- `events` 和 `archive/grok-raw` 分支。
- 卡片、固定源、事件草稿、论点记录、每日作业、台账存储、规则卡、设计规范相关的全部文档。
- 旧项目 `operations/` 下的历史记录。
- `requirements.txt` 中网页相关依赖不迁移；网页和部署相关内容与术语，不进入新项目研究内容。

## e. 已知数据情况

37 个面板容器中 34 个有合格研究序列；T36、T38 早期窗口暂无数据，预注册允许中途入场；T12 的执行基金身份待换，但研究用的是指数，不受影响。R1 清单还须如实列明缺 T16 / T36 / T38。

以上为 Owner 提供的情况，本次未复制、打开或复验数据；尚未形成新项目研究结论。
