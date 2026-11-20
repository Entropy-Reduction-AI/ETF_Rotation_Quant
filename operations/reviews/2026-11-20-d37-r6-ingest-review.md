# D37 round 6 · 指数窗口入库 + S1 重跑 · Reviewer 签收 · 2026-11-20

## Metadata

- Project: ETF_Rotation_Quant
- Document type: review（诊断独立复算；**不计入**任何过关判据）
- Date: 2026-11-20（Asia/Taipei）
- Author: ETF Rotation Reviewer（Cloud Agent）
- Dev PR: [#321](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/321)（**OPEN**，base `main` @ `1d56fd90304b44ae965cfb2aa5674cd332046f3c`，head **`aee4b7f780b9fce1e4cea07a3f1662f3ab3c312c`**，`cursor/d37-r6`）
- 数据包只读来源：[#312](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/312) **`grok/d37-r6-partial` @ `332b88fdb1b1b4272edb154754c3bf2925b5889d`**（**未合并**）
- Companion PR: 本分支 `cursor/d37-r6-review-fe00` → **`cursor/d37-r6`**（**未**合并 #321）
- 机器可读: `operations/reviews/diag/d37-r6/d37-r6-recalc.json`；脚本 `operations/reviews/diag/d37-r6/d37-r6-verify.py`；Reviewer 重跑产物 `operations/reviews/diag/d37-r6/rerun/`

## Decision

**approve**

本工作 **不** 重判 v5.1 优劣，**不** 计入过关判据。Must-fix **0**。

| 级别 | 数量 |
| --- | --- |
| Must-fix | **0** |
| Should-fix | **0** |
| Note | **2**（§8） |

---

## 1 · 身份与 PR 清单（#321）

| 项 | Reviewer 结果 |
| --- | --- |
| 状态 | **OPEN**，未合并 |
| head SHA | `aee4b7f780b9fce1e4cea07a3f1662f3ab3c312c`（审查时与 Owner 给定一致） |
| base | `1d56fd90304b44ae965cfb2aa5674cd332046f3c` |
| 提交数 | **2**（`e5222bb` 入库+S1；`aee4b7f` 变基记录） |
| 变更规模 | **823** 文件；`incoming/grok-d37-index-20261116/` 主体 + `results/v51-diag/d37/round6/` + `data/market.sqlite` LFS |
| `results/v5/LOCK` 正文 | **未**出现在 diff ✅ |
| 产品代码 | 仅 `src/v51/d37_round6.py` + `tests/v51/test_d37_round6.py`（入库/重跑器，非策略逻辑改写） |
| #312 | **OPEN**，`merged_at` 空 ✅；未把 #312 merge 进本分支 |

---

## 2 · 行情库 SHA256 与 append-only

| 对象 | SHA256 |
| --- | --- |
| base `main` @ `1d56fd90`（Reviewer worktree + LFS） | `c07297f8372c2b4dd8f79417306f4dda3b2b49db3cb2523a6ad306c13523588b` ✅ |
| #321 head `data/market.sqlite` | `79ba7780f7f5304d189bc49bd7dda9ff1e6325c88888165d71a0c9fae7c26a52` ✅ |
| Dev `db-sha256.txt` / `db-writes.txt` AFTER d37-round6 | 同上 ✅ |

**已有行**：Reviewer 对 **411** 个既有 `code` 做 `(date, close)` 全量对照（before vs after），**0** 篡改、**0** 消失；新增 **25** 个 `code`（`source=d37_r6`），与 `ingest.json` 一致。

---

## 3 · 入库计数与 Owner 裁决

| 类别 | Dev 宣称 | Reviewer |
| --- | ---: | --- |
| 已完成入库 | 20 | **20**（`group=complete`） |
| 部分完成入库 | 5 | **5**（`group=partial`） |
| 冻结（11） | 11 | **11**（名单与 `d37_round6.HELD` 一致；库内 **无** `d37_r6` 泄漏） |

`python -m src.v51.d37_round6 --check`：**exit 0**，25 条全部 `OK`（双日线中位数 ≤ 0.01% 或部分完成单源规则）。

### 3.1 五条部分完成起点（= max(发布日, 连续覆盖)）

| 容器 | 入库起点 | DB `MIN(date)` | 行数 |
| --- | --- | --- | ---: |
| SPAHLVCP | 2017-08-04 | 2017-08-04 | 1507 |
| SP5NENRS | 1998-12-31 | 1998-12-31 | 4038 |
| SP5CSSUP | 2022-11-25 | 2022-11-25 | 294 |
| IXY | 1998-12-16 | 1998-12-16 | 4351 |
| SPNCSCUP | 2020-05-14 | 2020-05-14 | 116 |

早前洞 **未** 补（例：SPAHLVCP 无 2017-02-20；SPNCSCUP 无 2018-12-24 段）。

### 3.2 十一条冻结（独立核对理由 = Dev `HELD` + `--check` 未构建入库行）

豆粕、巴西 IBOVESPA、东证、MSCI China VW、MSCI USA 50、DAXK、iEdge EA50、新交所泛东南亚科技、富时亚太低碳、富时沙特、恒生中国企业 —— 缺第二独立日线 / 收益类型不一致 / 双官方发布日未决 / 仅汇率无指数等，与 Owner 2026-11-20 口径一致。**未**发现应入库却被误冻的条目。

---

## 4 · 点位抽查（≥8；实际 **12**）

| # | 检查项 | 结果 |
| ---: | --- | --- |
| 1 | `399006` 腾讯仍在、`399006.SZSE` 新代码 | ✅ |
| 2 | HSFML25 行数/起点 vs `ingest.json` | ✅ |
| 3 | HSISC 同上 | ✅ |
| 4 | **IXY 2000-01-21 收盘 288.89**（非 CNBC 293.63） | ✅ |
| 5–9 | 五条 partial `MIN(date)` | ✅ |
| 10 | S5INFT 2001-09-11..14 **未**填；有 2001-01-02 CNBC 补洞 | ✅ |
| 11 | SPGOGUP 自 2011-07-08 | ✅ |
| 12 | SPAHLVCP 无连续覆盖前补齐 | ✅ |

---

## 5 · S0 / S1 独立重跑

Reviewer **未** 全矩阵 V0–V4 重跑（工作量与 #321 已提交 `round6/S1/**` 重叠）。**已**独立重跑：

- **S0 检验段 V0** vs 第五轮 `S0/检验段/V0`：**2611 天，逐位一致**（与 Dev `s0-v0-check.txt` 一致）
- **S1 设计期 V0**、**S1 检验段 V0**、**S1 检验段方案 B**（同步 `s1-index-registry.csv` / `s1-splice-roster.csv` 后）

### 5.1 Reviewer 重跑 vs Dev `round6` 产物

| 格 | 年化（round6） | 与 Reviewer 重跑 |
| --- | ---: | --- |
| S1 设计期 V0 | 10.13% | **一致** |
| S1 检验段 V0 | 1.65% | **一致** |
| S1 检验段 B | 6.24% | **一致** |

### 5.2 round6 vs 第五轮（`s1-vs-previous.csv`；预期小幅漂移）

| 格 | round6 年化 | 第五轮 | Δ |
| --- | ---: | ---: | ---: |
| 设计期 V0 | 10.13% | 10.25% | −0.12pp |
| 检验段 V0 | 1.65% | 1.66% | −0.01pp |
| 检验段 B | 6.24% | 6.20% | +0.04pp |

S0 V0 检验段 **不受** 新拼接影响（与第五轮 bit-identical），符合「中国检验段主干未因 append 漂移」的预期。

---

## 6 · 复现

```bash
cd /path/to/ETF_Rotation_Quant
git checkout aee4b7f780b9fce1e4cea07a3f1662f3ab3c312c
git lfs pull --include="data/market.sqlite"

git worktree add /tmp/d37-r6-main 1d56fd90304b44ae965cfb2aa5674cd332046f3c
cd /tmp/d37-r6-main && git lfs pull --include="data/market.sqlite"

BEFORE_DB=/tmp/d37-r6-main/data/market.sqlite \
  .venv/bin/python operations/reviews/diag/d37-r6/d37-r6-verify.py
```

---

## 7 · 纪律

Reviewer **未** merge #321 或 companion PR；**未** push `cursor/d37-r6`；**未** 改 `results/v5/LOCK` 正文；**未** 移动 tag 或改写 `main`；**未** 合并/变基 #312。

---

## 8 · Note

1. 独立重跑时 `diag_d37` 仍打印「S0 V0 对不上签收」后 **停止同段后续版本** —— 指中国 oneshot 签收对照的已知路径，**不**影响上表与第五轮 r5 产物的 bitmatch（见 `d37-r6-recalc.json`）。
2. 沪深300 **十个行业** 指数 **未** 在本包；incoming 无该批入库痕迹 ✅。