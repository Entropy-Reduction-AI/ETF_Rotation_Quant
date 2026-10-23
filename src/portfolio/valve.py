"""慢阀。只给设计期复现用，生产目标不读这里的状态。"""
from __future__ import annotations

import pandas as pd

def slow_valve(shadow: pd.Series, out: float, back: float, cash_monthly: float):
    """d2.py 的 valve。返回 (持有收益, 切换次数, 当月使用的状态)。

    当月收益先按进入该月时的状态记（在场用影子收益，出场用现金），再用该月月末的影子净值决定下月。
    状态 1 在场，0 出场。
    """
    nav = (1 + shadow).cumprod()
    state = 1
    hi = 1.0
    lo = None
    held, during = [], []
    switches = 0
    for i in range(len(shadow)):
        during.append(state)
        held.append(float(shadow.iloc[i]) if state else cash_monthly)
        level = float(nav.iloc[i])
        if state:
            hi = max(hi, level)
            if level / hi - 1 < -out:
                state = 0
                lo = level
                switches += 1
        else:
            lo = min(lo, level)
            if level / lo - 1 > back:
                state = 1
                hi = level
                switches += 1
    index = shadow.index
    return (
        pd.Series(held, index=index, dtype=float),
        switches,
        pd.Series(during, index=index, dtype=int),
    )


def valve_path(shadow: pd.Series, out: float, back: float) -> dict:
    """走到影子序列的最后一根，给出阀状态和距高点回撤。不返回收益序列。"""
    nav = (1 + shadow).cumprod()
    state = 1
    hi = 1.0
    lo = None
    level = 1.0
    for i in range(len(shadow)):
        level = float(nav.iloc[i])
        if state:
            hi = max(hi, level)
            if level / hi - 1 < -out:
                state = 0
                lo = level
        else:
            lo = min(lo, level)
            if level / lo - 1 > back:
                state = 1
                hi = level
    return {"in_market": bool(state), "level": level, "high": hi, "drawdown": level / hi - 1,
            "as_of": shadow.index[-1]}
