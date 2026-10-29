"""v4-R5 设计期配置。不读行情库，不写正式 ledger，不算 2016 年以后的收益。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.v3.engine.book import RunnerError
from src.v3.engine.limits import previous_and_close
from src.v3.engine.spec import load_spec
from src.v4.r5.design import (
    DESIGN_END,
    Job,
    budget_jobs,
    complete_params,
    dividend_contribution,
    final_jobs,
    passed_from_table,
    peer_params,
    prior_positive,
    require_design_index,
    robustness_jobs,
    single_jobs,
    upsert_ledger,
)
from src.v4.scorecard.gate import GATE_COLUMNS


class Budget(unittest.TestCase):
    def test_design_jobs_stay_inside_the_ledger_cap(self):
        none = budget_jobs([])
        some = budget_jobs(["T1", "T4"])
        self.assertEqual(len(single_jobs()), 10)
        self.assertEqual(len(final_jobs([])), 2)
        self.assertEqual(len(robustness_jobs(final_jobs([])[0])), 25)
        self.assertEqual(len(none), 37)
        self.assertEqual(len(some), 37)
        self.assertLessEqual(len(none) + 4, 60)
        pools = {job.pool for job in none}
        self.assertEqual(pools, {"index", "tradable"})
        substitute = [job for job in none if job.case == "no-substitute"]
        self.assertEqual([job.pool for job in substitute], ["tradable"])
        self.assertTrue(all(job.params()["end"] == DESIGN_END for job in none))

    def test_final_turns_on_only_the_passed_switches(self):
        quiet = final_jobs([])[0]
        self.assertFalse(quiet.t1 or quiet.t2 or quiet.t3 or quiet.t4)
        both = final_jobs(["T2", "T4"])[0]
        self.assertTrue(both.t2 and both.t4)
        self.assertFalse(both.t1 or both.t3)
        switches = both.switches()
        self.assertTrue(switches.fill_limits and switches.fx_v4 and switches.carriers)
        self.assertTrue(switches.t2_state_weights and switches.t4_pool)
        self.assertFalse(switches.t1_turn or switches.t3_refill)

    def test_single_arms_match_the_prereg(self):
        found = {(job.case, job.pool): job for job in single_jobs()}
        self.assertFalse(found[("B0", "index")].t4)
        self.assertTrue(found[("T1", "tradable")].t1)
        self.assertTrue(found[("T2", "index")].t2)
        self.assertTrue(found[("T3", "index")].t3)
        self.assertTrue(found[("T4", "index")].t4)
        self.assertFalse(found[("T4", "index")].t1)

    def test_default_lookbacks_are_written_into_the_ledger_payload(self):
        spec = load_spec()
        payload = complete_params(single_jobs()[0], spec, [])
        self.assertEqual(payload["lookbacks"], list(spec.lookbacks))
        custom = Job(case="lookback-10-40-90-180", pool="index", kind="robustness",
                     lookbacks=(10, 40, 90, 180))
        self.assertEqual(complete_params(custom, spec)["lookbacks"], [10, 40, 90, 180])


class GateTable(unittest.TestCase):
    def test_only_true_passes_are_kept(self):
        rows = []
        for arm, flag in (("B0", ""), ("T1", True), ("T2", False), ("T3", "True"), ("T4", None)):
            row = {column: 0.0 for column in GATE_COLUMNS}
            row["arm"] = arm
            row["pool"] = "index"
            row["pass"] = flag
            rows.append(row)
        self.assertEqual(passed_from_table(pd.DataFrame(rows)), ["T1", "T3"])

    def test_dates_after_the_design_end_are_refused(self):
        with self.assertRaises(RunnerError):
            require_design_index(pd.to_datetime(["2015-12-31", "2016-01-04"]), what="试算")
        kept = require_design_index(pd.to_datetime(["2015-12-30", "2015-12-31"]), what="试算")
        self.assertEqual(str(kept.max().date()), DESIGN_END)


class PrevClose(unittest.TestCase):
    def test_precomputed_previous_print_matches_the_daily_scan(self):
        index = pd.to_datetime(["2010-01-04", "2010-01-05", "2010-01-06", "2010-01-07", "2010-01-08"])
        series = pd.Series([1.0, float("nan"), 2.0, -1.0, 3.0], index=index)
        prev = prior_positive(series)
        for stamp in index:
            slow = previous_and_close(series, stamp, None)
            fast = previous_and_close(series, stamp, prev)
            self.assertEqual(slow, fast)
        missing = pd.Timestamp("2010-01-09")
        self.assertEqual(previous_and_close(series, missing, None)[1], None)
        self.assertEqual(previous_and_close(series, missing, prev)[1], None)


class Dividend(unittest.TestCase):
    def test_ten_percent_of_the_dividend_gap_is_removed_and_splits_are_not(self):
        index = pd.to_datetime(["2010-01-04", "2010-01-05"])
        total = pd.Series([0.01, 0.02], index=index)
        price = pd.Series([-0.01, -0.50], index=index)
        out = dividend_contribution(total, price, 0.10)
        self.assertAlmostEqual(float(out.iloc[0]), 0.01 - 0.002)
        self.assertAlmostEqual(float(out.iloc[1]), 0.02)


class Ledger(unittest.TestCase):
    def test_rerun_replaces_the_same_row(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trial-ledger.csv"
            spec = load_spec()
            first = complete_params(single_jobs()[0], spec, [])
            second = dict(first)
            second["rerun"] = "实现错误，按原配置重跑"
            self.assertEqual(upsert_ledger(first, path=path), "appended")
            self.assertEqual(upsert_ledger(second, path=path), "replaced")
            text = path.read_text(encoding="utf-8")
            rows = [line for line in text.splitlines() if line and not line.startswith("run_at")]
            self.assertEqual(len(rows), 1)
            self.assertIn("实现错误", rows[0])
            peer = peer_params("A1", "index")
            self.assertEqual(upsert_ledger(peer, path=path), "appended")
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 3)
            self.assertEqual(peer["end"], DESIGN_END)


if __name__ == "__main__":
    unittest.main()
