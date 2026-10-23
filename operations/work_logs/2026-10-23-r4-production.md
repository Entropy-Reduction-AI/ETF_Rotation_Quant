# R4 收手版正式配置

## Metadata

- Project: ETF_Rotation_Quant
- Task: 落实 D5 执行规则
- Date: 2026-10-23
- Owner: project owner
- Route: direct-execute
- Source of truth: `operations/planning/2026-10-22-parallel-lanes.md` D2 / D5，`operations/reviews/2026-10-23-qdii-premium-and-weight.md`

## Goal / Summary

`config/r4_fallback.toml` 去掉待定字段，写成 D5 的 16 只 A 股执行基金、同指数备选、海外两池和带宽。执行仍走 `src/signals/fallback.py`。`replicate` 只算到 2015-12-31，不读净值、不套溢价。`target` 只写当日目标股数、候选溢价和触发的规则。

F（`fund_nav`）不在 main。`origin/main` 仍是 `1ad86ac`，`data/market.sqlite` 没有 `fund_nav` 表。2026-09-30 的目标用合成净值；F 合入 main 之后要用真实 `fund_nav` 重算这一天。

## 规则落在哪

| 规则 | 代码 |
| --- | --- |
| 配置：16 只主基金、备选上市日、两池、`band = 0.075`、`premium_cap = 0.10`、`nav_lag_trading_days = 2`、`lot_size = 100`；159509 在 `excluded` | `config/r4_fallback.toml`；`load_config` / `_validate` |
| 主基金清盘、停牌、暂停交易 → 同指数备选里上市最早且仍正常交易的一只 | `resolve_execution_fund`。月度再平衡日才换进目标股数 |
| 买入：同指数池内溢价最低 | `plan_targets`，规则 `buy_lowest_premium:<池>:<代码>` |
| 海外腿实际权重偏离 30% 超过 ±7.5 个百分点才再平衡；刚好等于带宽不交易。两指数一起看，再平衡时各回到 15% | `_outside_band`；`plan_targets` 的 `overseas_inside_band` / `overseas_rebalance` |
| A 股腿仍只在该月第一个或最后一个交易日对齐 | `a_share_session`；规则 `a_share_monthly` / `a_share_hold` |
| 池内最低溢价 > 10%：该指数不新买，已有股数不动，应买金额留 511880。等于 10% 仍可买 | `_over_cap`；规则 `premium_cap:<池>`、`park_511880` |
| 需要卖出时先卖溢价最高的持仓，下一手会卖穿目标就停 | `_sell_down`；规则 `sell_highest_premium:<池>` |
| 溢价 = 决策日收盘 / 已公布最新单位净值 − 1。净值日期必须 ≤ T−2 个交易日，T−1 和 T 的行就算在表里也不用 | `published_cutoff`、`select_nav`；读 `fund_nav` 的 `load_fund_nav` |
| 股数按 `lot_size` 向下取整。配置是 100，A 股、QDII、511880 都用这一手 | `_lot_floor` |
| 设计期复现不调用上面这套 | `replicate`。测试把 `plan_targets` 换成会抛错的函数，复现仍然得到同一组设计期数字 |

成交额改成 60 日均额最大，这次没有做。停牌状态要另给 `--status`；不给就按正常交易。2026-09-30 这 16 只主基金在 `bars` 里都有收盘。

## 2026-09-30 目标持仓

没有真实账户。按总权益 1,000,000、当前持仓为空生成同日目标。空仓的海外权重是 0，偏离 30% 超过带宽，所以触发买入。这一天是 9 月最后一个交易日，A 股腿做月度对齐。阀在场，应买的海外没有顶到 10% 溢价上限，目标里没有 511880。

净值来源：`synthetic_fixture`。收盘价是 `data/market.sqlite` 的 `bars.adj = raw`。合成净值在 `tests/signals/fixtures/fund_nav_2026-09-30.csv`：决策可用的是 2026-09-28；2026-09-29 和 2026-09-30 是故意相反的溢价，用来确认没有用到 T−1 / T。截止日写在结果里是 `2026-09-28`。

候选溢价（相对 2026-09-28 单位净值）：

