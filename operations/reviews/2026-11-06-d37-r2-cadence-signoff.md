# D37 round 2 · v5.1 cadence 诊断 · Reviewer 签收 · 2026-11-06

## Metadata

- Project: ETF_Rotation_Quant
- Document type: review（诊断独立复算；**不计入**任何过关判据）
- Date: 2026-11-06（Asia/Taipei）
- Author: ETF Rotation Reviewer（Cloud Agent）
- Dev PR: [#271](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/271) @ `447b5453c89ebb2f3a79ee87bb1961c59566c8c1`（分支 `cursor/d37-v51-cadence-diag-68d4`）
- Companion PR: 本仓库 `cursor/d37-r2-cadence-signoff-0a7d` → `main`（**未**合并 #271）
- 依据: `results/v5/LOCK-addendum-D37.md`；Dev 产物 `results/v51-diag/d37/`
- 机器可读: `operations/reviews/diag/v51/d37-r2-recalc.json`；复跑脚本 `operations/reviews/diag/v51/d37-r2-verify.py`

## Decision

**approve**

本诊断 **不** 重判 D34 oneshot / U-指数结论，**不** 计入 v5 预注册 §6.4 或任何其它过关判据。D35 场内口径（已在 `main`）**不是** 本 round 新门禁。

| 级别 | 数量 |
| --- | --- |
| Must-fix | **0** |
| Should-fix | **0** |
| Note | **1**（见 §5） |

---

## 1 · 1a 签收库逐位（S0 V0 检验段）

| 项 | Reviewer 独立结果 |
| --- | --- |
| 库来源 | git 提交 `af8edfd` 的 LFS 对象 → 临时 `/tmp/market-167d4e39.sqlite`（**未**覆盖 `data/market.sqlite`） |
| SHA256 | `167d4e39ffab4302e6f55d2b3436b3400ea28b2282cd7f9b9bda644d87c1acf3` |
| 方法 | Dev worktree @ #271 head 上 `diag_d37.run_cn(检验段, V0, S0)` + 与 `results/v5/oneshot/index/v5.1-对照/net.csv` 逐日对比 |
| 交易日数 | 2611（2016-01-04 → 2026-09-30） |
| **net 最大绝对差** | **0.0** |
| 不一致日期 | 无 |

Dev 说明文件 `baseline-167d4e39-note.txt` 与上述一致；Reviewer **未** 将其当作证据，只作对照。

---

## 2 · 检验段矩阵（当前库产物，S0/S1 × V0–V4）

对照基线为 **#271 当前库** 上的 S0 V0 检验段（Owner 裁定；OTC 续接导致与签收 oneshot 名字列 64 天不同，**不是** cadence 代码失败）。

### 2.1 签收库 vs 当前库 S0 V0（检验段）

| 口径 | 年化 | 最大回撤 | picks 不同天数 | market 不同天数 | 首次 picks 分歧 |
| --- | ---: | ---: | ---: | ---: | --- |
| 签收库重跑（167d4e39） | −3.33% | −53.65% | — | — | — |
| 当前库（#271 产物） | −3.46% | −54.32% | 64 | 0 | 2019-03-08 |

### 2.2 各格独立复算 vs Dev `stats.json`

从各格 `daily.csv` 的 `net` 与 `buy`/`sell`/`cost` 复算年化、最大回撤、每年笔数、双边换手、每年成本（BM-主 来自 `benchmark_returns(..., allow_after=True)`）。**10/10 格与 Dev 公布值一致**（浮点容差见 JSON）。

| 范围 | 版本 | 年化 | 最大回撤 | 每年笔数 | 双边换手/年 | 每年成本 | 与 Dev |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| S0 | V0 | −3.46% | −54.32% | 69.9 | 69.0 | 6.62% | ✅ |
| S0 | V1 | −1.22% | −47.92% | 64.9 | 64.0 | 6.44% | ✅ |
| S0 | V2 | −2.66% | −51.45% | 63.7 | 65.5 | 6.43% | ✅ |
| S0 | V3 | −2.57% | −46.83% | 80.1 | 79.1 | 7.54% | ✅ |
| S0 | V4 | −1.27% | −44.34% | 70.6 | 72.6 | 7.08% | ✅ |
| S1 | V0 | 1.90% | −40.39% | 51.2 | 59.3 | 5.12% | ✅ |
| S1 | V1 | 2.81% | −32.73% | 48.6 | 57.5 | 5.07% | ✅ |
| S1 | V2 | 2.66% | −35.38% | 48.7 | 58.4 | 5.12% | ✅ |
| S1 | V3 | 2.09% | −43.62% | 53.9 | 63.0 | 5.40% | ✅ |
| S1 | V4 | 3.21% | −38.08% | 50.2 | 60.3 | 5.25% | ✅ |

### 2.3 库 SHA256

| 时点 | SHA256 | 说明 |
| --- | --- | --- |
| 签收 oneshot | `167d4e39…` | 1a 临时库 |
| `main` 工作区（Reviewer 跑数时） | `1fe4925e7993eb18d93a5cf359185242a98f7114583f7225033a9ec119ec288f` | LOCK-addendum-D37 写入时 OTC baseline；**不是** #271 跑诊断时的库 |
| #271 本轮结束（Dev 登记） | `6b8af8a22cac80c87909f1ace55181bac94577f457607cf8caaca8d8e6fff89a` | 独立 `sha256sum` Dev worktree 实文件，与 `db-sha256.txt` / `manifest.json` 一致 |

---

## 3 · S1 发布日抽查

- `s1-splice-roster.csv`：**25** 行 `status=spliced`，与 Dev 声称一致。
- 抽查 SOX（`theme-PHLX Semiconductor Sector Index`）、NBI、NDXTMC、931790（中韩半导体）、多只中证海外/港股通容器，以及若干 **未拼接** 行：拼接后 **第一次可打分日均 ≥ 正式发布日**；样本中 **0** 例违反。
- **931790**：库内仍有发布日前的旧 bars（1778 行），Dev 说明为不覆盖已有序列；拼接逻辑只从发布日取收益，第一次可打分 2022-12-28 ≥ 2021-12-20。详情见 JSON `s1_publish_spot_check`。

---

## 4 · D35 小表口径（仅标签，未复跑 gate）

Dev `report.md` 中检验段 **1.58% / −20.94%** 来自 **场内口径重算** `49a3b759`（`results/v5/oneshot-listed/`，开盘前持仓复原、**不是** 签收账本原列）。签收指数池 E2/B0 oneshot 为 **2.508% / −16.67%**（167d4e39 库）。**二者不可混读**；D35 已在 `main`，本诊断不将其当作新判据。

---

## 5 · Note（非 Must-fix）

- #271 上 S0 V0 检验段与签收 oneshot **state/picks/held** 有多项差异（Dev `manifest.json` `allow_v0_diff: true`）；**net 在签收库上已证明代码路径正确**，当前库差异归因 OTC 续接，与 Dev `inspection-v0-note.txt` 一致。
- Reviewer **未** 合并 #271；**未** 修改 `results/v5/LOCK` 或 LOCK-addendum 正文；**未** 移动 tag。

---

## 6 · 复现

```bash
# 见 operations/reviews/diag/v51/d37-r2-verify.py 文件头注释
DEV_WORKTREE=/tmp/d37-dev-review SIGNED_DB=/tmp/market-167d4e39.sqlite \\
  python operations/reviews/diag/v51/d37-r2-verify.py
```
