# D22 · 每只场内基金只用一条后复权（2026-10-29）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning（决定记录）
- Status: active
- Owner: L. Loric
- Maintainer: Orchestrator
- Date: 2026-10-29（Asia/Taipei）
- 依据：`operations/reviews/2026-10-29-v4-r1f-d21-hfq-spot.md` 的 follow-up：160125、160644 同时有旧的腾讯后复权（`kind=backward`）和 D21 还原的后复权（`backward_rebuild`），研究代码仍读旧的；`bars.adj=hfq` 只认东财来源

## 决定

| 编号 | 决定 | 说明 |
| --- | --- | --- |
| D22-1 | 每只场内基金在研究和回测里只用**一条**后复权，按来源顺序取第一个可用的：东财后复权 → 腾讯后复权（含按比例延长的尾部）→ D21 还原 | 数据读取层提供一个统一的入口，研究代码一律从这里读，不直接读某个来源 |
| D22-2 | 同一只有两条以上来源时，逐日比对日收益；任一天差超过 0.1 个百分点的，列清单交 Orchestrator，不自动选 | 160125、160644 先比 |
| D22-3 | `bars.adj=hfq` 列维持只放东财来源；还原和腾讯来源留在 `v4_series`，统一入口负责挑选 | 不改历史表结构 |
