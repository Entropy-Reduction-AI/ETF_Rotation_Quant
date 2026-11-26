"""预演脚本的开关。只用合成日收益，不读 2016 年以后的行情。"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.v6.engine import mix_monthly, slot
from src.v6.guard import IsolationError
from src.v6.health import COST
from src.v6.oneshot_exam import (
    ACTIVE,
    OFFICIAL,
    PREMIUM_TOLERANCE,
    REHEARSAL,
    S6_SAME_WEIGHTS,
    SIGNED_PREMIUM,
    control_spec,
    d51_accept,
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

    def test_d51_controls_follow_except_s8_and_s6_benchmark(self):
        doubled = {"n": 3, "cost": COST * 2, "lag": 0, "stress": 2, "exclude": None, "weight_a": 0.4}
        self.assertEqual(control_spec("S1", doubled)["cost"], COST * 2)
        delayed = {"n": 3, "cost": COST, "lag": 1, "stress": 2, "exclude": None, "weight_a": 0.4}
        self.assertEqual(control_spec("S2", delayed)["lag"], 1)
        self.assertEqual(control_spec("S6", {"n": 3, "cost": COST, "lag": 0, "stress": 2, "exclude": None, "weight_a": 0.5})["weight_a"], 0.5)
        self.assertEqual(control_spec("S7", {"n": 2, "cost": COST, "lag": 0, "stress": 2, "exclude": None, "weight_a": 0.4})["n"], 2)
        held = control_spec("S8", {"n": 3, "cost": COST, "lag": 0, "stress": 3, "exclude": None, "weight_a": 0.4})
        self.assertEqual(held["stress"], 2)
        self.assertEqual(held["cost"], COST)
        self.assertEqual(S6_SAME_WEIGHTS, {"H00300": 0.50, "XNDX": 0.25, "SP500TR": 0.25})

    def test_d51_acceptance_uses_the_signed_premium(self):
        ok = d51_accept({"明细": [{
            "类": "判据", "段": "检验段", "项": "防守平时保费",
            "签收": SIGNED_PREMIUM, "预演": SIGNED_PREMIUM, "差": 0.0, "实质差异": False,
        }]})
        self.assertTrue(ok["通过"])
        self.assertLessEqual(abs(ok["保费差"]), PREMIUM_TOLERANCE)
        bad = d51_accept({"明细": [{
            "类": "判据", "段": "检验段", "项": "防守平时保费",
            "签收": SIGNED_PREMIUM, "预演": 2.829, "差": 1.445, "实质差异": True,
        }]})
        self.assertFalse(bad["通过"])


if __name__ == "__main__":
    unittest.main()
