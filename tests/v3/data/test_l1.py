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


def _shell(cid: str, codes: list[str] | None = None) -> dict:
    return {
        "id": cid, "asset_class": "港股", "name": cid, "arm": "main",
        "in_pool_index": True, "in_pool_tradable": True,
        "research": {"note": "原注记。"},
        "execution": [{"code": code, "list_date": "取不到", "track": ""} for code in (codes or [])],
    }


def _etf(code: str, track: str, listed: str, nav_rows: int = 3) -> dict:
    return {
        "code": code, "name": code, "list_date": listed, "list_date_source": "src",
        "bars_status": "in_db", "track": track, "track_source": "jbgk",
        "note": "附录 1 纳入。", "nav_rows": nav_rows,
    }


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

    def test_same_index_merges_and_keeps_the_prereg_example_first(self):
        containers = [
            _shell("hsi", ["159920"]),
            _shell("hstech"),
            _shell("ndx100", ["513100", "159941"]),
            _shell("spx"),
        ]
        included = [
            _etf("164705", "恒生指数", "2015-04-13"),
            _etf("159920", "恒生指数", "2012-10-22"),
            _etf("159501", "纳斯达克100指数", "2023-06-14"),
            _etf("513870", "纳斯达克100指数", "取不到"),
            _etf("159660", "纳斯达克100指数", "2023-04-17"),
            _etf("159509", "纳斯达克科技市值加权指数", "2023-08-08", nav_rows=9),
            _etf("513290", "纳斯达克生物科技指数", "取不到"),
            _etf("159605", "中证海外中国互联网30人民币指数", "2021-12-02"),
            _etf("159607", "中证海外中国互联网30人民币指数", "2021-12-02"),
        ]
        themes = emit_universe.attach_qdii(containers, included)
        by_id = {row["id"]: row for row in containers}
        self.assertEqual([ex["code"] for ex in by_id["hsi"]["execution"]], ["159920", "164705"])
        self.assertEqual(
            [ex["code"] for ex in by_id["ndx100"]["execution"]],
            ["513100", "159941", "159660", "159501", "513870"],
        )
        self.assertNotIn("纳斯达克生物科技指数", by_id["ndx100"]["research"]["note"])
        ids = [row["id"] for row in themes]
        self.assertEqual(ids, [
            "theme-中证海外中国互联网30人民币指数",
            "theme-纳斯达克生物科技指数",
            "theme-纳斯达克科技市值加权指数",
        ])
        nasdaq = next(row for row in themes if row["id"] == "theme-纳斯达克科技市值加权指数")
        self.assertEqual(nasdaq["research"]["series_code"], "159509")
        self.assertEqual(nasdaq["research"]["publish_date"], "2023-08-08")
        self.assertEqual(nasdaq["research"]["series_status"], "in_db")
        internet = next(row for row in themes if "互联网30" in row["id"])
        self.assertEqual([ex["code"] for ex in internet["execution"]], ["159605", "159607"])
        self.assertEqual(internet["asset_class"], "美股和全球主题")
        held = {}
        for row in containers + themes:
            for ex in row["execution"]:
                self.assertNotIn(ex["code"], held)
                held[ex["code"]] = row["id"]

    def test_refuses_to_put_one_code_on_two_main_containers(self):
        containers = [
            _shell("hsi"), _shell("hstech"), _shell("ndx100"),
            _shell("spx", ["513500"]),
        ]
        with self.assertRaises(RuntimeError):
            emit_universe.attach_qdii(containers, [_etf("513500", "恒生指数", "2013-01-01")])

    def test_static_file_is_one_index_per_container(self):
        errors = U.validate()
        self.assertEqual(errors, [])
        rows = U.containers()
        by_id = {row["id"]: row for row in rows}

        def codes(cid: str) -> list[str]:
            return [ex["code"] for ex in by_id[cid]["execution"]]

        self.assertIn("159660", codes("ndx100"))
        self.assertIn("160213", codes("ndx100"))
        self.assertIn("513870", codes("ndx100"))
        self.assertEqual(codes("ndx100")[:3], ["513100", "159941", "513300"])
        self.assertIn("164705", codes("hsi"))
        self.assertIn("159920", codes("hsi"))
        for code in ("513130", "159741", "158042", "513260"):
            self.assertIn(code, codes("hstech"))
        for code in ("159655", "161125"):
            self.assertIn(code, codes("spx"))
        self.assertEqual(by_id["ndx100"]["research"]["series_code"], "XNDX")
        self.assertEqual(by_id["hsi"]["asset_class"], "港股")
        self.assertEqual(by_id["hstech"]["asset_class"], "港股")
        self.assertNotIn("qdii-159741", by_id)
        self.assertNotIn("qdii-164705", by_id)
        self.assertNotIn("qdii-513100", by_id)
        holders = [
            row["id"] for row in rows
            if any(ex["code"] == "159509" for ex in row.get("execution") or [])
        ]
        self.assertEqual(holders, ["theme-纳斯达克科技市值加权指数"])
        self.assertNotIn("513290", codes("ndx100"))
        self.assertIn("theme-纳斯达克生物科技指数", by_id)
        seen: dict[str, str] = {}
        for row in rows:
            if row.get("arm") != "main":
                continue
            for ex in row.get("execution") or []:
                self.assertNotIn(ex["code"], seen, ex["code"])
                seen[ex["code"]] = row["id"]
        whole: dict[str, list[str]] = {}
        for row in rows:
            for ex in row.get("execution") or []:
                code = ex.get("code") or ""
                if code in {"", "取不到", "TBD"}:
                    continue
                whole.setdefault(code, []).append(row["id"])
        overlap = {code: ids for code, ids in whole.items() if len(ids) > 1}
        self.assertEqual(overlap, {
            "510300": ["csi300", "s2-沪深300"],
            "510500": ["csi500", "s2-中证500"],
            "512100": ["csi1000", "s2-中证1000"],
            "159915": ["chinext", "s2-创业板"],
            "510880": ["csi-dividend", "s2-红利"],
        })

    def test_validate_rejects_the_same_code_on_two_main_containers(self):
        research = {key: "" for key in U.RESEARCH_FIELDS}
        def box(cid: str, code: str, arm: str = "main") -> dict:
            execution = {key: "" for key in U.EXEC_FIELDS}
            execution["code"] = code
            return {
                "id": cid, "asset_class": "港股", "name": cid, "arm": arm,
                "in_pool_index": True, "in_pool_tradable": True,
                "research": dict(research), "execution": [execution],
            }
        dup = U.validate({"container": [box("hsi", "159920"), box("qdii-159920", "159920")]})
        self.assertTrue(any("159920" in item for item in dup))
        twin = U.validate({"container": [box("csi300", "510300"), box("s2-沪深300", "510300", "S2")]})
        self.assertEqual(twin, [])


