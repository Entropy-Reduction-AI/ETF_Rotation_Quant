"""§6.2 / §6.3 ⑤。只用手造序列，不读候选收益。"""
from __future__ import annotations

import csv
import unittest
from pathlib import Path

import pandas as pd

from src.v3.eval.sharpe import trial_count
from src.v3.engine.spec import LEDGER
from src.v4.scorecard.gate import GATE_COLUMNS, TARGET_STATE, attempt_count, candidate_gate


def _states() -> pd.Series:
    return pd.Series(
        ["反弹", "熊市", "牛市", "回调"],
        index=pd.to_datetime(["2006-01-31", "2011-01-31", "2006-02-28", "2011-02-28"]),
    )


def _frame() -> tuple[pd.DataFrame, pd.Series]:
    # 每个状态两天。B0 全 0。T1 在反弹里有正超额，两段年化都更高，熊市只差 10 个点整。
    index = pd.to_datetime([
        "2006-01-04", "2006-01-05", "2006-02-06", "2006-02-07",
        "2011-01-04", "2011-01-05", "2011-02-08", "2011-02-09",
    ])
    benchmark = pd.Series(0.0, index=index)
    b0 = pd.Series(0.0, index=index)
    t1 = pd.Series(0.0, index=index)
    t1.loc["2006-01-04"] = 0.001
    t1.loc["2006-02-06"] = 0.01
    t1.loc["2011-01-04"] = -0.05
    t1.loc["2011-01-05"] = -0.05
    t1.loc["2011-02-08"] = 0.10
    t1.loc["2011-02-09"] = 0.10
    short = t1.copy()
    short.loc["2011-01-05"] = -0.0500001
    returns = pd.DataFrame({"B0": b0, "T1": t1, "T2": short})
    return returns, benchmark


class GateMath(unittest.TestCase):
    def test_hand_series_matches_the_formula_and_does_not_round(self):
        returns, benchmark = _frame()
        table = candidate_gate(returns, benchmark, _states(), pool="index")
        self.assertEqual(list(table.columns), list(GATE_COLUMNS))
        self.assertEqual(table["arm"].tolist(), ["B0", "T1", "T2"])
        b0 = table.set_index("arm").loc["B0"]
        t1 = table.set_index("arm").loc["T1"]
        t2 = table.set_index("arm").loc["T2"]
        self.assertIsNone(b0["pass"])
        self.assertIsNone(b0["pass_segments"])
        self.assertIsNone(b0["pass_bear"])
        self.assertTrue(bool(t1["pass_segments"]))
        self.assertTrue(bool(t1["pass_target"]))
        self.assertAlmostEqual(float(t1["pp_rebound"]), 0.1)
        self.assertAlmostEqual(float(t1["pp_bear"]), -10.0)
        self.assertTrue(bool(t1["pass_bear"]))
        self.assertTrue(bool(t1["pass"]))
        self.assertFalse(bool(t2["pass_bear"]))
        self.assertFalse(bool(t2["pass"]))
        self.assertEqual(TARGET_STATE["T1"], "反弹")
        self.assertEqual(t1["pool"], "index")
        # 0.01 的两天不能被收成 0。
        self.assertNotEqual(round(float(t1["pp_rebound"]), 0), float(t1["pp_rebound"]))

    def test_attempt_count_matches_addendum_a3_on_the_v3_ledger(self):
        self.assertEqual(attempt_count(LEDGER, Path("/tmp/v4-ledger-missing-r2c.csv")), trial_count(LEDGER))
        self.assertEqual(attempt_count(LEDGER, Path("/tmp/v4-ledger-missing-r2c.csv")), 73)
        root = Path("/tmp/v4-r2c-ledgers")
        root.mkdir(parents=True, exist_ok=True)
        v3 = root / "v3.csv"
        v4 = root / "v4.csv"
        header = ["run_at", "git_sha", "arm", "params", "segment", "runner"]

        def write(path, rows):
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=header)
                writer.writeheader()
                writer.writerows(rows)

        common = {"run_at": "2026-10-28T00:00:00+08:00", "git_sha": "abc", "runner": "dev"}
        write(v3, [
            {**common, "arm": "A", "params": "{}", "segment": "design"},
            {**common, "arm": "A", "params": "{}", "segment": "design"},
            {**common, "arm": "C1-shadow", "params": "{}", "segment": "design"},
            {**common, "arm": "B", "params": "{\"x\":1}", "segment": "design"},
        ])
        write(v4, [
            {**common, "arm": "T1", "params": "{}", "segment": "design"},
            {**common, "arm": "C1-shadow", "params": "{}", "segment": "design"},
        ])
        # 去重后 v3 三行（含 1 条影子）、v4 两行（含 1 条影子）。C = 2。63 + 5 - 2 = 66。
        self.assertEqual(attempt_count(v3, v4), 66)


if __name__ == "__main__":
    unittest.main()
