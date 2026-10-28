# 标签清理（D14-2）

## Metadata

- Project: ETF_Rotation_Quant
- Task: D14-2 标签清理
- Date: 2026-10-28
- Owner: L. Loric
- Route: direct-execute
- Source of truth: `operations/planning/2026-10-28-d14-owner-decisions.md`（D14-2）；`operations/planning/2026-10-28-v4-r1b-plan.md` §1

## 目标

按 D14-2 精简 origin 上的标签：保留 3 个现行基线标签，删除列出的 9 个。删除前把 12 个标签全部写入 `docs/manual/milestones.md`。核对不过的不删。不移动任何标签。不删除、不移动 `milestone/phase1-archive`。不改写 `main`。

## 改动面

- 新建 `docs/manual/milestones.md`：12 行，含标签对象 SHA、指向提交、说明、处置和理由。三个保留标签的对象 SHA 是删除前从 origin 读到的值。
- `AGENTS.md`：tag 与分支纪律改为不移动任何 tag；删除 tag 只按 Owner 决定记录执行，且先写入里程碑索引；`milestone/phase1-archive` 永不删除、不移动。数据约束加一句：取数按 `docs/manual/data-principles.md`。「分支」一节与上述纪律对齐，不再要求 `keep/*`。
- `docs/manual/roadmap-and-naming.md`：每个版本最多 `milestone/<版本>-prereg-freeze` 与 `milestone/<版本>-code-freeze`；每个阶段一个 `milestone/phase<N>-archive`；不再用 `keep/*`。
- 本工作记录。
- origin 上删除通过核对的 9 个标签（普通删除，没有 `--force`）。没有改 `src/`，没有跑组合收益，没有改 `data/market.sqlite`。

## 验证

清理前 `git rev-parse --is-shallow-repository` 为 `false`。`git fetch origin main` 之后 `origin/main` 为 `29650f0d5fa88b29d8ba460c7a4855fb74178edf`。

删除前 `git ls-remote --tags origin`（12 个附注标签；`^{}` 是剥开后的提交）：

```text
08b76ccddfe2636214c2986f1967088be64b8288	refs/tags/keep/cursor/owner-progress-boundary-audit
6cba1c77d4c9309df6a2b3375c8654cd1b6162fa	refs/tags/keep/cursor/owner-progress-boundary-audit^{}
65cd8b74149ff9b0a7645427ac9637420dd1e465	refs/tags/keep/cursor/task-complete-owner-experience
cbc80ca069e26f6398cc2dc2df899228260963a6	refs/tags/keep/cursor/task-complete-owner-experience^{}
156aef4316e695ddd3a98278fe6b0e9f5a9f2469	refs/tags/keep/cursor/v3.1-prereg-review-7a9f
fa825b7beccacda24004fdb52f48b3073fddf052	refs/tags/keep/cursor/v3.1-prereg-review-7a9f^{}
86eefebc5c2af14610efb870bc52331129057cd4	refs/tags/milestone/core-portfolio-live-config
745ecedca4bfef5f5af881182c1fbcb9c5a32cac	refs/tags/milestone/core-portfolio-live-config^{}
4812115867d0e9176175bd45d21b2dae19c10979	refs/tags/milestone/phase1-archive
0dd93fa13e0aa79b09ef16ba80676c022004be02	refs/tags/milestone/phase1-archive^{}
abaac28cdb532cf678d1eee212106514930f1e11	refs/tags/milestone/v1-code-freeze
cb8fe7b09253208fba157195c2fefbf3eb76d2b3	refs/tags/milestone/v1-code-freeze^{}
f1e2cbf836007f2128eb2f89326cc5756d533ce7	refs/tags/milestone/v1-r2-stop
ed1501cf2ec2eed6a025f39786fb83f1e432b491	refs/tags/milestone/v1-r2-stop^{}
72b492d9242d917f49ddae29aa6762efd24769f3	refs/tags/milestone/v2-oos-result
36e53ce0cc0a35c9d99d7461d01b6107b3ed1279	refs/tags/milestone/v2-oos-result^{}
efe33cbc77779664db791c0a721c78bff76c7a5b	refs/tags/milestone/v2-prereg-freeze
1ad86ac0150138b7284cca7566d421e63bf39032	refs/tags/milestone/v2-prereg-freeze^{}
f1d3d0c170ecbd5eb3b463c26834bafd5dc40254	refs/tags/milestone/v3-code-freeze
b1f84d899f4a37914c1ce4ef0ab16484f0ef7cdb	refs/tags/milestone/v3-code-freeze^{}
007c9accf9be2c423564b7b885ea1961124b7f32	refs/tags/milestone/v3-prereg-freeze
bfeb49cc65eb0ba419bc98348f1d643fac1211f6	refs/tags/milestone/v3-prereg-freeze^{}
e3b55a7b8ce967a43341a3c9d02e6a0a42e2b508	refs/tags/milestone/v3.1-prereg-freeze
1040035ee1d707368b58687994894189753843ac	refs/tags/milestone/v3.1-prereg-freeze^{}
```

六个 `milestone/*` 用 `git merge-base --is-ancestor <指向提交> origin/main`，全部通过：

