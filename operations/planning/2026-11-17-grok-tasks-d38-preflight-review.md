# 给 Grok 群的任务：D38 预演复算与红队（2026-11-17）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning（任务派发）
- Status: active
- Owner: L. Loric
- Maintainer: Orchestrator
- 依据：D38 预演登记“谁做、怎么验”；完成判据第 2 条

下面整段可以直接复制给 Reviewer。

```text
【任务】D38 预演复算与红队（Reviewer）

先读：
1. docs/project-intake/project-diagnosis.md
2. operations/planning/2026-11-16-d38-project-diagnosis-and-preflight.md（登记、候选结构、不做线、运行附表 0–4）
3. docs/owner/v6-preflight-forecast.md（预测表第 1 版）

纪律：独立实现，不 import scripts/preflight/ 下的代码；数据边界同登记（合成行情、长历史、项目池 ≤2015-12-31；2016 年以后不读收益）。只报告，不改判，不改候选结构和不做线。

R1 合成行情复算：按登记的规则自己实现 K0、K1、K2，跑“慢牛”“急跌”“V 型反转”三种，各 1000 条路径（噪声取 ^GSPC、^HSI 1987-01 → 2003-06 同日成对日收益，20 日一段重抽）。核对 behavior.csv 的“比K0年化_p50”（容差 ±0.5 个点）和“比K0回撤_p50”（±1.5 个点），以及 cost.csv 的每年成本（±0.05）。
R2 长历史复算：标普 1956–2003、恒生和日经 1988–2015 的 K0、K1、K2，核对 longhist.csv 的“比K0年化”（±0.2）、“最大回撤”（±1）、“平均仓位”（±0.02）。
R3 信号准确度复算：ic.json 里 ① 长历史三市场的 IC，③ A 股内 12−1“涨幅”和“涨幅÷波动”两段的 IC 均值（±0.01）。
R4 预测表算术：第 1 节每一行的四项加总是否等于“合计”；换算口径（股票 8.7%、国债 2.5%、打五折、成本取上限）是否前后一致；第 4 节每一格是否和结果文件一致。
R5 红队：写一页“假设 v6 按 K2 上线两年后失败了，最可能的五个原因”，每个原因写清机制、触发它的行情、预计每年损失几个点，以及预测表里有没有覆盖。
R6 结论：approve / approve_with_follow_up / return_to_planning。

交付：operations/reviews/2026-11-17-d38-preflight-review.md（复算表 + 红队 + 结论），复算脚本放 operations/reviews/diag/d38/。

完成判据：R1–R4 每一项都有“一致 / 不一致（差多少、原因）”；R5 五条都有数字；R6 有结论。
```

## 第 2 部分：K2A 复算（2026-11-17 追加）

```text
【任务】D38 预演第 2 部分：K2A 复算（Reviewer）

背景：你在第 1 部分（PR #300）的跟进项已经查清：原脚本六种行情共用一个随机数流，现已改成每种行情从同一种子重新开始，和你的口径一致，V 型反转逐位相同（K1 −31.84、K2 −25.03）。红队第 3 条促成了新候选 K2A，需要你复算。

先读：docs/owner/v6-preflight-forecast.md 第 2 版；D38 登记“第 3 版补充”和附表第 5–7 行。

纪律同第 1 部分：独立实现，不 import scripts/preflight/；不读 2016 年以后的收益。

R7 K2A 合成行情：在你的 review_engine.py 里加 K2A（K2 的规则只作用在 A 股腿，美股腿一直持有），跑慢牛、急跌、V 型反转各 1000 条路径。核对 behavior.csv 里 K2A 的“比K0年化_p50”（±0.5）、“比K0回撤_p50”（±1.5），cost.csv 的每年成本（±0.05）。
R8 K2A 敏感度：美股比 A 股每年多涨 −10、0、+10、+20 个点（十年，A 股 6%、波动 25%，美股波动 17%），核对 sensitivity.csv 里 K2 和 K2A 的“比70_30年化_p50”（±0.5）。
R9 沪深300 回放：项目池 index 口径 2006–2015，单市场 K0、K1、K2，核对 csi300.json 的“比K0年化”（±0.2）、“最大回撤”（±1）、“平均仓位”（±0.02）。
R10 预测表第 2 版：K2A 一行四项加总；第 4 节 K2A 三格；第 6 节 K2A 一行的金额（十年约 30 万）。
R11 结论：approve / approve_with_follow_up / return_to_planning。

交付：在 operations/reviews/2026-11-17-d38-preflight-review.md 末尾追加“第 2 部分”，脚本放 operations/reviews/diag/d38/。
```

## 之后

Orchestrator 把复算结果和红队意见并入预测表第 2 版，再交 Owner 定保费上限。
