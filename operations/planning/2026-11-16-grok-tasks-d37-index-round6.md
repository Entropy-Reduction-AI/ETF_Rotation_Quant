# 给 Grok 群的任务：D37 第六轮，用浏览器补齐 36 条指数历史（2026-11-16）

## Metadata

- Project: ETF_Rotation_Quant
- Document type: planning（任务派发）
- Status: active
- Owner: L. Loric
- Maintainer: Orchestrator
- Date: 2026-11-16（Asia/Taipei）
- 依据：D36-4（新上市 ETF 上市前接跟踪指数历史）；D37 第 3、4 版补充（取数不以“匿名取不到”为由停下；Grok 用自己电脑的浏览器前台取）；`docs/manual/data-principles.md` 第 38 行
- 现状：D37 第五轮已合入 main（PR #284 `1a19235`，签收 PR #285 `10db5a5`）。`results/v51-diag/d37/s1-splice-roster.csv` 有 54 个冻结，其中 15 个不在冻结 universe、3 个不是单一指数（原油、跨境商品、印度 ETP），不处理；其余 36 个是本任务

下面整段可以直接复制给 Grok 群（Manager / Dev / Reviewer）。

---

```text
【任务】D37 第六轮：用浏览器补齐 36 条指数历史，然后重跑 S1（Owner 2026-11-06 授权，D37 第 4 版补充）

先读：
1. operations/planning/2026-11-05-d37-v51-cadence-diagnostic.md（第 3、4、5 版补充）
2. results/v51-diag/d37/report.md（第三、四轮为什么卡住）
3. results/v51-diag/d37/s1-splice-roster.csv（每个容器已试过的网址和原因，列 tried_urls、reason）

为什么要做：v6 要让新上市 ETF 上市当天就能打分（D36-4）。云端 agent 收不到注册验证邮件、遇到 403，36 条指数没接上。你们有自己的电脑和邮箱，用浏览器前台去取。

========== 规则（不变） ==========
- 允许：指数公司、交易所官网免费注册后下载；页面的历史数据导出、事实表、图表数据；逐页整理。
- 次选：官网确实没有时，用公开行情网站导出，再用官网事实表的若干点位核对，误差写进登记。
- 不允许：付费数据、破解或绕过登录、来源不明的数据。
- 发布日：只用指数公司公布的正式发布日（launch date）及之后的点位；基日到发布日之间的回填不要。发布日必须从页面上读到并截图，读不到就写“未核对”，不能猜。
- 入库门槛（同第四轮）：两条独立日线，收盘相对差中位数 ≤ 0.01%。官网下载 + 东财或同花顺核对即可。只有一条的不入库，写明原因。
- 价格指数即可，只用于打分。只需要“发布日 → 首只场内基金上市日后 30 个交易日”这一段。

========== 第 1 部分：取数（Grok，有电脑的同学） ==========

G1 恒生指数公司（13 条）——注册 INdex360 免费账号（https://www.hsi.com.hk/en-hk/index360/create-account/），用你们自己的邮箱收验证邮件后下载日线。东财已有一条日线，官网下载就是第二条。
   HSFML25、HSISC、HSSC50、HSSCAM、HSSCHKY、HSSCITI、HSSCPB、HSSCSOY、HSSCT、HSCSOE（恒生中国央企）、HSIDI（恒生创新药）、HSBIO（恒生生物科技）、恒生中国企业指数（HSCEI）

G2 标普道琼斯（12 条）——注册 S&P DJI 免费账号（https://www.spglobal.com/spdji/en/register/），在各指数页导出历史（Export → Historical）。
   标普500信息科技 SP500-45、标普500医疗保健等权 SP5HEW、标普500消费精选 SP500-25、标普生物科技精选 SPSIBI、道琼斯美国石油开发与生产 DJSOEP、道琼斯美国精选REIT DJUSRE、标普500能源(NTR)、标普全球石油、标普油气勘探及生产精选、标普美国品质消费、标普中国新经济行业、SPAHLVCP（标普亚太低波红利）

G3 其他指数公司（9 条）
   - MSCI：China Value Weighted、USA 50（msci.com 的 index end of day 页面，免费注册后可导出）
   - 富时罗素：亚太低碳精选、沙特阿拉伯（lseg.com/ftse-russell 注册后看历史数据）
   - 新交所 iEdge：Emerging Asia Select 50、泛东南亚科技 ASIATECN
   - 德交所：DAX（stoxx.com 或 dax-indices.com 历史文件；403 时用浏览器打开下载）
   - 东证指数 TPX（JPX 官网，按月历史表；日元，汇率库里已有 100JPY/CNY）
   - 巴西 IBOVESPA（两条日线已核对通过，只缺汇率：取中国外汇交易中心或 B3/巴西央行的 BRL 兑美元或人民币日度汇率，二选一，写明来源）

G4 国内（2 条）
   - 创业板指 399006：国证指数官网（cnindex.com.cn）或深交所官网历史行情导出。库里现有的来自腾讯，不能用来接。
   - 豆粕期货价格指数：大商所官网“指数行情”的历史数据。东财的“豆粕加权”不是这条指数，不用。

优先级：先做首只基金 2016 年及以后上市的 30 条（影响检验段打分）；创业板、标普500能源、恒生中国企业、标普全球石油、标普油气勘探、DAX 这 6 条首只基金上市在 2016 年前，只影响设计期，放最后。

交付（每条指数一份，不改库、不建分支）：
   incoming/grok-d37-index-20261116/
     <container_id>.csv          两列：date, close（原币种，原始点位，不做任何换算）
     sources.csv                 container_id, index_code, source_url, download_time(Asia/Taipei), publish_date, publish_date_url, screenshot_file, note
     screenshots/                下载页面、发布日页面各一张
     MANIFEST.md                 文件清单 + 每个文件的 SHA256；取不到的列出来，写明到了哪一步、卡在哪

完成判据：36 条每条要么有 CSV + 截图 + 发布日，要么写明取不到的原因；MANIFEST 哈希可复算。

========== 第 2 部分：入库和重跑（Dev） ==========

D1 入库：按第四轮的做法只追加（不改已有行），两条日线核对过 0.01% 门槛才入库；汇率（BRL）同样登记来源。记录库 SHA256 前后值。
D2 重跑：S1 设计期和检验段 V0–V4，以及 S1 检验段方案 B（selection=all，节奏 V0）。输出写到 results/v51-diag/d37/round6/，与第四、五轮并列对照（年化、回撤、20 日做对、每年笔数、每年成本）；更新 s1-splice-roster.csv 状态。
D3 S0 V0 检验段在新库上必须和第五轮逐位一致（新数据只进 S1 打分）。
   改动面：只写 results/v51-diag/d37/ 和库里新增的指数、汇率行；不改冻结代码、不碰 results/v5/LOCK。

========== 第 3 部分：签收（Reviewer） ==========

R1 抽查：至少 8 条（每个指数公司至少 1 条）对照截图和官网复核发布日与 3 个点位。
R2 复算：S0 V0 一致性；S1 V0 和方案 B 的年化、笔数、成本独立复算。
R3 结论：approve / approve_with_follow_up / return_to_planning。

纪律不变：诊断，只报告，不改判；不移动任何 tag；不强推、不改写 main。
```

---

## 之后

签收后 Orchestrator 把第六轮数字写进《v5.1 换手深挖》，与方案 B 一起给 Owner 看，再定 v6 的“保险”方案（D37“之后”一节）。
