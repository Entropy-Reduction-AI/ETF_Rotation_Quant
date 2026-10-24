"""Cash returns for reviewer market loader (mirrors engine benchmark.cash_returns)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.research.prereg_v2.engine import cash_daily, haven_total_return, load_haven


def cash_returns(db: Path, calendar: pd.DatetimeIndex, end: str | pd.Timestamp,
                 annual: float = 0.02) -> pd.Series:
    end_ts = pd.Timestamp(end)
    closes, dividends = load_haven(Path(db), "511880", end_ts)
    if closes.empty:
        return pd.Series(cash_daily(annual), index=pd.DatetimeIndex(calendar), dtype=float)
    series = haven_total_return(closes, dividends, calendar, cash_daily(annual))
    series.index = pd.to_datetime(series.index)
    return series.astype(float)
