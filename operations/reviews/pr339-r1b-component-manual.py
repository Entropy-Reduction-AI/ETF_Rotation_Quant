"""Manual component anchors — generated structure, quotes from 653de22 prereg."""
from __future__ import annotations

_SPECS = {
    (1, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§1 details 1.4', "quote": "| 每个名额选几只 | 3 |"},
            {"location": '§1 details 1.4', "quote": "| 美股比例 | 60% |"},
            {"location": '§1 details 1.4', "quote": "| 确认紧张的票数 | ≥ 2 |"},
        ],
        "reviewer_notes": '3 = 计 1/2/3 rows',
    },
    (1, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§1 details 1.4', "quote": "| 回看期 | 12−1 | Jegadeesh"},
            {"location": '§1 details 1.4', "quote": "| 均线 | 10 个月 | Faber"},
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
            {"location": '§2 details 执行四步', "quote": "成交**：信号日的下一个交易日收盘价成交，**只用场内基金"},
            {"location": '§2 details 规则表', "quote": "| 成交 | 信号日的下一个交易日收盘价成交 |"},
        ],
    },
    (2, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§2 details 执行四步', "quote": "**选溢价偏离最小的**"},
            {"location": '§2 details 规则表', "quote": "高 5 个点以上不买，换同指数偏离最小的一只"},
        ],
    },
    (2, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§2 details 规则表', "quote": "都不行时给下一名候选，再不行给母指数"},
            {"location": '§2 details 执行四步', "quote": "都不行时给下一名候选，再不行给母指数"},
        ],
    },
    (2, 'component', 3): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§1 details 1.1', "quote": "| 美股（60%） | 标普500（SPX） |"},
            {"location": '§1 details 1.1', "quote": "| A 股（40%） | 沪深300 |"},
            {"location": '§2 details 规则表', "quote": "再不行给母指数"},
        ],
        "reviewer_notes": 'SPX/沪深300 来自名额母指数列；退路句在 §2',
    },
    (3, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§4 details 七条', "quote": "| 2 | **美国 49 行业 2016–2026**"},
        ],
    },
    (3, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§4 details 七条', "quote": "| 5 | **常识性的市场历史**：2016–2025 年美股大幅跑赢 A 股"},
        ],
    },
    (3, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§4 details 七条', "quote": "| 1 | **项目池 ≤ 2015 的全部预演结果**"},
        ],
    },
    (3, 'component', 3): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§4 details 七条', "quote": "| 3 | **QDII 溢价 2016 年以后的分布**"},
        ],
    },
    (3, 'component', 4): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§4 details 七条', "quote": "| 4 | **v2、v3–v5.1 在 2016-01 → 2026-09 的一次性检验结果**"},
        ],
    },
    (3, 'component', 5): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§4 details 七条', "quote": "| 6 | **A 股选人的试验次数约 12 种**"},
        ],
    },
    (3, 'component', 6): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§4 details 七条', "quote": "| 7 | **冻结前新增的三项检验**"},
        ],
    },
    (4, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§5 details 5.3', "quote": "| ① 底线 | 回撤 ≤ 40% |"},
            {"location": '§3 details 3.2', "quote": "第 ① 条底线大概率过（约八成）"},
        ],
    },
    (4, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§5 details 5.3', "quote": "| ② 保费 | ≤ 4 点 |"},
            {"location": '§3 details 3.2', "quote": "第 ② 条保费（只量防守成本）约八成五"},
        ],
    },
    (4, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§5 details 5.3', "quote": "| ③ 不输增强基准 | 高于 K2A |"},
            {"location": '§3 details 3.2', "quote": "第 ③ 条对增强基准约六成"},
        ],
    },
    (4, 'component', 3): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§5 details 5.3', "quote": "| ④ 对同仓位基准 | ≥ 0 |"},
            {"location": '§3 details 3.2', "quote": "第 ④ 条对同仓位基准不低于 0 约五成"},
        ],
    },
    (4, 'component', 4): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§3 details 3.2', "quote": "合起来全部通过的机会约三成"},
            {"location": '§5 details 5.3', "quote": "四条都要过，合起来约三成"},
        ],
    },
    (5, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§5 details 5.1', "quote": "**BM-主** | 70% 沪深300 全收益 + 15% 纳指100"},
        ],
    },
    (5, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§5 details 5.1', "quote": "**BM-同仓位** | 40% 沪深300 全收益 + 30% 纳指100 + 30% 标普500"},
        ],
    },
    (5, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§5 details 5.1', "quote": "**增强基准** | K2A（D39，美股 50%）"},
        ],
    },
    (6, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§7 details 四步', "quote": "2. **模拟盘**：按冻结规则每月出持仓，**至少 6 个月**"},
            {"location": '§7 details 条款表', "quote": "一次性检验通过后，按冻结规则每月出持仓，至少 6 个月（D27）"},
        ],
    },
    (6, 'component', 1): {
        "verdict": 'review_incomplete',
        "normative_sources": [],
        "reviewer_notes": '653 @653de22 无折叠条款承载「不通过→关闭」；仅组件表。8f7ffbae §5.3 曾有「结果怎么用」子弹（历史，不作 653 正文锚）',
    },
    (7, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§6 details 疼痛表', "quote": "| A 股大牛市 | 基准 70% 在 A 股，我们只有 40% |"},
        ],
    },
    (7, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§6 details', "quote": "| V 型急跌急涨 |"},
            {"location": '§6 details', "quote": "| 突发急跌 |"},
        ],
    },
    (7, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§6 details', "quote": "| 挑选没有动量的年份 |"},
            {"location": '§6 details', "quote": "| A 股挑选分阶段 |"},
            {"location": '§6 details', "quote": "| 试了很多种防守和选法 |"},
        ],
    },
    (7, 'component', 3): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§6 details', "quote": "| 稀缺 QDII 溢价消失 |"},
            {"location": '§6 details', "quote": "| 换手和成本 |"},
        ],
    },
    (7, 'companion_visual', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§6 details 八种情形原文', "quote": "| A 股大牛市 |"},
        ],
    },
    (7, 'companion_visual', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§6 details 八种情形原文', "quote": "| V 型急跌急涨 |"},
        ],
    },
    (7, 'companion_visual', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§6 details 八种情形原文', "quote": "| 突发急跌 |"},
        ],
    },
    (7, 'companion_visual', 3): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§6 details 八种情形原文', "quote": "| 挑选没有动量的年份 |"},
        ],
    },
    (7, 'companion_visual', 4): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§6 details 八种情形原文', "quote": "| A 股挑选分阶段 |"},
        ],
    },
    (7, 'companion_visual', 5): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§6 details 八种情形原文', "quote": "| 稀缺 QDII 溢价消失 |"},
        ],
    },
    (7, 'companion_visual', 6): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§6 details 八种情形原文', "quote": "| 试了很多种防守和选法 |"},
        ],
    },
    (7, 'companion_visual', 7): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§6 details 八种情形原文', "quote": "| 换手和成本 |"},
            {"location": '附表 B 文', "quote": "A 股名额每年 6.6 倍，美股名额 5.9 倍；按单边 0.2% 每年约 1.5 点成本"},
            {"location": 'results/v6-preflight/v6-appendix-b.json', "quote": "收益拆分.成本.2006–15 = -1.48"},
        ],
    },
    (8, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§7 details 条款表', "quote": "| **前向模拟盘** | 一次性检验通过后"},
        ],
    },
    (8, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§7 details 四步', "quote": "2. **模拟盘**：…**至少 6 个月**；每月对账预测表各项和疼痛表"},
        ],
    },
    (8, 'component', 2): {
        "verdict": 'review_incomplete',
        "normative_sources": [],
        "reviewer_notes": "653 折叠条款无「小资金/另批」句；仅 §5/§7 组件表与 8f7ffbae §5.3「结果怎么用」历史句",
    },
    (9, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§7 details 条款表', "quote": "| **影子：结构市才挑选**"},
        ],
    },
    (9, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§7 details 四步', "quote": "4. **暂停**：跌破 60 万，或连续 6 个月对同仓位基准累计落后超过 6 点"},
        ],
    },
    (10, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§8 details 陷阱表', "quote": "| **主题指数回填** |"},
        ],
    },
    (10, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§8 details', "quote": "| **指数与 ETF 的差异** |"},
            {"location": '§8 details', "quote": "| **腾讯减法 qfq** |"},
            {"location": '§8 details', "quote": "| **份额折算假跳空** |"},
        ],
    },
    (10, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§8 details', "quote": "| **美股代理与 QDII** |"},
            {"location": '§8 details', "quote": "| **申万一级的历史点位** |"},
        ],
    },
    (11, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§9 details 9.1', "quote": "1. **Owner 看初稿**：已确认 §9.2 第 6 条三项"},
        ],
    },
    (11, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§9 details 9.1', "quote": "2. **Reviewer R1**"},
        ],
    },
    (11, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§9 details 9.2', "quote": "冻结前待办：6 件全部完成"},
            {"location": '§9 details 9.2', "quote": "| 1 | 行业标签补齐检验段全部 A 股候选 | … | 已完成 |"},
            {"location": '§9 details 9.2', "quote": "| 6 | Owner 确认：单只上限、判据 ② 的算法、判据 ③ ④ 的门槛 | … | 已完成 |"},
        ],
        "reviewer_notes": '组件「冻结前6件待办」对 §9.2 六行完成态',
    },
    (11, 'component', 3): {
        "verdict": 'review_incomplete',
        "normative_sources": [],
        "reviewer_notes": '组件路线图「R1b|现在」无 §9.2 待办表或 9.1 有序列表等价句；流程态叙述非阈值条款',
    },
    (11, 'component', 4): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§9 details 9.1', "quote": "3. **冻结**：`milestone/v6-prereg-freeze`"},
        ],
    },
    (11, 'component', 5): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§9 details 9.1', "quote": "4. **实现与复算**：Dev 在 `src/v6/`"},
        ],
    },
    (11, 'component', 6): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§9 details 9.1', "quote": "6. **一次性检验**：Owner 批准后跑一次"},
        ],
    },
    (11, 'component', 7): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '§9 details 9.1', "quote": "7. **前向模拟盘**：见 §7"},
        ],
    },
    (12, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '附表 A 美股明细', "quote": "| SPX（母） | … | 同一指数 |"},
            {"location": '附表 A 美股明细', "quote": "| NDX | … | 同一指数 |"},
            {"location": '附表 A 美股明细', "quote": "| DJIA | … | 同一指数 |"},
        ],
    },
    (12, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '附表 A 美股明细', "quote": "| XLK | … | 相近指数 |"},
            {"location": '附表 A 美股明细', "quote": "| XLV | … | 相近指数 |"},
            {"location": '附表 A 美股明细', "quote": "| XLE | … | 相近指数 |"},
        ],
    },
    (12, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '附表 A 美股明细', "quote": "| XLP | … | 无场内基金 |"},
            {"location": '附表 A 美股明细', "quote": "| XLF | … | 无场内基金 |"},
            {"location": '附表 A 美股明细', "quote": "| XLI | … | 无场内基金 |"},
            {"location": '附表 A 美股明细', "quote": "| XLB | … | 无场内基金 |"},
            {"location": '附表 A 美股明细', "quote": "| XLU | … | 无场内基金 |"},
        ],
    },
    (13, 'component', 0): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '附表 A A股按组', "quote": "| 宽基 | 沪深300（母，2005-04-08）、中证500"},
        ],
    },
    (13, 'component', 1): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '附表 A A股按组', "quote": "| 红利 | 中证红利（2008-05-26）、上证红利"},
        ],
    },
    (13, 'component', 2): {
        "verdict": 'anchored',
        "normative_sources": [
            {"location": '附表 A A股按组', "quote": "| 中证全指一级行业 | 能源、原材料、工业、可选消费"},
        ],
    },
    (13, 'component', 3): {
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
    (13, 'component', 4): {
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
            "reviewer_notes": f"Missing manual spec for {table_index}/{table_kind}/{row_index}",
            "automated_anchor_forbidden": True,
        }
    return {**spec, "automated_anchor_forbidden": True}

