# v6 预注册初稿 R1b 独立复核 · 2026-11-24

## Metadata

- 类型：review-only（仅 `operations/reviews/**`）
- **PR #339 复核起点 head**：`8f7ffbae3ac1885cefce9bc1281e4ab2d030687f`（2.2 版）
- **收尾刷新 head**：`8f7ffbae3ac1885cefce9bc1281e4ab2d030687f`（**无** Orchestrator 页后追加）
- **对照 v2.1**：`27036630f6916aa921e7b9a2eb6f905c7c642551`
- **main（前置）**：`24762d27f08786d4045bf4d40259d7c1ab878b16`
- 机器可读：`operations/reviews/pr339-r1b-verify.json`
- **未**：合并 #339、 formal GitHub review、2016+ 项目池 v6 PnL、改 `claude/v6-prereg-r1` / tag

---

## 前置条件（独立核实，非 Manager 转述）

| 项 | 结果 |
| --- | --- |
| merge #361 `c7253ec…` parents `05e39c56` + `ce058680` | ✅ |
| merge #362 `24762d27…` parents `c7253ec` + `d5c54f61`；NET 3 个 `operations/reviews/*` | ✅ |
| main `data/market.sqlite` LFS oid `02458762…` | ✅ |
| main raw **DJIA / DWRTF** `MAX(date)` | **2026-09-30** / **2026-09-30** |
| `2024-12-25` DJIA+DWRTF 行数 | **0** |

---

## 执行基线（代码 vs 数据隔离）

| 层 | SHA / 路径 |
| --- | --- |
| 受检代码 | `8f7ffbae3ac1885cefce9bc1281e4ab2d030687f`（只读 `git show`，未 push 主题分支） |
| 行情库 | **main** LFS 实体（`02458762…`），覆盖 subject 树内 pointer `832119b7…` |
| 隔离 workspace | `/tmp/v6-r1b-overlay`（subject 脚本/附表/页面 + main 库副本） |
| French 49 | `633958bf…`（Reviewer 缓存，与历次 D38 复核同惯例） |

附录 B 链路仅触达 ≤2015-12-31（`v6_appendix_b.py` 中 `END`、股指 `lvl(… date<=2015-12-31)`）；附录 A 仅读 raw 覆盖与间隔，**不算收益**。

---

## (a) 附表 A

```bash
cd /tmp/v6-r1b-overlay && python -I scripts/preflight/v6_appendix_a.py
```

| 检查 | 观测 |
| --- | --- |
| 相对 subject 提交 `results/v6-preflight/v6-appendix-a.csv` **字节一致** | ❌ **不一致**（main 库下复跑） |
| 差异行 | **DJIA**：库内止 `2024-02-01`→`2026-09-30`，行数 8515→9182；**DWRTF**：库内止 `2017-11-22`→`2026-09-30`，行数 4752→6975（与 #361 入库一致） |
| subject CSV SHA | `96a21d56…` |
| main 库复跑 SHA | `3f8407a0…` |
| 一级行业回填备注 | 10 条 `allshare-*` 均含「2011-08-02 之前允许用回填点位」 |
| 931743 | CSV 列「发布日」2012-12-21 + 备注疑义；**规范正文**附表 A 表「参选起点 **2023-07-27**」 |
| 细分化工 | CSV 仍有 frozen 登记行；§9.2 / 要点写 **不参选**（R1 **J-3** 叙事闭合，行保留作状态说明） |
| 美股 15 个有 `maps_to` 的候选 vs `config/v4/universe.toml` | **10/10** 有对应 CN 载体（SPX/NDX/DJIA/SOX/NBI/XLK/XLV/XLE/XLY/DWRTF）；XLP/XLF/XLI/XLB/XLU 无 theme key、脚本标「无场内基金」，与 v4 一致 |

**阻塞 (a)**：在 **main 数据基线**上，附表 A 产出 **不能**与 #339 树内已提交 CSV 逐字节一致；正文/附表 prose 已写 DJIA/DWRTF 至 2026-09-30，与 main 库一致，与 **旧 CSV** 不一致。

---

## (b) 附表 B

```bash
python -I scripts/preflight/v6_appendix_b.py \
  operations/reviews/diag/v6-r1b-cache/49_Industry_Portfolios.csv \
  results/v5/other-market/raw/DTB3.csv
```

