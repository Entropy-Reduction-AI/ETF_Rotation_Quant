# 并行开发线与当前决定（2026-10-22）

- Owner: L. Loric · Orchestrator 维护 · 每次决定变更追加，不改旧条

## 已定（Owner 2026-10-22）

| # | 决定 |
| --- | --- |
| D1 | V1 不成立（R2 刻画分不开）；dev 快进合入 main |
| D2 | R4 收手版 = **底仓永远满仓**：A 股板块等权 70% + 海外（纳指100 / 标普500 各半）30%，月度再平衡；A 股部分加**慢阀 25/10**（月末自高点回撤 > 25% 转货币 ETF 511880，自出场后最低月末反弹 > 10% 转回）。不做快速择时、不做无信号留现金 |
| D3 | v2 只检验一个问题：满仓 vs 按大盘动态切现金（借 Qullamaggie 原版 10/20 日线，不选设计期更好看的宽松版）；样本外一次；登记为第 2 次尝试 |
| D4 | 单笔风险 0.5% 只用于将来验证通过的进攻层；底仓不按单笔风险定仓 |
| D6 | Owner 事先授权：分支经 orchestrator 评审通过（写入 `operations/reviews/`）且全量测试 0 失败，即可由 Cloud Agent `--ff-only` 合入 main，无需再等 Owner 点头。D5 标的决定、v2 冻结样本外运行、上真钱不在授权内 |
| 待定 | **标的清单**（A 股腿用哪些容器、海外与避风港用哪些 ETF）由 Owner 与 orchestrator 讨论后写入 D5。在此之前所有代码按配置文件读标的，不写死 |

依据：`operations/reviews/2026-10-22-r2-review.md`、`operations/reviews/2026-10-22-r2-diagnostics.md`。

## 样本外保护（v2 的样本外还没用）

在 v2 冻结样本外跑完之前，任何线都**不得计算或报告 2016-01-01 之后的策略 / 择时 / 组合收益、回撤、排名**。允许：数据质量与覆盖、ETF 与指数的跟踪差、流动性、上市日期、当日目标持仓（只输出持仓，不输出历史绩效）。

## 线与写权限

| 线 | 执行者 | 分支 | 只写这些路径 |
| --- | --- | --- | --- |
| A 收手版信号 | Cloud Agent #1 | `cursor/r4-fallback-engine` | `src/signals/`、`tests/signals/`、`config/`、`results/r4/`、`docs/work_logs/` 自己的日志 |
| B 执行标的清点 | Cloud Agent #2 | `cursor/execution-inventory` | `data/market.sqlite`（本线独占写；每次变更记 SHA256）、`docs/execution-inventory.md`、`results/inventory/`、`docs/work_logs/` 自己的日志 |
| C 服务器 | Pi | main（只加日志文件） | `operations/work_logs/` |
| D 评审与决策 | Orchestrator | dev / main（文档） | `operations/`、`docs/` 的规则与计划文档 |
| 取数 | Grok（按需） | 指定的 `incoming/<任务>/` | 只写该目录 |

共享文件（`docs/etf-rotation-prereg-*.md`、`docs/prereg-v1-implementation-notes.md`、`data/universe.csv`）只由 orchestrator 改，或在派活时写明交给哪条线。

## 汇合与评审

- 每条线推到自己的分支后停下，回报写进自己的工作日志。Orchestrator 复跑全量测试、核对代码与数据，在 `operations/reviews/` 写「通过 / 返工 / 新决定」。
- 合入 main：只用 `--ff-only`；不能快进就先合入 origin/main 再推分支，等再次评审。不 rebase、不 force push、不删标签。

## 讨论记录（2026-10-22，未成决定，D5 讨论时用）

- 项目只做 ETF。个股另开项目，不在本项目范围。
- 候选池方向：从 33 个容器扩到全市场 ETF，由「按当时信息自动纳入」的规则进池（上市时长、成交、跟踪指数发布后的实时历史），不由人挑；包括细分主题 ETF 与科技类 QDII。
- 原则草案（待 Owner 确认）：数据层未来函数为零；规则层后见之明要登记尝试次数并用未参与挑选的数据验证；机制层先验可以用。
- 依据：`operations/reviews/2026-10-22-r2-diagnostics.md`（含宽度测算、板块层面「好形态」特征无区分度）。

## 待办

1. D5：纳入规则与 A 股腿 / 海外 / 避风港清单；确认上面的原则草案。
2. v2 预注册（满仓 vs 按大盘切现金），等 D5 后写。
3. QDII 溢价数据（Grok）；成交额来源；`cash_dividends` 用一手公告替换。
4. Grok `incoming/grok-pit-20261022/` 交付尚未出现在仓库。
