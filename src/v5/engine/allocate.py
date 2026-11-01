"""§4.2 S0、§4.3 C1、§7.1 三种结构对照。

只产出目标权重，不读行情库，不算组合收益。

和 v3 不同、预注册没有写死的地方，按字面实现并记在工作记录里：
同分只看容器 id，不看 R；C1 的标准差用样本标准差（ddof=1）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.v3.engine.book import DESIGN_END, assert_window
from src.v3.engine.score import Lookback
from src.v3.engine.sessions import decision_dates

from .classes import CASH_CLASS, DEFENSIVE_CLASSES, RISK_CLASSES

LOOKBACKS = (20, 60, 120, 250)
BLEND_COUNT = 4
STRUCTURE_S0 = "s0"
STRUCTURE_STRONGEST = "strongest_class"
STRUCTURE_FIXED_BUDGET = "fixed_budget"
STRUCTURE_NO_DEFENSE = "no_defense"
STRUCTURES = (
    STRUCTURE_S0,
    STRUCTURE_STRONGEST,
    STRUCTURE_FIXED_BUDGET,
    STRUCTURE_NO_DEFENSE,
)
# §4.3 只写“标准差”。得分波动在 v3 §4.1 是样本标准差，这里沿用 ddof=1。
# 平稳序列上 σ20 会略大于 σ250，m 因此略小于 1。σ20 = 0 时除零，取 m = 1。
VOL_DDOF = 1
VOL_LONG = 250
VOL_SHORT = 20


class EngineError(ValueError):
    pass


@dataclass(frozen=True)
class Sleeve:
    """一个容器在某一个回看期上的输入。参加排名和跑赢现金是两件事。"""

    container_id: str
    class_name: str
    score: float
    total: float
    participates: bool
    beats_cash: bool


def _usable_score(score: float) -> bool:
    return math.isfinite(score) or math.isinf(score)


def _check(sleeves: list[Sleeve], cash_id: str) -> None:
    seen: set[str] = set()
    for row in sleeves:
        if row.container_id == cash_id or row.class_name == CASH_CLASS:
            continue
        if row.container_id in seen:
            raise EngineError(f"重复容器 {row.container_id}")
        seen.add(row.container_id)
        if row.class_name not in RISK_CLASSES and row.class_name not in DEFENSIVE_CLASSES:
            raise EngineError(f"未知大类 {row.class_name}（{row.container_id}）")


def _candidates(sleeves: list[Sleeve], kind: str) -> list[Sleeve]:
    pool = [
        row for row in sleeves
        if row.class_name == kind and row.participates and row.beats_cash and _usable_score(row.score)
    ]
    pool.sort(key=lambda row: (-row.score, row.container_id))
    return pool


def _winners(sleeves: list[Sleeve], kinds: tuple[str, ...]) -> dict[str, Sleeve | None]:
    """每一类单独取 s 最高的一只。没有合格成员就是没开着。"""
    found = {}
    for kind in kinds:
        pool = _candidates(sleeves, kind)
        found[kind] = pool[0] if pool else None
    return found


def _place_defense(winners: dict[str, Sleeve | None], amount: float, cash_id: str) -> dict[str, float]:
    """开着的防守大类等分。都没开着，这笔钱就是现金。"""
    chosen = [winners[kind] for kind in DEFENSIVE_CLASSES if winners[kind] is not None]
    if not chosen or amount == 0.0:
        return {cash_id: amount}
    share = amount / len(chosen)
    out = {cash_id: 0.0}
    for win in chosen:
        out[win.container_id] = out.get(win.container_id, 0.0) + share
    return out


def _risk_split(open_risk: list[Sleeve], cash_id: str) -> dict[str, float]:
    weights = {cash_id: 0.0}
    share = 1.0 / len(open_risk)
    for win in open_risk:
        weights[win.container_id] = share
    return weights


def group_weights(sleeves: list[Sleeve], *, cash_id: str = "cash",
                  structure: str = STRUCTURE_S0) -> dict[str, float]:
    """一个回看期里的第 3 步。结构对照只改这一步。"""
    if structure not in STRUCTURES:
        raise EngineError(f"未知结构 {structure}")
    _check(sleeves, cash_id)
    risk = _winners(sleeves, RISK_CLASSES)
    defense = _winners(sleeves, DEFENSIVE_CLASSES)
    open_risk = [risk[kind] for kind in RISK_CLASSES if risk[kind] is not None]
    if structure == STRUCTURE_NO_DEFENSE and not open_risk:
        return {cash_id: 1.0}
    if structure == STRUCTURE_STRONGEST and open_risk:
        best = sorted(open_risk, key=lambda win: (-win.score, win.container_id))[0]
        return {best.container_id: 1.0, cash_id: 0.0}
    if structure == STRUCTURE_FIXED_BUDGET:
        return _fixed_budget(sleeves, risk, defense, cash_id)
    if not open_risk:
        return _place_defense(defense, 1.0, cash_id)
    return _risk_split(open_risk, cash_id)


def _fixed_budget(sleeves: list[Sleeve], risk: dict[str, Sleeve | None],
                  defense: dict[str, Sleeve | None], cash_id: str) -> dict[str, float]:
    """参加排名的风险大类共 m 个，每类预算 1/m。没开着的那份走 k=0 的防守位。

    m = 0 时 1/m 没有定义。预注册没写这一支，这里把该组做成全现金。
    """
    participating = [
        kind for kind in RISK_CLASSES
        if any(row.class_name == kind and row.participates for row in sleeves)
    ]
    if not participating:
        return {cash_id: 1.0}
    share = 1.0 / len(participating)
    weights = {cash_id: 0.0}
    closed = 0
    for kind in participating:
        win = risk[kind]
        if win is None:
            closed += 1
            continue
        weights[win.container_id] = weights.get(win.container_id, 0.0) + share
    if closed:
        placed = _place_defense(defense, closed * share, cash_id)
        for name, value in placed.items():
            weights[name] = weights.get(name, 0.0) + value
    return weights


def average_lookbacks(groups: list[dict[str, float]], names: list[str], cash_id: str) -> dict[str, float]:
    """四个回看期逐容器算术平均。除数恒为 4。缺的组视为全现金。"""
    if len(groups) > BLEND_COUNT:
        raise EngineError("回看期多于 4 组")
    keys: list[str] = []
    seen: set[str] = set()
    for name in [*names, cash_id]:
        if name not in seen:
            seen.add(name)
            keys.append(name)
    for group in groups:
        for key in group:
            if key not in seen:
                seen.add(key)
                keys.append(key)
    acc = {key: 0.0 for key in keys}
    for group in groups:
        for key in keys:
            acc[key] += float(group.get(key, 0.0))
    acc[cash_id] += float(BLEND_COUNT - len(groups))
    return {key: value / BLEND_COUNT for key, value in acc.items()}


def apply_c1(weights: dict[str, float], multipliers: dict[str, float],
             class_of: dict[str, str], cash_id: str) -> dict[str, float]:
    """风险大类的目标权重乘 m。减下来的进现金。防守大类不乘。"""
    out = {name: float(value) for name, value in weights.items()}
    out.setdefault(cash_id, 0.0)
    released = 0.0
    for name, weight in list(out.items()):
        if name == cash_id or weight == 0.0:
            continue
        if weight < 0.0:
            raise EngineError(f"权重为负 {name}")
        kind = class_of.get(name)
        if kind is None:
            raise EngineError(f"没有大类 {name}")
        if kind not in RISK_CLASSES:
            continue
        if name not in multipliers:
            raise EngineError(f"缺少 {name} 的波动乘数")
        raw = float(multipliers[name])
        if not math.isfinite(raw) or raw < 0.0:
            raise EngineError(f"波动乘数无效 {name}")
        factor = min(1.0, raw)
        scaled = weight * factor
        released += weight - scaled
        out[name] = scaled
    out[cash_id] = float(out[cash_id]) + released
    return out


def blend_lookbacks(groups: list[dict[str, float]], names: list[str], cash_id: str, *,
                    class_of: dict[str, str] | None = None,
                    vol_multipliers: dict[str, float] | None = None) -> dict[str, float]:
    """先按第 4 步合成，再在这一天的目标上乘 C1。不乘时就是 S0。"""
    averaged = average_lookbacks(groups, names, cash_id)
    if vol_multipliers is None:
        return averaged
    if class_of is None:
        raise EngineError("C1 需要大类")
    return apply_c1(averaged, vol_multipliers, class_of, cash_id)


def _valid_history(returns: pd.Series, asof: pd.Timestamp) -> np.ndarray:
    """截至 asof 的有效日收益。有效：有限且大于 −1，与 v3 打分同一条。"""
    stamp = pd.Timestamp(asof)
    if stamp.tzinfo is not None:
        raise EngineError("日收益索引不带时区")
    stamp = stamp.normalize()
    if stamp > DESIGN_END:
        raise EngineError(f"拒绝 {stamp.date()} 的波动：晚于 {DESIGN_END.date()}")
    history = returns.copy()
    history.index = pd.DatetimeIndex(pd.to_datetime(history.index))
    if history.index.tz is not None:
        raise EngineError("日收益索引不带时区")
    history = history[~history.index.duplicated(keep="last")].sort_index()
    history = history.loc[:stamp]
    values = history.to_numpy(dtype=float)
    mask = np.isfinite(values) & (values > -1.0)
    return values[mask]


def vol_multiplier(returns: pd.Series, asof, *, long: int = VOL_LONG, short: int = VOL_SHORT) -> float:
    """m = min(1, σ_long / σ_short)。有效日收益不足 long 个时 m = 1。"""
    if long < 2 or short < 2 or short > long:
        raise EngineError("波动窗口无效")
    valid = _valid_history(returns, pd.Timestamp(asof))
    if valid.size < long:
        return 1.0
    long_std = float(np.std(valid[-long:], ddof=VOL_DDOF))
    short_std = float(np.std(valid[-short:], ddof=VOL_DDOF))
    if not math.isfinite(long_std) or not math.isfinite(short_std) or short_std == 0.0:
        return 1.0
    return min(1.0, long_std / short_std)


def sleeves_on(panel: Lookback, day, names: list[str], class_of: dict[str, str], cash_id: str,
               liquidity: pd.DataFrame | None = None) -> list[Sleeve]:
    """从一张回看期面板取出当天的容器。流动性掩码关掉 = 当天没有载体，不参加排名。"""
    if panel.rankable is None:
        raise EngineError("Lookback 缺少 rankable，无法分开参加排名和跑赢现金")
    stamp = pd.Timestamp(day).normalize()
    total = panel.total.loc[stamp]
    score = panel.score.loc[stamp]
    rankable = panel.rankable.loc[stamp]
    gate = None
    if liquidity is not None:
        if stamp not in liquidity.index:
            raise EngineError(f"{stamp.date()} 没有可交易掩码")
        gate = liquidity.loc[stamp]
    cash_r = float(total[cash_id])
    rows = []
    for name in names:
        if name == cash_id:
            continue
        kind = class_of[name]
        if kind == CASH_CLASS:
            continue
        participates = bool(rankable[name])
        if gate is not None:
            if name not in gate.index:
                raise EngineError(f"{stamp.date()} 的掩码没有 {name}")
            participates = participates and bool(gate[name])
        try:
            r_value = float(total[name])
        except (TypeError, ValueError):
            r_value = float("nan")
        try:
            s_value = float(score[name])
        except (TypeError, ValueError):
            s_value = float("nan")
        beats = math.isfinite(r_value) and math.isfinite(cash_r) and r_value > cash_r
        rows.append(Sleeve(name, kind, s_value, r_value, participates, beats))
    return rows


def _multipliers_on(returns: pd.DataFrame, day, names: list[str], class_of: dict[str, str],
                    cash_id: str) -> dict[str, float]:
    found = {}
    for name in names:
        if name == cash_id or class_of[name] not in RISK_CLASSES:
            continue
        if name not in returns.columns:
            raise EngineError(f"波动序列没有 {name}")
        found[name] = vol_multiplier(returns[name], day)
    return found


def path_decisions(panels: dict[int, Lookback], dates, freq: str, names: list[str],
                   class_of: dict[str, str], cash_id: str, *,
                   liquidity: pd.DataFrame | None = None,
                   structure: str = STRUCTURE_S0,
                   returns: pd.DataFrame | None = None) -> pd.DataFrame:
    """一条路的常规调仓目标。`returns` 给了就乘 C1，不给就是 S0 或结构对照。"""
    assert_window(dates, allow_after=False)
    if freq not in {"week", "month"}:
        raise EngineError(f"未知频率 {freq}")
    days = decision_dates(pd.DatetimeIndex(dates), freq)
    columns = [name for name in names if name != cash_id]
    columns.append(cash_id)
    rows = []
    index = []
    for day in days:
        stamp = pd.Timestamp(day).normalize()
        groups = []
        for length in LOOKBACKS:
            panel = panels.get(length)
            if panel is None or stamp not in panel.score.index:
                groups.append({cash_id: 1.0})
                continue
            sleeves = sleeves_on(panel, stamp, names, class_of, cash_id, liquidity)
            groups.append(group_weights(sleeves, cash_id=cash_id, structure=structure))
        multipliers = None if returns is None else _multipliers_on(returns, stamp, names, class_of, cash_id)
        blended = blend_lookbacks(
            groups, columns, cash_id, class_of=class_of, vol_multipliers=multipliers)
        rows.append([float(blended.get(name, 0.0)) for name in columns])
        index.append(stamp)
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, index=pd.DatetimeIndex(index), columns=columns)
