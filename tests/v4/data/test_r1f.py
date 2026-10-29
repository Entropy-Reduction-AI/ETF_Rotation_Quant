"""v4-R1f 后复权还原。不出网，不算组合收益。"""
from __future__ import annotations

import unittest

import tests  # noqa: F401 — ETF_LEDGER_TESTING

from src.data import db as DB
from src.v4.data.r1f import (
    CASH_CODES,
    END,
    FLAT_CODES,
    KIND_BACKWARD,
    KIND_REBUILD,
    METHOD_DIV,
    METHOD_FLAT,
    SOURCE,
    R1fError,
    choose_method,
    destination,
    insert_series,
    rebuild_bars,
    same_closes,
    window_dividends,
    year_crosscheck,
)


EMPTY = {
    "dividends": [],
    "splits": [],
    "explicit_empty_dividend": True,
    "explicit_empty_split": True,
}


def _bar(day, close, open_=None):
    return {
        "date": day,
        "open": close if open_ is None else open_,
        "high": close,
        "low": close if open_ is None else min(open_, close),
        "close": close,
        "volume": 10,
    }


def _table(con):
    con.execute(
        """CREATE TABLE v4_series (
            code TEXT, kind TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL,
            volume REAL, unit_nav REAL, accum_nav REAL, filled INTEGER, source TEXT,
            source_url TEXT, method TEXT, fetched_at TEXT,
            PRIMARY KEY (code, kind, date))""")


class Factor(unittest.TestCase):
    def test_no_corporate_action_copies_raw_and_uses_factor_one(self):
        bars = [_bar("2024-03-04", 1.01), _bar("2024-03-05", 1.02, open_=1.015)]
        self.assertEqual(choose_method(EMPTY, []), METHOD_FLAT)
        built = rebuild_bars(bars, [])
        self.assertTrue(same_closes(bars, built["adjusted"]))
        self.assertEqual(built["adjusted"][1]["open"], 1.015)
        self.assertEqual(built["adjusted"][1]["close"], 1.02)
        self.assertEqual(built["applied"], [])

    def test_ex_date_factor_is_prev_over_prev_minus_dividend(self):
        bars = [_bar("2024-01-02", 10), _bar("2024-01-03", 9.5), _bar("2024-01-04", 10.5)]
        built = rebuild_bars(bars, [{"date": "2024-01-03", "amount": 0.5}])
        step = 10 / (10 - 0.5)
        self.assertAlmostEqual(built["applied"][0]["factor_step"], step)
        self.assertAlmostEqual(built["adjusted"][0]["close"], 10)
        self.assertAlmostEqual(built["adjusted"][1]["close"], 9.5 * step)
        self.assertAlmostEqual(built["adjusted"][2]["close"], 10.5 * step)
        self.assertAlmostEqual(built["adjusted"][1]["close"], 10)

    def test_dividend_after_cutoff_is_left_out(self):
        parsed = {
            "dividends": [
                {"date": "2026-09-23", "amount": 0.004, "record_date": "2026-09-22", "text": "每10份派现金0.0400元"},
                {"date": "2026-10-27", "amount": 0.004, "record_date": "2026-10-26", "text": "每10份派现金0.0400元"},
            ],
            "splits": [],
        }
        kept = window_dividends(parsed, END)
        self.assertEqual([row["date"] for row in kept], ["2026-09-23"])
        self.assertEqual(choose_method(parsed, kept), METHOD_DIV)

    def test_per_share_amount_rounds_to_the_published_precision(self):
        parsed = {"dividends": [{"date": "2026-04-27", "amount": 0.003 / 10}], "splits": []}
        self.assertEqual(window_dividends(parsed)[0]["amount"], 0.0003)

    def test_split_is_refused(self):
        with self.assertRaises(R1fError):
            window_dividends({"dividends": [], "splits": [{"date": "2024-01-02"}]})

    def test_dividend_not_below_prev_close_is_refused(self):
        with self.assertRaises(R1fError):
            rebuild_bars([_bar("2024-01-02", 0.2), _bar("2024-01-03", 0.1)],
                         [{"date": "2024-01-03", "amount": 0.2}])

    def test_blank_page_that_is_not_explicitly_empty_is_refused(self):
        with self.assertRaises(R1fError):
            choose_method({"dividends": [], "splits": [], "explicit_empty_dividend": False,
                           "explicit_empty_split": True}, [])


