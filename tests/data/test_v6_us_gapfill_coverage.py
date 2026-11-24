"""交易日覆盖规则。不连行情库，不改原始收盘。"""
import importlib.util
import unittest
from pathlib import Path

import tests  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "v6_us_gapfill_compare",
    ROOT / "scripts" / "v6_us_gapfill_compare.py",
)
GAP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GAP)


class SessionCalendarTest(unittest.TestCase):
    def test_named_dates(self):
        self.assertFalse(GAP.is_session("2024-12-25"))
        self.assertTrue(GAP.is_session("2024-12-24"))
        self.assertTrue(GAP.is_session("2023-04-06"))
        self.assertFalse(GAP.is_session("2023-04-07"))
        self.assertTrue(GAP.is_session("2021-12-31"))
        self.assertFalse(GAP.is_session("2017-09-04"))

    def test_fred_blanks_match_named_closes(self):
        blanks = GAP.fred_blank_weekdays(
            ROOT / "incoming/v6-us-gapfill/raw/fred-DJIA.csv",
            "2017-08-01",
            "2026-09-30",
        )
        self.assertEqual(set(blanks), set(GAP.NYSE_FULL_CLOSE))

    def test_pseudo_day_is_not_coverage_and_a_gap_stays_open(self):
        rows = {"2024-12-24": "1", "2024-12-25": "1", "2024-12-26": "2"}
        report = GAP.archive_vs_sessions(rows, "2024-12-24", "2024-12-26")
        self.assertEqual(report["missing_sessions"], [])
        self.assertEqual(report["non_session_rows"], ["2024-12-25"])
        self.assertEqual(report["sessions_present"], 2)
        self.assertFalse(report["sessions_complete"] and not report["non_session_rows"])

        gapped = {"2023-04-05": "1", "2023-04-10": "2"}
        missing = GAP.archive_vs_sessions(gapped, "2023-04-05", "2023-04-10")
        self.assertIn("2023-04-06", missing["missing_sessions"])
        self.assertNotIn("2023-04-07", missing["missing_sessions"])
        self.assertFalse(missing["sessions_complete"])

    def test_close_conflict_is_not_adopted(self):
        left = {"2019-08-12": "294.58", "2019-08-13": "295.10"}
        right = {"2019-08-12": "294.46", "2019-08-13": "295.10"}
        found = GAP.close_conflicts(left, right, "2019-08-12", "2019-08-13")
        self.assertEqual([item["date"] for item in found], ["2019-08-12"])
        self.assertIsNone(found[0]["adopted_close"])
        self.assertEqual(found[0]["kind"], "unresolved_source_conflict")
        self.assertGreater(found[0]["abs_diff"], 0.005)


if __name__ == "__main__":
    unittest.main()
