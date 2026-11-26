"""预演脚本的开关。只用合成日收益，不读 2016 年以后的行情。"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.v6.engine import mix_monthly, slot
from src.v6.guard import IsolationError
from src.v6.oneshot_exam import (
    ACTIVE,
    OFFICIAL,
    REHEARSAL,
    extend_plan,
    official,
    refuse_market_after_design,
)


def _votes(levels, parent, names):
    periods = pd.PeriodIndex(sorted(set(levels.index.to_period("M"))), freq="M")
    return pd.Series(2, index=periods), len(names)


def _panel():
    index = pd.bdate_range("2014-01-02", "2015-06-30")
    rng = np.random.default_rng(1)
    frame = pd.DataFrame(index=index)
    level = 100.0
    for name, drift in (("csi300", 0.0002), ("a", 0.0008), ("b", 0.0001), ("c", -0.0002)):
        shock = drift + rng.normal(0.0, 0.01, len(index))
        level = 100.0 * np.cumprod(1.0 + shock)
        frame[name] = level
    bond = pd.Series(0.0001, index=index)
    cash = pd.Series(0.0, index=index)
    return frame, bond, cash


def _run(**kwargs):
    levels, bond, cash = _panel()
    args = dict(n=3, cost=0.002, signal_lag=0, stress_votes=2, exclude=None)
    args.update(kwargs)
    series, _turnover, _log = slot(
        levels, "csi300", args["n"], None, {}, "v6", args["cost"], _votes, bond, cash,
        signal_lag=args["signal_lag"], stress_votes=args["stress_votes"], exclude=args["exclude"],
    )
    return series


class OneshotExamTests(unittest.TestCase):
    def test_window_constant_is_the_rehearsal_and_official_refuses(self):
        self.assertIs(ACTIVE, REHEARSAL)
        self.assertEqual((REHEARSAL.exam_start, REHEARSAL.exam_end), ("2011-01-01", "2015-12-31"))
        self.assertEqual((REHEARSAL.full_start, REHEARSAL.full_end), ("2006-01-01", "2015-12-31"))
        self.assertEqual(OFFICIAL.exam_end, "2026-09-30")
        self.assertEqual(OFFICIAL.full_end, "2026-09-30")
        with self.assertRaises(IsolationError):
            official()
        with self.assertRaises(IsolationError):
            refuse_market_after_design("2026-09-30")

    def test_extend_plan_does_not_read_market_data(self):
        plan = extend_plan("2026-09-30")
        self.assertFalse(plan["读行情"])
        self.assertEqual(plan["end"], "2026-09-30")
        self.assertTrue(any("ACTIVE" in step for step in plan["步骤"]))

    def test_scenarios_change_the_simulated_series(self):
        base = _run()
        self.assertFalse(_run(cost=0.004).equals(base))
        self.assertFalse(_run(signal_lag=1).equals(base))
        self.assertFalse(_run(stress_votes=3).equals(base))
        self.assertFalse(_run(n=2).equals(base))
        self.assertFalse(_run(exclude=["a"]).equals(base))
        levels, _bond, _cash = _panel()
        left = mix_monthly(base, base * 0.5, 0.002, 0.4)
        right = mix_monthly(base, base * 0.5, 0.002, 0.5)
        self.assertFalse(left.equals(right))
        self.assertEqual(len(levels), len(base))


if __name__ == "__main__":
    unittest.main()