class Store(unittest.TestCase):
    def test_insert_refuses_to_overwrite_an_existing_kind(self):
        con = DB.connect(":memory:")
        _table(con)
        con.execute(
            """INSERT INTO v4_series
               (code, kind, date, close, filled, source, source_url, method, fetched_at)
               VALUES ('160125', 'backward', '2012-02-17', 1.1, 0, 'tencent_etf_hfq', 'u', 'tencent_hfq', 't')""")
        with self.assertRaises(R1fError):
            insert_series(con, "160125", KIND_BACKWARD, [_bar("2012-02-17", 1.2)], "u", METHOD_DIV, "t")
        close = con.execute(
            "SELECT close, source FROM v4_series WHERE code='160125' AND kind='backward'").fetchone()
        self.assertEqual(close[0], 1.1)
        self.assertEqual(close[1], "tencent_etf_hfq")
        con.close()

    def test_existing_backward_sends_the_rebuild_to_another_kind(self):
        con = DB.connect(":memory:")
        _table(con)
        con.execute(
            """INSERT INTO v4_series
               (code, kind, date, close, filled, source, source_url, method, fetched_at)
               VALUES ('159501', 'backward', '2024-01-02', 2.2, 0, 'eastmoney_fhsp', 'u', ?, 't')""",
            (METHOD_FLAT,))
        adjusted = [_bar("2024-01-02", 2.2)]
        kind, action = destination(con, "159501", adjusted, METHOD_FLAT)
        self.assertEqual((kind, action), (KIND_REBUILD, "insert"))
        insert_series(con, "159501", kind, adjusted, "https://fundf10.eastmoney.com/fhsp_159501.html",
                      METHOD_FLAT, "t")
        row = con.execute(
            "SELECT source, method, close FROM v4_series WHERE code='159501' AND kind=?",
            (KIND_REBUILD,)).fetchone()
        self.assertEqual(row[0], SOURCE)
        self.assertEqual(row[1], METHOD_FLAT)
        self.assertEqual(row[2], 2.2)
        old = con.execute(
            "SELECT source FROM v4_series WHERE code='159501' AND kind='backward'").fetchone()[0]
        self.assertEqual(old, "eastmoney_fhsp")
        con.close()

    def test_empty_backward_is_the_r1c_slot(self):
        con = DB.connect(":memory:")
        _table(con)
        adjusted = [_bar("2024-03-04", 1.5)]
        kind, action = destination(con, "513910", adjusted, METHOD_FLAT)
        self.assertEqual((kind, action), (KIND_BACKWARD, "insert"))
        con.close()


class Crosscheck(unittest.TestCase):
    def test_year_rows_list_the_difference_and_do_not_sum_a_total(self):
        hfq = [
            {"date": "2024-05-16", "close": 1.0},
            {"date": "2024-12-31", "close": 1.1},
            {"date": "2025-12-31", "close": 1.21},
        ]
        nav = [
            {"date": "2024-05-16", "accum_nav": 1.0, "source": "eastmoney_pingzhongdata"},
            {"date": "2024-12-31", "accum_nav": 1.2, "source": "eastmoney_pingzhongdata"},
            {"date": "2025-12-31", "accum_nav": 1.2, "source": "eastmoney_pingzhongdata"},
        ]
        rows = year_crosscheck("513820", hfq, nav)
        self.assertEqual([row["year"] for row in rows], ["2024", "2025"])
        self.assertEqual(rows[0]["hfq_growth"], "0.10000000")
        self.assertEqual(rows[0]["accum_growth"], "0.20000000")
        self.assertEqual(rows[0]["diff"], "-0.10000000")
        self.assertIn("当年内", rows[0]["note"])
        self.assertEqual(rows[1]["hfq_growth"], "0.10000000")
        self.assertEqual(rows[1]["accum_growth"], "0.00000000")
        self.assertEqual(rows[1]["diff"], "0.10000000")
        self.assertNotIn("当年内", rows[1]["note"])
        self.assertFalse(any("total" in row or "cagr" in row for row in rows))

    def test_task_codes_stay_in_two_groups(self):
        self.assertEqual(len(FLAT_CODES), 5)
        self.assertEqual(len(CASH_CODES), 3)
        self.assertEqual(set(FLAT_CODES) & set(CASH_CODES), set())
