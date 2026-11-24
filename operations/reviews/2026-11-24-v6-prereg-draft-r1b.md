# v6 预注册初稿 R1b · 2026-11-24（修订 i）

## 技术结论

| 项 | 值 |
| --- | --- |
| **结论** | **`同意冻结前置条件已满足`**（**非**已冻结、**非**合 PR） |
| **产品阻塞** | **无**（@653 仅 BLOCK-A；@`292568ba` 已闭合） |
| **R1b 全量审计窗** | `8f7ffbae3ac1885cefce9bc1281e4ab2d030687f`（要点 103、附表 B、规范 diff v2.1→2.2） |
| **增量 refresh** | `653de223400567f06ce3abd42b78c0394bf3cf57`（story v3；历史 BLOCK-A 见下） |
| **#339 当前全 HEAD** | `292568ba10b1de937ddb2eb7743c1279ad9f9666`（BLOCK-A 修复 + 三处规范闭合 + §3/§6 组件表） |
| v2.1 对照 | `27036630f6916aa921e7b9a2eb6f905c7c642551` |
| main | `24762d27f08786d4045bf4d40259d7c1ab878b16` |

**要点数字**：103 个 token 已全部语义映射（88 `anchored` + 15 `excluded_non_content`，`manual_pass_complete: true`）；详见 `pr339-r1b-keypoint-numbers.json` → `semantic_groups`（按可见主张去重，保留 html/md 双出现）。

---

## 前置与基线

- merge #361/#362 parents ✅；LFS `02458762…`
- main：`DJIA`/`DWRTF` raw max **2026-09-30**；`2024-12-25` **0**
- 执行：subject 代码 @8f7ffbae + overlay `/tmp/v6-r1b-overlay` + main 库副本；**无** 2016+ 项目池 PnL

---

## (a) 附表 A

| 阶段 | subject CSV SHA256 | 与 main 复跑 |
| --- | --- | --- |
| @653（历史 BLOCK-A） | `96a21d56…` | **不等**（DJIA/DWRTF 止日与行数滞后） |
| @`292568ba`（本轮闭合） | `3f8407a0d760ab0ce9dcd3b519d28f2e8b276548ea4c0a2123230f735e266d94` | **字节一致** |

相对 @653 仅 **DJIA、DWRTF** 两行止日→2026-09-30、行数更新；相对 @8f7ffbae 差分同左。附表 B / preflight 脚本 / PNG / config **653→292568ba 无改动**。命令：`pr339-r1b-commands.md`。

---

## (1) 美股 15 候选 · `maps_to` 一致性（非「15 个都必须有 QDII」）

判定：**有 `maps_to` 的** 行在 `config/v4/universe.toml` 中应有对应 CN 基金；**无 maps_to 的 5 个 SPDR** 脚本与附表 A 标「无场内基金」→ **内部一致**。

| 候选 | maps_to | v4 CN 基金数 | 附表 A 载体 | maps_to 一致 |
| --- | --- | ---: | --- | --- |
| SPX | spx | 5 | 有三只节选 | ✅ |
| NDX | ndx100 | **13**（全表见下） | 513100；159941；513300 | ✅ |
| DJIA | theme-道琼斯… | 1 | 513400 | ✅ |
| SOX | theme-PHLX… | 1 | 501225 | ✅ |
| NBI | theme-纳斯达克生物科技 | 1 | 513290 | ✅ |
| XLK | theme-标普500信息科技 | 1 | 161128 | ✅ |
| XLV | theme-标普500医疗保健等权重 | 1 | 161126 | ✅ |
| XLE | theme-S&P 500 Energy… | 1 | 163208 | ✅ |
| XLY | theme-标普500消费精选 | 1 | 159529 | ✅ |
| XLP | — | 0 | 无场内基金 | ✅ |
| XLF | — | 0 | 无场内基金 | ✅ |
| XLI | — | 0 | 无场内基金 | ✅ |
| XLB | — | 0 | 无场内基金 | ✅ |
| XLU | — | 0 | 无场内基金 | ✅ |
| DWRTF | theme-道琼斯美国精选REIT | 1 | 160140 | ✅ |

