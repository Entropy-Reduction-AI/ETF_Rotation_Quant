# D14 · Owner 决定（2026-10-28）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning（决定记录）
- Status: active
- Owner: L. Loric
- Maintainer: Orchestrator
- Date: 2026-10-28（Asia/Taipei）
- 依据：Owner 对 v4-R1–R3 五段汇报的答复；Owner 对标签清理的要求；`operations/work_logs/2026-10-28-v4-r1-data-exploration.md` 的“待 Orchestrator”
- 相关：`docs/owner/v4-research-memo.md`（第 5 版）；`operations/planning/2026-10-28-v4-r1b-plan.md`

## 决定

| 编号 | 决定 | 说明 |
| --- | --- | --- |
| D14-1 | **A 股场外行业指数基金进入 v4 的可交易池**：2006–2011 年境内还没有对应 ETF 时，用当时已经成立、跟踪同一或相近指数的场外指数基金代表“当时能买到的仓位” | Owner 批准（D12-8 原则）。按净值做成收益序列，和其他序列一样参加排名；申购赎回费、确认和到账天数不考虑（Owner 2026-10-28，见 D14-8）。取数在 v4-R1b，不需要改引擎 |
| D14-2 | **标签清理**：保留 3 个，删除 9 个，删除前写入里程碑索引 | Owner 要求。`milestone/phase1-archive` 永不删除、不移动（第一阶段里程碑，对应现在的 README）。细则见下方 |
| D14-3 | **美股行业收益口径**：A，自己还原，按后复权处理（D14-8），不购买标普官方历史 | D13-1 已定美股以 ETF 为主、官方指数只作核对。还原前先查清拆分日收盘是否已调整（R1 质量清单），避免复权两次 |
| D14-4 | **港股行业粒度**：A，先用恒生指数 4 个分类（金融、公用、地产、工商），预注册写明这是对“同样粒度”原则的偏离 | 恒生综合 12 个行业没有公开日线，需付费。新池里港股约占前几名的 10% |
| D14-5 | **港股汇率口径**：A，港股换算成人民币。2005 年缺的汇率先上网页找，找不到用最近数据往前平滑补齐并标明（D14-8） | 三个市场口径统一 |
| D14-6 | **池子构成**：宽基和行业同时进入排名，不删宽基 | Orchestrator 决定。A 股池本来就是宽基（沪深300、中证500、中证1000、红利）加 10 个行业，美股、港股同样处理才是“同样的粒度” |
| D14-8 | **数据原则**（Owner 2026-10-28）：① 场内 ETF 一律后复权，分红、拆分、合并都要处理，这是项目的基石；② 场外基金只用来还原市场，不考虑申赎费和到账天数；③ 汇率缺了就补：先找，找不到往前平滑补齐；④ 接口拿不到的，Grok 团队用自己的电脑去网页上想办法 | 写成 `docs/manual/data-principles.md` |
| D14-7 | **IC 检验记为探索，不计入判据 ⑤** | Orchestrator 决定。只用指数价格算排名相关和门槛预测力，没有组合配置。记录见 `operations/work_logs/2026-10-28-orchestrator-ic-baseline.md`。Reviewer 可以提出异议 |

## D14-2 标签细则

保留（3 个）：

| 标签 | 为什么保留 |
| --- | --- |
| `milestone/phase1-archive` | 第一阶段里程碑，对应现在的 README。**永不删除、不移动** |
| `milestone/v3.1-prereg-freeze` | 现行基线的规则在看结果之前冻结的证据 |
| `milestone/v3-code-freeze` | 现行基线（v3.1 = E2）的代码。名字里是 v3，内容是 v3.1，不改名（改名等于删了再建） |

删除（9 个）。删除前逐个写进 `docs/manual/milestones.md`（标签名、标签对象 SHA、指向的提交、说明、为什么能删）：

| 标签 | 删除前要确认 |
| --- | --- |
| `milestone/v1-code-freeze` | 指向的提交是 `origin/main` 的祖先 |
| `milestone/v1-r2-stop` | 同上 |
| `milestone/v2-prereg-freeze` | 同上 |
| `milestone/v2-oos-result` | 同上 |
| `milestone/v3-prereg-freeze` | 同上 |
| `milestone/core-portfolio-live-config` | 同上 |
| `keep/cursor/owner-progress-boundary-audit` | 指向的提交等于已关闭 PR #42 的 `refs/pull/42/head` |
| `keep/cursor/task-complete-owner-experience` | 指向的提交等于已关闭 PR #46 的 `refs/pull/46/head` |
| `keep/cursor/v3.1-prereg-review-7a9f` | 指向的提交等于已关闭 PR #33 的 `refs/pull/33/head` |

任何一个确认不通过，就不删它，写进工作记录交 Orchestrator。删除后这些提交仍可从 `main` 的历史或 GitHub 的 PR 页面找到，不会丢。

以后的规矩（写进 `docs/manual/roadmap-and-naming.md` 和 `AGENTS.md`）：

- 每个版本最多两个标签：`milestone/<版本>-prereg-freeze`（规则冻结）和 `milestone/<版本>-code-freeze`（代码冻结）。每个阶段结束一个 `milestone/phase<N>-archive`。
- 不再用 `keep/*` 标签保存关闭的 PR，PR 页面本身就保留了提交。
- 不移动任何标签。删除只按 Owner 的决定记录执行，删除前写进里程碑索引。`milestone/phase1-archive` 永不删除、不移动。

更正（Orchestrator）：D13-6 让团队“补打 5 个缺失的 milestone 标签”，方向是补全而不是精简，标签因此从 7 个变成 12 个。这条由 D14-2 取代。

## 给 bot 团队的变更

见 `operations/planning/2026-10-28-v4-r1b-plan.md`（可整段复制给 Grok 群）。
