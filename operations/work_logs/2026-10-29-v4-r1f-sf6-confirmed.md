# v4-R1f SF-6 已确认

## Metadata

- Project: ETF_Rotation_Quant
- Task: 附表 A A1/A2 的 sf6 从 pending-manager 改为 confirmed
- Date: 2026-10-29
- Owner: project owner
- Route: direct-execute
- Source of truth: `docs/prereg/etf-multiasset-rotation-prereg-v4.md` 附表 A；`operations/work_logs/2026-10-29-v4-r1f-peers-a1a2.md`

## Goal / Summary

Manager 确认 SF-6：月末决策日是上交所交易日历里每个自然月的最后一个交易日。附表 A 的 A1/A2 把 `sf6` 从 `pending-manager` 改为 `confirmed`。月末怎么判定、两条规则的公式、成交日都不改。

## Scope / Changes

- `config/v4/peers.toml`：`sf6 = "confirmed"`
- `src/v4/peers/calendar.py`：`SF6_STATUS = "confirmed"`
- `src/v4/peers/config.py`：加载时要求 `sf6` 为 `confirmed`
- `tests/v4/test_peers.py`：断言同步为 `confirmed`

## Validation

`.venv/bin/python -m unittest tests.v4.test_peers`：16 项通过。

## Decision / Next Steps

定义已确认。不跑真实收益，不写 ledger，不改预注册正文。
