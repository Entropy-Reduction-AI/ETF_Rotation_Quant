# 代码与目录整理

## Metadata

- Project: ETF_Rotation_Quant
- Task: 只改结构，不改行为
- Date: 2026-10-23
- Owner: project owner
- Route: direct-execute
- Source of truth: 本任务说明；对照表 `docs/PATHS.md`

## Goal / Summary

从 main 整理目录和名字。计算、参数、配置字段和预注册正文都没有改。本分支不合入 main，等评审后按 D6 `--ff-only` 合入。

## 目录树（两层）

```text
src/data/  src/indicators/  src/portfolio/  src/research/
tests/data/  tests/indicators/  tests/portfolio/  tests/research/
config/  scripts/
docs/data/  docs/manual/  docs/prereg/  docs/project-intake/  docs/research/
results/inventory/  results/portfolio/  results/prereg_v1/  results/v2/
operations/planning/  operations/reviews/  operations/work_logs/
data/  incoming/
```

`src/portfolio/` 里是 `config.py`、`valve.py`、`replicate.py`、`execution.py`、`target.py`、`__main__.py`。`tests/indicators/reference/etf_probe.py` 是原来的探针。

## 删除和 grep

删除前对 `HEAD` 的 `src`、`tests`、`scripts` 做了 `git grep`。没有别的模块 import 这些文件。互相引用只发生在即将一起删除的脚本里：`dividend_sizing_controls.py`、`is_mining.py`、`oos_run.py` 引用 `enh_engine`。`src/indicators/build.py` 的注释提到 `build_hfq.py`，不是 import。`tests/research/test_prereg_v1.py` 的方法名 `test_oos_runs_only_once_and_steps_in_order` 含有 `oos_run` 这几个字母，测的是 `prereg_v1`，不是 `src/research/oos_run.py`。`characterize_extra.py`、`dividend_spread_check.py`、`ref_strong_check.py`、`universe_breadth.py` 在这三处目录里没有别的命中。

`src/research/characterize.py` 按任务保留。

| 删除 | grep |
| --- | --- |
| `src/research/baseline.py` | 只命中自己写的 `baseline_card.md` |
| `src/research/build_hfq.py` | 只在 `src/indicators/build.py` 的注释里出现 |
| `src/research/characterize_extra.py` | 无其他命中 |
| `src/research/dividend_sizing_controls.py` | 只引用同批删除的 `enh_engine` |
| `src/research/dividend_spread_check.py` | 无其他命中 |
| `src/research/enh_engine.py` | 只被同批删除的三个脚本引用 |
| `src/research/is_mining.py` | 只引用 `enh_engine` |
| `src/research/oos_run.py` | 只引用 `enh_engine`；测试方法名不是这个文件 |
| `src/research/ref_strong_check.py` | 无其他命中 |
| `src/research/universe_breadth.py` | 无其他命中 |
| `scripts/f2_t16_coverage.py` | 只命中自己的字段名 |

这些文件最后存在于 `b39f1807a839a8528242190003703eda723fc575`。

## 移动

一对一的移动用 `git mv`。`src/signals/fallback.py` 先 `git mv` 到 `src/portfolio/`，再按函数拆开。函数名、算法、默认值和配置字段没改。预注册三份文件只移动，`git show HEAD:docs/<文件>` 与新路径逐字节相同。

诊断脚本里的 `/data/ETF_Rotation_Quant` 改成 `Path(__file__).resolve().parents[3]`（`qdii/prem.py` 是 `parents[4]`）。传给 `read_table` 的仍是字符串。

## 逐字节对比

整理前用 `745eced` 跑，整理后用本分支跑。面板是 `outputs/panel-2026-09-30.sqlite`，库是 `data/market.sqlite`。

| 命令 | 结果 |
| --- | --- |
| `replicate --end 2015-12-31` 写出的 JSON | 逐字节相同 |
| `target --date 2026-09-30 --equity 1000000` 写出的 JSON | 逐字节相同 |
| `src.research.prereg_v2.run --end 2015-12-31` 的设计期摘要 | 去掉 `generated_at` 和 `code_sha` 之后相同 |
| `data/market.sqlite` SHA256 | `3b9f8fb253a29de5835aa54c0b8062bbaa77ebf3f229611eb91b97a9ece155f9` |

没有写 `results/v2/`，没有跑样本外。

## 测试和断链

`mkdir -p outputs && python3 -m unittest discover -s tests -t .`：Ran 344 tests in 92.435s，OK，0 失败。整理前 main 上最近一次全量也是 344。没有删测试，也没有加测试。删掉的脚本原来就没有测试，所以数量不变。

`docs/` 里 6 条相对链接，0 条断链。`docs/data/` 内部的链接跟着一起搬了，仍然有效。`docs/research/indicators-layer.md` 里指向恢复说明的链接改成 `../data/h00300-offline-restore.md`。原来有两条链接的目标不在仓库里：`operations/work_logs/2026-10-04-h00300-server-restore.md` 和 `runnable-ledger.md`。这两处改成了纯文本，不再是链接。

## Decision / Next Steps

分支 `cursor/repo-restructure` 待评审。通过后按 D6 `git merge --ff-only` 合入 main。
