# 交易员方法笔记（共同学习用的参考）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: reference（导航）
- Status: active
- Owner: L. Loric
- Maintainer: Orchestrator（Notion AI）
- Last updated: 2026-10-25
- Source of truth: Owner 在 Notion 私人区整理的视频笔记（原页带截图）

## Purpose

这里存放 Owner 分享过、并和 Orchestrator 一起讨论过的外部交易方法。它们是**启发来源，不是规则**：任何想法要进入策略，都必须先写进预注册、计入尝试次数，再检验。新会话读这里，是为了理解 Owner 的直觉从哪里来。

## 笔记

| 笔记 | 一句话 | 对本项目的启发 | 在项目里的去向 |
| --- | --- | --- | --- |
| [Martin Luk 的美股交易体系](martin-luk-trading-system.md) | 胜率 22%，靠截断亏损、让盈利跑，年收益 969.8% | 评价看期望，不看胜率和回撤：他一个月回撤 26.6%，全年仍是 +969.8% | “期望最大化、回撤是手段”写进 `docs/project-intake/owner-vision-and-principles.md` §2.1；离场纪律 → v3.1 单只 10% 离场 |
| [Qullamaggie 的三种交易策略](qullamaggie-three-setups.md) | 按 1/3/6 个月涨幅取最强的 1%–2%，突破买入，跌破 10/20 日线离场 | 强势有连续性；用多个回看期排名；按均线或回撤跟踪离场 | 多回看期排名 = v3 的 20/60/120/250 日；跟踪离场 → v3.1（用固定回撤比例，参数更少）；**纳指 10/20 日线大盘过滤的 A 股版本已在第 2 次尝试中检验失败并关闭，不得重做** |
| [唯阔：用涨停股看资金偏好](weikuo-limit-up-preference.md) | 用涨停股的分布判断资金当下偏好什么 | 资金偏好（“品味”）能否用于 ETF 选择 | 板块层“品味”特征已检验，见 `operations/reviews/2026-10-22-r2-diagnostics.md` §5（计入尝试次数） |

相关讨论记录：`docs/research/2026-10-22-external-reading-notes.md`（Quant-Arena、《非对称风险》等）。

## 用到 ETF 上要注意

- 这些方法针对的是个股，日波幅（ADR）常在 5% 以上，所以止损可以放在 1%–5%。宽基和行业 ETF 的日波幅大约只有 1%–2%，照搬这么近的止损会被反复洗出去。v3.1 用的是 10%，并且检验过 8%–15% 都成立。
- 交易员靠的是大量小额试错，加上少数大赢家。轮动策略每期只持有少数几个标的，交易次数少得多，只能借鉴“截断亏损、让盈利跑”这个思想，不能照搬具体参数。
- 他们都不做空，或者做空吃过大亏。这和本项目“不做空、不加杠杆”的纪律一致。
