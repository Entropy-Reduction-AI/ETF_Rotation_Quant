"""v4-R1c 解析、后复权拼装、完整性。不出网，不算组合收益。"""
from __future__ import annotations

import unittest

import tests  # noqa: F401 — ETF_LEDGER_TESTING

from src.data import db as DB
from src.v4.data.integrity import (
    adj_discontinuity, count_findings, large_move_days, list_date_findings, missing_ranges,
    scan_price_series,
)
from src.v4.data.r1c import (
    actions_after, carried_tail, insert_backward, limit_up_checks, merge_manager_class,
    overlap_mismatches, record_split, sort_codes, _events_for,
)
from src.v4.data.r1c_parse import (
    REJECTED_NOT_SUBSTITUTE, assemble_backward, cash_amount, near_substitute_rows, parse_fhsp,
    parse_sina_nav, sina_daily_growth, split_ratio, spot_event,
)


FHSP = """
<table class='w782 comm cfxq'><thead><tr><th>年份</th><th>权益登记日</th><th>除息日</th><th>每10份分红</th><th>分红发放日</th></tr></thead>
<tbody><tr><td>2026年</td><td>2026-01-16</td><td>2026-01-19</td><td>每10份派现金1.2300元</td><td>2026-01-27</td></tr></tbody></table>
<table class='w782 comm fhxq'><thead><tr><th>年份</th><th>拆分折算日</th><th>拆分类型</th><th>拆分折算比例</th></tr></thead>
<tbody><tr><td>2012年</td><td>2012-05-11</td><td>份额折算</td><td>1:0.3709</td></tr></tbody></table>
"""

EMPTY = """
<table><thead><tr><th>每10份分红</th></tr></thead><tbody><tr><td>暂无分红信息!</td></tr></tbody></table>
<table><thead><tr><th>拆分折算比例</th></tr></thead><tbody><tr><td>暂无拆分信息!</td></tr></tbody></table>
"""


def _bar(day, close):
    return {"date": day, "open": close, "high": close, "low": close, "close": close, "volume": 1}


class Near(unittest.TestCase):
    def test_registry_matches_vehicle_table(self):
        rows = near_substitute_rows()
        self.assertEqual([row["code"] for row in rows], ["161211", "510880"])
        by_code = {row["code"]: row for row in rows}
        self.assertEqual(by_code["161211"]["tracked_index"], "沪深300金融地产指数")
        self.assertEqual(by_code["161211"]["near_index"], "中证全指金融地产指数")
        self.assertEqual(by_code["510880"]["tracked_index"], "上证红利指数")
        self.assertEqual(by_code["510880"]["near_index"], "中证红利指数")
        blob = " ".join(row["near_index"] + row["tracked_index"] for row in rows)
        for name in REJECTED_NOT_SUBSTITUTE:
            self.assertNotIn(name, blob)

    def test_carriers_come_before_the_rest(self):
        ordered = sort_codes(["159100", "159944", "510300", "159940"], {"159940", "159944", "510300"})
        self.assertEqual(ordered, ["159940", "159944", "510300", "159100"])


