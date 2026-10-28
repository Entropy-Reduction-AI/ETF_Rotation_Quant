# v4-R1b · D14-2 标签清理独立核对 · 2026-10-28

## Decision：`approve`

Manager D14-2 执行与 PR #71 合入文档（`origin/main` = `d5d460abde1f320f775fce23787644a7b7b050c5`）满足 `operations/planning/2026-10-28-v4-r1b-plan.md` §1 与 D14-2 完成判据。Reviewer 未创建、删除或移动任何 tag，未合并 `main`。

## Metadata

- Project: ETF_Rotation_Quant
- Task: v4-R1b plan §1 标签清理（Reviewer 独立核对）
- Date: 2026-10-28 (UTC)
- Author: ETF Rotation Reviewer（独立签收）
- Route: review-only（`operations/reviews/**` + diag；未改业务代码、未动 tag）
- Manager 工作记录: `operations/work_logs/2026-10-28-tag-cleanup.md`
- 里程碑索引: `docs/manual/milestones.md`
- 机器可读证据: `operations/reviews/diag/v4/v4-r1b-tag-cleanup-verify.json`

## A. 独立运行命令

```bash
cd /workspace
git fetch origin main
git rev-parse --is-shallow-repository   # false
git ls-remote --tags origin
git ls-remote origin 'refs/tags/*' | grep -v refs/tags/milestone/ || true
git ls-remote origin refs/pull/42/head refs/pull/46/head refs/pull/33/head
# 六个已删 milestone/* 指向提交：
git merge-base --is-ancestor <pointed_commit> origin/main
```

复现 JSON：

```bash
/workspace/.venv/bin/python -c "import json; print(json.load(open('operations/reviews/diag/v4/v4-r1b-tag-cleanup-verify.json'))['decision_gate_all_checks_pass'])"
```

## B. origin 标签现状（`git ls-remote --tags origin`）

| ref | SHA |
| --- | --- |
| `refs/tags/milestone/phase1-archive` | `4812115867d0e9176175bd45d21b2dae19c10979` |
| `refs/tags/milestone/phase1-archive^{}` | `0dd93fa13e0aa79b09ef16ba80676c022004be02` |
| `refs/tags/milestone/v3-code-freeze` | `f1d3d0c170ecbd5eb3b463c26834bafd5dc40254` |
| `refs/tags/milestone/v3-code-freeze^{}` | `b1f84d899f4a37914c1ce4ef0ab16484f0ef7cdb` |
| `refs/tags/milestone/v3.1-prereg-freeze` | `e3b55a7b8ce967a43341a3c9d02e6a0a42e2b508` |
| `refs/tags/milestone/v3.1-prereg-freeze^{}` | `1040035ee1d707368b58687994894189753843ac` |

- 附注标签 **3** 个；无 `keep/*`；无其它 `refs/tags/*`。
- 与 Manager 删除后快照及 `docs/manual/milestones.md` 中三个「保留」行的 **标签对象 SHA** 一致，且与 `operations/work_logs/2026-10-28-tag-cleanup.md` 删除前记录一致（未移动）。

## C. 保留标签 SHA 对照

| 标签 | 标签对象 SHA（origin = milestones.md = 工作记录删除前） | 指向提交 SHA |
| --- | --- | --- |
| `milestone/phase1-archive` | `4812115867d0e9176175bd45d21b2dae19c10979` | `0dd93fa13e0aa79b09ef16ba80676c022004be02` |
| `milestone/v3-code-freeze` | `f1d3d0c170ecbd5eb3b463c26834bafd5dc40254` | `b1f84d899f4a37914c1ce4ef0ab16484f0ef7cdb` |
| `milestone/v3.1-prereg-freeze` | `e3b55a7b8ce967a43341a3c9d02e6a0a42e2b508` | `1040035ee1d707368b58687994894189753843ac` |

## D. 已删除 9 个标签（索引 + 可达性）

`docs/manual/milestones.md` 共 **12** 行；下列 9 行处置为「删除」，字段齐全（标签名、标签对象 SHA、指向提交、理由）。origin 上已不存在对应 ref。

| 标签 | 指向提交 | 可达性（Reviewer 独立） |
| --- | --- | --- |
| `milestone/v1-code-freeze` | `cb8fe7b09253208fba157195c2fefbf3eb76d2b3` | `origin/main` 祖先 ✓ |
| `milestone/v1-r2-stop` | `ed1501cf2ec2eed6a025f39786fb83f1e432b491` | `origin/main` 祖先 ✓ |
| `milestone/v2-prereg-freeze` | `1ad86ac0150138b7284cca7566d421e63bf39032` | `origin/main` 祖先 ✓ |
| `milestone/v2-oos-result` | `36e53ce0cc0a35c9d99d7461d01b6107b3ed1279` | `origin/main` 祖先 ✓ |
| `milestone/v3-prereg-freeze` | `bfeb49cc65eb0ba419bc98348f1d643fac1211f6` | `origin/main` 祖先 ✓ |
| `milestone/core-portfolio-live-config` | `745ecedca4bfef5f5af881182c1fbcb9c5a32cac` | `origin/main` 祖先 ✓ |
| `keep/cursor/owner-progress-boundary-audit` | `6cba1c77d4c9309df6a2b3375c8654cd1b6162fa` | = `refs/pull/42/head` ✓ |
| `keep/cursor/task-complete-owner-experience` | `cbc80ca069e26f6398cc2dc2df899228260963a6` | = `refs/pull/46/head` ✓ |
| `keep/cursor/v3.1-prereg-review-7a9f` | `fa825b7beccacda24004fdb52f48b3073fddf052` | = `refs/pull/33/head` ✓ |

## E. 文档与 D14-2 纪律（只读对照）

| 要求 | 状态 |
| --- | --- |
| `AGENTS.md`：不移动 tag；删除前先写 `milestones.md`；`phase1-archive` 永不删移；不再要求 `keep/*`；取数指向 `data-principles.md` | ✓（main @ d5d460a） |
| `docs/manual/roadmap-and-naming.md`：每版本最多 prereg/code 两个标签；每阶段一个 `phase<N>-archive`；不用 `keep/*` | ✓ |
| 未移动任何保留标签对象 SHA | ✓ |
| 仅删除 D14-2 列出的 9 个（非 `--force` 批量删除，见 Manager 工作记录） | ✓（远端状态与记录一致） |

## F. Blockers

无。

## G. Pull request

（本 Reviewer PR 合入后更新本节 URL。）
