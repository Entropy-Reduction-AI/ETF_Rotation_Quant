"""搜狐成交额：hq[8] 按万元换算，不改价格；同一来源连续失败两次即停。"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from src.data import http
from src.data import sohu_amount
from src.data import store
from tests.marketdb import open_db, put


def _bar(day, close, amount=None):
    return {"date": day, "open": close, "high": close, "low": close, "close": close, "volume": 10.0, "amount": amount}


class Parse(unittest.TestCase):
    def test_hq8_is_wan_yuan_and_first_date_wins(self):
        payload = [{"status": 0, "code": "cn_510300", "hq": [
            ["2026-09-30", "4", "4.1", "0", "0%", "4", "4.2", "100", "1.5", "1%"],
            ["2026-09-30", "4", "4.1", "0", "0%", "4", "4.2", "100", "9.9", "1%"],
            ["2026-09-29", "4", "4"],
        ]}]
        got = sohu_amount.parse_sohu(payload, "510300")
        self.assertEqual(got, {"2026-09-30": 15000.0})

    def test_bad_status_is_a_failure(self):
        with self.assertRaises(http.FetchError):
            sohu_amount.parse_sohu([{"status": 2, "code": "cn_510300", "hq": []}], "510300")


class Apply(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.db = self.tmp / "market.sqlite"
        self.con = open_db(self.db)
        put(self.con, "510300", pd.DataFrame([_bar("2026-09-30", 4.432)]), "tencent_etf")

    def tearDown(self):
        self.con.close()

    def test_amount_fills_without_touching_price_or_source(self):
        detail = sohu_amount.apply_amounts(self.con, "510300", {"2026-09-30": 15000.0, "2026-09-29": 1.0})
        row = self.con.execute(
            "SELECT open, high, low, close, volume, amount, source, fetched_at FROM bars WHERE code = '510300'").fetchone()
        self.assertEqual(detail["updated"], 1)
        self.assertEqual(row["close"], 4.432)
        self.assertEqual(row["open"], 4.432)
        self.assertEqual(row["amount"], 15000.0)
        self.assertEqual(row["source"], "tencent_etf")
        self.assertEqual(row["fetched_at"], "test")
        self.assertEqual(self.con.execute("SELECT count(*) FROM bars").fetchone()[0], 1)

    def test_upsert_keeps_existing_amount_when_tencent_has_none(self):
        sohu_amount.apply_amounts(self.con, "510300", {"2026-09-30": 15000.0})
        store.upsert(self.con, "510300", "tencent_etf", [_bar("2026-09-30", 4.5)], "2026-10-23T00:00:00+00:00")
        row = self.con.execute("SELECT close, amount, source, fetched_at FROM bars WHERE code = '510300'").fetchone()
        self.assertEqual(row["close"], 4.5)
        self.assertEqual(row["amount"], 15000.0)
        self.assertEqual(row["source"], "tencent_etf")
        self.assertEqual(row["fetched_at"], "2026-10-23T00:00:00+00:00")
        store.upsert(self.con, "510300", "tencent_etf", [_bar("2026-09-30", 4.5, amount=42)], "2026-10-23T01:00:00+00:00")
        self.assertEqual(self.con.execute("SELECT amount FROM bars").fetchone()[0], 42.0)


class Stop(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.db = self.tmp / "market.sqlite"
        con = open_db(self.db)
        for code in ("510300", "510500", "512100", "159915"):
            put(con, code, pd.DataFrame([_bar("2026-09-30", 1.0)]), "tencent_etf")
        con.close()

    def test_two_consecutive_failures_stop_the_rest(self):
        calls = []

        def fake(url, params=None, **kwargs):
            calls.append(params["code"])
            raise http.FetchError("down")

        with mock.patch("src.data.sohu_amount.time.sleep"), mock.patch("src.data.sohu_amount.http.get", side_effect=fake):
            report = sohu_amount.fill(self.db, codes=["510300", "510500", "512100"], apply=True, pause=0, log=lambda *_: None)
        self.assertEqual(calls, ["cn_510300", "cn_510500"])
        self.assertIn("连续失败两次", report["stopped"])
        self.assertEqual(report["updated_rows"], 0)

    def test_a_success_resets_the_streak(self):
        calls = []

        def fake(url, params=None, **kwargs):
            code = params["code"]
            calls.append(code)
            if code in ("cn_510300", "cn_512100"):
                raise http.FetchError("down")
            body = [{"status": 0, "code": code, "hq": [["2026-09-30", "1", "1", "0", "0%", "1", "1", "8", "1.25", "0%"]]}]
            return json.dumps(body).encode("gbk")

        with mock.patch("src.data.sohu_amount.time.sleep"), mock.patch("src.data.sohu_amount.http.get", side_effect=fake):
            report = sohu_amount.fill(self.db, codes=["510300", "510500", "512100", "159915"], apply=True, pause=0,
                                      log=lambda *_: None)
        self.assertEqual(calls, ["cn_510300", "cn_510500", "cn_512100", "cn_159915"])
        self.assertIsNone(report["stopped"])
        self.assertEqual(report["updated_rows"], 2)
        con = open_db(self.db)
        try:
            row = con.execute("SELECT close, amount FROM bars WHERE code = '510500'").fetchone()
            self.assertEqual(row["close"], 1.0)
            self.assertEqual(row["amount"], 12500.0)
        finally:
            con.close()
