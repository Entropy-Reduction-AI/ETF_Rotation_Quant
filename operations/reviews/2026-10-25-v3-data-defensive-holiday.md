# v3 防御资产与海外假日收益 · 2026-10-25

## Metadata

- Project: ETF_Rotation_Quant
- Task: Owner 优先项 ① 长历史防御资产、② 海外假日零收盘（看板第 7–8 项）
- Date: 2026-10-25 (Asia/Shanghai)
- Author: ETF Rotation Reviewer
- Model: composer-2.5
- Route: review-only（仅 `operations/reviews/**` + diag；不改业务代码、不合 main、不写 LOCK、不改预注册正文）
- Prereg: `docs/prereg/etf-multiasset-rotation-prereg-v3.md` @ `milestone/v3-prereg-freeze` → `bfeb49c`
- Dev delivery: `dev/v3-data-defensive-holiday` @ `c80aa56804c8927b762ada71b232c08a24b42fc5`（[PR #29](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/29)）
- Baseline main: `4c6d4b086d28bc58e1ec107210ce1b8125cea4c5`
- Work log: `operations/work_logs/2026-10-25-v3-data-defensive-holiday.md`
- Review branch: `cursor/v3-data-defensive-holiday-review-5690`（基于 `dev/v3-data-defensive-holiday` @ `c80aa568`，仅追加评审产物）

## Goal

独立签收 PR #29：黄金与中债财富研究序列是否按 §3 机械写入容器；`CBA00601` 国债总财富在库但不进池是否合理；`XNDX` 2012-10-29 零收盘删除后人民币日收益是否全为有限数；海外底层是否无同类残留；SHA256 / emit-only / 评估层非有限收益门禁；全量 unittest。

---

## SHA256

| 对象 | Dev 声称 | Reviewer `sha256sum`（LFS pull 后） | 结论 |
| --- | --- | --- | --- |
| `config/v3/universe.toml` | `04ff3572ebd82a5159eaccced0bed5bc3531b732a1b11025f86021ebd0454be0` | **一致** | 冻结 |
| `data/market.sqlite` | `3e3e6f1d594586da2abf28db5fa88b05c1cc91fa29adf061fc699e1b8d4bc1d6` | **一致** | 已写入防御序列与删行 |
| `results/v3/inventory/coverage.csv` | `577125a16c28830f38bb5bbd89ba72179efb848cbe8a725945762db9f4a039b2` | **一致** | 记录 |

机器可读汇总：`operations/reviews/diag/v3/2026-10-25-defensive-holiday-verify.json`（由同目录 `2026-10-25-defensive-holiday-verify.py` 生成）。

**emit-only**：签收环境执行 `python -m src.v3.data emit` 后 `universe.toml` 与 `coverage.csv` SHA **不变**。Reviewer **未**手改 toml。`tests/v3/engine/test_l2.py` 已钉 `UNIVERSE_SHA = 04ff3572…`。

---

## ① 黄金（`gold`）

| 项 | Reviewer 独立结果 |
| --- | --- |
| 研究代码 | `Au99.99`，`series_source = sge_daily` |
| 行数 / 区间 | **4402** 行，**2008-08-11 → 2026-09-30**（`close > 0`） |
| `series_status` | `partial`（首根晚于设计期起点 2006-01-04） |
| §3 发布日 | `publish_date = 取不到`；引擎不按发布日截断（与 Dev / toml note 一致） |
| Au9999 vs Au99.99 | 预注册写 Au9999；toml note 说明 Dailyhq 与历史文章合约字段差异，重叠日一致，**研究序列统一 Au99.99** — 可接受 |

**2006-01-04 → 2008-08-10 缺口**：该段设计期 **黄金容器无研究序列**，不参与 U-指数排名；2008-08-11 起可参与。Dev 丢弃 2003 片段以避免列表缺页导致「五年涨跌记在一个交易日」— `trim_discontinuous_prefix` 逻辑与 work log 一致。

---

## ① 债券（`cgb-10y` / `cgb-5y`）

| 代码 | 容器 | 行数 / 区间 | 编制名称匹配 |
| --- | --- | --- | --- |
| `CBA04501` | `cgb-10y` | 4687，2008-01-02 → 2026-09-30 | 「中债-10年期国债指数」✓ |
| `CBA03101` | `cgb-5y` | 4687，2008-01-02 → 2026-09-30 | 「中债-5年期国债指数」✓ |
| `CBA00601` | **不进池** | 6190，2002-01-04 → 2026-09-30（库内） | 「中债-国债总指数」≠ §3.2 冻结的 10y/5y 名称 |

**CBA00601 判定**：在预注册冻结容器名称下 **机械不写入池** 是正确的；toml 末尾注释仅作参考。看板举例「中债国债总财富」与冻结 §3.2（10 年 / 5 年国债）不一致时，应停手或 v3.1 改预注册 — Dev 行为符合合同，**不是本 PR 缺陷**，但 Owner 若要以总财富替代 10y/5y 需另开版本。

**2006–2007**：10y/5y 财富自 2008-01-02 起，设计期前两年债券仍缺序列。

`publish_date`：编制说明无单列首次发布日，登记「取不到」— 与 §3 一致。

---

## ② 海外假日 / 零收盘

| 检查 | 结果 |
| --- | --- |
| `XNDX` 2012-10-29 零收盘 | **库内无该日 K 线**（已删；原件 `incoming/.../overseas-zero-close.json` 1 行） |
| 2012-10-30 / 2012-11-01 | 无 −100% / +inf；独立 `cny_from_usd` 人民币日收益全 **有限** |
| 2012-10-30 收益 | **+0.057%**（沿用 2012-10-26 美元收盘 + 中间价变动） |
| 2012-11-01 收益 | **−0.636%**（重开市，有限负收益） |
| 海外来源 `close ≤ 0` | **0 行**（`nasdaq`、`yahoo`、`tencent_hk_index`、`stooq`、`eia`） |
| `audit_overseas` 可疑 gap_move | **0 条**（`overseas-holiday-audit.csv` 仅表头） |

修复路径：`src/report/fx.py` `usable_closes` 丢弃非正收盘后再 D−1 对齐；**不是**在评估层把 inf/NaN 填 0。`src/v3/eval/common.py` `_values` 对非有限收益 **抛 `EvalError`**。

单测：`tests/v3/engine/test_holiday.py` 覆盖桑迪窗口有限收益。

---

## 仍未补上的序列（对判定影响）

| 缺口 | 影响 |
| --- | --- |
| 创业板指发布序列 | `chinext` 仍 `gap`；U-指数不含创业板指研究臂 |
| 美股人民币全收益发布序列 | `ndx100`/`spx` 仍为 `total_return_usd` + 中间价换算；非新存「人民币全收益」序列 |
| 豆粕 / 原油超额 | 仍「取不到」 |
| 黄金 2006–2008-08、债券 2006–2007 | 设计期子段可选标的仍偏少；需 Orchestrator 复诊（看板第 4 项） |

覆盖登记表：研究 **81** 条，`ok` 77、`partial` 1（黄金）、`gap` 3 — emit 输出与 work log 一致。

---

## 工程门禁

| 项 | 结论 |
| --- | --- |
| `results/v3/LOCK` | **不存在** |
| 2016+ 组合收益 / `allocate_container` 接线 | **本 PR 未交付**（与 work log 一致） |
| 全量 unittest | **448** 项，**OK**（skipped=1） |
| 合 main / tag / 强推 | Reviewer **未**执行 |

---

## Follow-up（不阻塞 ①② 签收）

1. **Owner / v3.1**：若要坚持「国债总财富」单容器，需改预注册后再 emit；`CBA00601` 已在库待命。
2. **黄金更长历史**：上金所列表缺页导致 2008-08-11 为可机械追溯起点；2002 举例需新来源或 Owner 接受 partial。
3. **创业板指、美股 CNY 全收益**：仍 gap；G2 设计期复诊时一并登记。
4. **债券 `publish_date`**：取不到时引擎不截断；若担心回填点进入 R/s，应在数据说明中保留（已记在 toml note）。

---

## Decision

**approve_with_follow_up**

- **②** 海外假日零收盘：独立复算通过，审计无残留，评估层不零填非有限收益 — **签收**。
- **①** 在冻结 §3.2 名称下机械纳入黄金（partial）与 10y/5y 财富 — **签收**；`CBA00601` 不进池 **正确**；与设计期仍缺 2006–2008 黄金、2006–2007 债券及 chinext / 美股 CNY 发布序列的 gap — **记入 follow-up**，不退回本 PR。

## Reviewer signature

- ETF Rotation Reviewer（composer-2.5）
- 2026-10-25
- 冻结 `config/v3/universe.toml` SHA256 = `04ff3572ebd82a5159eaccced0bed5bc3531b732a1b11025f86021ebd0454be0`
- Parent delivery SHA: `c80aa56804c8927b762ada71b232c08a24b42fc5`
