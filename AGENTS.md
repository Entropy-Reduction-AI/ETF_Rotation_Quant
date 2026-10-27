# AGENTS.md

<!-- HARNESS:MANAGED:START -->
## Harness Managed Execution Contract

本分区由 Harness 管理（`harness.sh` 会整体替换）。项目产品、领域、安全和运行时规则请写在 `PROJECT:OWNED` 分区。

### Authority

- 本文件是模型执行合同；冲突时优先于 README、human manual、`.pi/` 和历史 evidence。
- `.pi/` 只是 capability layer，不是 policy authority。

### Owner-Facing Language

面向 Owner 的聊天总结、交付说明、状态报告和控制门提示默认使用中文。文件名、命令、代码标识、协议字段和必要原文引用可保留英文。

### 交付主线

1. **按需规划** — 目标、范围或风险不清时先澄清，必要时切分 round；清楚且已授权的 bounded task 在当前会话直接执行，不强制另开 Orchestration session。
2. **按需委派，不设分发门禁** — 本项目不再通过 `/fleet` 分发任务。任务和 round 均可在当前会话执行；独立 Pi session、`session_spawn`、`session_bus`、终端复用器或子代理可用性都不是开工、验证或交付前置条件。仅在任务确需并行或专门复核时，使用当前宿主可用的委派能力；不为分发而安装、升级或 patch 包。
3. **可选 Subagents 执行** — 需要委派时匹配角色模板优先；builder 实现，reviewer 只读复核并给出 `approve` / `approve_with_follow_up` / `return_to_planning`。未委派的任务由当前会话执行相称验证；只读是角色约束，不是运行时沙箱承诺。
4. **ponytail 门禁** — 新增代码由 ponytail 做准入判定。

需要规划时由 Owner 确认范围与 round 划分；已授权的清楚任务直接执行。使用 reviewer 时由其出复核结论，代码准入仍由 ponytail 判定。**不得把逐轮 review 结论推回 Owner**；只有无法结论、与任务目标冲突或触及安全边界时，才向 Owner 升级，不以另开会话作为前置条件。

不存在需要 Owner 逐条批准的 formal mode、fixed Round ledger、independent review gate 或 session handoff 合同。历史 evidence 不激活任何旧流程。

### Round 的定义

round 是 Orchestration 阶段切出的**任务切分单位，不是验收单位**。不需要 ledger、固定编号规则或跨 round 状态机。

一个 round 说清楚四件事即可：目标、改动面、验证方式、完成判据。

### 默认模式

理解请求、必要时少量澄清、执行 bounded change、运行相称验证、用中文总结。复杂、跨文件或已有历史 evidence 不会自动加重流程。

Plan 用于澄清目标、范围、风险、验证和 round 切分，不产生额外审核义务。

### First Session

Greenfield 或无 baseline 的项目，首次从项目根运行：

```bash
pi --name "00-orchestration"
```

Owner 批准规划前只允许 read/infer/discuss 和 chat Plan Preview；不得修改业务 code/config、创建 durable evidence、安装依赖或执行破坏性操作。接受 recommended defaults 不等于批准规划。

### Routing

- `direct-execute`：清楚 bounded task。
- `plan`：目标、范围、风险、验证或 round 切分需要澄清。
- `review-only`：只要 findings。
- `needs-package`：确有能力缺口。

skills 和 domain modeling 是按需能力，不是默认关卡。

### 治理层边界

产品 round 不修改治理层（`.pi/`、`AGENTS.md`、Harness 下发的文件）。发现治理层问题时单独提出，不在产品 round 里顺手改。

`.pi/extensions/` 下不放 vendored extension 源码。能力通过 `.pi/settings.json` 的 `packages` 声明获得；按 npm 包名做全局去重，但保留项目显式锁版、对象资源过滤及自定义字段。

`npm:pi-web-ui` 可选、默认不下发。包已安装或声明不等于当前启用的执行路径；启用 Web UI 不卸载 CLI 包，也不改变安装或同步行为。`harness.sh` 自动检测项目及执行环境全局的已知 Dashboard 声明并迁移为 Web UI；共享全局配置仅在 `--apply` 且项目检查通过后备份、原子替换。只清理准确关联的 Dashboard bridge，不卸载包、不停止服务、不删除会话。`--no-global-dedup` 不关闭迁移检测。

### Document And Evidence Governance

新增或实质更新 Markdown 时先判定承载位置：

- `docs/**`：长期说明、manual、reference、project intake 与导航；kebab-case 文件名和最小 Metadata。
- `operations/**`：事件型 durable evidence；`YYYY-MM-DD-<slug>.md` 日期前缀与任务型 Metadata。

只有进入 Plan、round 切分、合同/bootstrap 变更或需要保留 review trail 时，才写 durable evidence。详细格式见 `docs/manual/document-governance.md`。

### Evidence And Safety

高风险、破坏性、外部授权、scope 改变或验证失败时 fail closed 并询问 Owner。不自动 push。
<!-- HARNESS:MANAGED:END -->

<!-- PROJECT:OWNED:START -->
## 项目合同 · ETF_Rotation_Quant

### 任务执行约定（Owner 更新，2026-10-21）

- 本项目不再通过 `/fleet` 分发任务，不以 Fleet、独立 session、终端复用器或强制子代理分发作为门禁。清楚且已授权的任务默认在当前会话直接执行并验证；委派按需。
- 本条是项目分发方式的权威约定；若 Harness managed 分区、manual、`.pi/` 模板/技能或历史记录仍要求先 `/fleet`、每 round 新建 session，则以本条为准，不恢复旧门禁。Harness 同步不得覆盖本 owned 约定。
- 本次只取消分发前置要求，不解除项目边界、执行者职责边界、研究纪律、安全约束、必要验证或提交/推送授权要求。

