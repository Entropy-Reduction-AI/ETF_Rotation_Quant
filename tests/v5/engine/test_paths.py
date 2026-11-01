"""§4.1 两路合成，§4.4 离场。手造价格，日期停在设计期内。"""
from __future__ import annotations

import unittest

import pandas as pd

from src.v3.engine.book import RunnerError
from src.v3.engine.costs import CrossBorderCosts
from src.v3.engine.exit import NO_EXIT, simulate_path
from src.v3.engine.limits import FillQuote
from src.v4.scorecard.core import ScorecardError
from src.v5.engine.allocate import EngineError
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
        self.assertEqual(float((off.cost - on.cost).abs().max()), 0.0)

    def test_c2_refuses_dates_after_the_design_period(self):
        days = pd.bdate_range("2016-01-04", periods=3)
        pnl = pd.DataFrame({"asset": 0.0, "cash": 0.0}, index=days)
        decisions = pd.DataFrame([{"asset": 1.0, "cash": 0.0}], index=[days[0]])
        fees = {"asset": 0.001, "cash": 0.0005}
        with self.assertRaises(RunnerError):
            run_path(pnl, fees, "cash", decisions, enable_c2=False)

    def test_no_exit_is_opt_in_and_the_default_still_sells(self):
        days = pd.bdate_range("2006-02-01", periods=6)
        level = pd.Series(100.0, index=days, dtype=float)
        level.iloc[3:] = 80.0
        pnl = pd.DataFrame({"asset": level.pct_change().fillna(0.0), "cash": 0.0}, index=days)
        levels = pd.DataFrame({"asset": level, "cash": 1.0}, index=days)
        targets = pd.DataFrame([{"asset": 1.0, "cash": 0.0}], index=[days[0]])
        fees = {"asset": 0.001, "cash": 0.0005}
        default = simulate_path(pnl, levels, fees, "cash", targets=targets)
        quiet = simulate_path(pnl, levels, fees, "cash", targets=targets, exit_drawdown=NO_EXIT)
        self.assertIsNone(NO_EXIT)
        self.assertAlmostEqual(float(default.held.loc[days[-1], "asset"]), 0.0)
        self.assertAlmostEqual(float(quiet.held.loc[days[-1], "asset"]), 1.0)
        with self.assertRaises(EngineError):
            run_path(pnl, fees, "cash", targets, enable_c2=False, exit_drawdown=0.08)

    def test_s0_and_c2_defer_the_same_limit_up_when_exit_never_fires(self):
        days = pd.to_datetime(["2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09", "2006-01-10"])
        levels = pd.DataFrame({"asset": 100.0, "other": 50.0, "cash": 1.0}, index=days)
        pnl = pd.DataFrame({"asset": 0.0, "other": 0.0, "cash": 0.0}, index=days)
        decisions = pd.DataFrame([{"asset": 1.0, "other": 0.0, "cash": 0.0}], index=[days[0]])
        fees = {"asset": 0.001, "other": 0.001, "cash": 0.0005}
        quotes = {
            "asset": FillQuote(
                close=pd.Series([10.0, 10.0, 11.0, 12.1, 12.1], index=pd.to_datetime(
                    ["2006-01-03", "2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09"])),
                board="main",
            ),
        }
        clear = {
            "asset": FillQuote(
                close=pd.Series(10.0, index=pd.to_datetime(
                    ["2006-01-03", "2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09"])),
                board="main",
            ),
        }
        kwargs = dict(fill_limits=True, fill_quotes=quotes)
        off = run_path(pnl, fees, "cash", decisions, enable_c2=False, levels=levels, **kwargs)
        on = run_path(pnl, fees, "cash", decisions, enable_c2=True, levels=levels, **kwargs)
        opened = run_path(
            pnl, fees, "cash", decisions, enable_c2=False, levels=levels,
            fill_limits=True, fill_quotes=clear,
        )
        self.assertEqual(float((off.net - on.net).abs().max()), 0.0)
        self.assertEqual(float((off.held - on.held).abs().to_numpy().max()), 0.0)
        self.assertEqual(float((off.cost - on.cost).abs().max()), 0.0)
        self.assertAlmostEqual(float(off.held.loc[days[2], "asset"]), 0.0)
        self.assertAlmostEqual(float(on.held.loc[days[2], "asset"]), 0.0)
        self.assertAlmostEqual(float(off.cost.loc[days[1]]), 0.0)
        self.assertAlmostEqual(float(off.cost.loc[days[2]]), 0.0)
        self.assertAlmostEqual(float(off.cost.loc[days[3]]), 0.0015)
        self.assertAlmostEqual(float(off.held.loc[days[4], "asset"]), 1.0)
        self.assertAlmostEqual(float(opened.held.loc[days[2], "asset"]), 1.0)
        self.assertAlmostEqual(float(opened.cost.loc[days[1]]), 0.0015)
        self.assertTrue(on.exits.empty)

    def test_delay_moves_the_fill_one_session_and_c2_stays_identical(self):
        days = pd.bdate_range("2006-04-03", periods=6)
        levels = pd.DataFrame({"asset": 100.0, "cash": 1.0}, index=days)
        pnl = pd.DataFrame({"asset": 0.0, "cash": 0.0}, index=days)
        decisions = pd.DataFrame([{"asset": 1.0, "cash": 0.0}], index=[days[0]])
        fees = {"asset": 0.001, "cash": 0.0005}
        plain = run_path(pnl, fees, "cash", decisions, enable_c2=False, levels=levels)
        delayed = run_path(
            pnl, fees, "cash", decisions, enable_c2=False, levels=levels, decision_delay=1)
        delayed_on = run_path(
            pnl, fees, "cash", decisions, enable_c2=True, levels=levels, decision_delay=1)
        self.assertAlmostEqual(float(plain.held.loc[days[2], "asset"]), 1.0)
        self.assertAlmostEqual(float(delayed.held.loc[days[2], "asset"]), 0.0)
        self.assertAlmostEqual(float(delayed.held.loc[days[3], "asset"]), 1.0)
        self.assertEqual(float((delayed.net - delayed_on.net).abs().max()), 0.0)
        self.assertEqual(float((delayed.held - delayed_on.held).abs().to_numpy().max()), 0.0)
        self.assertEqual(float((delayed.cost - delayed_on.cost).abs().max()), 0.0)

    def test_cross_border_dividend_is_withheld_on_the_same_path(self):
        days = pd.bdate_range("2006-05-02", periods=4)
        pnl = pd.DataFrame({"asset": [0.0, 0.0, 0.02, 0.0], "cash": 0.0}, index=days)
        levels = pd.DataFrame({"asset": 100.0, "cash": 1.0}, index=days)
        decisions = pd.DataFrame([{"asset": 1.0, "cash": 0.0}], index=[days[0]])
        fees = {"asset": 0.0, "cash": 0.0}
        dividend = pd.DataFrame({"asset": [0.0, 0.0, 0.02, 0.0]}, index=days)
        plain = run_path(pnl, fees, "cash", decisions, enable_c2=False, levels=levels)
        taxed = run_path(
            pnl, fees, "cash", decisions, enable_c2=False, levels=levels,
            cross_border=CrossBorderCosts(dividend_withholding=0.5),
            cross_border_names={"asset"}, dividend_yield=dividend,
        )
        self.assertAlmostEqual(float(plain.net.loc[days[2]]), 0.02)
        self.assertAlmostEqual(float(taxed.net.loc[days[2]]), 0.01)
        self.assertEqual(float((plain.held - taxed.held).abs().to_numpy().max()), 0.0)


if __name__ == "__main__":
    unittest.main()
