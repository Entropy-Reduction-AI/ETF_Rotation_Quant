# v5 引擎 S0 / C1 / C2 / 部件过关 · 代码签收 · 2026-11-01

## Metadata

- Project: ETF_Rotation_Quant
- Document type: review（Dev PR #159 代码签收）
- Date: 2026-11-01（Asia/Taipei）
- Author: ETF Rotation Reviewer（独立复核）
- Route: review-only（仅 `operations/reviews/**`；未改业务代码、`config/v5/classes.csv`、预注册、`results/v5/LOCK`、tag；未 merge）
- 目标 PR: [#159](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/159) · 分支 `cursor/v5-engine-s0-c1-c2-889e`
- 复核 head: `792ab6d375b4d81718fc09fd0aee9f056c0d63b9`
- Base（签收时）: main `81e0c5c43cd908665b1c454129460620a0764763`（`milestone/v5-prereg-freeze` 之后）
- 依据: `docs/prereg/etf-multiasset-rotation-prereg-v5.md`（冻结稿；§4.1–4.4、§6.2、§7.1 结构对照）
- Dev 工作记录: `operations/work_logs/2026-11-01-v5-engine-s0-c1-c2.md`

## Decision（对 #159）

**approve**

在 PR #159 尖端 `792ab6d` 上，对照冻结预注册逐项核对：`config/v5/classes.csv` 与 inventory 草稿字节一致；S0 / C1 / C2 / 两路合成 / §7.1 三种结构对照 / `component_gate()` 与 §4、§6.2、§7.1 字面一致；Reviewer 独立复跑 `tests/v5` **24** 项全部通过。未跑设计期、未写 LOCK、未动 v3/v4 源码。五处 Orchestrator 歧义不违背预注册字面，记为 **note**，不阻塞合入。

| 级别 | 数量 |
| --- | --- |
| must（阻塞） | **0** |
| should（建议跟进） | **0** |
| note（已登记、非阻塞） | **5**（见 §Orchestrator 歧义） |

---

## 对照清单（vs 预注册）

| # | 检查项 | 方法 | 结果 |
| --- | --- | --- | --- |
| 1 | `config/v5/classes.csv` = `results/v5/inventory/classes-draft.csv`（117 行；无静默编辑） | `diff -q`；MD5；`tests/v5/test_classes.py` | **通过**。两文件 MD5 `ab99ef22…` 相同；数据行 **117**（+ 表头 1）；`load_classes()` 行数门禁一致。 |
| 2 | **S0 §4.2**：风险大类开着 → 等分、每类一只 best-`s`；k=0 → 国债/黄金分别判断再等分；全无 → 该 L 组全现金 | 读 `allocate.py`（`group_weights`、`_place_defense`、`_risk_split`）；`tests/v5/engine/test_allocate.py` | **通过**。防守仅 k=0 启用；单类开着 100% 给最强一只；国债/黄金分桶后等分；全关 `{cash:1}`。 |
| 3 | **C1 §4.3**：`m = min(1, σ250/σ20)` 只乘风险类目标权重；削下来的进现金；防守不乘 | `apply_c1`、`vol_multiplier`、`blend_lookbacks`；单测 | **通过**。`class_of` 非 `RISK_CLASSES` 跳过缩放；释放权重累加 `cash`。 |
| 4 | **C2 §4.4**：v3.1 §4.5 单只 −10% 离场，分路；`simulate_path`；不补位；所得留现金 | `paths.run_path`；`EXIT_DRAWDOWN==0.1`；`refill_targets=None`；单测 | **通过**。阈值常数 **0.1**；触发后 `held` 全进 `cash`，不买 `other`。 |
| 5 | **§7.1** 三种结构对照：最强一类 / 固定预算 / 无防守 — 各改 L 组第 3 步，再经第 4 步 ÷4 | `STRUCTURES`、`group_weights(..., structure=…)`；`path_decisions` 先四组再 `average_lookbacks` | **通过**。最强一类 k=0 回退 S0 防守；固定预算 closed 份额走 k=0 防守规则；无防守 k=0 全现金。 |
| 6 | **§4.1**：`r_A = (r_周 + r_月)/2`；两路同一日历 | `arm_return`；单测拒绝错位索引 | **通过**。索引必须 `equals`；算术平均；2016+ 组合日收益在 gate 路径拒绝（见边界）。 |
| 7 | **§6.2** `component_gate()`：列名与四条 pass 逻辑 | `gate.GATE_COLUMNS`、`_compare_row`、`_report_row`；`tests/v5/test_gate.py` | **通过**。17 列与预注册一致；S0 行 `pass` 及比较列留空；guard 按目标状态排除对应状态；tradable 差 **百分点**（×100）。不要求写 `component-gate.csv`。 |
| 8 | **单元测试**（Reviewer 复跑） | 见下节 | **24 OK**（0.123s）。 |
| 9 | **边界** | diff 范围；grep 设计期/LOCK | **通过**。见 §边界清单。 |
| 10 | **Orchestrator 歧义** | PR body + work log §交给 Orchestrator | **5 条 note**，不违反字面 → 不升格为 must/should。 |

---

## 测试复跑（Reviewer 独立）

环境：仓库根 `.venv`（`requirements.txt`）；`mkdir -p outputs`。

```bash
.venv/bin/python -m unittest discover -s tests/v5 -t .
```

| 项 | 结果 |
| --- | --- |
| 合计 | **Ran 24 tests in 0.123s — OK** |
| k=0 国债/黄金分别再等分 | `GroupWeights.test_defensive_classes_are_judged_separately_then_split` |
| 单一风险大类开着 → 100% | `test_single_open_risk_class_takes_the_whole_group` |
| 四回看算术平均、除数恒 4 | `LookbackAverage.*`、`PathAssembly.test_missing_lookback_*` |
| 两路 `r_A` 平均 | `TwoPaths.test_arm_return_is_the_mean_of_the_two_paths` |
| C1 只减风险 / 固定预算 / 结构对照 / gate 边界 | 其余 `tests/v5/**` |

未跑：设计期 `execute`、2016+ 中国组合 PnL、§7.2 别的市场、全库 `unittest discover`。

---

## Orchestrator 歧义（note，非阻塞）

预注册字面未写死的实现选择；Dev 已在 PR / work log 披露。Reviewer 判定均**不违背**已冻结条文，留给 Orchestrator 统一口径或设计期前澄清即可。

| # | 主题 | Dev 选择 | Reviewer |
| --- | --- | --- | --- |
| 1 | 同分 | 仅容器 id 升序，不用 v3 的 R 次关键；跨类打平同理 | §4.2 写明 id 升序；**note** |
| 2 | 固定预算 m=0 | 无任何风险大类「参加排名」→ 该 L 组全现金 | §7.1 未定义此支；字面允许；**note**（Orchestrator 可择一写死） |
| 3 | C1 σ | 样本标准差 `ddof=1`（与 v3 得分波动一致）；σ20=0 → m=1 | §4.3 只写「标准差」；**note** |
| 4 | `component_gate` 的 `pool` | 固定 `index`；S0 行除 `pass` 外比较列亦空；P2 基线由调用方传 `base_arm` | §6.2 列名满足；pool 未规定取值；**note** |
| 5 | S0 vs C2 成交路径 | S0 用 `book.simulate`；C2 用 `simulate_path`；离场不触发时一致（单测）；v4 成交限制仅 C2 路径 | §4.4 要求 v3.1 离场条文；未要求统一 simulate 入口；**note** |

（work log 另列有效日收益过滤、单位等小点，与 v3/v4 沿用一致，不单独升格。）

---

## 边界清单

| 边界 | 结果 |
| --- | --- |
| 设计期引擎 / S0·P1·P2 组合运行 | **未跑**（`src/v5` 仅配权与 gate API；注释明确） |
| 2016+ 中国组合 PnL | **未跑**；`vol_multiplier` / `assert_window` / gate 测试对 2016+ 日期 **拒绝** |
| `results/v5/LOCK` | **未写**（仓库无该路径变更） |
| §7.2 别的市场 F | **未跑** |
| tag 移动/创建/删除 | **未动** |
| `src/v3/`、`src/v4/` | **diff 为零**（`git diff 81e0c5c..792ab6d` 仅 v5 + config + tests + work log） |
| 预注册 | **未改** |
| C2 复用 | 仅 `paths.py` import `simulate_path` / `EXIT_DRAWDOWN`，无 v3 源码编辑 |

---

## 范围摘要（便于审计）

PR #159 相对 main `81e0c5c`：**15 files, +1345** — `config/v5/classes.csv`、`src/v5/**`、`tests/v5/**`、`operations/work_logs/2026-11-01-v5-engine-s0-c1-c2.md`。

---

## 结论

**approve** — 可合入 main（合并不在本 review PR 执行）。设计期运行前 Orchestrator 宜对 §Orchestrator 歧义 five notes 做一次口径确认；不确认也不推翻本次代码签收。
