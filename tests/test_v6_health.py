"""体检口径。不读 2016 年以后的行情。"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.v6.engine import continuity_state, slot
from src.v6.guard import IsolationError
from src.v6.health import _clip, _premium


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
        self.assertFalse(last["正收益过滤"])
        self.assertIn("csi300", last["持有"] + last["可参选名单"])
