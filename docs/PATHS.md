# 路径对照

## Metadata

- Project: ETF_Rotation_Quant
- Document type: index
- Status: active
- Owner: project owner
- Last updated: 2026-10-23
- Source of truth: `operations/work_logs/2026-10-23-repo-restructure.md`

## Purpose

2026-10-23 这次只改目录和名字。计算、参数和配置字段没有改。下面是旧路径到新路径的对照。历史记录里的旧路径以这张表为准，不回改那些记录。

## 删除

这些文件最后存在于提交 `b39f1807a839a8528242190003703eda723fc575`。

| 旧路径 | 现在 |
| --- | --- |
| `src/research/baseline.py` | 已删除 |
| `src/research/build_hfq.py` | 已删除 |
| `src/research/characterize_extra.py` | 已删除 |
| `src/research/dividend_sizing_controls.py` | 已删除 |
| `src/research/dividend_spread_check.py` | 已删除 |
| `src/research/enh_engine.py` | 已删除 |
| `src/research/is_mining.py` | 已删除 |
| `src/research/oos_run.py` | 已删除 |
| `src/research/ref_strong_check.py` | 已删除 |
| `src/research/universe_breadth.py` | 已删除 |
| `scripts/f2_t16_coverage.py` | 已删除 |
| `src/signals/__init__.py` | 已删除。包改到 `src/portfolio/` |
| `src/signals/__main__.py` | 已删除。命令改成 `python -m src.portfolio` |

`src/research/characterize.py` 保留。

## 生产代码

| 旧路径 | 新路径 |
| --- | --- |
| `src/signals/fallback.py` | 拆成 `src/portfolio/`。配置在 `config.py`，慢阀在 `valve.py`，设计期复现在 `replicate.py`，执行规则在 `execution.py`，目标在 `target.py`，命令行在 `__main__.py` |
| `config/r4_fallback.toml` | `config/portfolio.toml` |
| `results/r4/` | `results/portfolio/` |
| `tests/signals/` | `tests/portfolio/` |
| `src/rotation/etf_probe.py` | `tests/indicators/reference/etf_probe.py` |
| `python -m src.signals.fallback` | `python -m src.portfolio` |

## 文档

| 旧路径 | 新路径 |
| --- | --- |
| `docs/etf-rotation-prereg-v1.md` | `docs/prereg/etf-rotation-prereg-v1.md` |
| `docs/etf-timing-prereg-v2.md` | `docs/prereg/etf-timing-prereg-v2.md` |
| `docs/etf-dividend-enhancement-prereg.md` | `docs/prereg/etf-dividend-enhancement-prereg.md` |
| `docs/data-layer.md` | `docs/data/data-layer.md` |
| `docs/data-inventory.md` | `docs/data/data-inventory.md` |
| `docs/execution-inventory.md` | `docs/data/execution-inventory.md` |
| `docs/h00300-offline-restore.md` | `docs/data/h00300-offline-restore.md` |
| `docs/h00300-year-end-supplement.md` | `docs/data/h00300-year-end-supplement.md` |
| `docs/tencent-price-index-offline.md` | `docs/data/tencent-price-index-offline.md` |
| `docs/etf-characterization-z.md` | `docs/research/etf-characterization-z.md` |
| `docs/etf-l1-retrospective.md` | `docs/research/etf-l1-retrospective.md` |
| `docs/prereg-v1-implementation-notes.md` | `docs/research/prereg-v1-implementation-notes.md` |
| `docs/indicators-layer.md` | `docs/research/indicators-layer.md` |
| `docs/work_logs/2026-10-22-execution-inventory.md` | `operations/work_logs/2026-10-22-execution-inventory.md` |
| `docs/work_logs/2026-10-22-r4-fallback-engine.md` | `operations/work_logs/2026-10-22-r4-fallback-engine.md` |

`docs/manual/` 和 `docs/project-intake/` 没有移动。

## 诊断脚本里的仓库根

`operations/reviews/diag/` 里写死的 `/data/ETF_Rotation_Quant`，以及 `qdii/prem.py` 里的 `ETF_Rotation_Quant/data/market.sqlite`，改成由 `Path(__file__)` 推出仓库根。文件还在原处。`d6_grok_xcheck.py` 和 `qdii/fetch.py` 原来就没有这条绝对路径，没有改。
