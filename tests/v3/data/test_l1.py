"""v3 L1 解析、登记表和写入规则。不出网，不连默认库。"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.v3.data import emit_universe

from src.v3.data import coverage
from src.v3.data import parse
from src.v3.data import store
from src.v3.data import universe as U
from tests.marketdb import open_db


SGE_HTML = """
<table><tr><td>2024-06-06</td><td>Au99.99</td><td>550.80</td><td>561.00</td><td>550.80</td>
<td>559.36</td><td>1</td><td>0.2%</td><td>555</td><td>10</td><td>1000</td></tr>
<tr><td>2024-06-06</td><td>Au9999</td><td>1</td><td>2</td><td>1</td><td>1.5</td><td>0</td><td>0</td><td>1</td><td>1</td><td>2</td></tr>
<tr><td>2024-06-06</td><td>Au99.95</td><td>1</td><td>1</td><td>1</td><td>1</td><td>0</td><td>0</td><td>1</td><td>1</td><td>2</td></tr>
</table>
"""


class UniverseFile(unittest.TestCase):
    def test_static_containers_have_fields(self):
        errors = U.validate()
        self.assertEqual(errors, [])
        ids = [row["id"] for row in U.containers()]
        for required in (
            "csi300", "csi500", "csi1000", "chinext", "star50",
            "allshare-energy", "allshare-materials", "allshare-industrials",
            "allshare-discretionary", "allshare-staples", "allshare-healthcare",
            "allshare-financials-re", "allshare-it", "allshare-communication",
            "allshare-utilities", "csi-dividend", "hsi", "hstech", "ndx100", "spx",
            "gold", "soymeal", "crude-oil", "cgb-10y", "cgb-5y", "cash",
        ):
            self.assertIn(required, ids)

    def test_patch_one_status(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        path = tmp / "universe.toml"
        path.write_text(
            '[[container]]\nid = "gold"\n\n[container.research]\nseries_status = "TBD"\n\n'
            '[[container]]\nid = "allshare-energy"\n\n[container.research]\nseries_status = "TBD"\n',
            encoding="utf-8")
        U.patch_field("gold", "series_status", "partial", path=path)
        text = path.read_text(encoding="utf-8")
        gold = text.split('id = "gold"', 1)[1].split("[[container]]", 1)[0]
        energy = text.split('id = "allshare-energy"', 1)[1]
        self.assertIn('series_status = "partial"', gold)
        self.assertIn('series_status = "TBD"', energy)


class Emit(unittest.TestCase):
    def test_code_comes_from_identity_file(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        (tmp / "H00986.json").write_text(json.dumps({"data": {
            "indexCode": "H00986", "indexFullNameCn": "中证全指能源全收益指数",
            "publishDate": "2011-08-02", "basicDate": "2004-12-31",
        }}), encoding="utf-8")
        got = emit_universe.load_csi(tmp)
        self.assertEqual(got["中证全指能源全收益指数"]["code"], "H00986")
        self.assertEqual(got["中证全指能源全收益指数"]["publish_date"], "2011-08-02")


class Parse(unittest.TestCase):
    def test_sge_keeps_au9999_apart_from_au99_99(self):
        rows = parse.parse_sge_daily(SGE_HTML)
        self.assertEqual(sorted(r["contract"] for r in rows), ["Au99.99", "Au9999"])
        au = next(r for r in rows if r["contract"] == "Au99.99")
        self.assertEqual(au["close"], 559.36)
        self.assertEqual(au["amount"], 1000)

    def test_track_classification(self):
        self.assertEqual(parse.classify_track("恒生科技指数"), "single_index")
        self.assertEqual(parse.classify_track("该基金无跟踪标的"), "not_single_index")
        self.assertEqual(parse.classify_track("纳指*80%+恒生科技*10%"), "not_single_index")

    def test_exchange_code(self):
        self.assertTrue(parse.exchange_code("513100"))
        self.assertTrue(parse.exchange_code("159920"))
        self.assertTrue(parse.exchange_code("161129"))
        self.assertFalse(parse.exchange_code("000041"))
        self.assertFalse(parse.exchange_code("519601"))

    def test_appendix1_excludes_multi_asset_and_commodity(self):
        self.assertEqual(parse.appendix1_decision("纳指ETF", "指数型-海外股票", "纳斯达克100指数"), "include")
        self.assertEqual(
            parse.appendix1_decision("原油", "QDII-商品", "该基金无跟踪标的"),
            "exclude:跨境商品，归入商品大类",
        )
        self.assertNotEqual(parse.appendix1_decision("配置", "QDII-混合灵活", "纳指*80%+恒生*10%"), "include")

    def test_catalog_keeps_exchange_qdii_only(self):
        text = '''var r = [["000041","X","华夏全球(QDII)","QDII-普通股票","A"],["513100","Y","纳指ETF","指数型-海外股票","B"],["000071","Z","华夏恒生ETF联接A","指数型-海外股票","C"],["510300","W","沪深300ETF","指数型-股票","D"]];'''
        got = parse.on_exchange_qdii(parse.parse_fund_catalog(text))
        self.assertEqual([row["code"] for row in got], ["513100"])

    def test_rank_line(self):
        text = 'var rankData = {datas:["000041,华夏全球,PY,2026-10-22"],allRecords:1};'
        self.assertEqual(parse.parse_qdii_rank(text), [{"code": "000041", "name": "华夏全球"}])

    def test_jbgk_does_not_invent_list_date(self):
        html = "<td>跟踪标的</td><td>中证红利指数</td><td>成立日期/规模</td><td>2019年11月26日</td>"
        got = parse.parse_jbgk(html)
        self.assertEqual(got["track"], "中证红利指数")
        self.assertEqual(got["setup_date"], "2019-11-26")
        self.assertEqual(got["list_date"], "")


class WriteSeries(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.con = open_db(self.tmp / "market.sqlite")
        self.addCleanup(self.con.close)

    def test_does_not_stitch_another_source(self):
        store.write_series(self.con, "HSI", "tencent_hk_index", [
            {"date": "2020-07-27", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "amount": None},
        ], "t")
        again = store.write_series(self.con, "HSI", "yahoo", [
            {"date": "2020-07-28", "open": 2, "high": 2, "low": 2, "close": 2, "volume": 1, "amount": None},
        ], "t")
        self.assertEqual(again["status"], "skipped_other_source")
        self.assertEqual(self.con.execute("SELECT count(*) FROM bars WHERE code = 'HSI'").fetchone()[0], 1)

    def test_appends_missing_dates_only(self):
        row = {"date": "2024-06-06", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "amount": 3}
        store.write_series(self.con, "Au99.99", "sge_daily", [row], "t")
        extra = dict(row, date="2024-06-07", close=2)
        result = store.write_series(self.con, "Au99.99", "sge_daily", [row, extra], "t2")
        self.assertEqual(result["status"], "appended")
        closes = list(self.con.execute("SELECT date, close FROM bars WHERE code = 'Au99.99' ORDER BY date"))
        self.assertEqual([tuple(r) for r in closes], [("2024-06-06", 1), ("2024-06-07", 2)])

    def test_coverage_marks_gap_without_prices(self):
        doc = {"container": [{
            "id": "crude-oil", "asset_class": "商品", "name": "原油",
            "research": {
                "index_code": "TBD", "return_basis": "excess_return", "publish_date": "TBD",
                "base_date": "TBD", "series_code": "", "series_status": "取不到", "source_url": "", "note": "",
            },
            "execution": [],
        }]}
        rows = coverage.build_rows(self.con, doc)
        self.assertEqual(rows[0]["missing_flag"], "gap")
        self.assertEqual(rows[0]["rows"], 0)
