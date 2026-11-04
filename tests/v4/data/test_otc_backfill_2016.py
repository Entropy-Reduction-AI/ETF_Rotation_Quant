"""场外净值续接只追加接缝之后的日期。不出网，不碰默认库。"""
from __future__ import annotations

import unittest

import tests  # noqa: F401 — ETF_LEDGER_TESTING

from src.v4.data.otc_backfill_2016 import END, SEAM, plan_continuation


def _row(day: str, close: float, unit: float = 1.0, accum: float | None = None) -> dict:
    return {
        "date": day,
        "close": close,
        "unit_nav": unit,
        "accum_nav": unit if accum is None else accum,
    }


class Continuation(unittest.TestCase):
    def test_exact_seam_appends_only_later_dates(self):
        stored = [_row("2015-12-30", 1.0, 1.1), _row(SEAM, 1.1, 1.2)]
        fresh = [
            _row("2015-12-30", 1.0, 1.1),
            _row(SEAM, 1.1, 1.2),
            _row("2016-01-04", 1.2, 1.3),
            _row("2026-10-01", 9.0, 2.0),
        ]
        plan = plan_continuation(stored, fresh)
        self.assertEqual(plan["status"], "exact")
        self.assertEqual(plan["scale"], 1.0)
        self.assertEqual([row["date"] for row in plan["rows"]], ["2016-01-04"])
        self.assertEqual(plan["rows"][0]["close"], 1.2)
        self.assertLessEqual(plan["overlap_max_rel"], 1e-12)

    def test_unit_mismatch_inserts_nothing(self):
        stored = [_row(SEAM, 1.0, 1.0)]
        fresh = [_row(SEAM, 1.0, 1.2), _row("2016-01-04", 1.1, 1.3)]
        plan = plan_continuation(stored, fresh)
        self.assertEqual(plan["status"], "seam_refuse")
        self.assertEqual(plan["rows"], [])

    def test_small_close_gap_scales_the_tail(self):
        stored = [_row(SEAM, 1.0, 1.5)]
        fresh = [_row(SEAM, 1.0005, 1.5), _row("2016-01-04", 1.10055, 1.6)]
        plan = plan_continuation(stored, fresh)
        self.assertEqual(plan["status"], "scaled")
        self.assertEqual(len(plan["rows"]), 1)
        self.assertAlmostEqual(plan["rows"][0]["close"], 1.10055 * (1.0 / 1.0005))
        self.assertNotIn(SEAM, {row["date"] for row in plan["rows"]})

    def test_large_close_gap_is_refused(self):
        stored = [_row(SEAM, 1.0, 1.5)]
        fresh = [_row(SEAM, 1.2, 1.5), _row("2016-01-04", 1.3, 1.6)]
        plan = plan_continuation(stored, fresh)
        self.assertEqual(plan["status"], "seam_refuse")
        self.assertEqual(plan["rows"], [])

    def test_missing_seam_inserts_nothing(self):
        plan = plan_continuation([_row("2015-12-30", 1.0)], [_row("2016-01-04", 1.1)])
        self.assertEqual(plan["status"], "seam_missing")
        self.assertEqual(plan["rows"], [])

    def test_end_date_is_kept(self):
        stored = [_row(SEAM, 1.0)]
        fresh = [_row(SEAM, 1.0), _row(END, 1.4), _row("2026-10-09", 1.5)]
        plan = plan_continuation(stored, fresh)
        self.assertEqual([row["date"] for row in plan["rows"]], [END])


if __name__ == "__main__":
    unittest.main()
