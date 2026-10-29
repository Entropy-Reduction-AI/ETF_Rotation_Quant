"""v4-R1e 分组、登记表改写和只插入行情。不出网。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.data import db as DB
from src.v4.data.r1e import insert_missing_bars
from src.v4.data.r1e_parse import (
    OIL,
    SOX,
    commodity_bucket,
    group_funds,
    heaviest_benchmark_index,
    is_qdii_row,
)
from src.v4.data.r1e_register import apply_register


def _fund(**kwargs):
    base = {
        "code": "", "name": "", "full_name": "", "index_code": "", "index_name": "",
        "english_name": "", "benchmark": "", "benchmark_index": "", "benchmark_english": "",
        "fund_type": "", "vehicle": "ETF", "sub_class": "",
    }
    base.update(kwargs)
    return base


class Group(unittest.TestCase):
    def test_oil_equity_names_merge_and_are_not_crude(self):
        rows = group_funds([
            _fund(code="162411", name="华宝标普石油天然气上游股票指数证券投资基金(LOF)",
                  index_name="标普石油天然气上游股票指数"),
            _fund(code="159518", name="嘉实标普石油天然气勘探及生产精选行业ETF",
                  index_name="标普石油天然气勘探及生产精选行业指数"),
            _fund(code="513350", index_code="SPSIOP", index_name="标普石油天然气勘探及生产精选行业指数"),
        ])
        keys = {row["code"]: row["group_key"] for row in rows}
        self.assertEqual(keys["162411"], OIL)
        self.assertEqual(keys["159518"], OIL)
        self.assertEqual(keys["513350"], OIL)
        self.assertEqual(commodity_bucket("华宝标普石油天然气上游股票指数", "", "标普石油天然气上游股票指数"), "")

    def test_bovespa_translations_merge(self):
        rows = group_funds([
            _fund(code="159100", index_name="巴西伊博维斯帕指数"),
            _fund(code="520870", index_name="巴西IBOVESPA指数"),
        ])
        self.assertEqual(rows[0]["group_key"], rows[1]["group_key"])

    def test_active_chip_fund_follows_the_heaviest_index(self):
        heavy = heaviest_benchmark_index(
            "费城半导体指数(PHLX Semiconductor Sector Index)收益率*70%"
            "+中证芯片产业指数收益率*20%+人民币活期存款基准利率*10%"
        )
        self.assertEqual(heavy["english"], "PHLX Semiconductor Sector Index")
        self.assertEqual(heavy["weight"], 70.0)
        nasdaq = heaviest_benchmark_index(
            "经人民币汇率调整的纳斯达克100指数收益率*80%+恒生科技指数收益率*10%+中证综合债指数收益率*10%"
        )
        self.assertEqual(nasdaq["name"], "纳斯达克100指数")
        self.assertEqual(nasdaq["weight"], 80.0)
        rows = group_funds([
            _fund(code="513100", index_code="NDX", index_name="纳斯达克100指数"),
            _fund(code="501312", benchmark_index=nasdaq["name"]),
        ])
        self.assertEqual({row["group_key"] for row in rows}, {"NDX"})
        energy = heaviest_benchmark_index("标普能源行业指数(净收益)(S&P 500 Energy Sector Index(NTR))")
        self.assertEqual(energy["english"], "S&P 500 Energy Sector Index(NTR)")
        rows = group_funds([
            _fund(code="501225", name="景顺长城全球半导体芯片", fund_type="QDII-普通股票",
                  benchmark_index=heavy["name"], benchmark_english=heavy["english"]),
            _fund(code="513310", index_code="SOX", index_name="费城半导体指数"),
        ])
        keys = {row["code"]: row["group_key"] for row in rows}
        self.assertEqual(keys["501225"], SOX)
        self.assertEqual(keys["513310"], SOX)

    def test_crude_lof_is_the_commodity_container(self):
        rows = group_funds([
            _fund(code="161129", name="易方达原油证券投资基金(QDII)", fund_type="QDII-商品"),
            _fund(code="501018", name="南方原油", fund_type="QDII-商品"),
        ])
        self.assertEqual({row["group_key"] for row in rows}, {"crude-oil"})

    def test_exchange_code_links_a_chinese_name(self):
        rows = group_funds([
            _fund(code="510900", index_code="HSCEI", index_name="恒生中国企业指数"),
            _fund(code="159920", index_name="恒生中国企业指数"),
        ])
        self.assertEqual(rows[0]["group_key"], "HSCEI")
        self.assertEqual(rows[1]["group_key"], "HSCEI")

    def test_domestic_gold_etf_stays_out_of_the_qdii_list(self):
        self.assertFalse(is_qdii_row(_fund(code="518880", name="黄金ETF", sub_class="06"), "指数型-商品")[0])
        self.assertTrue(is_qdii_row(_fund(code="510900", name="恒生中国", sub_class="33"), "")[0])
        self.assertTrue(is_qdii_row(_fund(code="501225", name="全球芯片(QDII-LOF)"), "QDII-普通股票")[0])


class Register(unittest.TestCase):
    def test_moves_162411_and_adds_the_active_fund(self):
        text = """# 机械生成。

