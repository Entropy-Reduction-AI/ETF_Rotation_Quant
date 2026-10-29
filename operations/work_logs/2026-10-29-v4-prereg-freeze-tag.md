# v4 预注册冻结标签（D23-1）

## Metadata

- Project: ETF_Rotation_Quant
- Task: D23-1 登记 `milestone/v4-prereg-freeze`
- Date: 2026-10-29
- Owner: L. Loric
- Route: direct-execute
- Source of truth: Owner D23 kick；`docs/manual/milestones.md`；`docs/manual/roadmap-and-naming.md`

## 目标

在合入 PR #118 后的 `main` 上新建一个附注标签，并把它写入里程碑索引。不移动、不删除、不改写任何既有标签。不改写 `main`。

## 改动面

- origin 上新建附注标签 `milestone/v4-prereg-freeze`（普通推送，没有 `--force`）。
- `docs/manual/milestones.md`：文末追加清理之后的登记。十二个标签那张表和三个保留标签的对象 SHA 不改。
- 本工作记录。
- 没有改 `src/`，没有写 `results/`，没有 `LOCK`，没有跑 2016 及以后的收益。

## 验证

打标签前 `origin/main` 为 `6bcba53e36e74ec81dd21fb7ee7b8cea695038fb`。`milestone/v4-prereg-freeze` 在 origin 上不存在。

标签对象：

```text
830320d03712df3a4098f352be8932e0553b5eeb	refs/tags/milestone/v4-prereg-freeze
6bcba53e36e74ec81dd21fb7ee7b8cea695038fb	refs/tags/milestone/v4-prereg-freeze^{}
```

附注说明为 `D23-1 Owner 批准 v4 预注册第 2.3 版`。`^{}` 等于指定提交。

推送后 `git ls-remote --tags origin` 里四个 `milestone/*` 为：

```text
4812115867d0e9176175bd45d21b2dae19c10979	refs/tags/milestone/phase1-archive
0dd93fa13e0aa79b09ef16ba80676c022004be02	refs/tags/milestone/phase1-archive^{}
f1d3d0c170ecbd5eb3b463c26834bafd5dc40254	refs/tags/milestone/v3-code-freeze
b1f84d899f4a37914c1ce4ef0ab16484f0ef7cdb	refs/tags/milestone/v3-code-freeze^{}
e3b55a7b8ce967a43341a3c9d02e6a0a42e2b508	refs/tags/milestone/v3.1-prereg-freeze
1040035ee1d707368b58687994894189753843ac	refs/tags/milestone/v3.1-prereg-freeze^{}
830320d03712df3a4098f352be8932e0553b5eeb	refs/tags/milestone/v4-prereg-freeze
6bcba53e36e74ec81dd21fb7ee7b8cea695038fb	refs/tags/milestone/v4-prereg-freeze^{}
```

三个保留标签的对象 SHA 与清理后索引一致，没有移动。

## 完成判据

标签已在 origin 上，指向 `6bcba53e36e74ec81dd21fb7ee7b8cea695038fb`。索引登记的是标签对象 SHA `830320d03712df3a4098f352be8932e0553b5eeb`，处置为保留。合入由 Manager rebase-merge。
