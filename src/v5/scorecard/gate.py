"""§6.2 部件过关。

记号沿用 v4 §6.2：段内年化超额 A，状态累计超额 P（不四舍五入）。
本函数只比较调用方给的日收益，不读行情库，也不写 `results/v5/design/component-gate.csv`。
设计期运行时再落那张表。P2 的比较基准由调用方传入，这里不根据 C1 是否过关自动改。

`ann_excess_*` 与 `pp_*` 是 U-指数上的 A 和 P，单位与 v4 `candidate_gate` 相同（A 是小数）。
`tradable_d_*` = 100 × (A_X − A_Y)，单位是百分点，好和 −2 直接比。
`pool` 固定写 `index`：一行里同时有两池的数，预注册没有规定这一列填哪个池。
S0 只报告，预注册点名 `pass` 留空；没有比较对象，其余 pass 列和 tradable_d 也留空。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from src.v4.scorecard.core import STATE_ORDER, ScorecardError, refuse_portfolio_dates
from src.v4.scorecard.gate import SEGMENTS, _excess, _segment_excess, state_points

GATE_COLUMNS = (
    "arm", "base_arm", "pool", "target_state",
    "ann_excess_s1", "ann_excess_s2",
    "pp_bull", "pp_correction", "pp_bear", "pp_rebound",
    "pass_segments", "pass_target", "pass_guard",
    "tradable_d_s1", "tradable_d_s2", "pass_tradable", "pass",
)
BLANK_COLUMNS = (
    "pass_segments", "pass_target", "pass_guard",
    "tradable_d_s1", "tradable_d_s2", "pass_tradable", "pass",
)
# 一行比较同时写下 U-指数和 U-可交易。绝对数列的是指数，所以这一列写 index。
POOL_NAME = "index"
COMPONENT_TARGET = {"C1": "熊市", "C2": "回调"}
_STATE_COLUMNS = {"牛市": "pp_bull", "回调": "pp_correction", "熊市": "pp_bear", "反弹": "pp_rebound"}


@dataclass(frozen=True)
class ComponentStep:
    arm: str
    base_arm: str
    target_state: str


def _annualized(series: pd.Series, benchmark: pd.Series) -> dict[str, float]:
    return {key: _segment_excess(series, benchmark, start, end) for key, start, end in SEGMENTS}


def _points(series: pd.Series, benchmark: pd.Series, states: pd.Series) -> dict[str, float]:
    return state_points(_excess(series, benchmark), states)


def _column(frame: pd.DataFrame, name: str) -> pd.Series:
    if name not in frame.columns:
        raise ScorecardError(f"缺少 {name}")
    return frame[name].astype(float)


def _report_row(arm: str, ann: dict[str, float], points: dict[str, float]) -> dict:
    row = {
        "arm": arm,
        "base_arm": "",
        "pool": POOL_NAME,
        "target_state": "",
        "ann_excess_s1": ann["s1"],
        "ann_excess_s2": ann["s2"],
        "pass_segments": None,
        "pass_target": None,
        "pass_guard": None,
        "tradable_d_s1": None,
        "tradable_d_s2": None,
        "pass_tradable": None,
        "pass": None,
    }
    for state, column in _STATE_COLUMNS.items():
        row[column] = points[state]
    return row


def _compare_row(step: ComponentStep, index_returns: pd.DataFrame, tradable: pd.DataFrame,
                 benchmark: pd.Series, states: pd.Series) -> dict:
    if step.target_state not in STATE_ORDER:
        raise ScorecardError(f"未知目标状态 {step.target_state}")
    arm = _column(index_returns, step.arm)
    base = _column(index_returns, step.base_arm)
    arm_t = _column(tradable, step.arm)
    base_t = _column(tradable, step.base_arm)
    ann_x = _annualized(arm, benchmark)
    ann_y = _annualized(base, benchmark)
    points_x = _points(arm, benchmark, states)
    points_y = _points(base, benchmark, states)
    trad_x = _annualized(arm_t, benchmark)
    trad_y = _annualized(base_t, benchmark)
    segments_ok = bool(ann_x["s1"] > ann_y["s1"] and ann_x["s2"] > ann_y["s2"])
    target_ok = bool(points_x[step.target_state] > points_y[step.target_state])
    guard_ok = True
    for state in STATE_ORDER:
        if state == step.target_state:
            continue
        if not (points_x[state] >= points_y[state] - 10.0):
            guard_ok = False
            break
    d1 = 100.0 * (trad_x["s1"] - trad_y["s1"])
    d2 = 100.0 * (trad_x["s2"] - trad_y["s2"])
    tradable_ok = bool(
        math.isfinite(d1) and math.isfinite(d2) and d1 >= -2.0 and d2 >= -2.0
    )
    row = {
        "arm": step.arm,
        "base_arm": step.base_arm,
        "pool": POOL_NAME,
        "target_state": step.target_state,
        "ann_excess_s1": ann_x["s1"],
        "ann_excess_s2": ann_x["s2"],
        "pass_segments": segments_ok,
        "pass_target": target_ok,
        "pass_guard": guard_ok,
        "tradable_d_s1": d1,
        "tradable_d_s2": d2,
        "pass_tradable": tradable_ok,
        "pass": bool(segments_ok and target_ok and guard_ok and tradable_ok),
    }
    for state, column in _STATE_COLUMNS.items():
        row[column] = points_x[state]
    return row


def component_gate(index_returns: pd.DataFrame, benchmark: pd.Series, states: pd.Series,
                   steps: list[ComponentStep] | tuple[ComponentStep, ...] = (),
                   tradable_returns: pd.DataFrame | None = None, *,
                   report_arm: str = "S0") -> pd.DataFrame:
    """每行一次比较。`report_arm` 在指数列里就先写一行只报告的结果。"""
    if not isinstance(states, pd.Series) or len(states) == 0:
        raise ScorecardError("需要 classify_months 给出的月份状态")
    frame = index_returns.sort_index()
    bench = benchmark.sort_index()
    refuse_portfolio_dates(frame.index, what="U-指数日收益")
    refuse_portfolio_dates(bench.index, what="BM-主")
    if len(tuple(steps)) > 0 and tradable_returns is None:
        raise ScorecardError("部件比较需要 U-可交易日收益")
    tradable = None
    if tradable_returns is not None:
        tradable = tradable_returns.sort_index()
        refuse_portfolio_dates(tradable.index, what="U-可交易日收益")
    rows = []
    if report_arm and report_arm in frame.columns:
        series = _column(frame, report_arm)
        rows.append(_report_row(report_arm, _annualized(series, bench), _points(series, bench, states)))
    for step in steps:
        if tradable is None:
            raise ScorecardError("部件比较需要 U-可交易日收益")
        rows.append(_compare_row(step, frame, tradable, bench, states))
    out = pd.DataFrame(rows, columns=list(GATE_COLUMNS))
    # 混进 None 的数值列会被收成 NaN。留空的列按原值重建，S0 的 pass 才仍是空。
    for column in BLANK_COLUMNS:
        out[column] = pd.Series([row[column] for row in rows], dtype=object).to_numpy()
    return out
