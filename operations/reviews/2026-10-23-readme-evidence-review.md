# 评审：任务 H 证据包（`cursor/readme-evidence` 7026491）

## Metadata
- Project: ETF_Rotation_Quant · 评审: orchestrator · 日期: 2026-10-23
- 对象: `cursor/readme-evidence`（f4d9f39 数据、34f96b0 证据与图、7026491 阀标签），基线 main 530508b
- 结论: **通过（附修补，orchestrator 已推到本分支）**。合入前需由 Agent 重新生成 `docs/assets/` 的 PNG（MCP 推送不了二进制文件）。

## 独立复核
| 检查 | 结果 |
|---|---|
| 第 0 步 | main 已快进到 530508b，远端 `cursor/repo-restructure` 已删 |
| `python -m src.report evidence` 在独立目录重跑 | `results/report/` 下 8 个 csv/json 与提交逐字节相同 |
| 删除的 775 条非交易日中证行 | 面板日期全部落在交易日历内（不在日历上的有 0 个），删行不影响面板、复现和目标持仓 |
| v2 §9 原口径对账 | 工作记录三条都在 0.01pp 内；orchestrator 此前的独立复算一致 |
| 基准口径 | 按任务：70/15/15，人民币中间价，全收益，月初再平衡；起点 2006-01-05 的原因已披露 |
| `target-2026-09-30.json` | 只有 `valve` 一个字段变化 |

## 发现与修补
1. **（已修）净值图难读**：纵轴是 10⁰/10¹ 的科学计数；三条线起点不同（沪深300 从 2005 年起，另外两条从 2006 年起）；没有回撤。改成：
   - `nav-vs-benchmark.png`：三条线同一天起点 = 1 元，对数刻度用普通数字标注，线尾标注期末净值和年化，下方加回撤面板，设计期和样本外用虚线分界；
   - 新增 `oos-vs-benchmark.png`：样本外单独一张，累计收益用线性刻度（%），下方是回撤。
   线尾的年化和 `benchmark.csv` 同口径（含起点当天的收益）。图例改成全称，不再用「BM-主」。
2. **（已修）字体**：`Noto Sans CJK SC` 不存在时回退到 `Noto Sans SC`。
3. **（已修）`requirements.txt`** 增加 matplotlib（`src/report` 需要）。
4. （不阻塞）`decay.csv` 用 BM-主（含美股）去拆 A 股部分的衰减，口径不对应。README §6.2 改用中证全指和沪深300 拆，数字直接取自 `benchmark.csv` 和 `representativeness.json`。
5. （记录）中证一级行业权重没有拿到，README 如实写明。

## 同一提交里 orchestrator 推送的文档
README.md 重写；AGENTS.md（PROJECT:OWNED 部分）；规划文档追加 D8；v2 预注册 §9 末尾追加一条勘误（价格指数是 7/16，另附人民币口径的对照）。

## 动作
Agent：重新生成 PNG（数字文件必须逐字节不变）→ 全量测试 → `--ff-only` 合入 main → 删分支 → 打 `milestone/phase1-closeout`。
