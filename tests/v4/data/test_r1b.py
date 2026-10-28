"""v4-R1b 后复权、场外解析、汇率补齐、0 收盘。不出网。"""
from __future__ import annotations

import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

import tests  # noqa: F401 — ETF_LEDGER_TESTING

from src.data import db as DB
from src.data import store
from src.v4.data.adjust import (
    backward_total_return, cny_per_hkd, compound_adjusted_nav, fill_backward,
    ms_to_date, safe_quote_to_cny, split_already_in_close,
)
from src.v4.data.r1b import _LISTING, _SERIES, _audit_one, null_zero_closes
from src.v4.data.r1b_parse import (
    parse_jbgk, parse_pingzhongdata, parse_rank_index_funds, parse_safe_mid, parse_tencent_kline_rows,
)


def _bar(day, close, open_=None):
    return {"date": day, "open": close if open_ is None else open_, "high": close,
            "low": close, "close": close, "volume": 1}


class Adjust(unittest.TestCase):
    def test_split_not_in_price_is_undone(self):
        bars = [_bar("2024-01-02", 10), _bar("2024-01-03", 5)]
        out = backward_total_return(bars, [], [{"date": "2024-01-03", "numerator": 2, "denominator": 1}],
                                    splits_in_price=False)
        self.assertAlmostEqual(out[1]["close"], 10.0)
        self.assertEqual(bars[1]["close"], 5)

    def test_split_already_in_price_is_not_applied_again(self):
        bars = [_bar("2024-01-02", 10), _bar("2024-01-03", 10)]
        out = backward_total_return(
            bars, [], [{"date": "2024-01-03", "numerator": 2, "denominator": 1}], splits_in_price=True)
        self.assertAlmostEqual(out[1]["close"], 10.0)

    def test_dividend_is_reinvested(self):
        bars = [_bar("2024-01-02", 10), _bar("2024-01-03", 10)]
        out = backward_total_return(bars, [{"date": "2024-01-03", "amount": 0.5}], [], splits_in_price=True)
        self.assertAlmostEqual(out[1]["close"], 10.5)

    def test_detector_matches_yahoo_style_and_raw_split(self):
        self.assertTrue(split_already_in_close(44.235, 44.09, 2, 1))
        self.assertFalse(split_already_in_close(20, 10, 2, 1))
        self.assertTrue(split_already_in_close(19.1876525878906, 19.3099994659424, 1231, 1000))

    def test_fill_uses_mean_of_next_twenty_and_marks_days(self):
        known = [(f"2006-01-{day:02d}", 8.0 + day / 100) for day in range(4, 24)]
        out = fill_backward(known, ["2005-12-30"], 20)
        filled = [row for row in out if row["filled"] == 1]
        self.assertEqual([row["date"] for row in filled], ["2005-12-30"])
        self.assertAlmostEqual(filled[0]["close"], sum(close for _, close in known) / 20)
        self.assertTrue(all(row["filled"] == 0 for row in out if row["date"] >= "2006-01-04"))

    def test_hkd_cross_and_safe_scale(self):
        self.assertAlmostEqual(cny_per_hkd(8.2765, 7.80), 8.2765 / 7.80)
        self.assertAlmostEqual(safe_quote_to_cny(807.02), 8.0702)
        self.assertAlmostEqual(safe_quote_to_cny(104.08), 1.0408)

    def test_nav_timestamp_is_beijing_date(self):
        self.assertEqual(ms_to_date(1125244800000), "2005-08-29")

    def test_adjusted_nav_compounds_published_return(self):
        points = [
            {"date": "2024-01-02", "unit_nav": 1.0, "accum_nav": 1.0, "equity_return": 0, "dividend": 0},
            {"date": "2024-01-03", "unit_nav": 0.99, "accum_nav": 1.04, "equity_return": 4.0, "dividend": 0.05},
        ]
        out = compound_adjusted_nav(points)
        self.assertAlmostEqual(out[1]["close"], 1.04)


class Parse(unittest.TestCase):
    def test_rank_keeps_early_index_funds_and_ignores_fees(self):
        text = ('var rankData = {datas:['
                '"050002,博时沪深300指数A,X,2026-10-27,1,2,0,0,0,0,0,0,0,0,0,1,2003-08-26,1,1,1.50%,0.15%",'
                '"160119,南方中证500,X,2026-10-27,1,2,0,0,0,0,0,0,0,0,0,1,2012-01-01,1,1,1.50%,0.15%"'
                '],allRecords:2}')
        rows = parse_rank_index_funds(text, "2011-12-31")
        self.assertEqual(rows, [{"code": "050002", "name": "博时沪深300指数A", "inception": "2003-08-26"}])
        self.assertNotIn("1.50%", rows[0].values())

    def test_jbgk_reads_tracked_index_not_fees(self):
        html = ("<tr><th>基金全称</th><td>博时沪深300指数证券投资基金</td></tr>"
                "<tr><th>成立日期/规模</th><td>2003年08月26日 / 51亿份</td></tr>"
                "<tr><th>跟踪标的</th><td>沪深300指数</td></tr>"
                "<tr><th>管理费率</th><td>0.50%</td></tr>")
        got = parse_jbgk(html)
        self.assertEqual(got["tracked_index"], "沪深300指数")
        self.assertEqual(got["inception"], "2003-08-26")
        self.assertNotIn("费率", got)

    def test_pingzhong_compounds_until_end(self):
        text = (
            'var Data_netWorthTrend = ['
            '{"x":1125244800000,"y":1.0,"equityReturn":0,"unitMoney":""},'
            '{"x":1125590400000,"y":1.01,"equityReturn":1.0,"unitMoney":""}'
            '];'
            'var Data_ACWorthTrend = [[1125244800000,1.0],[1125590400000,1.01]];'
        )
        # 1125590400000 ms is 2005-09-02 00:00 +08.
        points = parse_pingzhongdata(text, date(2005, 8, 29))
        self.assertEqual([p["date"] for p in points], ["2005-08-29"])

    def test_tencent_hfq_row_uses_close_not_the_second_price_as_high(self):
        rows = parse_tencent_kline_rows([["2024-01-02", "1.522", "1.504", "1.522", "1.503", "10"]])
        self.assertEqual(rows[0]["close"], 1.504)
        self.assertEqual(rows[0]["open"], 1.522)
        self.assertEqual(rows[0]["low"], 1.503)

    def test_safe_sheet_reads_usd_and_hkd(self):
        path = Path(tempfile.mkdtemp()) / "mid.xlsx"
        _xlsx(path, [("日期", "美元", "欧元", "日元", "港元"), ("2005-01-04", "827.65", "0", "0", "106.41")])
        rows = parse_safe_mid(path)
        self.assertEqual(rows, [{"date": "2005-01-04", "usd_per_hundred": 827.65, "hkd_per_hundred": 106.41}])


