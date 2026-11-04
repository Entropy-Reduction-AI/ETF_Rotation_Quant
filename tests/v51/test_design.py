"""设计期接线。不连行情库，不跑 2006–2015。"""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from src.v3.engine.book import RunnerError
from src.v3.engine.ledger import COLUMNS
from src.v51.design import (
    design_params,
    eligible_frame,
    gate_draft,
    metric_block,
    record_design,
    t_of,
    windowed,
)
from src.v51.params import V51Error


def _spec():
    return SimpleNamespace(lookbacks=(20, 60, 120, 250), trade_eps=1e-12, weight_eps=1e-6)


def _metrics():
    index = pd.bdate_range("2006-01-02", "2015-12-31")
    strategy = pd.Series(0.0004, index=index)
    benchmark = pd.Series(0.0001, index=index)
    strategy.iloc[30] = -0.08
    benchmark.iloc[30] = -0.03
    rows = []
    for pool in ("index", "tradable"):
        for segment, start, end in (
            ("full", "2006-01-01", "2015-12-31"),
            ("s1", "2006-01-01", "2010-12-31"),
            ("s2", "2011-01-01", "2015-12-31"),
        ):
            rows.append(metric_block(pool, segment, start, end, strategy, benchmark))
    return rows


class DesignWiring(unittest.TestCase):
    def test_window_rejects_2016(self):
        series = pd.Series([0.01, 0.01], index=pd.to_datetime(["2015-12-31", "2016-01-04"]))
        with self.assertRaises(V51Error):
            windowed(series, "2006-01-01", "2015-12-31")

    def test_t_of_matches_the_written_ratio(self):
        excess = pd.Series([0.01, 0.03])
        self.assertAlmostEqual(t_of(excess), 2.0)

    def test_index_pool_does_not_take_the_carrier_mask(self):
        index = pd.bdate_range("2015-01-05", periods=3)
        liquid = pd.DataFrame({"csi300": [True, False, True]}, index=index)
        self.assertIsNone(eligible_frame("index", liquid, index))
        masked = eligible_frame("tradable", liquid, index)
        self.assertFalse(bool(masked.at[index[1], "csi300"]))
        self.assertTrue(bool(masked.at[index[0], "csi300"]))

    def test_params_stay_on_the_frozen_rule(self):
        payload = design_params("index", _spec())
        self.assertEqual(payload["rules"], "v5.1")
        self.assertEqual(payload["pool"], "index")
        self.assertEqual(payload["end"], "2015-12-31")
        self.assertEqual(payload["engine_arm"], "A")
        self.assertEqual(payload["paths"], ["week"])
        self.assertEqual(payload["frontier"], 0.5)
        self.assertEqual(payload["cost_multiplier"], 1.0)
        self.assertEqual(payload["decision_delay"], 0)
        self.assertFalse(payload["cross_border"])
        with self.assertRaises(V51Error):
            design_params("G", _spec())

    def test_ledger_replaces_the_same_pool_and_refuses_lock(self):
        payload = design_params("tradable", _spec())
        other = design_params("index", _spec())
        with self.assertRaises(V51Error):
            record_design(payload, Path("/tmp/v51-not-used/LOCK"))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trial-ledger.csv"
            record_design(payload, path)
            record_design(other, path)
            record_design(payload, path)
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(list(rows[0]), COLUMNS)
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["arm"] for row in rows}, {"v5.1"})
        self.assertEqual({row["segment"] for row in rows}, {"design"})
        self.assertEqual({json.loads(row["params"])["pool"] for row in rows}, {"index", "tradable"})

    def test_draft_marks_controls_pending_and_scores_the_benchmark(self):
        states = {"牛市": 1.5, "回调": -0.2, "熊市": -0.4, "反弹": 0.1, "rebound_t": -0.5, "rebound_n": 12}
        a1 = {"index": {"monthly_excess_t": -1.0}, "tradable": {"monthly_excess_t": -3.0}}
        draft = gate_draft(_metrics(), states, a1)
        pending = draft[draft["status"] == "待 R5"]["item"].tolist()
        self.assertIn("0", pending)
        self.assertIn("3", pending)
        self.assertNotIn("1", pending)
        self.assertTrue((draft[draft["item"] == "5"]["status"] == "待 R6").all())
        beat = draft[(draft["item"] == "1") & (draft["metric"] == "cagr")]
        self.assertTrue((beat["status"] == "通过").all())
        peers = draft[draft["item"] == "2"].set_index("pool")
        self.assertEqual(peers.loc["index", "status"], "通过")
        self.assertEqual(peers.loc["tradable", "status"], "未通过")
        self.assertEqual(draft[draft["metric"] == "p_bull"]["status"].iloc[0], "通过")
        self.assertIn("未完成", set(draft[draft["item"] == "入围"]["status"]))
        reported = draft[(draft["item"] == "报告") & (draft["metric"] == "calmar")]
        self.assertEqual(len(reported), 6)

    def test_metric_block_rejects_a_later_benchmark(self):
        index = pd.bdate_range("2015-12-01", periods=5)
        strategy = pd.Series(0.01, index=index)
        benchmark = pd.Series(0.01, index=pd.bdate_range("2016-01-04", periods=5))
        with self.assertRaises((V51Error, RunnerError)):
            metric_block("index", "full", "2006-01-01", "2015-12-31", strategy, benchmark)
