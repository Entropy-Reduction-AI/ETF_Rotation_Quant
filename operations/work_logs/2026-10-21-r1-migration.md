# R1 迁移

## Metadata

- Project: ETF_Rotation_Quant
- Task: R1 搭建
- Date: 2026-10-21
- Owner: project owner
- Route: direct-execute
- Source of truth: 本任务说明与 `docs/project-intake/etf-rotation-quant.md`

## Goal / Summary

从 `lwx0218/ETF_Opportunity_Ledger` 提交 `fa70cb709738dad3ebf426a71959943abe88fd0e` 迁入研究代码、数据、测试和 9 份文档。取文件用 `git archive`，没有从源仓库工作区复制，也没有向源仓库推送。目标仓库只提交到 `dev`。

代码提交 `db5fe4c7c881d027458928d4065eca43504ba7e3`。数据清单提交 `689340b100c2b8d23f300bc0f8ae1917aae99f88`。

## Scope / Changes

### 复制的路径

`src/__init__.py` 在 fa70cb7 不存在，没有新建。

- `data/market.sqlite`
- `data/universe.csv`
- `src/data/`（`__init__.py`、`__main__.py`、`date_constraints.py`、`db.py`、`dividends.py`、`http.py`、`offline_restore.py`、`offline_supplement.py`、`quality.py`、`runner.py`、`sources.py`、`store.py`、`tencent_offline.py`、`universe.py`）
- `src/indicators/`（`__init__.py`、`__main__.py`、`build.py`、`calendar.py`、`metrics.py`、`states.py`）
- `src/research/`（`baseline.py`、`build_hfq.py`、`characterize.py`、`characterize_extra.py`、`dividend_sizing_controls.py`、`dividend_spread_check.py`、`enh_engine.py`、`is_mining.py`、`oos_run.py`、`ref_strong_check.py`、`universe_breadth.py`、`prereg_v1/` 下 `__init__.py`、`characterize.py`、`config.py`、`engine.py`、`metrics.py`、`panel.py`、`run.py`、`signals.py`）
- `tests/__init__.py`、`tests/marketdb.py`
- `tests/data/`（`__init__.py`、`fakenet.py`、`fixtures/` 下 README 与 7 个夹具、9 个 `test_*.py`）
- `tests/indicators/`（`__init__.py`、`test_indicators.py`）
- `tests/research/`（`__init__.py`、`test_prereg_v1.py`、`fixtures/p6e1_nav.csv`、`fixtures/p6e1_skipped.csv`、`fixtures/p6e1_trades.csv`）
- `docs/etf-rotation-prereg-v1.md`
- `docs/etf-dividend-enhancement-prereg.md`
- `docs/etf-characterization-z.md`
- `docs/etf-l1-retrospective.md`
- `docs/data-layer.md`
- `docs/indicators-layer.md`
- `docs/h00300-offline-restore.md`
- `docs/h00300-year-end-supplement.md`
- `docs/tencent-price-index-offline.md`
- `requirements.txt`（见下）
- `src/rotation/etf_probe.py`（见下，其余 rotation 文件没有迁）

除三处改动外，上述文件与 fa70cb7 的 blob 逐字节一致。三处是 `requirements.txt`、`tests/data/test_lock_timeout.py`、`tests/data/test_runner.py`。

### requirements.txt

保留版本说明两行和 `pandas>=3.0,<4`、`numpy>=2.0,<3`。删掉 akshare 的两行注释，因为只有 `src/rotation/etf_probe.py` 使用它，测试加载该文件时会注入伪模块。

### 步骤 2 的删改

没有删测试方法。fa70cb7 基线是 data 192、indicators 40、research 44。删改前后方法数都是这个数，差为 0。

- `tests/data/test_lock_timeout.py`：删掉 `from src.ledger.store import Ledger`，以及文件末尾创建 `Ledger`、检查其 `busy_timeout` 和 `journal_mode` 的那段。market 库的 `busy_timeout` 和读锁等待断言保留。文件还测得了 market 库，所以没有整文件删除。
- `tests/data/test_runner.py` 的 `test_default_db_refused_in_tests`：删掉 `from src.ledger.store import DEFAULT_DB, Ledger, LedgerError`，删掉 `Ledger(DEFAULT_DB)` 的 `assertRaises` 块，并从 `existed` 去掉 `data/ledger.sqlite`。`DB.connect`、`runner.probe`、`runner.package`、`load_trading_days` 的拒绝断言保留。

删完后 `src/`、`tests/` 下没有 `src.ledger`、`src.jobs`、`src.web`、`src.home`、`src.observation`、`src.rotation`、`src.scoring` 的匹配。

### etf_probe.py

排除清单不迁 `src/rotation`。指标测试 `legacy_probe()` 按路径加载 `src/rotation/etf_probe.py` 来对照 `kell_states`。不放这个文件时，全量测试 276 个里有 2 个错误：`StatePort.test_identical_to_kell_states` 和 `LegacyCheck.test_against_analyze_py_format`。因此只从 fa70cb7 原样放入这一个文件。`analyze.py`、`analyze2.py`、`gen_panel.py`、`signals.py`、`signals_r_breakdown.py` 没有迁。

### 数据清单与 README

`scripts/data_inventory.py` 读库和 CSV，覆写 `docs/data-inventory.md`。命令：`.venv/bin/python scripts/data_inventory.py`。README 状态改为「R1 已迁移，待 R2」，并加上该清单入口。

没有跑 prereg_v1 的 characterize / design / oos / rolling 作业，没有对真实库做回测。仓库里没有 `OOS_LOCK.json`。测试在临时目录里写过锁文件，路径在 `/tmp`。

## Validation

环境按 `AGENTS.md` 的 Cursor Cloud 说明：已有 `.venv`，执行 `.venv/bin/python -m pip install -r requirements.txt`（pandas 3.0.6、numpy 2.5.4），然后 `mkdir -p outputs`。

| 检查 | 结果 |
| --- | --- |
| 删台账断言后、放入 etf_probe 前 | `Ran 276 tests`，`FAILED (errors=2)`，0 失败 |
| 放入 etf_probe 后 `.venv/bin/python -m unittest discover -s tests -t .` | `Ran 276 tests in 48.010s`，`OK`。0 失败，0 错误 |
| 分组 | data 192，indicators 40，research 44。与基线一致，因为步骤 2 没有删测试方法 |
| SHA256 `data/market.sqlite` | `b56148daf640d4bca6bbd2856a9c36fd9a11472ea9ebe94753476e0bb02e5290` |
| SHA256 `data/universe.csv` | `cb73f8daab938cda538eab02e8ac539cba129d90672d6757b3df93f55c374178` |
| `PRAGMA integrity_check` | `ok` |
| `git check-ignore` | 两个数据文件可入库；`outputs` 被忽略 |
| `pi-fleet` | 全库无匹配 |

## Decision / Next Steps

`dev` 等待审查。合入 `main` 需要 Owner 点头。未改 `AGENTS.md`、`.pi/`、`Harness_manual.md`、`docs/manual/`。
