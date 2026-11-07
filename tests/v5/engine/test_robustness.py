"""§6.1 从过关表读 F；§7.1 每个对照只改一项。"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

import pandas as pd

from src.v4.r5.design import LOOKBACKS
from src.v5.campaign import version_flags
from src.v5.engine.allocate import EngineError
from src.v5.robustness import (
    NEIGHBOR_LOOKBACKS,
    final_arm,
    robustness_jobs,
    robustness_params,
)


def _spec():
    return SimpleNamespace(trade_eps=1e-12, weight_eps=1e-6, lookbacks=(20, 60, 120, 250))


def _table(p1, p2, base):
    return pd.DataFrame([
        {"arm": "S0", "base_arm": "", "pass": None},
        {"arm": "P1", "base_arm": "S0", "pass": p1},
        {"arm": "P2", "base_arm": base, "pass": p2},
    ])


class FinalArm(unittest.TestCase):
    def test_c2_kept_on_s0_when_c1_fails(self):
        self.assertEqual(final_arm(_table(False, True, "S0")), "P2")
        flags = version_flags("P2", c1_passed=False)
        self.assertFalse(flags["enable_c1"])
        self.assertTrue(flags["enable_c2"])
        self.assertEqual(flags["base_arm"], "S0")

    def test_both_fail_keeps_s0(self):
        self.assertEqual(final_arm(_table(False, False, "S0")), "S0")

    def test_c1_kept_when_c2_fails(self):
        self.assertEqual(final_arm(_table(True, False, "P1")), "P1")

    def test_both_pass_keeps_p2_with_c1(self):
        self.assertEqual(final_arm(_table(True, True, "P1")), "P2")
        flags = version_flags("P2", c1_passed=True)
        self.assertTrue(flags["enable_c1"] and flags["enable_c2"])

    def test_blank_or_inconsistent_base_does_not_pick(self):
        with self.assertRaises(EngineError):
            final_arm(_table(None, False, "S0"))
        with self.assertRaises(EngineError):
            final_arm(_table(False, None, "S0"))
        with self.assertRaises(EngineError):
            final_arm(_table(False, True, "P1"))
        with self.assertRaises(EngineError):
            final_arm(_table(True, True, "S0"))
        filled = _table(False, True, "S0")
        filled.loc[0, "pass"] = False
        with self.assertRaises(EngineError):
            final_arm(filled)

    def test_csv_blank_pass_still_selects(self):
        import tempfile
        from pathlib import Path

        frame = _table(False, True, "S0")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "component-gate.csv"
            frame.to_csv(path, index=False)
            loaded = pd.read_csv(path)
        self.assertEqual(final_arm(loaded), "P2")


class RobustnessList(unittest.TestCase):
    def test_neighbor_sets_match_v4(self):
        self.assertEqual(NEIGHBOR_LOOKBACKS, LOOKBACKS)

    def test_p2_without_c1_has_exit_contrasts_and_one_change(self):
        flags = version_flags("P2", c1_passed=False)
        jobs = robustness_jobs(flags, final="P2")
        self.assertEqual(len(jobs), 27)
        self.assertEqual(sum(job.pool == "index" for job in jobs), 13)
        self.assertEqual(sum(job.pool == "tradable" for job in jobs), 14)
        index_cases = [job.case for job in jobs if job.pool == "index"]
        self.assertEqual(index_cases, [
            "lookback-10-40-90-180",
            "lookback-15-50-100-200",
            "lookback-30-80-150-300",
            "cost-double",
            "delay-1d",
            "drop-best-1",
            "drop-best-2",
            "drop-best-3",
            "strongest-class",
            "fixed-budget",
            "no-defense",
            "exit-8",
            "exit-12",
        ])
        self.assertEqual(jobs[-1].case, "no-substitute")
        self.assertEqual(jobs[-1].pool, "tradable")
        self.assertFalse(any(job.case == "no-substitute" and job.pool == "index" for job in jobs))
        self.assertFalse(any(job.case == "exit-15" for job in jobs))
        self.assertTrue(all(job.final_arm == "P2" and job.enable_c2 and not job.enable_c1 for job in jobs))
        self.assertLessEqual(6 + len(jobs), 45)

    def test_s0_omits_exit_contrasts(self):
        flags = version_flags("S0", c1_passed=None)
        jobs = robustness_jobs(flags, final="S0")
        self.assertEqual(len(jobs), 23)
        self.assertFalse(any(job.case.startswith("exit-") for job in jobs))
        self.assertTrue(all(not job.enable_c2 and job.exit_drawdown is None for job in jobs))

    def test_params_record_final_arm_and_refuse_a_short_drop_list(self):
        flags = version_flags("P2", c1_passed=False)
        job = next(item for item in robustness_jobs(flags, final="P2") if item.case == "exit-8" and item.pool == "index")
        params = robustness_params(job, _spec(), [])
        self.assertEqual(params["final_arm"], "P2")
        self.assertEqual(params["base_arm"], "S0")
        self.assertEqual(params["kind"], "robustness")
        self.assertEqual(params["end"], "2015-12-31")
        self.assertEqual(params["exit_drawdown"], 0.08)
        self.assertFalse(params["enable_c1"])
        self.assertTrue(params["enable_c2"])
        self.assertEqual(params["paths"], ["week", "month"])
        self.assertFalse(params["cross_border"])
        drop = next(item for item in robustness_jobs(flags, final="P2") if item.case == "drop-best-2" and item.pool == "tradable")
        with self.assertRaises(EngineError):
            robustness_params(drop, _spec(), ["only-one"])
        quiet = robustness_jobs(version_flags("S0", c1_passed=None), final="S0")[0]
        built = RobustShadow(quiet)
        with self.assertRaises(EngineError):
            robustness_params(built, _spec(), [])


class RobustShadow:
    """测参数函数：C2 关着却带了离场阈值。"""

    def __init__(self, job):
        self.__dict__.update(job.__dict__)
        self.exit_drawdown = 0.08
        self.enable_c2 = False


if __name__ == "__main__":
    unittest.main()
