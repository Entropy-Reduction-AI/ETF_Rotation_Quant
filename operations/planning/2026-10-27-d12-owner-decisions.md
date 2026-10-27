# D12 · Owner 决定（2026-10-27，第二批）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning（决定记录）
- Status: active
- Owner: L. Loric
- Maintainer: Orchestrator
- Date: 2026-10-27（Asia/Taipei）
- 依据：Owner 对《v4 研究备忘》第 6 节的答复（“四个选择我都同意”），以及对 Orchestrator 定义、时代风格和检验方式的补充
- 相关：`docs/research/2026-10-27-v4-research-memo.md`；`operations/planning/2026-10-27-d11-owner-decisions.md`；`docs/prereg/etf-multiasset-rotation-prereg-v3.1-addendum-1.md`（第 2 版）

## 决定

| 编号 | 决定 | 说明 |
| --- | --- | --- |
| D12-1 | **成交限制**：v4 起，收盘涨停的买单、收盘跌停的卖单、停牌或无当日价格，一律当作“当天成交不了”，顺延到下一个能成交的交易日。指数池按对应 ETF 的涨跌停幅度判断 | 备忘选择 1-A。D11-1 的“等下一个有效价”并入这一条，在 v4 实现；v3.1 冻结基线按现行实现写明（见下方“更正”） |
| D12-2 | **检验方式**：v4 以“任意起点”为主，报告持有 1/3/5 年时对基准和各单一指数的胜率、中位差、最差的一次，并标出策略会输的起点 | 备忘选择 2-A |
| D12-3 | **v4 研究方向**：D1 转折点换挡、D2 按市场状态分配速度、D3 空位当天补、D4 海外行业池，每个只改一处 | 备忘选择 3-A |
| D12-4 | 2026-10-27 的 4 个分解诊断计入，Orchestrator 诊断计数 **31 → 35** | 备忘选择 4-A；写入 addendum-1 第 2 版 A3 |
| D12-5 | **C1 只计一次**：影子运行的 ledger 行标 `C1-shadow`，计入 60 条预算，不计入判据 ⑤ | 闭合 Reviewer R1 的 B1（Orchestrator 拍板，Owner 授权） |
| D12-6 | **五日无价**：按现行实现逐条写成可测试条文 | 闭合 R1 的 B2，见 addendum-1 第 2 版 A1 |
| D12-7 | **Orchestrator 的定义**：Orchestrator 是 Owner 当前主要对话、负责设计和解读的 agent，跟随 Owner 的选择而变（曾为 GPT Astra、Notion AI；2026-10-27 起为 Claude）。Owner 可以同时向多个 agent 交叉征询意见 | 修改 `AGENTS.md` 项目分区（单独 PR） |
| D12-8 | **重建真实可投资市场**：设计期可以用今天的知识，不能用今天的数据。当年境内没有对应 ETF、但当时的投资者可以用合理方式买到的市场（例如直接交易美股行业 ETF），用有长期官方历史的指数还原；入选指数按固定分类整组纳入（如标普500 全部行业），不挑表现好的行业 | Owner 原则；落到 D4 |
| D12-9 | **策略要在各种市场状态下都站得住**：牛市里人人都赚钱，策略的价值在于顺应市场，而不是被某一段行情选中。v4 体检按牛市、回调、熊市、反弹四种状态分别报告超额 | Owner 原则；落到检验方式 |

## 更正（Orchestrator）

D11-1 记录时写“等到下一个有效价再卖，等同当前代码实现”，与代码不符。现行引擎在无当日价格时沿用最近收盘价，离场卖单当天按沿用值成交；只有价格为 0、负数或非有限值才顺延。设计期 P1 的 647 次离场成交里只有 5 次（2 个事件）受影响，P6 为 0 次。处理：v3.1 冻结基线按现行实现写明（addendum-1 第 2 版 A1），Owner 想要的“顺延”与涨跌停、停牌一起在 v4 实现（D12-1）。不重跑设计期。

## 给 bot 团队的变更

- Dev：`trial_count()` 的诊断常数 31 改为 35，并排除 `arm` 为 `C1-shadow` 的 ledger 行；相关测试同步（现有 10 行 ledger 下返回 73，无 ledger 时返回 63）。
- Dev D3：按 addendum-1 第 2 版 A1 第 5 条的 4 种情况写边界测试。
- Reviewer：对 addendum-1 第 2 版做 R1 复审。
