"""v4-R5c。U-指数成交价用研究序列。不读 2016-01-01 及以后的组合收益。"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.v3.engine.limits import FillQuote, session_tradable
from src.v3.engine.market import index_pool_fill_close, market_from_returns
from src.v3.engine.spec import load_spec
from src.v3.engine.switches import EngineSwitches
from src.v4.engine.apply import apply_market


def _schema(con: sqlite3.Connection) -> None:
    con.execute("CREATE TABLE bars (code TEXT, adj TEXT, date TEXT, close REAL, amount REAL)")
    con.execute("CREATE TABLE v4_series (code TEXT, kind TEXT, date TEXT, close REAL)")
    con.execute(
        "CREATE TABLE v4_listing (code TEXT, name TEXT, maps_to TEXT, tracked_index TEXT, "
        "inception TEXT, enhanced INTEGER)")


class IndexFill(unittest.TestCase):
    def test_research_close_can_be_bought_before_the_etf_lists(self):
        dates = pd.to_datetime(["2008-01-02", "2008-01-03"])
        research = pd.Series([100.0, 100.4], index=dates)
        traded = pd.Series(dtype=float)
        chosen = index_pool_fill_close("index", "债券", research, traded)
        flags = session_tradable(
            {"cgb-10y": FillQuote(close=chosen, board="main")}, dates[1], ["cgb-10y"])
        self.assertEqual(flags["cgb-10y"], (True, True))
        limited = pd.Series([100.0, 109.6], index=dates)
        blocked = session_tradable(
            {"cgb-10y": FillQuote(close=limited, board="main")}, dates[1], ["cgb-10y"])
        self.assertEqual(blocked["cgb-10y"], (False, True))
        other = index_pool_fill_close("tradable", "债券", research, traded)
        quiet = session_tradable(
            {"cgb-10y": FillQuote(close=other, board="main")}, dates[1], ["cgb-10y"])
        self.assertEqual(quiet["cgb-10y"], (False, False))

    def test_spliced_research_can_be_bought_when_the_etf_has_no_bars(self):
        days = pd.bdate_range("2011-06-13", periods=4)
        path = Path(tempfile.mkdtemp()) / "market.sqlite"
        con = sqlite3.connect(path)
        _schema(con)
        bars = [("H00300", "raw", str(day.date()), 1000.0, None) for day in days]
        nav = []
        price = 1.0
        for day in days:
            nav.append(("050021", "otc_nav", str(day.date()), price))
            price *= 1.01
        con.executemany("INSERT INTO bars VALUES (?, ?, ?, ?, ?)", bars)
        con.executemany("INSERT INTO v4_series VALUES (?, ?, ?, ?)", nav)
        con.execute(
            "INSERT INTO v4_listing VALUES (?, ?, ?, ?, ?, ?)",
            ("050021", "博时创业板联接", "chinext", "创业板指数(价格)", "2011-06-10", 0))
        con.commit()
        con.close()
        signal = pd.DataFrame({"chinext": float("nan"), "cash": 0.0}, index=days)
        fees = {"chinext": 0.001, "cash": 0.0005}
        containers = [{
            "id": "chinext",
            "arm": "main",
            "asset_class": "A股宽基",
            "research": {"series_code": "", "series_status": "取不到"},
            "execution": [{"code": "159915", "name": "创业板ETF", "track": "创业板指数(价格)"}],
        }]
        market = market_from_returns(signal, fees)
        apply_market(
            market, EngineSwitches(carriers=True), db=path, containers=containers,
            spec=load_spec(), pool="index")
        self.assertTrue(pd.isna(market.fill_close["chinext"].loc[days[0]]))
        self.assertAlmostEqual(float(market.fill_close["chinext"].loc[days[1]]), 101.0)
        self.assertNotAlmostEqual(float(market.fill_close["chinext"].loc[days[1]]), 1.01)
        self.assertEqual(market.fill_board["chinext"], "chinext")
        flags = session_tradable(
            {"chinext": FillQuote(
                close=market.fill_close["chinext"], board=market.fill_board["chinext"])},
            days[2], ["chinext"])
        self.assertEqual(flags["chinext"], (True, True))
        early = session_tradable(
            {"chinext": FillQuote(
                close=market.fill_close["chinext"], board=market.fill_board["chinext"])},
            days[0], ["chinext"])
        self.assertEqual(early["chinext"], (False, False))


if __name__ == "__main__":
    unittest.main()
