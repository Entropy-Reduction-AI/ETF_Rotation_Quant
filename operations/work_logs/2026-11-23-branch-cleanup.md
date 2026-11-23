# 分支归档与清理、补打 `milestone/phase2-archive`（2026-11-23）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: work_log
- Status: pending（清单已登记，待执行；执行后由 Manager 补“执行结果”一节）
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
| `milestone/phase2-archive` | `8875fe57e`（PR #294 合入后的 main） | `phase 2 archive (D36: v3→v5.1 closed as not established; D35 listed-only recalc, turnover deep-dive, D37 diagnostics done; last main before v6 preflight D38 #295)` |

既有 9 个标签不移动、不删除、不改写。

## 执行结果

（待 Manager 补：删除条数、跳过的分支及原因、`git ls-remote --heads origin` 剩余分支、`git ls-remote --tags origin` 全部标签与对象 SHA。）
