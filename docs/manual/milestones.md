# 里程碑索引

## Metadata

- Project: ETF_Rotation_Quant
- Document type: index
- Status: active
- Owner: L. Loric
- Maintainer: Manager
- Last updated: 2026-11-04（`milestone/v5-code-freeze` 指向 `8970bcbc`：D34-1 #251+#252；`results/v5/LOCK` 待 D34-3 PR 合入；设计期 ≤2015-12-31；过关 B0；既有标签不移动）
- Source of truth: `operations/planning/2026-10-28-d14-owner-decisions.md`（D14-2）；清理前 `git ls-remote --tags origin`；D23-1 新增见 `operations/work_logs/2026-10-29-v4-prereg-freeze-tag.md`；D26-5 见 `operations/planning/2026-10-31-d26-v5-direction.md`；2026-11-01 新增见 `operations/work_logs/2026-11-01-v5-prereg-freeze-tag.md`；2026-11-04 新增见 `operations/work_logs/2026-11-04-v5.1-prereg-freeze-tag.md`；2026-11-04 代码冻结见 `operations/work_logs/2026-11-04-v5-code-freeze-tag.md`

## Purpose

登记 2026-10-28 清理前 origin 上的全部 12 个附注标签，以及清理之后按 Owner 决定新增的标签。标签对象 SHA 是附注标签对象本身，不是剥开后的提交（`^{}`）。三个保留标签的对象 SHA 以本表为准，删除其他标签时不得改变。新增标签写在文末，不改上表。

清理前读取时，仓库不是浅克隆，`origin/main` 为 `29650f0d5fa88b29d8ba460c7a4855fb74178edf`。

## 十二个标签

| 标签 | 标签对象 SHA | 指向提交 SHA | 说明 | 处置 | 理由 |
| --- | --- | --- | --- | --- | --- |
| `milestone/phase1-archive` | `4812115867d0e9176175bd45d21b2dae19c10979` | `0dd93fa13e0aa79b09ef16ba80676c022004be02` | Phase 1 archive: closeout + external reading notes (D9-7) | 保留 | 第一阶段里程碑，对应现在的 README。永不删除、不移动 |
| `milestone/v3.1-prereg-freeze` | `e3b55a7b8ce967a43341a3c9d02e6a0a42e2b508` | `1040035ee1d707368b58687994894189753843ac` | D10 v3.1 prereg freeze. Reviewer PR #36 decision approve_with_follow_up on the parent, the rebased equivalent of 1c52b5b725b60471280dbbca4779d7f66e808315, now 3a9415da1ac226a72e02c47c2b8fe25c0ee962c7. Rule commit lineage c6205e0985161aeba2335af582a758f91911e7cb is now c29758a70c4bb3b29a1a8fd3cebed4d249e4da92. B1/B2 closed. G2/G3 engineering follow-ups do not block this freeze. No results/v3/LOCK. No milestone/v3-code-freeze. | 保留 | 现行基线的规则在看结果之前冻结的证据 |
| `milestone/v3-code-freeze` | `f1d3d0c170ecbd5eb3b463c26834bafd5dc40254` | `b1f84d899f4a37914c1ce4ef0ab16484f0ef7cdb` | v3.1 代码冻结 D11-4；一次性检验未批准 D11-5 | 保留 | 现行基线（v3.1 = E2）的代码。名字里是 v3，内容是 v3.1，不改名 |
| `milestone/v1-code-freeze` | `abaac28cdb532cf678d1eee212106514930f1e11` | `cb8fe7b09253208fba157195c2fefbf3eb76d2b3` | restore from 2026-10-23 cleanup log。2026-10-23 记录中的说明：V1 预注册实现的代码冻结 | 删除 | V1 已关闭。提交在 `origin/main` 历史上。不是现行基线 |
| `milestone/v1-r2-stop` | `f1e2cbf836007f2128eb2f89326cc5756d533ce7` | `ed1501cf2ec2eed6a025f39786fb83f1e432b491` | restore from 2026-10-23 cleanup log。2026-10-23 记录中的说明：V1 刻画分不开，STOP | 删除 | V1 的 STOP 记录。提交在 `origin/main` 历史上。不是现行基线 |
| `milestone/v2-prereg-freeze` | `efe33cbc77779664db791c0a721c78bff76c7a5b` | `1ad86ac0150138b7284cca7566d421e63bf39032` | restore from 2026-10-23 cleanup log。2026-10-23 记录中的说明：v2 预注册冻结 | 删除 | v2 已关闭。提交在 `origin/main` 历史上。现行规则冻结是 `milestone/v3.1-prereg-freeze` |
| `milestone/v2-oos-result` | `72b492d9242d917f49ddae29aa6762efd24769f3` | `36e53ce0cc0a35c9d99d7461d01b6107b3ed1279` | restore from 2026-10-23 cleanup log。2026-10-23 记录中的说明：v2 样本外一次性运行的产物 | 删除 | 结果标签不在新规矩的两个名字里。提交在 `origin/main` 历史上 |
| `milestone/v3-prereg-freeze` | `007c9accf9be2c423564b7b885ea1961124b7f32` | `bfeb49cc65eb0ba419bc98348f1d643fac1211f6` | G1: prereg v3 frozen (Owner approved 2026-10-24) | 删除 | v3 预注册已被 v3.1 取代。提交在 `origin/main` 历史上。现行规则冻结是 `milestone/v3.1-prereg-freeze` |
| `milestone/core-portfolio-live-config` | `86eefebc5c2af14610efb870bc52331129057cd4` | `745ecedca4bfef5f5af881182c1fbcb9c5a32cac` | restore from 2026-10-23 cleanup log。2026-10-23 记录中的说明：D7 之后的生产配置 | 删除 | 第一阶段生产配置，不在 `<版本>-prereg-freeze`、`<版本>-code-freeze`、`phase<N>-archive` 里。提交在 `origin/main` 历史上 |
| `keep/cursor/owner-progress-boundary-audit` | `08b76ccddfe2636214c2986f1967088be64b8288` | `6cba1c77d4c9309df6a2b3375c8654cd1b6162fa` | 留档：PR #42 已关闭，看板由已合入的 #48 取代。尖端未进 main。 | 删除 | 不再用 `keep/*` 保存已关闭 PR。指向提交等于 `refs/pull/42/head`，PR 页面仍保留该提交 |
| `keep/cursor/task-complete-owner-experience` | `65cd8b74149ff9b0a7645427ac9637420dd1e465` | `cbc80ca069e26f6398cc2dc2df899228260963a6` | 留档：PR #46 已关闭。UI/UX 已进入 docs/reference/owner-facing-uiux-principles.md（#48）。尖端未进 main。 | 删除 | 不再用 `keep/*` 保存已关闭 PR。指向提交等于 `refs/pull/46/head`，PR 页面仍保留该提交 |
| `keep/cursor/v3.1-prereg-review-7a9f` | `156aef4316e695ddd3a98278fe6b0e9f5a9f2469` | `fa825b7beccacda24004fdb52f48b3073fddf052` | 留档：PR #33 已关闭，由已合入的 #36 取代。退回评审文件不在 main。 | 删除 | 不再用 `keep/*` 保存已关闭 PR。指向提交等于 `refs/pull/33/head`，PR 页面仍保留该提交 |

