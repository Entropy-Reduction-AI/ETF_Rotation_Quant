"""v4-R3 打分卡。合成序列测公式；P1 与 Reviewer 独立函数对参考数。"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import pandas as pd

from src.v4.scorecard import (
    DESIGN_END,
    ScorecardError,
    acceptance,
    any_start,
    cash_weight_on,
    label_state,
    reference_scorecard,
    score_book,
)
from src.v4.scorecard.core import any_start_summary

ROOT = Path(__file__).resolve().parents[2]
DIAG = ROOT / "results/v3/diag/2026-10-27-owner-board"
DB = ROOT / "data/market.sqlite"

# anystart.py 在 P1 上的 1 位小数。基准列与 2026-10-27 诊断记录一致。
ANYSTART = {
    1: {
        "n": 108,
        "基准": (63, 4.6, -43.0, "2008-11-03"),
        "沪深300": (56, 3.8, -72.1, "2008-11-03"),
        "标普500": (49, -3.0, -27.4, "2010-07-01"),
        "纳指100": (44, -4.6, -34.3, "2010-02-01"),
    },
    2: {
        "n": 96,
        "基准": (62, 2.0, -18.6, "2008-11-03"),
        "沪深300": (81, 6.0, -25.0, "2008-11-03"),
        "标普500": (48, -0.8, -20.1, "2009-03-02"),
        "纳指100": (45, -7.9, -28.8, "2009-03-02"),
    },
    3: {
        "n": 84,
        "基准": (64, 1.4, -11.0, "2008-11-03"),
        "沪深300": (83, 7.5, -11.9, "2008-11-03"),
        "标普500": (51, 1.4, -17.6, "2010-07-01"),
        "纳指100": (43, -5.7, -23.9, "2009-04-01"),
    },
    5: {
        "n": 60,
        "基准": (63, 4.1, -6.6, "2008-11-03"),
        "沪深300": (93, 8.5, -3.7, "2008-11-03"),
        "标普500": (50, -0.4, -14.7, "2009-04-01"),
        "纳指100": (32, -4.8, -19.8, "2009-03-02"),
    },
}

# states.py 打出的 1 位小数。看板整数是对这些数再四舍五入。
STATES = {
    "牛市": (53, 54.7, -25.9, 26.5, 0.6, 1),
    "回调": (21, 71.4, 21.1, 8.8, 29.9, 30),
    "熊市": (27, 85.2, 45.4, 49.4, 94.9, 95),
    "反弹": (19, 15.8, -23.9, -32.8, -56.7, -57),
}


def _reviewer():
    path = DIAG / "reviewer_r3_scorecard.py"
    spec = importlib.util.spec_from_file_location("reviewer_r3_scorecard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Rules(unittest.TestCase):
    def test_flat_month_is_the_down_branch(self):
        slow = pd.Series([0.1, 0.1, -0.1, -0.1, 0.0, 0.0, float("nan")])
        fast = pd.Series([0.1, -0.01, -0.01, 0.1, 0.0, 0.1, 0.1])
        labels = label_state(slow, fast)
        self.assertEqual(list(labels.iloc[:6]), ["牛市", "回调", "熊市", "反弹", "熊市", "反弹"])
        self.assertTrue(pd.isna(labels.iloc[6]))

    def test_cash_weight_uses_the_previous_row(self):
        days = pd.to_datetime(["2006-01-04", "2006-01-05", "2006-01-06"])
        held = pd.Series([0.2, 0.4, 0.9], index=days)
        window = days[1:]
        weight = cash_weight_on(held, window)
        self.assertEqual(list(weight), [0.2, 0.4])

    def test_any_start_stops_when_the_hold_runs_past_the_end(self):
        index = pd.to_datetime(["2006-01-03", "2006-02-01", "2007-01-03", "2007-02-01", "2007-03-01"])
        navs = {
            "E2": pd.Series([1.0, 1.0, 2.0, 2.0, 2.0], index=index),
            "基准": pd.Series([1.0, 1.0, 1.5, 1.5, 1.5], index=index),
        }
        tables = any_start(navs, horizons=(1,))
        self.assertEqual(list(tables[1].index), list(index[:2]))
        self.assertAlmostEqual(tables[1].loc[index[0], "E2"], 1.0)
        self.assertAlmostEqual(tables[1].loc[index[0], "基准"], 0.5)
        summary = any_start_summary(tables)
        self.assertEqual(int(summary.iloc[0]["win_pct"]), 100)
        self.assertEqual(summary.iloc[0]["worst_start"], "2006-01-03")

    def test_short_sample_completes_no_hold(self):
        index = pd.bdate_range("2015-12-01", periods=5)
        navs = {"E2": pd.Series(1.0, index=index), "基准": pd.Series(1.0, index=index)}
        summary = any_start_summary(any_start(navs, horizons=(1,)))
        self.assertEqual(int(summary.iloc[0]["n"]), 0)
        self.assertIsNone(summary.iloc[0]["win_pct"])

    def test_refuses_an_end_date_after_2015(self):
        with self.assertRaises(ScorecardError):
            score_book(Path("missing-paths.csv"), Path("missing-held.csv"), DB, end="2016-01-04")

    def test_refuses_2016_returns_before_opening_the_database(self):
        days = pd.to_datetime(["2015-12-31", "2016-01-04"])
        frame = pd.DataFrame({"executed": [0.0, 0.0], "cash": [1.0, 1.0]}, index=days)
        folder = ROOT / "outputs" / "v4-scorecard-reject"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "paths.csv"
        frame.to_csv(path)
        with self.assertRaises(ScorecardError):
            score_book(path, path, Path("/tmp/does-not-exist.sqlite"), end=str(DESIGN_END.date()))


class P1Reference(unittest.TestCase):
    def setUp(self):
        if not DB.exists() or DB.stat().st_size < 1000:
            self.skipTest("market.sqlite 不在这台机器上")

    def test_p1_matches_published_reference_and_reviewer_functions(self):
        report = reference_scorecard(ROOT, DB)
        self.assertEqual(report["start"], "2006-01-05")
        self.assertEqual(report["end"], "2015-12-31")
        self.assertEqual(report["n_days"], 2428)
        self.assertTrue(report["acceptance"]["ok"])
        summary = report["summary"]
        for years, expected in ANYSTART.items():
            block = summary[summary["years"] == years]
            for name, row in block.iterrows():
                del name
                comparator = row["comparator"]
                if comparator not in expected:
                    continue
                win, median, worst, worst_start = expected[comparator]
                self.assertEqual(int(row["n"]), expected["n"])
                self.assertEqual(int(row["win_pct"]), win)
                self.assertEqual(float(row["median_excess_pp"]), median)
                self.assertEqual(float(row["worst_excess_pp"]), worst)
                self.assertEqual(row["worst_start"], worst_start)
        states = report["states"]
        for name, (months, win, cash, selection, excess, board) in STATES.items():
            row = states.loc[name]
            self.assertEqual(int(row["months"]), months)
            self.assertEqual(float(row["win_month_pct"]), win)
            self.assertEqual(float(row["cash_pp"]), cash)
            self.assertEqual(float(row["selection_pp"]), selection)
            self.assertEqual(float(row["excess_pp"]), excess)
            self.assertEqual(int(row["excess_pp_board"]), board)
        self.assertEqual(report["capture"]["up_capture"], 0.86)
        self.assertEqual(report["capture"]["down_capture"], 0.52)
        self.assertEqual(report["capture"]["up_months"], 74)
        self.assertEqual(report["capture"]["down_months"], 46)

        reviewer = _reviewer()
        prices, benchmark = reviewer.build_lab2_pickle()
        try:
            executed, held = reviewer.load_p1()
            returns = prices.pct_change(fill_method=None)
            theirs = reviewer.anystart_independent(executed, benchmark, prices, returns)
            for years, row in theirs.items():
                block = summary[summary["years"] == years]
                for comparator, rate in row.items():
                    got = float(block.loc[block["comparator"] == comparator, "win_rate"].iloc[0])
                    self.assertAlmostEqual(got, rate, places=9)
            state = reviewer.states_independent(executed, held, benchmark)
            for name, excess in state["excess_pp"].items():
                self.assertEqual(float(states.loc[name, "excess_pp"]), excess)
            self.assertEqual(report["capture"]["up_capture"], state["up_capture"])
            self.assertEqual(report["capture"]["down_capture"], state["down_capture"])
        finally:
            for name in ("data.pkl", "aux.pkl", "anystart.pkl"):
                path = DIAG / name
                if path.exists() or path.is_symlink():
                    path.unlink()
        self.assertTrue(acceptance(report)["ok"])