[[container]]
id = "theme-标普石油天然气上游股票指数"
asset_class = "美股和全球主题"
name = "标普石油天然气上游股票指数"
arm = "main"
in_pool_index = true
in_pool_tradable = true

[container.research]
index_code = "标普石油天然气上游股票指数"
index_name = "标普石油天然气上游股票指数"
return_basis = "unit_nav"
publish_date = "2012-06-08"
publish_date_source = ""
base_date = "取不到"
base_date_source = ""
series_code = "162411"
series_source = "eastmoney_f10_lsjz"
series_status = "in_db"
source_url = ""
note = "原来的容器。"

[[container.execution]]
code = "162411"
name = "华宝"
list_date = "2012-06-08"
list_date_source = ""
bars_status = "in_db"
track = "标普石油天然气上游股票指数"
track_source = ""
note = "原来的执行。"

[[container]]
id = "theme-标普石油天然气勘探及生产精选行业指数"
asset_class = "美股和全球主题"
name = "标普石油天然气勘探及生产精选行业指数"
arm = "main"
in_pool_index = true
in_pool_tradable = true

[container.research]
index_code = "标普石油天然气勘探及生产精选行业指数"
index_name = "标普石油天然气勘探及生产精选行业指数"
return_basis = "unit_nav"
publish_date = "2023-11-15"
publish_date_source = ""
base_date = "取不到"
base_date_source = ""
series_code = "159518"
series_source = "eastmoney_f10_lsjz"
series_status = "in_db"
source_url = ""
note = "精选行业。"

[[container.execution]]
code = "159518"
name = "嘉实"
list_date = "2023-11-15"
list_date_source = ""
bars_status = "in_db"
track = "标普石油天然气勘探及生产精选行业指数"
track_source = ""
note = "原来的执行。"

[[container]]
id = "gold"
asset_class = "商品"
name = "黄金"
arm = "main"
in_pool_index = true
in_pool_tradable = true

[container.research]
index_code = "Au99.99"
index_name = "Au99.99"
return_basis = "price"
publish_date = "取不到"
publish_date_source = ""
base_date = "取不到"
base_date_source = ""
series_code = "Au99.99"
series_source = "sge_daily"
series_status = "in_db"
source_url = ""
note = "黄金。"

[[container.execution]]
code = "518880"
name = "黄金ETF"
list_date = "2013-07-29"
list_date_source = ""
bars_status = "in_db"
track = "Au99.99"
track_source = ""
note = "黄金执行。"

# 附录 1 排除（不进入海外主题）

