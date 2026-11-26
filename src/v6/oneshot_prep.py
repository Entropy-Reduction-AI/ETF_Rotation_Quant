"""一次性检验的接线。不算考试，不读 2016 年以后的行情文件。

判定窗口和四条判据来自冻结稿 §5。三级结论和 D50-4 = B 来自 D50 第 3 稿
（#388 头 2db459de，已在当前 main）。全段只报告，来自 D49。
调用方把日收益放进内存；本模块不打开行情库，也不写 results/v6/oneshot/。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.report.metrics import cagr, max_drawdown, monthly_returns, yearly_returns
from src.v6.guard import DESIGN_END_TEXT, IsolationError, assert_sql
from src.v6.health import A1_SHA, A2_SHA, COST, SLEEVE_WEIGHT
from src.v6.health_random import SEED, TRIALS, annualize, beat_median_share, rank_percentile

EXAM_START = "2016-01-01"
EXAM_END = "2026-09-30"
FULL_START = "2006-01-01"
DESIGN_START = "2006-01-01"
D50_4 = "B"
JUDGMENT_WINDOW = "检验段"
JUDGMENT_POOL = "指数池"
JUDGMENT_PATH = "连续运行截出"
RESTART_REASON = (
    "冻结的 slot 从给定序列的第一天累积把握 p、仓位和国债均线，"
    "没有在 2016-01 把状态清掉。D49-1：只有冻结代码本身在 2016-01 重新起步时，"
    "判定才用重新起步。因此判定用连续运行截出的检验段；重新起步只出差异。"
)
ROBUSTNESS = (
    ("S1", "成本加倍（单边 0.4%）"),
    ("S2", "信号日延后 1 个交易日"),
    ("S3", "去掉检验段贡献最大的 1 个候选"),
    ("S4", "去掉检验段贡献最大的 2 个候选"),
    ("S5", "去掉检验段贡献最大的 3 个候选"),
    ("S6", "美股 50%、A 股 50%"),
    ("S7", "每个名额选前 2"),
    ("S8", "紧张门槛改为 3 票全中"),
)
# 冻结稿 §5.4 的改动。数字都是冻结稿写死的，不是拟合出来的。
SCENARIO = {
    "S1": {"成本": COST * 2},
    "S2": {"信号延后交易日": 1},
    "S3": {"去掉贡献最大": 1},
    "S4": {"去掉贡献最大": 2},
    "S5": {"去掉贡献最大": 3},
    "S6": {"美股权重": 0.5, "A股权重": 0.5},
    "S7": {"每个名额只数": 2},
    "S8": {"紧张票数": 3},
}
DRAWDOWN_LIMIT = -0.40
PREMIUM_LIMIT_PP = 4.0
A_WEIGHT = SLEEVE_WEIGHT["A股挑选"]
US_WEIGHT = SLEEVE_WEIGHT["美股挑选"]
BLOCKS = ("分红", "仓位差", "等权倾斜", "挑选", "防守", "成本")
SPANS = (
    ("2006–10", "2006-01-01", "2010-12-31"),
    ("2011–15", "2011-01-01", "2015-12-31"),
    ("2016–20", "2016-01-01", "2020-12-31"),
    ("2021-01→2026-09", "2021-01-01", EXAM_END),
    ("全段", FULL_START, EXAM_END),
)
NAMED_STRESS = (
    ("2008", "2008-01", "2008-12"),
    ("2011", "2011-01", "2011-12"),
    ("2015–16", "2015-01", "2016-12"),
    ("2018", "2018-01", "2018-12"),
    ("2020", "2020-01", "2020-12"),
    ("2022", "2022-01", "2022-12"),
)
EIGHT_LINES = ("v6", "连续性版", "K2A", "A1", "A2", "现行配置", "BM-主", "BM-同仓位")
RANDOM_WINDOWS = (
    ("检验段", EXAM_START, EXAM_END),
    ("全段", FULL_START, EXAM_END),
)
LEDGERS = {
    "A1": {
        "设计期": "results/v4/r5/design/A1/index/net.csv",
        "检验段": "results/v5/oneshot/index/A1/net.csv",
        "设计期sha256": A1_SHA,
        "检验段sha256前缀": "c9c883c5",
    },
    "A2": {
        "设计期": "results/v4/r5/design/A2/index/net.csv",
        "检验段": "results/v5/oneshot/index/A2/net.csv",
        "设计期sha256": A2_SHA,
        "检验段sha256前缀": "713d9816",
    },
}
CUT = pd.Timestamp("2015-12-31")
EXAM_OPEN = pd.Timestamp("2016-01-01")


@dataclass(frozen=True)
class Criteria:
    """四条判据的数。最大回撤用负数，例如 −0.25。超额和保费用百分点。"""

    max_drawdown: float
    premium_pp: float
    ratio: float
    benchmark_ratio: float
    excess_vs_same_pp: float


@dataclass(frozen=True)
class SpanBook:
    """一条组合的日收益。调用方准备，本模块不读盘。"""

    v6: pd.Series
    gross: pd.Series
    undefended: pd.Series
    equal_weight: pd.Series
    bm_main_total: pd.Series
    bm_main_price: pd.Series
    bm_same_total: pd.Series
    bm_same_price: pd.Series
    k2a: pd.Series


def passes(item: Criteria) -> dict[str, bool]:
    premium = item.premium_pp <= PREMIUM_LIMIT_PP
    ratio = item.ratio > item.benchmark_ratio
    if item.premium_pp != item.premium_pp:
        premium = False
    if item.ratio != item.ratio or item.benchmark_ratio != item.benchmark_ratio:
        ratio = False
    return {
        "最大回撤": item.max_drawdown >= DRAWDOWN_LIMIT,
        "保费": premium,
        "年化除以回撤": ratio,
        "对同仓位基准": item.excess_vs_same_pp >= 0.0,
    }


def conclusion(flags: dict[str, bool]) -> str:
    return "通过" if all(flags.values()) else "不通过"


def _delta(main: Criteria, variant: Criteria) -> dict[str, float]:
    return {
        "最大回撤": variant.max_drawdown - main.max_drawdown,
        "保费": variant.premium_pp - main.premium_pp,
        "年化除以回撤": variant.ratio - main.ratio,
        "对同仓位基准": variant.excess_vs_same_pp - main.excess_vs_same_pp,
    }


def sensitivity(main: Criteria, variant: Criteria) -> str:
    """很敏感 = 总结论翻转。只改了值、总结论没翻，记有影响。"""
    main_pass = passes(main)
    variant_pass = passes(variant)
    if conclusion(main_pass) != conclusion(variant_pass):
        return "很敏感"
    if main_pass != variant_pass or main != variant:
        return "有影响"
    return "无变化"


def overall(main: Criteria, variants: dict[str, Criteria]) -> dict:
    """D50-2。主判不通过就不再下降。至少一项翻转才是通过（有条件）。"""
    missing = [code for code, _text in ROBUSTNESS if code not in variants]
    if missing:
        raise IsolationError(f"稳健性缺项：{missing}")
    main_result = conclusion(passes(main))
    details = []
    for code, _text in ROBUSTNESS:
        kind = sensitivity(main, variants[code])
        flags = passes(variants[code])
        details.append({
            "item": code,
            "结论": conclusion(flags),
            "判据": flags,
            "敏感": kind,
            "变化": _delta(main, variants[code]),
        })
    if main_result == "不通过":
        level = "不通过"
    elif any(row["敏感"] == "很敏感" for row in details):
        level = "通过（有条件）"
    else:
        level = "通过"
    return {"主判": main_result, "总结论": level, "稳健性": details}


def downgrade_for_europe(level: str, europe: str) -> str:
    """D50-4 = B。支持不升档；不通过不再降；通过（有条件）再遇不支持 = 不通过。"""
    if D50_4 != "B":
        raise IsolationError("D50-4 不是 B，不能用这套累积降级")
    if europe not in ("支持", "不支持"):
        raise IsolationError(f"欧洲检验只记支持或不支持：{europe}")
    if level not in ("通过", "通过（有条件）", "不通过"):
        raise IsolationError(f"没有这一档结论：{level}")
    if europe == "支持" or level == "不通过":
        return level
    if level == "通过":
        return "通过（有条件）"
    return "不通过"


def europe_after_conditional(level: str | None = None, europe: str | None = None) -> str:
    """没有欧洲检验的结果时不替它填。两边都给出时按 D50-4 = B 降级。"""
    if level is None or europe is None:
        raise IsolationError("欧洲检验还没有结果，不替它填支持或不支持。")
    return downgrade_for_europe(level, europe)


def feed_flip(window: str, pool: str, main: Criteria, variants: dict[str, Criteria]) -> dict:
    """翻转只吃检验段的指数池主判。别的窗口和池子不能进这个函数。"""
    if window != JUDGMENT_WINDOW or pool != JUDGMENT_POOL:
        raise IsolationError(f"{window}、{pool} 只报告，不进翻转判定")
    return overall(main, variants)


def official_verdict(
    lines: dict[tuple[str, str], tuple[Criteria, dict[str, Criteria]]],
    europe: str | None = None,
) -> dict:
    """官方结论只来自检验段指数池。其余线条放在只报告，不改总结论。"""
    key = (JUDGMENT_WINDOW, JUDGMENT_POOL)
    if key not in lines:
        raise IsolationError("翻转判定缺少检验段指数池主判")
    main, variants = lines[key]
    result = feed_flip(JUDGMENT_WINDOW, JUDGMENT_POOL, main, variants)
    if europe is not None:
        result["欧洲"] = europe
        result["总结论"] = downgrade_for_europe(result["总结论"], europe)
    reports = {}
    for label, (other_main, other_variants) in lines.items():
        if label == key:
            continue
        reports["、".join(label)] = overall(other_main, other_variants)
    result["只报告"] = reports
    result["进入翻转"] = ["、".join(key)]
    return result


def run_exam() -> None:
    raise IsolationError(
        "一次性检验未授权。接线可以在授权后使用，"
        "本次不读、不算 2016 年以后的行情、收益、信号、排名或检验结果。"
    )


def main() -> None:
    run_exam()


def market_query(sql: str, params=None):
    """行情查询先过设计期封顶，然后仍然不执行。"""
    assert_sql(sql, params)
    raise IsolationError("一次性检验模块不执行行情查询。")


def open_ledger(path: str) -> None:
    """检验段账本和行情库都不打开。衔接用调用方放在内存里的序列。"""
    text = str(path).replace("\\", "/")
    blocked = ("results/v5/oneshot", "results/v6/oneshot", "market.sqlite", "data_census", "europe-japan")
    if any(piece in text for piece in blocked):
        raise IsolationError(f"不打开 {text}")
    raise IsolationError("账本衔接不读文件。")


def current_configuration(end: str) -> dict:
    """现行配置面板的终点可以写到 2026-09，但本 PR 不调用 package。"""
    if end > DESIGN_END_TEXT:
        raise IsolationError(
            f"现行配置面板接到 {end} 要读 2016 年以后的行情。本 PR 不调用 package，不开考。"
        )
    raise IsolationError("设计期现行配置用 portfolio_design.design_book，这里不重跑。")


def _window(series: pd.Series, start: str, end: str) -> pd.Series:
    window = pd.Series(series, dtype=float).sort_index().loc[start:end].dropna()
    if window.empty:
        raise IsolationError(f"{start} 至 {end} 没有收益")
    return window


def _complete_years(calendar: pd.DatetimeIndex, start: str, end: str) -> list[int]:
    years = []
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    for year, block in pd.Series(1, index=calendar).groupby(calendar.year):
        if block.index.min() >= start_ts and block.index.max() <= end_ts:
            years.append(int(year))
    return years


def _covers(series: pd.Series, year: int, calendar: pd.DatetimeIndex) -> bool:
    block = calendar[calendar.year == year]
    have = series.index[series.index.year == year]
    if len(block) == 0 or len(have) == 0:
        return False
    return have.min() <= block.min() and have.max() >= block.max()


def premium_pp(v6: pd.Series, undefended: pd.Series, bm_main: pd.Series, start: str, end: str) -> float:
    """判据②。不设防守的年收益减 v6，只在 BM-主该自然年收益为正时平均。首尾不满一年的不计。"""
    calendar = pd.DatetimeIndex(pd.Series(v6, dtype=float).dropna().sort_index().index)
    v6_w = _window(v6, start, end)
    plain = _window(undefended, start, end)
    bm = _window(bm_main, start, end)
    covered = _complete_years(calendar, start, end)
    y_v = yearly_returns(v6_w)
    y_p = yearly_returns(plain)
    y_b = yearly_returns(bm)
    gaps = []
    for year in covered:
        if not (_covers(v6_w, year, calendar) and _covers(plain, year, calendar) and _covers(bm, year, calendar)):
            continue
        if year not in y_v or year not in y_p or year not in y_b or y_b[year] <= 0:
            continue
        gaps.append((y_p[year] - y_v[year]) * 100.0)
    if not gaps:
        return float("nan")
    return float(sum(gaps) / len(gaps))


def _ratio(series: pd.Series, start: str, end: str) -> tuple[float, float]:
    window = _window(series, start, end)
    growth = cagr(window)
    depth = max_drawdown(window)["max_drawdown"]
    if depth == 0.0 or depth != depth:
        return growth, float("nan")
    return growth, growth / abs(depth)


def evaluate(book: SpanBook, start: str, end: str) -> Criteria:
    """冻结稿 §5 的四条数。年化是 metrics.cagr，回撤高点不取窗口之前。"""
    _growth, ratio = _ratio(book.v6, start, end)
    _k_growth, k_ratio = _ratio(book.k2a, start, end)
    excess = (_growth - cagr(_window(book.bm_same_total, start, end))) * 100.0
    depth = max_drawdown(_window(book.v6, start, end))["max_drawdown"]
    return Criteria(
        max_drawdown=depth,
        premium_pp=premium_pp(book.v6, book.undefended, book.bm_main_total, start, end),
        ratio=ratio,
        benchmark_ratio=k_ratio,
        excess_vs_same_pp=excess,
    )


def item_result(book: SpanBook, start: str, end: str) -> dict:
    """一条稳健性（或主判）的四条判据和该条自己的结论。"""
    item = evaluate(book, start, end)
    flags = passes(item)
    return {"判据": flags, "结论": conclusion(flags), "数": item}


def _same_days(series: dict[str, pd.Series], start: str, end: str) -> pd.DatetimeIndex:
    frames = [_window(series[name], start, end).rename(name) for name in series]
    joined = pd.concat(frames, axis=1, join="inner").dropna()
    if joined.empty:
        raise IsolationError(f"{start} 至 {end} 没有共同交易日")
    return joined.index


def _cagr_pp(series: pd.Series, index: pd.DatetimeIndex) -> float:
    return cagr(series.reindex(index).astype(float)) * 100.0


def six_blocks(book: SpanBook, start: str, end: str) -> dict[str, float]:
    """D49-3。六块都在同一组交易日上算年化之差，所以相加等于 v6 净减 BM-主全收益。"""
    names = {
        "v6": book.v6,
        "gross": book.gross,
        "undefended": book.undefended,
        "equal_weight": book.equal_weight,
        "bm_main_total": book.bm_main_total,
        "bm_main_price": book.bm_main_price,
        "bm_same_price": book.bm_same_price,
    }
    index = _same_days(names, start, end)
    price_main = _cagr_pp(book.bm_main_price, index)
    total_main = _cagr_pp(book.bm_main_total, index)
    price_same = _cagr_pp(book.bm_same_price, index)
    equal = _cagr_pp(book.equal_weight, index)
    top = _cagr_pp(book.undefended, index)
    gross = _cagr_pp(book.gross, index)
    net = _cagr_pp(book.v6, index)
    parts = {
        "分红": price_main - total_main,
        "仓位差": price_same - price_main,
        "等权倾斜": equal - price_same,
        "挑选": top - equal,
        "防守": gross - top,
        "成本": net - gross,
    }
    parts["和"] = float(sum(parts[name] for name in BLOCKS))
    parts["v6净减BM主全收益"] = net - total_main
    if abs(parts["和"] - parts["v6净减BM主全收益"]) > 1e-8:
        raise IsolationError("六块相加没有等于 v6 净减 BM-主全收益")
    return parts


def fx_layer(rmb: pd.Series, usd: pd.Series, start: str, end: str) -> float:
    """D49-3 的汇率层。不进入六块的和。"""
    index = _same_days({"rmb": rmb, "usd": usd}, start, end)
    return _cagr_pp(rmb, index) - _cagr_pp(usd, index)


def source_reading(design: float, exam: float, segments: list[float]) -> str:
    """D49-8。先符合设计期才有，再看稳定，其余不稳定。数的单位是百分点。"""
    if len(segments) != 4:
        raise IsolationError("读法要四个五年段")
    if design > 0 and (exam < 0 or abs(exam) < 0.5):
        return "设计期才有"
    positive = sum(value > 0 for value in segments)
    negative = sum(value < 0 for value in segments)
    same_sign = (design > 0 and exam > 0) or (design < 0 and exam < 0)
    if (positive >= 3 or negative >= 3) and same_sign:
        return "稳定"
    return "不稳定"


def _year_spans(index: pd.DatetimeIndex) -> list[tuple[str, str, str]]:
    rows = []
    for year in range(2006, 2026):
        start, end = f"{year}-01-01", f"{year}-12-31"
        if year in _complete_years(index, start, end):
            rows.append((str(year), start, end))
    rows.append(("2026年前9个月", "2026-01-01", EXAM_END))
    return rows


def attribution(book: SpanBook, rmb: pd.Series | None = None, usd: pd.Series | None = None) -> dict:
    """D49-2、D49-3。全段和分段并列。这里不出过不过。"""
    design = six_blocks(book, DESIGN_START, DESIGN_END_TEXT)
    exam = six_blocks(book, EXAM_START, EXAM_END)
    span_parts = {label: six_blocks(book, start, end) for label, start, end in SPANS}
    rows = []
    for block in BLOCKS:
        four = [span_parts[label][block] for label, _start, _end in SPANS[:4]]
        row = {
            "块": block,
            "设计期": design[block],
            "检验段": exam[block],
            "读法": source_reading(design[block], exam[block], four),
        }
        for label, _start, _end in SPANS:
            row[label] = span_parts[label][block]
        rows.append(row)
    yearly = []
    index = _same_days({"v6": book.v6}, FULL_START, EXAM_END)
    for label, start, end in _year_spans(index):
        try:
            parts = six_blocks(book, start, end)
        except IsolationError:
            continue
        yearly.append({"年": label, **{name: parts[name] for name in BLOCKS}})
    fx = None
    if rmb is not None and usd is not None:
        fx = {
            "设计期": fx_layer(rmb, usd, DESIGN_START, DESIGN_END_TEXT),
            "检验段": fx_layer(rmb, usd, EXAM_START, EXAM_END),
            "全段": fx_layer(rmb, usd, FULL_START, EXAM_END),
            "进入六块": False,
        }
    return {"六块": rows, "逐年": yearly, "汇率": fx, "总结论": None, "判据格": None}


def sleeve_split(series: dict[str, pd.Series], start: str, end: str) -> list[dict]:
    """D49-4。③④⑤⑥ 的名额内年化之差，再乘 D47-2 的名额权重。"""
    needed = (
        "A股前3", "A股等权", "A股母指数", "A股毛", "A股净",
        "美股前3", "美股等权", "美股母指数", "美股毛", "美股净", "SPX",
    )
    missing = [name for name in needed if name not in series]
    if missing:
        raise IsolationError(f"名额拆分缺序列：{missing}")
    index = _same_days({name: series[name] for name in needed}, start, end)

    def gap(left: str, right: str) -> float:
        return _cagr_pp(series[left], index) - _cagr_pp(series[right], index)

    specs = (
        ("A股", A_WEIGHT, {
            "等权倾斜": gap("A股等权", "A股母指数"),
            "挑选": gap("A股前3", "A股等权"),
            "防守": gap("A股毛", "A股前3"),
            "成本": gap("A股净", "A股毛"),
        }),
        ("美股", US_WEIGHT, {
            "等权倾斜": gap("美股等权", "美股母指数"),
            "挑选": gap("美股前3", "美股等权"),
            "防守": gap("美股毛", "美股前3"),
            "成本": gap("美股净", "美股毛"),
        }),
    )
    rows = []
    for sleeve, weight, parts in specs:
        for block, value in parts.items():
            rows.append({
                "名额": sleeve,
                "块": block,
                "名额内": value,
                "权重": weight,
                "组合贡献": value * weight,
            })
    versus_spx = gap("美股前3", "SPX")
    rows.append({
        "名额": "美股",
        "块": "前3减SPX",
        "名额内": versus_spx,
        "权重": US_WEIGHT,
        "组合贡献": versus_spx * US_WEIGHT,
        "进入六块": False,
    })
    return rows


def largest_contributors(rows: list[dict], sleeve: str, start: str, end: str, k: int) -> list[str]:
    """S3–S5 去掉的名字：这一段里对挑选贡献最大的 k 个候选。"""
    table = pick_detail(rows, {sleeve: []}, start, end)
    ranked = table[sleeve]["前10"]
    return [row["候选"] for row in ranked[:k]]


def pick_detail(rows: list[dict], universe: dict[str, list[str]], start: str, end: str) -> dict:
    """D49-5。贡献 = 入选月（该候选下月收益 − 同结构等权下月收益）/ 当月入选人数，再乘 100。"""
    start_p, end_p = pd.Period(start, freq="M"), pd.Period(end, freq="M")
    kept = []
    for row in rows:
        period = pd.Period(row["月份"], freq="M")
        if start_p <= period <= end_p:
            kept.append(row)
    by_month: dict[tuple[str, pd.Period], list[dict]] = {}
    for row in kept:
        period = pd.Period(row["月份"], freq="M")
        by_month.setdefault((row["名额"], period), []).append(row)
    out = {}
    sleeves = set(universe) | {row["名额"] for row in kept}
    for sleeve in sleeves:
        total: dict[str, float] = {}
        months: dict[str, int] = {}
        for (name, _period), group in by_month.items():
            if name != sleeve:
                continue
            width = len(group)
            for row in group:
                candidate = row["候选"]
                share = (float(row["下月收益"]) - float(row["等权收益"])) / width * 100.0
                total[candidate] = total.get(candidate, 0.0) + share
                months[candidate] = months.get(candidate, 0) + 1
        ranked = sorted(total, key=lambda candidate: (-total[candidate], candidate))
        known = list(universe.get(sleeve, []))
        never = [candidate for candidate in known if months.get(candidate, 0) == 0]
        out[sleeve] = {
            "前10": [
                {"候选": candidate, "入选月数": months[candidate], "对挑选的贡献": total[candidate]}
                for candidate in ranked[:10]
            ],
            "从未入选": never,
        }
    return out


def stress_detail(rows: list[dict]) -> dict:
    """D49-6。紧张月按名额连成段。累计差是月超额百分点之和。"""
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise IsolationError("没有逐月防守记录")
    frame["期间"] = frame["月份"].map(lambda value: pd.Period(value, freq="M"))
    episodes = []
    quiet = []
    covered = set()
    for sleeve, group in frame.groupby("名额"):
        group = group.sort_values("期间")
        covered.update(group["期间"])
        current: list[dict] = []
        for row in group.to_dict("records"):
            if row["紧张"]:
                if current and row["期间"] != current[-1]["期间"] + 1:
                    episodes.append(_episode(sleeve, current))
                    current = []
                current.append(row)
            elif current:
                episodes.append(_episode(sleeve, current))
                current = []
        if current:
            episodes.append(_episode(sleeve, current))
        for label, start, end in SPANS:
            if label == "全段":
                continue
            start_p, end_p = pd.Period(start, freq="M"), pd.Period(end, freq="M")
            calm = group[(~group["紧张"]) & (group["期间"] >= start_p) & (group["期间"] <= end_p)]
            premium = float(((calm["不设防守"] - calm["v6"]) * 100.0).sum()) if len(calm) else 0.0
            quiet.append({"名额": sleeve, "段": label, "不紧张月数": int(len(calm)), "累计保费": premium})
    named = []
    for label, start, end in NAMED_STRESS:
        start_p, end_p = pd.Period(start, freq="M"), pd.Period(end, freq="M")
        inside = [period for period in covered if start_p <= period <= end_p]
        if not inside:
            state = "数据未覆盖"
        else:
            hit = frame[(frame["期间"] >= start_p) & (frame["期间"] <= end_p) & frame["紧张"]]
            state = "触发" if len(hit) else "未触发"
        named.append({"时段": label, "状态": state})
    return {"紧张段": episodes, "不紧张保费": quiet, "指名时段": named}


def _episode(sleeve: str, rows: list[dict]) -> dict:
    excess = [(float(row["v6"]) - float(row["不设防守"])) * 100.0 for row in rows]
    weights = [float(row["股票仓位"]) for row in rows]
    return {
        "名额": sleeve,
        "起": str(rows[0]["期间"]),
        "止": str(rows[-1]["期间"]),
        "月数": len(rows),
        "股票平均仓位": float(sum(weights) / len(weights)),
        "累计差": float(sum(excess)),
    }


def select_judgment(cutout: Criteria, restart: Criteria) -> dict:
    """差异行两边都列。进入判定的只有连续运行截出。"""
    pairs = (
        ("最大回撤", cutout.max_drawdown, restart.max_drawdown),
        ("保费", cutout.premium_pp, restart.premium_pp),
        ("年化除以回撤", cutout.ratio, restart.ratio),
        ("对同仓位基准", cutout.excess_vs_same_pp, restart.excess_vs_same_pp),
    )
    rows = []
    for name, cut, fresh in pairs:
        rows.append({
            "判据": name,
            "连续运行截出": cut,
            "重新起步": fresh,
            "差": fresh - cut,
            "判定用": JUDGMENT_PATH,
        })
    cut_pass = conclusion(passes(cutout))
    rows.append({
        "判据": "该窗口结论",
        "连续运行截出": cut_pass,
        "重新起步": conclusion(passes(restart)),
        "差": None,
        "判定用": JUDGMENT_PATH,
    })
    return {
        "判定口径": JUDGMENT_PATH,
        "原因": RESTART_REASON,
        "主判": cut_pass,
        "数": cutout,
        "差异": rows,
    }


def full_span(book: SpanBook, rmb: pd.Series | None = None, usd: pd.Series | None = None) -> dict:
    """2006-01 → 2026-09 的连续运行。只报告，不画判据格，不出总结论。"""
    _window(book.v6, FULL_START, EXAM_END)
    report = attribution(book, rmb, usd)
    if report["总结论"] is not None or report["判据格"] is not None:
        raise IsolationError("全段不能出总结论或判据格")
    return {"窗口": (FULL_START, EXAM_END), "只报告": True, "拆账": report}


def crosses_cut(peak: pd.Timestamp, trough: pd.Timestamp) -> bool:
    """最深一跌的高点在 2015-12-31 或更早，低点在 2016-01-01 或更晚。"""
    return pd.Timestamp(peak) <= CUT and pd.Timestamp(trough) >= EXAM_OPEN


def eight_line_table(books: dict[str, pd.Series], start: str, end: str) -> list[dict]:
    """D49-7。八条线只报年化、回撤和是否跨过 2016-01，不进翻转。"""
    missing = [name for name in EIGHT_LINES if name not in books]
    if missing:
        raise IsolationError(f"八条线缺：{missing}")
    rows = []
    for name in EIGHT_LINES:
        stats = line_character(books[name], start, end)
        stats["线"] = name
        rows.append(stats)
    return rows


def line_character(series: pd.Series, start: str, end: str) -> dict:
    """D49-7 的一条线：普通刻度净值、年化、最大回撤和是否跨过 2016-01。"""
    window = _window(series, start, end)
    depth = max_drawdown(window)
    nav = 1_000_000.0 * (1.0 + window).cumprod()
    drawdown = nav / nav.cummax() - 1.0
    return {
        "年化": cagr(window),
        "最大回撤": depth["max_drawdown"],
        "高点": pd.Timestamp(depth["peak"]).date().isoformat(),
        "低点": pd.Timestamp(depth["trough"]).date().isoformat(),
        "跨2015-12/2016-01": crosses_cut(depth["peak"], depth["trough"]),
        "净值末": float(nav.iloc[-1]),
        "回撤末": float(drawdown.iloc[-1]),
    }


def month_regime(level: pd.Series) -> pd.Series:
    """沪深300全收益的月末：12 个月方向 × 当月方向。慢动量还没有值的月份留空。"""
    month_end = level.sort_index().resample("ME").last()
    slow = month_end.pct_change(12)
    fast = month_end.pct_change(1)
    labels = np.select(
        [(slow > 0) & (fast > 0), (slow > 0) & (fast <= 0), (slow <= 0) & (fast <= 0)],
        ["牛市", "回调", "熊市"],
        "反弹",
    )
    out = pd.Series(labels, index=month_end.index).where(slow.notna())
    out.index = out.index.to_period("M")
    return out


def regime_table(strategy: pd.Series, benchmarks: dict[str, pd.Series], labels: pd.Series) -> list[dict]:
    """四种行情。合计是月超额的百分点之和。跑赢是严格大于。"""
    strategy_m = monthly_returns(strategy)
    rows = []
    for name, bench in benchmarks.items():
        excess = (strategy_m - monthly_returns(bench).reindex(strategy_m.index)).dropna()
        used = labels.reindex(excess.index)
        for state in ("牛市", "回调", "熊市", "反弹"):
            block = excess[used == state]
            rows.append({
                "对照": name,
                "行情": state,
                "月数": int(len(block)),
                "合计": float(block.sum() * 100.0) if len(block) else 0.0,
                "跑赢月份": float((block > 0).mean()) if len(block) else None,
            })
    return rows


def any_start(navs: dict[str, pd.Series], strategy: str, years: int) -> dict:
    """月初买进，持有整年。终点超过最后一天就停止。跑赢是严格大于。"""
    index = pd.DatetimeIndex(navs[strategy].index).sort_values().unique()
    starts = pd.Series(index, index=index).groupby([index.year, index.month]).first().to_numpy()
    wins = {name: 0 for name in navs if name != strategy}
    n = 0
    for origin in starts:
        stop = pd.Timestamp(origin) + pd.DateOffset(years=int(years))
        if stop > index[-1]:
            break
        end = index[index <= stop][-1]
        growth = {
            name: (float(nav.loc[end]) / float(nav.loc[origin])) ** (1 / years) - 1
            for name, nav in navs.items()
        }
        n += 1
        for name in wins:
            if growth[strategy] > growth[name]:
                wins[name] += 1
    return {
        "年数": years,
        "起点数": n,
        "跑赢占比": {name: (count / n if n else None) for name, count in wins.items()},
    }


def join_ledgers(design: pd.Series, exam: pd.Series, *, name: str) -> dict:
    """A1、A2 首尾衔接。重叠日必须逐日一致，否则停下，不返回接好的序列。"""
    design = pd.Series(design, dtype=float).sort_index()
    exam = pd.Series(exam, dtype=float).sort_index()
    if design.empty or exam.empty:
        raise IsolationError(f"{name} 账本是空的")
    if pd.Timestamp(design.index.max()) > CUT:
        raise IsolationError(f"{name} 设计期账本晚于 2015-12-31")
    both = design.index.intersection(exam.index)
    if len(both) and float((design.loc[both] - exam.loc[both]).abs().max()) > 1e-8:
        raise IsolationError(f"{name} 接口逐日不一致，停下，不衔接")
    stitched = pd.concat([design, exam[~exam.index.isin(both)]]).sort_index()
    return {
        "名称": name,
        "重叠日": int(len(both)),
        "序列": stitched,
        "续跑": False,
    }


def run_random_exam() -> None:
    raise IsolationError("不在真实 2016 年以后的行情上跑同结构随机。")


def random_report(rule: pd.Series, paths: np.ndarray) -> dict:
    """同结构随机的百分位和每月跑赢中位数的比例。正式口径仍是种子 20261122、1000 次。

    这里只吃调用方已经放在内存里的路径。正式开考走 run_random_exam，本 PR 里它拒绝。
    """
    rule = pd.Series(rule, dtype=float).sort_index().dropna()
    values = np.atleast_2d(np.asarray(paths, dtype=float))
    if values.shape[1] != len(rule):
        raise IsolationError("随机路径的天数和规则不一致")
    rows = []
    for label, start, end in RANDOM_WINDOWS:
        day = (rule.index >= pd.Timestamp(start)) & (rule.index <= pd.Timestamp(end))
        if not day.any():
            rows.append({
                "窗口": label,
                "日数": 0,
                "百分位": None,
                "每月跑赢中位数": None,
                "种子": SEED,
                "正式试验次数": TRIALS,
                "本次是正式检验": False,
            })
            continue
        sliced = rule.to_numpy()[day]
        path_cagr = annualize(values[:, day])
        rule_cagr = float(annualize(sliced)[0])
        if abs(rule_cagr - cagr(pd.Series(sliced, index=rule.index[day]))) > 1e-12:
            raise IsolationError("随机年化没有用和 metrics.cagr 相同的 252 日复利")
        months = monthly_returns(pd.Series(sliced, index=rule.index[day]))
        path_months = _path_months(values[:, day], rule.index[day])
        rows.append({
            "窗口": label,
            "日数": int(day.sum()),
            "月数": int(len(months)),
            "规则年化": rule_cagr,
            "百分位": rank_percentile(rule_cagr, path_cagr),
            "每月跑赢中位数": beat_median_share(months.to_numpy(), path_months),
            "种子": SEED,
            "正式试验次数": TRIALS,
            "本次路径数": int(values.shape[0]),
            "本次是正式检验": False,
        })
    return {
        "口径": {
            "种子": SEED,
            "试验次数": TRIALS,
            "年化": "日收益连乘，再按 252 个交易日，与 src/report/metrics.py cagr 相同",
            "准入": "v6 去重后的可参选池，每次 3 只",
        },
        "窗口": rows,
    }


def _path_months(paths: np.ndarray, index: pd.DatetimeIndex) -> np.ndarray:
    periods = index.to_period("M")
    labels = pd.PeriodIndex(periods.unique(), freq="M")
    matrix = np.empty((paths.shape[0], len(labels)))
    for i, period in enumerate(labels):
        block = paths[:, periods == period]
        matrix[:, i] = np.prod(1.0 + block, axis=1) - 1.0
    return matrix
