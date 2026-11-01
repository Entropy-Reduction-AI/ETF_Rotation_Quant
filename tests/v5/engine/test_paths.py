"""§4.1 两路合成，§4.4 离场。手造价格，日期停在设计期内。"""
from __future__ import annotations

import unittest

import pandas as pd

from src.v3.engine.book import RunnerError
from src.v4.scorecard.core import ScorecardError
from src.v5.engine.paths import arm_return, run_path


class TwoPaths(unittest.TestCase):
    def test_arm_return_is_the_mean_of_the_two_paths(self):
        index = pd.to_datetime(["2006-01-04", "2006-01-05", "2006-01-06"])
        week = pd.Series([0.02, -0.01, 0.00], index=index)
        month = pd.Series([0.04, 0.01, 0.00], index=index)
        blended = arm_return(week, month)
        self.assertEqual(list(blended), [0.03, 0.0, 0.0])
        self.assertEqual(blended.name, "r_A")
        self.assertTrue(blended.index.equals(index))
        swapped = month.copy()
        swapped.index = index[::-1]
        self.assertTrue(arm_return(week, swapped).index.equals(index))

    def test_a_missing_day_is_not_dropped_from_the_divisor(self):
        index = pd.to_datetime(["2006-01-04", "2006-01-05"])
        week = pd.Series([0.02, 0.02], index=index)
        month = pd.Series([0.04], index=index[:1])
        with self.assertRaises(Exception) as caught:
            arm_return(week, month)
        self.assertIn("同一交易日历", str(caught.exception))

    def test_dates_after_the_design_period_are_refused(self):
        index = pd.to_datetime(["2016-01-04", "2016-01-05"])
        series = pd.Series([0.01, 0.01], index=index)
        with self.assertRaises(ScorecardError):
            arm_return(series, series)


class ExitWiring(unittest.TestCase):
    def test_c2_sells_to_cash_and_does_not_buy_another_name(self):
        days = pd.bdate_range("2006-01-02", periods=8)
        level = pd.Series(100.0, index=days, dtype=float)
        level.iloc[3:] = 80.0
        asset = level.pct_change().fillna(0.0)
        pnl = pd.DataFrame({"asset": asset, "other": 0.0, "cash": 0.0}, index=days)
        levels = pd.DataFrame({"asset": level, "other": 100.0, "cash": 1.0}, index=days)
        decisions = pd.DataFrame(
            [{"asset": 1.0, "other": 0.0, "cash": 0.0}],
            index=[days[0]],
        )
        fees = {"asset": 0.001, "other": 0.001, "cash": 0.0005}
        held_off = run_path(pnl, fees, "cash", decisions, enable_c2=False).held
        held_on = run_path(pnl, fees, "cash", decisions, enable_c2=True, levels=levels).held
        self.assertAlmostEqual(float(held_off.loc[days[-1], "asset"]), 1.0)
        self.assertAlmostEqual(float(held_on.loc[days[5], "asset"]), 0.0)
        self.assertAlmostEqual(float(held_on.loc[days[5], "other"]), 0.0)
        self.assertAlmostEqual(float(held_on.loc[days[5], "cash"]), 1.0)
        self.assertAlmostEqual(float(held_on.loc[days[-1], "asset"]), 0.0)
        self.assertAlmostEqual(float(held_on.loc[days[-1], "other"]), 0.0)

    def test_c2_matches_s0_when_the_exit_does_not_fire(self):
        days = pd.bdate_range("2006-03-01", periods=12)
        level = pd.Series([100 * (1.002 ** i) for i in range(len(days))], index=days)
        pnl = pd.DataFrame({
            "asset": level.pct_change().fillna(0.0),
            "other": 0.0,
            "cash": 0.0001,
        }, index=days)
        levels = pd.DataFrame({"asset": level, "other": 50.0, "cash": 1.0}, index=days)
        decisions = pd.DataFrame([{"asset": 0.6, "other": 0.0, "cash": 0.4}], index=[days[0]])
        fees = {"asset": 0.001, "other": 0.001, "cash": 0.0005}
        off = run_path(pnl, fees, "cash", decisions, enable_c2=False)
        on = run_path(pnl, fees, "cash", decisions, enable_c2=True, levels=levels)
        self.assertEqual(float((off.net - on.net).abs().max()), 0.0)
        self.assertEqual(float((off.held - on.held).abs().to_numpy().max()), 0.0)

    def test_c2_refuses_dates_after_the_design_period(self):
        days = pd.bdate_range("2016-01-04", periods=3)
        pnl = pd.DataFrame({"asset": 0.0, "cash": 0.0}, index=days)
        decisions = pd.DataFrame([{"asset": 1.0, "cash": 0.0}], index=[days[0]])
        fees = {"asset": 0.001, "cash": 0.0005}
        with self.assertRaises(RunnerError):
            run_path(pnl, fees, "cash", decisions, enable_c2=False)


if __name__ == "__main__":
    unittest.main()
