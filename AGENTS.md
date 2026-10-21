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

### 执行者

- Claude（规划评审）：切分轮次、写 prompt、直接看仓库评审每次推送，不改代码。
- Cloud Agent（开发，Owner 可改派）：在临时 dev 分支开发，测试通过再推，合入 main 需要 Owner 点头，合入后删除 dev。
- Pi（服务器）：按指令补数据、核原件、跑指定作业，执行记录写 `operations/work_logs/`，不改代码。
- Grok bot：只在缺数据时按需取数，交付推到指定目录，不新建分支。
- 任务只写四件事：目标、改动面、验证、完成判据。

### 目标

在 A 股主题 ETF 上找到一套样本外站得住的轮动规则，交付结论报告和可执行的持仓信号；结论不成立就如实交付「不成立」。

### 不可协商的研究纪律

- 不重做已关闭的方向，不换参数重跑。
- 结果盲、机械选样；数据只来自已登记的来源，并且有明确的发布日期；不用未来信息；诚实登记已经看过的数据。
- 回测前完成预注册；冻结样本外只跑一次；失败如实记录并关闭；新尝试另起版本，注明是第几次尝试。
- 回测用含分红再投的后复权；新增自由度上限约 4 个；禁止机器学习、因子合成、网格搜索、看到结果再调参。
- 按 R 倍数分布评估，必须报告去掉最好 1 / 2 / 3 笔后的期望；不以胜率或夏普作为评价指标；双基准是等权组合和沪深300全收益。
- 单标的结论和横截面结论不得互相冒充；不做空，不加杠杆，不做日内。

### 数据约束

- 指数逐个核实代码、起始日期、价格 / 全收益口径。
- 黄金、原油、海外、国债、现金是一等容器。
- 结论必须声明四项数据陷阱：主题指数回填、指数与 ETF 的差异、腾讯减法 qfq、份额折算造成的假跳空。
- `data/market.sqlite` 纳入版本管理，每次变更都记录 SHA256；时区按 Asia/Shanghai。

### 分支

常驻只有 main；开发用临时 dev，合入后删除；需要存档的分支打 `keep/` 标签。

### 面向 Owner 的语言

面向 Owner 用中文。
<!-- PROJECT:OWNED:END -->