| 池 | 代码 | 溢价 | 买入 |
| --- | --- | --- | --- |
| 纳指100 | 513100 | +7.0% | |
| 纳指100 | 159941 | +5.0% | 是 |
| 纳指100 | 513300 | +6.0% | |
| 标普500 | 513500 | +6.5% | |
| 标普500 | 159612 | +4.0% | 是 |
| 标普500 | 513650 | +8.0% | |

159509 在合成表里有一行更低的溢价，不在池内，也没有出现在溢价或目标里。

目标股数（价格是 2026-09-30 收盘；每只都是 100 的整数倍）：

| 代码 | 名称 | 腿 | 股数 |
| --- | --- | --- | --- |
| 510300 | 沪深300 | A 股 | 9800 |
| 510500 | 中证500 | A 股 | 5800 |
| 512100 | 中证1000 | A 股 | 14700 |
| 159915 | 创业板 | A 股 | 13800 |
| 159819 | AI/算力 | A 股 | 26300 |
| 512400 | 有色 | A 股 | 26900 |
| 515220 | 煤炭 | A 股 | 34800 |
| 512660 | 军工 | A 股 | 39700 |
| 512010 | 医药 | A 股 | 112700 |
| 159928 | 消费 | A 股 | 66400 |
| 512690 | 白酒 | A 股 | 104900 |
| 159825 | 农业 | A 股 | 60500 |
| 512800 | 银行 | A 股 | 51200 |
| 512880 | 券商 | A 股 | 42500 |
| 512200 | 地产 | A 股 | 33600 |
| 510880 | 红利 | A 股 | 12900 |
| 159941 | 纳指100 | 海外 | 86400 |
| 159612 | 标普500 | 海外 | 72200 |

剩余现金 2207.20，是取整留下的，不是一笔收益。规则：`overseas_rebalance`、`a_share_monthly`、`buy_lowest_premium:纳指100:159941`、`buy_lowest_premium:标普500:159612`。

文件：`results/r4/target-2026-09-30.json`。里面没有收益、回撤、排名。

## replicate

设计期 2005-02-28 → 2015-12-31。与 d2 的差都在 0.04 个百分点以内，切换次数相同。`matches_d2` 为真。溢价参数改掉以后，同一面板的月频和日频数字不变。

| 项 | d2 | 本次 | 差（百分点） |
| --- | --- | --- | --- |
| A股等权+阀25/10 年化 | +27.1% | 0.270661 | −0.0339 |
| A股等权+阀25/10 最大回撤 | −42.6% | −0.426280 | −0.0280 |
| 切换次数 | 6 | 6 | 0 |
| A股70%（阀25/10）+海外30% 年化 | +22.7% | 0.227206 | +0.0206 |
| A股70%（阀25/10）+海外30% 最大回撤 | −29.5% | −0.294741 | +0.0259 |

日频仍是 2005-02-01 → 2015-12-31，单边成本 0.0005，年化 0.216936，最大回撤 −0.371356，切换 6。文件：`results/r4/replicate.json`。

## 命令

工作目录 `/workspace`。解释器 `.venv/bin/python`。

| 命令 | 退出码 | 耗时 |
| --- | --- | --- |
| `.venv/bin/python -m src.data package --end 2026-09-30` | 0 | 面板构建的前置步骤，只读 `data/market.sqlite` |
| `.venv/bin/python -m src.indicators build --package outputs/research-package-2026-09-30.sqlite --out outputs/panel-2026-09-30.sqlite` | 0 | 阀的在场/出场用这块面板；产出在 `outputs/`，不入库 |
| `.venv/bin/python -m src.signals.fallback replicate --panel outputs/panel-2026-09-30.sqlite --end 2015-12-31 --out results/r4/replicate.json` | 0 | 设计期 |
| `.venv/bin/python -m src.signals.fallback target --panel outputs/panel-2026-09-30.sqlite --date 2026-09-30 --equity 1000000 --nav-db outputs/fund_nav_fixture.sqlite --price-db data/market.sqlite --nav-source synthetic_fixture --nav-note "…" --out results/r4/target-2026-09-30.json` | 0 | 合成净值 |
| `mkdir -p outputs && .venv/bin/python -m unittest discover -s tests -t .` | 0 | 85.961s |

全量测试 Ran 317 tests，OK。

## market.sqlite

SHA256 `9bc8e74935fe34f22c254568f4b6ef284df79a97496bcc8fcd704fe58ec5d49b`。本线只读，工作区相对 HEAD 没有改这个文件。