class Parse(unittest.TestCase):
    def test_fhsp_cash_and_split_ratio(self):
        got = parse_fhsp(FHSP)
        self.assertEqual(got["dividends"][0]["date"], "2026-01-19")
        self.assertAlmostEqual(got["dividends"][0]["amount"], 0.123)
        self.assertEqual(got["splits"][0]["date"], "2012-05-11")
        self.assertEqual((got["splits"][0]["numerator"], got["splits"][0]["denominator"]), (0.3709, 1.0))
        self.assertAlmostEqual(cash_amount("每10份派现金1.2300元"), 0.123)
        self.assertEqual(split_ratio("1:2"), (2.0, 1.0))

    def test_empty_tables_are_explicit(self):
        got = parse_fhsp(EMPTY)
        self.assertEqual(got["dividends"], [])
        self.assertEqual(got["splits"], [])
        self.assertTrue(got["explicit_empty_dividend"])
        self.assertTrue(got["explicit_empty_split"])

    def test_split_undoes_price_gap_and_dividend_is_reinvested(self):
        bars = [_bar("2024-01-02", 10), _bar("2024-01-03", 5)]
        built = assemble_backward(bars, [], [{
            "date": "2024-01-03", "numerator": 2, "denominator": 1, "text": "1:2",
        }])
        self.assertAlmostEqual(built["adjusted"][1]["close"], 10.0)
        self.assertEqual(bars[1]["close"], 5)
        bars = [_bar("2024-01-02", 10), _bar("2024-01-03", 9.8)]
        built = assemble_backward(bars, [{
            "date": "2024-01-03", "amount": 0.3, "text": "每10份派现金3.0000元",
        }], [])
        self.assertAlmostEqual(built["adjusted"][1]["close"], 10.1)
        spot = spot_event("dividend", "2024-01-03", bars, built["adjusted"], 0.3, 1.0)
        self.assertEqual(spot["continuous"], "1")

    def test_consolidation_ratio_one_to_half_does_not_leave_the_gap(self):
        bars = [_bar("2024-01-02", 10), _bar("2024-01-03", 20)]
        built = assemble_backward(bars, [], [{
            "date": "2024-01-03", "numerator": 0.5, "denominator": 1, "text": "1:0.5",
        }])
        self.assertAlmostEqual(built["adjusted"][1]["close"], 10.0)

    def test_sina_growth_adds_back_the_accum_gap(self):
        payload = {"result": {"data": {"data": [
            {"fbrq": "2008-01-04 00:00:00", "jjjz": "1.0000", "ljjz": "1.7000"},
            {"fbrq": "2008-01-03 00:00:00", "jjjz": "1.1000", "ljjz": "1.7000"},
        ]}}}
        rows = parse_sina_nav(payload)
        growth = sina_daily_growth(rows)
        self.assertEqual(growth[0]["date"], "2008-01-04")
        self.assertAlmostEqual(growth[0]["growth"], 0.0)


class Integrity(unittest.TestCase):
    def test_flags_a_hole_and_a_large_move_without_summing(self):
        calendar = ["2016-01-04", "2016-01-05", "2016-01-06", "2016-01-07"]
        self.assertEqual(missing_ranges(calendar, {"2016-01-04", "2016-01-07"}, "2016-01-04", "2016-01-07"),
                         [("2016-01-05", "2016-01-06", 2)])
        rows = [_bar("2016-01-04", 10), _bar("2016-01-05", 13)]
        found = large_move_days(rows, 0.20, set())
        self.assertEqual(found[0]["check"], "large_move")
        self.assertNotIn("annual", found[0]["detail"])
        quiet = large_move_days(rows, 0.20, {"2016-01-05"})
        self.assertEqual(quiet, [])
        smoothed = large_move_days(rows, 0.20, set(), {"2016-01-04": 10, "2016-01-05": 10.1})
        self.assertEqual(smoothed[0]["check"], "large_move_hfq_smoothed")

    def test_otc_threshold_is_thirty_percent_and_class_stays_blank(self):
        rows = [
            {"date": "2016-01-04", "close": 1.0},
            {"date": "2016-01-05", "close": 1.25},
            {"date": "2016-01-06", "close": 1.7},
        ]
        _info, found = scan_price_series(
            "310318", "otc", "otc_nav", "eastmoney_pingzhongdata", rows,
            ["2016-01-04", "2016-01-05", "2016-01-06"], 0.30)
        checks = [row["check"] for row in found]
        self.assertNotIn("large_move", checks[:1] if False else [row["check"] for row in found if row["date"] == "2016-01-05"])
        self.assertIn("large_move", [row["check"] for row in found if row["date"] == "2016-01-06"])
        self.assertTrue(all(row["manager_class"] == "" for row in found))
        self.assertNotIn("annualized", count_findings(found))

    def test_unknown_list_date_is_a_finding(self):
        got = list_date_findings("159940", "取不到", "2015-04-17")
        self.assertEqual(got[0]["check"], "list_date_unknown")

    def test_insert_refuses_to_overwrite_backward_series(self):
        con = DB.connect(":memory:")
        con.execute(
            """CREATE TABLE v4_series (
                code TEXT, kind TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL,
                volume REAL, unit_nav REAL, accum_nav REAL, filled INTEGER, source TEXT,
                source_url TEXT, method TEXT, fetched_at TEXT,
                PRIMARY KEY (code, kind, date))""")
        con.execute(
            """INSERT INTO v4_series
               (code, kind, date, close, filled, source, source_url, method, fetched_at)
               VALUES ('510300', 'backward', '2016-01-04', 1, 0, 'tencent_etf_hfq', 'u', 'm', 't')""")
        with self.assertRaises(Exception):
            insert_backward(con, "510300", [_bar("2016-01-04", 2)], "u", "m", "t")
        close = con.execute("SELECT close FROM v4_series WHERE code='510300'").fetchone()[0]
        self.assertEqual(close, 1)
        con.close()


