# ETF_Rotation_Quant 初始化记录

## Metadata

- Project: ETF_Rotation_Quant
- Task: 最小治理初始化
- Timestamp (UTC): 2026-10-21T13:23:30Z
- Owner: project owner
- Route: direct-execute
- Source of truth: Owner 初始化要求与 AGENTS.md

## a. 原文逐段对照与实际验证

来源：`ETF_Opportunity_Ledger` main `fa70cb7`，完整提交 `fa70cb709738dad3ebf426a71959943abe88fd0e`。通过 `git -C <参考目录> ls-tree -r --name-only fa70cb7 -- <指定路径>` 列出治理文件，再以 `git show fa70cb7:<路径>` 读取；未用参考工作区替代源提交。

仅修改目标目录的治理骨架、说明、intake、忽略规则和本记录；未复制业务代码、数据或研究产物，未安装依赖、未运行研究、未改变全局配置、未修改参考项目或生成器工作区。本执行线程未运行生成器或 apply 操作。此前骨架生成和远端空仓检查沿用主会话已报告结果，不冒充本线程重跑。

### 三类授权变化

1. ① 项目名：原名的下划线、连字符变体统一替换为 `ETF_Rotation_Quant`；涉及角色说明、治理入口、manual 标题和 settings 项目名。
2. ② 包声明：仅从源 settings packages 移除前端检查包和旧 CLI 分发包；保留 `npm:pi-subagents`、`npm:@dietrichgebert/ponytail`、`npm:pi-web-access`。其余字段、结构、顺序与源提交一致；未添加项目级 Web UI 声明，也未安装、卸载或升级任何包。
3. ③ 删除旧强制分发操作与下发说明：删除 AGENTS managed 的旧包默认下发前缀；agents 导航的第 2 步；governance-loop 的强制分发句；project-kickoff 的确认尾句、独立开发会话后缀及分发列表项；governance-loop-entry 的独立会话分发段落。其余原文不改，包括取消性约定、流程用语及原有编号。

### 实际对照结果

对每个源文件及输出在系统临时目录执行 `git diff --no-index -- original output`，AGENTS 只取 managed 分区（以下该行 hunk 行号相对分区正文）。临时目录已自动清除，未留下脚本。下表为真实返回码和逐段 hunk；1 表示存在列出的授权差异，不是检查失败。另将源文只应用①②③，再执行 `git diff --no-index -- authorized output`，所有返回 0；断言逐项替换只匹配一次且全文相等。

| 对照范围 | 原始对照返回码 | 实际 hunk | 授权类别 | 授权变换后返回码 |
| --- | --- | --- | --- | --- |
| `AGENTS.md` | 1 | @@ -60,7 +60,7 @@ | ③ | 0 |
| `.pi/agents/README.md` | 1 | @@ -5,7 +5,6 @@ | ③ | 0 |
| `.pi/agents/builder.md` | 1 | @@ -3,7 +3,7 @@ | ① | 0 |
| `.pi/agents/planner.md` | 1 | @@ -3,7 +3,7 @@ | ① | 0 |
| `.pi/agents/reviewer.md` | 1 | @@ -3,7 +3,7 @@ | ① | 0 |
| `.pi/prompt-templates/governance-loop.md` | 1 | @@ -48,7 +48,7 @@ | ③ | 0 |
| `.pi/prompt-templates/project-kickoff.md` | 1 | @@ -80,18 +80,16 @@ | ③ | 0 |
| `.pi/settings.json` | 1 | @@ -1,5 +1,5 @@；@@ -11,10 +11,8 @@ | ①、② | 0 |
| `.pi/skills/domain-modeling/ADR-FORMAT.md` | 0 | 无差异 | 原样 | 0 |
| `.pi/skills/domain-modeling/CONTEXT-FORMAT.md` | 0 | 无差异 | 原样 | 0 |
| `.pi/skills/domain-modeling/LICENSE` | 0 | 无差异 | 原样 | 0 |
| `.pi/skills/domain-modeling/SKILL.md` | 0 | 无差异 | 原样 | 0 |
| `.pi/skills/domain-modeling/SOURCE.md` | 0 | 无差异 | 原样 | 0 |
| `.pi/skills/governance-loop-entry/SKILL.md` | 1 | @@ -7,7 +7,7 @@；@@ -63,8 +63,6 @@ | ①、③ | 0 |
| `.pi/skills/grill-me/SKILL.md` | 0 | 无差异 | 原样 | 0 |
| `.pi/skills/grill-with-docs/SKILL.md` | 0 | 无差异 | 原样 | 0 |
| `Harness_manual.md` | 1 | @@ -1,4 +1,4 @@ | ① | 0 |

原始逐段差异已在执行终端完整输出；本表用 hunk 定位而不在新内容中重复被删除的旧包字面名称。未出现三类授权变化之外的差异。

### 其他范围与检查

