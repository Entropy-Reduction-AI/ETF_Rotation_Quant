"""v4-R5b。手造容器。不读 2016-01-01 及以后的组合收益。"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.v3.engine.market import market_from_returns
from src.v3.engine.spec import load_spec
from src.v3.engine.switches import EngineSwitches
from src.v4.engine.apply import apply_market
from src.v4.engine.carriers import (
    _Candidate,
    build_candidates,
    choose_path,
    spliced_portfolio,
)


def _schema(con: sqlite3.Connection) -> None:
    con.execute("CREATE TABLE bars (code TEXT, adj TEXT, date TEXT, close REAL, amount REAL)")
    con.execute("CREATE TABLE v4_series (code TEXT, kind TEXT, date TEXT, close REAL)")
    con.execute(
        "CREATE TABLE v4_listing (code TEXT, name TEXT, maps_to TEXT, tracked_index TEXT, "
        "inception TEXT, enhanced INTEGER)")


class Tier1Registry(unittest.TestCase):
    def test_empty_exact_index_still_takes_the_listed_etf_and_matching_otc(self):
        con = sqlite3.connect(":memory:")
        _schema(con)
        con.execute(
            "INSERT INTO v4_series VALUES ('040046', 'otc_nav', '2013-08-02', 1.0)")
        con.execute(
            "INSERT INTO v4_listing VALUES (?, ?, ?, ?, ?, ?)",
            ("040046", "华安纳斯达克100ETF联接(QDII)A", "ndx100", "纳斯达克100指数", "2013-08-02", 0))
        con.execute(
            "INSERT INTO v4_listing VALUES (?, ?, ?, ?, ?, ?)",
            ("999001", "增强联接", "ndx100", "纳斯达克100指数", "2013-08-02", 1))
        containers = [{
            "id": "ndx100",
            "arm": "main",
            "asset_class": "美股宽基",
            "research": {
                "series_code": "XNDX",
                "series_status": "in_db",
                "index_name": "Nasdaq-100 Total Return",
                "index_code": "XNDX",
            },
            "execution": [
                {"code": "513100", "name": "纳斯达克100ETF", "track": "纳斯达克100指数"},
                {"code": "510880", "name": "红利ETF", "track": "纳斯达克100指数"},
            ],
        }]
        days = pd.to_datetime(["2013-08-02"])
        grouped = build_candidates(con, containers, pd.DatetimeIndex(days), "2013-08-02")
        codes = {item.code: item.tier for item in grouped["ndx100"]}
        self.assertEqual(codes.get("513100"), 1)
        self.assertEqual(codes.get("040046"), 2)
        self.assertNotIn("999001", codes)
        # 510880 是登记过的相近替身，即使跟踪标的被写成纳指，也不占第 1 档。
        self.assertNotIn("510880", codes)


class CarrierOwnReturn(unittest.TestCase):
    def test_otc_only_and_illiquid_etf_use_carrier_return_not_the_research_series(self):
        days = pd.bdate_range("2006-01-02", periods=5)
        path = Path(tempfile.mkdtemp()) / "market.sqlite"
        con = sqlite3.connect(path)
        _schema(con)
        bars = []
        nav = []
        for i, day in enumerate(days):
            text = str(day.date())
            bars.append(("H00300", "raw", text, 1000.0, None))
            bars.append(("510300", "raw", text, 3.0, 1_000_000.0))
            bars.append(("159915", "raw", text, 2.0, 1_000_000.0))
            nav.append(("050002", "otc_nav", text, 1.0 * (1.1 ** i)))
        con.executemany("INSERT INTO bars VALUES (?, ?, ?, ?, ?)", bars)
        con.executemany("INSERT INTO v4_series VALUES (?, ?, ?, ?)", nav)
        con.execute(
            "INSERT INTO v4_listing VALUES (?, ?, ?, ?, ?, ?)",
            ("050002", "博时裕富沪深300指数", "csi300", "沪深300指数", "2003-08-26", 0))
        con.commit()
        con.close()
        signal = pd.DataFrame({"csi300": 0.0123, "chinext": 0.0456, "cash": 0.0}, index=days)
        fees = {"csi300": 0.001, "chinext": 0.001, "cash": 0.0005}
        liquidity = pd.DataFrame({"csi300": True, "chinext": True}, index=days)
        containers = [
            {
                "id": "csi300",
                "arm": "main",
                "asset_class": "A股宽基",
                "research": {"series_code": "H00300", "series_status": "in_db", "index_name": "沪深300全收益指数"},
                "execution": [{"code": "510300", "name": "沪深300ETF", "track": "沪深300指数"}],
            },
            {
                "id": "chinext",
                "arm": "main",
                "asset_class": "A股宽基",
                "research": {"series_code": "", "series_status": "取不到"},
                "execution": [{"code": "159915", "name": "创业板ETF", "track": "创业板指数(价格)"}],
            },
        ]
        traded = market_from_returns(signal, fees, pnl=signal.copy(), liquidity=liquidity.copy())
        apply_market(
            traded, EngineSwitches(carriers=True), db=path, containers=containers,
            spec=load_spec(), pool="tradable")
        # 研究序列留下来做排名。成交额不够、交易日也不够 60 天，场内不进第 1 档。
        self.assertTrue((traded.signal["csi300"] == 0.0123).all())
        self.assertTrue(bool(traded.liquidity.loc[days[0], "csi300"]))
        self.assertTrue(pd.isna(traded.pnl.loc[days[0], "csi300"]))
        self.assertAlmostEqual(float(traded.pnl.loc[days[1], "csi300"]), 0.10)
        self.assertAlmostEqual(float(traded.pnl.loc[days[2], "csi300"]), 0.10)
        self.assertNotAlmostEqual(float(traded.pnl.loc[days[1], "csi300"]), 0.0123)
        # 只有冷清的场内 ETF，没有场外档，当天不进排名。
        self.assertFalse(bool(traded.liquidity.loc[days[-1], "chinext"]))
        self.assertTrue(pd.isna(traded.pnl.loc[days[-1], "chinext"]))

    def test_switch_day_return_stays_on_the_previous_carrier(self):
        days = pd.to_datetime(["2006-01-04", "2006-01-05", "2006-01-06"])
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE v4_series (code TEXT, kind TEXT, date TEXT, close REAL)")
        closes = {"510300": [10.0, 11.0, 12.1], "159919": [50.0, 40.0, 48.0]}
        rows = []
        for code, series in closes.items():
            for day, close in zip(days, series):
                rows.append((code, "backward", str(day.date()), close))
        con.executemany("INSERT INTO v4_series VALUES (?, ?, ?, ?)", rows)

        def candidate(code, medians):
            index = pd.DatetimeIndex(days)
            flags = [value >= 30_000_000.0 for value in medians]
            return _Candidate(
                container="csi300", code=code, vehicle="etf", tier=1,
                inception="", nav_start="", order=0,
                available=pd.Series(flags, index=index, dtype=bool),
                median=pd.Series(medians, index=index, dtype=float),
                board="main")

        held = candidate("510300", [80e6, 10e6, 10e6])
        peer = candidate("159919", [40e6, 90e6, 90e6])
        path = choose_path([held, peer], days)
        self.assertEqual(path[0].label, "etf:510300")
        self.assertEqual(path[1].label, "etf:159919")
        series = spliced_portfolio(con, [held, peer], days, "2006-01-06", nav_lag=2)
        self.assertTrue(pd.isna(series.iloc[0]))
        # 第二天已经换成 159919，收益仍是 510300 的 11/10−1，不是 40/50−1。
        self.assertAlmostEqual(float(series.iloc[1]), 0.10)
        self.assertNotAlmostEqual(float(series.iloc[1]), 40.0 / 50.0 - 1.0)
        self.assertAlmostEqual(float(series.iloc[2]), 48.0 / 40.0 - 1.0)


if __name__ == "__main__":
    unittest.main()
