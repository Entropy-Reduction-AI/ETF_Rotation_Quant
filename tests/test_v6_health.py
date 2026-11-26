"""体检口径。不读 2016 年以后的行情。"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.v6.engine import continuity_pick, continuity_state, slot
from src.v6.k2a import month_end_positions
from src.v6.guard import IsolationError
from src.v6.health import _clip, _premium, contribution


class WindowTests(unittest.TestCase):
    def test_clip_rejects_2016(self):
        series = pd.Series([0.01, 0.01], index=pd.to_datetime(["2015-12-31", "2016-01-04"]))
        with self.assertRaises(IsolationError):
            _clip(series, "2006-01-01", "2015-12-31")

    def test_premium_uses_only_positive_full_years(self):
        days = pd.bdate_range("2006-01-02", "2007-12-31")
        v6 = pd.Series(0.0, index=days)
        plain = pd.Series(0.0, index=days)
        plain.loc[plain.index.year == 2006] = 0.001
        bm = pd.Series(0.001, index=days)
        bm.loc[bm.index.year == 2007] = -0.002
        got = _premium(v6, plain, bm, "2006-01-01", "2007-12-31")
        self.assertEqual(got["years"], [2006])
        self.assertGreater(got["premium_pp"], 0)


class ContinuityTests(unittest.TestCase):
    def test_id_sign_and_two_hundred_day_gate(self):
        months = pd.bdate_range("2013-01-31", periods=14, freq="BME")
        days = pd.bdate_range(months[0], months[-1])
        level = pd.DataFrame(100.0, index=days, columns=["a", "b"])
        level["a"] = 100 + np.arange(len(days))
        level["b"] = 100 + np.arange(len(days))
        scores = np.array([0.2, -0.1])
        ident, eligible = continuity_state(level, months[-1], months, scores, min_days=5)
        self.assertTrue(bool(eligible.all()))
        self.assertLess(float(ident[0]), 0)
        self.assertGreater(float(ident[1]), 0)
        _short, short_ok = continuity_state(level, months[-1], months, scores, min_days=10_000)
        self.assertFalse(bool(short_ok.any()))

    def test_slot_keeps_its_own_leaders(self):
        months = pd.bdate_range("2013-01-31", periods=16, freq="BME")
        days = pd.bdate_range(months[0], months[-1])
        level = pd.DataFrame({
            "csi300": np.linspace(100, 130, len(days)),
            "slow": np.linspace(100, 160, len(days)),
            "choppy": 100 + np.sin(np.arange(len(days)) / 3),
        }, index=days)
        bond = pd.Series(0.0001, index=days)
        cash = pd.Series(0.00005, index=days)

        def votes(levels, parent, which):
            return pd.Series(2, index=pd.PeriodIndex(months, freq="M")), 3

        _series, _turn, log = slot(
            level, "csi300", 3, None, {"slow": "x", "choppy": "y"}, "id", 0.0,
            votes, bond, cash)
        last = log[months[-1]]
        self.assertIsNotNone(last["p"])
        self.assertTrue(last["过滤规则"])
        self.assertIn("csi300", last["持有"] + last["可参选名单"])
        _open, _turn_open, open_log = slot(
            level, "csi300", 3, None, {"slow": "x", "choppy": "y"}, "id_open", 0.0,
            votes, bond, cash)
        self.assertFalse(open_log[months[-1]]["过滤规则"])
        self.assertNotEqual(last["p"], None)

    def test_filter_removes_a_negative_name_before_the_half(self):
        scores = np.array([0.05, -0.01, -0.02, -0.50])
        ident = np.array([0.5, -0.9, 0.2, 0.1])
        eligible = np.ones(4, dtype=bool)
        tags = np.array(["a", "b", "c", "d"], dtype=object)
        opened = continuity_pick(scores, ident, eligible, tags, 3)
        held = continuity_pick(scores, ident, eligible & (scores > 0), tags, 3)
        self.assertEqual(opened[0], 1)
        self.assertEqual(held, [0])


class K2ATests(unittest.TestCase):
    def test_calendar_month_is_not_every_21_bars(self):
        index = pd.bdate_range("2014-01-02", "2014-03-31")
        calendar = month_end_positions(index, True)
        bars = month_end_positions(index, False)
        self.assertEqual(pd.Timestamp(index[calendar[-1]]).month, 3)
        self.assertNotEqual(list(calendar), list(bars))


class CapTests(unittest.TestCase):
    def test_panel_chain_sql_is_date_capped(self):
        from pathlib import Path
        runner = Path("src/data/runner.py").read_text(encoding="utf-8")
        quality = Path("src/data/quality.py").read_text(encoding="utf-8")
        self.assertIn("AND date <= ?", runner)
        self.assertIn("date<=?", quality)


class ContributionTests(unittest.TestCase):
    def test_sleeve_weight_does_not_touch_portfolio_items(self):
        value, weight = contribution("美股挑选", 4.86)
        self.assertAlmostEqual(value, 4.86 * 0.6)
        self.assertEqual(weight, 0.6)
        same, plain_weight = contribution("防守保费", -1.61)
        self.assertEqual(same, -1.61)
        self.assertIsNone(plain_weight)
        tilt, tilt_weight = contribution("A股等权倾斜", 5.69)
        self.assertAlmostEqual(tilt, 5.69 * 0.4)
        self.assertEqual(tilt_weight, 0.4)