class Quality(unittest.TestCase):
    def test_zero_close_becomes_null_and_other_rows_stay(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        con = DB.connect(Path(tmp.name) / "market.sqlite")
        self.addCleanup(con.close)
        store.replace(con, "H20184", "csi", [
            {"date": "2013-06-27", "close": 1547.19},
            {"date": "2013-06-28", "open": None, "close": 0, "volume": 10},
        ], "t0")
        store.replace(con, "510300", "tencent_etf", [{"date": "2013-06-28", "close": 2.2}], "t0")
        notes = null_zero_closes(con, ("H20184",), "2013-06-28")
        self.assertIn("0 -> null", notes[0])
        close = con.execute("SELECT close FROM bars WHERE code='H20184' AND date='2013-06-28'").fetchone()[0]
        self.assertIsNone(close)
        kept = con.execute("SELECT close FROM bars WHERE code='H20184' AND date='2013-06-27'").fetchone()[0]
        self.assertEqual(kept, 1547.19)
        other = con.execute("SELECT close FROM bars WHERE code='510300'").fetchone()[0]
        self.assertEqual(other, 2.2)
        with self.assertRaises(Exception):
            null_zero_closes(con, ("510300",), "2013-06-28")

    def test_schema_has_no_fee_columns(self):
        self.assertNotIn("fee", _SERIES.lower())
        self.assertNotIn("赎回", _LISTING)
        self.assertNotIn("申购", _LISTING)

    def test_audit_flags_small_split_and_real_gap(self):
        raw = [
            _bar("2020-01-02", 10),
            _bar("2020-01-03", 10),
            _bar("2020-01-06", 8, open_=8),
        ]
        hfq = [_bar("2020-01-02", 10), _bar("2020-01-03", 10), _bar("2020-01-06", 10.1)]
        flagged, counts = _audit_one(raw, hfq, [])
        self.assertEqual(counts["missed_action"], 1)
        self.assertEqual(flagged[0]["kind"], "missed_action")
        crash = [
            _bar("2020-01-02", 10),
            _bar("2020-01-03", 5, open_=5),
        ]
        hfq_crash = [_bar("2020-01-02", 10), _bar("2020-01-03", 5)]
        flagged, counts = _audit_one(crash, hfq_crash, [])
        self.assertEqual(counts["gap_removed_real"], 1)
        flat = [_bar("2020-01-02", 10), _bar("2020-01-03", 10)]
        flagged, counts = _audit_one(crash, flat, [])
        self.assertEqual(counts["gap_matches_action"], 1)


def _xlsx(path: Path, table: list[tuple]) -> None:
    strings = []
    index = {}

    def sid(value: str) -> int:
        if value not in index:
            index[value] = len(strings)
            strings.append(value)
        return index[value]

    rows_xml = []
    for r, record in enumerate(table, 1):
        cells = []
        for c, value in enumerate(record):
            ref = f"{chr(ord('A') + c)}{r}"
            if r == 1 or c == 0:
                cells.append(f'<c r="{ref}" t="s"><v>{sid(str(value))}</v></c>')
            else:
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
        rows_xml.append(f'<row r="{r}">{"".join(cells)}</row>')
    shared = "".join(f"<si><t>{escape(text)}</t></si>" for text in strings)
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    sheet = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<worksheet xmlns="{ns}"><sheetData>{"".join(rows_xml)}</sheetData></worksheet>'
    )
    shared_xml = f'<?xml version="1.0" encoding="UTF-8"?><sst xmlns="{ns}">{shared}</sst>'
    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet0" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" '
        'Target="sharedStrings.xml"/></Relationships>'
    )
    root = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        '</Types>'
    )
    with zipfile.ZipFile(path, "w") as book:
        book.writestr("[Content_Types].xml", content)
        book.writestr("_rels/.rels", root)
        book.writestr("xl/workbook.xml", workbook)
        book.writestr("xl/_rels/workbook.xml.rels", rels)
        book.writestr("xl/sharedStrings.xml", shared_xml)
        book.writestr("xl/worksheets/sheet1.xml", sheet)


if __name__ == "__main__":
    unittest.main()
