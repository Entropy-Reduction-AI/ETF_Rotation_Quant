"""收盘涨跌停的报价规则。只用构造价，外加已落盘的 P6 离场信号。不重跑组合。"""
from __future__ import annotations

import csv
import sqlite3
import unittest
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pandas as pd

from src.v3.data.universe import containers
from src.v3.diag.limit_close import as_tick, at_limits, limit_prices, mark_planned_fill, quote_pair
from src.v3.engine.universe import execution_code, pool_members

ROOT = Path(__file__).resolve().parents[3]
DESIGN = ROOT / "results/v3/design-period/9b421c0294a8509e5283aa871034ff0e8ed66c75"


class LimitQuote(unittest.TestCase):
    def test_half_up_tick_matches_the_2015_crash_closes(self):
        # 159915：2015-06-26 收 2.767，06-29 收 2.490，正好跌停。
        up, down = limit_prices(2.767)
        self.assertEqual(down, Decimal("2.490"))
        self.assertEqual(up, Decimal("3.044"))
        self.assertEqual(at_limits(2.767, 2.49), (False, True))
        # 510300：2015-08-21 收 3.625，08-24 收 3.263。3.2625 按四舍五入是 3.263，不是银行家舍入的 3.262。
        self.assertEqual(limit_prices(3.625)[1], Decimal("3.263"))
        self.assertEqual(at_limits(3.625, 3.263), (False, True))
        self.assertEqual(limit_prices(2.226)[1], Decimal("2.003"))
        self.assertEqual(limit_prices(7.698)[1], Decimal("6.928"))
        self.assertEqual(limit_prices(2.879)[1], Decimal("2.591"))
        # 同一天沪深300 收 4.182，不是跌停。
        self.assertEqual(at_limits(4.346, 4.182), (False, False))
        self.assertEqual(mark_planned_fill(2.767, 2.49, "exit"), "close_limit_down")
        self.assertEqual(mark_planned_fill(2.767, 2.49, "buy"), "has_price")
        self.assertEqual(mark_planned_fill(None, None, "buy"), "no_price")
        self.assertEqual(mark_planned_fill(1.0, 0.0, "exit"), "no_price")
        self.assertEqual(mark_planned_fill(None, 1.0, "buy"), "has_price")
        self.assertEqual(as_tick(3.2625), Decimal("3.263"))

    def test_saved_p6_exit_signals_include_the_known_limit_down_days(self):
        db = ROOT / "data" / "market.sqlite"
        if not db.exists() or db.stat().st_size < 1000:
            self.skipTest("market.sqlite 不在这台机器上")
        members = {row["id"]: row for row in pool_members(containers(), "A", "tradable")}
        code_of = {name: execution_code(row) for name, row in members.items()}
        codes = sorted({code for code in code_of.values() if code})
        con = sqlite3.connect(db)
        try:
            marks = ",".join("?" * len(codes))
            frame = pd.read_sql_query(
                f"SELECT code, date, close FROM bars WHERE adj = 'raw' AND date <= '2015-12-31' "
                f"AND code IN ({marks})",
                con,
                params=codes,
            )
        finally:
            con.close()
        frame["date"] = pd.to_datetime(frame["date"])
        closes = {
            code: block.set_index("date")["close"].sort_index()
            for code, block in frame.groupby("code")
        }
        calendar = pd.DatetimeIndex(pd.to_datetime(
            pd.read_csv(DESIGN / "P6" / "held.csv", usecols=["date"])["date"]
        )).sort_values().unique()
        with (DESIGN / "P6" / "exits.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        signals = [row for row in rows if row["kind"] == "signal"]
        self.assertEqual(len(signals), 173)
        counted = Counter()
        limit_down = []
        for row in signals:
            day = pd.Timestamp(row["date"])
            pos = int(calendar.searchsorted(day, side="right"))
            if pos >= len(calendar):
                counted["no_next_session"] += 1
                continue
            fill = pd.Timestamp(calendar[pos])
            code = code_of.get(row["name"])
            prev, close = quote_pair(closes.get(code), fill)
            mark = mark_planned_fill(prev, close, "exit")
            counted[mark] += 1
            if mark == "close_limit_down":
                limit_down.append((row["path"], str(fill.date()), row["name"], code))
        self.assertEqual(counted["close_limit_down"], 22)
        self.assertIn(("3-week", "2015-06-29", "chinext", "159915"), limit_down)
        for name, code in (
            ("csi300", "510300"),
            ("csi500", "510500"),
            ("chinext", "159915"),
            ("csi-dividend", "510880"),
        ):
            self.assertIn(("5-week", "2015-08-24", name, code), limit_down)
        self.assertLessEqual(max(pd.Timestamp(item[1]) for item in limit_down), pd.Timestamp("2015-12-31"))


if __name__ == "__main__":
    unittest.main()
