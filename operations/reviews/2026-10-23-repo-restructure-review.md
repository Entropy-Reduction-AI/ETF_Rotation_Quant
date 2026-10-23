# 评审：任务 2 代码与目录整理（`cursor/repo-restructure` 5793b60）

## Metadata
- Project: ETF_Rotation_Quant · 评审: orchestrator · 日期: 2026-10-23
- 对象: `cursor/repo-restructure` 5793b60（基线 main b39f180）
- 结论: **通过（附 1 处修补，已由 orchestrator 推到本分支）**，按 D6 `--ff-only` 合入

## 独立复核（orchestrator 在两个独立工作目录各跑一次）
| 检查 | 结果 |
|---|---|
| `replicate --end 2015-12-31` JSON：main（`src.signals`）vs 分支（`src.portfolio`） | 逐字节相同；与分支内 `results/portfolio/replicate.json` 相同 |
| `target --date 2026-09-30 --equity 1000000 --nav-source eastmoney_f10_lsjz` JSON | 逐字节相同；与 main 的 `results/r4/…`、分支的 `results/portfolio/…` 已提交文件均相同 |
| `src.research.prereg_v2.run --end 2015-12-31` 设计期摘要 | 去掉 `generated_at`、`code_sha` 后相同 |
| `data/market.sqlite` SHA256 | `3b9f8fb2…155f9`，未变 |
| 全量测试 | Ran 344，OK |
| 三份预注册 | R100 纯移动，正文未改 |
| `docs/PATHS.md` | 删除、移动、命令改名均有对照 |

## 发现
1. **（已修）`scripts/data_inventory.py` 仍写到旧路径** `docs/data-inventory.md`。再生成清单会在旧位置新建文件。已改 `OUT_PATH` 为 `docs/data/data-inventory.md`，同步改了 docstring 和生成文本里的 `docs/data/data-layer.md`，`docs/data/data-inventory.md` 对应一行同改。
2. （不阻塞）README.md 第 14 行链接指向旧路径。README 将整体重写，届时一并处理。
3. （不阻塞）若干 docstring、历史文档的 Source of truth 仍写旧路径（纯文本，非链接）。按 PATHS.md「历史记录不回改」处理，不改。

## 动作
- 本分支在修补提交之后按 D6 `git merge --ff-only` 合入 main。
