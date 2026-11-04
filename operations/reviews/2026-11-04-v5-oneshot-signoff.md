# D34-4/5 · v5 一次性检验 · Dev #255 签收 · 2026-11-04

## Metadata

- Project: ETF_Rotation_Quant
- Document type: review（oneshot 产物独立复算；**未**重跑 2016+ 组合引擎；**未**合入 #255）
- Date: 2026-11-04（Asia/Taipei）
- Author: ETF Rotation Reviewer（lwx0218）
- Route: review-only（`operations/reviews/**` + diag 脚本/JSON）
- Dev PR: [#255](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/255)
- 一次性产物 tip: **`6c94f5ed6d6e88e7d992d7b51787b8bf3fcba3c5`**（Dev #255 附录 tip: **`6615b81cc99aca74a8e87ade375318d917360511`**）
- 运行代码（`ran.json` / oneshot 入口）: **`e4ccbc3c41e1769e6404c9cf2b01af0b9906e3e8`**
- 代码冻结 tag: `milestone/v5-code-freeze` → **`8970bcbc7986c9a67d9ca535ca58a8855c910495`**
- LOCK: `results/v5/LOCK`（D34-3 已签收）
- 依据: `operations/planning/2026-11-04-d34-v5-seal-oneshot.md`；`docs/prereg/etf-multiasset-rotation-prereg-v5.md` §6.4

## Decision

**approve**

Reviewer 独立核对：① 在运行代码 `e4ccbc3` 上设计期（end ≤ 2015-12-31）E2/B0、A1、A2、v5.1 两池日净序列与已签收冻结产物 **逐位一致**；② 只读 `results/v5/oneshot/**` 的 `net.csv` + `month-states.csv` 重算 `criteria.csv` **12 行全列一致**；③ 判据⑤ 尝试次数 **115** 与 Dev `attempts.json` 一致（L3=10，L4=41，L5=0，C=0）；④ Dev 附录 `operations/reviews/2026-11-04-v5-oneshot-signoff-appendix-a1-cash.md`（#255 @ `6615b81`）与 oneshot `held.csv` / 冻结规则 **一致**，现金月成因已闭合。**未**合并 #255；**未**移动 tag；**未**重跑 2016+ 中国组合 NAV。

正式判据①⑥对 U-指数 E2/B0 的结论为 **不通过**（`criteria.csv` `pass=False`），属预注册检验结果，非落盘/复算差错。

| 级别 | 数量 |
| --- | --- |
| Must-fix | **0** |
| Should-fix | **0** |
| Note | **0** |

---

## 1 · 设计期逐位复现（运行代码 `e4ccbc3`）

**登记语句（signoff）**：运行代码 `e4ccbc3` ≠ 冻结 `8970bcb`，差异只是窗口开关，已用设计期逐位复现证明。

| 臂 | 池 | 冻结路径 | n | 逐位相等 |
| --- | --- | --- | ---: | --- |
| E2/B0 | U-指数 | `results/v4/r5/design/B0/index/net.csv` | 2671 | ✅ |
| E2/B0 | U-可交易 | `results/v4/r5/design/B0/tradable/net.csv` | 2671 | ✅ |
| A1 | U-指数 | `results/v4/r5/design/A1/index/net.csv` | 2671 | ✅ |
| A1 | U-可交易 | `results/v4/r5/design/A1/tradable/net.csv` | 2671 | ✅ |
| A2 | U-指数 | `results/v4/r5/design/A2/index/net.csv` | 2671 | ✅ |
| A2 | U-可交易 | `results/v4/r5/design/A2/tradable/net.csv` | 2671 | ✅ |
| v5.1 | U-指数 | `results/v5.1/design/index/daily.csv`（`net` 列） | 2671 | ✅ |
| v5.1 | U-可交易 | `results/v5.1/design/tradable/daily.csv` | 2671 | ✅ |

- DB: `data/market.sqlite` SHA256 **`167d4e39ffab4302e6f55d2b3436b3400ea28b2282cd7f9b9bda644d87c1acf3`**（LFS 实文件）
- 方法: `git worktree` @ `e4ccbc3` → `run_job(B0)` + `run_peers(A1,A2)` + `python -m src.v51 design`；与 main 树冻结 CSV 逐日 `==`
- 证据: `operations/reviews/diag/v51/v5-oneshot-design-bitmatch-e4ccbc3.json`

---

## 2 · 一次性窗口 `criteria.csv` 独立复算

- 窗口: **2016-01-01 → 2026-09-30**（只读 Dev 已落盘 `net.csv`；**未**调用 `src.v51.oneshot` 的 `_criteria_row` / `run_oneshot`）
- 输入: `results/v5/oneshot/**/net.csv`、`month-states.csv`、基准 `benchmarks/*/net.csv`
- 输出比对: Dev `results/v5/oneshot/criteria.csv`，按 `(pool, arm)` 合并，数值列 `atol=5e-7`（与 CSV `%.12g` 一致）

| 检查 | 结果 |
| --- | --- |
| 12 行 × 全列 | ✅ **0** 不一致 |
| U-指数 E2/B0 正式 `pass` | **False**（① median 36/60 与 60m 正超额占比；⑥ P(牛市)&lt;0、rebound t≈−3.25） |
| 脚本 | `operations/reviews/diag/v51/v5-oneshot-criteria-recalc.py` → `.json` |

---

## 3 · 判据⑤ 尝试次数（v5 §6.4）

公式: **L3 + L4 + L5 − C + 28 + 35 + 1**

| 符号 | 来源 | Reviewer 计数 |
| --- | --- | ---: |
| L3 | `results/v3/trial-ledger.csv`（`_deduped`） | **10** |
| L4 | `results/v4/trial-ledger.csv` | **41** |
| L5 | `results/v5/trial-ledger.csv` | **0**（本树**不存在**该文件） |
| C | 两账本 `arm=C1-shadow` | **0** |
| +28 / +35 / +1 | `src/v3/eval/common.py` | 28 / 35 / 1 |
| **合计** | | **115** |

与 Dev `results/v5/oneshot/attempts.json` **一致**。D34-3 / oneshot 实现说明: 一次性判据⑤ **只**读当前树上的 `results/v5/trial-ledger.csv`，**不**把未并入的 v5.1 账本行补进 L5（`excluded_from_L5`: v5.1、A1）。

**交叉清单（不计入本次 L5，仅供 Orchestrator 台账）**: `results/v5.1/trial-ledger.csv` 去重 **30** 行；其中 `kind∈{design,other-market}` **6** 行（臂: v5.1、E2式、A1、R0 等），**不**改变 oneshot 已公布的 L5=0。

---

## 4 · 附录 · A1 可交易现金月（Dev 只读诊断）

**来源（Dev #255 head `6615b81`）**: [`operations/reviews/2026-11-04-v5-oneshot-signoff-appendix-a1-cash.md`](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/blob/6615b81cc99aca74a8e87ade375318d917360511/operations/reviews/2026-11-04-v5-oneshot-signoff-appendix-a1-cash.md)

Reviewer 对附录结论的 spot（只读 `results/v5/oneshot/tradable/A1/held.csv`、`net.csv` 与 `config/v4/peers.toml`，**未**重跑组合）:

| 核对点 | 结论 |
| --- | --- |
| 现金是否溢价控制 | **否** — A1 `premium_module = false`，对照不读 θ |
| 主因 1 | 规则要 10 年国债时 **`511260` 不可用** → 整仓现金 |
| 主因 2 | 规则要标普时 **`513500` 流动性未过 3000 万** → 选中 **`050025`**，复权净值止于 2015-12-31，2016+ 无成交打印 |
| 2017-08 | **不是现金月**（2017-08-31 开盘持仓为沪深300，见附录表） |
| 2017-12 / 2018-04 | 月末决策买沪深300；当月开盘现金来自**上一笔**标普/国债买不进 |

Follow-up **已关闭**（原 Note：附录待 Dev 补）。

---

## 5 · 边界

| 项 | 状态 |
| --- | --- |
| 中国设计期复跑 end ≤ 2015-12-31 | ✅ |
| 未重跑 2016+ 中国组合 NAV / 未再跑 oneshot | ✅ |
| 未写 LOCK / 未动 tag / 未 merge #255 | ✅ |
| 增量仅 review 文档与 diag | ✅ |

---

## 6 · Reviewer 测试

```bash
mkdir -p outputs
.venv/bin/python operations/reviews/diag/v51/v5-oneshot-criteria-recalc.py
.venv/bin/python -m unittest discover -s tests -t . -q
```

| 项 | 结果 |
| --- | --- |
| criteria 独立复算 | exit **0**；`all_match: true` |
| 全库 unittest | **OK**（discover） |

---

## Follow-ups

| 角色 | 行动 |
| --- | --- |
| **Owner / Orchestrator** | 知悉一次性检验 **不通过**（`pass=False`）为策略结论；是否关闭 v5 入围线由看板/预注册流程决定，非本签收 MF |
| **Cloud / Owner** | 若合入 Dev #255，仍按 LOCK 纪律：**禁止**再跑 2016+ 中国 PnL |
