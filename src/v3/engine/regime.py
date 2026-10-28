"""T1 转折点换挡、T2 按市场状态分配四组权重。

快组和慢组由已有回看期切成两半。v3.1 的四组是 20、60 为快，120、250 为慢。
规则以预注册草案 §4.2、§4.3 为准。开关关闭时这些函数不被调用。

T1 只改慢组的资格：

- 反弹：本组跑输现金，快组都跑赢。慢组可以买，但数据必须够排名。
- 回调：本组跑赢现金，快组都跑输。慢组没有资格，已经持有的也在这次调仓调出。
- 其他情况仍看本组是否跑赢现金。

T2 用 BM-主净值的 60 日趋势效率。q(t) 是此前所有 E(s)（s < t）里严格小于 E(t) 的比例。
此前的 E 少于 250 个时 q = 0.5。f = 0.25 + 0.5 × q。快组各 f/2，慢组各 (1-f)/2。
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
            rebound = (not own) and up and _rankable(prepared[length], stamp, name)
            # 回调：本组仍跑赢、快组都转负。已持有的也不再有资格，本次调仓调出。
            if own and down:
                flags.append(False)
            else:
                flags.append(bool(own or rebound))
            _ = held, weight_eps
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


# 草案 §4.3：此前 E 值少于 250 个时 q = 0.5。不是可调参数。
Q_MIN_HISTORY = 250


def efficiency_series(level: pd.Series | None, window: int) -> pd.Series:
    """每个时点的 E(t)。窗口不够、或窗口里有非正价格时，这一天是空值。"""
    if level is None or window < 1 or len(level) == 0:
        return pd.Series(dtype=float)
    hist = level.sort_index()
    hist = hist[~hist.index.duplicated(keep="last")]
    values = hist.to_numpy(dtype=float)
    out = np.full(len(hist), np.nan)
    for i in range(int(window), len(hist)):
        chunk = values[i - int(window):i + 1]
        if not np.isfinite(chunk).all() or np.any(chunk <= 0.0):
            continue
        change = abs(float(chunk[-1]) - float(chunk[0]))
        path = float(np.abs(np.diff(chunk)).sum())
        out[i] = 0.0 if path == 0.0 else change / path
    return pd.Series(out, index=hist.index, dtype=float)


def percentile_q(efficiency: pd.Series | None, min_history: int = Q_MIN_HISTORY) -> pd.Series:
    """q(t) = 此前 E(s)（s < t）中严格小于 E(t) 的比例。历史少于 min_history 时为 0.5。

    相等的不算小于。E(t) 自己不进入分母。空的 E 不占历史。
    """
    if efficiency is None or len(efficiency) == 0:
        return pd.Series(dtype=float)
    values = efficiency.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    prior: list[float] = []
    need = int(min_history)
    for i, value in enumerate(values):
        if not math.isfinite(float(value)):
            continue
        current = float(value)
        if len(prior) < need:
            out[i] = 0.5
        else:
            out[i] = sum(item < current for item in prior) / float(len(prior))
        prior.append(current)
    return pd.Series(out, index=efficiency.index, dtype=float)


def speed_fraction(q: float | None) -> float | None:
    """f(t) = 0.25 + 0.5 × q(t)。q 先收到 [0, 1]，所以 f 在 25% 到 75%。"""
    if q is None or not math.isfinite(float(q)):
        return None
    clipped = min(1.0, max(0.0, float(q)))
    return 0.25 + 0.5 * clipped


def sleeve_weights_from_q(q: float | None, lookbacks) -> list[float] | None:
    """快组各 f/2，慢组各 (1-f)/2。q 算不出来时返回 None，调用方改回等权。"""
    fraction = speed_fraction(q)
    fast, slow = split_speed(lookbacks)
    if fraction is None or not fast or not slow:
        return None
    fast_set = set(fast)
    fast_each = fraction / float(len(fast))
    slow_each = (1.0 - fraction) / float(len(slow))
    return [fast_each if length in fast_set else slow_each for length in lookbacks]


def blend_sleeves(parts: list[dict[str, float]], q: float | None, lookbacks,
                  names: list[str], cash_id: str, equal) -> dict[str, float]:
    """`equal` 是 v3.1 的等权平均。q 为空时直接调用它。"""
    sleeve = sleeve_weights_from_q(q, lookbacks)
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