**NDX 全部 13 个 `maps_to=ndx100` 基金**：513100, 513110, 513300, 513390, 513870, 501312, 159501, 159513, 159632, 159659, 159660, 159696, 159941（上市日见 `pr339-r1b-audit.json`）。

---

## (b) 附表 B

- **JSON** `d5dcc888f93211992324e0f63c849325644f2f19607d9b0d34fa6b57dab53f01`：subject = main 复跑 **字节一致**
- **≤2015 过滤**：`v6_appendix_b.py:21` `END`；`a_official.py:28` `bars date<=2015-12-31`；`topn_dedupe.py:21` `lvl date<=2015-12-31`

### 五分量求和（JSON 精确值）

**2006–10**：−9.33 + 1.78 + 5.03 + 0.65 + (−1.46) = **−3.33** = 合计 **−3.33** ✅  

**2011–15**：2.25 + 0.49 + 3.54 + (−0.88) + (−1.49) = **3.91** = 合计 **3.91** ✅  

**2006–15**：−3.36 + 1.13 + 4.28 + (−0.13) + (−1.48) = **0.44** = 合计 **+0.44** ✅  

附表 B **规范表**（正文 639–644 行）与上表 JSON **逐字段一致**（非四舍五入）。

### p3 / p4 · PNG 内嵌数字（Reviewer 读图，非仅 alt）

**`p3-decompose.png`**（@8f7ffbae）瀑布标签：

- BM-主 **15.1%** → 仓位差 **−3.4** → 等权 **+1.1** → 挑选 **+4.3** → 防守 **−0.1** → 成本 **−1.5** → v6 净 **15.5%**
- 蓝线参照 **13.3%**（第 47 行截断口径）
- 桥：**15.1−3.4+1.1+4.3−0.1−1.5=15.5**（与图标签一致）

与 JSON 三分段表：图用 **2006–15 四舍五入叙事**；精确分拆见上「五分量」表（等权 1.13 vs 图 1.1 等）。

**`p4-signals.png`** 柱顶「确认紧张月数」：

| 年 | A | 美 |
| --- | ---: | ---: |
| 2006 | 0 | 0 |
| 2007 | 0 | 3 |
| 2008 | 12 | 12 |
| 2009 | 2 | 4 |
| 2010 | 6 | 3 |
| 2011 | 8 | 5 |
| 2012 | 8 | 0 |
| 2013 | 0 | 0 |
| 2014 | 2 | 0 |
| 2015 | 4 | 2 |
| **合计** | **42** | **29** |

与 JSON `信号画像` 逐年紧张月数之和 **一致**。副标题：A 把握 p 年末 0.31→0.57；美约 0.997（逐年明细见 JSON `信号画像`）。

---

## 要点数字映射（手工语义层）

- **范围**：summary / `p.memo` / ledger `lg-big` / md 要点 blockquote（不含全页 CSS 噪声）。
- **103 token**：88 已锚至规范节或附表 B JSON；15 显式 **excluded**（D9-1、12−1 标签、§2 交叉引用、日期碎片、v6 版本名等），各附 `exclusion_rationale`。
- **33 个 `semantic_groups`**：同一可见主张合并；`source_occurrences` 列 html memo 与 md 重复出现。
- **机器可读**：`pr339-r1b-keypoint-numbers.json`（非产品阻塞；无 demonstrated mismatch）。

---

## 规范 diff `27036630` → `8f7ffbae`（人工表为准）

`audit.py` 的 `allowed_*` 仅用 Owner/已写入/回填等关键词建议分类，**不能单独作证**。  
权威：**`reviewer_manual_classification_v21_8f7`**（17 行，完整 before/after 在 `normative_diff.all_section_deltas` + 各行 `*_quote_full`）。

