# 里程碑索引

## Metadata

- Project: ETF_Rotation_Quant
- Document type: index
- Status: active
- Owner: L. Loric
- Maintainer: Manager
- Last updated: 2026-10-29
- Source of truth: `operations/planning/2026-10-28-d14-owner-decisions.md`（D14-2）；清理前 `git ls-remote --tags origin`；D23-1 新增见 `operations/work_logs/2026-10-29-v4-prereg-freeze-tag.md`

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

## Related Files

- `operations/planning/2026-10-28-d14-owner-decisions.md`
- `operations/work_logs/2026-10-28-tag-cleanup.md`
- `operations/work_logs/2026-10-29-v4-prereg-freeze-tag.md`
- `docs/manual/roadmap-and-naming.md`
- `AGENTS.md`
