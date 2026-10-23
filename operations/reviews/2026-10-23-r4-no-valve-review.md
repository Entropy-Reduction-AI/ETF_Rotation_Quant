# 评审：`cursor/r4-no-valve` 6e2d1ea（2026-10-23）

结论：**通过**，可按 D6 `--ff-only` 合入。

- v2 结果已在 main（0178e24，含 `results/v2/oos/LOCK`）。
- `[valve] enabled = false`，参数保留；`plan_targets`/`target`/`target_snapshot` 在关闭时 A 股永远在场且不读阀；`replicate` 仍复现 25/10（≤0.04pp）。测试覆盖开/关两种行为；全量 344 OK；market.sqlite `3b9f8fb2…` 未动。
- 2026-09-30 目标与之前逐字节相同（当日阀本就在场），符合预期。
- 小瑕疵（不阻断，下次顺手改）：阀关闭时快照仍写「阀：在场」，应写「关闭（D7）」，避免误读为阀在工作。
