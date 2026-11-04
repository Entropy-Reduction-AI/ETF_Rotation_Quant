# v5 代码冻结标签

## Metadata

- Project: ETF_Rotation_Quant
- Task: 登记 `milestone/v5-code-freeze`
- Date: 2026-11-04
- Owner: L. Loric
- Route: direct-execute
- Source of truth: Owner 指令（D34-2：#251 与 #252 rebase-merge 之后打标签）；`docs/manual/milestones.md`；`docs/manual/roadmap-and-naming.md`

## 目标

在 #252 rebase-merge 之后的 `main` 上新建一个附注标签，并把它写入里程碑索引。不移动、不删除、不改写任何既有标签。不改写 `main`。

## 改动面

- origin 上新建附注标签 `milestone/v5-code-freeze`（只推送 `refs/tags/milestone/v5-code-freeze`，没有 `--force`，没有 `--tags`）。
- `docs/manual/milestones.md`：文末追加这一条登记，并更新 Last updated。十二个标签那张表、清理后三标签表，以及 v4 / v5 / v5.1 各表的处置列不改。
- 本工作记录。
- 没有改 `src/`，没有写 `results/`，没有 `LOCK`，没有跑设计期或 2016 及以后的收益。

## 验证

打标签前 `origin/main` 为 `8970bcbc7986c9a67d9ca535ca58a8855c910495`。`milestone/v5-code-freeze` 在 origin 上不存在。该提交是 PR #252 的 rebase-merge（Reviewer 对 D34-1 换手「合计」双计修复 `approve`）。其父提交是 `6df9b9b4a8470d18117807484cb5328f72d1bc24`（PR #251 rebase-merge：合计只加一次来源）。该提交历史上含 wrap 签收 `5a4678127bedea72c88b503de4e4f496d83f6899`（Dev #241）与 SF1 账本测试签收 `753d34ab3dfef7f7ab12010218effa22ce3b3fd2`（Dev #243）。预注册 v5 与 v5.1 都写明中国数据只允许 end ≤ 2015-12-31。`results/v5.1/design/gate.csv` 的入围名单是 B0。`git ls-tree` 没有 `results/v5/LOCK`，也没有 `results/v5.1/LOCK`。

标签对象：

```text
0aeae744177074c84bce68206021c21c6963341a	refs/tags/milestone/v5-code-freeze
8970bcbc7986c9a67d9ca535ca58a8855c910495	refs/tags/milestone/v5-code-freeze^{}
```

附注说明为 `v5 code freeze (D34-1 turnover total signed #251+#252; wrap+SF1 on main; gate B0; design-period ≤2015-12-31; no results/v5/LOCK; no 2016+)`。对象类型是 `tag`。`^{}` 等于指定提交。标签日期 2026-11-04 21:47:58 +0800。

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
0aeae744177074c84bce68206021c21c6963341a	refs/tags/milestone/v5-code-freeze
8970bcbc7986c9a67d9ca535ca58a8855c910495	refs/tags/milestone/v5-code-freeze^{}
40aac3ced0f1f7e710403cd49076a0fb4a91c51c	refs/tags/milestone/v5-prereg-freeze
f2ab4f527b3081b0b73ebc860f3aedd8ee54523e	refs/tags/milestone/v5-prereg-freeze^{}
87a57809bac36f1f2feec4b79e52656be456a35b	refs/tags/milestone/v5.1-prereg-freeze
1174e475ecb62995eb420f700bd1771b52e34295	refs/tags/milestone/v5.1-prereg-freeze^{}
```

与打标签前相比，只多出 `milestone/v5-code-freeze` 及其 `^{}`。八个既有 `milestone/*` 的对象 SHA 与清理后索引及此后各次登记一致，没有移动。

## 完成判据

标签已在 origin 上，指向 `8970bcbc7986c9a67d9ca535ca58a8855c910495`。索引登记的是标签对象 SHA `0aeae744177074c84bce68206021c21c6963341a`，处置为保留。本索引的合入不在本次执行里。
