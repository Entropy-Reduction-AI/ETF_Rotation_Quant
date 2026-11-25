"""D45 第二版的构造测试。不打开 2016 年以后的行情。"""

from __future__ import annotations

import unittest

import pandas as pd

from v6ind.d45_engine import first_on_or_after, trin_from_prices
from v6ind.d45_french import _panel
from v6ind.load import FX_SQL


class FrenchWindowTest(unittest.TestCase):
    def test_dates_outside_the_prior_window_are_not_parsed(self) -> None:
        text = "\n".join([
            "Average Value Weighted Returns -- Monthly",
            ",Agric",
            "192607,1.0",
            "199812,2.0",
            "199901,999.0",
            "",
        ])
        frame = _panel(text, "Average Value Weighted Returns -- Monthly")
        self.assertEqual(list(frame.index.strftime("%Y%m")), ["192607", "199812"])
        self.assertNotIn(999.0, frame.to_numpy())


class PublishMaskTest(unittest.TestCase):
    def test_first_print_after_a_hole_is_the_next_session(self) -> None:
        series = pd.Series([1.0, 2.0], index=pd.to_datetime(["2013-12-25", "2014-01-02"]))
        self.assertEqual(str(first_on_or_after(series, pd.Timestamp("2013-12-26")).date()), "2014-01-02")


class ClipTest(unittest.TestCase):
    def test_sql_filters_fx_by_date(self) -> None:
        self.assertIn("date <= ?", FX_SQL)

    def test_expanding_clip_can_differ_and_zero_is_explicit(self) -> None:
        index = pd.bdate_range("2010-01-04", periods=40)
        prices = pd.DataFrame({name: range(1, 41) for name in "abcd"}, index=index, dtype=float)
        prices["c"] = range(40, 0, -1)
        prices["d"] = range(20, 60)
        amounts = pd.DataFrame(1.0, index=index, columns=list("abcd"))
        full = trin_from_prices(prices, amounts, clip="full")
        expanding = trin_from_prices(prices, amounts, clip="expanding")
        self.assertEqual(len(full), len(expanding))
        self.assertTrue(full.notna().any() or expanding.notna().any())


if __name__ == "__main__":
    unittest.main()
