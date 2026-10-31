"""D25-8 修正收盘和 D25-9 反向尖刺。手造序列，不出网，不算组合收益。"""
from __future__ import annotations

import sqlite3
import unittest

import pandas as pd

import tests  # noqa: F401 — ETF_LEDGER_TESTING

from src.v4.data.d25_8 import (
    BAD_HFQ,
    BAD_RAW,
    CODE,
    DAY,
    PREV_DAY,
    PREV_HFQ,
    PREV_RAW,
    corrected_hfq_close,
    insert_correction,
)
from src.v4.data.hfq import CORRECTION_KIND, canonical_hfq
from src.v4.data.spike_check import affects_holding, reversal_spikes


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute(
        """CREATE TABLE bars (
            code TEXT, adj TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL,
            volume REAL, amount REAL, source TEXT, fetched_at TEXT,
            PRIMARY KEY (code, adj, date))"""
    )
    con.execute(
        """CREATE TABLE v4_series (
            code TEXT, kind TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL,
            volume REAL, unit_nav REAL, accum_nav REAL, filled INTEGER,
            source TEXT, source_url TEXT, method TEXT, fetched_at TEXT,
            PRIMARY KEY (code, kind, date))"""
    )
    return con


def _raw(con, day, close):
    con.execute(
        """INSERT INTO bars
           (code, adj, date, close, source, fetched_at)
           VALUES (?, 'raw', ?, ?, 'tencent_etf', 't')""",
        (CODE, day, close),
    )


def _hfq(con, day, close, kind="backward", source="tencent_etf_hfq"):
    con.execute(
        """INSERT INTO v4_series
           (code, kind, date, close, filled, source, source_url, method, fetched_at)
           VALUES (?, ?, ?, ?, 0, ?, 'u', '', 't')""",
        (CODE, kind, day, close, source),
    )


class Correction(unittest.TestCase):
    def test_insert_keeps_the_bad_rows_and_hfq_uses_the_new_close(self):
        con = _db()
        _raw(con, PREV_DAY, PREV_RAW)
        _raw(con, DAY, BAD_RAW)
        _raw(con, "2008-01-03", 4.794)
        _hfq(con, PREV_DAY, PREV_HFQ)
        _hfq(con, DAY, BAD_HFQ)
        _hfq(con, "2008-01-03", 3.141)
        result = insert_correction(con, fetched_at="2026-10-31T12:00:00+08:00")
        self.assertEqual(result["status"], "inserted")
        chosen = canonical_hfq(con, CODE, "2015-12-31")
        self.assertEqual(chosen.tier, "tencent")
        self.assertAlmostEqual(float(chosen.closes.loc[pd.Timestamp(DAY)]), corrected_hfq_close())
        self.assertAlmostEqual(float(chosen.closes.loc[pd.Timestamp(PREV_DAY)]), PREV_HFQ)
        self.assertAlmostEqual(float(chosen.closes.loc[pd.Timestamp("2008-01-03")]), 3.141)
        raw = con.execute(
            "SELECT close FROM bars WHERE code = ? AND adj = 'raw' AND date = ?",
            (CODE, DAY),
        ).fetchone()[0]
        old = con.execute(
            """SELECT close FROM v4_series
               WHERE code = ? AND kind = 'backward' AND date = ?""",
            (CODE, DAY),
        ).fetchone()[0]
        self.assertAlmostEqual(raw, BAD_RAW)
        self.assertAlmostEqual(old, BAD_HFQ)
        again = insert_correction(con, fetched_at="2026-10-31T12:00:00+08:00")
        self.assertEqual(again["status"], "already")
        count = con.execute(
            "SELECT COUNT(*) FROM v4_series WHERE code = ? AND kind = ?",
            (CODE, CORRECTION_KIND),
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_eastmoney_tier_is_not_overwritten_by_the_tencent_correction(self):
        con = _db()
        con.execute(
            """INSERT INTO bars (code, adj, date, close, source, fetched_at)
               VALUES ('160125', 'hfq', '2012-02-17', 12.0, 'eastmoney_etf_hfq', 't')"""
        )
        _hfq(con, "2012-02-16", 10.0, source="tencent_etf_hfq")
        con.execute(
            """INSERT INTO v4_series
               (code, kind, date, close, filled, source, source_url, method, fetched_at)
               VALUES ('160125', 'backward', '2012-02-17', 11.0, 0, 'tencent_etf_hfq', 'u', '', 't')"""
        )
        con.execute(
            """INSERT INTO v4_series
               (code, kind, date, close, filled, source, source_url, method, fetched_at)
               VALUES ('160125', ?, '2012-02-17', 9.0, 0, 'd25-8-eastmoney-kline', 'u', '', 't')""",
            (CORRECTION_KIND,),
        )
        chosen = canonical_hfq(con, "160125", "2012-02-17")
        self.assertEqual(chosen.tier, "eastmoney")
        self.assertAlmostEqual(float(chosen.closes.iloc[-1]), 12.0)

    def test_corrected_close_matches_the_previous_day_raw_move(self):
        close = corrected_hfq_close()
        self.assertAlmostEqual(close / PREV_HFQ - 1.0, 4.649 / PREV_RAW - 1.0, places=12)
        self.assertGreater(close, 3.0)
        self.assertLess(close, 3.1)


class Spikes(unittest.TestCase):
    def test_only_a_large_move_that_reverses_on_the_next_print(self):
        rows = [
            ("2015-01-05", 10.0),
            ("2015-01-06", 12.0),
            ("2015-01-07", 8.0),
            ("2015-01-08", 8.2),
            ("2015-01-09", 9.5),
            ("2016-01-04", 1.0),
        ]
        found = reversal_spikes(rows)
        self.assertEqual([item["date"] for item in found], ["2015-01-06", "2015-01-07"])
        self.assertAlmostEqual(found[0]["ret"], 0.2)
        self.assertLess(found[0]["next_ret"], 0)
        quiet = reversal_spikes([
            ("2015-01-05", 10.0),
            ("2015-01-06", 11.4),
            ("2015-01-07", 11.0),
        ])
        self.assertEqual(quiet, [])
        same_way = reversal_spikes([
            ("2015-01-05", 10.0),
            ("2015-01-06", 12.0),
            ("2015-01-07", 13.0),
        ])
        self.assertEqual(same_way, [])

    def test_holding_flag_follows_the_earning_carrier(self):
        self.assertEqual(affects_holding(
            role="carrier", code="510880", earning_code="510880",
            held_index=0.0, held_tradable=0.2), "yes")
        self.assertEqual(affects_holding(
            role="carrier", code="510880", earning_code="515180",
            held_index=0.0, held_tradable=0.2), "no")
        self.assertEqual(affects_holding(
            role="research", code="H00922", earning_code="",
            held_index=0.1, held_tradable=0.0), "yes")
        self.assertEqual(affects_holding(
            role="research", code="H00922", earning_code="",
            held_index=0.0, held_tradable=0.0), "no")


if __name__ == "__main__":
    unittest.main()