- `.pi/.harness-manifest.json` 保持生成时内容，且与源提交逐字一致；没有复制缓存或本机配置。`docs/manual/document-governance.md` 与三个 `operations/**/.gitkeep` 保留现状。
- AGENTS owned 的三条任务执行约定由源提交原样提取，仅把「项目冻结」改为「项目边界」；其余为 Owner 指定的新项目执行者、目标、六项纪律、数据、分支和中文要求。未保留旧环境段；intake c 只登记 R1 按需补入。
- intake a–e、R1–R6、九份文档及五个存档标签均逐条登记；V1 §9 五项仅引用，不补造；数据情况和依赖边界为 Owner 提供，本次不复验。
- README 参照 Owner 指定的 `02fb8f8` 风格，仅项目简介、状态和入口；忽略规则保留源通用项，删除旧数据例外及相关注释，仅放行两个指定数据文件。
- 实际运行 `date +%F` 返回 `2026-10-21`；执行 `git init -b main` 仅建立本地仓库，以便检查忽略规则。未设置身份、remote，未暂存、提交或推送。
- `git check-ignore -v --no-index`：两个指定数据路径分别命中否定规则（第 42、43 行）；普通数据文件和数据库热日志命中 `/data/*`，产物、依赖缓存和密钥文件命中通用规则。分别执行 `git check-ignore -q` 检查两个放行路径，均返回 1（不忽略）。没有为测试创建任何数据文件。
- 分区标记配对、新写内容无未替换模板提示、根目录无 `src/` 和 `data/`、全库指定字面禁词（排除 `.git` 元数据）零命中：已用 Python 断言检查，并以 grep 复核。模式扫描见 b。
- staged 清单验证：主会话已按明确路径暂存 26 个文件，`git diff --cached --name-only` 仅含治理模板、交付清单、配置、说明、目录占位及本记录；无临时脚本、业务代码、数据或运行缓存，`git diff --cached --check` 通过。本地身份设置为 levi / linzhen.luo@gmail.com，origin 为授权新项目远端；提交前再次查询远端为空。只读复核结论 approve；主会话独立复核实际 diff 与扫描通过，并明确补入 intake 排除项中的网页依赖。

### 保留的旧版本说明与未核验路径

manual 与能力模板按源提交保留，故包含旧版 UI 开关、默认包、首次规划和 CLI 执行器描述；它们不是本次实际能力验证，也不是执行这些操作的授权。未来生成器同步可能覆盖本次定制，需重新按 Owner 要求核对。

manual owned 原文仍提及 `docs/status.md`、README 启动命令以及项目冻结；这些是照搬内容，本次未创建该路径、未提供启动命令，亦未以该旧项目状态代替新项目「已初始化，待 R1」状态。manual 的目录参数提示语、能力模板的 `$ARGUMENTS`、空字段及格式示例属于原文模板，不是遗漏替换；按原文保留。intake c 的代码、数据、测试、依赖、九份文档和存档标签均仅登记，不验证其存在或内容。代码准入不适用：本次没有新增业务代码。

## b. 新内容模式扫描

扫描范围：AGENTS owned（按文件真实行号）、intake、README、忽略规则及本日志；照搬部分不参与此限制。白名单 A：intake d 内的排除项；B：intake、README 或本日志里的指定来源标识；C：取消旧分发门禁的表述。审计表的匹配内容用字符实体显示，渲染后即原匹配字串，避免清单自身重复产生扫描命中。扫描覆盖写入审计表后的最终全文；审计表不含模式字面命中。

| 文件 | 行号 | 字符位置（从 1 起） | 匹配内容 | 白名单类别 |
| --- | --- | --- | --- | --- |
| `AGENTS.md` | 86 | 13–17 | &#102;&#108;&#101;&#101;&#116; | C |
| `AGENTS.md` | 86 | 28–32 | &#70;&#108;&#101;&#101;&#116; | C |
| `AGENTS.md` | 87 | 70–74 | &#102;&#108;&#101;&#101;&#116; | C |
| `docs/project-intake/etf-rotation-quant.md` | 31 | 42–47 | &#76;&#101;&#100;&#103;&#101;&#114; | B |
| `docs/project-intake/etf-rotation-quant.md` | 82 | 8–13 | &#108;&#101;&#100;&#103;&#101;&#114; | A |
| `docs/project-intake/etf-rotation-quant.md` | 84 | 4–9 | &#101;&#118;&#101;&#110;&#116;&#115; | A |
| `docs/project-intake/etf-rotation-quant.md` | 85 | 3–4 | &#21345;&#29255; | A |
| `docs/project-intake/etf-rotation-quant.md` | 85 | 25–26 | &#21488;&#36134; | A |
| `operations/work_logs/2026-10-21-bootstrap.md` | 14 | 21–26 | &#76;&#101;&#100;&#103;&#101;&#114; | B |

最终扫描：9 处匹配，全部归入 A / B / C，无其他命中。

## c. 最终配置全文

```json
{
  "project_name": "ETF_Rotation_Quant",
  "project_root": ".",
  "instructions_file": "AGENTS.md",
  "agents_doc": ".pi/agents/README.md",
  "prompts": [
    "prompt-templates"
  ],
  "skills": [
    "skills"
  ],
  "enableSkillCommands": true,
  "packages": [
    "npm:pi-subagents",
    "npm:@dietrichgebert/ponytail",
    "npm:pi-web-access"
  ]
}
```