class Parse(unittest.TestCase):
    def test_sge_history_reads_headers_not_column_order(self):
        early = """
        <table><tr><td>品 种</td><td>开盘 价</td><td>收盘 价</td><td>最高 价</td><td>最低 价</td>
        <td>成交 量</td><td>成交 金额</td></tr>
        <tr><td>Au99.95</td><td>83.6</td><td>83.66</td><td>83.8</td><td>83.55</td><td>44</td><td>100</td></tr>
        <tr><td>Au99.99</td><td>83.9</td><td>83.91</td><td>83.92</td><td>83.9</td><td>66</td><td>200</td></tr>
        </table>
        """
        later = """
        <table><tr><td>合约</td><td>开盘价</td><td>最高价</td><td>最低价</td><td>收盘价</td><td>成交量</td><td>成交金额</td></tr>
        <tr><td>Au9999</td><td>257.30</td><td>257.45</td><td>256.60</td><td>257.38</td><td>3,514</td><td>900</td></tr>
        <tr><td>iAu99.99</td><td>1</td><td>1</td><td>1</td><td>1</td><td>1</td><td>1</td></tr>
        </table>
        """
        early_rows = parse.parse_sge_history(early)
        later_rows = parse.parse_sge_history(later)
        self.assertEqual(early_rows[0]["close"], 83.91)
        self.assertEqual(early_rows[0]["high"], 83.92)
        self.assertEqual(early_rows[0]["contract"], "Au99.99")
        self.assertEqual(later_rows[0]["contract"], "Au9999")
        self.assertEqual(later_rows[0]["close"], 257.38)
        self.assertEqual(later_rows[0]["volume"], 3514)
        self.assertEqual(len(later_rows), 1)
        page = '<a href="/sjzx/mrhqsj/509625"><span>上海黄金交易所2003年1月23日交易行情</span></a>'
        self.assertEqual(parse.parse_sge_index_page(page), [{"path": "/sjzx/mrhqsj/509625", "date": "2003-01-23"}])

    def test_dailyhq_order_is_open_close_low_high(self):
        rows = parse.parse_sge_dailyhq({"time": [["2023-12-29", 480.5, 479.59, 471.9, 486.0], ["2023-12-30", 1, 0, 1, 1]]})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["close"], 479.59)
        self.assertEqual(rows[0]["low"], 471.9)
        self.assertEqual(rows[0]["high"], 486.0)

    def test_chinabond_wealth_uses_shanghai_date_and_exact_names(self):
        rows = parse.parse_chinabond_wealth({"CFZS_00": {"1010073600000": 99.9987, "1010332800000": 100.0381}})
        self.assertEqual([row["date"] for row in rows], ["2002-01-04", "2002-01-07"])
        text = """
        中文名称：中债-10 年期国债指数
        英文名称：ChinaBond 10-year Treasury Bond Index
        财富指数代码：CBA04501
        2. 样本选取方法
        基准日
        2007 年 12 月 29 日，基点值为 100
        """
        ident = parse.parse_chinabond_method(text)
        self.assertEqual(ident["index_name"], "中债-10年期国债指数")
        self.assertEqual(ident["wealth_code"], "CBA04501")
        self.assertEqual(ident["base_date"], "2007-12-29")
        bucket = parse.parse_chinabond_method("中文名称：中债-3-5年期国债指数\n英文名称：X\n财富指数代码：CBA04601\n基准日为2006年12月31日")
        self.assertNotEqual(bucket["index_name"], "中债-5年期国债指数")

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

    def test_bond_wealth_lands_only_on_the_exact_container(self):
        from src.data import store as bars
        bars.replace(self.con, "CBA04501", "chinabond", [{"date": "2008-01-02", "close": 101.2}], "t")
        bars.replace(self.con, "CBA00601", "chinabond", [{"date": "2002-01-04", "close": 100.0}], "t")
        identities = [
            {"index_name": "中债-10年期国债指数", "wealth_code": "CBA04501", "base_date": "2007-12-29", "text_path": "a.txt"},
            {"index_name": "中债-3-5年期国债指数", "wealth_code": "CBA04601", "base_date": "2006-12-31", "text_path": "b.txt"},
            {"index_name": "中债-国债总指数", "wealth_code": "CBA00601", "base_date": "2001-12-31", "text_path": "c.txt"},
        ]
        boxes = {row["id"]: row for row in emit_universe.build_bonds_cash(self.con, {}, {}, identities)}
        self.assertEqual(boxes["cgb-10y"]["research"]["series_code"], "CBA04501")
        self.assertEqual(boxes["cgb-10y"]["research"]["base_date"], "2007-12-29")
        self.assertEqual(boxes["cgb-10y"]["research"]["publish_date"], "取不到")
        self.assertEqual(boxes["cgb-5y"]["research"]["series_status"], "取不到")
        refs = emit_universe.bond_references(self.con, identities)
        self.assertTrue(any("CBA00601" in line and "不进入池" in line for line in refs))
        self.assertFalse(any("CBA04501" in line for line in refs))

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