| 结论 | 值 |
| --- | --- |
| `reviewer_non_permitted_rule_changes` | **[]** |
| 脚本 `normative_sec_change_count` | 0（与人工一致） |

## 增量 `8f7ffbae` → `653de22`

见 **`incremental_653_review`**（12 节）+ **`page_lint.at_refresh_653de22`**（0 ERROR / 1 WARN）。  
**无非许可 §1–8 规则改写**；§6/附表 B 披露换手重估 **~1.5 点**（警戒线仍 **2 点**）。要点 8 条见 `pr339-r1b-keypoint-numbers.json` → `incremental_653de22`。

## 增量 `653de22` → `292568ba`

见 **`incremental_653_to_292568ba`**：`reviewer_non_permitted_rule_changes` **[]**；附表 A 字节闭合；§5.3/§7/§9.1 三句规范闭合（非阈值）。  
§3 **`组件：风险`**、§6 **`组件：代价`** 为 story 重组；警戒线数字与 @653 `<details>` 一致；挑选警戒线加「对同结构等权」为表述对齐。

## 组件小表穷举 @`292568ba`

权威：`component_tables_exhaustive`（**14 表、61 claim、61 anchored、0 review_incomplete**）；`pr339-r1b-component-manual.py`。

历史 @653：**57 anchored + 3 incomplete**（§5 不通过、§7 小资金、§9 R1b 现态）→ @292568ba 三处已用 md 原文闭合。

**§3 风险 + §6 代价**：每可见数字/名称已人工锚至 §3.5 红队表、八种情形 `<details>` 或附表 B（见 audit `tables`）。

**§6 agree/disagree**：**同意** Owner（规则阈值意图未改；页首代价表显式 1.0–1.5 点与脚注一致）。JSON 成本 **−1.48** pp（2006–15）。

---

## R1 · SF-1 / J-3（subject 树内）

- **SF-1**：`2026-11-23-v6-prereg-draft-r1.md` 原 defer 附表 B → 2.2 §9.2#3 **已完成** + JSON 可复算
- **J-3**：R1 **J-3** → §9.2#2 / 附表 A「细分化工 **不参选**」

@653 时 R1/SF-1/J-3 已闭合；不单独构成阻塞。

---

## (e) 页面

- **@`292568ba`**：`owner_page_lint` **0 ERROR / 1 WARN**（§8 表；见 `page_lint.at_current_292568ba`）。
- **@653de22**：0 ERROR / 1 WARN（保留 lineage）。
- **@8f7ffbae**：6 WARN。

---

## Companion 七路径（Owner 本轮 scope）

| 路径 | 角色 |
| --- | --- |
| `operations/reviews/2026-11-24-v6-prereg-draft-r1b.md` | 本 memo |
| `operations/reviews/pr339-r1b-verify.json` | 裁决摘要 |
| `operations/reviews/pr339-r1b-audit.json` | 全量审计 + 增量 + 组件表 |
| `operations/reviews/pr339-r1b-keypoint-numbers.json` | 要点数字映射 |
| `operations/reviews/pr339-r1b-commands.md` | 复现命令 |
| `operations/reviews/pr339-r1b-audit.py` | 审计生成器 |
| `operations/reviews/pr339-r1b-component-manual.py` | 组件表人工锚点 |

### Companion 净差异与 blob

不在此 memo 写入 companion tip SHA 或 `git diff --stat` 行数（随提交变动）。基线：`origin/main`；分支：`cursor/pr339-r1b-reviewer-d912`；**七路径**见 `pr339-r1b-verify.json` → `companion_artifacts_seven_paths_owner_scope`。当次全量 SHA 与 stat 见交付回复。

**修订 i**：`table_index` 12 路线表改绑 §9.1/§9.2（修正 653→292568ba 后逐步错位）；§5 增强基准 K2A 补 D39-3 + §5.3③；§6 打折行补 §3 五折/六折原文。