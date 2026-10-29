# v4-R1e · 引擎（载体粘性 + 无指数拼接）· 签收 · 2026-10-29

## Decision：`approve`

在 Dev PR [#101](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/101) 尖端 `a9069e844442aa68b174efd874f494eb02b2143d`（base main `8fc7dacae389ec8a6e6890529562e44703c41a25`）上，Reviewer **独立走读** `src/v4/engine/carriers.py`、`src/v4/engine/apply.py` 与 `tests/v4/engine/test_r1e.py`，并复跑指定 unittest 套件。对照预注册 v4 第 2.2 版 §3.1 / §3.2（D19-2）与 `operations/planning/2026-10-29-v4-r1e-plan.md` §3：**未发现阻塞项**。**Manager 应先合入 #101，再合入本 Review PR。**

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R1e 引擎签收
- Date: 2026-10-29 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（Review PR 仅追加本文件）
- Dev: PR #101 · head `a9069e8…`
- Work log（Dev）: `operations/work_logs/2026-10-29-v4-r1e-engine.md`
- 预注册: `docs/prereg/etf-multiasset-rotation-prereg-v4.md`（第 2.2 版 §3.1、§3.2）
- 范围: `git diff 8fc7dac..a9069e8` — 4 文件（`carriers.py`、`apply.py`、`test_r1e.py`、Dev work log）；无 `data/`、无 LOCK、无 prereg 改动

## A. 复跑命令（Reviewer 独立）

环境：仓库根 `.venv`；`mkdir -p outputs`。

| 步骤 | 命令 | 结果 |
| --- | --- | --- |
| R1e 签收套件 | `.venv/bin/python -m unittest tests.v4.engine.test_r1e tests.v4.engine.test_r2c tests.v4.engine.test_r2b tests.v3.engine.test_v4_r2` | **44** 项：**42 pass**，**2 skip**，**0 fail** |
| FreezeP1（显式） | `PYTHONHASHSEED=0 .venv/bin/python -m unittest tests.v3.engine.test_v4_r2.FreezeP1.test_switches_off_match_freeze_p1_day_by_day` | **skip**（D17 输入漂移，见 §B6） |

Skip 明细（缺完整 `market.sqlite`）：

- `tests.v4.engine.test_r2b.CarrierTable.test_year_end_matches_the_vehicle_table`
- `tests.v4.engine.test_r2b.NewPoolRanks.test_month_end_top8_against_manager_r1`

## B. Checklist（对照 prereg 2.2 §3.1 / §3.2 与 R1e plan §3）

| # | 项 | 独立方法 | 结果 |
| --- | --- | --- | --- |
| 1 | **Sticky tier-1（D19-2）** | 读 `_kept_holding` / `choose_on` / `choose_path`；`test_r1e.HeldCarrier` | 仅 **tier=1** 且 `available[day]` 为真时留住昨日载体；**510300** 中位数 5000 万、**159919** 9000 万仍留 510300；510300 **1000 万**（&lt;3000 万）才换 159919；510300 回到 1 亿已持有 **159919** 仍留；中位数打平无持仓取代码小者、有持仓不换回 |
| 2 | **「已持有」语义** | 代码注释 + `choose_path` 递推 | 指容器 **上一交易日** 的 `CarrierChoice`，**非**组合权重 |
| 3 | **OTC 不粘、升档** | `test_otc_holding_steps_up_when_an_etf_qualifies` | 第 1 档 ETF 一旦合格即从 OTC 升上去 |
| 4 | **`choices_on` 不变** | `choices_on` → `choose_on(..., held=None)`；`test_r2b` 仍用 `choices_on` | 单日 / 年末载体表 **无** 路径依赖；粘性仅 `choose_path` → 研究序列、`stitch_fills`、U-可交易掩码 |
| 5 | **无指数拼接** | `has_investable_index`、`_splice_indexless`、`splice_returns`；`test_r1e.Spliced*` / `ApplySplice` | 研究码空 / `取不到` / `TBD` 或 status `取不到` 时 `carriers` 打开后接基金日收益；**partial / in_db 指数** 容器不动（如 csi300 恒 0.0123）；换日收益 **−20%** ≠ 80/11−1；复利 100×1.1×0.8=88 |
| 6 | **QDII T−2** | `lagged_nav_returns` / `research_return`；`test_qdii_*` | 选中基金的 **滞后单位净值** 涨跌，非跨基金价格比 |
| 7 | **关联基金来源** | `_add_indexless_etfs` + `build_candidates`；`IndexlessLinks` | 执行层场内关联；`maps_to` 非增强 OTC **tier-2**；`enhanced=1` / 名称含增强 **排除** |
| 8 | **开关全关 ≡ v3.1 路径** | `apply_market` 四开关全关 early return；`EngineSwitches.idle()`；`test_r1e.ApplySplice` + `test_v4_r2.SwitchDefaults` / `FillLimitPaths` | `EngineSwitches()` 下 `signal` **equals** 改前；`execute(..., switches=EngineSwitches())` 仍走 v3.1（`run` 不进入 v4 改写） |
| 9 | **Look-ahead** | `etf_available` / `_median_on` 均 `index <= day`；载体打印 `prints <= stamp` | 未发现决策日 D 读取 D 之后成交额或净值的新增路径 |
| 10 | **范围纪律** | diff + 未跑组合 PnL | 无 v4 候选组合收益、无 2016+ 汇总、无 tag / LOCK / prereg 编辑 |

### B1 · 手造路径（test_r1e 覆盖，Reviewer 核对断言）

| 场景 | 期望 | 测试 |
| --- | --- | --- |
| 粘性 + 更高成交额 | 159919 90M vs 510300 50M → 仍 510300 | `test_stays_while_qualified_and_leaves_when_the_median_breaks` |
| 失去 3000 万 | 510300 10M → 159919 | 同上 |
| 成交价跟持有载体 | day2 close/prev = 510300 的 11/10，非 159919 130 | `test_fill_uses_the_held_funds_own_close` |
| 80 日切换更热基金 | day60 起 +10% hfq，非 55/10−1 | `ApplySplice` |
| 路径拼接 | day3 −20% after sticky switch | `test_path_splice_matches_the_held_funds_hfq_return` |

### B2 · `MIN_AMOUNT`

`carriers.MIN_AMOUNT = 30_000_000.0`（人民币成交额中位数，与 prereg「3,000 万元」一致）。

## B6 · FREEZE_P1（九项常量）

| 检查 | 结果 |
| --- | --- |
| `git diff 8fc7dac..a9069e8 -- tests/v3/engine/test_v4_r2.py` | **无改动** |
| 九项 SHA 字面量 vs R2c 签收表 | **全部 unchanged**（net / held / cost / 3·5·8 × week·month） |
| 本机 `freeze_inputs_match()` | **false**（D17 后登记表 + 库 SHA ≠ `FREEZE_INPUT_*`） |
| `FreezeP1` 行为 | **skip**，不重算、**未写入**新 SHA（符合 D17 / work log） |
| 开关全关回归 | `test_r1e.ApplySplice` + 既有 `test_v4_r2` 开关关测试 **pass**（非完整库上的 P1 逐日复算 skip 为预期） |

九项常量（与 milestone / R2b 一致，PR #101 **未改**）：

| 序列 | SHA256 |
| --- | --- |
| net | `962178c503df7d1ee900971711271fc4fac4436522053dbc9c297b48c3b8fa57` |
| held | `bdd1521f7d9d66404184351dfe50e3e4681edfd91415e46572394c44d6eea32b` |
| cost | `62b76e5375f73360de7e4b03753808bd00058310c7dc35ce353ca091a4e44e0c` |
| 3-week | `75e3f744c2f347781965632729a184cd9c0244efc41a84963f5b3550f0e6e5a6` |
| 3-month | `6cbf6fd1e24696d6c855305a63447f0e761f7ca73c6c559a28dfea253243d42f` |
| 5-week | `d5bddc5cea82b4aa9bc3b32bda21c8c00e8af66e31f8aac7ed8afafdf10ce760` |
| 5-month | `f2470bf01046c3739b4fafd87dc356b80212a52ba2f20db37297c04320478fe3` |
| 8-week | `64ed67d0756a69cda899903ea8da7db100828b07f09cd6560a730e5c73d2aa7f` |
| 8-month | `83131d7b8d4f010fec33bf799669cfa88bae465d483be7bd03dcee4f3acf1f6e` |

## C. Must-fix / Should-fix / Follow-up

| 级别 | 项 | 说明 |
| --- | --- | --- |
| Must-fix | — | 无 |
| Should-fix | — | 无 |
| Follow-up | 完整库签收 | Manager 合入后在有 LFS `market.sqlite` 的环境复跑 `test_r2b` 两项 skip + `PYTHONHASHSEED=0 FreezeP1`（预期仍 D17 skip，除非回到冻结输入） |
| Follow-up | prereg 2.2 三处 | 本签收仅 **引擎** §3；§3.1 纳入分组 / §6.1 B0 文字复核仍属 plan §2 另一条线 |

## D. Reviewer 纪律

未 merge #101、未移动 tag、未改 prereg、未写 LOCK、未算 v4 候选 PnL、未汇总 2016-01-01+ 组合收益、未 push main。

---

本人，ETF Rotation Reviewer，于 2026-10-29 对 Dev PR #101 @ `a9069e844442aa68b174efd874f494eb02b2143d` 签收：**`approve`**。
