# v4-R1f · 引擎（MF-6 研究序列 timing）· 签收 · 2026-10-29

## Decision：`approve`

在 Dev PR [#111](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/111) 尖端 `ef4d467359b64270b5370a3fdb0fb6542182ca63`（base main `4f1b1d6068da41fd1a9371c20455c97a200bbfc8`）上，Reviewer **独立走读** `src/v4/engine/carriers.py`、`src/v4/engine/apply.py` 与 `tests/v4/engine/test_r1e.py`，并复跑 Dev work log 指定 unittest 套件。对照预注册 v4 第 **2.3** 版 §3.1 / §3.2（D21-5 MF-6）、`operations/planning/2026-10-29-d21-hfq-rebuild-and-mf6.md` 与 R1e 引擎基线：**未发现阻塞项**。**Manager 应先合入 #111，再合入本 Review PR。**

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R1f MF-6 引擎签收
- Date: 2026-10-29 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（Review PR 仅追加本文件）
- Dev: PR #111 · head `ef4d467…`
- Work log（Dev）: `operations/work_logs/2026-10-29-v4-r1f-mf6.md`
- 预注册: `docs/prereg/etf-multiasset-rotation-prereg-v4.md`（第 2.3 版 §3.1 研究序列、§3.2「已选定」）
- 范围: `git diff 4f1b1d6..ef4d467` — 引擎 2 文件 + `test_r1e.py` + Dev work log；另从 `operations/reviews/2026-10-29-v4-prereg-r1e.md` **删去** R1f 预注册复审附录（非 `docs/prereg/*` 改动）；无 `data/`、无 LOCK、无 prereg 正文编辑

## A. 复跑命令（Reviewer 独立）

环境：仓库根 `.venv`；`mkdir -p outputs`。

| 步骤 | 命令 | 结果 |
| --- | --- | --- |
| R1f 签收套件 | `.venv/bin/python -m unittest tests.v4.engine.test_r1e tests.v4.engine.test_r2c tests.v4.engine.test_r2b tests.v3.engine.test_v4_r2` | **45** 项：**43 pass**，**2 skip**，**0 fail** |
| FreezeP1（显式） | `PYTHONHASHSEED=0 .venv/bin/python -m unittest tests.v3.engine.test_v4_r2.FreezeP1.test_switches_off_match_freeze_p1_day_by_day` | **skip**（D17 输入漂移，见 §B6） |

Skip 明细（缺完整 `market.sqlite`）：

- `tests.v4.engine.test_r2b.CarrierTable.test_year_end_matches_the_vehicle_table`
- `tests.v4.engine.test_r2b.NewPoolRanks.test_month_end_top8_against_manager_r1`

## B. Checklist（对照 prereg 2.3 §3.1 / §3.2 与 D21-5）

| # | 项 | 独立方法 | 结果 |
| --- | --- | --- | --- |
| 1 | **同一条 §3.2 粘性路径** | `spliced_research` → `choose_path` + `earning_path`；与 `_gate` / `stitch_fills` 共用 `choose_path` | 无指数容器研究序列与 U-可交易 **同一** `choose_path` 递推；tier-1 **≥3000 万** 粘性规则未改（`_kept_prior`，原 `_kept_holding` 更名） |
| 2 | **「已选定」= 前一日载体** | `choose_on(..., prior=)`；`inspect.signature`；`choices_on` 仍无 prior | **无** `weight` 参数；传入 `prior=CarrierChoice` 时 510300 留仓、不传则按成交额重选 159919；`choices_on` 单日、年末表 **无** 路径依赖 |
| 3 | **Timing / earning_path** | 读 `earning_path`、`spliced_research`；`SplicedFromCandidates` / `ApplySplice` | D 日 **选定** 用 D 及以前信息；D 日 **研究收益** 用 D−1 载体（`[None, *selected[:-1]]`）；换日 01-06 收益 = 510300 的 12/11−1 ≠ 159919 −20%；新基金 01-09 起 88/80−1 ≠ 88/12−1；`stitch_fills` 用 **当日** 载体收盘（执行价），注释与 `test_fill_*` / `ApplySplice` 区分研究滞后 |
| 4 | **有指数容器不动** | `_splice_indexless` + `has_investable_index`（含 `partial`） | `ApplySplice` 中 csi300 全程 **0.0123**；仅 `oil` 无指数列被拼接 |
| 5 | **排名读滞后 signal** | `_splice_indexless` 写 `market.signal`；v3 `lookback_panel(market.signal, …)` | 拼接后 **signal / pnl / levels** 均为滞后研究序列；排名链路读 `market.signal`，与 prereg「然后再算 D 日排名」一致（本 PR 未改 regime 代码，仅确认写入点） |
| 6 | **开关全关 ≡ v3.1** | `apply_market` 四开关全关 early return；`ApplySplice` + `test_v4_r2` | `EngineSwitches()` 下 `signal` / `pnl` / `levels` **equals** 改前；`SwitchDefaults` / idle execute 仍 pass |
| 7 | **Look-ahead** | `choose_on` / `_median_on` / `earning_path` 时序 | D 日收益不读 D 日选定载体；选定仍只用 `index <= day` 成交额与打印；未发现 D 后信息进入研究收益的新路径 |
| 8 | **范围纪律** | diff + 未跑组合 | 无 v4 候选 PnL、无 2016+ 汇总、无 tag / LOCK / prereg 正文编辑 |

### B1 · MF-6 手造路径（Reviewer 核对断言）

| 场景 | 期望 | 测试 |
| --- | --- | --- |
| 粘性 + 更高成交额 | 159919 90M vs 510300 50M → 仍 510300 | `HeldCarrier.test_stays_while_qualified_*` |
| 掉出 3000 万才换 | 510300 10M → 159919；510300 回到 1 亿仍留 159919 | 同上 |
| 换日收益跟旧载体 | path[2]=159919 但 series[2]=510300 日收益 | `SplicedFromCandidates.test_path_splice_*` |
| 80 日更热基金 | 选定日收益空，次日 +10% hfq，非 55/10−1 | `ApplySplice` |
| 执行价 vs 研究 | day61 fill_close=55（当日选定），signal 滞后 +10% | `ApplySplice` tradable 分支 |

## B6 · FREEZE_P1（九项常量）

| 检查 | 结果 |
| --- | --- |
| `git diff 4f1b1d6..ef4d467 -- tests/v3/engine/test_v4_r2.py` | **无改动** |
| 九项 SHA 字面量 | **全部 unchanged**（与 R1e / milestone 一致） |
| 本机 `FreezeP1.test_switches_off_match_freeze_p1_day_by_day` | **skip**，消息含 D17；**未写入**新 SHA |
| 开关全关 | `ApplySplice` + 既有 `test_v4_r2` **pass** |

九项常量（PR #111 **未改**）：

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
| Follow-up | 完整库 | 有 LFS `market.sqlite` 时复跑 `test_r2b` 两项 skip |
| Follow-up | Dev diff 文档 | #111 从 `operations/reviews/2026-10-29-v4-prereg-r1e.md` 移除 R1f 附录；若需永久保留 R1f 预注册签收正文，确认是否已迁至独立 review 分支/文件（非引擎阻塞） |

## D. Reviewer 纪律

未 merge #111、未移动 tag、未改 prereg 正文、未写 LOCK、未算 v4 候选 PnL、未汇总 2016-01-01+ 组合收益、未 push main。

---

本人，ETF Rotation Reviewer，于 2026-10-29 对 Dev PR #111 @ `ef4d467359b64270b5370a3fdb0fb6542182ca63` 签收：**`approve`**。