处置按 D14-2。删除是否执行，以 `operations/work_logs/2026-10-28-tag-cleanup.md` 的核对结果为准：核对不过的不删。

## 执行结果

2026-10-28，D14-2 已执行。上表 9 个「删除」标签已从 origin 去掉（PR #71 写入索引和纪律，PR #72 独立核对 `approve`）。核对时没有跳过的标签。三个「保留」标签的对象 SHA 与上表一致，清理之后没有移动。

收口核对时 `origin/main` 为 `3d5ce322899576c1dbb7d0e3d456b7c7c8eac1bd`。`git ls-remote --tags origin` 只剩：

| 标签 | 标签对象 SHA | 指向提交 SHA |
| --- | --- | --- |
| `milestone/phase1-archive` | `4812115867d0e9176175bd45d21b2dae19c10979` | `0dd93fa13e0aa79b09ef16ba80676c022004be02` |
| `milestone/v3.1-prereg-freeze` | `e3b55a7b8ce967a43341a3c9d02e6a0a42e2b508` | `1040035ee1d707368b58687994894189753843ac` |
| `milestone/v3-code-freeze` | `f1d3d0c170ecbd5eb3b463c26834bafd5dc40254` | `b1f84d899f4a37914c1ce4ef0ab16484f0ef7cdb` |

「十二个标签」那张表仍是清理前的登记，处置列不改。

## 清理之后新增

2026-10-29，D23-1。Owner 批准 v4 预注册第 2.3 版。附注标签打在合入 PR #118 后的 `main` 上。新建时 origin 上还没有这个名字；没有移动、删除或改写任何既有标签。三个保留标签的对象 SHA 与上表一致。

