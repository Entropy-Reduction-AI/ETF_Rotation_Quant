"""T1 转折点换挡、T2 按趋势效率分配四组权重、T3 离场后补位。

规则见 v4 研究备忘 §4。快组和慢组由已有回看期切成两半，不另加自由度。
v3.1 的四组是 20、60 为快，120、250 为慢。T2 的窗口长度由调用方传入，占位值
不在这里写死成预注册参数。

T1 是 C1 的两个方向：

- 反弹：快组都跑赢现金、慢组自己还没有。慢组也可以买它，但数据必须够排名。
- 回调：快组都没跑赢现金、慢组自己仍跑赢。慢组不新买它；上一决策日本组已经持有的可以留。

快组本身的过滤不变。一快一慢对不上时，不换挡，各组仍看自己。
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .score import Lookback, weighted_average


def split_speed(lookbacks) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """较短的一半是快组，较长的一半是慢组。奇数个时中间那档归慢组。"""
    ordered = tuple(sorted(int(length) for length in lookbacks))
    mid = len(ordered) // 2
    return ordered[:mid], ordered[mid:]


def _flag(panel: Lookback, day: pd.Timestamp, name: str) -> bool:
    if day not in panel.ok.index or name not in panel.ok.columns:
        return False
    return bool(panel.ok.at[day, name])


def _rankable(panel: Lookback, day: pd.Timestamp, name: str) -> bool:
    frame = panel.rankable
    if frame is None or day not in frame.index or name not in frame.columns:
        return False
    return bool(frame.at[day, name])


def t1_eligible(prepared: dict[int, Lookback], day: pd.Timestamp, names: list[str], lookbacks,
                held: dict[int, dict[str, float]], weight_eps: float) -> dict[int, pd.Series]:
    """每个回看期一张是否可排名的表。快组等于原来的 `ok`。"""
    fast, _slow = split_speed(lookbacks)
    fast_set = set(fast)
    stamp = pd.Timestamp(day).normalize()
    out: dict[int, pd.Series] = {}
    for length in lookbacks:
        flags = []
        for name in names:
            own = _flag(prepared[length], stamp, name)
            if length in fast_set or not fast:
                flags.append(own)
                continue
            up = all(_flag(prepared[item], stamp, name) for item in fast)
            down = all(not _flag(prepared[item], stamp, name) for item in fast)
            prev = float(held.get(length, {}).get(name, 0.0)) > weight_eps
            rebound = (not own) and up and _rankable(prepared[length], stamp, name)
            pullback_block = own and down and (not prev)
            flags.append((own and not pullback_block) or rebound)
        out[length] = pd.Series(flags, index=names, dtype=bool)
    return out


def trend_efficiency(level: pd.Series | None, day, window: int) -> float | None:
    """Kaufman 趋势效率：|净变动| / 每日绝对变动之和。样本不足时返回 None，调用方改回等权。"""
    if level is None or window < 1 or len(level) == 0:
        return None
    stamp = pd.Timestamp(day).normalize()
    hist = level.loc[:stamp]
    values = hist.to_numpy(dtype=float)
    keep = np.isfinite(values) & (values > 0.0)
    hist = hist.loc[keep]
    if len(hist) <= window:
        return None
    px = hist.iloc[-(window + 1):].to_numpy(dtype=float)
    change = abs(float(px[-1]) - float(px[0]))
    path = float(np.abs(np.diff(px)).sum())
    if path == 0.0:
        return 0.0
    return change / path


def sleeve_weights(efficiency: float | None, lookbacks) -> list[float] | None:
    """效率高时快组权重大，效率低时慢组权重大。None 表示这一天用原来的等权平均。"""
    if efficiency is None or not math.isfinite(efficiency):
        return None
    fast, slow = split_speed(lookbacks)
    if not fast or not slow:
        return None
    er = min(1.0, max(0.0, float(efficiency)))
    fast_set = set(fast)
    fast_each = er / float(len(fast))
    slow_each = (1.0 - er) / float(len(slow))
    return [fast_each if length in fast_set else slow_each for length in lookbacks]


def blend_sleeves(parts: list[dict[str, float]], efficiency: float | None, lookbacks,
                  names: list[str], cash_id: str, equal) -> dict[str, float]:
    """`equal` 是 v3.1 的等权平均函数。效率算不出来时直接调用它。"""
    sleeve = sleeve_weights(efficiency, lookbacks)
    if sleeve is None:
        return equal(parts, names, cash_id)
    return weighted_average(parts, sleeve, names, cash_id)


def next_replacement(rank_row, held: set[str]) -> str | None:
    """排名数字小的优先。NaN 或缺值不参与。`held` 含刚卖掉的名字和仍持有的名字。"""
    best_name = None
    best_rank = None
    items = rank_row.items() if hasattr(rank_row, "items") else []
    for name, value in items:
        if name in held:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(number):
            continue
        if best_rank is None or number < best_rank or (number == best_rank and str(name) < str(best_name)):
            best_rank = number
            best_name = str(name)
    return best_name


def daily_ranks(prepared: dict[int, Lookback], dates: pd.DatetimeIndex, names: list[str], lookbacks,
                sort_ids: dict[str, str], liquidity: pd.DataFrame | None, *, t1: bool = False,
                weight_eps: float = 1e-6) -> pd.DataFrame:
    """每个交易日一张排名。0 是最优先的合格标的，不合格是 NaN。T3 用当天这张表补位。

    补位是新买，所以 T1 打开时用空持仓做换挡：回调里的慢组信号不会把名字排进来。
    """
    rows = []
    index = []
    empty = {int(length): {} for length in lookbacks}
    for day in dates:
        stamp = pd.Timestamp(day).normalize()
        masks = t1_eligible(prepared, stamp, names, lookbacks, empty, weight_eps) if t1 else None
        ranked = []
        for name in names:
            if liquidity is not None and stamp in liquidity.index and name in liquidity.columns:
                if not bool(liquidity.at[stamp, name]):
                    continue
            scores = []
            totals = []
            for length in lookbacks:
                allowed = bool(masks[length].at[name]) if masks is not None else _flag(prepared[length], stamp, name)
                if not allowed:
                    continue
                panel = prepared[length]
                if stamp not in panel.score.index or name not in panel.score.columns:
                    continue
                score = float(panel.score.at[stamp, name])
                total = float(panel.total.at[stamp, name])
                if not math.isfinite(score) or not math.isfinite(total):
                    continue
                scores.append(score)
                totals.append(total)
            if not scores:
                continue
            ranked.append((-sum(scores) / len(scores), -sum(totals) / len(totals), sort_ids.get(name, name), name))
        ranked.sort()
        row = {name: float("nan") for name in names}
        for pos, item in enumerate(ranked):
            row[item[3]] = float(pos)
        rows.append([row[name] for name in names])
        index.append(stamp)
    return pd.DataFrame(rows, index=pd.DatetimeIndex(index), columns=names)
