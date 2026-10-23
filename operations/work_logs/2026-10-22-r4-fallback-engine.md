# R4 收手版信号引擎

## Metadata

- Project: ETF_Rotation_Quant
- Task: R4 收手版信号引擎（标的走配置，待 D5）
- Date: 2026-10-22
- Owner: project owner
- Route: direct-execute
- Source of truth: `operations/planning/2026-10-22-parallel-lanes.md` D2 / D4，`operations/reviews/2026-10-22-r2-diagnostics.md` 第 3 节，`operations/reviews/diag/d2.py`

## Goal / Summary

慢阀与 d2.py 同一套月末规则。标的在 `config/r4_fallback.toml`，名单是 d2 的 16 个 A 股容器，注明待 D5。replicate 只算到 2015-12-31。target 只给当日权重、阀状态和距高点回撤。

## 命令

工作目录 `/workspace`。解释器是系统 `python3`（已装 pandas 3.0.6、numpy 2.5.4）。时刻按 Asia/Taipei。

| 命令 | 退出码 | 耗时 |
| --- | --- | --- |
| `python3 -m pip install --break-system-packages 'pandas>=3.0,<4' 'numpy>=2.0,<3'` | 0 | 6.145s |
| `python3 -m src.signals.fallback replicate --panel outputs/panel-2026-09-30.sqlite --end 2015-12-31 --out results/r4/replicate.json` | 0 | 0.591s |
| `python3 -m src.signals.fallback target --panel outputs/panel-2026-09-30.sqlite --date 2026-09-30 --out results/r4/target-2026-09-30.json` | 0 | 0.713s |
| `mkdir -p outputs && python3 -m unittest discover -s tests -t .` | 0 | 89.014s |

全量测试 Ran 301 tests in 88.715s，OK。

## replicate (a) 与 d2

设计期 2005-02-28 → 2015-12-31。印刷到 1 位百分数后与 d2 第 3 节两行相同。原始差都在 ±0.1 个百分点以内。切换次数相同。

| 项 | d2 | 本次 | 差（百分点） |
| --- | --- | --- | --- |
| A股等权+阀25/10 年化 | +27.1% | +27.1%（0.270661） | −0.034 |
| A股等权+阀25/10 最大回撤 | −42.6% | −42.6%（−0.426280） | −0.028 |
| 切换次数 | 6 | 6 | 0 |
| A股70%（阀25/10）+海外30% 年化 | +22.7% | +22.7%（0.227206） | +0.021 |
| A股70%（阀25/10）+海外30% 最大回撤 | −29.5% | −29.5%（−0.294741） | +0.026 |

## replicate (b)

月末收盘出信号，下一交易日收盘成交，成交金额乘单边成本 0.0005。年化按 252 个交易日。区间 2005-02-01 → 2015-12-31，2651 个交易日。511880 在 2015-12-31 之前有收盘的日子用它的收益，更早用现金年化 2% / 252。

- 年化 +21.7%（0.216936）
- 最大回撤 −37.1%（−0.371356）
- 阀切换 6 次（与月频是同一套月末判定）

## 2026-09-30 的 target

只含当日目标，没有区间收益。阀在场。A 股腿影子净值距高点 −8.8%（−0.088005）。QDII 溢价一列是「未接入」。A 股 16 只各 0.043750，纳指100 / 标普500 各 0.150000。

```
2026-09-30  信号日 2026-09-30  阀 在场  A股距高点 -8.8%  QDII 未接入
沪深300      510300  0.043750
中证500      510500  0.043750
中证1000     512100  0.043750
创业板       159915  0.043750
AI/算力      159819  0.043750
有色         512400  0.043750
煤炭         515220  0.043750
军工         512660  0.043750
医药         512010  0.043750
消费         159928  0.043750
白酒         512690  0.043750
农业         159825  0.043750
银行         512800  0.043750
券商         512880  0.043750
地产         512200  0.043750
红利         510880  0.043750
纳指100      513100  0.150000
标普500      513500  0.150000
```

## market.sqlite

SHA256 `e013b960b9d77cbb78a10116e3c50b61bf0b81ad63247afeb67316fa54cee961`。replicate 与 target 前后一致，本线没有写这个库。
