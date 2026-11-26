"""构造数据上的规则测试。不打开行情库，不读 2016 年以后的任何数值。"""

from __future__ import annotations

import sqlite3
import unittest

from v6ind.calendar_math import add_months, momentum_anchors
from v6ind.load import CLOSE_SQL, CutoffBreach, load_closes, provenance
from v6ind.momentum import Score, dedupe_top, month_ends, ten_month_ma, twelve_one


class MomentumTest(unittest.TestCase):
    def test_anchors_skip_signal_month(self) -> None:
        self.assertEqual(momentum_anchors("2015-08"), ("2015-07", "2014-07"))
        self.assertEqual(momentum_anchors("2013-04"), ("2013-03", "2012-03"))

    def test_twelve_one_uses_those_anchors(self) -> None:
        rows = [
            ("2014-07-31", 100.0),
            ("2015-07-31", 206.0),
            ("2015-08-31", 50.0),
        ]
        got = twelve_one(month_ends(rows), "2015-08")
        self.assertIsNotNone(got)
        assert got is not None
        score, end_date, end_level, start_date, start_level = got
        self.assertEqual(score, 1.06)
        self.assertEqual((end_date, end_level), ("2015-07-31", 206.0))
        self.assertEqual((start_date, start_level), ("2014-07-31", 100.0))

    def test_last_print_in_month_is_month_end(self) -> None:
        ends = month_ends([("2015-07-30", 1.0), ("2015-07-31", 2.0)])
        self.assertEqual(ends["2015-07"], ("2015-07-31", 2.0))

    def test_anniversary_is_calendar_twelve_months(self) -> None:
        self.assertEqual(add_months("2013-12-26", 12), "2014-12-26")
        self.assertEqual(add_months("2014-12-10", 12), "2015-12-10")
        self.assertEqual(add_months("2005-01-31", 1), "2005-02-28")

    def test_dedupe_keeps_highest_tag_and_both_untagged(self) -> None:
        scores = [
            Score("高", "B", "信息技术", 0.5, "d", 1, "d", 1),
            Score("低", "A", "信息技术", 0.4, "d", 1, "d", 1),
            Score("宽基1", "C", "", 0.3, "d", 1, "d", 1),
            Score("宽基2", "D", "", 0.2, "d", 1, "d", 1),
        ]
        chosen, bond_slots, dropped = dedupe_top(scores, positive_only=False)
        self.assertEqual([row.code for row in chosen], ["B", "C", "D"])
        self.assertEqual(bond_slots, 0)
        self.assertEqual([row.code for row in dropped], ["A"])

    def test_positive_filter_leaves_bond_slots(self) -> None:
        scores = [
            Score("正", "A", "", 0.2, "d", 1, "d", 1),
            Score("负", "B", "", -0.1, "d", 1, "d", 1),
        ]
        chosen, bond_slots, _dropped = dedupe_top(scores, positive_only=True)
        self.assertEqual([row.code for row in chosen], ["A"])
        self.assertEqual(bond_slots, 2)

    def test_ma_includes_signal_month_and_strict_break(self) -> None:
        rows = [(f"2015-{month:02d}-28", float(month)) for month in range(1, 9)]
        rows.append(("2015-08-31", 1.0))
        ends = month_ends(rows)
        # 2015-08 只有 8 个点，不足 10 个月。
        self.assertIsNone(ten_month_ma(ends, "2015-08"))
        full = [(f"2014-{month:02d}-28", 10.0) for month in range(11, 13)]
        full += [(f"2015-{month:02d}-28", 10.0) for month in range(1, 8)]
        full.append(("2015-08-31", 9.0))
        checked = ten_month_ma(month_ends(full), "2015-08")
        self.assertIsNotNone(checked)
        assert checked is not None
        _date, close, average = checked
        self.assertLess(close, average)


class LoadCutoffTest(unittest.TestCase):
    def test_sql_filters_before_reading_values(self) -> None:
        self.assertIn("date <= ?", CLOSE_SQL)
        con = sqlite3.connect(":memory:")
        con.execute(
            "CREATE TABLE bars (code TEXT, adj TEXT, date TEXT, close REAL, volume REAL, amount REAL, source TEXT)"
        )
        con.executemany(
            "INSERT INTO bars VALUES (?,?,?,?,?,?,?)",
            [
                ("H00300", "raw", "2015-12-31", 10.0, 1.0, 1.0, "src"),
                ("H00300", "raw", "2016-01-04", 999.0, 1.0, 1.0, "src"),
            ],
        )
        rows = load_closes(con, "H00300", cutoff="2015-12-31")
        self.assertEqual(rows, [("2015-12-31", 10.0)])
        info = provenance(con, "H00300", cutoff="2015-12-31")
        self.assertEqual(info["excluded_rows"], 1)
        self.assertEqual(info["kept"][0]["last"], "2015-12-31")
        self.assertNotIn(999.0, [close for _date, close in rows])

    def test_breach_is_raised_if_a_late_row_is_returned(self) -> None:
        class Late:
            def execute(self, _sql, _params):
                return [("2016-01-01", 1.0)]

        with self.assertRaises(CutoffBreach):
            load_closes(Late(), "X", cutoff="2015-12-31")


if __name__ == "__main__":
    unittest.main()
