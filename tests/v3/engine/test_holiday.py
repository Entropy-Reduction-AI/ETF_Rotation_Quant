"""美国休市被写成收盘 0 时，人民币日收益仍是有限数。"""
import unittest

import numpy as np
import pandas as pd

from src.report.fx import cny_from_usd


class HolidayClose(unittest.TestCase):
    def test_zero_close_on_sandy_is_not_a_crash(self):
        calendar = pd.to_datetime(["2012-10-26", "2012-10-29", "2012-10-30", "2012-10-31", "2012-11-01"])
        usd = pd.DataFrame({
            "date": pd.to_datetime(["2012-10-26", "2012-10-29", "2012-10-31"]),
            "open": [2828.0, None, None],
            "high": [2839.0, 0.0, 0.0],
            "low": [2797.0, 0.0, 0.0],
            "close": [2828.62219942411, 0.0, 2809.95163633277],
            "volume": [0.0, 0.0, 0.0],
        })
        fx = pd.Series([6.301, 6.2992, 6.3028, 6.3002, 6.3017], index=calendar)
        priced = cny_from_usd(usd, fx, pd.DatetimeIndex(calendar))
        level = pd.Series(priced["close_cny"].to_numpy(dtype=float), index=pd.to_datetime(priced["date"]))
        returns = level.pct_change().dropna()
        self.assertTrue(np.isfinite(returns.to_numpy()).all())
        self.assertGreater(float(returns.loc[pd.Timestamp("2012-10-30")]), -0.05)
        self.assertNotEqual(float(level.loc[pd.Timestamp("2012-10-30")]), 0.0)
        reopen = float(returns.loc[pd.Timestamp("2012-11-01")])
        self.assertGreater(reopen, -0.02)
        self.assertLess(reopen, 0.0)
