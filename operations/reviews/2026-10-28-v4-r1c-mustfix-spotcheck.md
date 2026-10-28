# v4-R1c · 必须修 12 · spot-check · 2026-10-28

## Decision：`approve_with_follow_up`

在 Dev PR [#85](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/85) 尖端 `48f50796640ff4c98c0f1c105dd2473c8ff1922c`（base `e338a5b`）上独立复核：写入后 `market.sqlite` SHA、`PRAGMA integrity_check`、`bars` 行数、v4/v3 单测、7 符号 12 条原 must_fix 修复与清单重扫均与 Dev 声明一致。**未发现 Dev 阻塞缺陷**。Follow-up 仅属 Manager / Orchestrator：`需要 Orchestrator` **15** 行与 `e338a5b` 分类完全一致；清单新增 **42** 行 `manager_class` 留空的后复权缺交易日（三只 LOF carry 尾部，accept 口径遗留，非 must_fix）。

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R1c D15-9 必须修 12 follow-up spot-check
- Date: 2026-10-28 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（本 PR 仅 `operations/reviews/**`）
- 签收对象（Dev）: PR #85 · head `48f50796640ff4c98c0f1c105dd2473c8ff1922c`
- Dev work log: `operations/work_logs/2026-10-28-v4-r1c-mustfix.md`
- 前次 R1c spot-check: `operations/reviews/2026-10-28-v4-r1c-spotcheck.md`（#83 / Dev #82）
- Review branch: `review/v4-r1c-mustfix-spotcheck`（基于 Dev tip，仅追加评审产物）

## 证据总表

| 检查项 | 方法 | 结论 |
| --- | --- | --- |
| 库文件 SHA | `git lfs pull` + `sha256sum data/market.sqlite` | **6c896fd1e5de6bc66ddf6f42833033f202f6e480f4d78c6cd267c6c6a4362248**（246054912 B）与 Dev **一致** |
| 写入前 SHA | 任务登记 / LFS oid @ `e338a5b` | **43bf125532da01fb6f0056db77f2ab05b3da3f0bdc5f32fa33502bafffd922fc** |
| `PRAGMA integrity_check` | 只读 URI | **ok** |
| `bars` 行数 | `SELECT COUNT(*) FROM bars` | **787005** |
| `-wal` / `-shm` | 文件系统 | **无** |
| v4 单测 | `unittest discover -s tests/v4` | **58** OK |
| v3 单测 | `unittest discover -s tests/v3` | **136** OK |
| 组合 PnL / 2016+ 收益汇总 | 硬规则 | **未**运行 |
| LOCK / tag / 合 main | PR diff | **无** LOCK；**无** tag；Reviewer **未**合 main |

## 1. Sqlite / 清单计数

- Post-write SHA256 match Dev claim: **yes**
- `integrity-findings.csv`：**2419** 行（较 #82 重扫 +30，来自 carry 尾部缺交易日行）
- `manager_class` 计数：

| manager_class | 行数 |
| --- | ---: |
| 必须修 | **0** |
| 可以接受 | **2362** |
| 需要 Orchestrator | **15** |
| 留空 | **42** |

- 原 12 条 must_fix 对应检查类型在重扫后：**adj_discontinuous 0**；三只 LOF 的 **ended_before_cutoff 0**；159952/588050/588080 相关 **large_move 0**（剩余 **large_move** 仅 XLE 2020-03-09，仍为 accept）
- **42** 行留空：均为 `missing_trade_days`，代码仅 **160125 / 161831 / 164705**，与 Dev 工作日志「carry 后复权缺交易日、未填分类」一致；Reviewer **未**填写 `manager_class`

### Orchestrator 15 未改动

与 `e338a5b` 上已分类的 15 行 `(code, check, date)` 集合 **逐行一致**（931160×6、HSTECH×1、161229×2、510300/510500/510880/512100/515180 各 1）。Reviewer **未**修改这些行的数据或口径。

## 2. 按符号 spot-check

| 代码 | 原 must_fix 主题 | Reviewer 结论 | 要点 |
| --- | --- | --- | --- |
| **159922** | adj_discontinuous 2024-12-02 | **pass** | `v4_corp_action` 登记 `split` 除权日 2024-12-02、比例 2.5/1；`cash_dividends` 0.1292/股保留；腾讯 hfq 1.93→1.961 未改价；期望日收益 +1.6074% vs 实际 +1.6062%（差 0.0012pp）；清单 **无** 159922 行 |
| **160125** | ended_before_cutoff | **pass** | 腾讯 hfq 止于 2019-07-03；`tencent_etf_hfq_carry` 自 2019-07-04 至 2026-09-30（1721 行）；与 anchor 比例一致、与 carry **0** 日期重叠；`r1c-mustfix-hfq-extend.csv` overlap_max_abs=0 |
| **161831** | ended_before_cutoff | **pass** | 腾讯止于 2020-12-31；carry 2021-01-05→2026-09-30（1392 行）；公式与无重叠 **ok** |
| **164705** | ended_before_cutoff | **pass** | 腾讯止于 2020-11-30；carry 2020-12-02→2026-09-30（1410 行）；公式与无重叠 **ok** |
| **159952** | large_move 2024-10-08 | **pass** | raw 收盘=前收×1.2 四舍五入 1.618；**Sina** 不复权 1.618 一致；`v4_move_check`/`r1c-mustfix-verified.csv` limit_up；清单无 large_move |
| **588050** | large_move 2024-09-30、2024-10-08 | **pass** | 两日涨停价与库内 raw、**Sina** 一致；`v4_move_check` 四行（raw+backward）；清单无 large_move |
| **588080** | large_move 2024-10-08 | **pass** | 同上；Sina 1.097；清单无 large_move |

## 3. 范围与纪律

- PR diff：仅 `data/market.sqlite`、R1c 清单/CSV、`src/v4/data/{integrity,r1c}.py`、v4 测试、工作日志；**无** Orchestrator 15 行 `manager_class` 或数据改动
- Reviewer：**未**写 LOCK；**未**移动 tag；**未**跑 v4 候选 PnL 或 2016-01-01+ 组合收益

## Dev 缺陷 vs Manager / Orchestrator follow-up

| 类型 | 项 | 说明 |
| --- | --- | --- |
| **Dev 缺陷** | （本 spot-check 无） | 12/12 修复项与重扫判据满足 |
| **Manager follow-up（非 Dev）** | 42 行留空 `missing_trade_days` | 三只 LOF carry 后复权缺交易日；可并入 accept 或单独登记，**非** must_fix 回归 |
| **needs_Orchestrator（15）** | 931160、HSTECH、161229、载体 list_date_unknown 等 | 与 #84 分类一致；**非** #85 范围 |
| **accept 遗留** | XLE 2020-03-09 `large_move` 等 | 仍为 accept；与 Dev 工作日志一致 |

## 诊断 artifact

| 产物 | 路径 |
| --- | --- |
| JSON | `operations/reviews/diag/v4/2026-10-28-v4-r1c-mustfix-spotcheck.json` |

## Review PR

- Review 签收 PR：（本分支 push 后创建）
- Dev must-fix PR：https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/85
