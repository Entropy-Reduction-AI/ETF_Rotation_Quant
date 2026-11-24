# 分支归档与清理、补打 `milestone/phase2-archive`（2026-11-23）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: work_log
- Status: done (2026-11-23 Asia/Taipei)
- Owner: L. Loric
- Maintainer: Orchestrator（Claude）登记；Manager、Cloud Agent 执行
- Date: 2026-11-23（Asia/Taipei）
- 决定：`operations/planning/2026-11-23-d41-branch-tag-cleanup.md`（D41-1 至 D41-3）
- 授权：Owner 2026-11-23 在对话中明确要求，答复“1 删，2 同意，3A”

## 盘点（2026-11-23，`git fetch --prune` 之后）

远程分支 289 条（含 `main`），标签 9 个。

| 类别 | 条数 | 处置 |
| --- | ---: | --- |
| PR 已合入，分支尖端是 main 的祖先 | 27 | 删 |
| PR 已合入（squash / rebase），分支尖端等于合入时的 PR 尖端 | 245 | 删 |
| PR 已合入，之后分支又多了提交，那些提交已由后续 PR 整体合入 main | 3 | 删 |
| PR 已关闭，内容已被取代（#335、#336、#300） | 3 | 删 |
| 没有 PR，补丁都已在 main | 1 | 删 |
| 开着但过时的 PR（#145、#165、#338） | 3 | 关闭 PR 后删 |
| 开着、在用的 PR（#312、#339、#346、#347、#348、#349，以及 #350） | 7 | 保留 |

逐条清单（分支名、原指向提交、最后提交日期、理由）：`operations/work_logs/2026-11-23-branch-cleanup-list.csv`，共 282 条。

“合入后又多了提交”的 3 条，逐个核对过多出来的提交都已在 main：

| 分支 | 多出的提交 | 在 main 上的位置 |
| --- | --- | --- |
| `claude/d38-r46` | 预测表 3.12–3.14 版、D40-10 | `f7fceae2`（D38 第 48 行与 D40-10；预测表 3.12–3.14 版） |
| `claude/d38-us-share` | 预测表 3.3–3.7 版 | `43f09a99`（预测表 3.3–3.7 版） |
| `cursor/v51-wrapup-9753` | `5bae8c33` 测试改动 | `tests/v51/test_params.py` 已被 `9e3a0ba6` 覆盖得更全 |

## 执行方法

删除前逐条核对远程分支当前指向与清单一致：

```bash
tail -n +2 operations/work_logs/2026-11-23-branch-cleanup-list.csv | while IFS=, read -r b sha d why; do
  cur=$(git ls-remote origin "refs/heads/$b" | cut -f1)
  if [ "$cur" = "$sha" ]; then git push origin --delete "$b" && echo "deleted $b $sha"; else echo "SKIP $b listed=$sha now=${cur:-gone}"; fi
done
```

## 新标签

| 标签 | 指向提交 | 附注 |
| --- | --- | --- |
| `milestone/phase2-archive` | `8875fe576496e9dacfb0681ac93df4f42cd894ca`（PR #294 合入后的 main） | `phase 2 archive (D36: v3→v5.1 closed as not established; D35 listed-only recalc, turnover deep-dive, D37 diagnostics done; last main before v6 preflight D38 #295)` |

既有 9 个标签不移动、不删除、不改写。

## 执行结果

脚本退出码 0。

删除 282 条分支。清单上的每一条，都是在远程当时的尖端与清单里的 SHA 一致之后才删除。删除顺序与 CSV 顺序一致。最后删除的是 `cursor/v6-prereg-r1-reviews-745d`，指向 `53a03cc2ed1fc2e6fa0cff111e9acf8bd9e250cd`（CSV 最后一行）。

SKIP：0。没有跳过的分支，因此没有 SKIP 原因。

282 行清单之外的分支都没有删除。

脚本之后 `git ls-remote --heads origin` 的剩余分支（原样，9 行）：

```
0bff3eda70c64d62944940a4cd94ea702cd95adb	refs/heads/claude/d38-r45-r56
16770fa70dd46b2d6a91a20affadcac251479a05	refs/heads/claude/d41-cleanup
b08f0e49a6743cd0ce4592213bfdfa6c6cb622e0	refs/heads/claude/data-board-1123
bd62984d988299a9607f0b35643ead999a424b0d	refs/heads/claude/owner-board-v6
462d1d32e2695708cc0c79f1fd814d6148dde4be	refs/heads/claude/owner-page-ledger-score
2a452ae55a69e524dcca2bf6e72096e145777fef	refs/heads/claude/v6-prereg-r1
50f52a9db748a640df29f9a4da89ebfff1a68df0	refs/heads/claude/v6-prereg-r1-review-files
332b88fdb1b1b4272edb154754c3bf2925b5889d	refs/heads/grok/d37-r6-partial
89f030d5bba53c9fae3194cae807d3ae4e1459ef	refs/heads/main
```