class Command(unittest.TestCase):
    def test_pnl_is_rejected(self):
        from src.v4.data.__main__ import main
        self.assertEqual(main(["r1c", "pnl"]), 2)


class MustFix(unittest.TestCase):
    def test_split_plus_dividend_uses_post_split_cash(self):
        raw = [_bar("2024-11-29", 6.159), _bar("2024-12-02", 2.374)]
        adjusted = [_bar("2024-11-29", 1.93), _bar("2024-12-02", 1.961)]
        events = [
            {"date": "2024-12-02", "kind": "dividend", "amount": 0.1292},
            {"date": "2024-12-02", "kind": "split", "numerator": 2.5, "denominator": 1},
        ]
        self.assertEqual(adj_discontinuity(raw, adjusted, events), [])
        dividend_only = adj_discontinuity(raw, adjusted, events[:1])
        self.assertEqual(dividend_only[0]["check"], "adj_discontinuous")

    def test_verified_limit_up_is_not_a_large_move(self):
        rows = [_bar("2024-09-30", 0.929), _bar("2024-10-08", 1.115)]
        flagged = large_move_days(rows, 0.20, set())
        self.assertEqual(flagged[0]["check"], "large_move")
        quiet = large_move_days(rows, 0.20, set(), explained={"2024-10-08"})
        self.assertEqual(quiet, [])

    def test_carry_keeps_overlap_and_matches_the_next_raw_move(self):
        raw = [_bar("2019-07-02", 1.05), _bar("2019-07-03", 1.051), _bar("2019-07-04", 1.069)]
        backward = [_bar("2019-07-02", 1.140), _bar("2019-07-03", 1.141)]
        got = carried_tail(raw, backward, "2019-07-04")
        self.assertEqual([row["date"] for row in got["tail"]], ["2019-07-04"])
        self.assertAlmostEqual(got["tail"][0]["close"] / 1.141, 1.069 / 1.051)
        self.assertEqual(overlap_mismatches({"2019-07-03": 1.141}, {"2019-07-03": 1.141}), [])
        self.assertEqual(actions_after({"dividends": [{"date": "2013-05-14"}], "splits": []}, "2019-07-03"), [])
        self.assertEqual(actions_after({"dividends": [], "splits": [{"date": "2021-01-04"}]}, "2019-07-03")[0]["kind"], "split")

    def test_limit_up_check_accepts_a_rounded_twenty_percent_print(self):
        raw = [_bar("2024-09-30", 1.348), _bar("2024-10-08", 1.618)]
        backward = [_bar("2024-09-30", 1.348), _bar("2024-10-08", 1.618)]
        rows = limit_up_checks("159952", "2024-10-08", raw, backward, 1.618, "sina", "https://example.test", "创业板")
        self.assertEqual([row["series_kind"] for row in rows], ["raw", "backward"])
        self.assertTrue(all(row["conclusion"] == "limit_up" for row in rows))

    def test_recorded_split_keeps_its_ratio_for_the_continuity_check(self):
        con = DB.connect(":memory:")
        con.execute("CREATE TABLE cash_dividends (code TEXT, ex_date TEXT, amount REAL)")
        record_split(con, "159922", "2024-12-02", 2.5, 1.0, "1:2.5", "u", "abc", "除权日", "t")
        _days, detailed = _events_for(con, "159922")
        self.assertEqual(detailed[0]["numerator"], 2.5)
        self.assertEqual(detailed[0]["denominator"], 1.0)
        con.close()

    def test_manager_class_stays_on_unchanged_rows(self):
        previous = [{
            "code": "931160", "series_kind": "raw", "source": "csi", "check": "missing_trade_days",
            "date": "2019-01-02", "end_date": "2019-01-04", "detail": "日历有、序列没有正收盘",
            "manager_class": "需要 Orchestrator",
        }]
        findings = [
            {**previous[0], "manager_class": ""},
            {"code": "160125", "series_kind": "backward", "source": "tencent_etf_hfq",
             "check": "missing_trade_days", "date": "2024-01-02", "end_date": "2024-01-02",
             "detail": "日历有、序列没有正收盘", "manager_class": ""},
        ]
        merged = merge_manager_class(findings, previous)
        self.assertEqual(merged[0]["manager_class"], "需要 Orchestrator")
        self.assertEqual(merged[1]["manager_class"], "")


if __name__ == "__main__":
    unittest.main()
