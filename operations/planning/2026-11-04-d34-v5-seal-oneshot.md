# D34 · v5 封板；一次性检验跑四条（2026-11-04）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning（决定记录）
- Status: active
- Owner: L. Loric
- Maintainer: Orchestrator
- Date: 2026-11-04（Asia/Taipei）
- 依据：Owner 2026-11-04：“我批准封板。一次性检验，我想把 E2、A1、基准、V5.1 都跑了。”；`results/v5.1/design/gate.csv`；《v5 研究备忘》第 22 版第 3–11 节。

## 决定

| 编号 | 决定 |
| --- | --- |
| D34-1 | 按 D27 封板：v5 研究阶段结束，v5.1 规则不再改动；之后的新想法记作 v6 |
| D34-2 | 一次性检验（2016-01-01 → 2026-09-30，已污染检验段，只跑一次）同次运行：E2 新口径（B0）、A1、基准 BM-主、v5.1；A2 和单一指数照 v5 §6.3 作对照一并报告 |
| D34-3 | 入围名单不变：只有 E2 新口径（v5.1 §6.3 不入围）。v5.1 在一次性检验里**只作对照、只报告**：结果再好也不能入围、不能进模拟盘候选，判据 ⑤ 不计入；它的用处是给 v6 提供“中国 2016 年以后”的证据 |
| D34-4 | 一次性检验用 `milestone/v5-code-freeze` 指向的代码；Reviewer 写 `results/v5/LOCK` 后才运行；判据按 v5 §6.4，⑥ 的反弹按 D33-3 |
