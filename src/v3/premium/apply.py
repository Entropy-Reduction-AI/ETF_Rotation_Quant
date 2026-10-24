"""§5.2 乘子、§5.3 风险预算、§5.4 同一指数选代码。

这里只动权重，不乘收益，不产生净值曲线。
"""
from __future__ import annotations

import math

from .rules import (
    HELD_EPS,
    NORMAL,
    PULSE,
    SINGLE_BUDGET,
    STRUCTURAL_DISCOUNT,
    STRUCTURAL_HIGH,
    TOTAL_BUDGET,
    PremiumError,
)

_SUM_TOL = 1e-6


def _finite(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    if number != number or math.isinf(number):
        return float("nan")
    return number


def _premium_key(premiums: dict[str, float], code: str) -> float:
    number = _finite(premiums.get(code))
    if number != number:
        return float("-inf")
    return number


def representative_code(premiums: dict[str, float], held: dict[str, float]) -> str | None:
    """多只代码时，状态看哪一只。

    预注册把状态写在「该只 ETF」上，容器权重是一条。未持有时，状态用 §5.4 将买入的那只
    （溢价最低，代码较小者优先）。已持有时，状态用已持有里溢价最高的那只（减仓先卖的那只，
    代码较小者优先）。只有一只代码时两条是同一只。
    """
    held_codes = [code for code, weight in held.items() if _finite(weight) > HELD_EPS]
    if not held_codes:
        finite = [code for code, value in premiums.items() if _finite(value) == _finite(value)]
        if not finite:
            return None
        return min(finite, key=lambda code: (_finite(premiums[code]), code))
    return min(held_codes, key=lambda code: (-_premium_key(premiums, code), code))


def _simplex(weights: dict[str, float], cash_id: str) -> dict[str, float]:
    if cash_id not in weights:
        raise PremiumError("权重里没有现金")
    out = {}
    for name, value in weights.items():
        number = _finite(value)
        if number != number:
            raise PremiumError(f"{name} 的权重不是数")
        if number < -HELD_EPS:
            raise PremiumError(f"{name} 的权重是负数")
        out[name] = 0.0 if number < 0.0 else number
    total = sum(out.values())
    if abs(total - 1.0) > _SUM_TOL:
        raise PremiumError(f"权重和是 {total}，不是 1")
    return out


def adjust_weights(targets: dict[str, float], *, states: dict[str, str], held: dict[str, float],
                   premiums: dict[str, float], premium_ids: set[str], eligible: set[str],
                   cash_id: str = "cash") -> dict[str, float]:
    """按 §5 的顺序改容器权重。`targets` 是 §4 的合成权重。

    1. 调用方已经拿到 §4 权重。
    2. 状态乘子。脉冲：未持有记 0，已持有则原权重 × 0.5。结构型冲高 × 0.5。
       结构型折价先记着，下一步再加。常态不动。
    3. 削掉的权重进现金。折价要加的权重只从现金拨，含刚刚削进来的部分。
       现金不够就封顶在原权重加剩余现金。不压缩别的持仓。多只折价时按 §4 权重从大到小，
       权重相同则容器 id 较小者先拿现金。
    4. 单只权重 × max(p, 0) ≤ 2%，全部溢价容器合计 ≤ 5%。合计超了就对正溢价的权重按同一比例缩小。
    5. 第 4 步截下的权重，按 §4 权重从大到小，给下一个非溢价、仍有资格的容器；没有就进现金。
    """
    if cash_id in premium_ids:
        raise PremiumError("现金不是溢价容器")
    for name, state in states.items():
        if name in premium_ids and state not in {PULSE, STRUCTURAL_HIGH, STRUCTURAL_DISCOUNT, NORMAL}:
            raise PremiumError(f"{name} 的状态无法识别：{state}")
    base = _simplex(targets, cash_id)
    weights = dict(base)
    cash = weights[cash_id]
    discounts = []
    for name in sorted(premium_ids):
        origin = weights.get(name, 0.0)
        state = states.get(name, NORMAL)
        if state == PULSE:
            updated = origin * 0.5 if _finite(held.get(name)) > HELD_EPS else 0.0
        elif state == STRUCTURAL_HIGH:
            updated = origin * 0.5
        elif state == STRUCTURAL_DISCOUNT:
            discounts.append((base.get(name, 0.0), name, origin))
            continue
        else:
            continue
        cash += origin - updated
        weights[name] = updated
    discounts.sort(key=lambda item: (-item[0], item[1]))
    for _rank, name, origin in discounts:
        extra = origin * 0.5
        take = min(extra, cash) if cash > 0.0 else 0.0
        weights[name] = origin + take
        cash -= take
    weights[cash_id] = cash

    clipped = 0.0
    for name in sorted(premium_ids):
        premium = _finite(premiums.get(name))
        weight = weights.get(name, 0.0)
        if not (premium > 0.0) or weight <= 0.0:
            continue
        if weight * premium > SINGLE_BUDGET + 1e-12:
            capped = SINGLE_BUDGET / premium
            clipped += weight - capped
            weights[name] = capped
    exposure = 0.0
    contributors = []
    for name in sorted(premium_ids):
        premium = _finite(premiums.get(name))
        weight = weights.get(name, 0.0)
        if premium > 0.0 and weight > 0.0:
            exposure += weight * premium
            contributors.append(name)
    if exposure > TOTAL_BUDGET + 1e-12:
        scale = TOTAL_BUDGET / exposure
        for name in contributors:
            before = weights[name]
            weights[name] = before * scale
            clipped += before - weights[name]

    order = sorted((name for name in eligible if name != cash_id and name not in premium_ids),
                   key=lambda name: (-base.get(name, 0.0), name))
    for name in order:
        if clipped <= 1e-15:
            break
        weights[name] = weights.get(name, 0.0) + clipped
        clipped = 0.0
    weights[cash_id] = weights.get(cash_id, 0.0) + clipped
    _simplex(weights, cash_id)
    return weights


def allocate_container(target: float, held: dict[str, float], premiums: dict[str, float]) -> tuple[dict[str, float], float]:
    """§5.4。新买加在溢价最低的代码上；减仓先减溢价最高的。返回 (代码权重, 没处放的权重)。

    没处放只发生在要加仓、但没有一只代码有溢价的时候。调用方把这部分放回现金。
    并列时代码较小者先买；减仓时溢价相同也先减代码较小者。
    """
    target_weight = _finite(target)
    if target_weight != target_weight or target_weight < -HELD_EPS:
        raise PremiumError("容器目标权重必须是非负数")
    if target_weight < 0.0:
        target_weight = 0.0
    book = {}
    for code, weight in held.items():
        number = _finite(weight)
        if number > HELD_EPS:
            book[code] = number
    current = sum(book.values())
    if abs(target_weight - current) <= HELD_EPS:
        return book, 0.0
    if target_weight > current:
        finite = [code for code, value in premiums.items() if _finite(value) == _finite(value)]
        if not finite:
            return book, target_weight - current
        code = min(finite, key=lambda item: (_finite(premiums[item]), item))
        book[code] = book.get(code, 0.0) + (target_weight - current)
        return book, 0.0
    need = current - target_weight
    order = sorted(book, key=lambda code: (-_premium_key(premiums, code), code))
    for code in order:
        if need <= HELD_EPS:
            break
        take = min(book[code], need)
        book[code] -= take
        need -= take
        if book[code] <= HELD_EPS:
            book[code] = 0.0
    kept = {code: weight for code, weight in book.items() if weight > HELD_EPS}
    return kept, 0.0
