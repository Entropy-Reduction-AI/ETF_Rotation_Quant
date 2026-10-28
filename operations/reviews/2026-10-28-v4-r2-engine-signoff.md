# v4-R2 · Dev 引擎开关签收 · 2026-10-28

## Decision：`approve`

在 Dev PR [#67](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/67) **rebase 后**尖端 `c4eebdc52c4da05a981b423277541f43818ef22c`（引擎 `6ee2f091e5e9fef4cee1a41765a76c11d81c8118`，base `a5b6fb434404802555c3925755929b192e89c4d7`）上，Reviewer **独立复跑** Decision 门禁：开关全关时 P1 九项 SHA 与 `milestone/v3-code-freeze`（`b1f84d89…`）登记值一致；涨跌停/停牌/跨境占位/T1–T3 开闭测试通过；PR diff 无 R1 数据/registry 静默改动、无 scorecard 或 2016+ 组合 PnL 泄漏。**预 rebase 尖端 `c786a8a` 的结论作废**；本签收仅覆盖 `c4eebdc`。

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R2（D13 · 成交限制、跨境成本挂钩、T1–T3 机制开关）
- Date: 2026-10-28 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（本 PR 仅 `operations/reviews/**`）
- Dev: PR #67 · branch `cursor/v4-r2-engine-8e66`
- Work log（Dev）: `operations/work_logs/2026-10-28-v4-r2-engine.md`（§Rebase 以 `a5b6fb4` 为准）
- 冻结参照: annotated tag `milestone/v3-code-freeze` → `b1f84d899f4a37914c1ce4ef0ab16484f0ef7cdb`（未移动）
- `data/market.sqlite` SHA256: `3e3e6f1d594586da2abf28db5fa88b05c1cc91fa29adf061fc699e1b8d4bc1d6`（main `#65` 后；P1 摘要仍与冻结一致）

## A. 复跑命令（签收时在 detached `c4eebdc`）

环境：仓库根 `.venv`；`git lfs pull`；`mkdir -p outputs`；**必须** `PYTHONHASHSEED=0` 跑 P1 对照。

| 步骤 | 命令 | 日志 |
| --- | --- | --- |
| R2 + 引擎回归（63） | `PYTHONHASHSEED=0 .venv/bin/python -m unittest tests.v3.engine.test_v4_r2 tests.v3.engine.test_exit_a1_boundary tests.v3.engine.test_l2 tests.v3.engine.test_v31 tests.v3.engine.test_holiday tests.v3.diag.test_limit_close` | `/opt/cursor/artifacts/v4-r2-reviewer-gate-63-c4eebdc.log` |
| v3 全量 | `.venv/bin/python -m unittest discover -s tests/v3 -t .` | `/opt/cursor/artifacts/v4-r2-reviewer-discover-v3-c4eebdc.log`（**136** OK） |
| v4（R1 已合 main） | `.venv/bin/python -m unittest tests.v4.test_scorecard tests.v4.data.test_ingest` | `/opt/cursor/artifacts/v4-r2-reviewer-v4-modules-c4eebdc.log`（**17** OK） |
| P1 冻结门 | `PYTHONHASHSEED=0 .venv/bin/python -m unittest tests.v3.engine.test_v4_r2.FreezeP1` | 同上 gate log 内 `FreezeP1` |
| Reviewer 独立摘要 | `PYTHONHASHSEED=0 .venv/bin/python operations/reviews/diag/v4/v4-r2-freeze-p1-verify.py --dev-tip c4eebdc… --freeze-worktree /tmp/freeze-wt --json-out operations/reviews/diag/v4/2026-10-28-v4-r2-engine-signoff-rerun.json` | 需在含 R2 引擎的 checkout 上执行 |

独立脚本与 JSON 产物：`operations/reviews/diag/v4/v4-r2-freeze-p1-verify.py`、`operations/reviews/diag/v4/2026-10-28-v4-r2-engine-signoff.json`。

## B. Decision 证据表

| 门禁 | 方法 | 结果 |
| --- | --- | --- |
| **1 · 开关全关 ≡ 冻结 P1** | `execute(…, switches=EngineSwitches())` 与无 `switches`；九项 SHA；另在 worktree `b1f84d89` 跑冻结 `execute` 核 net SHA | 九项与 Dev/work_log 表一致；冻结 net SHA **匹配** |
| **2 · 涨跌停边界** | `test_v4_r2.LimitBands` + `FillLimitPaths`；创业板 **2020-08-24**、科创板 **2020-08-21** 切 ±20%；ETF 原始价 | 单元测试 **OK**（见 JSON `limit_boundary_evidence`） |
| **3 · 跨境成本占位** | `CrossBorderCosts()` 全 0 不改变路径；占位仅在显式传入时 | `CrossBorderHook` **OK** |
| **4 · T1/T2/T3** | `TurnAndRefill` 开/关；默认全关走原 `group_decisions` / 无 refill | **OK** |
| **5 · 范围** | `git diff a5b6fb4..c4eebdc`：10 文件，仅 engine + R2 测试 + work log；无 `data/`、`config/`、`results/`、`src/v4/scorecard` | **通过** |
| **2016+ / LOCK / tag** | 未跑候选组合；未写 LOCK；未动 tag / 未 merge main | **遵守** |

### B1 · P1 SHA256（Reviewer 独立，`PYTHONHASHSEED=0`）

| 序列 | SHA256 | 与冻结登记 |
| --- | --- | --- |
| net | `962178c503df7d1ee900971711271fc4fac4436522053dbc9c297b48c3b8fa57` | 一致 |
| held | `bdd1521f7d9d66404184351dfe50e3e4681edfd91415e46572394c44d6eea32b` | 一致 |
| cost | `62b76e5375f73360de7e4b03753808bd00058310c7dc35ce353ca091a4e44e0c` | 一致 |
| 3-week … 8-month | 见 JSON / Dev work log | 六项均一致 |

窗口：2005-01-04 → 2015-12-31，**2671** 交易日。

## C. Notes（非否决）

1. **Work log 首段**仍写旧 base `0eb25e2` / 旧引擎 SHA；§「Rebase 到 a5b6fb4」已更正——签收以 **gh PR #67 @ `c4eebdc`** 为准。
2. **`unittest discover -s tests/v4`** 会因 `src/v4/data/__main__.py` 打印用法而异常退出；Dev/work log 已改为显式跑 `test_scorecard` + `test_ingest`（17 项），Reviewer 同法复跑。
3. **`FreezeP1`** 现要求子进程不得因缺库 `skip` 冒充通过（rebase 后改进）；签收前须 `git lfs pull`。

## D. Reviewer 纪律

未 merge main、未创建/移动/删除 tag、未写 `results/v3/LOCK`、未计算 2016-01-01 及以后组合 PnL、未改 Dev #67 业务代码（本 PR 仅 review 文档与 diag）。

---

本人，ETF Rotation Reviewer，于 2026-10-28 对 Dev PR #67 @ `c4eebdc52c4da05a981b423277541f43818ef22c` 签收：**`approve`**。
