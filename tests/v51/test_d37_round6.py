"""第六轮入库的纯函数：不连行情库，不补缺口，不覆盖已有收盘。"""
from __future__ import annotations

import unittest

from src.v51.d37_round6 import (
    MEDIAN_LIMIT,
    PARTIAL_START,
    append_after,
    clip_levels,
    fill_missing,
    rel_stats,
)


class PartialStarts(unittest.TestCase):
    def test_ingest_is_the_later_of_publish_and_continuous(self):
        self.assertEqual(set(PARTIAL_START), {
            "theme-SPAHLVCP",
            "theme-S&P 500 Energy Sector Index(NTR)",
            "theme-标普500消费精选指数",
            "theme-标普美国品质消费股票指数",
            "theme-标普中国新经济行业指数",
        })
        for spec in PARTIAL_START.values():
            self.assertEqual(spec["ingest"], max(spec["publish"], spec["continuous"]))
        self.assertEqual(PARTIAL_START["theme-SPAHLVCP"]["ingest"], "2017-08-04")
        self.assertEqual(PARTIAL_START["theme-S&P 500 Energy Sector Index(NTR)"]["ingest"], "1998-12-31")
        self.assertEqual(PARTIAL_START["theme-标普500消费精选指数"]["ingest"], "2022-11-25")
        self.assertEqual(PARTIAL_START["theme-标普美国品质消费股票指数"]["ingest"], "1998-12-16")
        self.assertEqual(PARTIAL_START["theme-标普中国新经济行业指数"]["ingest"], "2020-05-14")


class Levels(unittest.TestCase):
    def test_fill_missing_does_not_overwrite(self):
        base = {"2000-01-21": 288.89, "2000-01-20": 290.0}
        extra = {"2000-01-21": 293.63, "2000-01-24": 291.0, "1999-12-31": 280.0}
        got, added = fill_missing(base, extra, "2000-01-02", "2001-12-04")
        self.assertEqual(added, 1)
        self.assertEqual(got["2000-01-21"], 288.89)
        self.assertEqual(got["2000-01-24"], 291.0)
        self.assertNotIn("1999-12-31", got)

    def test_append_after_does_not_overlap(self):
        got, added = append_after({"2012-09-24": 502.22}, {"2012-09-24": 1.0, "2012-09-25": 494.52})
        self.assertEqual(added, 1)
        self.assertEqual(got["2012-09-24"], 502.22)
        self.assertEqual(got["2012-09-25"], 494.52)

    def test_clip_drops_pre_start_list_date_and_disclosed_bar(self):
        levels = {
            "2017-02-20": 1000.0,
            "2017-08-03": 1200.0,
            "2017-08-04": 1231.02,
            "2023-12-07": 1300.0,
            "2023-12-08": 1301.0,
            "2025-11-28": 1350.08,
        }
        rows = clip_levels(levels, "2017-08-04", "2023-12-08", drop={"2025-11-28"})
        self.assertEqual([row["date"] for row in rows], ["2017-08-04", "2023-12-07"])

    def test_median_gate_is_one_basis_point_of_a_percent(self):
        left = {f"2020-01-{day:02d}": 100.0 for day in range(1, 32)}
        right = dict(left)
        right["2020-01-15"] = 100.02
        stats = rel_stats(left, right)
        self.assertLessEqual(stats["median"], MEDIAN_LIMIT)
        right = {day: close * 1.002 for day, close in left.items()}
        stats = rel_stats(left, right)
        self.assertGreater(stats["median"], MEDIAN_LIMIT)
        self.assertFalse(stats["ok"])


if __name__ == "__main__":
    unittest.main()
