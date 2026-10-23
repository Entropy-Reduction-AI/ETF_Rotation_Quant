"""构造数据：换汇、月初再平衡、区间指标。"""
from __future__ import annotations

import math
import unittest

import numpy as np
import pandas as pd

from src.report.blend import monthly_rebalance
from src.report.fx import cny_from_usd, latest_on_or_before
from src.report.metrics import ann_vol, cagr, calmar, decay_split, max_drawdown, sharpe, tracking_error
from src.research.prereg_v2.engine import monthly_blend


class FxConversion(unittest.TestCase):
    def test_latest_mid_on_or_before_the_day(self):
        fx = pd.Series([7.0, 8.0], index=pd.to_datetime(["2024-01-03", "2024-01-05"]))
        days = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
        got = latest_on_or_before(fx, pd.DatetimeIndex(days))
        self.assertTrue(math.isnan(got.iloc[0]))
        self.assertEqual(list(got.iloc[1:]), [7.0, 7.0, 8.0])

    def test_cny_uses_prior_usd_close_and_same_day_or_prior_mid(self):
        usd = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
            "open": [100.0, 110.0, 120.0],
            "high": [100.0, 110.0, 120.0],
            "low": [100.0, 110.0, 120.0],
            "close": [100.0, 110.0, 120.0],
            "volume": [0.0, 0.0, 0.0],
        })
        calendar = pd.to_datetime(["2024-01-03", "2024-01-04", "2024-01-05"])
        fx = pd.Series([7.0, 8.0], index=pd.to_datetime(["2024-01-03", "2024-01-05"]))
        out = cny_from_usd(usd, fx, pd.DatetimeIndex(calendar))
        self.assertEqual(list(pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")), ["2024-01-03", "2024-01-04", "2024-01-05"])
        self.assertEqual(list(out["close"]), [100.0, 110.0, 120.0])
        self.assertEqual(list(out["close_cny"]), [700.0, 770.0, 960.0])


class MonthStartBlend(unittest.TestCase):
    def test_resets_on_the_first_session_of_the_month(self):
        index = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-02-01"])
        frame = pd.DataFrame({
            "a": [0.10, 0.00, 0.00],
            "b": [0.00, 0.00, 0.20],
            "c": [0.00, 0.00, 0.20],
        }, index=index)
        port, weights = monthly_rebalance(frame, {"a": 0.70, "b": 0.15, "c": 0.15})
        self.assertAlmostEqual(port.iloc[0], 0.07)
        self.assertAlmostEqual(port.iloc[1], 0.0)
        self.assertAlmostEqual(port.iloc[2], 0.06)
        self.assertAlmostEqual(weights.iloc[2]["a"], 0.70)
        drifted = 0.70 * 1.10 / 1.07
        self.assertAlmostEqual(weights.iloc[1]["a"], drifted)

    def test_two_asset_case_matches_monthly_blend(self):
        index = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-02-01"])
        a = pd.Series([0.10, -0.02, 0.01], index=index)
        o = pd.Series([0.00, 0.03, 0.20], index=index)
        got, _weights = monthly_rebalance(pd.DataFrame({"a": a, "o": o}), {"a": 0.70, "o": 0.30})
        expect = monthly_blend(a, o, 0.70)
        self.assertLess(float((got - expect).abs().max()), 1e-12)


class MetricMath(unittest.TestCase):
    def setUp(self):
        self.index = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
        self.returns = pd.Series([0.01, -0.02, 0.03], index=self.index)

    def test_cagr_vol_drawdown_sharpe_calmar(self):
        nav = 1.01 * 0.98 * 1.03
        years = 3 / 252
        self.assertAlmostEqual(cagr(self.returns), nav ** (1 / years) - 1)
        self.assertAlmostEqual(ann_vol(self.returns), float(np.std([0.01, -0.02, 0.03], ddof=1) * np.sqrt(252)))
        depth = max_drawdown(self.returns)
        self.assertAlmostEqual(depth["max_drawdown"], 0.98 - 1)
        self.assertEqual(str(depth["peak"].date()), "2024-01-02")
        self.assertEqual(str(depth["trough"].date()), "2024-01-03")
        rf = pd.Series(0.0, index=self.index)
        values = np.array([0.01, -0.02, 0.03])
        expect_sharpe = values.mean() / values.std(ddof=1) * np.sqrt(252)
        self.assertAlmostEqual(sharpe(self.returns, rf), expect_sharpe)
        self.assertAlmostEqual(calmar(self.returns), cagr(self.returns) / 0.02)

    def test_tracking_error_uses_monthly_excess(self):
        left = pd.Series(
            [0.10, 0.00, 0.00],
            index=pd.to_datetime(["2024-01-31", "2024-02-15", "2024-02-29"]),
        )
        right = pd.Series(0.0, index=left.index)
        excess = np.array([0.10, 0.0])
        expect = float(excess.std(ddof=1) * np.sqrt(12))
        self.assertAlmostEqual(tracking_error(left, right), expect)

    def test_decay_splits_into_benchmark_and_relative(self):
        split = decay_split(0.20, 0.05, 0.08, 0.03)
        self.assertAlmostEqual(split["decay_total"], -0.15)
        self.assertAlmostEqual(split["decay_benchmark"], -0.05)
        self.assertAlmostEqual(split["decay_relative"], -0.10)
        self.assertAlmostEqual(split["decay_total"], split["decay_benchmark"] + split["decay_relative"])


if __name__ == "__main__":
    unittest.main()
