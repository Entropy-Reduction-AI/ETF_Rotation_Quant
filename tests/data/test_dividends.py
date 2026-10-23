"""现金分红：由不复权与 qfq 的阶跃推导，只追加，取数失败不让行情更新失败。

一手公告替换另测：10 只可信基金逐行对齐，511880 三个除息日用价格日。
"""
import csv
import shutil
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import pandas as pd

from src.data import db as DB
from src.data import http
from src.data import runner
from src.data.dividends import (TRUSTED_FUNDS, announcement_rows, derive_cash_dividends, ensure,
                                load_dividends, replace_from_events, sync_qfq, verified_no_dividend_codes)
from src.data.sources import Fetched
from tests.marketdb import open_db, put, put_coverage

EVENTS = DB.ROOT / "incoming/grok-pit-20261022/etf_events.csv"
README = DB.ROOT / "incoming/grok-pit-20261022/README.md"


def _bar(day, close, open_=None):
    px = close if open_ is None else open_
    return {"date": day, "open": px, "high": px, "low": px, "close": close, "volume": 1.0, "amount": None}


class Derive(unittest.TestCase):
    def test_511260_step_is_the_cash_dividend(self):
        raw = [_bar("2026-09-17", 135.970), _bar("2026-09-18", 134.739)]
        qfq = [_bar("2026-09-17", 134.695), _bar("2026-09-18", 134.739)]
        got = derive_cash_dividends(raw, qfq)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["ex_date"], "2026-09-18")
        self.assertAlmostEqual(got[0]["amount"], 1.275)
        self.assertAlmostEqual(got[0]["prev_close"], 135.970)
        factor = got[0]["prev_close"] / (got[0]["prev_close"] - got[0]["amount"])
        self.assertAlmostEqual(134.739 * factor, 136.014, places=3)

    def test_noise_and_upward_steps_are_ignored(self):
        raw = [_bar("2026-09-17", 10.0), _bar("2026-09-18", 10.001)]
        qfq = [_bar("2026-09-17", 9.0), _bar("2026-09-18", 9.0004)]
        self.assertEqual(derive_cash_dividends(raw, qfq), [])


