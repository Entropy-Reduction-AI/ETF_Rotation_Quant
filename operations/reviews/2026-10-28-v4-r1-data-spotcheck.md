# v4-R1 · 数据采集 spot-check · 2026-10-28

## Decision：`approve_with_follow_up`

在 Dev PR [#65](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/65) 尖端 `10b6a4400e69d9ba1fe544587363d9789e9deea6`（base `0eb25e2ff96a5ab786e5745be0e9306410982560`）上独立复核：`data/market.sqlite` 文件 SHA、哨兵序列与 main 逐字节一致、registry 与 `python -m src.v4.data hash` 一致、随机 spot-check 与 Dev 登记表无冲突；**不**因 Orchestrator 待决的三类「取不到」序列（标普行业 TR、恒生综合 12 行业、HKDCNY 2006 前）否决 Dev 实现。Follow-up 仅登记给 Orchestrator，不是编码缺陷。

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R1 数据采集 spot-check（D13 · ② 标的池）
- Date: 2026-10-28 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（本 PR 仅 `operations/reviews/**`）
- 签收对象（Dev）: PR #65 · head `10b6a4400e69d9ba1fe544587363d9789e9deea6`
- Dev work log: `operations/work_logs/2026-10-28-v4-r1-data-ingest.md`
- Review branch: `review/v4-r1-data-spotcheck`（基于 `origin/main`，仅追加评审产物）

## A. 环境与文件 SHA

| 步骤 | 命令 / 动作 | 日志 |
| --- | --- | --- |
| LFS | `git lfs pull`（PR 尖端 checkout） | — |
| 库文件 | `sha256sum data/market.sqlite` | `/opt/cursor/artifacts/v4-r1-reviewer-spotcheck.json` |
| 完整性 | `PRAGMA integrity_check` | `/opt/cursor/artifacts/v4-r1-reviewer-integrity.log` |
| v4 单测 | `.venv/bin/python -m unittest tests.v4.data.test_ingest -v` | `/opt/cursor/artifacts/v4-r1-reviewer-unittest-v4-data.log` |
| 独立脚本 | `.venv/bin/python operations/reviews/diag/v4/2026-10-28-r1-spotcheck.py` | `/opt/cursor/artifacts/v4-r1-reviewer-spotcheck-run.log` · JSON 同上 |
| Dev CNBC 表 | 重算 `crosscheck.csv` 15 对 | `/opt/cursor/artifacts/v4-r1-reviewer-crosscheck.log` |

| 对象 | Dev 声称 | Reviewer 实测 | 结论 |
| --- | --- | --- | --- |
| `data/market.sqlite`（写入后） | `a130af9e…` | **一致**（129429504 B） | OK |
| `data/market.sqlite`（main 基线） | `3e3e6f1d…` | worktree @ `0eb25e2` **一致** | OK |
| `PRAGMA integrity_check` | `ok` | **ok** | OK |
| `config/v3/universe.toml` | 未改 | 与 main **逐文件相同** | OK |
| `data/universe.csv` | 未改 | 与 main **逐文件相同** | OK |

## B. 哨兵与「不重写既有 bars」

Reviewer 只读打开 PR 尖端库与 main 基线库（`/tmp/etf-main-wt`），对 `C.SENTINELS` 全序列做 `bar_sha256` 对比；并统计「非 v4-R1 新 code」的 `bars` 行数。

| 检查 | 结果 |
| --- | --- |
| `H00300` / `USDCNY` / `510300` / `HSI` / `^SP500TR` | 各行数与 main **一致**，SHA256 **一致** |
| 非 v4 新 code 的 raw bars 行数 | **668746** = main 全库 bars 行数 |
| `universe` 表 | **39** 行（与 Dev 一致） |
| `cash_dividends` | **104** 行（与 Dev 一致） |

结论：**未发现**对既有 A 股 / v3 研究序列的改写。

## C. Registry ↔ DB

| 检查 | 结果 |
| --- | --- |
| `build_coverage(con)` vs `results/v4/inventory/coverage.csv` | **66** 行逐字段一致 |
| `config/v4/universe.toml`（`status=in_db` bar）vs coverage bar 键 | **一致** |
| 全 in_db bar code · `python -m src.v4.data hash CODE` | 行数 + bar/dividend/split SHA 与 coverage **一致**（见 JSON `hash_cli_sample`） |
| Dev `spotcheck.csv` 15 点 vs 库内 close | **15/15** 匹配 |

## D. Spot-check（随机 3 序列 × 5 日 · seed=`20261028`）

按市场独立抽样（脚本 `operations/reviews/diag/v4/2026-10-28-r1-spotcheck.py`）。

### D1 · US（Yahoo 入库）

| 随机 code | 第二来源策略 | 5 日结论 |
| --- | --- | --- |
| `XLRE` | 5/5 Yahoo 实时 chart 重拉 | 绝对差 **0** |
| `XLY` | 4/5 Yahoo 重拉 + **1/5 CNBC**（2025-09-29，差 **2.7e-6**） | 全部 ≤ **1e-4** |
| `SP500-60` | 5/5 Yahoo 重拉（`^SP500-60`） | 绝对差 **0** |

**独立第二来源（CNBC）**：Dev `results/v4/inventory/crosscheck.csv` 中 `XLB` / `XLK` / `XLF` 共 **15** 对（2026 年 5 日 × 3 代码）；Reviewer 重算 DB close、Yahoo 登记价与 CNBC，**bad=0**（最大差与 Dev 同量级 ~6e-6）。

Stooq 在本云环境对 `.us` / `^sp500-60` 日线 **拉取失败**（与 Dev work log「Stooq 挑战页」一致），**未**据此否决。

### D2 · HK（腾讯 `tencent_hk_index`）

| 随机 code | 第二来源 | 5 日结论 |
| --- | --- | --- |
| `HSF` | 腾讯 API **独立重拉**（公开免费源仅此一路） | 5/5 与库 **完全一致** |
| `HSFGTR` | 同上 | 5/5 一致 |
| `HSUGTR` | 同上 | 5/5 一致 |

说明：恒生分类 / GTR 代码在 Yahoo / Stooq **无**可靠免费日线；Reviewer 用 live 腾讯重拉验证「库 = 当前 API」，并交叉核对 Dev `spotcheck.csv` 的 `HSF` 五点。

### D3 · FX

| code | 第二来源 | 5 随机日 |
| --- | --- | --- |
| `HKDCNY` | 中国货币网 `CcprHisNew` **按年重拉** | 5/5 与库 **完全一致** |

Dev 固定五点（含 2006-01-04 首行 **1.0408**）与库一致。

### D4 · 分红（`v4_event` · 随机 3 ETF）

| code | 除息日 | DB amount | Yahoo events | 结论 |
| --- | --- | --- | --- | --- |
| `XLF` | 2021-12-20 | 0.184 | 0.184 | OK |
| `XLC` | 2021-06-21 | 0.141 | 0.141 | OK |
| `XLU` | 2024-09-23 | 0.2695 | 0.2695 | OK |

## E. Dev 声称的「取不到」（Orchestrator · 非 Dev 缺陷）

覆盖表与 `universe.toml` 均为 `status=unavailable`、**rows=0**、无 bars；Dev **未**虚假声称已 ingest：

1. **标普 500 11 个行业 TR**（`^SP500-10TR` … `^SP500-60TR`）— Yahoo 无历史日线；唯一入库行业相关为 **`SP500-60` 价格指数**。
2. **恒生综合行业 12 指数**（`HSCIE` … `HSCIC`）— 目录有元数据，公开日线不可用；已入库替代为 **HSF/HSU/HSP/HSC**（+GTR，2021-04 起）。
3. **`HKDCNY` 早于 2006-01-04** — 中间价接口无数据；首行 **2006-01-04** 与 Dev 说明一致。

## F. 硬门禁

| 检查 | 结果 |
| --- | --- |
| v4 候选组合 / 2016+ 组合 PnL | PR diff **无**；CLI 拒绝 `returns`/`backtest`（单测通过） |
| 合 main / tag / `results/v3/LOCK` / trial-ledger | Reviewer **未**执行；Dev PR **未**改上述路径 |
| 改写 v3 universe / 既有 bars | **否**（§B） |

## G. Follow-up（Orchestrator · 不阻塞 Dev #65）

1. 行业 **全收益 TR** 历史来源决策（购买 / 自建还原 / 接受 ETF 价格+分红口径）。
2. **恒生综合 12 行业** 是否与 GICS 11 对齐、是否接受四类子指数 + 短 GTR 历史。
3. **2006 前 HKD/CNY** 若 v4 需要港币标价港股，需另登记汇率或接受缺口。

## H. 机器可读证据

- `/opt/cursor/artifacts/v4-r1-reviewer-spotcheck.json` — 完整 spot-check、registry、哨兵对比
- `/opt/cursor/artifacts/v4-r1-reviewer-spotcheck-run.log`
- `/opt/cursor/artifacts/v4-r1-reviewer-crosscheck.log`
- `/opt/cursor/artifacts/v4-r1-reviewer-unittest-v4-data.log`
- `/opt/cursor/artifacts/v4-r1-reviewer-integrity.log`

---

**Reviewer 结论**：Dev #65 在「只增 v4 容器、不重写既有库、registry 可机械复算」合同下 **可签收**；待 Orchestrator 事项见 §G，**不作为 return 理由**。
