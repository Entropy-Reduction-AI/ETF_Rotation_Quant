"""Manual component anchors @59a1b56 (D42 rev j)."""
from __future__ import annotations

_SPECS = {
    (1, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§1 details 1.4', "quote": "| 每个名额选几只 | 3 |"},
            {"location": '§1 details 1.4', "quote": "| 美股比例 | 60% |"},
            {"location": '§1 details 1.4', "quote": "| 确认紧张的票数 | ≥ 2 |"},
        ],
    },
    (1, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§1 details 1.4', "quote": "| 回看期 | 12−1 |"},
            {"location": '§1 details 1.4', "quote": "| 均线 | 10 个月 |"},
        ],
    },
    (1, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§1 details 1.4', "quote": "| 宽度、TRIN 门槛 | 1/3、2/3 分位 |"},
            {"location": '§1 details 1.4', "quote": "| TRIN 平滑 | 10 日均值 |"},
            {"location": '§1 details 1.4', "quote": "| 最少历史 | 分位 24 个月"},
            {"location": '§1 details 1.4', "quote": "| 连续性版 | 前一半、200 天 |"},
        ],
    },
    (2, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§2 details', "quote": "成交**：信号日的下一个交易日收盘价成交"},
        ],
    },
    (2, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§2 details', "quote": "选溢价偏离最小的"},
        ],
    },
    (2, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§2 details', "quote": "给下一名候选，再不行给母指数"},
        ],
    },
    (2, 'component', 3): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§2 details', "quote": "标普500（SPX）"},
        ],
    },
    (3, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§3.5', "quote": "| 1 | **超额只有一个来源** | A 股挑选平均约为 0（沪深300 行业、申万一级上 12−1 甚至为负，§4 第 7 条），超额几乎全靠美股挑选；美股挑选一旦在检验段失灵，判据 ④ 就过不了 | 判据 ④；对照“同结构等权” |"},
        ],
    },
    (3, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§3.5', "quote": "| 2 | **能买到的抓不到能排名的** | 美股领头者常是溢价高的 QDII，换成同指数其他基金或下一名后，可交易池少抓一截 | 可交易池报告；疼痛表“稀缺 QDII” |"},
        ],
    },
    (3, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§3.5', "quote": "| 3 | **A 股把握 p 学错** | A 股从 0.5 起学，2016 年后紧张月领头者的表现若和 2015 年前不同，p 会滞后 | 疼痛表“V 型急跌急涨”；附表 B 的 p 轨迹 |"},
        ],
    },
    (3, 'component', 3): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§3.5', "quote": "| 4 | **V 型急跌急涨** | 紧张时减了仓，反弹时回来得晚 | 疼痛表；判据 ② 只量防守成本 |"},
        ],
    },
    (3, 'component', 4): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§3.5', "quote": "| 5 | **候选池变了** | 检验段 A 股候选随主题发布增加到四十个左右，同一行业的主题变多，去重和挑选的行为可能和设计期不同 | 附表 B 逐年可参选个数；稳健性 S3–S5 |"},
        ],
    },
    (4, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§4 details 七条', "quote": "| 2 | **美国 49 行业 2016–2026**"},
        ],
    },
    (4, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§4 details 七条', "quote": "| 5 | **常识性的市场历史**：2016–2025 年美股大幅跑赢 A 股"},
        ],
    },
    (4, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§4 details 七条', "quote": "| 1 | **项目池 ≤ 2015 的全部预演结果**"},
        ],
    },
    (4, 'component', 3): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§4 details 七条', "quote": "| 3 | **QDII 溢价 2016 年以后的分布**"},
        ],
    },
    (4, 'component', 4): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§4 details 七条', "quote": "| 4 | **v2、v3–v5.1 在 2016-01 → 2026-09 的一次性检验结果**"},
        ],
    },
    (4, 'component', 5): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§4 details 七条', "quote": "| 6 | **A 股选人的试验次数约 12 种**"},
        ],
    },
    (4, 'component', 6): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§4 details 七条', "quote": "| 7 | **冻结前新增的三项检验**"},
        ],
    },
    (5, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§5 details 5.3', "quote": "| ① 底线 | 回撤 ≤ 40% |"},
            {"location": '§3 details 3.2', "quote": "第 ① 条底线大概率过（约八成）"},
        ],
    },
    (5, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§5 details 5.3', "quote": "| ② 保费 | ≤ 4 点 |"},
            {"location": '§3 details 3.2', "quote": "第 ② 条保费（只量防守成本）约八成五"},
        ],
    },
    (5, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§5 details 5.3', "quote": "| ③ 不输增强基准 | 高于 K2A |"},
            {"location": '§3 details 3.2', "quote": "第 ③ 条对增强基准约六成"},
        ],
    },
    (5, 'component', 3): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§5 details 5.3', "quote": "| ④ 对同仓位基准 | ≥ 0 |"},
            {"location": '§3 details 3.2', "quote": "第 ④ 条对同仓位基准不低于 0 约五成"},
        ],
    },
    (5, 'component', 4): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§3 details 3.2', "quote": "合起来全部通过的机会约三成"},
        ],
    },
    (6, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§5 details 5.1', "quote": "| **BM-主** | 70% 沪深300 全收益 + 15% 纳指100 全收益 + 15% 标普500 全收益，人民币，每月第一个交易日再平衡 | AGENTS.md 规定的并列基准，逐年列出 |"},
        ],
    },
    (6, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§5 details 5.1', "quote": "| **BM-同仓位** | 40% 沪深300 全收益 + 30% 纳指100 + 30% 标普500，同口径 | 判据 ④；v6 的仓位差 = BM-同仓位 − BM-主，挑选、防守、成本的合计 = v6 − BM-同仓位 |"},
        ],
    },
    (6, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§5.1 details 基准表', "quote": "| **增强基准** | K2A（D39，美股 50%） | 判据 ③ |"},
            {"location": '§5.3 details 判据表', "quote": "| ③ 不输增强基准 | 高于 K2A | 同一窗口、同一口径（指数池、人民币、扣成本）：v6 的年化 ÷ 最大回撤的绝对值，高于 K2A 的同一比值 | D38 第 18 行“赢过增强基准”；Owner 2026-11-23 定（D40-14） |"},
            {"location": 'D39-3（operations/planning/2026-11-17-d39-insurance-layer-k2a.md）', "quote": "D39-3 | **v6 的保险层用 K2A**：K2 的规则只作用在 A 股腿上（月末低于 10 个月均线换国债；仓位 = 长期波动 ÷ 近 20 日波动，最多 1，每周看，变化不到 10 个点不动），美股腿一直持有。参数全部是文献默认值，不新增自由度"},
            {"location": 'docs/owner/v6-preflight-forecast.md D40-14（prereg Metadata 依据）', "quote": "对增强基准比年化 ÷ 最大回撤"},
        ],
        "reviewer_notes": "页首「A 股 50｜美股 50」为 K2A 摘要：US 50% 见 §5.1（D39）；A 股腿定义见 D39-3（非 v6 的 40/60，D40-4）",
    },
    (7, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§5.3', "quote": "- **结果怎么用**：通过 → 进入 6 个月前向模拟盘（D27），小资金起步需 Owner 另批；不通过 → 如实记录、关闭，新想法另起版本并注明第几次尝试。"},
        ],
    },
    (7, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§5.3', "quote": "- **结果怎么用**：通过 → 进入 6 个月前向模拟盘（D27），小资金起步需 Owner 另批；不通过 → 如实记录、关闭，新想法另起版本并注明第几次尝试。"},
        ],
    },
    (8, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§6 details', "quote": "| A 股大牛市 | 基准 70% 在 A 股，我们只有 40% | **2006–2010 每年少约 9 点**（设计期） | 单年落后 BM-主超过 20 点 |"},
        ],
    },
    (8, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§6 details', "quote": "| V 型急跌急涨 | 紧张时减了仓，反弹时回来得晚 | **合成 V 型每年落后约 15 点**（短期年化） | 见底后 3 个月股票仓位仍低于一半 |"},
        ],
    },
    (8, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§6 details', "quote": "| 突发急跌 | 每月看一次来不及 | **较差的十分之一约剩 58.8 万** | 低于 55 万 |"},
        ],
    },
    (8, 'component', 3): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§6 details', "quote": "| 挑选没有动量的年份 | 前 3 只是噪声，多付换手 | **每年少约 1.6 点** | 连续 3 年挑选部分（对同结构等权）为负 |"},
        ],
    },
    (8, 'component', 4): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§6 details', "quote": "| A 股挑选分阶段 | 结构市里 12−1 有效，轮动和崩盘时反噬 | **两段各约 ±16 万**：2011–13 每年 +16.9、2014–15 每年 −21.1（40 万本金，只看挑选层） | 单年 A 股挑选部分低于 −25 点 |"},
        ],
    },
    (8, 'component', 5): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§3 预测表单位与打折（details 3.1）', "quote": "单位：每年比基准多几个百分点。来自历史数据的超额已打五折，再按候选个数打六折；成本按单边 0.2%。"},
            {"location": '§6 八种情形 details', "quote": "| 试了很多种防守和选法 | 设计期挑出来的最好结果有挑选偏差 | **已按打折处理** | 检验段明显低于预测下限，先查是否偏差所致 |"},
        ],
    },
    (8, 'component', 6): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§6 details', "quote": "| 稀缺 QDII 溢价消失 | 额度放开时一次性损失 | **约 1.8 万**（常态溢价约 9%、单只 20 万，D40-14 不另设上限） | 单次损失超过组合的 3% |"},
        ],
    },
    (8, 'component', 7): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§6 details', "quote": "| 换手和成本 | 两个名额每月换人 | **每年约 1.0–1.1 点**（附表 B 按设计期换手重估约 1.5 点，2.2 版补） | 每年成本超过 2 点 |"},
            {"location": '附表B md', "quote": "每年约 1.5 点成本，高于预演估的 1.0–1.1 点"},
        ],
    },
    (9, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§7 details 四步', "quote": "通过后才进入模拟盘"},
        ],
    },
    (9, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§7 details 四步', "quote": "至少 6 个月"},
        ],
    },
    (9, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§7 details 条款表 D42-5', "quote": "| **别的市场检验**（D42-5） | 一次性检验通过后、上线前，把一个名额的规则原样搬到一个没看过的市场，用该市场能取到的全部历史跑一次；市场在冻结后、看任何结果之前由 Owner 选定（候选：欧洲 STOXX 600 超级行业，母指数 STOXX 600；日本 TOPIX-17 行业，母指数 TOPIX）。没有行业成交额时 TRIN 一票缺席，只用均线、宽度两票，两票都中才算紧张；把握 p 从 0.5 起。计 1 次试验 | 挑选（前 3 对同结构等权）为正且防守保费不超过 4 点，记为“支持”；否则结论降一级，上线前需 Owner 另批 |"},
            {"location": 'D42-5 planning', "quote": "D42-5 | **上线前在别的市场检验一次**（选项 2A）：把一个名额的规则原样搬到一个没看过的市场，只报告。市场在冻结后、看任何结果之前由 Owner 选定"},
        ],
    },
    (9, 'component', 3): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§7 details 四步 closing D42-4', "quote": "上线：模拟盘之后，小资金起步需 Owner 另批（§5.3“结果怎么用”）；Owner 看着 v6 和现行配置在模拟盘、检验段、设计期的逐项比较拍板，不设“6 个月不差于现行配置”的门槛（D42-4）。"},
            {"location": 'D42-4 planning', "quote": "豁免 D27-5 的“6 个月并行模拟不差于它”这一上线门槛"},
        ],
    },
    (10, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§7 details 条款表', "quote": "| **影子：结构市才挑选**（D38 第 54 行 B2） | A 股名额候选里站上 10 个月均线的比例处在到当时为止最低三分之一时用 12−1 前 3，否则按标签等权持有全部候选 | 只记录，不交易 |"},
        ],
    },
    (10, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§7 details D42-4', "quote": "| **对照：现行配置**（D42-4） | 模拟盘每月同次记录现行配置（`config/portfolio.toml`）的持仓与净值 | 只报告；上线时 Owner 看逐项比较拍板 |"},
            {"location": '§5.2 D42-8 现行配置', "quote": "| 现行配置 | `config/portfolio.toml`（D5、D7）全部字段，用 `src/portfolio` 现有代码跑，不另写简化版：A 股 70%（16 个容器等权）、海外 30%（纳指100、标普500 各半），阀门关闭（D7），月末出信号、下一交易日收盘成交，单边成本 0.05%。回测走 `replicate.py` 的 `daily_book`（D5 签收的复现口径，用容器指数）；7.5% 偏离带、溢价上限 10%、主备基金、净值滞后 2 天、一手 100 份要用基金行情和净值，只在模拟盘按 `target.py` 执行，回测报告写明这几项缺席（D42-8） | 和在跑的策略逐项比：赢在哪、输在哪（D27-5、D42-4）；只报告 |"},
            {"location": '§5.2 D42-8 A1', "quote": "| A1 | 原样继承 v4 §7.4 附表 A 和该节执行段落（D42-8）：每个月末（每个自然月最后一个上交所交易日），标普500 全收益过去 12 个月收益高于现金，就在标普500 全收益和沪深300 全收益里拿过去 12 个月收益更高的一个全仓，否则全仓 10 年国债财富指数；下一个上交所交易日收盘成交；数据不足时、成本、收盘时点、汇率、现金都同 v4；U-指数口径 | 同行（D42-6）；只报告 |"},
            {"location": '§5.2 D42-8 A2', "quote": "| A2 | 同上原样继承（D42-8）：沪深300 全收益、标普500 全收益、恒生、10 年国债财富指数、黄金 Au99.99 各 1/5；每个月末，这一份的月末收盘**严格高于**过去 10 个月末收盘的简单平均才持有，等于或低于就这一份拿现金；不足 10 个月末收盘的那一份拿现金；U-指数口径 | 同行（D42-6）；只报告 |"},
            {"location": '§5.2 D42-8 ledgers', "quote": "设计期引用 v4 账本 U-指数行（`results/v4/r5/design/A1/index/`、`A2/index/`，summary 记的 net_sha256 为 3c371162…、cf3091d5…）；检验段引用 v5 一次性检验已签收的 U-指数净值（`results/v5/oneshot/index/A1/`、`A2/`，2016-01-04 → 2026-09-30，net_sha256 为 c9c883c5…、713d9816…）；不计试验。"},
            {"location": '§4.1 #8 D42-9', "quote": "| 8 | **欧洲、日本以前的接触**（D42-5 写定之前；Owner 2026-11-25 书面确认本人没看过两地行业层的走势或回测，D42-9）：日经225 价格指数 1988–2015 用在 v5.1 长历史复核和 D38 预演长历史回放（大盘层的 K0–K2 防守）；EWJ、VGK、FEZ、EWG、EWU、EWQ 是 v5.1 别的市场池 G 的容器（2003-07 → 2026-09，跑的是 v5.1、E2 式、A1）；东证指数、DAX 的 QDII 在 A 股项目池里，D37 为拼接取过 DAX 日线（1999 起）和东证资料页。STOXX 600 超级行业、TOPIX-17 行业的数据从未下载，也没有在欧洲、日本数据上跑过任何 v6 规则 | 两地大盘走势都见过，日本的大盘均线防守 1988–2015 已看过，欧洲没有；行业层两地都没看过 | 称“别的市场检验”，不称样本外 |"},
            {"location": '§9.2 #8 D42-8 D42-9', "quote": "| 8 | R1b 对 D42 增量的两项：别的市场写定前的接触；A1、A2、现行配置的执行口径 | Owner、Orchestrator | 已完成 | **已完成（2026-11-25，D42-8、D42-9）**：§4 第 8 条照实写明、Owner 书面确认；§5.2 写死口径并引用已签收账本 |"},
        ],
    },
    (10, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§7 details 暂停', "quote": "| **暂停** | 任一时点跌破 60 万底线，或连续 6 个月对同仓位基准累计落后超过 6 点 | 暂停并报告 Owner |"},
        ],
    },
    (11, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§8 details 陷阱表', "quote": "| **主题指数回填** |"},
        ],
    },
    (11, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§8 details', "quote": "| **指数与 ETF 的差异** |"},
            {"location": '§8 details', "quote": "| **腾讯减法 qfq** |"},
            {"location": '§8 details', "quote": "| **份额折算假跳空** |"},
        ],
    },
    (11, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§8 details', "quote": "| **美股代理与 QDII** |"},
            {"location": '§8 details', "quote": "| **申万一级的历史点位** |"},
        ],
    },
    (12, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§9.1', "quote": "1. **Owner 看初稿**：已确认 §9.2 第 6 条三项（D40-14）。"},
        ],
    },
    (12, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§9.1', "quote": "2. **Reviewer R1**：逐条核对设计评审、§1.4 计数、§4 已看信息；Orchestrator 闭合后 Reviewer R1b（当前所在步骤，见页首“进度”）。"},
            {"location": '§9 节标题', "quote": "## §9 运行纪律与冻结前待办：冻结前的 7 件待办全部完成，等 Reviewer R1b 后请你批准冻结"},
        ],
        "reviewer_notes": "路线表「R1｜Reviewer｜已完成」：R1 动作见 §9.1#2；「已完成」由 §9 标题与 R1b 为当前步共同推出",
    },
    (12, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§9 段首 blockquote', "quote": "> **7 件待办全部完成（附表 A、B 与 D42 于 2026-11-24 写入）；行业标签在看任何检验段收益之前已补齐；冻结后不改任何规则（程序错误除外）。**"},
            {"location": '§9.2 #7 D42', "quote": "| 7 | Owner 确认：D27-5 两项怎么写进预注册；补回 A1、A2 | Owner | 已完成 | **已完成（2026-11-24，D42-4 至 D42-7）**：现行配置作为对照、豁免 6 个月“不差于”门槛；上线前别的市场检验；A1、A2 写回 §5.2；报告四张图 |"},
        ],
    },
    (12, 'component', 3): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§9.1', "quote": "2. **Reviewer R1**：逐条核对设计评审、§1.4 计数、§4 已看信息；Orchestrator 闭合后 Reviewer R1b（当前所在步骤，见页首“进度”）。"},
            {"location": 'Metadata 进度表', "quote": "| 第 2.3 版（待冻结）：冻结前待办全部完成；D42 已写入；待 Reviewer R1b。 | 100 万分成 A 股 40 万、美股 60 万两个名额。每月各选最强 3 只等分；只在确认紧张时按把握 p 减仓。超额主要靠美股挑选，v6 的主要价值是控制回撤。 | 现在不用操作。Reviewer R1b 通过后，请你批准冻结（§9.1 第 3 步）。 |"},
        ],
    },
    (12, 'component', 4): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§9.1', "quote": "3. **冻结**：`milestone/v6-prereg-freeze`，由 Cloud Agent 按 Owner 指令打。"},
            {"location": 'Metadata 进度表', "quote": "Reviewer R1b 通过后，请你批准冻结（§9.1 第 3 步）。"},
        ],
    },
    (12, 'component', 5): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§9.1', "quote": "4. **实现与复算**：Dev 在 `src/v6/`、`config/v6/` 实现；Reviewer 独立实现复算设计期整套和两个月份示例（逐位一致），并复现 §3.2 合成行情。"},
        ],
    },
    (12, 'component', 6): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§9.1', "quote": "6. **一次性检验**：Owner 批准后跑一次，出报告并对账。"},
        ],
    },
    (12, 'component', 7): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§9.1', "quote": "7. **前向模拟盘**：见 §7。"},
            {"location": '§7', "quote": "通过后才进入模拟盘"},
        ],
    },
    (13, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '附表 A 美股明细', "quote": "| SPX（母） | … | 同一指数 |"},
            {"location": '附表 A 美股明细', "quote": "| NDX | … | 同一指数 |"},
            {"location": '附表 A 美股明细', "quote": "| DJIA | … | 同一指数 |"},
        ],
    },
    (13, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '附表 A 美股明细', "quote": "| XLK | … | 相近指数 |"},
            {"location": '附表 A 美股明细', "quote": "| XLV | … | 相近指数 |"},
            {"location": '附表 A 美股明细', "quote": "| XLE | … | 相近指数 |"},
        ],
    },
    (13, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '附表 A 美股明细', "quote": "| XLP | … | 无场内基金 |"},
            {"location": '附表 A 美股明细', "quote": "| XLF | … | 无场内基金 |"},
            {"location": '附表 A 美股明细', "quote": "| XLI | … | 无场内基金 |"},
            {"location": '附表 A 美股明细', "quote": "| XLB | … | 无场内基金 |"},
            {"location": '附表 A 美股明细', "quote": "| XLU | … | 无场内基金 |"},
        ],
    },
    (14, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '附表 A A股按组', "quote": "| 宽基 | 沪深300（母，2005-04-08）、中证500"},
        ],
    },
    (14, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '附表 A A股按组', "quote": "| 红利 | 中证红利（2008-05-26）、上证红利"},
        ],
    },
    (14, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '附表 A A股按组', "quote": "| 中证全指一级行业 | 能源、原材料、工业、可选消费"},
        ],
    },
    (14, 'component', 3): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '附表 A 主题：医药消费', "quote": "300 医药卫生（2007-07-02）"},
            {"location": '附表 A 主题：科技', "quote": "半导体材料设备"},
            {"location": '附表 A 主题：周期', "quote": "有色金属（2012-05-09）"},
            {"location": '附表 A 主题：金融地产', "quote": "银行、全指证券公司、全指房地产"},
            {"location": '附表 A 主题：制造与其他', "quote": "军工（2013-12-26）、机器人"},
        ],
        "reviewer_notes": '组件用短名；各主题行在 A 股按组明细',
    },
    (14, 'component', 4): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '附表 A 文后说明', "quote": "7 个一级行业（通信服务、能源、医药卫生、工业、信息技术、主要消费、公用事业）"},
            {"location": '附表 A 41 明细', "quote": "| 全指通信服务 | … | 无场内基金 |"},
            {"location": '附表 A 41 明细', "quote": "| 全指能源 | … | 无场内基金 |"},
            {"location": '附表 A 41 明细', "quote": "| 全指医药卫生 | … | 无场内基金 |"},
            {"location": '附表 A 41 明细', "quote": "| 全指工业 | … | 无场内基金 |"},
            {"location": '附表 A 41 明细', "quote": "| 全指信息技术 | … | 无场内基金 |"},
            {"location": '附表 A 41 明细', "quote": "| 全指主要消费 | … | 无场内基金 |"},
            {"location": '附表 A 41 明细', "quote": "| 全指公用事业 | … | 无场内基金 |"},
        ],
    },
}

def manual_anchor(table_index: int, table_kind: str, row_index: int, row_text: str) -> dict:
    spec = _SPECS.get((table_index, table_kind, row_index))
    if not spec:
        return {
            "verdict": "review_incomplete",
            "normative_sources": [],
            "reviewer_notes": f"Missing {table_index}/{table_kind}/{row_index}",
            "automated_anchor_forbidden": True,
        }
    return {**spec, "automated_anchor_forbidden": True}

