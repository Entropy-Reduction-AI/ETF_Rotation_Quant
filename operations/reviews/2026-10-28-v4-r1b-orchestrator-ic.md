# v4-R1b · Orchestrator 17 指数 Rank IC 基线独立复算 · 2026-10-28

## Decision：`numbers_ok`

五组平均 Rank IC（20 / 60 / 120 / 250 日、四个平均）与 Orchestrator 工作记录 `operations/work_logs/2026-10-28-orchestrator-ic-baseline.md` 在 **三位小数** 下一致；决策月数 **119**，样本为 17 指数（18 序列复现口径去掉黄金），数据截止 **≤2015-12-31**，未计算任何组合 PnL。

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R1b plan §Reviewer item 2（D14-7 基线 IC）
- Date: 2026-10-28 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（`operations/reviews/**` + diag；未改业务代码、未写 LOCK、未动 tag）
- 方法来源（只读）: `operations/work_logs/2026-10-28-orchestrator-ic-baseline.md`
- 登记脚本（只读对照，未调用）: `results/v3/diag/2026-10-28-orchestrator-ic/ic.py`
- 独立实现: `operations/reviews/diag/v4/v4-r1b-orchestrator-ic-recompute.py`
- 机器可读结果: `operations/reviews/diag/v4/v4-r1b-orchestrator-ic-recompute.json`
- `data/market.sqlite` SHA256（LFS 实体）: `a130af9eab11368d71488ee48f83bb71952d17eb5abd1d5bcc00d1cd6993f1e6`

## A. 运行命令

```bash
cd /workspace
git lfs pull   # data/market.sqlite
/workspace/.venv/bin/python operations/reviews/diag/v4/v4-r1b-orchestrator-ic-recompute.py
```

完整 JSON 同时写入 `/opt/cursor/artifacts/v4-r1b-orchestrator-ic-recompute.json`。

## B. 期望 vs 独立复算（Decision 门禁）

得分：过去 L 日收益 ÷（日收益标准差 × √L）。每月末截面 Spearman：得分 vs 之后 **20** 个交易日收益。四个平均：20/60/120/250 四个得分 **排名** 的横截面平均，再与 forward 排名做 Spearman。

| 回看长度 | Orchestrator 登记 | Reviewer 复算 | 三位小数一致 |
| --- | ---: | ---: | --- |
| 20 日 | 0.093 | **0.093** | 是 |
| 60 日 | 0.028 | **0.028** | 是 |
| 120 日 | −0.004 | **−0.004** | 是 |
| 250 日 | 0.049 | **0.049** | 是 |
| 四个平均 | 0.069 | **0.069** | 是 |

复算六位小数（JSON）：20 → 0.093372；60 → 0.028015；120 → −0.004128；250 → 0.049422；四个平均 → 0.069000。

样本规模：119 个月末决策（2006-01 … 2015-12）；17 个指数列名见 JSON `index_names`。

## C. 实现说明（与登记脚本刻意独立）

1. **面板**：从仓库根 `data/market.sqlite` 读 `bars.close`，按 18 序列复现口径（`lab2.py` / `lab.py` 同构逻辑）对齐 H00300 日历、USDCNY 换人民币、海外序列 +1 日对齐；不含黄金列；`≤2015-12-31` 截断。
2. **IC**：自写 `risk_adj_momentum` + 截面 `rank().corr()`（Spearman），未 import 登记目录代码。
3. **纪律**：未合并 main、未创建/移动/删除 tag、未写 `results/v3/LOCK`、未算 2016+ 收益或组合 PnL。

## D. 备注（非 Decision 门禁）

D14-7 将本 IC 表标为 **探索、不计入判据 ⑤**；Reviewer 不反对该定位——在 17 个高相关指数、119 个月、多长度并看的前提下，平均 IC 量级与分段不稳定性与工作记录结论一致，适合作「事前登记、事后只报告」的敏感性描述，而非单独 GO/NO-GO 门槛。

## E. Pull request

https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/70
