# PR359 独立取证（Reviewer · Owner 21:21 来源存档裁定）

供 Coordinator 签发正式 Reviewer 意见；**不在 GitHub 发 review/comment/merge**。

## Git 锚点

| 项 | 值 |
| --- | --- |
| PR359 live head | `e9b12dc6a4b24c6e0f470ddbec0fadaf2082b7bf` |
| 首包 commit | `74ea30699d184c01971ee55a0abdbcc1e36d5d84` |
| live 相对首包 | 10 文件 +3507（`COVERAGE.md`、session 证据、测试、Yahoo DWRTF 无柱 JSON 等） |
| PR359 vs `main` | 54 文件 +22473；**无** `data/market.sqlite` / `config/` / roster |
| PR360 当前 head（追加前） | `30ac2f9113b578b3aa0650a7092d8afb463858c2` |
| PR360 vs `main` 显示 ~50 文件 | **谱系假象**：分支从 `74ea306` 长出，含整棵 359 树 |
| **359 合并后 PR360 NET** | 仅下列 3 个路径（`operations/reviews/**`） |

### PR360 合并后预期 NET 文件清单

1. `operations/reviews/2026-11-24-pr359-independent-evidence.md`
2. `operations/reviews/pr359-independent-evidence.json`
3. `operations/reviews/pr359-independent-evidence.py`

合并顺序：Manager **merge 359 → merge 360**（merge commit）。不 restack / 不 force push。

## 时间线（正式 COMMENT）

- [PR359 review `6035852626`](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/359#pullrequestreview-6035852626)：针对 `74ea306`，状态 **COMMENTED / 暂不 approve**，要求区分「来源存档 vs 冻结可用日线」、标出伪日与 `2019-08-12` 冲突（**不作成因推断**）。
- Owner **2026-11-24 21:21 Asia/Taipei**：Reviewer **APPROVE PR359 for SOURCE ARCHIVES ONLY**（非可用日线、非入库）。
- 本报告：**OWNER 授权下的 ARCHIVE-ONLY 签收建议**；**不**声称已产出冻结可用日线序列。

## Owner 21:21 映射

| 裁定 | Reviewer 记录 |
| --- | --- |
| CNBC(LSEG) + 归档 TV(ICE) 可作缺口 **独立出版方** | 同意；共同日相对差复算见 JSON |
| TV 与 sqlite 同源 **仅** 禁止 TV↔库作独立 DB-overlap | 同意；DWRTF 独立库核对 = **CNBC↔库** |
| 两套完整历史 **不必** 均为本轮新下载 | 同意 |
| 日后可用序列 **排除** `2024-12-25` | 同意 |
| DWRTF `2023-04-06` TV **259.56** = single_source | 同意 |
| `2019-08-12` CNBC **294.58** vs TV **294.46** = **source_conflict** | 同意；**禁止成因推断** |
| 931743 名册未改 | 同意；Appendix A **2023-07-27** 由 Orchestrator |
| 后续入库 **另 PR** | 不在本签收范围 |

## 复算与取样诚实性

| 类型 | 含义 |
| --- | --- |
| `fresh_download_audits` | Reviewer 环境重下的 **原始** 文件 SHA256 与 PR 交付 raw 比对（见 JSON） |
| `delivered_normalized_samples` | 仅读 PR **已交付** `normalized/*.csv` 或 sqlite，**不是**另一轮现场下载 |
| `pairs_from_delivered_normalized` | 独立脚本重算相对差，不运行 Dev 脚本作结论 |

命令：`python3 -I operations/reviews/pr359-independent-evidence.py`（exit 0 = 报告写完）。

## 库只读重叠（<0.1% 停止线）

| 代码 | source | 窗 | n | 备注 |
| --- | --- | --- | ---: | --- |
| DJIA | `eastmoney_index` | 2023-11-01 … 2024-02-01 | 63 | 均 <0.1% |
| DWRTF | `d37_r6` | 2017-08-01 … 2017-11-22 | 81 | CNBC max 0 |

## 未冻结可用序列（存档内已标）

- DJIA：CNBC 多 `2024-12-25`（非交易日；raw 保留，不可计入可用覆盖）。
- DWRTF 新下 CNBC：**缺** `2023-04-06`；`2019-08-12` **冲突** 两边均不采用。
- **不** 声称 2224/668 交易日已冻结为可用日线。

## 931743

编制方案仅基日 2018-12-28；正式发布公告 **未找到**；名册 **未改**。

## Coordinator 建议结论

**APPROVE PR359 — SOURCE ARCHIVES ONLY**（在 Owner 群组已明示授权前提下；仍 **不** 在 GitHub 代发 formal approval）。

### 文档同步 blocker（不阻止 ARCHIVE-ONLY 实体签收，但应在正式 PR 描述/签收中对齐）

截至 live head `e9b12dc`，**PR359 body** 与 **`incoming/v6-us-gapfill/COVERAGE.md`** 仍写：

- TradingView「**不再把它算成独立证据**」/「不能算作独立于库的第二来源」
- 「本包不放宽」两套独立覆盖要求窗

这与 Owner **21:21**（TV 可与 CNBC 作为缺口第二出版方；仅 DB-overlap 不适用 TV）**措辞不一致**。Manager 已要求 Dev 同步 BODY；**在 Dev 对齐前，Coordinator 正式描述应以 Owner 裁定 + 本 `operations/reviews/**` 为准**，勿仅引用未更新的 PR body 段落。

### 不妨碍 SOURCE ARCHIVE 签收项

- 上述为 **说明文字** blocker，非 raw 缺失或 sqlite/config 写入。
- 入库、可用日线、冲突日选用：Owner 约定 **后续 ingestion PR**，本包不含。

## PR360 head 与 blob SHA（见分支 tip；下表为工作树 `git hash-object`）

| 路径 | `git hash-object` |
| --- | --- |
| `operations/reviews/2026-11-24-pr359-independent-evidence.md` | `c9f2677528b3e0fb8ca34609b6528e6bb2c58807` |
| `operations/reviews/pr359-independent-evidence.json` | `38245f556840934b62a273247b588c3a98f801d3` |
| `operations/reviews/pr359-independent-evidence.py` | `23b31b50f8acdd3e005019ed8546d2568e219f94` |

见 JSON 内 `fresh_download_audits`；独立 raw 在 `/opt/cursor/artifacts/reviewer-pr359/raw/`（不进仓库）。