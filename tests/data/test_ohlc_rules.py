"""I-28 的 k 换算，以及 I-29 的四种缺口。只用构造数据。"""
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.data.ohlc_rules import apply_i28, decide_i29
from src.indicators import build as B
from tests.marketdb import open_db, put


CAL = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05",
       "2024-01-08", "2024-01-09", "2024-01-10", "2024-01-11", "2024-01-12"]


def _price(day, close):
    return {"date": day, "open": close - 1, "high": close + 2, "low": close - 2, "close": close}


class Scale(unittest.TestCase):
    def test_k_scales_missing_ohlc_and_keeps_research_close(self):
        rows = [{"date": "2024-01-02", "open": None, "high": None, "low": None, "close": 220.0, "volume": 5}]
        prices = {"2024-01-02": _price("2024-01-02", 10.0)}
        out, source = apply_i28(rows, prices)
        self.assertEqual(source, "price_version")
        self.assertEqual((out[0]["open"], out[0]["high"], out[0]["low"], out[0]["close"]), (198.0, 264.0, 176.0, 220.0))
        self.assertEqual(out[0]["volume"], 5)

    def test_existing_ohlc_stays_self_even_when_research_is_the_price_index(self):
        row = _price("2024-01-02", 10.0)
        out, source = apply_i28([row], {"2024-01-02": {"date": "2024-01-02", "open": 1, "high": 1, "low": 1, "close": 1}})
        self.assertEqual(source, "self")
        self.assertEqual(out[0]["open"], 9.0)

    def test_price_without_ohlc_leaves_the_day_missing(self):
        rows = [{"date": "2024-01-02", "open": None, "high": None, "low": None, "close": 10.0}]
        out, source = apply_i28(rows, {})
        self.assertEqual(source, "self")
        self.assertIsNone(out[0]["open"])


class Gaps(unittest.TestCase):
    def test_jan1_does_not_count_and_window_starts_at_first_real_bar(self):
        real = ["2024-01-01", "2024-01-03", "2024-01-04", "2024-01-05",
                "2024-01-08", "2024-01-09", "2024-01-10", "2024-01-11", "2024-01-12"]
        got = decide_i29(real, CAL, "2024-01-12")
        self.assertTrue(got["enters_v1"])
        self.assertEqual(got["window_start"], "2024-01-03")
        self.assertEqual(got["reason"], "I-29(1)")
        self.assertEqual(got["placeholder_runs"], [])

    def test_short_gap_is_a_placeholder_and_still_enters(self):
        real = [day for day in CAL if day not in ("2024-01-01", "2024-01-04", "2024-01-05")]
        got = decide_i29(real, CAL, "2024-01-12")
        self.assertTrue(got["enters_v1"])
        self.assertEqual(got["window_start"], "2024-01-02")
        self.assertEqual(got["reason"], "I-29(1)")
        self.assertEqual(got["placeholder_runs"], [
            {"first": "2024-01-04", "last": "2024-01-05", "rows": 2, "trailing": False, "hole_rows": 2}])

    def test_long_gap_pushes_window_past_the_last_such_gap(self):
        missing = {"2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"}
        real = [day for day in CAL if day not in missing and day != "2024-01-01"]
        got = decide_i29(real, CAL, "2024-01-12")
        self.assertTrue(got["enters_v1"])
        self.assertEqual(got["reason"], "I-29(3)")
        self.assertEqual(got["window_start"], "2024-01-09")
        self.assertEqual(got["placeholder_runs"], [])

    def test_gap_through_the_end_does_not_enter_even_if_it_is_one_day(self):
        real = [day for day in CAL if day not in ("2024-01-01", "2024-01-12")]
        one = decide_i29(real, CAL, "2024-01-12")
        self.assertFalse(one["enters_v1"])
        self.assertFalse(one["blocks_pool"])
        self.assertIn("I-29(4)", one["reason"])
        self.assertIn("1 个交易日", one["reason"])
        long = decide_i29([day for day in real if day < "2024-01-08"], CAL, "2024-01-12")
        self.assertFalse(long["enters_v1"])
        self.assertIn("I-29(4)", long["reason"])
        self.assertNotIn("I-29(3)", long["reason"])


