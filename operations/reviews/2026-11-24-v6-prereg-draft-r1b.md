# v6 预注册初稿 R1b · 2026-11-24（修订 c）

## 技术结论

| 项 | 值 |
| --- | --- |
| **结论** | **`request_changes`** |
| **唯一产品阻塞** | **BLOCK-A**：main 数据基线复跑 `v6-appendix-a.csv` 与 subject 提交 **不字节一致** |
| **#339 head**（起/终/刷新） | `8f7ffbae3ac1885cefce9bc1281e4ab2d030687f`（无页后提交） |
| v2.1 对照 | `27036630f6916aa921e7b9a2eb6f905c7c642551` |
| main | `24762d27f08786d4045bf4d40259d7c1ab878b16` |

**非产品阻塞**：要点数字映射 **REVIEW-INCOMPLETE**（见下）= Reviewer 未在本轮钉满锚点，**不**等同 subject 数字矛盾。

---

## 前置与基线

- merge #361/#362 parents ✅；LFS `02458762…`
- main：`DJIA`/`DWRTF` raw max **2026-09-30**；`2024-12-25` **0**
- 执行：subject 代码 @8f7ffbae + overlay `/tmp/v6-r1b-overlay` + main 库副本；**无** 2016+ 项目池 PnL

---

## (a) 附表 A · BLOCK-A

| 文件 | SHA256 |
| --- | --- |
| subject `v6-appendix-a.csv` | `96a21d56ee2936c91ec390a262794dbee0ad54d15acd875f0d34d5c3d5b4e372` |
| main 复跑 | `3f8407a0d760ab0ce9dcd3b519d28f2e8b276548ea4c0a2123230f735e266d94` |

| 候选 | 列 | old | new |
| --- | --- | --- | --- |
| DJIA | 库内止 / 行数 | 2024-02-01 / 8515 | 2026-09-30 / 9182 |
| DWRTF | 库内止 / 行数 | 2017-11-22 / 4752 | 2026-09-30 / 6975 |

其余行无差。命令：`pr339-r1b-commands.md`。

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

## 要点数字映射（非全页扫数）

范围：**页首 summary 三格 + 各节 `p.memo` + ledger `lg-big` + md `> **` 要点**，见 `pr339-r1b-keypoint-numbers.json`。

| status | 含义 | 条数（本轮） |
| --- | --- | ---: |
| `anchored` | 已钉附表 B / §3 等语义锚点 | 6 |
| `needs_manual` | 需对照 forecast 3.22 等同节（未展开） | 20 |
| `review_incomplete` | **REVIEW-INCOMPLETE**：未钉锚点，**非证伪** | 85 |

**不作产品阻塞**；未逐项证明 subject 数字错误。

---

## 规范 diff `27036630` → `8f7ffbae`（§ 分段 + 段内段落）

方法：按 `## §` / `## 附表` 切分后段落 diff（见 `pr339-r1b-audit.json` → `normative_diff`）。

**`normative_sec_change_count = 0`**（无检出 §§1–8 规则改写类 unauthorized 段落）。

**有内容的允许/状态类变化（列举，非违规）**：

| 类 | 位置 | 摘要 |
| --- | --- | --- |
| `allowed_metadata_version` | Metadata | 初稿 **2.1→2.2**、日期 11-23→11-24 |
| `allowed_pollution_registry_row` | §4 | 新增污染登记行 **#5 常识性市场历史** 与「同仓位基准判」 |
| `allowed` / 附表·§9 | 附表 A/B、§9.2 | 2.2 写入附表、待办完成态、Owner 2026-11-24 确认 |
| `allowed_summary_pointing_to_appendix_b` | §3 八问表 | 问 4/6 填 **已写入** 42/29 月、拆分 **+4.3/−3.4/−1.5**（指向附表 B，非改 §1.2 规则） |
| `allowed_sec3_design_annualization` | §3 | **设计期年化口径** 15.5% / 13.3% |
| `allowed_owner_confirmed` | §4 数据陷阱表 | **主题指数回填** + Owner 一级行业回填确认 |

旧版 **U1–U6 unauthorized** 表已撤：其中 metadata、§9.2、Owner 确认、附表 B 摘要属 **允许类**；不含证实的 §1–8 规则句改写。

---

## R1 · SF-1 / J-3（subject 树内）

- **SF-1**：`2026-11-23-v6-prereg-draft-r1.md` 原 defer 附表 B → 2.2 §9.2#3 **已完成** + JSON 可复算
- **J-3**：R1 **J-3** → §9.2#2 / 附表 A「细分化工 **不参选**」

**不抵消 BLOCK-A。**

---

## (e) 页面

- `owner_page_lint`：**0 ERROR**，**6 WARN**：

  1. sec-1 单元格 63 字  
  2. sec-2 单元格 68 字  
  3. sec-2 单元格 72 字  
  4. sec-5 列表项 124 字  
  5. 附表-a 表单元格 56 字（513500…）  
  6. 附表-a 表单元格 56 字（513100…）

- `story_check`：0 ERROR（诊断门禁，非 Owner 硬约束）

---

## Companion 六路径（须整树存在）

| 路径 | 角色 |
| --- | --- |
| `operations/reviews/2026-11-24-v6-prereg-draft-r1b.md` | 本 memo |
| `operations/reviews/pr339-r1b-verify.json` | 裁决摘要 |
| `operations/reviews/pr339-r1b-audit.json` | 全量审计 |
| `operations/reviews/pr339-r1b-keypoint-numbers.json` | 要点数字映射 |
| `operations/reviews/pr339-r1b-commands.md` | 复现命令 |
| `operations/reviews/pr339-r1b-audit.py` | 审计生成器 |

### `git ls-tree` @ `3c25dc5`（六路径均在树）

| 路径 | git blob |
| --- | --- |
| `2026-11-24-v6-prereg-draft-r1b.md` | `91fb3b6498570ff2671940a8b40b60eabe034994` |
| `pr339-r1b-verify.json` | `275a393beead68fd8c39d3c4051d963c720aee60` |
| `pr339-r1b-audit.json` | `6f67e816ee4d735329b9f0611813fadd20885a23` |
| `pr339-r1b-keypoint-numbers.json` | `e5c0fa5237382e43d635731e064bf5a72eb5ab85` |
| `pr339-r1b-commands.md` | `5b845bc8e32da097c0ed6424a6153bb89aeeb168` |
| `pr339-r1b-audit.py` | `9ef67e8aa1d745d1053bb9c7adcb27c316696e54` |