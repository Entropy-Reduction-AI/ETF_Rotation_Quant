"""§4.5 单只离场。

触发用严格小于：收盘价等于峰值的 90% 不卖。10% 是固定阈值。
8%、12%、15% 只留给 §7.2 的稳健性入口，不在这里挑最好的一档。

缺价当天到期的离场单，预注册写明边界测试未签收前不冻结。这里不把 0、负数或
非有限价当成成交价，挂单留到下一根有效价。这不是一条已冻结的处置。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from .book import Book, RunnerError, assert_window, drift
from .limits import executable_weights, legs_clear, session_tradable

EXIT_DRAWDOWN = 0.10
ALLOWED_DRAWDOWNS = (0.08, 0.10, 0.12, 0.15)
# 只吸收二进制误差，不把真实的更低价当成相等。
_EQUAL_ABS = 1e-9


def check_drawdown(drawdown: float) -> float:
    for item in ALLOWED_DRAWDOWNS:
        if math.isclose(float(drawdown), item, rel_tol=0.0, abs_tol=_EQUAL_ABS):
            return item
    raise RunnerError(f"离场阈值只能是 {ALLOWED_DRAWDOWNS}，收到 {drawdown}")


def triggered(price: float, peak: float, drawdown: float = EXIT_DRAWDOWN) -> bool:
    """price < (1 − drawdown) × peak。等于该比例不触发。"""
    if not valid_mark(price) or not valid_mark(peak):
        return False
    limit = float(peak) * (1.0 - float(drawdown))
    if math.isclose(float(price), limit, rel_tol=0.0, abs_tol=_EQUAL_ABS):
        return False
    return float(price) < limit


def valid_mark(value) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0.0


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


@dataclass
class _Pending:
    weights: dict[str, float]
    codes: dict[str, dict[str, float]]


def _row_weights(raw, columns: list[str], cash_id: str) -> dict[str, float]:
    weights = {name: 0.0 for name in columns}
    for name in columns:
        if hasattr(raw, "index") and name in raw.index:
            number = _finite(raw[name])
        elif isinstance(raw, dict):
            number = _finite(raw.get(name))
        else:
            number = None
        weights[name] = 0.0 if number is None or number < 0.0 else number
    weights.setdefault(cash_id, 0.0)
    return weights


def _active(codes: dict[str, float] | None, weight_eps: float) -> dict[str, float]:
    return {code: weight for code, weight in (codes or {}).items() if weight > weight_eps}


def _spot_level(levels, code_levels, name: str, codes: dict[str, float], stamp: pd.Timestamp,
                weight_eps: float) -> float | None:
    """单代码优先用该代码的收益价，否则用容器计价序列。多代码不走这里。"""
    active = _active(codes, weight_eps)
    if len(active) == 1 and code_levels and name in code_levels:
        code = next(iter(active))
        frame = code_levels[name]
        if code in frame.columns and stamp in frame.index and valid_mark(frame.at[stamp, code]):
            return float(frame.at[stamp, code])
    if levels is not None and name in levels.columns and stamp in levels.index and valid_mark(levels.at[stamp, name]):
        return float(levels.at[stamp, name])
    return None


def _basket_return(codes: dict[str, float], rets: pd.DataFrame, stamp: pd.Timestamp,
                   weight_eps: float) -> float | None:
    num = 0.0
    den = 0.0
    for code, weight in codes.items():
        if weight <= weight_eps or code not in rets.columns or stamp not in rets.index:
            continue
        value = _finite(rets.at[stamp, code])
        if value is None:
            return None
        num += weight * value
        den += weight
    if den <= weight_eps:
        return None
    return num / den


def _scale_codes(codes: dict[str, float], new_weight: float, weight_eps: float) -> dict[str, float]:
    total = sum(weight for weight in codes.values() if weight > 0.0)
    if new_weight <= weight_eps or total <= weight_eps:
        return {}
    scale = new_weight / total
    return {code: weight * scale for code, weight in codes.items() if weight > 0.0}


def _target_row(refill_targets: pd.DataFrame | None, stamp: pd.Timestamp) -> dict[str, float]:
    if refill_targets is None or stamp not in refill_targets.index:
        return {}
    row = refill_targets.loc[stamp]
    return {str(name): float(row[name]) for name in refill_targets.columns}


def _queue_refill(refills, filled_slots, exited: set[str], refill_targets, stamp, trade_eps: float) -> None:
    """卖单在 t 日收盘成交。买单留到 t+1，目标用 t 日收盘的权重。"""
    sold = 0.0
    for name, weight in filled_slots:
        exited.add(str(name))
        sold += float(weight)
    if sold <= trade_eps:
        return
    refills.append({
        "proceeds": sold,
        "exclude": set(exited),
        "target": _target_row(refill_targets, stamp),
        "filled": {},
        "armed": False,
    })


def _fill_due_refills(weights, refills, stamp, cash_id, fee_table, fill_limits, fill_quotes,
                      columns, trade_eps, weight_eps, peaks, spot, deferred,
                      cash_cap: float | None = None) -> tuple[float, float]:
    """执行已经排到今天的补位买单。涨停或无价的那一档留下，不把额度让给更后面的名字。

    `cash_cap` 是卖单成交前的现金。同一天先卖后买时，这笔补位只用已经在账上的卖出所得，
    不把今天刚卖出、还没排进下一笔补位的现金算进去。
    """
    due = [order for order in refills if order.get("armed")]
    pending = [order for order in refills if not order.get("armed")]
    refills.clear()
    refills.extend(pending)
    extra_cost = 0.0
    extra_buy = 0.0
    spendable = None if cash_cap is None else float(cash_cap)
    names = [name for name in columns if name != cash_id]
    flags = session_tradable(fill_quotes, stamp, names) if fill_limits else {}
    for order in due:
        proceeds = float(order.get("proceeds") or 0.0)
        if proceeds <= trade_eps:
            continue
        target = order.get("target") or {}
        exclude = set(order.get("exclude") or ())
        filled = dict(order.get("filled") or {})
        held = {name for name in names if float(weights.get(name, 0.0)) > weight_eps}
        ranked = []
        for name, raw in target.items():
            if name == cash_id:
                continue
            room = float(raw) - float(filled.get(name, 0.0))
            if room <= trade_eps or name in held or name in exclude or name not in fee_table:
                continue
            ranked.append((-room, str(name), room))
        ranked.sort()
        for _, name, room in ranked:
            if proceeds <= trade_eps:
                break
            actual_cash = float(weights.get(cash_id, 0.0))
            cash_now = actual_cash if spendable is None else min(actual_cash, max(spendable, 0.0))
            take = min(room, proceeds, cash_now)
            if take <= trade_eps:
                break
            if fill_limits and not flags.get(name, (False, False))[0]:
                deferred.append({"date": stamp, "name": name, "reason": "refill_blocked"})
                refills.append({
                    "proceeds": proceeds,
                    "exclude": exclude,
                    "target": target,
                    "filled": filled,
                    "armed": False,
                })
                break
            weights[name] = float(weights.get(name, 0.0)) + take
            weights[cash_id] = actual_cash - take
            if spendable is not None:
                spendable -= take
            extra_cost += take * float(fee_table[name])
            extra_buy += take
            proceeds -= take
            filled[name] = float(filled.get(name, 0.0)) + take
            mark = spot(name, stamp)
            if valid_mark(mark):
                peaks[name] = float(mark)
    return extra_cost, extra_buy


def _execution_cost(before: dict[str, float], after: dict[str, float],
                    before_codes: dict[str, dict[str, float]], after_codes: dict[str, dict[str, float]],
                    fees: dict[str, float], cash_id: str, trade_eps: float) -> tuple[float, float, float]:
    cost = 0.0
    buy = 0.0
    sell = 0.0
    for name in set(before) | set(after):
        fee = float(fees[name])
        if name == cash_id:
            change = float(after.get(name, 0.0)) - float(before.get(name, 0.0))
            if abs(change) <= trade_eps:
                continue
            cost += abs(change) * fee
            if change > 0.0:
                buy += change
            else:
                sell -= change
            continue
        old = before_codes.get(name) or {}
        new = after_codes.get(name) or {}
        if old or new:
            for code in set(old) | set(new):
                change = float(new.get(code, 0.0)) - float(old.get(code, 0.0))
                if abs(change) <= trade_eps:
                    continue
                cost += abs(change) * fee
                if change > 0.0:
                    buy += change
                else:
                    sell -= change
            continue
        change = float(after.get(name, 0.0)) - float(before.get(name, 0.0))
        if abs(change) <= trade_eps:
            continue
        cost += abs(change) * fee
        if change > 0.0:
            buy += change
        else:
            sell -= change
    return cost, buy, sell


def simulate_path(pnl: pd.DataFrame, levels: pd.DataFrame | None, fees: dict[str, float], cash_id: str, *,
                  targets: pd.DataFrame | None = None, decisions: pd.DataFrame | None = None,
                  premium=None, code_levels=None, code_returns=None,
                  exit_drawdown: float = EXIT_DRAWDOWN, trade_eps: float = 1e-12,
                  cost_multiplier: float = 1.0, allow_after: bool = False,
                  weight_eps: float = 1e-6, fill_limits: bool = False,
                  fill_quotes: dict | None = None, refill_targets: pd.DataFrame | None = None,
                  cross_border=None, cross_border_names: set | None = None,
                  dividend_yield: pd.DataFrame | None = None) -> Book:
    """一条路：先记当日收益和漂移，再处理收盘成交，最后才接收新的调仓决定。

    `targets` 已经是成交日权重，无溢价时直接用。有溢价上下文时，`decisions` 是决策日的
    §4 权重：决策日收盘后改一次，下一交易日成交，成交日不再跑溢价状态机。

    `fill_limits`、`refill_targets`、`cross_border` 默认关闭。关闭时下面的分支不改权重和费用。
    `refill_targets` 打开时，离场卖单在 t 日收盘成交，补位买单在 t+1 日收盘成交。
    """
    drawdown = check_drawdown(exit_drawdown)
    assert_window(pnl.index, allow_after)
    columns = list(pnl.columns)
    if cash_id not in columns:
        raise RunnerError("收益里没有现金列")
    weights = {name: 0.0 for name in columns}
    weights[cash_id] = 1.0
    code_book: dict[str, dict[str, float]] = {name: {} for name in columns if name != cash_id}
    peaks: dict[str, float] = {}
    baskets: dict[str, float] = {}
    stopped: set[str] = set()
    tosell: list[str] = []
    pending: _Pending | None = None
    retry: _Pending | None = None
    refills: list[dict] = []
    exited: set[str] = set()
    fee_table = fees
    if cross_border is not None and cross_border_names:
        extra = float(cross_border.fx_spread) + float(cross_border.commission)
        if extra != 0.0:
            fee_table = dict(fees)
            for name in cross_border_names:
                if name in fee_table:
                    fee_table[name] = float(fee_table[name]) + extra
    target_rows = {}
    if targets is not None and not targets.empty and premium is None:
        target_rows = {pd.Timestamp(day).normalize(): row for day, row in targets.iterrows()}
    decision_rows = {}
    use_decisions = decisions is not None and not decisions.empty and (premium is not None or not target_rows)
    if use_decisions:
        decision_rows = {pd.Timestamp(day).normalize(): row for day, row in decisions.iterrows()}
    held_rows = []
    peak_rows = []
    net_rows = []
    gross_rows = []
    cost_rows = []
    buy_rows = []
    sell_rows = []
    index = []
    exits = []
    deferred = []
    applied_rows = []
    applied_index = []
    code_rows = []

    def spot(name: str, stamp: pd.Timestamp, codes: dict[str, float] | None = None) -> float | None:
        return _spot_level(levels, code_levels, name, codes if codes is not None else code_book.get(name) or {},
                           stamp, weight_eps)

    for day in pnl.index:
        stamp = pd.Timestamp(day).normalize()
        held_rows.append([weights.get(name, 0.0) for name in columns])
        rets: dict[str, float] = {}
        for name in columns:
            if name == cash_id:
                number = _finite(pnl.at[day, name])
                rets[name] = 0.0 if number is None else number
                continue
            codes = code_book.get(name) or {}
            basket = None
            if _active(codes, weight_eps) and code_returns and name in code_returns:
                basket = _basket_return(codes, code_returns[name], stamp, weight_eps)
            if basket is not None:
                rets[name] = basket
            else:
                number = _finite(pnl.at[day, name])
                rets[name] = 0.0 if number is None else number
        if cross_border is not None and dividend_yield is not None and cross_border.dividend_withholding:
            rate = float(cross_border.dividend_withholding)
            for name in cross_border_names or ():
                if name == cash_id or name not in rets or name not in dividend_yield.columns:
                    continue
                if stamp not in dividend_yield.index:
                    continue
                value = _finite(dividend_yield.at[stamp, name])
                if value is None or value <= 0.0:
                    continue
                rets[name] = float(rets[name]) - value * rate
        for name, weight in list(weights.items()):
            if name == cash_id or weight <= weight_eps:
                continue
            if len(_active(code_book.get(name), weight_eps)) > 1:
                if name not in baskets:
                    baskets[name] = 1.0
                if rets.get(name) is not None and math.isfinite(rets[name]):
                    baskets[name] = float(baskets[name]) * (1.0 + float(rets[name]))
        gross, drifted = drift(weights, rets)
        for name in list(code_book):
            code_book[name] = _scale_codes(code_book[name], drifted.get(name, 0.0), weight_eps)
        if refills:
            scale = 1.0 + gross
            growth = (1.0 + float(rets.get(cash_id, 0.0))) / scale if scale != 0.0 else 1.0
            for order in refills:
                order["proceeds"] = float(order.get("proceeds") or 0.0) * growth
        cost = 0.0
        buy = 0.0
        sell = 0.0
        rebalanced = False
        target = None
        if pending is not None:
            target = pending
            pending = None
            rebalanced = True
            retry = None
            refills.clear()
            exited.clear()
        elif stamp in target_rows:
            target = _Pending(_row_weights(target_rows[stamp], columns, cash_id), {})
            rebalanced = True
            retry = None
            refills.clear()
            exited.clear()
        elif fill_limits and retry is not None:
            target = retry
            retry = None
            rebalanced = True
        blocked_fill = False
        tradable = {}
        traded_names = [name for name in columns if name != cash_id]
        if rebalanced and target is not None and fill_limits:
            tradable = session_tradable(fill_quotes, stamp, traded_names)
            blocked_fill = not legs_clear(drifted, target.weights, tradable, cash_id, trade_eps)
        if rebalanced and target is not None and blocked_fill:
            new_w = executable_weights(drifted, target.weights, tradable, cash_id, trade_eps)
            before_codes = {name: dict(codes) for name, codes in code_book.items()}
            after_codes = {
                name: _scale_codes(before_codes.get(name) or {}, float(new_w.get(name, 0.0)), weight_eps)
                for name in code_book
            }
            cost, buy, sell = _execution_cost(
                drifted, new_w, before_codes, after_codes, fee_table, cash_id, trade_eps)
            weights = {name: float(new_w.get(name, 0.0)) for name in columns}
            code_book = after_codes
            tosell = []
            stopped = set()
            retry = target
            for name in list(peaks):
                if weights.get(name, 0.0) <= weight_eps:
                    peaks.pop(name, None)
                    baskets.pop(name, None)
            for name, weight in weights.items():
                if name == cash_id or weight <= weight_eps:
                    continue
                if abs(weight - float(drifted.get(name, 0.0))) <= trade_eps:
                    continue
                multi = len(_active(code_book.get(name), weight_eps)) > 1
                mark = baskets.get(name) if multi else spot(name, stamp)
                if valid_mark(mark):
                    peaks[name] = float(mark)
                    if multi:
                        baskets[name] = float(mark)
            applied_rows.append([weights.get(name, 0.0) for name in columns])
            applied_index.append(stamp)
        elif rebalanced and target is not None:
            after_codes = {name: {} for name in code_book}
            for name, codes in target.codes.items():
                after_codes[name] = dict(codes)
            cost, buy, sell = _execution_cost(
                drifted, target.weights, code_book, after_codes, fee_table, cash_id, trade_eps)
            weights = {name: float(target.weights.get(name, 0.0)) for name in columns}
            code_book = after_codes
            tosell = []
            stopped = set()
            peaks = {}
            for name, weight in weights.items():
                if name == cash_id or weight <= weight_eps:
                    baskets.pop(name, None)
                    continue
                multi = len(_active(code_book.get(name), weight_eps)) > 1
                if multi and drifted.get(name, 0.0) <= weight_eps:
                    baskets[name] = 1.0
                    peaks[name] = 1.0
                    continue
                mark = baskets[name] if multi and name in baskets else spot(name, stamp)
                if valid_mark(mark):
                    peaks[name] = float(mark)
                    baskets[name] = float(mark)
            applied_rows.append([weights.get(name, 0.0) for name in columns])
            applied_index.append(stamp)
        else:
            weights = drifted
            still: list[str] = []
            filled_slots: list[tuple[str, float]] = []
            # 同一天既有顺延卖单又有补位买单时先卖后买。补位只用卖出之前已经在账上的现金。
            cash_for_refill = float(weights.get(cash_id, 0.0))
            limit_flags = session_tradable(fill_quotes, stamp, traded_names) if fill_limits else None
            for name in list(tosell):
                weight = float(weights.get(name, 0.0))
                if weight <= weight_eps:
                    continue
                multi = len(_active(code_book.get(name), weight_eps)) > 1
                mark = baskets.get(name) if multi else spot(name, stamp)
                if limit_flags is not None and not limit_flags.get(name, (False, False))[1]:
                    still.append(name)
                    deferred.append({"date": stamp, "name": name, "reason": "limit_or_no_price"})
                    continue
                if not valid_mark(mark):
                    still.append(name)
                    deferred.append({"date": stamp, "name": name, "reason": "missing_exit_price"})
                    continue
                cost += weight * float(fee_table[name])
                sell += weight
                weights[cash_id] = float(weights.get(cash_id, 0.0)) + weight
                weights[name] = 0.0
                code_book[name] = {}
                peaks.pop(name, None)
                baskets.pop(name, None)
                stopped.discard(name)
                exits.append({"date": stamp, "name": name, "price": float(mark), "kind": "exit"})
                filled_slots.append((name, weight))
            tosell = still
            if refill_targets is not None:
                sold_names = {name for name, _weight in filled_slots}
                for order in refills:
                    if order.get("armed") and sold_names:
                        order["exclude"] = set(order.get("exclude") or ()) | sold_names
                extra_cost, extra_buy = _fill_due_refills(
                    weights, refills, stamp, cash_id, fee_table, fill_limits, fill_quotes,
                    columns, trade_eps, weight_eps, peaks, spot, deferred,
                    cash_cap=cash_for_refill)
                cost += extra_cost
                buy += extra_buy
            if refill_targets is not None and filled_slots:
                _queue_refill(refills, filled_slots, exited, refill_targets, stamp, trade_eps)
        cost *= cost_multiplier
        if retry is None:
            for name, weight in list(weights.items()):
                if name == cash_id or weight <= weight_eps:
                    continue
                multi = len(_active(code_book.get(name), weight_eps)) > 1
                mark = baskets.get(name) if multi else spot(name, stamp)
                if not valid_mark(mark):
                    continue
                if name not in peaks:
                    peaks[name] = float(mark)
                    continue
                peaks[name] = max(float(peaks[name]), float(mark))
                if triggered(float(mark), float(peaks[name]), drawdown) and name not in stopped:
                    stopped.add(name)
                    tosell.append(name)
                    exits.append({
                        "date": stamp, "name": name, "price": float(mark),
                        "peak": float(peaks[name]), "kind": "signal",
                    })
        if refill_targets is not None:
            for order in refills:
                if not order.get("armed"):
                    order["armed"] = True
        if stamp in decision_rows:
            raw = _row_weights(decision_rows[stamp], columns, cash_id)
            codes: dict[str, dict[str, float]] = {}
            ctx = premium.on(stamp) if premium is not None and hasattr(premium, "on") else premium
            if ctx:
                from .premium_wire import adjust_decision
                raw, codes = adjust_decision(
                    raw, weights, code_book, ctx, stamp, cash_id, weight_eps)
            pending = _Pending(raw, codes)
        for name, codes in code_book.items():
            for code, weight in codes.items():
                if weight > weight_eps:
                    code_rows.append({
                        "date": stamp, "container": name, "code": code, "weight": float(weight),
                    })
        peak_rows.append([peaks.get(name, float("nan")) for name in columns])
        gross_rows.append(gross)
        net_rows.append(gross - cost)
        cost_rows.append(cost)
        buy_rows.append(buy)
        sell_rows.append(sell)
        index.append(stamp)
    idx = pd.DatetimeIndex(index)
    if premium is not None and applied_index:
        applied = pd.DataFrame(applied_rows, index=pd.DatetimeIndex(applied_index), columns=columns)
    elif targets is not None:
        applied = targets
    else:
        applied = pd.DataFrame(applied_rows, index=pd.DatetimeIndex(applied_index), columns=columns) if applied_index else pd.DataFrame(columns=columns)
    return Book(
        net=pd.Series(net_rows, index=idx, dtype=float, name="net"),
        gross=pd.Series(gross_rows, index=idx, dtype=float, name="gross"),
        held=pd.DataFrame(held_rows, index=idx, columns=columns),
        decisions=decisions if decisions is not None else pd.DataFrame(),
        targets=applied,
        cost=pd.Series(cost_rows, index=idx, dtype=float, name="cost"),
        buy=pd.Series(buy_rows, index=idx, dtype=float, name="buy"),
        sell=pd.Series(sell_rows, index=idx, dtype=float, name="sell"),
        peaks=pd.DataFrame(peak_rows, index=idx, columns=columns),
        exits=pd.DataFrame(exits),
        deferred_exits=pd.DataFrame(deferred),
        code_audit=pd.DataFrame(code_rows),
    )
