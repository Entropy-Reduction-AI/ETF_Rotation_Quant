# docs/owner：给 Owner 看的文档

每份文档都有一个同内容的 Claude 页面；页面由 `scripts/owner_pages/build.py` 从这里的 md 生成。

## 预注册不在这个目录

所有版本的预注册都放在 [`docs/prereg/`](../prereg/)，v6 也一样：

- **v6 预注册（已冻结）**：[`docs/prereg/etf-multiasset-rotation-prereg-v6.md`](../prereg/etf-multiasset-rotation-prereg-v6.md)，冻结标签 `milestone/v6-prereg-freeze` → `f066da8e`；页面 https://claude.ai/artifact/VASWvP9wCzDvXmsQqzLFBh
- 冻结后这个文件一字不改，也不搬家：搬动会让冻结标签、D45（冻结代码是规范的一部分）和各 PR 里引用的路径失效。

## v6 相关

| 文档 | 页面 |
| --- | --- |
| [Owner 看板](owner-board.md) | https://claude.ai/artifact/17bW2rKeeBheRFfhnjsrSU |
| [v6 预演预测表](v6-preflight-forecast.md) | https://claude.ai/artifact/4uzHh1NzeLVAEovbyLqqby |
| [v6 预注册（已冻结）](../prereg/etf-multiasset-rotation-prereg-v6.md) | https://claude.ai/artifact/VASWvP9wCzDvXmsQqzLFBh |
| [v6 体检报告（设计期）](v6-health-check.md) | https://claude.ai/artifact/NRgYVyimeFrzdhRetr48Fq |
| [v6 一次性检验报告（骨架）](v6-oneshot-report.md) | https://claude.ai/artifact/GQKvS1KvRmWiPBkHKd7JRp |

决定记录（D 编号）在 [`operations/planning/`](../../operations/planning/)。
