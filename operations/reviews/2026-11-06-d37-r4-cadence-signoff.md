# D37 round 4 · v5.1 cadence 诊断 · Reviewer 签收 · 2026-11-06

## Metadata

- Project: ETF_Rotation_Quant
- Document type: review（诊断独立复算；**不计入**任何过关判据）
- Date: 2026-11-06（Asia/Taipei）
- Author: ETF Rotation Reviewer（Cloud Agent）
- Dev PR: [#280](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/280)（**OPEN**，base `main` @ `d1f44fc85282d91e74e46d84d5558ab03dd18f00`，head **`8cca838c887eb1dc0f35da4102396d6bd6d2a7b9`**）
- 拼接 / S1 复算：`665f41a…` 库与格子（未因 `8cca838` 改变）；`8cca838` **仅** 增补 `results/v51-diag/d37/plan-b-s12.txt`（方案 B 根因说明）
- Companion PR: 本分支 `cursor/d37-r4-cadence-signoff-a91d` → `main`（**未**合并 #280）
- 依据: `operations/planning/2026-11-05-d37-v51-cadence-diagnostic.md` 第 4/5 版补充；Dev 产物 `results/v51-diag/d37/`
- 机器可读: `operations/reviews/diag/v51/d37-r4-recalc.json`；复跑脚本 `operations/reviews/diag/v51/d37-r4-verify.py`

## Decision

**approve**

本诊断 **不** 重判策略优劣，**不** 计入 v5 预注册或任何过关判据。Must-fix（SHA、泄漏、点位/FX、S1 复算、目标权重）均为 **0**。方案 B 在 S0 设计期与 S12 **目标权重一致**、成交差异来自 `run_book` 涨跌停 vs S12 `simulate`（§7.2），且 Dev 按 Owner/Manager 指示 **未跑** 其余 B 格子 — **不是** missing-output Must-fix。

| 级别 | 数量 |
| --- | --- |
| Must-fix | **0** |
| Should-fix | **0** |
| Note | **2**（§8） |

---

## 1 · 身份（#280）

| 项 | Reviewer 结果 |
| --- | --- |
| 状态 | **OPEN**，未合并 |
| base | `main`（`d1f44fc85282d91e74e46d84d5558ab03dd18f00`，含 #271/#274 签收与 D37 第 5 版规划增补） |
| head | `8cca838c887eb1dc0f35da4102396d6bd6d2a7b9`（`665f41a..8cca838` 仅 `plan-b-s12.txt`） |
| 拼接 / 库 / 诊断格子 | 仍对应 `665f41a` 数据面（Reviewer 未重跑 splice/S1） |

---

## 2 · 行情库 SHA256

| 对象 | SHA256 |
| --- | --- |
| #280 worktree `data/market.sqlite`（LFS 实文件，`sha256sum`） | `d0b947d90b444eb1d874a04df6bcb1974cbea4422b489f214a56c0a658abf0d9` |
| Dev `results/v51-diag/d37/db-sha256.txt` AFTER d37-round4 | 同上 ✅ |
| `main` LFS 库（r3 后，BEFORE round4） | `e3af3b5e3cb098ee516cf75bc6e87f9e470dace4df2708489f6cc526fae65eda` ✅ |

---

## 3 · S0 V0 检验段 vs 第三轮（r3）

| 方法 | 天数 | net 最大绝对差 | picks 不同 | market 不同 |
| --- | ---: | ---: | ---: | ---: |
| `fac651f` 第三轮 `S0/检验段/V0/daily.csv` vs #280 同路径产物 | 2611 | **0.0** | 0 | 0 |
| Reviewer 在 #280 库上 `run_cn(检验段,V0,S0)` 重跑 vs 第三轮 daily | 2611 | **0.0** | — | — |

`diag_d37` 对 **签收 oneshot** 的 bitmatch 仍报已知 OTC 差异（与 r2 相同，非本轮 round4 回归）。

---

## 4 · 本轮新拼接（8 条 + 日经 FX）

Owner 要求 ≥10 条时全查；本轮 **仅 8 条新指数拼接 + 日经 225 补 `100JPY/CNY` 中间价**（r3 已接 NK225 点位），故 **9 项全部抽查**。

### 4.1 发布日 vs 恒生目录 / 事实来源

| 代码 | Dev 发布日 | Reviewer 核对（`round4/index-catalogue.txt`，来自恒生指数目录 PDF） | 一致 |
| --- | --- | --- | --- |
| HSSCNE | 2018-01-08 | Launch **08-01-2018** | ✅ |
| HSIII | 2015-08-17 | Launch **17-08-2015** | ✅ |
| HSHCI | 2015-08-17 | Launch **17-08-2015** | ✅ |
| HSCGSI | 2015-08-17 | Launch **17-08-2015** | ✅ |
| HSHYLV | 2017-05-08 | Launch **08-05-2017** | ✅ |
| HSSI | 2001-10-03 | Launch **03-10-2001** | ✅ |
| DJIA | 1896-05-26（行情自 1990-04-25） | 东财/Yahoo 长历史，发布日按 Dev 登记 | ✅（未另改发布日） |
| FCHI | 1990-09-11 | 东财/Yahoo 长历史 | ✅ |
| NK225 | 1950-09-07 | 日经概况 Commencement（r3 已登记） | ✅（本轮只补 FX） |

### 4.2 点位抽查（独立拉源；重叠段中位数相对差）

Reviewer **独立**请求东财 `push2his`（Cursor WebFetch）与 Yahoo `^DJI`/`^FCHI`；港股系列 Dev 主存同花顺更长段，与东财重叠段核对。

| 代码 | 重叠交易日 | 收盘相对差中位数 | 备注 |
| --- | ---: | ---: | --- |
| HSSCNE | 645 | **0** | DB 1025 行，均 ≥ 发布日 |
| HSIII | 371 | **0** | |
| HSHCI | 404 | **0** | |
| HSCGSI | 911 | **0** | |
| HSHYLV | 916 | **0** | |
| HSSI | 3718 | **0** | |
| DJIA | 8515（东财）；另 3 日 vs Yahoo | **0** | |
| FCHI | 7555 | **0** | |

### 4.3 泄漏与 ingest 窗口（库内）

8 码均为：`bars_before_publish = 0`，`bars_on_or_after_first_list = 0`；`first_scoreable_post` ≥ `publish_date`（见 JSON `round4_splice_db_checks`）。

### 4.4 FX → CNY

| 对 | 核对日 | Reviewer（中国货币网 `CcprHisNew`，`currency=100JPY/CNY`） | 库 `JPYCNY` | 一致 |
| --- | --- | ---: | ---: | --- |
| 100JPY/CNY | 2024-01-04 | **4.9788** | **4.9788** | ✅ |

港币/美元/欧元：本轮拼接使用既有 `HKDCNY`/`USDCNY` 与新写入 `EURCNY`（Dev 登记）；Reviewer 未改库。

---

## 5 · 范围 completeness（冻结容器，`first_list` ≥ 2016-01-01）

`s1-splice-roster.csv` 中仍 **frozen** 且 `first_list` ≥ 2016-01-01 的容器 **32** 个（与 effect 表同数；另 `hstech` 等为 `already` 不在此列）。恒生仅单源/双源不一致、标普行业 Yahoo 无长历史、IBOVESPA 缺 BRL 中间价、东证/豆粕/MSCI/富时/新交所等无可用日线、原油与印度 ETP 非同一指数等 blocker 均写在名册 **reason** / **tried_urls** 中；Reviewer 抽查 **0** 例 silent skip。

均未新拼接；原因写在 `s1-splice-roster.csv` / effect 表 **reason** 列：恒生主题仅单源日线、标普/道琼斯 403、巴西缺 BRL 中间价、东证无日线、MSCI/富时/新交所仅事实表等。Reviewer 认为文档 **足够** 说明「≥2 源尝试或结构性不拼」，**无** silent skip。

---

## 6 · S1 检验段 V0–V4（独立复算）

口径：`daily.csv` 的 `net` + `diag_stats.performance` / `trade_cost`（与 Dev `stats.json` 同口径）。**5/5 格与 Dev 一致**（浮点容差见 JSON）。

| 版本 | Reviewer 年化 | Dev 年化 | Reviewer 回撤 | Dev 回撤 | 匹配 |
| --- | ---: | ---: | ---: | ---: | --- |
| V0 | 1.66% | 1.66% | −41.82% | −41.82% | ✅ |
| V1 | 2.63% | 2.63% | −33.68% | −33.68% | ✅ |
| V2 | 2.46% | 2.46% | −36.94% | −36.94% | ✅ |
| V3 | 1.75% | 1.75% | −45.55% | −45.55% | ✅ |
| V4 | 2.98% | 2.98% | −39.81% | −39.81% | ✅ |

**检验段持有（V0，effect 表）**：HSSCNE 15 日、贡献 −0.00457；道琼斯工业平均 28 日、−0.00274；法国 CAC40 49 日、+0.02430；其余新接码 0 日 — 与 Dev `report.md` 一致（四舍五入层面 Dev 写 −0.005 / −0.003 / 0.024）。

S1 **设计期** 五版本与 r3（`fac651f`）stats **逐字段相同**（抽查 V0）。

---

## 7 · 方案 B（`selection="all"`，V0 节奏）

### 7.1 产物范围（独立确认）

全库检索 `results/v51-diag/d37/**/B/`：**仅有** `S0/设计期/B/`（11 个文件，含 `daily.csv`、`decisions.csv`、`stats.json` 等）。**未** 生成 `S0/别的市场/B/`、`S0/检验段/B/`、`S1/检验段/B/` — 与 Dev 停跑说明一致，**不是** Must-fix。

### 7.2 目标权重 vs S12

| 检查 | Reviewer |
| --- | --- |
| `S0/设计期/B/decisions.csv` vs `results/v5.1/robustness/S12/decisions.csv` | 748 行 × **24** 列（含 `date`；Dev 写 23 列为目标列），**max abs cell diff = 0** ✅ |

### 7.3 成交差异（独立复算，非引用 txt）

| 列 | 2015-07-27 | 2015-07-28 | 2015-07-29 起 |
| --- | --- | --- | --- |
| `buy`/`sell` 与 S12 差 | 0.737005 vs 1.0（**1** 天） | 均为 1.0 | 均为 0 |
| `gross` 与 S12 差 | **0**（−0.033627） | +0.000447 | 相同 |
| `net` 与 S12 差 | +0.000351 | **累计 +0.000535** | **0**（日 `net` 逐日相同） |
| `cost` 与 S12 差 | −0.000351 | −0.000088 | 0 |

**S0 设计期**统计（2006-01-04 → 2015-12-31，与 S12 对齐）：年化 26.86% / 26.85%，最大回撤 −31.99% / −32.06%，每年笔数 61.2，每年成本 4.31% — Reviewer 与 Dev `stats.json` 一致。

### 7.4 根因：2015-07-27 创业板跌停卖不出（独立核验）

Dev 在 `8cca838` 的 `plan-b-s12.txt` 叙述与 **Reviewer 从数据 + 代码复现的结论一致**：

| 声称 | Reviewer 独立结果 |
| --- | --- |
| 决定日 **2015-07-24**，执行 **2015-07-27** 收盘 | `decisions.csv` 2015-07-24 目标：通信 / 医药 / 中证1000 各 **1/3** ✅ |
| 159915 原始收盘 2.740 → 2.466（−10%） | `data/market.sqlite` `bars` code=`159915` adj=`raw`：2015-07-24 **2.740**，2015-07-27 **2.466**；2.740×0.9=2.466 ✅ |
| 2015 创业板卖触发线 **−9.5%** | `src/v3/engine/limits.py`：`LIMIT_BUFFER=0.005`，`limit_ratio('chinext',2015-07-27)=10%`，`blocked(..., sell)` 当跌幅 ≤ −9.5%；对 2.74→2.466 返回 **True** ✅ |
| 创业板未卖出，残留权重 **0.263**；买卖额 **0.737** | `held.csv` 2015-07-28 开盘前 `chinext=0.262995`；三只买入各 **0.245668**（=0.333333×0.737005）✅ |
| 同日毛收益相同，净收益差 = 少付费用 | `gross` 相同；`cost` 0.000983 vs 0.001333，差 **0.000351** = `net` 差 ✅ |
| 2015-07-28 159915 −2.88%，可卖；毛收益差 +0.000447；收盘后均国债 | 2.466→2.395 为 **−2.88%**；`held.csv` 2015-07-29 `cgb-10y=1`（B 侧）✅ |
| 2015-07-29 起日收益相同；净值差仅为两日复利残差 | 2015-07-29 起 `net` 列与 S12 **逐日相同**（max diff 0）；`net` 累计差自 2015-07-28 起保持 **+0.000535** 水平 ✅ |

**结论**：差异 **可** 由「S12 忽略涨跌停整笔换仓 vs D37 `run_book` 在创业板跌停日卖单不成交、买单按剩余预算缩小」解释；Reviewer **未发现** 与 Dev 机制说明相矛盾的数字。Dev 说明文件仅作对照，上表证据来自库内价格、`held.csv`/`daily.csv` 与 `limits.py`。

---

## 8 · Note

- 本轮新拼接仅 **8** 条；Owner「≥10 条全查」在本轮落实为 **8+FX 共 9 项全查**（见 §4）。
- Reviewer **未** 合并 #280；**未** 改 LOCK / LOCK-addendum 正文；**未** 移动 tag。

---

## 9 · 复现

```bash
git fetch origin cursor/d37-r4 main
git worktree add /tmp/d37-r4-dev-review origin/cursor/d37-r4
cd /tmp/d37-r4-dev-review && git lfs pull -I data/market.sqlite
cd /agent/repos/ETF_Rotation_Quant
git show fac651f:results/v51-diag/d37/S0/检验段/V0/daily.csv > /tmp/r3-s0-v0-daily.csv
DEV_WORKTREE=/tmp/d37-r4-dev-review .venv/bin/python operations/reviews/diag/v51/d37-r4-verify.py
```
