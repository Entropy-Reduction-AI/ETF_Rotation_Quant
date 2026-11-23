# PR #340 中证行业 incoming 包 · Reviewer 独立签收 · 2026-11-23

## Metadata

- Project: ETF_Rotation_Quant
- Document type: operations review（**reviews-only companion**；**不合并** Dev PR #340）
- Date: 2026-11-23（Asia/Taipei）
- Author: ETF Rotation Reviewer（Cloud Agent）
- Subject PR: [#340](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/340)（author `lwx0218`）
- Companion base: `cursor/incoming-csi-sectors-20261123-fc40` @ **`fc5834d0bc4b76c793d8064ab65b92cb9a94bedc`**（**未移动**；live 复核与 dispatch 一致）
- PR #340 base（main）: **`bb37214ff4670f27d8060d284345f594d19eb54a`**
- Tree（#340 head）: **`2e504f89450c29cbf21df6afd866495c9cbd9201`**
- 机器可读: `operations/reviews/diag/pr340/pr340-recalc.json`；`operations/reviews/diag/pr340/pr340_verify.py`
- **未** 写入 `data/market.sqlite`；**未** 计算策略 / v6 / 组合收益；**未** merge #340 或本 companion；**未** 改 LOCK / tag / `main`

## Decision（供 Coordinator 引用）

**`approve`**

| 级别 | 条数 |
| --- | --- |
| Must-fix | **0** |
| Should-fix | **0** |
| Note | **2** |

**#340 必须继续只停留在 `incoming/`，不得在未另案 custody / ingest 签收的情况下写入 `data/market.sqlite` 或合并入 main。Reviewer 不 merge。**

---

## 1 · 签署对象与 diff 边界

| 项 | Reviewer 独立结论 |
| --- | --- |
| head SHA | `fc5834d0bc4b76c793d8064ab65b92cb9a94bedc` |
| tree SHA | `2e504f89450c29cbf21df6afd866495c9cbd9201` |
| base SHA（main） | `bb37214ff4670f27d8060d284345f594d19eb54a` |
| 变更文件数 | **156**（GitHub PR 元数据一致） |
| 独有路径 | 仅 `incoming/grok-csi300-sectors-20261123/`、`incoming/grok-csi-allshare-l1-20261123/` |
| `data/market.sqlite` | **未触及** |
| mergeable | clean（GitHub live） |

### 文件清点（与 PR body 一致）

| 目录 | 合计 | MANIFEST | 概要单 | 完整日线 | 自发布日日线 | metadata |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `incoming/grok-csi300-sectors-20261123/` | **93** | 1 | 30 | 30 | 30 | 2 |
| `incoming/grok-csi-allshare-l1-20261123/` | **63** | 1 | 20 | 20 | 20 | 2 |

30 + 30 = CSI300 十行业 **价格指数 + 全收益 + 净收益**（000908–000917、H00908–H00917、N00908–N00917）。20 = 中证全指一级 **价格指数 + 全收益**（000986–000995、H00986–H00995）；**无** N00986–N00995 文件。

---

## 2 · Checklist 1 — MANIFEST / 哈希 / 计数

| 子项 | 结论 |
| --- | --- |
| 概要单 PDF × 50 | `metadata/factsheet-metadata.csv` SHA256 **50/50** 与磁盘一致；与 `MANIFEST.md` 首表 **50/50** 一致 |
| 自发布日 CSV × 50 | `from_publish_sha256` **50/50** 与 `dailies/from-publish-date/*.csv` 一致 |
| 完整日线官方 JSON | Reviewer 对 **50** 条 `index-perf` 重拉（`startDate=20040101&endDate=20261122`），响应体 SHA256 与 `MANIFEST.md` / `dailies-summary.csv` **50/50** 一致 |
| 完整日线 CSV 字节 | 已在 `pr340-recalc.json` → `csv_file_pin_sha256` **50** 条独立 pin（MANIFEST 登记的是 **JSON** 哈希，不是 CSV 字节） |
| N00986–N00995 | 目录 **0** 个 `N0098*` 路径；价格/全收益概要单 `deriv_N` 为空；Reviewer HEAD 探针 **N00986–N00989** OSS URL → **HTTP 404**（与 PR 叙述一致） |

---

## 3 · Checklist 2 — 基日 / 发布日 / 自发布日切片

- `metadata/factsheet-metadata.csv` 中基日均为 **2004年12月31日**、基值 **1000**；沪深300 行业发布日 **2007年7月2日**；全指一级 **2011年8月2日**；N 系列净收益发布日 **2013年2月8日**（与概要单登记一致）。
- **50/50** 条：`dailies-summary.verified_publish_date` = 自发布日 CSV **首行** `tradeDate`（YYYYMMDD）。

---

## 4 · Checklist 3 — 价格指数完整性（2005-01-04 → 2026-11-20）与官网 spot

### 4.1 包内完整性（20 条价格序列）

- 日历：深交所 `monthList` 冻结月 JSON（2005-01 → 2026-09）**+** 2026-10/11 用包内 **000908** 已含 OHLC 的交易日补全（Reviewer VM 访问 `szse.cn` SSL 失败，见 Note）。
- 窗口内 **5314** 个交易日；20 条 000908–000917 / 000986–000995：**末行均为 20261120**；在日历上 **无** 缺行、**无** 缺 OHLC/成交额（2005-01-04 起）。

### 4.2 官网 spot（3 指数 × 5 日 = 15 点，OHLC + 成交额逐字段）

API：`https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode={code}&startDate={d}&endDate=…`

| 代码 | 抽样日期 | 结论 |
| --- | --- | --- |
| 000908 | 20050104、20150612、20200309、20240930、20261120 | **5/5 match** |
| 000990 | 20050104、20110802、20180619、20241115、20261120 | **5/5 match** |
| 000993 | 20050104、20150708、20200203、20251009、20261120 | **5/5 match** |

**官网对比 blocker：无**（15/15 一致）。

---

## 5 · Checklist 4 — H / N 系列成交额首次非空

MANIFEST 口径：全收益/净收益 API 常为仅收盘；Reviewer **不** 将缺 OHLC 记为缺口。各 H/N 日线 `tradingValue` **首次非空**：

| 包 | 序列 | 首次非空 `tradeDate` |
| --- | --- | --- |
| CSI300 | H00908–H00917（10） | 全部 **20040101** |
| CSI300 | N00908–N00917（10） | 全部 **20040101** |
| All-share | H00986–H00995（10） | 全部 **20040101** |

（早期非交易日行在官方 JSON 中仍带 `tradingValue: 0.0`；与 PR 说明一致。）

---

## 6 · Checklist 5 — 重复日、交易日缺口、成交额为 0

| 项 | 结论 |
| --- | --- |
| 重复 `tradeDate`（20 价格序列） | **0** |
| 2005-01-04–2026-11-20 交易日缺口（同上日历） | **0** |
| 价格序列在**交易日**上 `tradingValue==0` | **1** 条：**000916 @ 20080527**（官方 API 同日亦为 0.0；非补造） |

---

## 7 · Must-fix / Should-fix / Note

### Must-fix

（无）

### Should-fix

（无）

### Note

1. **000916 / 20080527**：官方与包内成交额均为 **0.0**（成分仅 2 只、涨跌 0）； custody 上属真实字段，非 gap。
2. **2026-10/11 交易日历**：Reviewer 无法 live 拉取深交所月历；缺口判断在 2026-09 之后用 **000908 包内会话日** 外延，与 20 条价格序列末段一致。

---

## 8 · 推荐结论（唯一）

**`approve`**

原因：diff 仅限两包 `incoming/`；哈希与计数独立复算通过；价格序列在交易日窗口内完整且末日为 2026-11-20；官网 spot 15/15；全指净收益缺失主张与库存/OSS 一致；无 merge、无 sqlite、无收益计算。