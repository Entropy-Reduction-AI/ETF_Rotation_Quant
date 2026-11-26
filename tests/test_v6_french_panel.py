"""French 面板只保留 1926-07 至 1998-12。用合成文本，不读官网原件。"""

from __future__ import annotations

import io
import unittest

import pandas as pd

from src.v6.french_panel import extract_panels
from src.v6.prior import breadth_ex_parent, french_ma_vote

SAMPLE = """
Average Value Weighted Returns -- Monthly
,Agric,Food
192606, 1.00, 2.00
192607, 3.00, 4.00
199812, 5.00, 6.00
199901, 7.00, 8.00
201601, 9999.99, 8888.88

Average Equal Weighted Returns -- Monthly
,Agric,Food
199812, 1.00, 1.00
201601, 7777.77, 6666.66

Number of Firms in Portfolios
,Agric,Food
192607, 10, 11
199812, 12, 13
201609, 14, 15

Average Firm Size
,Agric,Food
192607, 20.5, 21.5
199812, 22.5, 23.5
202609, 24.5, 25.5
"""


class FrenchPanelTests(unittest.TestCase):
    def test_keeps_only_the_closed_window(self):
        panels = extract_panels(io.StringIO(SAMPLE))
        monthly = panels["Average Value Weighted Returns -- Monthly"]
        self.assertEqual([row["yyyymm"] for row in monthly], ["192607", "199812"])
        self.assertEqual(monthly[0]["Agric"], "3.00")
        blob = "\n".join(cell for row in monthly for cell in row.values())
        self.assertNotIn("9999.99", blob)
        self.assertNotIn("201601", blob)
        firms = panels["Number of Firms in Portfolios"]
        self.assertEqual([row["yyyymm"] for row in firms], ["192607", "199812"])
        self.assertNotIn("14", [row["Agric"] for row in firms])
        size = panels["Average Firm Size"]
        self.assertEqual(size[-1]["yyyymm"], "199812")
        self.assertNotIn("24.5", [row["Agric"] for row in size])


class FrenchVoteTests(unittest.TestCase):
    def test_equal_to_average_is_a_vote(self):
        self.assertTrue(french_ma_vote(10.0, 10.0))
        self.assertFalse(french_ma_vote(10.1, 10.0))

    def test_breadth_drops_the_market(self):
        above = pd.Series({"MKT": False, "Agric": True, "Food": True})
        self.assertEqual(breadth_ex_parent(above, "MKT"), 1.0)


if __name__ == "__main__":
    unittest.main()
