# v5 统一 B0 成交 · 代码签收 · 2026-11-01

## Metadata

- Project: ETF_Rotation_Quant
- Document type: review（Dev PR #163 代码签收）
- Date: 2026-11-01（Asia/Taipei）
- Author: ETF Rotation Reviewer（独立复核）
- Route: review-only（仅 `operations/reviews/**`；未改业务代码、预注册、裁定稿、`results/v5/LOCK`、tag；未 merge）
- 目标 PR: [#163](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/163) · 分支 `cursor/v5-unified-execution-dd1e`
- 复核 head: `1de98f31dd0487ff2bbe6dc39d007521406023cc`
- Base（签收时）: main `20559d1`（#161 裁定合入后）
- 依据: `operations/planning/2026-11-01-v5-engine-rulings.md`；冻结预注册 `docs/prereg/etf-multiasset-rotation-prereg-v5.md`
- Dev 工作记录: `operations/work_logs/2026-11-01-v5-unified-execution.md`

## Decision（对 #163）

**approve**

在 PR #163 尖端 `1de98f31` 上：回归 ① 两池 B0 日净 SHA256 与登记一致；v5 成交统一经 `run_arm` → `_run_path` → `simulate_path`，C2 关时 `exit_drawdown=None`（`NO_EXIT`），不再走 `book.simulate`；固定预算 m=0 退回 S0 k=0 防守；P2 `base_arm` 由 C1 过关自动写入 ledger `params`（§6.1，仅代码与单测，未跑设计期）。Reviewer 独立复跑 v3 61 / v4 32 / v5 36 项单元测试全部通过。未跑设计期、未写 LOCK、未动 tag。

| 级别 | 数量 |
| --- | --- |
| must（阻塞） | **0** |
| should（建议跟进） | **0** |
| note（非阻塞） | **1**（见文末） |

---

## 回归 ① · v4 B0 两池日净 SHA256

行情库：Git LFS 拉取后 SHA256 `167d4e39ffab4302e6f55d2b3436b3400ea28b2282cd7f9b9bda644d87c1acf3`（与 `src/v4/r5/design.py` 登记一致）。

| 池 | 登记 `net_sha256` | Reviewer 重算 | 日数 | 末交易日 |
| --- | --- | --- | --- | --- |
| U-指数 | `77fc2f7bdeae577f6329924fa590a5813414a65d626b4c9cf393c16cc3015482` | **相同** | 2671 | ≤ 2015-12-31 |
| U-可交易 | `f02d20ca7e848d0a1c817022a594e5c404c2d1012d8ceb8bb77e30bd79a42bab` | **相同** | 2671 | ≤ 2015-12-31 |

方法：`execute_job(B0, pool)` 与 `results/v4/r5/design/B0/*/net.csv` 逐日 `.12g` 文本比对；`tests/v5/engine/test_b0_regression.py` 独立通过（约 134s）。

---

## 执行入口参数 · vs v4 B0（`design._execute` / `arms._run_path`）

对照基准：B0 `Job.switches()` → `fill_limits=True`；`decision_delay=0` 时走 `execute(..., arm="A")` 内 `_run_path`；`decision_delay=1` 时第二次 `simulate_path` 仅传 `fill_limits`/`fill_quotes` 及 eps、乘数（与 `design._execute` 延后分支一致）。

v5 生产路径：`campaign.run_design` → `run_arm`（周、月两路）；稳健性 / §7.1 结构对照在 API 层同样只经 `run_arm`（`structure=` / `lookbacks` / `cost_multiplier` / `decision_delay` / `exit_drawdown` 由 `version_params` 写入 ledger，当前 CLI 仅暴露 `design` 步，未在本签收中运行）。

| 检查项 | v5 入口 | 与 B0 一致 | 说明 |
| --- | --- | --- | --- |
| `fill_limits` / `fill_quotes` | `run_arm`：`b0_switches()` + `quotes_from_market` | **Y** | 与 B0 `Job.switches()` 单测对齐（`test_execute.SharedEntry`） |
| `premium` | `run_arm`：`_schedule(...)` | **Y** | 与 `arms.execute` A 臂相同；延后第二次不传（同 v4） |
| `code_levels` / `code_returns` | `_run_path` → `simulate_path`（来自 `market`） | **Y** | B0 行情经 `Markets.get` 已装载 |
| `cross_border` / `dividend_yield` | `_run_path` 当 `switches.cross_border` 非空 | **Y** | B0 设计期开关为关；单测覆盖开开关时转发 |
| `trade_eps` / `weight_eps` | `spec` → `_run_path` | **Y** | `version_params` 写入 ledger |
| `cost_multiplier` | `run_arm` 复制到 `market.cost_multiplier` | **Y** | 默认 1.0 |
| C2 关 · `exit_drawdown` | `resolve_exit` → `NO_EXIT`（`None`） | **Y** | 不再调用 `book.simulate`；`simulate_path` 内 `drawdown is None` 不挂离场 |
| C2 开 · `exit_drawdown` | 默认 `EXIT_DRAWDOWN`（0.10） | **Y** | P2 / 稳健性点名阈值经 `version_params` |
| T+1 `decision_delay` | `delay_book` ↔ `design._execute` 延后分支 | **Y** | `test_paths.test_delay_moves_the_fill_one_session_and_c2_stays_identical` |
| 路数 | 仅 `week` + `month` | **Y（ intentional）** | 预注册 §4.1；非六路平均 |
| 补位 | `refill_targets=None` | **Y** | v5 不传 T3 补位 |

---

## 回归 ② · C2 关仍走 `simulate_path`（S0 ≡ 离场不触发的 C2）

| 检查 | 结果 |
| --- | --- |
| `NO_EXIT` 向后兼容 | `exit.py`：`check_drawdown(None)` → 不触发 `triggered` |
| S0 与 C2（离场从不触发）日收益 / 持仓 / 费用一致 | **通过** · `test_s0_and_c2_defer_the_same_limit_up_when_exit_never_fires` |
| 涨跌停顺延两边一致 | **通过** · 同上（涨停顺延到可成交日） |
| `grep book.simulate` under `src/v5` | 仅文档注释，无调用 |

---

## 回归 ③ · 固定预算 m=0 → S0 k=0 防守

Orchestrator 裁定 #2（2026-11-01）：m=0 时退回 S0 的 k=0 防守位（开着的防守大类等分，全关才现金）。

| 检查 | 结果 |
| --- | --- |
| `_fixed_budget` 无参加排名风险大类 → `_place_defense` | **通过** · 读 `allocate.py` |
| 单测 vs 同袖套 S0 | **通过** · `test_fixed_budget_parks_closed_classes_in_defense` |

---

## §6.1 · P2 `params.base_arm`（未跑设计期）

| 检查 | 结果 |
| --- | --- |
| C1 过关 → `base_arm=P1`，且 P2 带 C1+C2 | **通过** · `version_flags` / `test_campaign` |
| C1 不过 → `base_arm=S0`，P2 仅 C2 | **通过** |
| `record_version` 写入 ledger 行含 `base_arm` | **通过** · 临时 ledger 单测 |
| 拒绝写 v3/v4 ledger 与 LOCK | **通过** |

---

## 单元测试（Reviewer 独立）

环境：`.venv` + LFS 行情库；`mkdir -p outputs`。

```bash
.venv/bin/python -m unittest discover -s tests/v3/engine -t .
.venv/bin/python -m unittest discover -s tests/v4/engine -t .
.venv/bin/python -m unittest discover -s tests/v5 -t .
```

| 套件 | 结果 |
| --- | --- |
| v3/engine | **61 OK**（~22s） |
| v4/engine | **32 OK**（~10s） |
| v5 | **36 OK**（~130s，含 ①②③） |

未跑：`python -m src.v5 design`、2016+ 中国组合 PnL、全库 `unittest discover`。

---

## 边界清单

| 项 | 结果 |
| --- | --- |
| 设计期组合回测 | **未跑** |
| `results/v5/LOCK` | **不存在** |
| v3/v4 trial ledger 字节 | **未改**（`test_campaign` 哈希前后一致） |
| tag | **未移动 / 未删 / 未建** |
| 预注册 / 裁定稿 | **未改** |
| 设计期结束日 | 重算 B0 ≤ **2015-12-31** |

---

## Note（非阻塞）

- **稳健性 / §7.1 结构 CLI**：当前 `python -m src.v5` 仅 `design` 子命令；结构对照与稳健性参数已在 `version_params` / `run_arm` 预留，待后续 runner 接线。成交入口已统一，不阻塞 #163。

---

## 关联

- Dev PR: [#163](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/163)
- 本 Review PR: （由 Cursor PR 工具创建后补链）