| 标签 | 标签对象 SHA | 指向提交 SHA | 说明 | 处置 | 理由 |
| --- | --- | --- | --- | --- | --- |
| `milestone/v4-prereg-freeze` | `830320d03712df3a4098f352be8932e0553b5eeb` | `6bcba53e36e74ec81dd21fb7ee7b8cea695038fb` | D23-1 Owner 批准 v4 预注册第 2.3 版；合入 PR #118 后的 main | 保留 | v4 规则冻结。名字按 `milestone/<版本>-prereg-freeze` |

核对见 `operations/work_logs/2026-10-29-v4-prereg-freeze-tag.md`。

## `milestone/v4-code-freeze`

2026-10-29，v4-R5b。Reviewer 对 D24 U-可交易修复的结论是 `approve_with_follow_up`（PR #127，提交 `4a541df328361e967dcc87acb2b01892f4fcaae9`；修复在 PR #126，提交 `82f97453af6a221c5385fa6ddd5d21223d5b0383`）。收尾 PR #128 rebase-merge 之后，`main` 尖端是 `476abd7cb63395506c6a9bb5fdad0f7b16827f66`。附注标签打在这个提交上。新建时 origin 上还没有这个名字。`milestone/phase1-archive`、`milestone/v3-code-freeze`、`milestone/v3.1-prereg-freeze`、`milestone/v4-prereg-freeze` 的对象 SHA 与上表一致，没有移动。

附注说明：`v4-R5b D24 U-tradable fix signed off; design-period ≤2015-12-31; no LOCK; no 2016+`。

打标签时核对过：设计期上界 2015-12-31；该提交里没有 `results/v4/LOCK`。`milestone/v4-prereg-freeze` 仍指向 `6bcba53e36e74ec81dd21fb7ee7b8cea695038fb`。

| 标签 | 标签对象 SHA | 指向提交 SHA | 说明 | 处置 | 理由 |
| --- | --- | --- | --- | --- | --- |
| `milestone/v4-code-freeze` | `4ce2f2919b7c1bcf12dcd1bdd3eee77ae964a603` | `476abd7cb63395506c6a9bb5fdad0f7b16827f66` | v4 ⑦ 代码冻结。#128 rebase-merge 后的 main。D24 已签收。U-指数 20 条 `net_sha256` 相对 v4-R5 不变；过关表 SHA `32058828…`；库指纹 `79ae5a47…` | 保留 | v4 代码冻结。名字按 `milestone/<版本>-code-freeze` |

本索引提交只补上表。没有移动、删除或改写任何标签，也没有改写 `main`。

### D25-5 · `milestone/v4-code-freeze-2`

2026-10-30，v4-R5c。D25 按 v3 §9.4 把两处实现当成程序错误：U-指数成交价改回研究序列，A1 / A2 的 U-可交易月末判断改回附表 A 的研究序列；创业板指第 2 档非增强基金入库。Reviewer 对 PR #132 的结论是 `approve_with_follow_up`（PR #133，提交 `dff13f20d817abd2461603d4fcd09ac42c598647`；重跑在 `9c3e41c`）。过关仍是 B0。账本仍是 41 行。设计期上界仍是 2015-12-31。没有 `results/v4/LOCK`。没有 2016-01-01 及以后的组合收益。

上表的 `milestone/v4-code-freeze` **不移动、不删除、不改写**。它仍是附注对象 `4ce2f2919b7c1bcf12dcd1bdd3eee77ae964a603`，指向 `476abd7cb63395506c6a9bb5fdad0f7b16827f66`。R5c 之后的代码冻结用新名字 **`milestone/v4-code-freeze-2`**。

该附注标签已在 origin 上。标签对象 `aa72a148b8a598fa2cf9b488dcb21e5a9943d6c5`，指向 `c9f4e44c94c54922b6927b6f4d4902edf79e5dd8`。附注说明：`v4-R5c D25 U-index fill + A1/A2 peer口径 signed off; design-period ≤2015-12-31; no LOCK; no 2016+`。标签日期 2026-10-30（Asia/Taipei）。本索引不移动、不删除、不重建它。

D26-5 / v5-R1（决定 `operations/planning/2026-10-31-d26-v5-direction.md`；任务 `operations/planning/2026-10-31-v5-r1-plan.md` §1）：`c9f4e44` 不包含 D25-8 的 510880 `close_correction` 插入（`src/v4/data/d25_8.py` 的 `INSERT INTO v4_series`），也不包含完整性尖刺检查代码（`src/v4/data/spike_check.py`）。插入与尖刺检查在 #136 进入 `main`（插入提交 `af8edfd`，rebase-merge 尖端 `aa1d89f`）。#137（`a728a08`）签收，#138（`3b2d3b5`）刷新体检输入与可交易池读数。#139 rebase-merge 之后，`main` 尖端是 `0e82225b5155af735e53311f5f415b0eca7a3f3c`。标签仍停在 `c9f4e44`。

