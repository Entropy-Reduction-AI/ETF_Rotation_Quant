"""补导出的纯函数。不读 2016 年以后的行情，不写 results/。"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.v6.engine import slot
from src.v6.guard import IsolationError
from src.v6.oneshot_prep import any_start

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "v6_report" / "oneshot_supplement_export.py"
SPEC = importlib.util.spec_from_file_location("oneshot_supplement_export", PATH)
export = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(export)


def _votes(levels, parent, names):
    periods = pd.PeriodIndex(sorted(set(levels.index.to_period("M"))), freq="M")
    return pd.Series(0, index=periods), len(names)


def _panel():
    index = pd.bdate_range("2014-01-02", "2015-06-30")
    rng = np.random.default_rng(3)
    frame = pd.DataFrame(index=index)
    for name, drift in (("csi300", 0.0002), ("a", 0.0005), ("b", 0.0001), ("c", -0.0002)):
        level = 100.0 * np.cumprod(1.0 + drift + rng.normal(0.0, 0.01, len(index)))
        frame[name] = level
    bond = pd.Series(0.0001, index=index)
    cash = pd.Series(0.0, index=index)
    return frame, bond, cash


class SupplementExportTests(unittest.TestCase):
    def test_traced_slot_and_replay_match_the_engine(self):
        levels, bond, cash = _panel()
        run = export.traced_slot()
        traced, _turn, _log, trace, columns = run(
            levels, "csi300", 3, None, {}, "v6", 0.002, _votes, bond, cash,
            signal_lag=0, stress_votes=2, exclude=None,
        )
        official, _turn, _log = slot(
            levels, "csi300", 3, None, {}, "v6", 0.002, _votes, bond, cash,
            signal_lag=0, stress_votes=2, exclude=None,
        )
        self.assertEqual(columns, list(levels.columns))
        self.assertEqual(float((traced - official).abs().max()), 0.0)
        replayed = export.replay(levels, bond, cash, trace, 0.002)
        self.assertLess(float((replayed - official).abs().max()), 1e-12)

    def test_same_targets_change_when_prices_are_scaled(self):
        levels, bond, cash = _panel()
        run = export.traced_slot()
        _series, _turn, _log, trace, _columns = run(
            levels, "csi300", 3, None, {}, "v6", 0.002, _votes, bond, cash,
            signal_lag=0, stress_votes=2, exclude=None,
        )
        fx = pd.Series(np.linspace(6.0, 7.0, len(levels)), index=levels.index)
        scaled = levels.mul(fx, axis=0)
        priced = export.replay(scaled, bond, cash, trace, 0.002)
        plain = export.replay(levels, bond, cash, trace, 0.002)
        self.assertGreater(float((priced - plain).abs().max()), 1e-6)

    def test_buy_filter_matches_any_start_when_it_covers_every_start(self):
        index = pd.bdate_range("2014-01-02", "2015-12-31")
        frame = pd.DataFrame({
            "v6": 0.0004,
            "BM-主": 0.0002,
            "BM-同仓位": 0.0003,
            "K2A": 0.0001,
        }, index=index)
        official = any_start({name: frame[name] for name in frame.columns}, "v6", 1)
        starts = export._filtered_starts(frame, 1, "2014-01-01", "2015-12-31", False)
        stats = export._start_stats(frame, "v6", 1, starts)
        self.assertEqual(len(starts), official["起点数"])
        self.assertAlmostEqual(stats["BM-主"]["跑赢占比"], official["跑赢占比"]["BM-主"])
        self.assertAlmostEqual(stats["BM-主"]["中位"], official["中位"]["BM-主"])
        self.assertAlmostEqual(stats["BM-主"]["最差"], official["最差"]["BM-主"])
        later = export._filtered_starts(frame, 1, "2015-01-01", "2015-12-31", False)
        self.assertLess(len(later), len(starts))
        self.assertTrue(all(pd.Timestamp(day) >= pd.Timestamp("2015-01-01") for day in later))

    def test_cross_segment_requires_both_sides_of_2016(self):
        index = pd.bdate_range("2015-01-02", "2017-06-30")
        frame = pd.DataFrame({"v6": 0.0, "BM-主": 0.0}, index=index)
        crossed = export._filtered_starts(frame, 1, "2011-01-01", "2021-12-31", True)
        self.assertTrue(crossed)
        self.assertTrue(all(pd.Timestamp(day) < pd.Timestamp("2016-01-01") for day in crossed))
        inside = export._filtered_starts(frame.loc["2016-01-01":], 1, "2011-01-01", "2021-12-31", True)
        self.assertEqual(inside, [])

    def test_output_guard_rejects_judgment_files(self):
        with self.assertRaises(IsolationError):
            export.assert_safe_output(export.OFFICIAL / "verdict.json")
        with self.assertRaises(IsolationError):
            export.assert_safe_output(export.OUT / "verdict.json")
        export.assert_safe_output(export.OUT / "fx-layer.csv")


if __name__ == "__main__":
    unittest.main()
