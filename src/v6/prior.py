"""美股起点经验。只使用已经截到 1998-12 的三块面板，不打开官网全表。

口径是冻结 topn_phi.monthly：不高于均线算一票，宽度分母不含 MKT。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

def french_ma_vote(level: float, moving_average: float) -> bool:
    """不高于均线。等于均线也算这一票，和项目池的严格低于不同。"""
    return not bool(level > moving_average)


def breadth_ex_parent(above: pd.Series, parent: str) -> float:
    columns = [name for name in above.index if name != parent]
    return float(above[columns].mean())


def _frame(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.index = pd.to_datetime(frame["yyyymm"].astype(str), format="%Y%m") + pd.offsets.MonthEnd(0)
    data = frame.drop(columns=["yyyymm"]).apply(pd.to_numeric, errors="coerce")
    return data.where(data > -99)


def us_prior(directory: Path) -> list[float]:
    """返回 monthly(..., mode='phi') 的 hist。收益用 0 利率占位，hist 本身不用利率。"""
    directory = Path(directory)
    returns = _frame(directory / "vw-monthly.csv") / 100.0
    cap = _frame(directory / "n-firms.csv") * _frame(directory / "avg-firm-size.csv")
    weights = cap.shift(1).div(cap.shift(1).sum(axis=1), axis=0)
    market = (weights * returns).sum(axis=1, min_count=1)
    returns = returns.loc["1953":]
    market = market.loc["1953":]
    frame = pd.concat([returns, market.rename("MKT")], axis=1).loc[:"1998-12"]
    if frame.index.max() > pd.Timestamp("1998-12-31"):
        raise ValueError("起点面板晚于 1998-12")
    return _monthly_phi(frame)


def _monthly_phi(frame: pd.DataFrame) -> list[float]:
    """与 topn_phi.monthly(..., mode='phi') 收集 hist 的循环相同。"""
    level = (1 + frame.fillna(0)).cumprod().where(frame.notna().cumsum() > 0)
    momentum = level.shift(1) / level.shift(12) - 1
    average = level.rolling(10).mean()
    above = level > average
    industries = [name for name in frame.columns if name != "MKT"]
    share = above[industries].where(level[industries].rolling(10).count() == 10).mean(axis=1)
    low = share <= share.expanding(min_periods=24).quantile(1 / 3)
    history: list[float] = []
    pending = None
    for i in range(12, len(frame) - 1):
        day, nxt = frame.index[i], frame.index[i + 1]
        if pending is not None:
            history.append(pending)
            pending = None
        below = french_ma_vote(float(level.loc[day, "MKT"]), float(average.loc[day, "MKT"]))
        if below and bool(low.loc[day]):
            leaders = momentum.loc[day].dropna().nlargest(3).index
            if len(leaders):
                pending = float(frame.loc[nxt, leaders].mean())
    return history
