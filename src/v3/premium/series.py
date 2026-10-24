"""§5.1：溢价、常态线、偏离，以及 §5.2 用的净值 20 日收益。"""
from __future__ import annotations

import pandas as pd

from src.v3.engine.prices import lag_asof

from .rules import NAV_DAYS, NAV_LAG, PremiumSpec, classify_state


def trailing_median(premium: pd.Series, window: int) -> pd.Series:
    """过去 W 个有溢价的交易日的中位数，含当日。不足 W 个为缺失。"""
    finite = premium.dropna()
    median = finite.rolling(window, min_periods=window).median()
    return median.reindex(premium.index)


def premium_frame(close: pd.Series, nav: pd.Series, calendar: pd.DatetimeIndex,
                  spec: PremiumSpec | None = None) -> pd.DataFrame:
    """决策日 T 的溢价 = 当日收盘价 / 不晚于 T−2 的最新单位净值 − 1。

    常态线是这一只 ETF 自己的溢价中位数，不是全市场的。净值 20 日收益用同一条滞后净值。
    """
    spec = spec or PremiumSpec()
    days = pd.DatetimeIndex(pd.to_datetime(calendar)).sort_values().unique()
    prices = pd.Series(close, dtype=float).sort_index()
    prices = prices[prices > 0]
    prices = prices[~prices.index.duplicated(keep="last")]
    values = pd.Series(nav, dtype=float).sort_index()
    values = values[values > 0]
    values = values[~values.index.duplicated(keep="last")]
    aligned = prices.reindex(days)
    lagged = lag_asof(values, days, NAV_LAG)
    premium = aligned / lagged - 1.0
    premium = premium.where(aligned.notna() & lagged.gt(0))
    baseline = trailing_median(premium, spec.window)
    deviation = premium - baseline
    nav_return = lagged / lagged.shift(NAV_DAYS) - 1.0
    state = [
        classify_state(premium.iloc[i], baseline.iloc[i], deviation.iloc[i], nav_return.iloc[i], spec)
        for i in range(len(days))
    ]
    frame = pd.DataFrame({
        "close": aligned.to_numpy(dtype=float),
        "nav": lagged.to_numpy(dtype=float),
        "premium": premium.to_numpy(dtype=float),
        "baseline": baseline.to_numpy(dtype=float),
        "deviation": deviation.to_numpy(dtype=float),
        "nav_return": nav_return.to_numpy(dtype=float),
        "state": state,
    }, index=days)
    frame.index.name = "date"
    return frame
