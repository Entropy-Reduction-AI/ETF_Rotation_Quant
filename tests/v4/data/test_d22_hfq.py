"""D22 后复权统一入口。手造序列，不出网，不算组合收益。"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

import tests  # noqa: F401 — ETF_LEDGER_TESTING

from src.v4.data.hfq import (
    DIFF_PP,
    canonical_closes,
    canonical_hfq,
    exceeds_diff,
    return_conflicts,
    source_inventory,
    write_r5,
)
from src.v4.engine.carriers import hfq_dates, research_return
from src.v4.engine.pool import _closes_frame
from tests.v4.engine.test_r1e import _candidate


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute(
        """CREATE TABLE bars (
            code TEXT, adj TEXT, date TEXT, close REAL, source TEXT)"""
    )
    con.execute(
        """CREATE TABLE v4_series (
            code TEXT, kind TEXT, date TEXT, close REAL, source TEXT)"""
    )
    return con


def _bar(con, code, adj, day, close, source="eastmoney_etf_hfq"):
    con.execute(
        "INSERT INTO bars VALUES (?, ?, ?, ?, ?)",
        (code, adj, day, close, source))


def _series(con, code, kind, day, close, source):
    con.execute(
        "INSERT INTO v4_series VALUES (?, ?, ?, ?, ?)",
        (code, kind, day, close, source))


class SelectionOrder(unittest.TestCase):
    def test_eastmoney_beats_tencent_and_rebuild(self):
        con = _db()
        _bar(con, "160125", "hfq", "2012-02-16", 10.0)
        _bar(con, "160125", "hfq", "2012-02-17", 12.0)
        _series(con, "160125", "backward", "2012-02-16", 10.0, "tencent_etf_hfq")
        _series(con, "160125", "backward", "2012-02-17", 11.0, "tencent_etf_hfq")
        _series(con, "160125", "backward_rebuild", "2012-02-16", 10.0, "还原")
        _series(con, "160125", "backward_rebuild", "2012-02-17", 13.0, "还原")
        chosen = canonical_hfq(con, "160125", "2012-02-17")
        self.assertEqual(chosen.tier, "eastmoney")
        self.assertAlmostEqual(float(chosen.closes.iloc[-1]), 12.0)
        self.assertNotAlmostEqual(float(chosen.closes.iloc[-1]), 11.0)
        self.assertNotAlmostEqual(float(chosen.closes.iloc[-1]), 13.0)

    def test_tencent_includes_carry_tail_and_keeps_base_on_overlap(self):
        con = _db()
        _series(con, "160125", "backward", "2019-07-03", 10.0, "tencent_etf_hfq")
        _series(con, "160125", "backward", "2019-07-03", 99.0, "tencent_etf_hfq_carry")
        _series(con, "160125", "backward", "2019-07-04", 11.0, "tencent_etf_hfq_carry")
        closes = canonical_closes(con, "160125", "2019-07-04")
        self.assertEqual(canonical_hfq(con, "160125", "2019-07-04").tier, "tencent")
        self.assertAlmostEqual(float(closes.loc[pd.Timestamp("2019-07-03")]), 10.0)
        self.assertAlmostEqual(float(closes.loc[pd.Timestamp("2019-07-04")]), 11.0)
        self.assertNotAlmostEqual(float(closes.loc[pd.Timestamp("2019-07-03")]), 99.0)

    def test_v4_eastmoney_fills_dates_missing_from_bars(self):
        con = _db()
        _bar(con, "160216", "hfq", "2015-04-07", 2.0)
        _series(con, "160216", "backward", "2015-04-07", 9.0, "eastmoney_etf_hfq")
        _series(con, "160216", "backward", "2015-04-08", 2.2, "eastmoney_etf_hfq")
        closes = canonical_closes(con, "160216", "2015-04-08")
        self.assertAlmostEqual(float(closes.loc[pd.Timestamp("2015-04-07")]), 2.0)
        self.assertAlmostEqual(float(closes.loc[pd.Timestamp("2015-04-08")]), 2.2)

    def test_rebuild_is_used_only_after_eastmoney_and_tencent(self):
        con = _db()
        _series(con, "513820", "backward", "2015-01-05", 1.1, "还原")
        _series(con, "513820", "backward", "2015-01-06", 1.2, "还原")
        self.assertEqual(canonical_hfq(con, "513820", "2015-01-06").tier, "d21")
        _series(con, "160644", "backward", "2015-01-05", 1.0, "tencent_etf_hfq")
        _series(con, "160644", "backward", "2015-01-06", 1.5, "tencent_etf_hfq")
        _series(con, "160644", "backward_rebuild", "2015-01-05", 1.0, "还原")
        _series(con, "160644", "backward_rebuild", "2015-01-06", 1.0, "还原")
        chosen = canonical_hfq(con, "160644", "2015-01-06")
        self.assertEqual(chosen.tier, "tencent")
        self.assertAlmostEqual(float(chosen.closes.iloc[-1]), 1.5)

    def test_sole_backward_when_the_three_tiers_are_absent(self):
        con = _db()
        _series(con, "159501", "backward", "2015-01-05", 1.0, "eastmoney_fhsp")
        _series(con, "159501", "backward", "2015-01-06", 1.1, "eastmoney_fhsp")
        self.assertEqual(canonical_hfq(con, "159501", "2015-01-06").tier, "eastmoney_fhsp")
        _series(con, "XLB", "backward", "2015-01-05", 20.0, "yahoo")
        self.assertEqual(canonical_hfq(con, "XLB", "2015-01-06").tier, "yahoo")

    def test_two_leftover_sources_are_not_auto_picked(self):
        con = _db()
        _series(con, "159999", "backward", "2015-01-05", 1.0, "eastmoney_fhsp")
        _series(con, "159999", "backward", "2015-01-05", 2.0, "yahoo")
        self.assertIsNone(canonical_hfq(con, "159999", "2015-01-06"))
        self.assertTrue(canonical_closes(con, "159999", "2015-01-06").empty)

    def test_unlabeled_fixture_still_reads_kind_backward(self):
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE v4_series (code TEXT, kind TEXT, date TEXT, close REAL)")
        con.executemany(
            "INSERT INTO v4_series VALUES (?, ?, ?, ?)",
            [
                ("159985", "backward", "2006-01-04", 10.0),
                ("159985", "backward", "2006-01-05", 11.0),
            ])
        days = pd.to_datetime(["2006-01-04", "2006-01-05"])
        got = research_return(con, _candidate("159985", days, [80e6, 80e6]), days, "2006-01-05", 2)
        self.assertTrue(pd.isna(got.iloc[0]))
        self.assertAlmostEqual(float(got.iloc[1]), 0.10)
        self.assertEqual(list(hfq_dates(con, "159985", "2006-01-05")), list(days))


class ConflictList(unittest.TestCase):
    def test_lists_days_over_0_1_pp_and_does_not_change_the_series(self):
        con = _db()
        # 2 月 17 日差 0.20 个百分点；2 月 20 日差 0.05 个百分点。刚好 0.10 由 exceeds_diff 锁住。
        _series(con, "160125", "backward", "2012-02-16", 100.0, "tencent_etf_hfq")
        _series(con, "160125", "backward", "2012-02-17", 101.2, "tencent_etf_hfq")
        _series(con, "160125", "backward", "2012-02-20", 101.2, "tencent_etf_hfq")
        _series(con, "160125", "backward_rebuild", "2012-02-16", 100.0, "还原")
        _series(con, "160125", "backward_rebuild", "2012-02-17", 101.0, "还原")
        _series(con, "160125", "backward_rebuild", "2012-02-20", 101.0505, "还原")
        before = con.execute("SELECT COUNT(*) FROM v4_series").fetchone()[0]
        rows = return_conflicts("160125", {
            "tencent": canonical_closes(con, "160125", "2012-02-20"),
            "d21": pd.Series(
                [100.0, 101.0, 101.0505],
                index=pd.to_datetime(["2012-02-16", "2012-02-17", "2012-02-20"])),
        })
        # 选用仍是腾讯，不因为冲突日改成还原。
        self.assertEqual(canonical_hfq(con, "160125", "2012-02-20").tier, "tencent")
        self.assertEqual(con.execute("SELECT COUNT(*) FROM v4_series").fetchone()[0], before)
        dates = [row["date"] for row in rows]
        self.assertIn("2012-02-17", dates)
        self.assertNotIn("2012-02-20", dates)
        hit = next(row for row in rows if row["date"] == "2012-02-17")
        self.assertEqual(hit["left_tier"], "tencent")
        self.assertEqual(hit["right_tier"], "d21")
        self.assertGreater(abs(hit["diff_pp"]), DIFF_PP)
        self.assertFalse(exceeds_diff(0.0, 0.001))
        self.assertTrue(exceeds_diff(0.0, 0.001 + 0.001))

    def test_research_and_pool_use_the_canonical_series(self):
        con = _db()
        _bar(con, "159985", "hfq", "2006-01-04", 10.0)
        _bar(con, "159985", "hfq", "2006-01-05", 12.0)
        _series(con, "159985", "backward", "2006-01-04", 10.0, "tencent_etf_hfq")
        _series(con, "159985", "backward", "2006-01-05", 11.0, "tencent_etf_hfq")
        days = pd.to_datetime(["2006-01-04", "2006-01-05"])
        got = research_return(con, _candidate("159985", days, [80e6, 80e6]), days, "2006-01-05", 2)
        self.assertAlmostEqual(float(got.iloc[1]), 0.20)
        self.assertNotAlmostEqual(float(got.iloc[1]), 0.10)
        frame = _closes_frame(con, "159985", "2006-01-05", kind="backward")
        self.assertAlmostEqual(float(frame["close"].iloc[-1]), 12.0)
        only_bars = _db()
        _bar(only_bars, "510300", "hfq", "2006-01-04", 3.0)
        self.assertEqual(len(hfq_dates(only_bars, "510300", "2006-01-04")), 1)

    def test_inventory_marks_priority_without_writing_the_database(self):
        con = _db()
        _bar(con, "159920", "hfq", "2015-01-05", 1.0)
        _series(con, "159920", "backward", "2015-01-05", 1.0, "tencent_etf_hfq")
        _series(con, "160125", "backward", "2015-01-05", 1.0, "tencent_etf_hfq")
        _series(con, "160125", "backward", "2015-01-06", 1.3, "tencent_etf_hfq")
        _series(con, "160125", "backward_rebuild", "2015-01-05", 1.0, "还原")
        _series(con, "160125", "backward_rebuild", "2015-01-06", 1.0, "还原")
        rows = { (row["code"], row["tier"]): row["selected"] for row in source_inventory(con) }
        self.assertEqual(rows[("159920", "eastmoney")], "1")
        self.assertEqual(rows[("159920", "tencent")], "0")
        self.assertEqual(rows[("160125", "tencent")], "1")
        self.assertEqual(rows[("160125", "d21")], "0")
        before = con.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
        with tempfile.TemporaryDirectory() as tmp:
            summary = write_r5(con, ("160125",), Path(tmp), end="2015-01-06")
            self.assertTrue((Path(tmp) / "hfq-return-conflicts.csv").is_file())
        self.assertEqual(summary["by_code"]["160125"]["canonical_tier"], "tencent")
        self.assertEqual(summary["by_code"]["160125"]["conflict_days"], 1)
        self.assertEqual(summary["database_written"], False)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM bars").fetchone()[0], before)


if __name__ == "__main__":
    unittest.main()