`claude/d41-cleanup` 与 `claude/v6-prereg-r1-review-files` 是 282 行盘点之后新建的，不在清单上，已正确保留。仍开着的 PR 分支：#312 `grok/d37-r6-partial`，#339 `claude/v6-prereg-r1`，#346 `claude/d38-r45-r56`，#347 `claude/owner-page-ledger-score`，#348 `claude/data-board-1123`，#349 `claude/owner-board-v6`。

脚本之后 `git ls-remote --tags origin` 的全部标签与对象 SHA，与清理前快照相同（原样，20 行；`^{}` 与 ref 在同一行）：

```
4812115867d0e9176175bd45d21b2dae19c10979	refs/tags/milestone/phase1-archive
0dd93fa13e0aa79b09ef16ba80676c022004be02	refs/tags/milestone/phase1-archive^{}
48b63a84274b9d8349049630971095f82c9da7b9	refs/tags/milestone/phase2-archive
8875fe576496e9dacfb0681ac93df4f42cd894ca	refs/tags/milestone/phase2-archive^{}
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

这一步清理没有移动、删除或改写任何标签。`milestone/phase2-archive` 在清理前已经存在（附注标签对象 `48b63a84274b9d8349049630971095f82c9da7b9`，剥开后指向 `8875fe576496e9dacfb0681ac93df4f42cd894ca`）。

### 尾清理（2026-11-24 10:59:50–11:00:02 Asia/Taipei）

Owner 2026-11-24 授权。只删除下面四条已经合并的远程分支。每条在删除前立刻 `git ls-remote`；远程尖端等于授权 SHA，关联 PR 为 MERGED，且 PR head ref、head SHA 与该授权 SHA 一致，才删除。不一致或引用不在则 SKIP。比较并交换被拒则 SKIP，不换 SHA 重试。

```bash
git push --porcelain -v origin --force-with-lease=refs/heads/<branch>:<expected-sha> :refs/heads/<branch>
```

| 分支 | PR | 授权 SHA | 删除前观察到的 SHA | 结果 |
| --- | --- | --- | --- | --- |
| `claude/d41-cleanup` | #351 MERGED，merge `403ac7afe97ecd823737c0ea5016dd218de25b29` | `16770fa70dd46b2d6a91a20affadcac251479a05` | `16770fa70dd46b2d6a91a20affadcac251479a05` | 已删除 |
| `claude/v6-prereg-r1-review-files` | #350 MERGED，merge `89f030d5bba53c9fae3194cae807d3ae4e1459ef` | `50f52a9db748a640df29f9a4da89ebfff1a68df0` | `50f52a9db748a640df29f9a4da89ebfff1a68df0` | 已删除 |
| `cursor/d41-phase2-archive-register-60e1` | #352 MERGED，head 即该 SHA，merge `707237fc40651f35570dd8786433e24cca662ea9` | `ddfee847218bc8ce100c0c8fbd54669182557192` | `ddfee847218bc8ce100c0c8fbd54669182557192` | 已删除 |
| `cursor/d41-pr352-reviews-1e59` | #353 MERGED，head 即该 SHA，merge `981f466d7acd10211d1aea9e9e3399a7bbc7d0a0` | `f88fccc3883e9cb58281b1d7f7bbeba1b3ff800b` | `f88fccc3883e9cb58281b1d7f7bbeba1b3ff800b` | 已删除 |

合计：删除 4，SKIP 0。四条删除后的 `git ls-remote` 输出都为空。

heads 前后差异只有这四条。同期仍在的分支尖端未变：`claude/d38-r45-r56` `0bff3eda70c64d62944940a4cd94ea702cd95adb`，`claude/v6-prereg-r1` `2a452ae55a69e524dcca2bf6e72096e145777fef`，`grok/d37-r6-partial` `332b88fdb1b1b4272edb154754c3bf2925b5889d`，`claude/owner-page-ledger-score` `462d1d32e2695708cc0c79f1fd814d6148dde4be`，`claude/data-board-1123` `b08f0e49a6743cd0ce4592213bfdfa6c6cb622e0`，`claude/owner-board-v6` `bd62984d988299a9607f0b35643ead999a424b0d`。

标签对象：删除前与删除后 `git ls-remote --tags origin` 经 `LC_ALL=C sort` 后逐字节相同，SHA256 都是 `5c4056ceb6d33fc95475467c38feb199ca02a657919d2a84cb150f665acc8feb`，各 20 行。这一步没有移动、删除或改写任何标签。

`main` 只读。删除前与删除后远程 `refs/heads/main` 都是 `67e249d4e50c4783f59c1deef246bf246be5e8e4`。本次没有推送 `main`。
