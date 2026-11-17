# 分支清理：D37 第五轮与第六轮派单（2026-11-16）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: work_log
- Status: done
- Owner: L. Loric
- Maintainer: Orchestrator（Claude）
- Date: 2026-11-16（Asia/Taipei）
- 授权：Owner 2026-11-16 在对话中明确要求清理

## 删除的远程分支

都已合入 main，删除前逐个确认 `git merge-base --is-ancestor <分支> origin/main` 成立。

| 分支 | 原指向提交 | 合入 |
| --- | --- | --- |
| `cursor/d37-r5` | `770b22b2779309f70936b59ff210905922676d3f` | PR #284，`1a19235` |
| `cursor/d37-r5-plan-b-signoff-0579` | `503c90ac936f0fb479ca0aa79218737263320e6a` | PR #285，`10db5a5` |
| `claude/grok-d37-round6` | `a40f178f5d559a7ff9ed2e3b17af70a352307f95` | PR #287，`5c70dfb` |
| `claude/branch-cleanup-1116` | 本记录所在提交 | 本记录的 PR |

## 关闭、不合入的 PR

分支保留，不删除。

| PR | 分支 | 原因 |
| --- | --- | --- |
| #145 | `claude/v5-prereg-draft` | v5 预注册草案第 1 版，已被 main 上的 `docs/prereg/etf-multiasset-rotation-prereg-v5.md` 取代 |
| #165 | `cursor/v5-design-campaign-13b4` | v5 原版设计期结果；原版 2026-11-01 因结构硬伤淘汰（看板更新记录 11-01），改走 v5.1 |

没有移动、删除任何 tag。
