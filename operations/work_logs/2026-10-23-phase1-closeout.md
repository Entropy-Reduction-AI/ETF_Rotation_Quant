# 第一阶段收尾合入

## Metadata

- Project: ETF_Rotation_Quant
- Task: 第一阶段收尾合入
- Date: 2026-10-23
- Owner: project owner
- Route: direct-execute
- Source of truth: 任务 I；合入前 `origin/main` 为 `530508b5edff98a7e542672ced91447f5ae7938f`

## Goal / Summary

把 `cursor/readme-evidence` 快进合入 main，补上重新生成的图，打附注标签 `milestone/phase1-closeout`，删掉远端开发分支。操作时刻 2026-10-24 00:27 Asia/Taipei。没有 force push，没有移动或删除已有标签。

## 合入

`origin/cursor/readme-evidence` 在重出图之前是 `8ade37a5bc84b857911ace6968d44044d98e96fe`。`530508b` 是它的祖先。

在该分支上运行 `python -m src.report evidence`。`results/report/` 的 csv 和 json 与 `8ade37a` 逐字节相同。`git diff --stat 8ade37a` 只有 `docs/assets/nav-vs-benchmark.png` 和新增的 `docs/assets/oos-vs-benchmark.png`。`docs/assets/data-timeline.png` 重写后字节不变，没有进入这次提交。

图的提交是 `3aa61a7739092ce02224c6ceae6fe1744c6a1d11`，message 为 `assets: regenerate charts`。随后在 main 上 `git merge --ff-only origin/cursor/readme-evidence`，并推送。main 的这个头包含 `8ade37a` 和上述 PNG 提交。

远端分支 `cursor/readme-evidence` 已删除。`git ls-remote --heads origin` 只剩 `refs/heads/main`。

## 标签

附注标签 `milestone/phase1-closeout` 打在合入后的 main 头上。

| 项 | SHA |
| --- | --- |
| 标签指向的提交（合入后的 main） | `3aa61a7739092ce02224c6ceae6fe1744c6a1d11` |
| 标签对象 | `b785a886ed144f0e0551e63541bfb9d278f1fbf3` |

说明：第一阶段收尾：现行配置 + 基准证据包 + README。已有五个 milestone 标签的对象 SHA 没有变。本记录是标签之后的下一次提交，所以读这份日志时 main 会比标签指向的提交多这一笔。

## Validation

- `mkdir -p outputs && python3 -m unittest discover -s tests -t .`：351 项，0 失败。
- README 相对链接检查 28 条，断链 0。其中包括 `docs/assets/oos-vs-benchmark.png`。三张图都是 1600×900。
