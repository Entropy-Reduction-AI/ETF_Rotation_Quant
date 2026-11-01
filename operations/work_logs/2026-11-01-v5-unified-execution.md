# v5 成交与 v4 B0 对齐

## Metadata

- Project: ETF_Rotation_Quant
- Task: 按 2026-11-01 裁定，把 v5 每次运行改到与 v4 B0 相同的 `simulate_path`
- Date: 2026-11-01
- Owner: project owner
- Route: direct-execute
- Source of truth: `operations/planning/2026-11-01-v5-engine-rulings.md`；冻结预注册 `docs/prereg/etf-multiasset-rotation-prereg-v5.md`

## 结果

S0、P1、P2、稳健性和结构对照的成交都从 `run_arm` 进入，再调用 v4 B0 用的 `_run_path` → `simulate_path`。只跑周、月两路。C2 关着时 `exit_drawdown=None`，不再调用 `book.simulate`。固定预算在 m = 0 时退回 S0 的 k = 0 防守袖。P2 的上一版由 C1 是否过关决定，写进 ledger `params` 的 `base_arm`。

设计期没有跑。没有写 `results/v5/LOCK`。没有创建、移动或删除标签。没有计算 2016-01-01 及以后的中国组合收益。

## 改动面

- `src/v3/engine/exit.py`：`exit_drawdown=None`（`NO_EXIT`）表示不离场。不传时仍是 10%。
- `src/v3/engine/arms.py`：`_run_path` 接受这个取值。B0 仍传 0.10。
- `src/v5/engine/paths.py`：单路 `run_path` 一律走 `_run_path`。延后 1 天的第二次成交与 `src/v4/r5/design.py` 的 `_execute` 相同。
- `src/v5/engine/execute.py`：`run_arm`。周、月两路，参数与 B0 的 `_run_path` 相同，不补位。
- `src/v5/engine/allocate.py`：固定预算 m = 0 调用 `_place_defense`。`path_decisions` 可以传入四个回看期。
- `src/v5/campaign.py`、`src/v5/__main__.py`：§6.1。C1 过关则 P2 的 `base_arm` 为 P1，否则为 S0，并写入账本。
- `tests/v5/engine/`：①②③ 与账本选择。

`python -m src.v5 design` 会跑设计期。这次没有执行。

## 验证

① 用改过的 `simulate_path` 重跑 v4 B0 两个池，日净收益与 `results/v4/r5/design/B0/*/net.csv` 逐日相同（`.12g` 文本），SHA256 与 `summary.json` 的 `net_sha256` 相同。

- U-指数：`77fc2f7bdeae577f6329924fa590a5813414a65d626b4c9cf393c16cc3015482`，2671 日，止于 2015-12-31
- U-可交易：`f02d20ca7e848d0a1c817022a594e5c404c2d1012d8ceb8bb77e30bd79a42bab`，2671 日，止于 2015-12-31

② `test_s0_and_c2_defer_the_same_limit_up_when_exit_never_fires`：离场不触发时，S0 与 C2 的日收益、持仓、费用相同；连续涨停时两边都把买单顺延到能成交的交易日。没有涨跌停的对照在更早的交易日成交。

③ `test_fixed_budget_parks_closed_classes_in_defense`：没有风险大类参加排名时，权重等于同一组袖套上的 S0（国债、黄金开着则等分；都没开着才是现金）。

```bash
.venv/bin/python -m unittest discover -s tests/v3/engine -t .
# Ran 61 tests in 21.802s  OK

.venv/bin/python -m unittest discover -s tests/v4/engine -t .
# Ran 32 tests in 10.122s  OK

.venv/bin/python -m unittest discover -s tests/v5 -t .
# Ran 36 tests in 127.127s  OK
```

v5 这 36 项含上面的 ①②③。行情库 SHA256 为 `167d4e39ffab4302e6f55d2b3436b3400ea28b2282cd7f9b9bda644d87c1acf3`。

## 没有另造的规则

- 溢价：`run_arm` 调用 `arms._schedule`，与 B0 的 `execute` 相同。有溢价输入时，(W, θ) 仍由那条滚动前推选出，不按 v5 自己的收益重选。
- 延后 1 天的第二次 `simulate_path` 不传 `premium`、`code_levels`、`code_returns`、`cross_border`、`dividend_yield`。`design._execute` 就是这样写的。第一次成交仍传全套。
- B0 的 `cross_border` 是关的。设计期同样不传跨境成本对象。开关若打开，名字仍用行情上的 v4 `asset_classes`（`names_for`），不是 v5 大类名「美股」。
- `check_drawdown` 仍接受 15%。v5 §7.1 只点了 8% 和 12%。这里没有另禁 15%，设计期脚本也没有 15% 这一行。
- 「去掉最好的 1/2/3 只」和「不含相近替身」没有单独的枚举脚本。调用方先改池子或 `allow_substitute`，再进 `run_arm`。`python -m src.v5 design` 只覆盖 §6.1 的 S0、P1、P2。
- P1 的 `params.base_arm` 写成 `S0`，因为 §6.1 表里 P1 的比较对象是 S0。裁定点名要写入的是 P2。

## 下一步

Reviewer 签收之前不要跑设计期，不要写 LOCK，不要打标签。
