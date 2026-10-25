# 云端进度核查与执行边界

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning / boundary audit
- Status: active follow-up
- Owner: L. Loric
- Maintainer: Orchestrator（Notion AI）
- Last updated: 2026-10-25
- Scope: 仓库证据核查与文档同步；不代表新规则批准、合入授权、代码冻结、G3 或 G5 授权。

## 1. 核查基线与结论

| 对象 | 本轮观察 | 边界 |
| --- | --- | --- |
| main | `ed474f8ec992e0b18c74a7d954b4e7a181c1b645` | 核查时快照，不推断后续无变化 |
| 规则冻结 | #32/#36 已合入；`milestone/v3.1-prereg-freeze` 的目标 commit 为 `1040035ee1d707368b58687994894189753843ac` | annotated tag 对象不是目标 commit；不得移标或改冻结正文 |
| 规则内容 | 将冻结版本与 Owner 获批修订 `c6205e0985161aeba2335af582a758f91911e7cb` 只读下载比较，字节一致 | 原修订变基为 `c29758a`，交付 head 对应 `3a9415d`；SHA 变化本身不是规则变化 |
| Dev #39 | `dae20a48d9ef8a8ce8df0e718fe9766874bf62a2`：官方回溯、休市修复、独立离场、溢价接入均已交付 | 尚未合入，交付不等于正式业务结论 |
| Reviewer #40 | `f54dbacc330125a003bb65ce7c166ae657796740`：approve_with_follow_up | 复跑授权文字冲突，见下节；PR 包含 #39 祖先，不应把整个 diff 当成纯 review |
| 测试 | Reviewer 报告 462 项、跳过 1 项 | 不是“462 项全部通过”；Orchestrator 本轮没有自行重跑测试 |
| 后续门禁 | 本轮所列 main 标签未见代码冻结标签；`results/v3` 目录未见 LOCK | 仅仓库观察，不是对所有 bot 或运行环境的完整审计 |

## 2. 当前必须闭合的冲突

Reviewer 报告要求“缺价日到期离场单”的处置与原 v3 §3.3 的前值/五日规则在正式设计期复跑前闭合，但文末授权表又写“可启动正式设计期运行”。两句不能同时当作放行依据。

已直接在 [#40 留言](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/40#issuecomment-6398622133) 请求澄清。**在语义和 Reviewer 授权文字闭合前，不把附跟进项通过解释为正式复跑无条件放行。** 在既有权限内的集成/单测可以继续；它们不能替代规则语义批准。

请 Dev / Reviewer 提交不用回测收益挑方案的边界矩阵，至少区分：

- 原始缺价、正常海外休市、停牌；哪些值用于信号、估值及真实成交。
- 连续缺价第 1–4 天与第 5 天及以后；待执行离场单何时卖、是否能用前值成交。
- 多代码容器中部分代码缺价的处理；不得用一个代码的价隐含替另一个成交。
- 缺价、待执行离场与例行调仓同日冲突的先后顺序；不得恢复被取消旧单。
- 明确哪些属于冻结规则的无歧义落实，哪些改变收益/持仓语义。如确需规则修订，Orchestrator 汇总机制、影响与建议，请 Owner 决定新版本；不得改冻结快照或移动标签。

## 3. 后续报告仍须披露与核对

1. 发布日对照：纳指/标普发布日期缺失时当前路径不截断，不能称为完整 publish_date 对照。披露受影响标的、时间与覆盖，不能通过改列名掩盖缺口。
2. 官方序列缺口：早期黄金/国债、部分主题序列及 HSTECH 回溯等，不以补池等同全覆盖。CBA00601 继续不擅自纳入。
3. 六路日收益合成、多代码价格与成本、基准调仓日期和探索脚本差异须桥接。E2 约 26% 是探索观察，不能据此调规则或要求正式引擎凑到该数字。
4. B 对 A 的比较口径须在检验前写定，不以事后口径放宽验收。60 个正式配置与 28+29 次历史尝试分账，历史探索计入过拟合尝试；不得擅增预算。
5. #39 已重接旧 #29/#31 的相关工程；Manager 应登记依赖和处置旧 PR，不能重复合入或拿旧签收覆盖新 head。新正式结果需独立复核。

## 4. 可执行范围与停点

| 阶段 | 谁做 / 何时停 |
| --- | --- |
| 工程集成与测试 | Manager 按既有门禁处理 #39/#40；Dev 实现，Reviewer 对实际 head 签收；本文件不新增合入许可 |
| 正式设计期 ≤2015-12-31 | 先闭合上节语义与授权冲突，再按冻结规则复跑；产出体检、共同口径复现、差异桥接、覆盖及预算清单 |
| Owner 看报告 | 到这里停；Orchestrator 汇总后交 Owner，不自行替 Owner 接受 |
| 代码冻结 | 满足既有门槛后才由 Manager 执行，与规则冻结不是同一件事 |
| G3 一次性检验 | Owner 单独明确批准后才按冻结清单运行；此前不产出 2016+ 组合收益，不提前 LOCK；Reviewer 按既有规程控制 LOCK 与复核 |
| 模拟盘 / 真钱 | 分别由 Owner 决定，G3 不自动放行 G5 |

## 5. 文档处置

- 本 PR 仅同步 Owner 看板镜像、更新 intake 的现状与本核查记录，不改业务代码、数据、预注册、main、标签或 LOCK。
- [Notion Owner 看板](https://app.notion.com/p/850ec881bd2483418c45017aa6f835cf) 继续作为 Owner 入口。三张图片保留；路线图标明历史快照，避免旧进度图误导。
- `operations/planning/phase2-board.md` 为 Manager 工程登记，由 Manager 随实际处理结果更新；本轮发现其“未启动/待复审”状态滞后于 #39/#40 交付，不代写其签收结论。
- 冻结预注册中的历史状态字样不在本轮改写，当前状态以冻结标签及外部登记为准。
- 本轮已把问题直接留在云端，不要求 Owner 代传本次核查。未设置后台轮询或 bot 自动唤醒。

## Sources

- [规则复审 #36](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/36)；`operations/reviews/2026-10-25-v3.1-prereg-rereview.md`
- [工程 #39](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/39)
- [工程复审 #40](https://github.com/Entropy-Reduction-AI/ETF_Rotation_Quant/pull/40)；`operations/reviews/2026-10-25-v3.1-d10-post-freeze.md`
- `operations/planning/2026-10-25-v3.1-revision-handoff.md`