设计期上界仍是 2015-12-31。`c9f4e44` 里没有 `results/v4/LOCK`。没有 2016-01-01 及以后的组合收益。

`milestone/phase1-archive`、`milestone/v3-code-freeze`、`milestone/v3.1-prereg-freeze`、`milestone/v4-prereg-freeze` 的对象 SHA 与上表一致，本说明不改它们。

| 标签 | 标签对象 SHA | 指向提交 SHA | 说明 | 处置 | 理由 |
| --- | --- | --- | --- | --- | --- |
| `milestone/v4-code-freeze-2` | `aa72a148b8a598fa2cf9b488dcb21e5a9943d6c5` | `c9f4e44c94c54922b6927b6f4d4902edf79e5dd8` | v4-R5c 代码冻结名。指向 `c9f4e44`，不含 D25-8 的 510880 `close_correction` 插入与尖刺检查。设计期 ≤2015-12-31；无 LOCK；无 2016+ | 保留 | D25-5 登记的新名字。D26-5 注明实际指向，不改指向 |

本索引提交只补上面的注明。没有移动、删除或改写任何标签，也没有改写 `main`。

## `milestone/v5-prereg-freeze`

2026-11-01。附注标签打在 #157 squash-merge 之后的 `main` 尖端 `f2ab4f527b3081b0b73ebc860f3aedd8ee54523e`。尖端提交写入 Reviewer 对大类草稿的 `approve`（`operations/reviews/2026-11-01-v5-classes-draft-signoff.md`）。父历史含 D29（`aad13a60b1c6bd7aa7e19548da234d62094a0b82`，PR #156 rebase-merge：Owner 批准 v5 预注册四处选择）。新建时 origin 上还没有这个名字。`milestone/phase1-archive`、`milestone/v3-code-freeze`、`milestone/v3.1-prereg-freeze`、`milestone/v4-prereg-freeze`、`milestone/v4-code-freeze`、`milestone/v4-code-freeze-2` 的对象 SHA 与上表一致，没有移动。

附注说明：`v5 prereg freeze (D29 Owner four choices; #156 classes-draft signed #157; design-period ≤2015-12-31; no LOCK; no 2016+)`。标签日期 2026-11-01（Asia/Taipei）。

打标签时核对过：该提交的预注册写明中国数据的设计期运行只允许 end ≤ 2015-12-31；树里没有 `results/v5/LOCK`。`results/v5/inventory/classes-draft.csv` 为 117 行，六条原 `manual_rule` 已定类；标普全球石油指数归美股（美国为最大上市国别权重）。没有跑回测，没有改写 `main`。

| 标签 | 标签对象 SHA | 指向提交 SHA | 说明 | 处置 | 理由 |
| --- | --- | --- | --- | --- | --- |
| `milestone/v5-prereg-freeze` | `40aac3ced0f1f7e710403cd49076a0fb4a91c51c` | `f2ab4f527b3081b0b73ebc860f3aedd8ee54523e` | D29 Owner 批准 v5 预注册四处选择；#156 大类草稿 117 行经 #157 Reviewer approve 后的 main。无 `results/v5/LOCK`。设计期 ≤2015-12-31 | 保留 | v5 规则冻结。名字按 `milestone/<版本>-prereg-freeze` |

本索引提交只补上表。没有移动、删除或改写任何标签，也没有改写 `main`。

核对见 `operations/work_logs/2026-11-01-v5-prereg-freeze-tag.md`。

## `milestone/v5.1-prereg-freeze`

2026-11-04。附注标签打在 #230 rebase-merge 之后的 `main` 尖端 `1174e475ecb62995eb420f700bd1771b52e34295`。尖端提交是 Reviewer 对 v5.1 预注册 R1b 的 `approve`（MF/SF 全闭合）。父提交 `d9c966f035805cfb3bee9b8d564ea8ab65ade5e2` 已含 #228 的 R1b 稿（合并提交 `5bd75a0243ecfa00d8181efa60ce48827a252503`）。新建时 origin 上还没有这个名字。`milestone/phase1-archive`、`milestone/v3-code-freeze`、`milestone/v3.1-prereg-freeze`、`milestone/v4-prereg-freeze`、`milestone/v4-code-freeze`、`milestone/v4-code-freeze-2`、`milestone/v5-prereg-freeze` 的对象 SHA 与上表一致，没有移动。

