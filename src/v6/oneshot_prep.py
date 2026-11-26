"""一次性检验的脚手架。不读行情，不开考。

判定窗口和四条判据来自冻结稿 §5。总结论的三级来自 D50 第 2 稿
（#388 头 d7a49f3b，尚未合入）。全段只报告，来自已合入的 D49。
D50-4 在已经“通过（有条件）”后再遇欧洲“不支持”仍待 Owner 定，这里不选。
"""

from __future__ import annotations

from dataclasses import dataclass

from src.v6.guard import IsolationError

EXAM_START = "2016-01-01"
EXAM_END = "2026-09-30"
FULL_START = "2006-01-01"
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
DRAWDOWN_LIMIT = -0.40
PREMIUM_LIMIT_PP = 4.0


@dataclass(frozen=True)
class Criteria:
    """四条判据的数。最大回撤用负数，例如 −0.25。"""

    max_drawdown: float
    premium_pp: float
    ratio: float
    benchmark_ratio: float
    excess_vs_same_pp: float


def passes(item: Criteria) -> dict[str, bool]:
    return {
        "最大回撤": item.max_drawdown >= DRAWDOWN_LIMIT,
        "保费": item.premium_pp <= PREMIUM_LIMIT_PP,
        "年化除以回撤": item.ratio > item.benchmark_ratio,
        "对同仓位基准": item.excess_vs_same_pp >= 0.0,
    }


def conclusion(flags: dict[str, bool]) -> str:
    return "通过" if all(flags.values()) else "不通过"


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
        })
    if main_result == "不通过":
        level = "不通过"
    elif any(row["敏感"] == "很敏感" for row in details):
        level = "通过（有条件）"
    else:
        level = "通过"
    return {"主判": main_result, "总结论": level, "稳健性": details}


def europe_after_conditional() -> str:
    """D50-4 待 Owner 定。不选 A 或 B。"""
    raise IsolationError("D50-4 尚未由 Owner 定，不开考")


def run_exam() -> None:
    raise IsolationError("一次性检验未授权。D50 未合入，不读 2016 年以后的结果。")