class Record(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.db = self.tmp / "market.sqlite"
        con = open_db(self.db)
        put(con, "511260", pd.DataFrame([_bar("2026-09-17", 135.970), _bar("2026-09-18", 134.739)]), "tencent_etf")
        put_coverage(con, [dict(theme_id="T33", container="国债", status="flagged", exec_code="511260", exec_route="tencent_etf")])
        con.close()

    def test_append_only_and_first_write_wins(self):
        body = ('{"code":0,"data":{"sh511260":{"qfqday":['
                '["2026-09-17","134.7","134.695","134.8","134.6","1"],'
                '["2026-09-18","134.7","134.739","134.8","134.6","1"]]}}}').encode()
        later = ('{"code":0,"data":{"sh511260":{"qfqday":['
                 '["2026-09-17","130","130","130","130","1"],'
                 '["2026-09-18","134.739","134.739","134.739","134.739","1"]]}}}').encode()
        def serve(payload):
            def fake_get(url, params=None, **kw):
                full = url + ("?" + "&".join(f"{k}={v}" for k, v in (params or {}).items()))
                http.LOG.append({"url": full, "fetched_at": "2026-09-18T08:00:00+00:00", "bytes": len(payload),
                                 "sha256": "a" * 64, "error": None, "file": "qfq.body"})
                return payload
            return fake_get

        con = DB.connect(self.db)
        try:
            with mock.patch("src.data.sources.time.sleep"):
                http.LOG.clear()
                with mock.patch.object(http, "get", side_effect=serve(body)):
                    sync_qfq(con, 7, {"511260": date(2026, 9, 1)}, date(2026, 9, 30), log=lambda *_: None)
                self.assertEqual(len(http.LOG), 1)
                self.assertIn("qfq", http.LOG[0]["url"])
                seq = 0
                http.LOG.clear()
                with mock.patch.object(http, "get", side_effect=serve(later)):
                    sync_qfq(con, 8, {"511260": date(2026, 9, 1)}, date(2026, 9, 30), log=lambda *_: None)
            row = con.execute("SELECT amount, prev_close, run_id, request_seq FROM cash_dividends").fetchone()
            self.assertEqual((row["amount"], row["prev_close"], row["run_id"], row["request_seq"]), (1.275, 135.970, 7, seq))
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("UPDATE cash_dividends SET amount = 9")
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("DELETE FROM cash_dividends")
        finally:
            con.close()
        loaded = load_dividends(self.db, ["511260"])
        self.assertEqual(loaded["511260"][0]["ex_date"], "2026-09-18")
        self.assertEqual(load_dividends(self.db, []), {})

    def test_qfq_failure_is_logged_and_writes_nothing(self):
        con = DB.connect(self.db)
        notes = []
        try:
            with mock.patch("src.data.dividends.fetch_tencent", side_effect=http.FetchError("qfq down")):
                sync_qfq(con, 1, {"511260": date(2026, 9, 1)}, date(2026, 9, 30), log=notes.append)
            ensure(con)
            self.assertEqual(con.execute("SELECT count(*) FROM cash_dividends").fetchone()[0], 0)
        finally:
            con.close()
        self.assertTrue(any("qfq down" in line for line in notes))

    def test_update_report_stays_ok_when_qfq_fails(self):
        row = {"theme_id": "T33", "execution_fund_code": "511260"}
        cov = {"exec_code": "511260", "exec_route": "tencent_etf", "theme_id": "T33"}
        fresh = Fetched([_bar("2026-09-17", 135.970), _bar("2026-09-18", 134.739)])

        def route_fn(route, code):
            return lambda b, e: fresh

        with mock.patch("src.data.runner.mvp_targets", return_value=[(row, cov, "exec", "511260", "raw")]), \
             mock.patch("src.data.universe.route_fn", side_effect=route_fn), \
             mock.patch("src.data.dividends.fetch_tencent", side_effect=http.FetchError("qfq down")), \
             mock.patch("src.data.sources.time.sleep"):
            report = runner.update(date(2026, 9, 30), db=self.db, scope="mvp",
                                   dividend_windows={"511260": date(2026, 9, 1)}, log=lambda *_: None)
        self.assertEqual(len(report), 1)
        self.assertTrue(report[0]["ok"])
        self.assertEqual(load_dividends(self.db, ["511260"]), {})


class ReplaceFromEvents(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.db = self.tmp / "market.sqlite"
        self.con = open_db(self.db)
        wanted, verified = announcement_rows(EVENTS, README)
        self.verified = verified
        codes = sorted({row["code"] for row in wanted} | {"513100", "513300"})
        for code in codes:
            put(self.con, code, pd.DataFrame([_bar("2000-01-04", 200.0)]), "tencent_etf")
        put_coverage(self.con, [
            dict(theme_id="T02", container="中证500", status="retained", exec_code="510500", notes="原备注"),
            dict(theme_id="T16", container="黄金", status="flagged", exec_code="518880"),
            dict(theme_id="T35", container="纳指", status="retained", exec_code="513100"),
        ])
        ensure(self.con)
        self.con.executemany(
            """INSERT INTO cash_dividends (code, ex_date, amount, prev_close, run_id, request_seq, recorded_at)
               VALUES (?, ?, ?, ?, 1, 0, '2026-10-22T00:00:00+00:00')""",
            [("513100", "2020-01-02", 0.01, 1.0, ),
             ("513300", "2021-01-04", 0.02, 1.0),
             ("511880", "2014-01-16", 3.208, 100.0),
             ("510330", "2018-11-08", 0.163, 2.0)])
        self.con.commit()

    def tearDown(self):
        self.con.close()

    def test_grok_rows_replace_qfq_noise(self):
        self.assertIn("513300", self.verified)
        self.assertNotIn("513100", self.verified)
        self.assertEqual(len(verified_no_dividend_codes(README.read_text(encoding="utf-8"))), 35)
        run_id = DB.start_run(self.con, "update", args={"job": "test"})
        removed = self.tmp / "removed.csv"
        detail = replace_from_events(self.con, run_id, EVENTS, README, removed)
        wanted, _ = announcement_rows(EVENTS, README)
        by_code = {}
        for row in wanted:
            by_code.setdefault(row["code"], []).append(row)
        for code in TRUSTED_FUNDS:
            got = list(self.con.execute(
                "SELECT ex_date, amount FROM cash_dividends WHERE code = ? ORDER BY ex_date", (code,)))
            expect = sorted(by_code[code], key=lambda item: item["ex_date"])
            self.assertEqual([row["ex_date"] for row in got], [row["ex_date"] for row in expect])
            for have, want in zip(got, expect):
                self.assertEqual(round(have["amount"], 4), round(want["amount"], 4))
        dates = [row[0] for row in self.con.execute(
            """SELECT ex_date FROM cash_dividends WHERE code = '511880'
                AND substr(ex_date, 1, 7) IN ('2014-01', '2014-12', '2015-12') ORDER BY ex_date""")]
        self.assertEqual(dates, ["2014-01-17", "2014-12-31", "2015-12-31"])
        amounts = {row["ex_date"]: row["amount"] for row in by_code["511880"]}
        for day in dates:
            stored = self.con.execute("SELECT amount FROM cash_dividends WHERE code = '511880' AND ex_date = ?", (day,)).fetchone()[0]
            self.assertEqual(round(stored, 4), round(amounts[day], 4))
        self.assertEqual(self.con.execute("SELECT count(*) FROM cash_dividends WHERE code IN ('513100', '513300')").fetchone()[0], 0)
        self.assertEqual(self.con.execute("SELECT count(*) FROM cash_dividends WHERE amount <= 0").fetchone()[0], 0)
        self.assertNotIn("518880", {row[0] for row in self.con.execute("SELECT DISTINCT code FROM cash_dividends")})
        notes = {row["theme_id"]: row["notes"] for row in DB.read_coverage(self.con)}
        self.assertEqual(notes["T35"], "分红未知: 159941,513100")
        self.assertNotIn("513300", notes["T35"])
        self.assertEqual(notes["T02"], "原备注 | 分红未知: 512500")
        self.assertEqual(notes["T16"], "分红未知: 159934,518800,518880")
        with removed.open(encoding="utf-8") as handle:
            exported = list(csv.DictReader(handle))
        exported_keys = {(row["code"], row["ex_date"]) for row in exported}
        self.assertIn(("513100", "2020-01-02"), exported_keys)
        self.assertIn(("513300", "2021-01-04"), exported_keys)
        self.assertIn(("511880", "2014-01-16"), exported_keys)
        self.assertIn(("510330", "2018-11-08"), exported_keys)
        self.assertEqual(detail["deleted"], 4)
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("DELETE FROM cash_dividends")
        again = self.tmp / "removed-again.csv"
        second = replace_from_events(self.con, run_id, EVENTS, README, again)
        self.assertEqual(second["deleted"], 0)
        self.assertEqual(second["inserted"], 0)
        with again.open(encoding="utf-8") as handle:
            self.assertEqual(list(csv.DictReader(handle)), [])
