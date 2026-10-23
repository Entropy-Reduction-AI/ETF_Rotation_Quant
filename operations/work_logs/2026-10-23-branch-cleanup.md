# 分支整理：只留 main，关键节点打标签

## Metadata

- Project: ETF_Rotation_Quant
- Task: 删除已合入的开发分支，给关键提交打附注标签
- Date: 2026-10-23
- Owner: project owner
- Route: direct-execute
- Source of truth: AGENTS.md「分支」；当前 main `745ecedca4bfef5f5af881182c1fbcb9c5a32cac`

## Goal / Summary

远端分支只留 `main`。五个里程碑用附注标签标在指定提交上。PR #1 的说明没有整段落在 main 的「Cursor Cloud specific instructions」里，因此没有关闭。

## 合入确认

删除前对每个远端分支执行 `git merge-base --is-ancestor origin/<branch> origin/main`。九个都是 main 的祖先，全部删除。

| 分支 | 提交 | 结果 |
| --- | --- | --- |
| `dev` | `2a80d8d233bb5dd66f4a10ba0c4e96e862610bce` | 已合入 |
| `cursor/execution-inventory` | `92364e9f9e537b9bc23f37e214ab259436dabe0a` | 已合入 |
| `cursor/grok-pit-20261022-2031` | `5fb583abd9803b2844cab2f17e092d910c0b4cb8` | 已合入 |
| `cursor/qdii-nav-dividends` | `fba18d280c7e246233554fbb12683b0d78d9223a` | 已合入 |
| `cursor/r4-fallback-engine` | `d58f95c63510da20efca788d4a5c993dcb7794bc` | 已合入 |
| `cursor/r4-no-valve` | `f4106d588b71e81629da2b7a177d1b3371b4a873` | 已合入 |
| `cursor/r4-production` | `c091c28ea5b497ca7e5510b597de2fc5919fe775` | 已合入 |
| `cursor/v2-oos-result` | `0178e24961bad77320567e68eaee2880112d9372` | 已合入 |
| `cursor/v2-timing-runner` | `2dc53032d198e6c138aa4ba7c7879d79674da4d7` | 已合入 |

删除命令：

```text
git push origin --delete dev cursor/execution-inventory cursor/grok-pit-20261022-2031 cursor/qdii-nav-dividends cursor/r4-fallback-engine cursor/r4-no-valve cursor/r4-production cursor/v2-oos-result cursor/v2-timing-runner
```

没有 force push。删除后 `git ls-remote --heads origin` 只剩 `refs/heads/main`，指向 `745ecedca4bfef5f5af881182c1fbcb9c5a32cac`。`cursor/python-venv-cloud-notes-1df1` 在删除前就已经不在远端。

## 标签

五个都是新建的附注标签。说明各一句。标签对象指向下面的提交。原先没有任何远端标签，没有移动或删除已有标签。

| 标签 | 指向的提交 | 说明 |
| --- | --- | --- |
| `milestone/v1-code-freeze` | `cb8fe7b09253208fba157195c2fefbf3eb76d2b3` | V1 预注册实现的代码冻结 |
| `milestone/v1-r2-stop` | `ed1501cf2ec2eed6a025f39786fb83f1e432b491` | V1 刻画分不开，STOP |
| `milestone/v2-prereg-freeze` | `1ad86ac0150138b7284cca7566d421e63bf39032` | v2 预注册冻结 |
| `milestone/v2-oos-result` | `36e53ce0cc0a35c9d99d7461d01b6107b3ed1279` | v2 样本外一次性运行的产物 |
| `milestone/core-portfolio-live-config` | `745ecedca4bfef5f5af881182c1fbcb9c5a32cac` | D7 之后的生产配置 |

## PR #1

PR #1（`cursor/python-venv-cloud-notes-1df1`，提交 `cac2734edf4907cd62bd7d44b8e7261ee501a7df`）仍是打开的。该提交不是 `origin/main` 的祖先。对照 main 的 `AGENTS.md`「Cursor Cloud specific instructions」之后，没有附评论，也没有关闭。

该节现在是这两句：

- 默认镜像要先安装 `python3.12-venv`，否则 `python3 -m venv` 因缺少 ensurepip 失败。随后在仓库根执行 `python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt`。
- 跑测试前执行 `mkdir -p outputs`（`outputs/` 被 gitignore）。测试：`.venv/bin/python -m unittest discover -s tests -t .`。

PR 里有、这一节里没有的内容：

| PR #1 的句子 | main 上的情况 |
| --- | --- |
| `sudo apt-get install -y python3.12-venv`，再 `python3 -m venv .venv` | 该节写了先安装 `python3.12-venv` 并在仓库根建 `.venv`，没有 apt 命令 |
| 当时还没有 `requirements.txt`，文件出现后再 `.venv/bin/python -m pip install -r requirements.txt` | 该节已经直接安装 `requirements.txt`。这个文件现在在 main 上 |
| 研究时区 `Asia/Shanghai`；版本化数据只有 `data/market.sqlite` 和 `data/universe.csv`；更新 sqlite 后记录 SHA256；`.venv/` 不入库 | 时区和 sqlite 的 SHA256 在「数据约束」，不在这一节。`AGENTS.md` 没有写 `universe.csv`，也没有写 `.venv/` 不入库。这两个事实分别在已跟踪的 `data/universe.csv` 和 `.gitignore` 里 |
| `src/` 与 `tests/` 随 R1 迁入，见 `docs/project-intake/etf-rotation-quant.md`；没有常驻服务 | 这一节有测试命令，没有 R1 迁入说明、intake 路径，也没有「没有常驻服务」 |

## Decision / Next Steps

分支和标签已按上面的结果推送。PR #1 保持打开，等 Owner 看完差异再决定是否关闭。本记录是 main 上在 `745eced` 之后的一个文档提交；`milestone/core-portfolio-live-config` 仍指向 `745eced`。
