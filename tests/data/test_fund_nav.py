"""fund_nav：东财 lsjz 分页、同日去重、不插值。不出网。"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.data import fund_nav
from src.data import universe as U
from tests.marketdb import open_db


def _item(day, nav, acc="2", subscribe="开放申购", redeem="开放赎回"):
    return {"FSRQ": day, "DWJZ": nav, "LJJZ": acc, "SGZT": subscribe, "SHZT": redeem}


class Universe(unittest.TestCase):
    def test_required_codes_sit_inside_qdii_lof(self):
        codes = fund_nav.nav_codes()
        for code in fund_nav.REQUIRED:
            self.assertIn(code, codes)
        self.assertEqual(codes, U.qdii_lof_codes())
        self.assertIn("501018", codes)
        self.assertNotIn("510300", codes)


class Pagination(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.db = self.tmp / "market.sqlite"
        self.calls = []

    def test_pages_dedupe_and_keep_first(self):
        page1 = [_item(f"2024-01-{day:02d}", f"{day}.0000", subscribe="暂停申购", redeem="场内卖出") for day in range(1, 21)]
        page2 = [
            _item("2024-01-20", "99.0000", subscribe="后来的"),
            _item("2024-01-21", "", acc="", subscribe="限额申购", redeem="暂停赎回"),
            _item("2024-01-22", "1.2000"),
            _item("2024-01-23", "1.3000"),
            _item("2024-01-24", "1.4000"),
        ]

        def fake(url, params=None, **kwargs):
            self.calls.append((url, dict(params or {}), dict(kwargs.get("headers") or {})))
            page = params["pageIndex"]
            rows = page1 if page == 1 else page2
            return {"ErrCode": 0, "TotalCount": 24, "Data": {"LSJZList": rows}}

        with mock.patch("src.data.fund_nav.time.sleep") as slept, mock.patch("src.data.fund_nav.http.get_json", side_effect=fake):
            rows = fund_nav.fetch_code("513100", pause=0)
        self.assertEqual(slept.call_count, 1)
        self.assertEqual([call[1]["pageIndex"] for call in self.calls], [1, 2])
        self.assertTrue(all(call[1]["pageSize"] == 20 for call in self.calls))
        self.assertTrue(all(call[2]["Referer"] == fund_nav.REFERER for call in self.calls))
        self.assertEqual(len(rows), 24)
        kept = {row["date"]: row for row in rows}
        self.assertEqual(kept["2024-01-20"]["unit_nav"], 20.0)
        self.assertEqual(kept["2024-01-20"]["subscribe_status"], "暂停申购")
        self.assertIsNone(kept["2024-01-21"]["unit_nav"])
        self.assertEqual(kept["2024-01-21"]["subscribe_status"], "限额申购")
        self.assertEqual(rows[0]["date"], "2024-01-01")
        self.assertEqual(rows[-1]["source"], fund_nav.SOURCE)

        con = open_db(self.db)
        try:
            fund_nav.store_code(con, 3, rows, "2026-10-23T00:00:00+00:00")
            fund_nav.store_code(con, 3, rows, "2026-10-23T00:00:00+00:00")
            self.assertEqual(con.execute("SELECT count(*) FROM fund_nav").fetchone()[0], 24)
            self.assertEqual(tuple(con.execute(
                "SELECT unit_nav, subscribe_status, redeem_status FROM fund_nav WHERE date = '2024-01-20'").fetchone()),
                (20.0, "暂停申购", "场内卖出"))
            blank = con.execute("SELECT unit_nav, accum_nav FROM fund_nav WHERE date = '2024-01-21'").fetchone()
            self.assertIsNone(blank[0])
            self.assertIsNone(blank[1])
        finally:
            con.close()

    def test_store_missing_keeps_existing_rows(self):
        con = open_db(self.db)
        try:
            fund_nav.store_code(con, 1, [{
                "code": "160717", "date": "2021-01-04", "unit_nav": 0.8097, "accum_nav": 0.8097,
                "subscribe_status": "开放申购", "redeem_status": "开放赎回", "source": fund_nav.SOURCE,
            }], "2026-10-24T00:00:00+00:00")
            incoming = [
                {"code": "160717", "date": "2021-01-04", "unit_nav": 9.9, "accum_nav": 9.9},
                {"code": "160717", "date": "2010-09-30", "unit_nav": 1.0, "accum_nav": 1.0},
            ]
            blocked = fund_nav.store_missing(con, 2, incoming, "2026-10-28T00:00:00+00:00")
            self.assertEqual(blocked["inserted"], 0)
            self.assertEqual(blocked["conflicts"], ["2021-01-04"])
            self.assertEqual(tuple(con.execute(
                "SELECT unit_nav, source FROM fund_nav WHERE date='2021-01-04'").fetchone()),
                (0.8097, fund_nav.SOURCE))
            matched = [
                {"code": "160717", "date": "2021-01-04", "unit_nav": 0.8097, "accum_nav": 0.8097},
                {"code": "160717", "date": "2010-09-30", "unit_nav": 1.0, "accum_nav": 1.0},
                {"code": "160717", "date": "2026-10-01", "unit_nav": 0.5, "accum_nav": 0.5},
            ]
            wrote = fund_nav.store_missing(con, 3, matched, "2026-10-28T00:00:00+00:00")
            self.assertEqual(wrote["inserted"], 1)
            self.assertEqual(wrote["first"], "2010-09-30")
            self.assertIsNone(con.execute("SELECT 1 FROM fund_nav WHERE date='2026-10-01'").fetchone())
            kept = tuple(con.execute(
                "SELECT unit_nav, source FROM fund_nav WHERE date='2021-01-04'").fetchone())
            self.assertEqual(kept, (0.8097, fund_nav.SOURCE))
            added = tuple(con.execute(
                "SELECT unit_nav, source FROM fund_nav WHERE date='2010-09-30'").fetchone())
            self.assertEqual(added[0], 1.0)
            self.assertEqual(added[1], "eastmoney_pingzhongdata")
        finally:
            con.close()