### 执行者（2026-10-24 起，D9-6）

- Owner：定方向；批准合同修订、预注册冻结、跑已污染检验段、前向模拟盘和真钱。
- Orchestrator（Notion AI）：设计、写预注册、解读结果；不做主体开发。
- ETF Rotation Manager（bot）：任务拆分、派活、看板、每日状态、按规则升级；不写业务代码、不判定结果。
- ETF Rotation Dev（bot）：取数、开发、运行；在 `dev/v3-<线名>` 分支工作，可多实例并行；不判定通过、不碰 LOCK。
- ETF Rotation Reviewer（bot）：独立复核与复算、保管冻结与 LOCK、按判据出结论；不改业务代码；应与 Dev 使用不同的底层模型，或使用独立实现。
- Cloud Agent：按 Owner 的明确指令创建 tag、执行 `--ff-only` 合入。
- **tag 与分支纪律（所有执行者）**：不删除、不移动任何 tag；不删除、不强推、不改写 `main`。删除分支或 tag 只在 Owner 明确要求时执行，并在工作记录里写明名称和原指向提交。仓库不设 tag 保护规则，此条靠纪律执行。
- Pi（服务器）：暂缓，部署另行决定。
- 任务只写四件事：目标、改动面、验证、完成判据。

### 新会话必读（Owner 2026-10-25）

新会话先读 `docs/project-intake/owner-vision-and-principles.md`：愿景的深层含义、Owner 的判断原则、路线图与现状。Owner 看板镜像见 `docs/owner/phase2-owner-board.md`（权威版本在 Notion）。

### 目标

原目标：在 A 股主题 ETF 上找到一套样本外站得住的轮动规则；结论不成立就如实交付「不成立」。已交付：V1 轮动在设计期即不成立，v2 A 股择时在冻结样本外不通过（`docs/prereg/` 各预注册 §结果）。

现阶段（第一阶段已于 2026-10-23 收尾，D8）：维护并执行核心配置（`config/portfolio.toml`，决定记录 D2/D5/D7），输出可执行的目标持仓。策略本身（容器清单、权重）的重审另开讨论；第二阶段按预注册 v3 执行（D9）。第一阶段内容封存于 `milestone/phase1-archive`，第二阶段只写 `src/v3/`、`config/v3/`、`results/v3/` 等新目录。

报告组合层面的结果时，必须与基准并列：BM-主 = 70% 沪深300全收益 + 15% 纳指100全收益 + 15% 标普500全收益（人民币中间价换算），每月第一个交易日再平衡；人民币、全收益、逐年列出（GIPS 口径，实现见 `src/report/`，说明见 README §5）。旧路径以 `docs/PATHS.md` 为准。

### 不可协商的研究纪律

- 不重做已关闭的方向，不换参数重跑。已关闭：V1 横截面形态轮动（第 1 次尝试）；A 股趋势择时，含 Qulla 10/20 与慢阀 25/10（第 2 次尝试，连同旧项目红利择时）；月线布林上轨减仓（旧项目）。
- 2016-01-01 → 2026-09-30 已被 v2 使用。按 D9-1，它可以作为"已污染检验段"被预注册 v3 再用一次，须在预注册中登记所有已看过的信息，且不得称为样本外。干净证据只来自 2026-10 之后的数据和前向模拟盘。
- 结果盲、机械选样；数据只来自已登记的来源，并且有明确的发布日期；不用未来信息；诚实登记已经看过的数据。
- 回测前完成预注册；冻结样本外只跑一次；失败如实记录并关闭；新尝试另起版本，注明是第几次尝试。
- 回测用含分红再投的后复权；新增自由度上限约 4 个；禁止机器学习、因子合成、看到结果再调参。例外（D9-3）：在预注册写死的有限候选集里，按滚动前推程序选择参数，并报告回测过拟合概率。
- 进攻层（单笔交易系统）按 R 倍数分布评估，必须报告去掉最好 1 / 2 / 3 笔后的期望；不以胜率或夏普作为评价指标；双基准是等权组合和沪深300全收益。
- 单标的结论和横截面结论不得互相冒充；不做空，不加杠杆，不做日内。

### 数据约束

- 指数逐个核实代码、起始日期、价格 / 全收益口径。
- 黄金、原油、海外、国债、现金是一等容器。
- 结论必须声明四项数据陷阱：主题指数回填、指数与 ETF 的差异、腾讯减法 qfq、份额折算造成的假跳空。
- `data/market.sqlite` 纳入版本管理，每次变更都记录 SHA256；时区按 Asia/Taipei。

### 分支

常驻只有 main；开发用临时分支 `cursor/<任务>`，合入后删除；关键证据节点打 `milestone/` 附注标签（如 `milestone/v2-prereg-freeze`），不删、不移；需要存档但未合入的分支打 `keep/` 标签。

### 面向 Owner 的语言

面向 Owner 用中文。
<!-- PROJECT:OWNED:END -->

## Cursor Cloud specific instructions

- 默认镜像要先安装 `python3.12-venv`，否则 `python3 -m venv` 因缺少 ensurepip 失败。随后在仓库根执行 `python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt`。
- 跑测试前执行 `mkdir -p outputs`（`outputs/` 被 gitignore）。测试：`.venv/bin/python -m unittest discover -s tests -t .`。