```text
PASS ancestor milestone/v1-code-freeze object=abaac28cdb532cf678d1eee212106514930f1e11 commit=cb8fe7b09253208fba157195c2fefbf3eb76d2b3
PASS ancestor milestone/v1-r2-stop object=f1e2cbf836007f2128eb2f89326cc5756d533ce7 commit=ed1501cf2ec2eed6a025f39786fb83f1e432b491
PASS ancestor milestone/v2-prereg-freeze object=efe33cbc77779664db791c0a721c78bff76c7a5b commit=1ad86ac0150138b7284cca7566d421e63bf39032
PASS ancestor milestone/v2-oos-result object=72b492d9242d917f49ddae29aa6762efd24769f3 commit=36e53ce0cc0a35c9d99d7461d01b6107b3ed1279
PASS ancestor milestone/v3-prereg-freeze object=007c9accf9be2c423564b7b885ea1961124b7f32 commit=bfeb49cc65eb0ba419bc98348f1d643fac1211f6
PASS ancestor milestone/core-portfolio-live-config object=86eefebc5c2af14610efb870bc52331129057cd4 commit=745ecedca4bfef5f5af881182c1fbcb9c5a32cac
```

三个 `keep/cursor/*` 的指向提交对照 `git ls-remote origin refs/pull/42/head refs/pull/46/head refs/pull/33/head`，全部相等：

```text
fa825b7beccacda24004fdb52f48b3073fddf052	refs/pull/33/head
6cba1c77d4c9309df6a2b3375c8654cd1b6162fa	refs/pull/42/head
cbc80ca069e26f6398cc2dc2df899228260963a6	refs/pull/46/head
PASS equal keep/cursor/owner-progress-boundary-audit object=08b76ccddfe2636214c2986f1967088be64b8288 commit=6cba1c77d4c9309df6a2b3375c8654cd1b6162fa refs/pull/42/head=6cba1c77d4c9309df6a2b3375c8654cd1b6162fa
PASS equal keep/cursor/task-complete-owner-experience object=65cd8b74149ff9b0a7645427ac9637420dd1e465 commit=cbc80ca069e26f6398cc2dc2df899228260963a6 refs/pull/46/head=cbc80ca069e26f6398cc2dc2df899228260963a6
PASS equal keep/cursor/v3.1-prereg-review-7a9f object=156aef4316e695ddd3a98278fe6b0e9f5a9f2469 commit=fa825b7beccacda24004fdb52f48b3073fddf052 refs/pull/33/head=fa825b7beccacda24004fdb52f48b3073fddf052
```

没有跳过的标签。索引提交 `61e35373598629f4a8d4ec819242ecdc6e8ff2ac` 已推到 `cursor/d14-2-tag-cleanup-59d0` 之后，才执行删除。删除命令没有 `--force`，名单里没有三个保留标签：

```text
git push origin --delete \
  refs/tags/milestone/v1-code-freeze \
  refs/tags/milestone/v1-r2-stop \
  refs/tags/milestone/v2-prereg-freeze \
  refs/tags/milestone/v2-oos-result \
  refs/tags/milestone/v3-prereg-freeze \
  refs/tags/milestone/core-portfolio-live-config \
  refs/tags/keep/cursor/owner-progress-boundary-audit \
  refs/tags/keep/cursor/task-complete-owner-experience \
  refs/tags/keep/cursor/v3.1-prereg-review-7a9f
```

远端确认这 9 个已删除。随后 `git fetch origin main`，`origin/main` 仍是 `29650f0d5fa88b29d8ba460c7a4855fb74178edf`。没有强推，没有改写 `main`。

删除后 `git ls-remote --tags origin` 只剩 3 个标签。对象 SHA 与删除前一致：

```text
4812115867d0e9176175bd45d21b2dae19c10979	refs/tags/milestone/phase1-archive
0dd93fa13e0aa79b09ef16ba80676c022004be02	refs/tags/milestone/phase1-archive^{}
f1d3d0c170ecbd5eb3b463c26834bafd5dc40254	refs/tags/milestone/v3-code-freeze
b1f84d899f4a37914c1ce4ef0ab16484f0ef7cdb	refs/tags/milestone/v3-code-freeze^{}
e3b55a7b8ce967a43341a3c9d02e6a0a42e2b508	refs/tags/milestone/v3.1-prereg-freeze
1040035ee1d707368b58687994894189753843ac	refs/tags/milestone/v3.1-prereg-freeze^{}
```

| 保留标签 | 标签对象 SHA | 指向提交 SHA | 与删除前 |
| --- | --- | --- | --- |
| `milestone/phase1-archive` | `4812115867d0e9176175bd45d21b2dae19c10979` | `0dd93fa13e0aa79b09ef16ba80676c022004be02` | 一致 |
| `milestone/v3-code-freeze` | `f1d3d0c170ecbd5eb3b463c26834bafd5dc40254` | `b1f84d899f4a37914c1ce4ef0ab16484f0ef7cdb` | 一致 |
| `milestone/v3.1-prereg-freeze` | `e3b55a7b8ce967a43341a3c9d02e6a0a42e2b508` | `1040035ee1d707368b58687994894189753843ac` | 一致 |

## 完成判据

- origin 上只剩上述 3 个标签，对象 SHA 与清理前一致。
- `docs/manual/milestones.md` 有 12 行。
- 9 个候选全部通过核对并已删除。没有跳过的标签，没有需要交 Orchestrator 的核对失败。
- 已删除提交仍在 `main` 历史上，或仍可由对应 PR 的 head 到达（#42、#46、#33）。
