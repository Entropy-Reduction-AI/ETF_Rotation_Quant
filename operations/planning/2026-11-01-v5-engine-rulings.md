# v5 引擎：Orchestrator 对 9 处歧义的裁定，以及 1 条开跑前必须修的问题（2026-11-01）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning（裁定）
- Status: active
- Owner: L. Loric
- Maintainer: Orchestrator
- Date: 2026-11-01（Asia/Taipei）
- 依据：冻结预注册 `docs/prereg/etf-multiasset-rotation-prereg-v5.md`（`milestone/v5-prereg-freeze`）；Dev 工作记录 `operations/work_logs/2026-11-01-v5-engine-s0-c1-c2.md`；Reviewer 签收 `operations/reviews/2026-11-01-v5-engine-s0-c1-c2-signoff.md`

## 开跑前必须修：所有运行要在同一套交易条件下

`src/v5/engine/paths.py` 的 `run_path` 有两个问题：

1. C2 关着时走 `book.simulate`，没有 v4 的成交限制（涨跌停、停牌顺延）、QDII 溢价模块、多代码载体、跨境时点和分红口径。
2. C2 开着时虽然调用 `simulate_path`，但没有传 `fill_limits`、`fill_quotes`、`premium`、`code_levels`、`code_returns`、`cross_border`、`dividend_yield`、`trade_eps`、`weight_eps`、`cost_multiplier`。

后果：S0、P1、P2 与 B0 不在同一套交易条件下，P2 对 P1 的差别会混进“成交限制开没开”的影响，§6.2、§6.3 的比较都不成立。这违反预注册 §4.1（成交限制 v4 §4.5、收盘时点和汇率 v4 §3.1、溢价模块 v3 §5 不变）。

**修法**：v5 的每一次运行（S0、P1、P2、稳健性、结构对照）都走与 v4 B0 相同的执行入口和参数（`src/v3/engine/arms.py` 调 `simulate_path` 的那一组，含 `src/v4/r5/design.py` 的 `_execute` 对延后 1 天的处理），只把目标权重换成 v5 的 `path_decisions`，路数从六路换成周、月两路。C2 关着时用同一个 `simulate_path`，只是不离场：给 `simulate_path` 加一个向后兼容的“不离场”取值（默认不变），不另走 `book.simulate`。

**验证**：① 回归测试：用改动后的代码重跑 v4 B0 两个池，日净收益与 v4 账本里已登记的序列逐日相同（或 SHA256 相同）；② 单元测试：同一组目标权重，S0 与 C2 在离场从不触发的样本上日收益、持仓、费用完全一致，且两者都应用了涨跌停顺延。

## 9 处歧义的裁定

| # | 歧义 | 裁定 |
| --- | --- | --- |
| 1 | 同分只看容器 id | 同意。跨类同分也按容器 id 升序 |
| 2 | 固定预算 m = 0 | 改为退回 S0 的 k = 0 防守位（开着的防守大类等分，都没开着才拿现金），与“没开着的那份走防守位”一致 |
| 3 | C1 标准差 ddof = 1；σ20 = 0 时 m = 1 | 同意 |
| 4 | 有效日收益沿用 v3（有限且 > −1），不足 250 个 m = 1 | 同意 |
| 5 | `pool` 列固定写 `index` | 同意 |
| 6 | `ann_excess_*` 用小数，`tradable_d_*` 用百分点 | 同意；报告里两者都换成百分点展示 |
| 7 | S0 行除 `arm`、各 `pp_*`、`ann_excess_*` 外留空 | 同意 |
| 8 | P2 的上一版由调用方传入 | 同意；运行脚本必须按 §6.1 自动取：C1 过关则 base = P1，否则 base = S0，并写进 ledger 的 `params` |
| 9 | S0 与 C2 用两条成交函数 | **不同意**，见上节，开跑前必须修 |
