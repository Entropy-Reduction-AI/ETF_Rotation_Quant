# v4-R1d · 数据收尾 · spot-check · 2026-10-28

## Decision：`approve`

在 Dev PR [#94](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/94) 尖端 `302c1c3f11a2e31a74d3626fde7151fee0dab9ae`（base `83f300de0982b740c486017e427f4e7986eef9d9`）上独立复核：PR 仅追加工作日志与 `results/v4/inventory/r1d/` 证据；`data/market.sqlite` LFS oid / 实文件 SHA、`integrity-findings.csv`、预注册与 LOCK **未改**；`bars` 仍为 **787005** 行；**未**跑 v4 候选 PnL 或 2016+ 组合收益。六项声明（931160 缺口、HSTECH 停市、五只上市日、161229 缺日、§3.3 口径）与 Reviewer 只读库查及 PR 内原件 SHA256 **一致**。**未发现 Dev 阻塞缺陷**。

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R1d D16-3 / D16-4 / D16-5 数据收尾 spot-check
- Date: 2026-10-28 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（本 PR 仅 `operations/reviews/**`）
- 签收对象（Dev）: PR #94 · head `302c1c3f11a2e31a74d3626fde7151fee0dab9ae`
- Dev work log: `operations/work_logs/2026-10-28-v4-r1d-data.md`
- Review branch: `review/v4-r1d-spotcheck`（基于 Dev tip，仅追加评审产物）

## 证据总表

| 检查项 | 方法 | 结论 |
| --- | --- | --- |
| 库文件 SHA | `git lfs pull` + `sha256sum data/market.sqlite` | **6c896fd1e5de6bc66ddf6f42833033f202f6e480f4d78c6cd267c6c6a4362248**（246054912 B）与 Dev **一致** |
| `PRAGMA integrity_check` | 只读连接 | **ok** |
| `bars` 行数 | `SELECT COUNT(*) FROM bars` | **787005**（与 R1c 写入后一致，本 PR **无**新 bar） |
| `integrity-findings.csv` | `git diff` base..Dev tip | **无** diff |
| `docs/prereg/` / LOCK | `git diff` base..Dev tip | **无** diff |
| PR 改动面 | `git diff --stat` base..Dev tip | 工作日志 + `r1d/` 证据；**无** `src/`、sqlite 内容变更 |
| v4 单测 | `mkdir -p outputs && .venv/bin/python -m unittest discover -s tests/v4 -t .` | **58** OK |
| 组合 PnL / 2016+ 收益 | 硬规则 | **未**运行 |
| LOCK / tag / 合 main | 纪律 | Reviewer **未**合 main、**未**动 tag / LOCK |

## Bar 结论 spot-check（3/3）

### 1. 931160 · 2019-01 官方空窗 · §3.3

| 子项 | Reviewer 方法 | 结果 |
| --- | --- | --- |
| CSIndex 2019-01 空 | 读 `931160-perf-201901.json`；SHA256 **8309cff7…** 与 work log 一致 | `data: []`，**pass** |
| 2019-02-01 重复窗口起点 | 读 `931160-perf-201902.json`；SHA256 **ecaa3b66…** | 2019-02-01 与 2019-02-22 收盘 **5444.67** 及量额完全相同；**pass** |
| 库内缺口与 carry 价 | `bars` `code=931160` `adj=raw` `source=csi`；`calendar` 上交所 32 日 | 末 bar **2018-12-28** 收 **4303.78**；2019-01-02→2019-02-21 **32** 个交易日 **无** bar；下一根 **2019-02-22**；第 5 个无价 SSE 日 **2019-01-08**（与 §3.3 退出排名起始日声明一致）；**pass** |

Reviewer **未** live 重打 CSIndex API；以 PR 冻结 JSON 与库内序列交叉验证，足以 spot-check。

### 2. HSTECH · 2020-10-13 台风停市（D16-3 accept）

| 子项 | Reviewer 方法 | 结果 |
| --- | --- | --- |
| HKEX 原件 | `hkex-20201013-en.html` SHA256 **aa7d09a1…**；正文 Typhoon Signal No. 8、sessions cancelled | **pass** |
| 上交所港股通 | `sse-hkconnect-20201013.html` SHA256 **1809bab9…**；中投信〔2020〕24 号、台风暂停 | **pass** |
| 库内表现 | `bars` 2020-10-12..14 | **HSI** 2020-10-13 开高低收均为 **24649.68**、量 **0**（前日收平占位）；**HSTECH** **无** 2020-10-13 行（10-12 有、10-14 有）；与 work log「完整性用 HSI 日历、HSTECH 缺日、接受」一致；**pass** |

### 3. 161229 · 无 2026-09-30（D16-5 accept · §3.3 carry）

| 子项 | Reviewer 方法 | 结果 |
| --- | --- | --- |
| 腾讯后复权窗口 | `161229-tencent-hfq-window.json` SHA256 **d4eb0933…** | 末根 **2026-09-29** 收 **1.738**；下一根 **2026-10-08**；**无** 09-30；**pass** |
| 新浪不复权窗口 | `161229-sina-window.json` SHA256 **790d167c…** | 末根 **2026-09-29** 收 **1.368**；下一根 **2026-10-08**；**pass** |
| 库内 tail | `bars` `161229` `adj=raw` | 止于 **2026-09-29** 收 **1.368**；与新浪窗口及 work log 一致；库内 **无** hfq 行（后复权 1.738 仅在外部窗口 JSON，非本 PR 引入）；**pass** |

## 上市日 spot-check（3/5 样本）

Reviewer 对 CSV 全五行做了库内第一根正收盘核对（均一致）；下列 **3** 行额外对照 **登记表 + 本地 evidence 原文**：

| 代码 | CSV `list_date` / `first_positive_close` | Evidence SHA256（登记表） | Reviewer 原文 / 库 |
| --- | --- | --- | --- |
| **510300** | 2012-05-28 / 2012-05-28 | **2eb272eb…**（PDF） | `pdftotext` 资料概要「上市交易所及上市日期」段 **2012 年 05 月 28 日**；库内首正收 **2012-05-28** **2.604**；**pass** |
| **512100** | 2016-11-04 / 2016-11-04 | **656fed48…**（HTML） | 上证公告（基金）【2016】087 号：**2016 年 11 月 4 日**起上市；库内首正收 **2016-11-04** **1.0**；**pass** |
| **515180** | 2019-12-20 / 2019-12-20 | **423f8368…**（PDF） | `pdftotext`「上市日期 **2019-12-20**」；库内首正收 **2019-12-20** **1.0**；**pass** |

（未逐 PDF 抽文的另两只 **510500**、**510880**：CSV 与库内首正收日期 **2013-03-15**、**2007-01-18** 一致；evidence 文件 SHA256 与登记表一致。）

## Dev 缺陷 vs follow-up

| 类型 | 项 | 说明 |
| --- | --- | --- |
| **Dev 缺陷** | （本 spot-check 无） | — |
| **Orchestrator 队列（非本 PR 范围）** | 931160 / HSTECH / 161229 / list_date 等待决 15 行 | R1d 已写结论与证据；**未**回写 `integrity-findings.csv`（符合 Dev 声明） |
| **说明** | 161229 后复权 1.738 | 以腾讯 hfq 窗口 JSON 登记；sqlite 仅 **raw** 序列，与 R1c 后一致，**非** R1d 回归 |

## 诊断 artifact

- `operations/reviews/diag/v4/2026-10-28-v4-r1d-spotcheck.json`

## 链接

- Dev 数据 PR：https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/94
- Review 签收 PR：（本分支 push 后填写）
