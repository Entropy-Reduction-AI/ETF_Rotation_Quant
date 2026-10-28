# v4-R1b · 取数 spot-check · 2026-10-28

## Decision：`approve_with_follow_up`

在 Dev PR [#73](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/73) 尖端 `01dd5449b50db293ff51656590a46899e35492be`（base `9862d5f`）上独立复核：`data/market.sqlite` 写入后 SHA、`PRAGMA integrity_check`、相对写入前库（`a130af9e…`，与 main 上 R1 库一致）的 `bars` 仅 6 行 0→NULL、USDCNY/HKDCNY 原始 `bars` 不变、124 只 unavailable 后复权无 `v4_series` 泄漏、registry 与 `v4_series` SHA 一致；随机 spot-check 与第二来源无冲突。**不**因 HSF 无免费官方日线否决 Dev。Follow-up：HSF 官方历史来源（Orchestrator）；本 PR 未含计划 §Reviewer-2 的 IC 复算（见单独 review 线 `review/v4-r1b-orchestrator-ic`）。

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R1b 取数 spot-check（D14 · ② 标的池）
- Date: 2026-10-28 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（本 PR 仅 `operations/reviews/**`）
- 签收对象（Dev）: PR #73 · head `01dd5449b50db293ff51656590a46899e35492be`
- Dev work log: `operations/work_logs/2026-10-28-v4-r1b-ingest.md`
- Review branch: `review/v4-r1b-data-spotcheck-1ca4`（基于 `origin/main`，仅追加评审产物）

## 证据总表

| 检查项 | 方法 | 结论 |
| --- | --- | --- |
| 库文件 SHA | `sha256sum` + LFS pull @ PR tip | 写入后 `af4c5a376d…045b78`（208666624 B）**一致** |
| 写入前 SHA | 对比 `/tmp/etf-main-wt`（9862d5f） | `a130af9e…` **一致** |
| `PRAGMA integrity_check` | 只读打开 PR 库 | **ok** |
| `bars` 除 6 NULL | 787005 行逐行 vs 写入前库 | **786999** 行相同 + **6** 行 0→NULL；**0** 意外差异 |
| USDCNY/HKDCNY `bars` | `bar_sha256` vs 写入前 | **不变** |
| 六 H* @ 2013-06-28 | SQL `close` | 全部 **NULL**（非 0） |
| Yahoo 拆分已在价 | XLF 2016-09-19；XLB/XLE/XLK/XLU/XLY 2025-12-05 原始比≈1，后复权比=原始比 | **无二次拆分** |
| 后复权 ETF ×3 ×5 日 | seed=`2026102873`：XLK/XLV/XLE；美股用 raw+分红独立重算 | **15/15** 差 **0** |
| 场外基金 ×3 ×5 日 | 162711/020011/090010；东财 `pingzhongdata` 日增长率复算 | **15/15** 差 **0** |
| 汇率补齐 ×3 日 | 2005-05-05、2005-10-04、2005-10-06；`v4_series.fx` vs `fx-fill.csv` + 重拉 SAFE 工作簿 | **6/6** 与登记一致；补齐日外管局无发布（`safe_official=null`）符合 Dev 说明 |
| unavailable 后复权 | 124 行 `status=unavailable` | **无** `kind=backward` 泄漏 |
| Registry | 256 行 v4-R1b 覆盖 vs `v4_series` SHA | **0** mismatch；35 只 OTC ↔ `universe.toml` `otc_fund` **一致** |
| v4 单测 | `tests.v4.data.test_r1b` + `test_ingest` | **26** OK（PR tip） |
| 组合 PnL / 2016+ | PR diff + CLI | **未**运行；未改 LOCK/tag |

## A. 环境与脚本

| 产物 | 路径 |
| --- | --- |
| 独立脚本 | `operations/reviews/diag/v4/2026-10-28-v4-r1b-spotcheck.py` |
| JSON  artifact | `operations/reviews/diag/v4/2026-10-28-v4-r1b-spotcheck.json` |
| 运行日志 artifact | `/opt/cursor/artifacts/v4-r1b-reviewer-spotcheck.json`（与仓库 JSON 同内容） |

运行（须在 Dev PR #73 tip，`git lfs pull` 后）：

```bash
.venv/bin/python operations/reviews/diag/v4/2026-10-28-v4-r1b-spotcheck.py
```

## B. 拆分日与后复权（硬约束 1）

Dev 结论「Yahoo 收盘已含拆分、后复权只加分红」与 Reviewer 复核一致：拆分相邻日 raw/adj 收益比相同，`split_already_in_price=true`（见 JSON `split_basis`）。XLF 2016-09-19 收盘比 **1.0064**；2025-12-05 五只 Sector ETF 收盘比 **0.99–1.01**。

## C. 场外基金（硬约束 2）

第二来源：各基金 `https://fund.eastmoney.com/pingzhongdata/{code}.js`，用与 Dev 相同的 `parse_pingzhongdata` + `compound_adjusted_nav` 重算至 2026-09-30，对比 `v4_series.kind=otc_nav` 的复权 `close`。

## D. 2005 汇率补齐（硬约束 3）

第二来源：[外管局历史中间价说明](https://www.safe.gov.cn/safe/2020/1218/17833.html) 与工作簿 [xlsx](https://www.safe.gov.cn/safe/file/file/20260106/0f147e5357eb4c12a6406fc575cc21e8.xlsx)（Dev 登记 SHA `fe54b082…`）。抽查 3 个日历日（各 USDCNY+HKDCNY）均为 `filled=1`、`fill_mean_next_20`，与 `results/v4/inventory/fx-fill.csv` 及库内 **一致**；该 3 日无官方中间价发布，非 Dev 造假。

## E. 质量清单 · HSF（硬约束 4）

- 六 H* @ 2013-06-28：**NULL** ✓  
- HSF：Dev 已记录恒生公司多个 URL **404**、官方日线付费；Yahoo `^HSNF` 与腾讯 HSF 在 1997-10-28 / 2013-12-30 差 **<0.02**（见 `results/v4/inventory/hsf-check.csv`）。Reviewer **未**将其列为 Dev 缺陷；**Orchestrator**：是否接受 Yahoo 对照或购买官方 HSF 历史。

## F. 硬门禁

| 检查 | 结果 |
| --- | --- |
| 合 main / 移动 tag / `results/v3/LOCK` | Reviewer **未**执行 |
| 2016+ 组合 PnL | **未**计算 |
| 原始 `bars` 除 6 NULL | **是** |
| unavailable 用 raw 冒充后复权 | **否**（124 只无 backward 行） |

## G. Follow-up（不阻塞 Dev #73）

1. **HSF 官方日线** — 免费 URL 404；Yahoo 对照已文档化。  
2. **IC 17 指数复算** — 计划 §Reviewer-2；本签收 PR 不含该脚本（仓库另有 `review/v4-r1b-orchestrator-ic` 线）。

## H. Review PR

- Review 签收 PR：（本分支 `review/v4-r1b-data-spotcheck-1ca4` 合入 main 后 URL 由 CI 填充）
- Dev 取数 PR：https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/73
