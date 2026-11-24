# PR359 独立取证（Reviewer · Owner 21:21 来源存档裁定）

供 Coordinator 签发正式 Reviewer 意见；**不在 GitHub 发 review/comment/merge**。

## Git 锚点（Coordinator 固定用于签收）

| 项 | 值 |
| --- | --- |
| **PR359 签收 head** | `1a633b5059ec6571fd5e0afce775918926525969` |
| 首包 commit | `74ea30699d184c01971ee55a0abdbcc1e36d5d84` |
| `e9b12dc` → `1a633b5` | 8 文件 +178/−97（`COVERAGE.md`、`MANIFEST`、session 证据、测试；无业务目录） |
| **PR359 vs `main`** | **3 commits，54 files，+22554**；**无** sqlite / config / roster / `src/` |
| PR359 body / `COVERAGE.md` | **已与 Owner 21:21 对齐**（CNBC+归档 TV 为缺口独立出版方；裁定后标记表） |
| **PR360 NET（359 合并后）** | 仅本目录 3 个文件（见下） |
| PR360 vs `main` ~50 文件 | 谱系：分支含 359 树；合并 359 后净增仅 reviews |

### PR360 预期 NET 三文件

1. `operations/reviews/2026-11-24-pr359-independent-evidence.md`
2. `operations/reviews/pr359-independent-evidence.json`
3. `operations/reviews/pr359-independent-evidence.py`

合并顺序：Manager **merge 359 → merge 360**（merge commit）。

## 时间线

- Review [`6035852626`](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/359#pullrequestreview-6035852626)（`74ea306`）：COMMENTED，要求区分存档 vs 可用日线。
- Owner **2026-11-24 21:21**：**APPROVE SOURCE ARCHIVES ONLY**。
- PR359 **`1a633b5`**：Dev 同步 body/`COVERAGE.md` 与裁定后标记；**Reviewer 本报告据此签收**。

## Owner 21:21 映射

| 裁定 | Reviewer |
| --- | --- |
| CNBC(LSEG) + 归档 TV(ICE) = 缺口独立出版方 | 同意 |
| TV↔sqlite 同源 **仅** 不适用 TV 作独立 DB-overlap | 同意 |
| 日后可用序列排除 `2024-12-25` | 同意 |
| `2023-04-06` TV **259.56** = `single_source` | 同意 |
| `2019-08-12` = `source_conflict`（CNBC **294.58**，TV **294.46**） | 同意；**不推测成因** |
| 931743 名册未改；Appendix A **2023-07-27** | Orchestrator |
| 入库 | **另 PR**（359+360 入 main 之后） |

## 裁定后标记（与 PR359 `COVERAGE.md` 一致；**非**本签收声称已冻结可用日线）

| 日期 | 标记 | 说明 |
| --- | --- | --- |
| 2024-12-25 | `pseudo_session_excluded` | 未来可用序列不采用；raw 原样保留 |
| 2023-04-06 | `single_source` | TV 259.56；CNBC 缺日 |
| 2019-08-12 | `source_conflict` | CNBC 294.58，TV 294.46；**不推测成因** |

上述「不采用/冲突」指 **未来可用序列选源规则**；来源存档 **保留双方原始收盘**，本 PR **不入库**。

## 复算

```bash
python3 -I operations/reviews/pr359-independent-evidence.py
```

- `fresh_download_audits`：Reviewer 重下 raw 的 SHA256 比对（若有）
- `delivered_normalized_samples`：读交付 `normalized` / sqlite，非现场再下

## 库重叠（只读）

| 代码 | source | n | vs 0.1% |
| --- | --- | ---: | --- |
| DJIA | `eastmoney_index` | 63 | 未超 |
| DWRTF | `d37_r6` | 81 | CNBC 0 |

## 931743

正式发布公告 **未找到**；名册 **未改**。

## Coordinator 建议结论

**APPROVE PR359 @ `1a633b5059ec6571fd5e0afce775918926525969` — SOURCE ARCHIVES ONLY**

- **不**在 GitHub 代发 formal approval（由 Coordinator 签发）。
- **不**声称冻结可用日线或完成入库。
- **无**文档同步 blocker（body/`COVERAGE.md` 已在 `1a633b5` 对齐）。

## PR360 blob SHA

签收后以分支 tip 为准：`git ls-tree HEAD operations/reviews/pr359-independent-evidence.{json,py}` 及本 md 的 tree blob（**勿**在工作树 md 内自填 hash-object）。

独立 raw：`/opt/cursor/artifacts/reviewer-pr359/raw/`（不进仓）。