# 501225 景顺长城全球半导体芯片 exclude:跟踪标的不是单一指数 track=该基金无跟踪标的 list=取不到
# 161229 国投瑞银中国价值发现 exclude:跟踪标的不是单一指数 track=该基金无跟踪标的 list=2016-01-04
"""
        actions = [
            {
                "code": "162411", "name": "华宝", "list_date": "2012-06-08", "list_date_source": "szse",
                "bars_status": "in_db", "track": "标普石油天然气上游股票指数", "track_source": "jbgk",
                "note": "并入精选行业。", "target_id": "theme-标普石油天然气勘探及生产精选行业指数",
                "target_name": OIL, "group_key": OIL, "group_rule": "mandated", "create": False,
            },
            {
                "code": "501225", "name": "全球芯片", "list_date": "2023-06-08", "list_date_source": "sse",
                "bars_status": "取不到", "track": "该基金无跟踪标的", "track_source": "jbgk",
                "note": "主动基金。", "target_id": "theme-PHLX Semiconductor Sector Index",
                "target_name": SOX, "group_key": SOX, "group_rule": "benchmark_max_weight",
                "asset_class": "美股和全球主题", "create": True,
                "research": {
                    "index_code": SOX, "index_name": SOX, "return_basis": "unit_nav",
                    "publish_date": "2023-06-08", "publish_date_source": "sse",
                    "base_date": "取不到", "base_date_source": "",
                    "series_code": "501225", "series_source": "eastmoney_pingzhongdata",
                    "series_status": "取不到", "source_url": "jbgk",
                    "note": "D19 全球芯片。",
                },
            },
        ]
        got = apply_register(text, actions)
        self.assertNotIn('id = "theme-标普石油天然气上游股票指数"', got)
        self.assertIn('code = "162411"', got)
        self.assertIn('code = "159518"', got)
        self.assertIn('code = "518880"', got)
        self.assertIn('id = "theme-PHLX Semiconductor Sector Index"', got)
        self.assertNotIn("# 501225 ", got)
        self.assertIn("# 161229 ", got)
        self.assertLess(got.index('id = "theme-标普石油天然气勘探及生产精选行业指数"'), got.index('code = "162411"'))


class InsertOnly(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.con = DB.connect(self.tmp / "market.sqlite")
        self.addCleanup(self.con.close)

    def test_does_not_overwrite_an_existing_close(self):
        self.con.execute(
            """INSERT INTO bars (code, adj, date, open, high, low, close, volume, amount, source, fetched_at)
               VALUES ('501225', 'hfq', '2024-01-02', 1, 1, 1, 1.25, 10, 20, 'eastmoney_etf_hfq', 't0')""")
        self.con.commit()
        result = insert_missing_bars(self.con, "501225", "hfq", "eastmoney_etf_hfq", [
            {"date": "2024-01-02", "open": 9, "high": 9, "low": 9, "close": 9, "volume": 1, "amount": 1},
            {"date": "2024-01-03", "open": 2, "high": 2, "low": 2, "close": 2, "volume": 1, "amount": 1},
        ], "t1", end="2026-09-30")
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["inserted"], 0)
        kept = list(self.con.execute("SELECT date, close FROM bars WHERE code = '501225' ORDER BY date"))
        self.assertEqual([tuple(row) for row in kept], [("2024-01-02", 1.25)])

    def test_appends_only_missing_dates_of_the_same_source(self):
        self.con.execute(
            """INSERT INTO bars (code, adj, date, open, high, low, close, volume, amount, source, fetched_at)
               VALUES ('159100', 'raw', '2024-01-02', 1, 1, 1, 3, 1, 1, 'eastmoney_etf', 't0')""")
        self.con.commit()
        result = insert_missing_bars(self.con, "159100", "raw", "eastmoney_etf", [
            {"date": "2024-01-02", "open": 1, "high": 1, "low": 1, "close": 3, "volume": 1, "amount": 1},
            {"date": "2024-01-03", "open": 4, "high": 4, "low": 4, "close": 4, "volume": 2, "amount": 2},
        ], "t1", end="2026-09-30")
        self.assertEqual(result["inserted"], 1)
        rows = list(self.con.execute(
            "SELECT date, close, source FROM bars WHERE code = '159100' ORDER BY date"))
        self.assertEqual([tuple(row) for row in rows], [
            ("2024-01-02", 3.0, "eastmoney_etf"),
            ("2024-01-03", 4.0, "eastmoney_etf"),
        ])

    def test_refuses_to_stitch_another_source(self):
        self.con.execute(
            """INSERT INTO bars (code, adj, date, open, high, low, close, volume, amount, source, fetched_at)
               VALUES ('162411', 'raw', '2024-01-02', 1, 1, 1, 5, 1, 1, 'tencent_etf', 't0')""")
        self.con.commit()
        result = insert_missing_bars(self.con, "162411", "raw", "eastmoney_etf", [
            {"date": "2024-01-03", "close": 6},
        ], "t1")
        self.assertEqual(result["status"], "skipped_other_source")
        self.assertEqual(self.con.execute("SELECT count(*) FROM bars WHERE code = '162411'").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
