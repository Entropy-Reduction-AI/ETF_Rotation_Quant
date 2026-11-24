"""Authorized DJIA / DWRTF raw append. No returns and no database writes."""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
import unittest
from pathlib import Path

import tests  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "market.sqlite"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


LIB = _load("v6_us_raw_index_lib", "v6_us_raw_index_lib.py")


class SourcePlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = LIB.build_source_plan()

    def test_both_series_end_on_cutoff_and_omit_pseudo_session(self):
        self.assertEqual(self.plan.problems, [])
        self.assertEqual(self.plan.djia[-1].date, "2026-09-30")
        self.assertEqual(self.plan.dwrtf[-1].date, "2026-09-30")
        self.assertEqual(self.plan.djia[0].date, "2024-02-02")
        self.assertEqual(self.plan.dwrtf[0].date, "2017-11-24")
        self.assertEqual(len(self.plan.djia), 667)
        self.assertEqual(len(self.plan.dwrtf), 2223)
        self.assertNotIn("2024-12-25", [bar.date for bar in self.plan.bars])
        self.assertTrue(all(bar.source == "v6_gapfill_fred" for bar in self.plan.djia))
        tv = [bar for bar in self.plan.dwrtf if bar.source == "v6_gapfill_tv"]
        self.assertEqual([(bar.date, bar.close_text) for bar in tv], [("2023-04-06", "259.56")])
        conflict = next(bar for bar in self.plan.dwrtf if bar.date == "2019-08-12")
        self.assertEqual(conflict.source, "v6_gapfill_cnbc")
        self.assertEqual(float(conflict.close_text), 294.58)
        flags = {item["date"]: item["flag"] for item in self.plan.flags}
        self.assertEqual(flags, {"2023-04-06": "single_source", "2019-08-12": "source_conflict"})
        self.assertEqual(self.plan.flags[1]["cause"], "")
        self.assertEqual(self.plan.flags[1]["reference_close"], "294.46")
        self.assertNotIn("return", self.plan.flags[1]["level_gap_over_reference"])

    def test_samples_cover_at_least_twenty_dates(self):
        djia = LIB.sample_dates([bar.date for bar in self.plan.djia], ["2024-02-02", "2026-09-30"])
        dwrtf = LIB.sample_dates(
            [bar.date for bar in self.plan.dwrtf],
            ["2017-11-24", "2019-08-12", "2023-04-06", "2026-09-30"],
        )
        self.assertGreaterEqual(len(djia), 20)
        self.assertGreaterEqual(len(dwrtf), 20)
        self.assertNotIn("2024-12-25", djia)
        self.assertNotIn("2024-12-25", dwrtf)
        self.assertIn("2023-04-06", dwrtf)
        self.assertIn("2019-08-12", dwrtf)


class DatabaseIngestTest(unittest.TestCase):
    def setUp(self):
        if not DB.exists() or DB.stat().st_size < 1000 or DB.read_bytes()[:8] != b"SQLite f":
            self.skipTest("market.sqlite 不是已展开的行情库")
        self.con = sqlite3.connect(f"file:{DB.resolve()}?mode=ro", uri=True)
        self.addCleanup(self.con.close)

    def test_final_dates_and_pseudo_session_omitted(self):
        lasts = dict(self.con.execute(
            "SELECT code, MAX(date) FROM bars WHERE code IN ('DJIA', 'DWRTF') AND adj = 'raw' GROUP BY code"
        ))
        self.assertEqual(lasts, {"DJIA": "2026-09-30", "DWRTF": "2026-09-30"})
        pseudo = self.con.execute(
            "SELECT COUNT(*) FROM bars WHERE code IN ('DJIA', 'DWRTF') AND date = '2024-12-25'"
        ).fetchone()[0]
        self.assertEqual(pseudo, 0)
        fred = self.con.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM bars "
            "WHERE code = 'DJIA' AND adj = 'raw' AND source = 'v6_gapfill_fred'"
        ).fetchone()
        cnbc = self.con.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM bars "
            "WHERE code = 'DWRTF' AND adj = 'raw' AND source = 'v6_gapfill_cnbc'"
        ).fetchone()
        tv = self.con.execute(
            "SELECT date, close, open FROM bars "
            "WHERE code = 'DWRTF' AND adj = 'raw' AND source = 'v6_gapfill_tv'"
        ).fetchall()
        self.assertEqual(fred, (667, "2024-02-02", "2026-09-30"))
        self.assertEqual(cnbc, (2222, "2017-11-24", "2026-09-30"))
        self.assertEqual([(row[0], row[1], row[2]) for row in tv], [("2023-04-06", 259.56, None)])
        conflict = self.con.execute(
            "SELECT source, close FROM bars WHERE code = 'DWRTF' AND adj = 'raw' AND date = '2019-08-12'"
        ).fetchone()
        self.assertEqual(conflict[0], "v6_gapfill_cnbc")
        self.assertEqual(conflict[1], 294.58)
        edge_dj = self.con.execute(
            "SELECT source, close, open FROM bars WHERE code = 'DJIA' AND adj = 'raw' AND date = '2024-02-01'"
        ).fetchone()
        edge_dw = self.con.execute(
            "SELECT source, close, open FROM bars WHERE code = 'DWRTF' AND adj = 'raw' AND date = '2017-11-22'"
        ).fetchone()
        self.assertEqual(edge_dj[0], "eastmoney_index")
        self.assertEqual(edge_dj[1], 38519.84)
        self.assertEqual(edge_dj[2], 38175.34)
        self.assertEqual(edge_dw[0], "d37_r6")
        self.assertEqual(edge_dw[1], 275.66)
        self.assertIsNone(edge_dw[2])
        filled = self.con.execute(
            "SELECT COUNT(*) FROM bars WHERE source IN ('v6_gapfill_fred', 'v6_gapfill_cnbc', 'v6_gapfill_tv') "
            "AND (open IS NOT NULL OR high IS NOT NULL OR low IS NOT NULL "
            "OR volume IS NOT NULL OR amount IS NOT NULL)"
        ).fetchone()[0]
        self.assertEqual(filled, 0)

    def test_source_guard_sql_roundtrip(self):
        sql = self.con.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'bars_one_source'"
        ).fetchone()[0]
        memory = sqlite3.connect(":memory:")
        self.addCleanup(memory.close)
        memory.execute(
            "CREATE TABLE bars (code TEXT, adj TEXT, date TEXT, source TEXT, "
            "PRIMARY KEY (code, adj, date))"
        )
        memory.execute(sql)
        stored = memory.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'bars_one_source'"
        ).fetchone()[0]
        LIB.reinstall_source_guard(memory, stored)
        again = memory.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'bars_one_source'"
        ).fetchone()[0]
        self.assertEqual(stored, again)
        memory.execute("INSERT INTO bars VALUES ('DJIA', 'raw', '1990-04-25', 'eastmoney_index')")
        with self.assertRaises(sqlite3.IntegrityError):
            memory.execute("INSERT INTO bars VALUES ('DJIA', 'raw', '2024-02-02', 'v6_gapfill_fred')")


if __name__ == "__main__":
    unittest.main()