class Frame(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp))
        self.con = open_db(self.tmp / "m.sqlite")
        self.addCleanup(self.con.close)
        self.days = pd.bdate_range("2024-01-02", "2024-01-12")

    def _put(self, code, frame):
        put(self.con, code, frame, "csi")

    def test_research_frame_scales_by_k(self):
        days = self.days
        close = pd.Series(100.0 + pd.RangeIndex(len(days)), dtype=float)
        price = pd.DataFrame({"date": days, "open": close - 1, "high": close + 2, "low": close - 2,
                              "close": close, "volume": 10.0})
        research = price.assign(open=None, high=None, low=None, close=close * 2, volume=7.0)
        self._put("P", price)
        self._put("T", research)
        df, rep = B.research_frame(self.con, {"series_code": "T", "series_adj": "raw", "route_used": "csi", "code": "P"},
                                   pd.DatetimeIndex(days))
        self.assertEqual(rep["ohlc_source"], "price_version")
        self.assertEqual(rep["window_start"], "2024-01-02")
        self.assertEqual(int(df["data_hole"].sum()), 0)
        pd.testing.assert_series_equal(df["close"].reset_index(drop=True), (close * 2).reset_index(drop=True), check_names=False)
        pd.testing.assert_series_equal(df["open"].reset_index(drop=True), ((close - 1) * 2).reset_index(drop=True), check_names=False)
        pd.testing.assert_series_equal(df["high"].reset_index(drop=True), ((close + 2) * 2).reset_index(drop=True), check_names=False)
        pd.testing.assert_series_equal(df["low"].reset_index(drop=True), ((close - 2) * 2).reset_index(drop=True), check_names=False)

    def test_short_gap_becomes_flat_hole_and_terminal_gap_stays_out(self):
        days = self.days
        close = 100.0 + pd.Series(range(len(days)), dtype=float)
        full = pd.DataFrame({"date": days, "open": close - 1, "high": close + 2, "low": close - 2,
                             "close": close, "volume": 10.0})
        short = full[full["date"] != days[3]]
        self._put("S", short)
        df, rep = B.research_frame(self.con, {"series_code": "S", "series_adj": "raw", "route_used": "csi", "code": "S"},
                                   pd.DatetimeIndex(days))
        hole = df[df["date"] == days[3]].iloc[0]
        prev = df[df["date"] == days[2]].iloc[0]
        self.assertEqual(int(hole["data_hole"]), 1)
        self.assertEqual((hole["open"], hole["high"], hole["low"], hole["close"], hole["volume"]),
                         (prev["close"], prev["close"], prev["close"], prev["close"], 0.0))
        self.assertEqual(hole["state"], prev["state"])
        self.assertEqual(rep["stale_runs"][0]["hole_rows"], 1)
        terminal = full[full["date"] != days[-1]]
        self._put("E", terminal)
        empty, erep = B.research_frame(self.con, {"series_code": "E", "series_adj": "raw", "route_used": "csi", "code": "E"},
                                       pd.DatetimeIndex(days))
        self.assertTrue(empty.empty)
        self.assertFalse(erep["enters_v1"])
        self.assertIn("I-29(4)", erep["i29_reason"])

    def test_long_gap_drops_bars_before_the_new_window(self):
        days = self.days
        close = 100.0 + pd.Series(range(len(days)), dtype=float)
        full = pd.DataFrame({"date": days, "open": close - 1, "high": close + 2, "low": close - 2,
                             "close": close, "volume": 10.0})
        # 2024-01-02 起的第 1 到第 4 个交易日留下，中间连续去掉 4 天，尾部留下。
        drop = set(days[1:5])
        kept = full[~full["date"].isin(drop)]
        self._put("L", kept)
        df, rep = B.research_frame(self.con, {"series_code": "L", "series_adj": "raw", "route_used": "csi", "code": "L"},
                                   pd.DatetimeIndex(days))
        self.assertEqual(rep["window_start"], days[5].date().isoformat())
        self.assertEqual(str(df["date"].min().date()), rep["window_start"])
        self.assertNotIn(days[0], set(df["date"]))
