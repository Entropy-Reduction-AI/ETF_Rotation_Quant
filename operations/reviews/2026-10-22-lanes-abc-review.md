# 评审：Lane A（R4 引擎）、Lane B（执行清点）、Lane C（Pi cron）

- Date: 2026-10-22
- Reviewer: orchestrator

## 结论

三条都**通过**。按 D6 合入 main；合入时如需先合入 origin/main，只要无冲突且全量测试 0 失败即可直接快进，不必再等评审。

## Lane A · `cursor/r4-fallback-engine` 134c9c3

- 本地全量测试 Ran 301，OK。
- `replicate --end 2015-12-31` 本地重跑，与 `results/r4/replicate.json` 逐项相同；与 d2 的差都在 ±0.04 个百分点内，切换 6 次相同。
- `replicate --end 2016-06-30` 退出码 2 并拒绝，样本外保护有效。
- target 只含当日权重、阀状态、距高点回撤，没有历史绩效。
- 写入路径只在 Lane A 范围内；`data/market.sqlite` 未改。
- 记下：贴近实盘的日频版（次日成交、扣成本）设计期最大回撤 −37.1%，比月频的 −29.5% 深。以后对外口径用日频版。

## Lane B · `cursor/execution-inventory` 3617003

- 本地全量测试 Ran 293，OK。`data/market.sqlite` 实测 `9bc8e749…d49b`，与日志一致；`PRAGMA integrity_check` 回报 ok；run_id 10。
- 88 只基金（主 38 + 备选 50）都有行情，均为腾讯不复权。
- 已知限制（不返工，进待办）：
  1. 成交额全部为空（腾讯不给成交额，东财 `RemoteDisconnected`），只有成交量（手）。
  2. `cash_dividends` 只有 11 只稀疏代码可当分红日历；其余 36 只是 qfq 噪声阶跃，**任何代码不得把这 36 只当真实分红使用**，待 Grok 一手公告核对后替换。
  3. QDII / LOF 的净值、IOPV、溢价全部缺口（15 只）。
  4. 39 处份额折算假跳空已列出。

## Lane C · Pi 7219d6e

- 旧台账两行原本就不在；未写 crontab，未重启服务。交接 §6 的 Pi 一条已核实关闭。
