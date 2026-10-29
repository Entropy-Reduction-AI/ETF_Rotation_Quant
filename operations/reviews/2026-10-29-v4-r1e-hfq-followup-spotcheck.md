# v4-R1e · 520900 不复权 + 8 只后复权缺口 · spot-check · 2026-10-29

## Decision：`approve_with_follow_up`

在 Dev PR [#108](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/108) 尖端 `6d2fa8fdf6792a658736e5d26a2eeea3575acafe`（base main `36fae98dfaba2b43f834adff8ccdc6a157c8a896`）上，Reviewer **独立**对照 `data/market.sqlite`、`results/v4/inventory/r1e/`、`incoming/2026-10-29-v4-r1e-hfq-followup/` 与 `operations/work_logs/2026-10-29-v4-r1e-hfq-followup.md`：**520900 只插入 542 行 `adj=raw`、来源 `sse_yunhq`，与冻结 SSE dayk payload 五日复算一致；既有 `eastmoney_etf_hfq` 后复权未改，2026-09-30 hfq 收盘仍为 1.048**；**8 只代码 `adj=hfq` 仍为 0 行，未发现把交易所不复权改名写入 hfq**；缺口理由与交易所/深交所快照、分红送配原件及 live 东财断连复现一致。**Follow-up（非阻塞合入 #108）**：8 只 hfq 仍依赖东财 `fqt=2` 恢复或 Owner 书面接受缺口；ndx100 等载体序列完整性仍受影响。**未**跑 v4 候选 PnL、**未**汇总 2016+ 组合收益、**未**改 prereg/LOCK/tag。

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R1e #105 follow-up（PR #108）spot-check
- Date: 2026-10-29 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（Review PR 仅追加本文件）
- Dev: PR #108 · head `6d2fa8fdf6792a658736e5d26a2eeea3575acafe`
- Prior review: `operations/reviews/2026-10-29-v4-r1e-census-spotcheck.md`（follow-up 项）
- Dev work log: `operations/work_logs/2026-10-29-v4-r1e-hfq-followup.md`
- Specs: `docs/manual/data-principles.md`（东财 hfq 优先；禁止 raw→hfq 重命名）

## 证据总表

| 检查项 | 方法 | 结论 |
| --- | --- | --- |
| 库 SHA256 | `git lfs pull` + `sha256sum data/market.sqlite` | **5bbb9eba6095e6066ce7d01bc8e3bba4ec63a2fa3109449b6de759eb0367de27**（290332672 B）；作业前 **f5ac9944…**（290242560 B）；与 `summary.json` **一致** |
| `PRAGMA integrity_check` | 只读连接 | **ok** |
| `bars` 行数 | `SELECT COUNT(*)` | **1039735**（+542 vs 普查后 1039193） |
| 全库同日重复 | `GROUP BY code,date,adj HAVING COUNT(*)>1` | **0** |
| 520900 raw | 行数 / 来源 / 窗口 | **542** 行，`2024-07-10`…`2026-09-30`，`source=sse_yunhq` **仅此** |
| 520900 hfq 未改 | 行数 + 2026-09-30 close | **542** 行，`eastmoney_etf_hfq`；末日收盘 **1.048**（与 #105 后一致） |
| 8 只 hfq | `adj=hfq` 计数 | 513820、513910、159501、159687、159688、159822、160125、160644 均为 **0** |
| raw 未冒充 hfq | 8 只 `GROUP BY adj,source` | 仅既有 **raw**（`eastmoney_etf` 或 `tencent_etf`），**无** hfq 行 |
| 只插入纪律 | PK + 触发器；fill `inserted` | 520900 raw `in_db`；8 只 hfq `gaps` + `未写入 adj=hfq` |
| 单测 | `tests/v4/data/test_r1e_followup.py` | **4** ran，**OK** |
| PnL / 2016+ | 硬规则 | **未**运行 |

## 520900 不复权 spot-check（5/5 日）

Reviewer 用 `incoming/.../sse/520900-raw.json.gz` **解压 JSON SHA256** `6ea74e1e…`（= `fill.csv` `sha256`）对比 sqlite `bars`（`adj=raw`, `source=sse_yunhq`）。

| 日期 | sqlite close | SSE payload close | |
| --- | --- | --- | --- |
| 2024-07-10 | 0.962 | 0.962 | **pass**（上市日 raw=hfq 收盘同值，符合 Dev 声明） |
| 2025-01-02 | 0.921 | 0.921 | **pass** |
| 2025-06-30 | 0.962 | 0.962 | **pass** |
| 2026-09-22 | 0.992 | 0.992 | **pass** |
| 2026-09-30 | 0.990 | 0.990 | **pass** |

后复权对照：2026-09-30 **raw 0.990** vs **hfq 1.048** → 确认为 **不同 adj 序列**，非误标。

## 8 只后复权缺口 spot-check

### 库内状态（8/8）

| 代码 | hfq 行数 | 2026-09-30 raw close | raw source |
| --- | --- | --- | --- |
| 513820 | **0** | 1.220 | eastmoney_etf |
| 513910 | **0** | 1.577 | eastmoney_etf |
| 159501 | **0** | 2.205 | tencent_etf |
| 159687 | **0** | 1.871 | tencent_etf |
| 159688 | **0** | 0.694 | tencent_etf |
| 159822 | **0** | 0.564 | tencent_etf |
| 160125 | **0** | 1.514 | tencent_etf |
| 160644 | **0** | 1.978 | tencent_etf |

### 交易所 / 原件交叉（≥3 只）

| 代码 | 2026-09-30 交易所今收 | sqlite raw | 方法 | |
| --- | --- | --- | --- | --- |
| **513820** | **1.220** | 1.220 | Reviewer live `yunhq.sse.com.cn` dayk | **pass** |
| **513910** | **1.577** | 1.577 | Reviewer live SSE dayk | **pass** |
| **159501** | **2.205** | 2.205 | `incoming/.../szse/159501-2026-09-30.json.gz` | **pass** |
| **160125** | **1.514** | 1.514 | `incoming/.../szse/160125-2026-09-30.json.gz` | **pass** |

分红送配辅证（`parse_fhsp` 对冻结 HTML）：513820 **28** 次分红、0 拆分；513910 / 159501 **0** 分红；160125 **4** 次分红 — 与 `gaps.csv` / work log **一致**；页面性质为净值分红档案，**非**场内后复权 K 线。

### 东财 hfq 断连（Reviewer 独立复现）

| 探测 | 结果 |
| --- | --- |
| live `push2his` · 159501 · `fqt=2` · 2026-09-29/30 | **RemoteDisconnected** |
| 行情脚本 host | `incoming/.../fund2-kline-host.txt` 指向 **push2his.eastmoney.com** |

结论：8 只缺口为 **真缺东财 hfq payload**，Dev **未**用交易所 OHLC 冒充 `eastmoney_etf_hfq`。

## Blockers / Follow-ups

| 类型 | 项 | 说明 |
| --- | --- | --- |
| **Blocker** | （本 spot-check 无） | — |
| **Follow-up** | 8 只 hfq | 待东财恢复或 Owner 接受 documented gap；159501 等仍影响 ndx100 / 主题载体 hfq 完整性 |
| **Follow-up** | 513820 汇添富页 404、159822 银华 521 | 已记入 gaps；不影响「未写假 hfq」结论 |
| **说明** | Live 东财 | Reviewer VM 上 push2his 不稳定；bar 结论以 **incoming + sqlite + 交易所 spot** 为准 |

## 合入顺序

1. **先**合 Dev PR **#108**（520900 raw + 缺口文档 + 库）。
2. **再**合本 Review PR（仅 `operations/reviews/2026-10-29-v4-r1e-hfq-followup-spotcheck.md`）。

## 链接

- Dev PR：https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/108
- Review PR：（本分支推送后填写）