附注说明：`v5.1 prereg freeze (R1b approve #230; #228 R1b稿; design-period ≤2015-12-31; no LOCK; no 2016+)`。标签日期 2026-11-04（Asia/Taipei）。

打标签时核对过：该提交含 `docs/prereg/etf-multiasset-rotation-prereg-v5.1.md`；正文写明中国数据只允许 end ≤ 2015-12-31。树里没有 `results/v5.1/LOCK`。没有跑回测，没有改写 `main`。

| 标签 | 标签对象 SHA | 指向提交 SHA | 说明 | 处置 | 理由 |
| --- | --- | --- | --- | --- | --- |
| `milestone/v5.1-prereg-freeze` | `87a57809bac36f1f2feec4b79e52656be456a35b` | `1174e475ecb62995eb420f700bd1771b52e34295` | R1b approve #230；#228 R1b 稿。无 `results/v5.1/LOCK`。设计期 ≤2015-12-31 | 保留 | v5.1 规则冻结。名字按 `milestone/<版本>-prereg-freeze` |

本索引提交只补上表。没有移动、删除或改写任何标签，也没有改写 `main`。

核对见 `operations/work_logs/2026-11-04-v5.1-prereg-freeze-tag.md`。

## `milestone/v5-code-freeze`

2026-11-04。附注标签打在 #252 rebase-merge 之后的 `main` 尖端 `8970bcbc7986c9a67d9ca535ca58a8855c910495`。尖端提交是 Reviewer 对 D34-1 换手「合计」双计修复的 `approve`。父提交 `6df9b9b4a8470d18117807484cb5328f72d1bc24` 是 #251 的 rebase-merge（合计只加一次来源）。新建时 origin 上还没有这个名字。`milestone/phase1-archive`、`milestone/v3-code-freeze`、`milestone/v3.1-prereg-freeze`、`milestone/v4-prereg-freeze`、`milestone/v4-code-freeze`、`milestone/v4-code-freeze-2`、`milestone/v5-prereg-freeze`、`milestone/v5.1-prereg-freeze` 的对象 SHA 与上表一致，没有移动。

附注说明：`v5 code freeze (D34-1 turnover total signed #251+#252; wrap+SF1 on main; gate B0; design-period ≤2015-12-31; no results/v5/LOCK; no 2016+)`。标签日期 2026-11-04（Asia/Taipei）。

打标签时核对过：该提交的预注册 v5 与 v5.1 都写明中国数据只允许 end ≤ 2015-12-31。树里没有 `results/v5/LOCK`，也没有 `results/v5.1/LOCK`。`results/v5.1/design/gate.csv` 的入围名单是 B0。wrap 签收 `5a4678127bedea72c88b503de4e4f496d83f6899`（Dev #241）与 SF1 账本测试签收 `753d34ab3dfef7f7ab12010218effa22ce3b3fd2`（Dev #243）已在该提交的历史上。没有跑回测，没有改写 `main`。

| 标签 | 标签对象 SHA | 指向提交 SHA | 说明 | 处置 | 理由 |
| --- | --- | --- | --- | --- | --- |
| `milestone/v5-code-freeze` | `0aeae744177074c84bce68206021c21c6963341a` | `8970bcbc7986c9a67d9ca535ca58a8855c910495` | D34-1 #251 合计只加一次来源，#252 Reviewer approve。wrap 与 SF1 已在 main。过关名单 B0。无 `results/v5/LOCK`。设计期 ≤2015-12-31 | 保留 | v5 代码冻结。名字按 `milestone/<版本>-code-freeze` |

本索引提交只补上表。没有移动、删除或改写任何标签，也没有改写 `main`。

核对见 `operations/work_logs/2026-11-04-v5-code-freeze-tag.md`。

## Related Files

- `operations/planning/2026-10-28-d14-owner-decisions.md`
- `operations/work_logs/2026-10-28-tag-cleanup.md`
- `operations/work_logs/2026-10-29-v4-prereg-freeze-tag.md`
- `operations/work_logs/2026-11-01-v5-prereg-freeze-tag.md`
- `operations/work_logs/2026-11-04-v5.1-prereg-freeze-tag.md`
- `operations/work_logs/2026-11-04-v5-code-freeze-tag.md`
- `operations/reviews/2026-11-01-v5-classes-draft-signoff.md`
- `operations/planning/2026-10-30-v4-r5c-plan.md`
- `operations/reviews/2026-10-30-v4-r5c-d25-signoff.md`
- `operations/planning/2026-10-31-d26-v5-direction.md`
- `operations/planning/2026-10-31-v5-r1-plan.md`
- `docs/manual/roadmap-and-naming.md`
- `AGENTS.md`
