# v5 预注册冻结标签

## Metadata

- Project: ETF_Rotation_Quant
- Task: 登记 `milestone/v5-prereg-freeze`
- Date: 2026-11-01
- Owner: L. Loric
- Route: direct-execute
- Source of truth: Owner 指令（PR #156 合入与 #157 签收之后打标签）；`docs/manual/milestones.md`；`docs/manual/roadmap-and-naming.md`

## 目标

在 #157 squash-merge 之后的 `main` 上新建一个附注标签，并把它写入里程碑索引。不移动、不删除、不改写任何既有标签。不改写 `main`。

## 改动面

- origin 上新建附注标签 `milestone/v5-prereg-freeze`（只推送 `refs/tags/milestone/v5-prereg-freeze`，没有 `--force`，没有 `--tags`）。
- `docs/manual/milestones.md`：文末追加这一条登记，并更新 Last updated。十二个标签那张表、清理后三标签表，以及 v4 各表的处置列不改。
- 本工作记录。
- 没有改 `src/`，没有写 `results/`，没有 `LOCK`，没有跑设计期或 2016 及以后的收益。

## 验证

打标签前 `origin/main` 为 `f2ab4f527b3081b0b73ebc860f3aedd8ee54523e`。`milestone/v5-prereg-freeze` 在 origin 上不存在。该提交是 PR #157 的 squash-merge；其父历史含 PR #156 rebase-merge（D29 提交 `aad13a60b1c6bd7aa7e19548da234d62094a0b82`）。预注册正文写明中国数据的设计期运行只允许 end ≤ 2015-12-31。`git ls-tree` 没有 `results/v5/LOCK`。`results/v5/inventory/classes-draft.csv` 为 117 行；六条原 `manual_rule` 已定类，标普全球石油指数归美股。

标签对象：

```text
40aac3ced0f1f7e710403cd49076a0fb4a91c51c	refs/tags/milestone/v5-prereg-freeze
f2ab4f527b3081b0b73ebc860f3aedd8ee54523e	refs/tags/milestone/v5-prereg-freeze^{}
```

附注说明为 `v5 prereg freeze (D29 Owner four choices; #156 classes-draft signed #157; design-period ≤2015-12-31; no LOCK; no 2016+)`。对象类型是 `tag`。`^{}` 等于指定提交。标签日期 2026-11-01 14:41:25 +0800。

推送后 `git ls-remote --tags origin` 里的 `milestone/*` 为：

```text
4812115867d0e9176175bd45d21b2dae19c10979	refs/tags/milestone/phase1-archive
0dd93fa13e0aa79b09ef16ba80676c022004be02	refs/tags/milestone/phase1-archive^{}
f1d3d0c170ecbd5eb3b463c26834bafd5dc40254	refs/tags/milestone/v3-code-freeze
b1f84d899f4a37914c1ce4ef0ab16484f0ef7cdb	refs/tags/milestone/v3-code-freeze^{}
e3b55a7b8ce967a43341a3c9d02e6a0a42e2b508	refs/tags/milestone/v3.1-prereg-freeze
1040035ee1d707368b58687994894189753843ac	refs/tags/milestone/v3.1-prereg-freeze^{}
4ce2f2919b7c1bcf12dcd1bdd3eee77ae964a603	refs/tags/milestone/v4-code-freeze
476abd7cb63395506c6a9bb5fdad0f7b16827f66	refs/tags/milestone/v4-code-freeze^{}
aa72a148b8a598fa2cf9b488dcb21e5a9943d6c5	refs/tags/milestone/v4-code-freeze-2
c9f4e44c94c54922b6927b6f4d4902edf79e5dd8	refs/tags/milestone/v4-code-freeze-2^{}
830320d03712df3a4098f352be8932e0553b5eeb	refs/tags/milestone/v4-prereg-freeze
6bcba53e36e74ec81dd21fb7ee7b8cea695038fb	refs/tags/milestone/v4-prereg-freeze^{}
40aac3ced0f1f7e710403cd49076a0fb4a91c51c	refs/tags/milestone/v5-prereg-freeze
f2ab4f527b3081b0b73ebc860f3aedd8ee54523e	refs/tags/milestone/v5-prereg-freeze^{}
```

与打标签前相比，只多出 `milestone/v5-prereg-freeze` 及其 `^{}`。六个既有 `milestone/*` 的对象 SHA 与清理后索引及此后各次登记一致，没有移动。

## 完成判据

标签已在 origin 上，指向 `f2ab4f527b3081b0b73ebc860f3aedd8ee54523e`。索引登记的是标签对象 SHA `40aac3ced0f1f7e710403cd49076a0fb4a91c51c`，处置为保留。本索引的合入不在本次执行里。
