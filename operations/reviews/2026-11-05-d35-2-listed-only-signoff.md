# D35-2 · 可交易池场内口径登记重算 · Dev #264 签收 · 2026-11-05

## Metadata

- Project: ETF_Rotation_Quant
- Document type: review（独立复算 + 默认关闭逐位；**未** merge Dev #264）
- Date: 2026-11-05（Asia/Taipei）
- Author: ETF Rotation Reviewer（lwx0218）
- Route: review-only（`operations/reviews/**` + diag JSON）
- Dev PR: [#264](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/264)
- Dev head: **`49a3b75968c413c1f3cff3e8f9d70168182d9fe2`**
- Dev 打开 PR 时 base: **`425c1e83f21c`**（落后于当前 `main` tip **`f7ca1c9`**；含 D36/D37 与 #262 LOCK-addendum 之后的提交。**未**要求 Dev rebase 作为签收前置；本签收针对 head 内容与 LOCK-addendum-D35 登记口径。）
- 依据: `results/v5/LOCK-addendum-D35.md`；`config/v5/listed-only.toml`（默认 `enabled = false`）
- 范围: U-可交易 · 场内口径 ON 时写入 `results/v5/oneshot-listed/`；报告-only；**不计入判据⑤**；不改 D34 `results/v5/oneshot/`

## Decision（对 #264）

**approve**

Reviewer 独立核对：① PR diff **未**修改 `results/v5/LOCK`、`results/v5/oneshot/`、`trial-ledger` 或判据⑤ 账本；② 默认关闭路径下 B0 / A1 / A2 / v5.1 设计期两池与已冻结日净 **逐位一致**（实库跑通 Dev 测试）；③ 场内 ON 的登记窗 E2/B0 年化/MDD 与 Dev 表及 `criteria.csv` 一致，相对 D34 已签收 tradable E2/B0（2.02% / −20.79%）为叙事对照而非重判 D34；④ `listed-by-year.csv` 无 `otc:`、无 `161211`，`allshare-financials-re` 全年 `qualified_days=0`；⑤ oneshot 基准 `net.csv` 与 D34 `results/v5/oneshot/benchmarks/` **字节一致**，`net_sha256`（序列哈希）与 signed 摘要一致；⑥ `data/market.sqlite` SHA256 = OTC 基线 **`1fe4925e7993eb18d93a5cf359185242a98f7114583f7225033a9ec119ec288f`**。manifest 声明 `L5_delta=0`、`formal_pass` 空、`trial_ledger_written=false` 与 diff 一致。

| 级别 | 数量 |
| --- | --- |
| Must-fix | **0** |
| Should-fix | **0** |
| Note | **1**（Dev PR base 落后于 `main`；合入前建议 rebase，非签收阻塞） |

---

## 1 · 禁区与⑤

| 检查 | 结果 |
| --- | --- |
| `git diff main...49a3b759` 触及 `results/v5/LOCK` 正文 | **否** |
| 覆盖 / 改写 `results/v5/oneshot/**` | **否**（仅新增 `results/v5/oneshot-listed/**`） |
| 写入 `results/v5/trial-ledger.csv` 或改动 `attempts.json` | **否** |
| `manifest.json` / `oneshot/manifest.json`：`counts_toward_criterion_5=false`，`L5_delta=0` | **是** |

---

## 2 · 默认关闭 · 设计期逐位（实库）

- 配置: `config/v5/listed-only.toml` → `enabled = false`；`EngineSwitches().listed_only` 默认 **False**（Dev 单测断言）。
- 方法: LFS 实库 → `tests/v51/test_listed_off_bitmatch.py`（v5.1 index/tradable + A1/A2 两池）+ `tests/v5/engine/test_b0_regression.py`（B0 两池，`listed_only=False`）。
- 结果: **8/8 OK**（Reviewer `.venv` @ Dev head worktree，2026-11-05）。

---

## 3 · 场内 ON · E2/B0 登记窗（独立复算）

窗口 **2016-01-01 → 2026-09-30**；方法：`src.report.metrics.cagr` / `max_drawdown` 只读 `oneshot-listed/oneshot/tradable/E2-B0/net.csv`；判据① 中位数与 `criteria.csv` 行 spot-check。

| 口径 | CAGR | MaxDD | n |
| --- | ---: | ---: | ---: |
| **D35-2 listed-on**（本 PR） | **2.508%** | **−16.67%** | 2611 |
| **D34 signed tradable**（`results/v5/oneshot/tradable/E2-B0`） | 2.024% | −20.79% | 2611 |

设计期 listed-on E2/B0（2006–2015）：CAGR **4.986%**，MaxDD **−27.32%**，n=2429。

叙事：场内口径去掉 tier-2 OTC 与 161211 后，登记窗 tradable E2/B0 回撤浅于 D34 全可交易口径，年化略高；**不**改变 D34 已冻结结论与 formal 判据路径。

---

## 4 · 零收益 / 持仓与 `listed-by-year.csv`

| 检查 | 结果 |
| --- | --- |
| `held.csv` 权重列日度和 ≈ 1 | min **0.999999999998**，max **1.000000000002** |
| 有仓位日 `net=0` | **0** 日 |
| `listed-by-year.csv` 含 `otc:` / `161211` | **否** |
| `allshare-financials-re` | 容器在表内；各年 `qualified_days=0`（从未过 3000 万门槛） |

---

## 5 · 基准与数据库

- 基准: `oneshot-listed/oneshot/benchmarks/{BM-main,HS300,NDX,SPX}/net.csv` 与 `results/v5/oneshot/benchmarks/` **逐文件 SHA256 相同**；`summary.json` 的 `net_sha256`（`series_sha256`）与 signed 一致。
- DB: Reviewer LFS 实文件 SHA256 **`1fe4925e7993eb18d93a5cf359185242a98f7114583f7225033a9ec119ec288f`**，与 `oneshot-listed/manifest.json` 一致。
- LOCK / addendum 摘要哈希与 manifest 一致（Dev 树只读引用，未改 LOCK 正文）。

---

## 6 · 证据路径

- 机器可读: `operations/reviews/diag/v51/d35-2-listed-recalc.json`
- Dev 产物根: `results/v5/oneshot-listed/`（head `49a3b759`）

---

## 7 · Reviewer 动作

- 本 PR：**仅**登记上述 Decision；**不** merge Dev #264；**不** merge 本 review PR 至 `main`（除非 Owner 另指示）。
- Dev 合入前建议：rebase 到含 #262 LOCK-addendum 与 OTC 后 `main` tip，消除与 D37 等的分叉噪音（非本签收阻塞项）。