| 检查 | 观测 |
| --- | --- |
| 相对 subject `v6-appendix-b.json` | ✅ **字节一致**（main 库上复跑） |
| 五分量 + 合计（2006–10 / 2011–15 / 2006–15） | ✅ 三分段 `sum(5 steps)==合计` |
| v6 净 2006–15 | JSON **15.54**；正文/要点 **15.5**（四舍五入一致） |
| 拆分摘录 vs JSON | 挑选 +4.3、仓位差 −3.4、成本 −1.5、合计 +0.4 — 均在 `etf-multiasset-rotation-prereg-v6.md` 与 `index.html` 可检索 |
| A 股紧张月 / 美股紧张月 | JSON 逐年紧张月数合计 **42 / 29** — 与 §3 八问登记及页面一致 |
| **R1 SF-1** | **闭合** — 附表 B 落地，§9.2#3「已完成」且可复算 |

---

## (c) `27036630` → `8f7ffbae` · `docs/prereg/` 差异

允许类别（Owner 2026-11-24 22:17）：HTML 注释（问/看点/接力/页面标记）、要点列表、`<details>` 折叠、附表 A/B 全文、§9.2 状态、§3「设计期年化的口径」、Owner 确认增补。

**此外仍在 §§1–8 出现的规范面增量（需 Coordinator 目视，非清单式放行）：**

| # | 位置 | 性质 |
| --- | --- | --- |
| N1 | §3.1 | **SF-2**：「低于哪条线不做」+ D39 两条线 — 新规范句 |
| N2 | §3.1 | **D40-12**：A 股对账两块（挑选 / 等权倾斜）拆分表述 |
| N3 | §4 | 污染表第二套列「看过什么 / 对检验的影响 / 结论」及 **#3 QDII** 独立成行（原 v2.1 结构变更） |
| N4 | §5（检验段引言附近） | 检验段说明与「已污染段」表述重整（未改四档判据数字，但段落重组） |

附表 A/B、§9.2、讲故事层、§3 年化口径、Owner 三项确认 — 属允许大块；**未发现** §1.2 四步规则或 §5.3 四档阈值数字被改写（差异集中在登记、附表与叙事层）。

### 要点/摘要数字回链（节选）

| 页面/要点数字 | 规范/附表锚点 |
| --- | --- |
| 15.5% 设计期 v6 净 | §3 年化口径 + 附表 B JSON `v6 净…['2006–15']=15.54` |
| 13.3% 第 47 行 | §3 同段 + D38 第 47 行引用 |
| +0.4 vs BM-主 | 附表 B `合计（v6 净 − BM-主）` |
| +4.3 / −3.4 / −1.5 拆分 | 附表 B `收益拆分` 各分量 |
| 42 / 29 紧张月 | 附表 B `信号画像` 逐年 `紧张月数` 求和 |
| 40 个 A 股候选（检验段末） | 附表 A 叙事 + sector-tags；不含细分化工参选 |
| DJIA/DWRTF → 2026-09-30 | §4 #359 登记 + main 库查询（CSV 未更新见 (a)） |

---

## (d) R1 开放项

| ID | R1 状态 | R1b |
| --- | --- | --- |
| **SF-1** 附表 B | 开放 | **闭合**（JSON 可复现 + §9.2#3） |
| **J-3** 细分化工 | 开放 | **闭合（不参选）**；附表仍列 frozen 行 |
| MF/SF 其余 | R1 Must/Should | **未在本轮重审**（2.2 自称闭合 MF/SF-2..8；本 memo 不替代逐条复做 R1） |

---

## (e) Owner 页面门禁

```bash
python scripts/owner_page_lint.py docs/artifact/v6-prereg/index.html   # 需 bs4
python scripts/owner_pages/story_check.py docs/artifact/v6-prereg/index.html
```

| 工具 | ERROR | WARN | Owner 硬门禁 |
| --- | ---: | ---: | --- |
| `owner_page_lint` | **0** | 6 | **是**（0 ERROR）→ **过** |
| `story_check` | **0** | — | **诊断**（本 Owner 指令仅强制 lint 0 ERROR） |

脚本 **不**读取 `results/` 组合收益；仅解析 HTML。

---

## 建议结论（Coordinator，非签收）

**`approve_with_follow_up`**

| 阻塞 | 说明 |
| --- | --- |
| **BLOCK-A** | 在 main 行情库上 **附表 A CSV 未与 #339 提交字节一致** — 须在合并前用 main 库重跑并提交新 CSV（或书面钉死「CSV 故意基于入库前库」并与 prose 对齐） |

**非阻塞**：lint 6 WARN；story_check 无 ERROR；附表 B / SF-1 / J-3 在独立复算下闭合。

---

## 本 companion NET（reviews-only PR）

- `operations/reviews/2026-11-24-v6-prereg-draft-r1b.md`
- `operations/reviews/pr339-r1b-verify.json`