"""把已经写好的 §5 权重调整接进一条路的决策日。不新写溢价公式。

成交日不再调用这里。离场卖单只进现金，不经过状态乘子或折价加仓。
"""
from __future__ import annotations

import math

import pandas as pd

from src.v3.premium.apply import adjust_weights, allocate_container, representative_code
from src.v3.premium.rules import NORMAL, PremiumSpec
from src.v3.premium.series import premium_frame


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def frames_for(inputs: dict, spec: PremiumSpec, calendar: pd.DatetimeIndex) -> dict:
    """container → code → §5.1 表。收盘用未复权场内价，净值仍是 T−2。"""
    out = {}
    for name, codes in inputs.items():
        out[name] = {}
        for code, pair in codes.items():
            out[name][code] = premium_frame(pair["close"], pair["nav"], calendar, spec)
    return out


def panels_for(market, spec: PremiumSpec) -> dict | None:
    ready = getattr(market, "premium_panels", None)
    if ready:
        return ready
    inputs = getattr(market, "premium_inputs", None) or {}
    if not inputs:
        return None
    return frames_for(inputs, spec, market.dates)


def premium_ids_of(market) -> set[str]:
    raw = getattr(market, "premium_ids", None) or ()
    if raw:
        return set(raw)
    return {name for name in (getattr(market, "premium_inputs", None) or {})}


def adjust_decision(targets: dict[str, float], held: dict[str, float], code_held: dict[str, dict[str, float]],
                    ctx, day: pd.Timestamp, cash_id: str, weight_eps: float) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """ctx 需要 panels、ids、eligible。返回溢价后的容器权重，以及溢价容器的代码权重。"""
    panels = ctx["panels"]
    names = set(ctx["ids"])
    stamp = pd.Timestamp(day)
    states = {}
    container_premium = {}
    code_premiums: dict[str, dict[str, float]] = {}
    for name in names:
        by_code = panels.get(name) or {}
        today = {}
        for code, frame in by_code.items():
            if stamp not in frame.index or "premium" not in frame.columns:
                continue
            number = _finite(frame.at[stamp, "premium"])
            if number is not None:
                today[code] = number
        code_premiums[name] = today
        rep = representative_code(today, code_held.get(name) or {})
        if rep is None or stamp not in by_code[rep].index:
            states[name] = NORMAL
            container_premium[name] = float("nan")
            continue
        state = by_code[rep].at[stamp, "state"]
        if state is None or (isinstance(state, float) and not math.isfinite(state)):
            states[name] = NORMAL
        else:
            states[name] = str(state)
        container_premium[name] = today[rep]
    eligible = set(ctx.get("eligible") or [])
    gate = ctx.get("eligible_on")
    if gate is not None:
        row = gate.loc[stamp] if stamp in gate.index else None
        if row is not None:
            eligible = {name for name in row.index if bool(row[name])}
    adjusted = adjust_weights(
        targets, states=states, held=held, premiums=container_premium,
        premium_ids=names, eligible=eligible, cash_id=cash_id)
    codes: dict[str, dict[str, float]] = {}
    for name in sorted(names):
        alloc, leftover = allocate_container(
            float(adjusted.get(name, 0.0)), code_held.get(name) or {}, code_premiums.get(name) or {})
        if leftover > weight_eps:
            adjusted[name] = float(adjusted.get(name, 0.0)) - leftover
            adjusted[cash_id] = float(adjusted.get(cash_id, 0.0)) + leftover
        codes[name] = alloc
    return adjusted, codes
