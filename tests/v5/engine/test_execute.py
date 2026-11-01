"""两路成交走 v4 B0 的入口。手造行情，日期停在设计期内。"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from src.v3.engine.costs import CrossBorderCosts
from src.v3.engine.market import market_from_returns
from src.v3.engine.sessions import decision_dates
from src.v3.engine.switches import EngineSwitches
from src.v4.r5.design import prior_positive, single_jobs
from src.v5.engine.execute import b0_switches, run_arm


def _decisions(panels, dates, freq, names, class_of, cash_id, **kwargs):
    days = decision_dates(pd.DatetimeIndex(dates), freq)
    columns = [name for name in names if name != cash_id]
    columns.append(cash_id)
    row = {name: 0.0 for name in columns}
    row["asset"] = 1.0
    row[cash_id] = 0.0
    if len(days) == 0:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame([row], index=pd.DatetimeIndex([days[0]]))


class SharedEntry(unittest.TestCase):
    def test_b0_switches_match_the_registered_job(self):
        found = {(job.case, job.pool): job for job in single_jobs()}
        self.assertEqual(b0_switches(), found[("B0", "index")].switches())
        self.assertEqual(b0_switches(), found[("B0", "tradable")].switches())
        self.assertFalse(b0_switches(allow_substitute=False).allow_substitute)

    def test_two_paths_average_and_c2_off_keeps_the_crash(self):
        days = pd.bdate_range("2006-03-01", periods=12)
        level = pd.Series(100.0, index=days, dtype=float)
        level.iloc[5:] = 80.0
        signal = pd.DataFrame({
            "asset": level.pct_change().fillna(0.0),
            "cash": 0.0,
        }, index=days)
        fees = {"asset": 0.001, "cash": 0.0005}
        market = market_from_returns(signal, fees, levels=pd.DataFrame({
            "asset": level, "cash": 1.0,
        }, index=days))
        close = pd.Series(10.0, index=days)
        market.fill_close = {"asset": close}
        market.fill_board = {"asset": "none"}
        market.fill_prev = {"asset": prior_positive(close)}
        spec = SimpleNamespace(trade_eps=1e-12, weight_eps=1e-6, lookbacks=(20, 60, 120, 250))
        class_of = {"asset": "A股", "cash": "现金"}
        with patch("src.v5.engine.execute.path_decisions", side_effect=_decisions):
            off = run_arm(market, spec, class_of, enable_c2=False)
            on = run_arm(market, spec, class_of, enable_c2=True)
        self.assertEqual(set(off.paths), {"week", "month"})
        self.assertAlmostEqual(float(off.net.iloc[-1]), float((off.paths["week"].net.iloc[-1] + off.paths["month"].net.iloc[-1]) / 2))
        self.assertGreater(float(off.paths["week"].held["asset"].max()), 0.0)
        self.assertAlmostEqual(float(off.paths["week"].held["asset"].iloc[-1]), 1.0)
        self.assertAlmostEqual(float(on.paths["week"].held["asset"].iloc[-1]), 0.0)

    def test_arm_forwards_cross_border_dividend(self):
        days = pd.to_datetime([
            "2006-05-02", "2006-05-03", "2006-05-04", "2006-05-05",
            "2006-05-08", "2006-05-09", "2006-05-10",
        ])
        signal = pd.DataFrame({"asset": 0.0, "cash": 0.0}, index=days)
        signal.loc[days[5], "asset"] = 0.02
        fees = {"asset": 0.0, "cash": 0.0}
        market = market_from_returns(signal, fees)
        market.asset_classes = {"asset": "港股"}
        market.dividend_yield = pd.DataFrame({"asset": 0.0}, index=days)
        market.dividend_yield.loc[days[5], "asset"] = 0.02
        close = pd.Series(10.0, index=days)
        market.fill_close = {"asset": close}
        market.fill_board = {"asset": "none"}
        market.fill_prev = {"asset": prior_positive(close)}
        spec = SimpleNamespace(trade_eps=1e-12, weight_eps=1e-6, lookbacks=(20, 60, 120, 250))
        class_of = {"asset": "港股", "cash": "现金"}
        taxed = CrossBorderCosts(dividend_withholding=0.5)
        with patch("src.v5.engine.execute.path_decisions", side_effect=_decisions):
            plain = run_arm(market, spec, class_of, enable_c2=False)
            held = run_arm(
                market, spec, class_of, enable_c2=False,
                switches=EngineSwitches(
                    fill_limits=True, fx_v4=True, carriers=True, cross_border=taxed,
                ),
            )
        self.assertAlmostEqual(float(plain.paths["week"].net.loc[days[5]]), 0.02)
        self.assertAlmostEqual(float(held.paths["week"].net.loc[days[5]]), 0.01)
