"""§6.1：P2 的上一版由 C1 是否过关决定，并写进 ledger 的 params。"""
from __future__ import annotations

import csv
import hashlib
import json
import unittest
from types import SimpleNamespace

import pandas as pd

from src.v3.engine.spec import LEDGER as V3_LEDGER
from src.v4.scorecard.gate import V4_LEDGER
from src.v5.campaign import c1_passed, record_version, version_flags, version_params
from src.v5.engine.allocate import EngineError


def _spec():
    return SimpleNamespace(trade_eps=1e-12, weight_eps=1e-6, lookbacks=(20, 60, 120, 250))


class PreviousVersion(unittest.TestCase):
    def test_p2_base_follows_the_c1_pass_flag(self):
        self.assertEqual(version_flags("S0", c1_passed=None)["base_arm"], "")
        self.assertEqual(version_flags("P1", c1_passed=None)["base_arm"], "S0")
        self.assertFalse(version_flags("P1", c1_passed=None)["enable_c2"])
        passed = version_flags("P2", c1_passed=True)
        self.assertEqual(passed["base_arm"], "P1")
        self.assertTrue(passed["enable_c1"] and passed["enable_c2"])
        failed = version_flags("P2", c1_passed=False)
        self.assertEqual(failed["base_arm"], "S0")
        self.assertFalse(failed["enable_c1"])
        self.assertTrue(failed["enable_c2"])
        with self.assertRaises(EngineError):
            version_flags("P2", c1_passed=None)

    def test_blank_pass_is_not_treated_as_a_failure(self):
        blank = pd.DataFrame([{"arm": "S0", "pass": None}, {"arm": "P1", "pass": None}])
        with self.assertRaises(EngineError):
            c1_passed(blank)
        self.assertTrue(c1_passed(pd.DataFrame([{"arm": "P1", "pass": True}])))
        self.assertFalse(c1_passed(pd.DataFrame([{"arm": "P1", "pass": "False"}])))
        with self.assertRaises(EngineError):
            c1_passed(pd.DataFrame([{"arm": "P1", "pass": True}, {"arm": "P1", "pass": False}]))

    def test_p2_params_record_the_chosen_base(self):
        params = version_params("P2", "index", c1_passed=True, spec=_spec())
        self.assertEqual(params["base_arm"], "P1")
        self.assertEqual(params["paths"], ["week", "month"])
        self.assertTrue(params["fill_limits"])
        self.assertFalse(params["t3_refill"])
        self.assertFalse(params["cross_border"])
        self.assertEqual(params["end"], "2015-12-31")
        self.assertEqual(params["exit_drawdown"], 0.10)
        self.assertEqual(params["trade_eps"], 1e-12)
        self.assertEqual(params["weight_eps"], 1e-6)
        quiet = version_params("S0", "tradable", c1_passed=None, spec=_spec())
        self.assertIsNone(quiet["exit_drawdown"])
        self.assertEqual(quiet["base_arm"], "")
        failed = version_params("P2", "tradable", c1_passed=False, spec=_spec())
        self.assertEqual(failed["base_arm"], "S0")
        self.assertFalse(failed["enable_c1"])

    def test_ledger_row_contains_the_base_and_refuses_other_ledgers(self):
        import tempfile
        from pathlib import Path

        params = version_params("P2", "index", c1_passed=False, spec=_spec())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trial-ledger.csv"
            record_version(params, path)
            with path.open(encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle))
            payload = json.loads(row["params"])
            self.assertEqual(row["arm"], "P2")
            self.assertEqual(row["segment"], "design")
            self.assertEqual(payload["base_arm"], "S0")
            self.assertTrue(payload["enable_c2"])
            self.assertFalse(payload["enable_c1"])
            record_version(version_params("P2", "index", c1_passed=True, spec=_spec()), path)
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(json.loads(rows[0]["params"])["base_arm"], "P1")
            with self.assertRaises(EngineError):
                record_version(params, Path(folder) / "LOCK")
        before = {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in (("v3", V3_LEDGER), ("v4", V4_LEDGER))
        }
        for path in (V3_LEDGER, V4_LEDGER):
            with self.assertRaises(EngineError):
                record_version(params, path)
        after = {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in (("v3", V3_LEDGER), ("v4", V4_LEDGER))
        }
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
