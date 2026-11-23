# PR #343 · 申万一级 2021 版官方日线 incoming · Reviewer 签收 · 2026-11-23

## Metadata

- Project: ETF_Rotation_Quant
- Document type: operations review（**reviews-only companion**；不合并 Dev PR）
- Date: 2026-11-23（Asia/Taipei；独立核对完成于 **16:24** 之后）
- Author: ETF Rotation Reviewer（Cloud Agent）
- Subject PR: [#343](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/343)（**OPEN**，未合并）
- Head branch: `cursor/incoming-sw-l1-20261123`
- Head SHA: `48e0ec02ad9b584f96ebb8ecea480ed3bdb3517f`
- Head tree: `ee1e7dc47cb817d7b7be5f83c480474fa309111a`
- Head commit time: 2026-11-23T08:24:35Z = 2026-11-23 16:24:35 Asia/Taipei
- Companion PR: 本分支 → **`cursor/incoming-sw-l1-20261123`**（**未**合并 #343 或本 companion）
- 机器可读: `operations/reviews/diag/incoming-sw-l1-20261123/pr343-signoff-facts.json`
- Entry: **incoming only**；**未**写 `data/market.sqlite`；**未**入库；**未**算收益或 PnL

## Decision（已定，勿改）

**`approve`**

| 级别 | 数量 |
| --- | --- |
| Must-fix | **0** |
| Should-fix | **0** |
| Note | **4**（§9） |

Reviewer **不会** merge #343 或本 companion。Manager 仅在本 reviews-only companion **已 open** 后合入 #343；incoming only，不入库。#339 在冻结前保持 open。

---

## 1 · PR 身份与相对 main

| 项 | 值 |
| --- | --- |
| 状态 | **OPEN**，未合并 |
| 存储的 PR base | `main` @ `120becee585a0fe7a3e4555942e656919c5ed392` |
| 核对时 current main | `b2aef6a0db3d67cb27d082b2a9f8212accd3b6b9`（#344 merge） |
| vs current main | diverged；ahead **2** / behind **5**；mergeable=true；mergeable_state=clean |
| PR 规模 @ 本 tip | **2** commits；**98** files；**+149537 / 0** |
| 相对 current main 独有 | **98** added files，均在 `incoming/grok-sw-l1-20261123/`；**无**该前缀外路径；**无** `data/market.sqlite` |

---

## 2 · 相对上一 tip `4797949f` 的增量

| 项 | 值 |
| --- | --- |
| 本 tip 唯一新提交 | `48e0ec02`（parent `4797949fe02b7def89e349baf99fa177f0859613`） |
| 变更文件 | 仅 `incoming/grok-sw-l1-20261123/NOTE.md`（新增，62 行，7096 bytes，git blob `f9b78014763bcc7705868bda589c7aefb5ddda5f`）；`incoming/grok-sw-l1-20261123/MANIFEST.md`（+8 / -1，git blob `85e55931fd83fe43591c621a89b6c16684531cd3`） |
| 31 条日线 CSV blob | **未变** |
| 既有官方文档 / 往来 / 元数据 blob | **未变** |
| MANIFEST series 表 | **31/31** 行一致（counts、起止、CSV SHA256、官方 JSON SHA256） |
| MANIFEST file 表 | 原 **96** 行未变；仅新增 NOTE.md 一行 |
| NOTE.md SHA256（原始字节） | `777db2d1149c0dedd6fa19cfd14b6c9fdf4f5cd2743927292112a75f3d4ff1f2`（7096 bytes，与 MANIFEST file 表新行一致） |
| MANIFEST 页脚 | **97** files excluding MANIFEST；**17,618,611** bytes（= 原 17,611,515 + 7,096；自 file 表独立加总） |

---

## 3 · Check 1（MANIFEST 与日线完整性）— **PASS**

因 31 条日线与官方 JSON SHA256 行未变，Reviewer 在 `4797949f` 上的独立 PASS 对本 tip **仍有效**。

- MANIFEST 对除 `MANIFEST.md` 外每个打包文件登记哈希（现 **97** files）。
- **96/96** 原打包文件：本地 SHA256 与字节数仍与（未变的）file 表一致。
- **31/31** 日线 CSV：已提交字节、行数、起止仍与 series 表一致（16×6496 自 1999-12-30；11×3082 自 2014-02-21；801950×3089 自 2014-02-21；801960/801970/801980×1188 自 2021-12-13；全部结束 **2026-11-20**）。
- 2026-11-23 Asia/Taipei 早些时候对官方 trend 的 live 重取（DigiCert 中间证书 GeoTrust G2 TLS CN RSA4096 SHA256 2022 CA1）：**31/31** HTTP 200、api code 200；**31/31** live JSON SHA256 与 MANIFEST「官方 JSON SHA256」一致；日期集合与打包 CSV 一致；官方末日 **2026-11-20**。新 MANIFEST 中 JSON 哈希未变，故与早先独立 live fetch 一致。本 docs-only tip **未**再做全量 31 路 re-fetch。

---

## 4 · Check 2（列与映射）— **PASS 31/31**

- 列：`swindexcode,bargaindate,openindex,maxindex,minindex,closeindex,bargainamount,bargainsum,hike,markup`
- 映射：open=openindex，high=maxindex，low=minindex，close=closeindex，turnover/成交额=bargainsum，volume=bargainamount
- open/high/low/close/turnover（及 volume/hike/markup）**0** null/empty；无重复日期；无 swindexcode 错配；high/low 边界失败行 **0**
- MANIFEST 字段句仍只列前八个列名（hike/markup 未写在 MANIFEST 句中）。incoming-only 包：**非** Must-fix / Should-fix；可选 Note

---

## 5 · Check 3（官方缺口，非下载遗漏）— **PASS**（包未 patch）

- 深交所 `monthList` 将 **8** 个日期、**2015-11-27** 及五个样本日均标为交易日（jybz=1）
- Live 官方 API payload（字节与 MANIFEST JSON 哈希一致）缺少相同行
- 分组：范围内 **27** 个系列缺全部 8 日（16 个自 1999-12-30 + 11 个自 2014-02-21，**除** 801950）：801010, 801030, 801040, 801050, 801080, 801110, 801120, 801130, 801140, 801150, 801160, 801170, 801180, 801200, 801210, 801230, 801710, 801720, 801730, 801740, 801750, 801760, 801770, 801780, 801790, 801880, 801890
- **801950**：含全部 8 日；范围内仅缺 **2015-11-27**（邻日 2015-11-26、2015-11-30）；官方 JSON SHA256 仍为 `18c2501255ec1bf83b3a137b9d52184c3b64b911b5df9d37440a098ab6785f2f`；count 仍 **3089**
- **801960/801970/801980**：官方/包起点 **2021-12-13**，8 日在起点之前，非范围内缺口
- NOTE.md 现已写明上述分组（较早前「30 系列缺 8 日」表述更准确）

---

## 6 · Check 4（相对 live 官方 trend API  spot）— **PASS 15/15**

对照来源为 pack 引用的 **live 官方 trend API**，非渲染 HTML 图。

五个深交所交易日 **801120、801780、801750** 各一点：**2016-01-04、2018-12-28、2021-12-13、2024-06-28、2026-11-20** — 包内与官方均存在。

**15/15** 亦匹配 `bargainamount`、`hike`、`markup`。

示例 **801120 2016-01-04** packed/官方 open/high/low/close/turnover：**6948.77 / 6959.7 / 6494.97 / 6497.57 / 125.0286688335**

---

## 7 · Check 5（Grok 结论「未找到」）— **PASS**

**问题**：对 **28** 个在 2021-12-13 前有历史的代码（801010–801230 共十六个；801710–801890 加 801950 共十二个），官方点是否为同期已发布水平（代码复用），还是按 2021 成分回算？Owner 要求 verbatim 官方引文，或「未找到」且不做推断。

**Grok** 在 NOTE.md / MANIFEST 结论：**未找到**。Reviewer 独立阅读打包官方文件（blob 与 `4797949f` 未变；SHA256 与 MANIFEST 一致）**同意**。最近似可引用的官方句**不能**在两种解释间裁决；Reviewer **亦不推断**。

已核对原文摘引（verbatim）：

1. `official-docs/announcements/2021-07-31-19CBFEC8.txt`（745 bytes，SHA256 `a32a57bd32c5ed0cd55015d00915ef82b5de216cd23fc30dab213ebe08ab7aec`）含句：
   「基于申万行业分类标准（2021版）的新行业指数计划于2021年11月中旬发布，届时老行业指数（基于2014年行业分类）将同时终止发布，新行业指数将按《申万指数编制说明》追溯至该行业有成分股计入之日始。」
   — 说明新指数将按编制说明追溯至成分计入日及老指数停发；**未**说明追溯点是否等于同期已发布水平，或是否用 2021 成分。

2. `official-docs/announcements/2021-11-23-43CE85B9.txt` 与 `2021-11-23-8C619116.txt` 字节相同（315 bytes，SHA256 `588a47a6ff9d1de7d2cddb7910280d6d7859749b97a1b446baef90447b1482e8`）含句：
   「经过精心准备和一段时间的平稳运行，2021版申万行业指数将定于2021年12月10日18:00至2021年12月12日24:00进行新老切换，自2021年12月13日起发布2021版申万行业指数，申万行业指数分类标准敬请参考以下链接。申万行业指数分类标准2021版说明.xlsx」
   — 家族级切换/发布句；**未**说明 2021-12-13 之前点位如何产生。

3. `official-docs/80100350.txt`（编制说明 5.0；87844 bytes；SHA256 与上一 tip / MANIFEST 一致）。目录 §6.3 题为「指数计算」；该节下有「行业分类调整」子节，文档他处引用「参见 6.3"行业分类调整"」，故 Grok 标 §6.3「行业分类调整」准确。去 PDF 断行空白后含段：
   「某一行业有新公司进入视为"成份股计入指数"处理，某行业中原有上市公司退出视为"成份股退出"处理。为保持指数的连续性，如果某一行业有新公司进入或原有公司退出，指数进行调整。」
   — 成分进出与连续性调整，**非**分类版本切换后历史重述声明。全文无「追溯、回算、回测、重述」。§4.2 仅定价格序列基日 1999-12-31 / 1000。附录一写明 5.0 算法 2025-10-31 生效、行业分类参考由 2011 版改 2021 版；**未**说历史点是否重算。

4. 打包 `official-docs` 全部 `*.txt` / `*.html` 中，唯一「追溯」命中为 2021-07-31 公告（txt 与 html）。**无**其他公告文本回答该问题。

5. `official-docs/SwClassStd2021.pdf`（pdftotext）：「配套指数《申银万国行业指数》的调整时间将另行确定。」**零**命中追溯/回算/重述/历史。

2026-11-23 约 **16:32** Asia/Taipei 尝试 live `index_announcements/details/?id=19CBFEC8-…`：TLS 校验成功（同上中间证书），但 **HTTP 508**、body 空。Check 5 **倚靠**打包官方文件（SHA256 与 MANIFEST 一致）。Grok 亦披露 2054 次公告 detail 抓取中 **43** 次 HTTP 555 未读；标题为成分调整等，含两个 2009/2010 行业股价系列 IDs，**非** 2021 历史点方法论说明。Reviewer **未**独立重拉全部 2054 条公告。

---

## 8 · 边界（本 companion 与 Dev PR）

| 约束 | Reviewer |
| --- | --- |
| 写 `data/market.sqlite` | **否** |
| 入库 incoming pack | **否** |
| 收益 / PnL | **否** |
| 改 LOCK / 业务 `src/` | **否** |
| merge #343 / companion | **否** |
| push `main` 或 `cursor/incoming-sw-l1-20261123` | **否** |

---

## 9 · Notes（非 Must-fix / Should-fix）

1. **TLS**：官方 swsresearch.com 叶证书链不完整。Reviewer 早前 31/31 live trend fetch 使用已发布 DigiCert 中间证书 GeoTrust G2 TLS CN RSA4096 SHA256 2022 CA1。Dev 补充抓取在其环境无法校验证书；已在 NOTE.md 记录，且 JSON SHA256 未变，与 Reviewer 早前独立哈希一致。

2. **Incoming only**：勿写 `data/market.sqlite`、勿入库、勿算收益。

3. **可选文档**（非 Should-fix）：MANIFEST 字段句仍省略 hike/markup，而每条 CSV 均含这两列。

4. **Live 公告 detail**：16:32 Asia/Taipei 重取 HTTP 508；Check 5 使用打包官方文件。

---

## 10 · 复现提示（只读）

```bash
git checkout 48e0ec02ad9b584f96ebb8ecea480ed3bdb3517f
# 对照 incoming/grok-sw-l1-20261123/MANIFEST.md、NOTE.md 与 official-docs/
# 不写入 data/market.sqlite；不跑 ingest
```

签收事实索引：`operations/reviews/diag/incoming-sw-l1-20261123/pr343-signoff-facts.json`