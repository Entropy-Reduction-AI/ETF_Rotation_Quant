"""v4-R1 解析与写入边界。不出网，不连 data/market.sqlite。"""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import tests  # noqa: F401 — ETF_LEDGER_TESTING

from src.data import db as DB
from src.data import store
from src.v4.data.__main__ import main
from src.v4.data.ingest import IngestError, build_coverage, ensure, put_bars, run
from src.v4.data.parse import bar_sha256, parse_chinamoney, parse_yahoo_chart


def _yahoo():
    ts = int(datetime(2024, 9, 6, 16, 0, tzinfo=ZoneInfo("America/New_York")).timestamp())
    return {"chart": {"result": [{
        "meta": {"longName": "Example", "currency": "USD", "exchangeTimezoneName": "America/New_York"},
        "timestamp": [ts, ts + 86400],
        "indicators": {"quote": [{
            "open": [10.0, 11.0], "high": [12.0, 12.0], "low": [9.0, 10.0],
            "close": [11.0, None], "volume": [100, 100],
        }]},
        "events": {
            "dividends": {"a": {"amount": 0.25, "date": ts}},
            "splits": {"b": {"date": ts, "numerator": 2, "denominator": 1, "splitRatio": "2:1"}},
        },
    }]}}


class Parse(unittest.TestCase):
    def test_yahoo_keeps_raw_close_and_events(self):
        got = parse_yahoo_chart(_yahoo(), date(2024, 9, 1), date(2024, 9, 30))
        self.assertEqual([r["date"] for r in got["bars"]], ["2024-09-06"])
        self.assertEqual(got["bars"][0]["close"], 11.0)
        self.assertEqual(got["dividends"], [{"date": "2024-09-06", "amount": 0.25}])
        self.assertEqual(got["splits"][0]["ratio"], "2:1")
        self.assertEqual(got["currency"], "USD")

    def test_yahoo_clips_end(self):
        got = parse_yahoo_chart(_yahoo(), date(2024, 9, 1), date(2024, 9, 5))
        self.assertEqual(got["bars"], [])
        self.assertEqual(got["dividends"], [])

    def test_chinamoney_one_pair(self):
        payload = {"data": {"searchlist": ["HKD/CNY"]}, "records": [
            {"date": "2024-09-06", "values": ["0.91003"]},
            {"date": "2024-09-09", "values": ["0.9101"]},
        ]}
        rows = parse_chinamoney(payload, "HKD/CNY", date(2024, 9, 1), date(2024, 9, 6))
        self.assertEqual(rows, [{
            "date": "2024-09-06", "open": None, "high": None, "low": None,
            "close": 0.91003, "volume": None, "amount": None,
        }])

    def test_chinamoney_rejects_other_pair(self):
        with self.assertRaises(ValueError):
            parse_chinamoney({"data": {"searchlist": ["USD/CNY"]}, "records": []}, "HKD/CNY",
                             date(2024, 9, 1), date(2024, 9, 6))

    def test_bar_sha_is_stable(self):
        rows = [{"date": "2024-09-06", "open": None, "high": None, "low": None,
                 "close": 0.91003, "volume": None}]
        digest = hashlib.sha256(b"2024-09-06,,,,0.91003,\n").hexdigest()
        self.assertEqual(bar_sha256(rows), digest)


class WriteBoundary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "market.sqlite"
        self.con = DB.connect(self.path)
        ensure(self.con)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_refuses_sentinel_and_other_source(self):
        with self.assertRaises(IngestError):
            put_bars(self.con, "USDCNY", "chinamoney", [{"date": "2006-01-04", "close": 1}], "t")
        store.replace(self.con, "XLB", "yahoo", [{"date": "2024-09-06", "close": 90}], "t0")
        self.assertEqual(put_bars(self.con, "XLB", "yahoo", [{"date": "2024-09-06", "close": 1}], "t1"), "reused")
        close = self.con.execute("SELECT close FROM bars WHERE code='XLB'").fetchone()[0]
        self.assertEqual(close, 90)
        with self.assertRaises(IngestError):
            put_bars(self.con, "XLB", "stooq", [{"date": "2024-09-06", "close": 1}], "t2")

    def test_inserts_only_new_code(self):
        status = put_bars(self.con, "HKDCNY", "chinamoney",
                          [{"date": "2024-09-06", "close": 0.91}], "t")
        self.assertEqual(status, "inserted")
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM bars").fetchone()[0], 1)

    def test_missing_tr_stays_out_of_bars(self):
        rows = build_coverage(self.con)
        tr = next(r for r in rows if r["code"] == "SP500-45TR")
        hsci = next(r for r in rows if r["code"] == "HSCIE")
        self.assertEqual(tr["status"], "unavailable")
        self.assertEqual(tr["return_basis"], "total_return")
        self.assertEqual(tr["rows"], "0")
        self.assertEqual(hsci["official_launch"], "2006-09-11")
        self.assertEqual(hsci["base_date"], "2000-01-03")
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM bars").fetchone()[0], 0)

    def test_run_rejects_dates_after_ledger_end(self):
        with self.assertRaises(IngestError):
            run(self.con, date(2026, 10, 1))


class Cli(unittest.TestCase):
    def test_refuses_return_commands(self):
        self.assertEqual(main(["returns"]), 2)
        self.assertEqual(main(["backtest"]), 2)
        self.assertEqual(main([]), 2)
