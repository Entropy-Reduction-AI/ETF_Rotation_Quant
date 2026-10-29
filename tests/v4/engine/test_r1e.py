"""v4-R1e 引擎。手造序列。不跑候选组合收益，也不汇总 2016 年以后的收益。"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.v3.engine.market import levels_from_returns, market_from_returns
from src.v3.engine.spec import load_spec
from src.v3.engine.switches import EngineSwitches
from src.v4.engine.apply import apply_market
from src.v4.engine.carriers import (
    MIN_AMOUNT,
    CarrierChoice,
    _Candidate,
    build_candidates,
    choose_on,
    choose_path,
    earning_path,
    has_investable_index,
    lagged_nav_returns,
    research_return,
    splice_returns,
    spliced_research,
    stitch_fills,
)


def _candidate(code, days, medians, *, vehicle="etf", tier=1, board="main", qdii=False,
               available=None, order=0):
    index = pd.DatetimeIndex(days)
    median = pd.Series(medians, index=index, dtype=float)
    if available is None:
        flags = [value >= MIN_AMOUNT for value in medians]
    else:
        flags = available
    return _Candidate(
        container="oil", code=code, vehicle=vehicle, tier=tier,
        inception="2005-01-04", nav_start="2005-01-04", order=order,
        available=pd.Series(flags, index=index, dtype=bool),
        median=median, board=board, qdii=qdii)


class HeldCarrier(unittest.TestCase):
    def test_stays_while_qualified_and_leaves_when_the_median_breaks(self):
        days = pd.to_datetime(["2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09"])
        held = _candidate("510300", days, [80e6, 50e6, 10e6, 100e6])
        peer = _candidate("159919", days, [40e6, 90e6, 90e6, 40e6])
        path = choose_path([held, peer], days)
        # 第一天没有持仓，成交额高的先上。
        self.assertEqual(path[0].label, "etf:510300")
        # 第二天 159919 更活跃，但 510300 仍在 3000 万以上，不换。
        self.assertGreater(90e6, 50e6)
        self.assertEqual(path[1].label, "etf:510300")
        self.assertEqual(choose_on([held, peer], days[1]).label, "etf:159919")
        # 第三天 510300 掉到 3000 万以下，才换成仍有资格的 159919。
        self.assertLess(10e6, MIN_AMOUNT)
        self.assertEqual(path[2].label, "etf:159919")
        # 第四天 510300 重新变成成交额更高的，已持有的 159919 仍有资格，留住。
        self.assertEqual(path[3].label, "etf:159919")

    def test_equal_median_does_not_walk_back_to_the_lower_code(self):
        days = pd.to_datetime(["2006-01-04", "2006-01-05"])
        first = _candidate("510300", days, [80e6, 50e6])
        second = _candidate("159919", days, [40e6, 50e6])
        path = choose_path([first, second], days)
        self.assertEqual(path[0].label, "etf:510300")
        # 中位数打平的那天，没有持仓会按代码升序取 159919。有持仓则留在 510300。
        self.assertEqual(choose_on([first, second], days[1]).label, "etf:159919")
        self.assertEqual(path[1].label, "etf:510300")

    def test_otc_holding_steps_up_when_an_etf_qualifies(self):
        days = pd.to_datetime(["2006-01-04", "2006-01-05"])
        cold = _candidate("510300", days, [1e6, 80e6])
        feeder = _candidate(
            "000311", days, [0.0, 0.0], vehicle="otc", tier=2, board="none",
            available=[True, True])
        path = choose_path([cold, feeder], days)
        self.assertEqual(path[0].label, "otc:000311")
        self.assertEqual(path[1].label, "etf:510300")

    def test_fill_uses_the_held_funds_own_close(self):
        days = pd.to_datetime(["2006-01-04", "2006-01-05"])
        held = _candidate("510300", days, [50e6, 50e6])
        peer = _candidate("159919", days, [40e6, 90e6])
        prints = {
            "510300": pd.Series([10.0, 11.0], index=days),
            "159919": pd.Series([100.0, 130.0], index=days),
        }
        stitched = stitch_fills({"oil": [held, peer]}, days, prints, {"oil": "商品"})
        self.assertAlmostEqual(float(stitched["oil"].close.iloc[1]), 11.0)
        self.assertAlmostEqual(float(stitched["oil"].prev.iloc[1]), 10.0)
        self.assertNotAlmostEqual(float(stitched["oil"].close.iloc[1]), 130.0)

    def test_prior_day_selection_sticks_without_a_portfolio_weight(self):
        import inspect
        self.assertNotIn("weight", inspect.signature(choose_on).parameters)
        self.assertNotIn("weight", inspect.signature(choose_path).parameters)
        days = pd.to_datetime(["2006-01-04", "2006-01-05"])
        old = _candidate("510300", days, [50e6, 50e6])
        peer = _candidate("159919", days, [40e6, 90e6])
        prior = CarrierChoice("etf", "510300", "main")
        # 没有权重参数。前一日选定的 510300 仍有资格就留下；没有前一日才改选更活跃的 159919。
        self.assertEqual(choose_on([old, peer], days[1], prior=prior).label, "etf:510300")
        self.assertEqual(choose_on([old, peer], days[1]).label, "etf:159919")
        self.assertEqual(earning_path([]), [])
        self.assertIsNone(earning_path([prior])[0])


class SplicedResearch(unittest.TestCase):
    def test_switch_uses_the_new_funds_return_not_its_price_level(self):
        days = pd.to_datetime(["2006-01-04", "2006-01-05", "2006-01-06"])
        returns = {
            "A": pd.Series([float("nan"), 0.10, 12.0 / 11.0 - 1.0], index=days),
            "B": pd.Series([float("nan"), 0.0, -0.20], index=days),
        }
        choices = [
            CarrierChoice("etf", "A", "main"),
            CarrierChoice("etf", "A", "main"),
            CarrierChoice("etf", "B", "main"),
        ]
        spliced = splice_returns(choices, days, returns)
        self.assertTrue(pd.isna(spliced.iloc[0]))
        self.assertAlmostEqual(float(spliced.iloc[1]), 0.10)
        self.assertAlmostEqual(float(spliced.iloc[2]), -0.20)
        # 若把 11 和 80 拼成一条价格，当天收益会是 80/11-1，而不是 B 自己的 -20%。
        self.assertNotAlmostEqual(float(spliced.iloc[2]), 80.0 / 11.0 - 1.0)
        frame = pd.DataFrame({"oil": spliced, "cash": 0.0}, index=days)
        level = levels_from_returns(frame, "cash")["oil"]
        self.assertAlmostEqual(float(level.iloc[2]), 100.0 * 1.10 * 0.80)
        self.assertNotAlmostEqual(float(level.iloc[2]), 80.0)

    def test_qdii_uses_the_lagged_nav_of_the_selected_fund(self):
        days = pd.to_datetime(["2006-01-02", "2006-01-03", "2006-01-04", "2006-01-05", "2006-01-06"])
        nav_a = pd.Series([10.0, 10.0, 12.0, 12.0, 12.0], index=days)
        nav_b = pd.Series([40.0, 40.0, 40.0, 20.0, 20.0], index=days)
        ret_a = lagged_nav_returns(nav_a, days, 2)
        ret_b = lagged_nav_returns(nav_b, days, 2)
        # T−2：1 月 6 日看到的是 1 月 4 日净值。A 从 10 到 12，B 仍是 40。
        self.assertAlmostEqual(float(ret_a.iloc[-1]), 0.20)
        self.assertAlmostEqual(float(ret_b.iloc[-1]), 0.0)
        choices = [None, None, None, CarrierChoice("etf", "A", "main"), CarrierChoice("etf", "B", "main")]
        spliced = splice_returns(choices, days, {"A": ret_a, "B": ret_b})
        self.assertAlmostEqual(float(spliced.iloc[-2]), 0.0)
        self.assertAlmostEqual(float(spliced.iloc[-1]), 0.0)
        self.assertNotAlmostEqual(float(spliced.iloc[-1]), 40.0 / 12.0 - 1.0)

    def test_research_return_reads_hfq_and_lagged_nav(self):
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE v4_series (code TEXT, kind TEXT, date TEXT, close REAL)")
        con.execute(
            "CREATE TABLE fund_nav (code TEXT, date TEXT, unit_nav REAL, accum_nav REAL, "
            "subscribe_status TEXT, redeem_status TEXT, source TEXT, run_id INTEGER, fetched_at TEXT)")
        days = pd.to_datetime(["2006-01-04", "2006-01-05"])
        con.executemany(
            "INSERT INTO v4_series VALUES (?, ?, ?, ?)",
            [
                ("159985", "backward", "2006-01-04", 10.0),
                ("159985", "backward", "2006-01-05", 11.0),
            ])
        con.executemany(
            "INSERT INTO fund_nav (code, date, unit_nav) VALUES (?, ?, ?)",
            [("161129", str(day.date()), 10.0) for day in pd.to_datetime(
                ["2006-01-02", "2006-01-03", "2006-01-04", "2006-01-05", "2006-01-06"])])
        con.execute(
            "UPDATE fund_nav SET unit_nav = 12 WHERE code = '161129' AND date >= '2006-01-04'")
        plain = _candidate("159985", days, [80e6, 80e6])
        got = research_return(con, plain, pd.DatetimeIndex(days), "2006-01-05", 2)
        self.assertTrue(pd.isna(got.iloc[0]))
        self.assertAlmostEqual(float(got.iloc[1]), 0.10)
        qdii_days = pd.to_datetime(
            ["2006-01-02", "2006-01-03", "2006-01-04", "2006-01-05", "2006-01-06"])
        qdii = _candidate("161129", qdii_days, [80e6] * 5, qdii=True)
        nav = pd.Series([10.0, 10.0, 12.0, 12.0, 12.0], index=qdii_days)
        from_sql = research_return(con, qdii, pd.DatetimeIndex(qdii_days), "2006-01-06", 2)
        by_hand = lagged_nav_returns(nav, qdii_days, 2)
        self.assertTrue(from_sql.equals(by_hand))


class IndexlessLinks(unittest.TestCase):
    def test_index_flag_and_linked_funds_ignore_the_track_name(self):
        self.assertFalse(has_investable_index({"research": {"series_code": "", "series_status": "取不到"}}))
        self.assertFalse(has_investable_index({"research": {"series_code": "取不到", "series_status": "取不到"}}))
        self.assertTrue(has_investable_index({"research": {"series_code": "H00300", "series_status": "in_db"}}))
        self.assertTrue(has_investable_index({"research": {"series_code": "Au99.99", "series_status": "partial"}}))
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE bars (code TEXT, adj TEXT, date TEXT, close REAL, amount REAL)")
        con.execute("CREATE TABLE v4_series (code TEXT, kind TEXT, date TEXT, close REAL)")
        con.execute(
            "CREATE TABLE v4_listing (code TEXT, name TEXT, maps_to TEXT, tracked_index TEXT, "
            "inception TEXT, enhanced INTEGER)")
        con.execute(
            "INSERT INTO v4_series VALUES ('000311', 'otc_nav', '2006-01-04', 1.2)")
        con.executemany(
            "INSERT INTO v4_listing VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("000311", "原油联接", "crude-oil", "不是指数", "2006-01-04", 0),
                ("000312", "原油增强", "crude-oil", "不是指数", "2006-01-04", 1),
                ("050099", "别的联接", "csi300", "别的指数", "2006-01-04", 0),
            ])
        containers = [
            {
                "id": "crude-oil", "arm": "main", "asset_class": "商品",
                "research": {"series_code": "", "series_status": "取不到", "return_basis": "excess_return"},
                "execution": [
                    {"code": "161129", "name": "易方达原油证券投资基金(QDII)", "track": "该基金无跟踪标的"},
                    {"code": "160723", "name": "嘉实原油证券投资基金(QDII-LOF)", "track": "该基金无跟踪标的"},
                ],
            },
            {
                "id": "csi300", "arm": "main", "asset_class": "A股宽基",
                "research": {"series_code": "H00300", "series_status": "in_db"},
                "execution": [
                    {"code": "999999", "name": "不该进来", "track": "不是沪深300指数"},
                ],
            },
        ]
        calendar = pd.to_datetime(["2006-01-04"])
        grouped = build_candidates(con, containers, pd.DatetimeIndex(calendar), "2006-01-04")
        crude = {item.code: item for item in grouped["crude-oil"]}
        self.assertEqual(set(crude), {"161129", "160723", "000311"})
        self.assertTrue(crude["161129"].qdii)
        self.assertEqual(crude["161129"].tier, 1)
        self.assertEqual(crude["000311"].tier, 2)
        self.assertNotIn("000312", crude)
        csi = [item.code for item in grouped.get("csi300", [])]
        self.assertNotIn("999999", csi)
        self.assertNotIn("050099", csi)


class ApplySplice(unittest.TestCase):
    def test_switches_off_leave_the_series_and_on_splices_the_hotter_fund(self):
        dates = pd.bdate_range("2006-01-02", periods=80)
        path = Path(tempfile.mkdtemp()) / "market.sqlite"
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE bars (code TEXT, adj TEXT, date TEXT, close REAL, amount REAL)")
        con.execute("CREATE TABLE v4_series (code TEXT, kind TEXT, date TEXT, close REAL)")
        con.execute(
            "CREATE TABLE v4_listing (code TEXT, name TEXT, maps_to TEXT, tracked_index TEXT, "
            "inception TEXT, enhanced INTEGER)")
        bars = []
        backward = []
        for i, day in enumerate(dates):
            text = str(day.date())
            bars.append(("H00300", "raw", text, 1000.0, None))
            bars.append(("159985", "raw", text, 10.0, 40_000_000.0))
            # 第 60 个交易日才能入选。入选当天的收益仍空，涨幅放在下一天。
            price = 50.0 if i < 61 else 55.0
            bars.append(("159986", "raw", text, price, 80_000_000.0))
            backward.append(("159985", "backward", text, 10.0))
            backward.append(("159986", "backward", text, price))
        con.executemany("INSERT INTO bars VALUES (?, ?, ?, ?, ?)", bars)
        con.executemany("INSERT INTO v4_series VALUES (?, ?, ?, ?)", backward)
        con.commit()
        con.close()
        signal = pd.DataFrame({"oil": 0.0, "csi300": 0.0123, "cash": 0.0}, index=dates)
        fees = {"oil": 0.001, "csi300": 0.001, "cash": 0.0005}
        liquidity = pd.DataFrame({"oil": False, "csi300": True}, index=dates)
        market = market_from_returns(signal, fees, liquidity=liquidity)
        containers = [
            {
                "id": "oil", "arm": "main", "asset_class": "商品",
                "research": {"series_code": "", "series_status": "取不到"},
                "execution": [
                    {"code": "159985", "name": "豆粕甲", "track": "没有指数"},
                    {"code": "159986", "name": "豆粕乙", "track": "没有指数"},
                ],
            },
            {
                "id": "csi300", "arm": "main", "asset_class": "A股宽基",
                "research": {"series_code": "H00300", "series_status": "in_db"},
                "execution": [],
            },
        ]
        spec = load_spec()
        before_signal = market.signal.copy()
        before_pnl = market.pnl.copy()
        before_levels = market.levels.copy()
        apply_market(market, EngineSwitches(), db=path, containers=containers, spec=spec, pool="index")
        self.assertTrue(market.signal.equals(before_signal))
        self.assertTrue(market.pnl.equals(before_pnl))
        self.assertTrue(market.levels.equals(before_levels))
        apply_market(
            market, EngineSwitches(carriers=True), db=path, containers=containers, spec=spec, pool="index")
        # 可交易首日选定 159986，但这天还没有 D−1 载体，收益为空。下一天才记它自己的 +10%。
        self.assertTrue(pd.isna(market.signal.loc[dates[59], "oil"]))
        self.assertTrue(pd.isna(market.signal.loc[dates[60], "oil"]))
        self.assertAlmostEqual(float(market.signal.loc[dates[61], "oil"]), 0.10)
        self.assertAlmostEqual(float(market.signal.loc[dates[62], "oil"]), 0.0)
        self.assertNotAlmostEqual(float(market.signal.loc[dates[61], "oil"]), 55.0 / 10.0 - 1.0)
        self.assertTrue(pd.isna(market.levels.loc[dates[60], "oil"]))
        self.assertAlmostEqual(float(market.levels.loc[dates[61], "oil"]), 110.0)
        self.assertNotAlmostEqual(float(market.levels.loc[dates[61], "oil"]), 55.0)
        self.assertFalse(bool(market.liquidity.loc[dates[60], "oil"]))
        self.assertTrue(bool(market.liquidity.loc[dates[61], "oil"]))
        self.assertTrue((market.signal["csi300"] == 0.0123).all())
        # 同一条路径再走 U-可交易。研究收益同样滞后；成交价是当天选定那只自己的收盘。
        traded = market_from_returns(signal, fees, liquidity=liquidity.copy())
        apply_market(
            traded, EngineSwitches(carriers=True), db=path, containers=containers, spec=spec,
            pool="tradable")
        self.assertTrue(pd.isna(traded.signal.loc[dates[60], "oil"]))
        self.assertAlmostEqual(float(traded.signal.loc[dates[61], "oil"]), 0.10)
        self.assertAlmostEqual(float(traded.fill_close["oil"].loc[dates[60]]), 50.0)
        self.assertNotAlmostEqual(float(traded.fill_close["oil"].loc[dates[60]]), 10.0)
        self.assertAlmostEqual(float(traded.fill_close["oil"].loc[dates[61]]), 55.0)
        self.assertAlmostEqual(float(traded.fill_prev["oil"].loc[dates[61]]), 50.0)


class SplicedFromCandidates(unittest.TestCase):
    def test_path_splice_uses_prior_day_carrier_then_the_new_fund(self):
        """D 日收益是 D−1 的载体。换日当天仍是旧基金，新基金从下一天起，且不拼价格。"""
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE v4_series (code TEXT, kind TEXT, date TEXT, close REAL)")
        days = pd.to_datetime(["2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09"])
        rows = []
        closes = {
            "510300": [10.0, 11.0, 12.0, 12.0],
            "159919": [100.0, 100.0, 80.0, 88.0],
        }
        for code, series in closes.items():
            for day, close in zip(days, series):
                rows.append((code, "backward", str(day.date()), close))
        con.executemany("INSERT INTO v4_series VALUES (?, ?, ?, ?)", rows)
        # 01-06 起 510300 掉出 3000 万，当天更新成 159919；01-09 510300 回到 1 亿也不换回。
        old = _candidate("510300", days, [80e6, 50e6, 10e6, 100e6])
        peer = _candidate("159919", days, [40e6, 90e6, 90e6, 90e6])
        selected = choose_path([old, peer], days)
        self.assertEqual([item.label for item in selected], [
            "etf:510300", "etf:510300", "etf:159919", "etf:159919"])
        earned = earning_path(selected)
        self.assertIsNone(earned[0])
        self.assertEqual([item.label for item in earned[1:]], [
            "etf:510300", "etf:510300", "etf:159919"])
        series = spliced_research(con, [old, peer], days, "2006-01-09", nav_lag=2)
        self.assertTrue(pd.isna(series.iloc[0]))
        self.assertAlmostEqual(float(series.iloc[1]), 0.10)
        # 01-06 已经换成 159919，但这天的收益仍是 510300 的 12/11−1，不是 159919 的 −20%。
        self.assertAlmostEqual(float(series.iloc[2]), 12.0 / 11.0 - 1.0)
        self.assertNotAlmostEqual(float(series.iloc[2]), -0.20)
        # 01-09 才开始计 159919 自己的 88/80−1，不是 88/12−1。
        self.assertAlmostEqual(float(series.iloc[3]), 88.0 / 80.0 - 1.0)
        self.assertNotAlmostEqual(float(series.iloc[3]), 88.0 / 12.0 - 1.0)


if __name__ == "__main__":
    unittest.main()
