"""French 49 起点经验。只解析 192607–199812，再按冻结代码从 1953 年起算。"""

from __future__ import annotations

import io
import math

import numpy as np
import pandas as pd

WINDOW = ("192607", "199812")


def _panel(text: str, title: str, start: str = WINDOW[0], end: str = WINDOW[1]) -> pd.DataFrame:
    lines = text.splitlines()
    start_at = next(i for i, line in enumerate(lines) if title in line) + 1
    header = [part.strip() for part in lines[start_at].split(",")]
    kept = []
    for line in lines[start_at + 1:]:
        if not line.strip():
            break
        token = line.split(",", 1)[0].strip()
        if not token.isdigit():
            break
        if token < start or token > end:
            continue
        kept.append(line)
    frame = pd.read_csv(io.StringIO("\n".join([",".join(header), *kept])), index_col=0)
    frame.columns = [str(column).strip() for column in frame.columns]
    frame.index = pd.to_datetime(frame.index.astype(str).str.strip(), format="%Y%m") + pd.offsets.MonthEnd(0)
    return frame.astype(float).where(lambda values: values > -99)


def value_weighted_market(official_text: str) -> pd.DataFrame:
    """冻结 `topn_longhist.py`：1953 起的 49 行业收益，加市值加权的 MKT。不用 DTB3。"""
    returns = _panel(official_text, "Average Value Weighted Returns -- Monthly") / 100.0
    firms = _panel(official_text, "Number of Firms in Portfolios")
    size = _panel(official_text, "Average Firm Size")
    cap = firms * size
    weights = cap.shift(1).div(cap.shift(1).sum(axis=1), axis=0)
    market = (weights * returns).sum(axis=1, min_count=1)
    returns = returns.loc["1953":]
    market = market.loc["1953":]
    return pd.concat([returns, market.rename("MKT")], axis=1)


def phi(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def confidence(history: list[float], prior: list[float] | None = None, min_n: int = 12) -> float:
    sample = list(prior or []) + list(history)
    if len(sample) < min_n:
        return 0.5
    values = np.asarray(sample, dtype=float)
    scale = float(values.std(ddof=1))
    if scale == 0.0:
        return 0.5
    return phi(float(values.mean()) / scale * math.sqrt(len(values)))


def us_prior(frame: pd.DataFrame) -> list[float]:
    """`topn_phi.monthly` 到 1998-12。均线票是不高于均线，宽度不含 MKT。"""
    data = frame.loc[: "1998-12"]
    level = (1.0 + data.fillna(0.0)).cumprod().where(data.notna().cumsum() > 0)
    momentum = level.shift(1) / level.shift(12) - 1.0
    above = level > level.rolling(10).mean()
    names = [column for column in data.columns if column != "MKT"]
    breadth = above[names].where(level[names].rolling(10).count() == 10).mean(axis=1)
    low = breadth <= breadth.expanding(min_periods=24).quantile(1.0 / 3.0)
    history: list[float] = []
    pending: float | None = None
    columns = list(data.columns)
    for pos in range(12, len(data) - 1):
        if pending is not None:
            history.append(pending)
            pending = None
        stamp = data.index[pos]
        nxt = data.index[pos + 1]
        score = momentum.loc[stamp, columns]
        parent_below = not bool(above.loc[stamp, "MKT"])
        stressed = parent_below and bool(low.loc[stamp])
        leaders = score.dropna().nlargest(3).index
        if stressed and len(leaders):
            pending = float(data.loc[nxt, leaders].mean())
    return history
