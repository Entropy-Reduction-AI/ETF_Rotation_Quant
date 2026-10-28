"""v4-R2c。手造序列。不跑候选组合收益，也不汇总 2016 年以后的收益。"""
from __future__ import annotations

import sqlite3
import unittest

import pandas as pd

from src.v3.engine.benchmark import WEIGHTS
from src.v3.engine.exit import _fill_due_refills
from src.v3.engine.limits import FillQuote, fill_board_for, session_tradable
from src.v3.engine.market import _usd_level, index_pool_fill_close
from src.v3.engine.regime import efficiency_series, percentile_q
from src.v3.engine.spec import load_spec
from src.v4.engine.carriers import _Candidate, build_candidates, choose_on, stitch_fills
from src.v4.engine.pool import _hk_level

from tests.v3.engine.test_v4_r2 import FEE, _book, _days, _quote


class SessionClock(unittest.TestCase):
    def test_hk_uses_today_and_us_leg_of_bm_uses_the_prior_close(self):
        """D18-1。BM-主 权重没有港股；和它同一条决策日上的港股用 D 当天，美股腿用前一收盘。"""
        self.assertEqual(set(WEIGHTS), {"H00300", "XNDX", "SP500TR"})
        days = pd.to_datetime(["2006-01-04", "2006-01-05", "2006-01-06"])
        closes = [100.0, 130.0, 90.0]
        frame = pd.DataFrame({"date": days, "open": closes, "close": closes})
        fx = pd.Series([0.8, 0.9, 1.0], index=days)
        spec = load_spec()
        hk, _fresh, _gaps = _hk_level("HSI", {"HSI": frame}, days, spec, fx, same_day=True)
        us, _us_fresh, _us_gaps = _usd_level(frame, fx, days, spec.stale_limit, None)
        # 1 月 5 日：港股用当天 130，不乘前一天的 100。汇率用当天或之前，这里就是 0.9。
        self.assertAlmostEqual(float(hk.loc[days[1]]), 130.0 * 0.9)
        self.assertNotAlmostEqual(float(hk.loc[days[1]]), 100.0 * 0.9)
        # 美股：严格早于 D，所以用 1 月 4 日的 100，再乘 1 月 5 日的汇率。
        self.assertAlmostEqual(float(us.loc[days[1]]), 100.0 * 0.9)
        self.assertNotAlmostEqual(float(us.loc[days[1]]), 130.0 * 0.9)
        # 港股休市：1 月 5 日没有打印，沿用 1 月 4 日收盘。
        holiday = frame.iloc[[0, 2]]
        halted, _hfresh, _hgaps = _hk_level("HSI", {"HSI": holiday}, days, spec, fx, same_day=True)
        self.assertAlmostEqual(float(halted.loc[days[1]]), 100.0 * 0.9)

    def test_old_pool_hsi_same_day_is_the_b0_default(self):
        days = pd.to_datetime(["2006-01-04", "2006-01-05"])
        frame = pd.DataFrame({"date": days, "open": [10.0, 12.0], "close": [10.0, 12.0]})
        spec = load_spec()
        level, _fresh, _gaps = _hk_level("HSI", {"HSI": frame}, days, spec, None, same_day=True)
        self.assertAlmostEqual(float(level.loc[days[1]]), 12.0)
        lagged, _lfresh, _lgaps = _hk_level("HSI", {"HSI": frame}, days, spec, None, same_day=False)
        self.assertAlmostEqual(float(lagged.loc[days[1]]), 10.0)


class TierBreak(unittest.TestCase):
    def test_same_tier_uses_median_then_code_and_falls_through(self):
        day = pd.Timestamp("2006-06-01")
        index = pd.DatetimeIndex([day])
        on = pd.Series([True], index=index)

        def etf(code, median, order):
            return _Candidate(
                container="csi300", code=code, vehicle="etf", tier=1,
                inception="", nav_start="", order=order, available=on,
                median=pd.Series([median], index=index), board="main")

        # 登记顺序把小成交额放前面。成交额高的优先，和登记顺序无关。
        picked = choose_on([etf("159919", 40e6, 0), etf("510300", 80e6, 1)], day)
        self.assertEqual(picked.label, "etf:510300")
        # 中位数相同，代码升序。
        tied = choose_on([etf("510300", 50e6, 0), etf("159919", 50e6, 1)], day)
        self.assertEqual(tied.label, "etf:159919")
        # 两只都不到 3000 万时不在可用名单里，落到第 2 档联接。
        feeder = _Candidate(
            container="csi300", code="000311", vehicle="otc", tier=2,
            inception="2005-01-04", nav_start="2005-01-04", order=0,
            available=on, median=pd.Series(dtype=float), board="none")
        cold = choose_on([feeder], day)
        self.assertEqual(cold.label, "otc:000311")
        self.assertEqual(cold.board, "none")

    def test_feeder_is_tier_2_and_illiquid_etf_steps_down(self):
        con = sqlite3.connect(":memory:")
        dates = pd.bdate_range("2006-01-02", periods=150)
        con.execute("CREATE TABLE bars (code TEXT, adj TEXT, date TEXT, close REAL, amount REAL)")
        con.execute(
            "CREATE TABLE v4_series (code TEXT, kind TEXT, date TEXT, close REAL)")
        con.execute(
            "CREATE TABLE v4_listing (code TEXT, name TEXT, maps_to TEXT, tracked_index TEXT, "
            "inception TEXT, enhanced INTEGER)")
        rows = []
        for i, day in enumerate(dates):
            text = str(day.date())
            rows.append(("H00300", "raw", text, 1000.0, None))
            high = 90_000_000.0 if i < 80 else 1_000_000.0
            peer = 50_000_000.0 if i < 110 else 1_000_000.0
            rows.append(("510300", "raw", text, 3.0, high))
            rows.append(("159919", "raw", text, 3.0, peer))
        con.executemany("INSERT INTO bars VALUES (?, ?, ?, ?, ?)", rows)
        backward = [(code, "backward", str(day.date()), 3.0) for code in ("510300", "159919") for day in dates]
        nav = [("000311", "otc_nav", str(day.date()), 1.2) for day in dates]
        con.executemany("INSERT INTO v4_series VALUES (?, ?, ?, ?)", backward + nav)
        con.executemany(
            "INSERT INTO v4_listing VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("000311", "某某沪深300联接", "csi300", "沪深300指数", "2005-03-01", 0),
                ("000312", "某某沪深300增强联接", "csi300", "沪深300指数", "2005-03-01", 1),
            ])
        containers = [{
            "id": "csi300", "arm": "main", "asset_class": "A股宽基",
            "execution": [
                {"code": "159919", "track": "沪深300指数", "name": "先登记"},
                {"code": "510300", "track": "沪深300指数", "name": "后登记"},
            ],
        }]
        grouped = build_candidates(con, containers, dates, str(dates[-1].date()))
        liquid = choose_on(grouped["csi300"], dates[70])
        peer = choose_on(grouped["csi300"], dates[100])
        feeder = choose_on(grouped["csi300"], dates[140])
        self.assertEqual(liquid.label, "etf:510300")
        self.assertEqual(peer.label, "etf:159919")
        self.assertEqual(feeder.label, "otc:000311")
        codes = [item.code for item in grouped["csi300"]]
        self.assertNotIn("000312", codes)
        self.assertIn("000311", codes)


class SameDaySellThenBuy(unittest.TestCase):
    def test_blocked_name_keeps_the_quota(self):
        day = pd.Timestamp("2006-01-10")
        weights = {"hot": 0.0, "next": 0.0, "cash": 0.5}
        order = {
            "proceeds": 0.5, "exclude": set(), "filled": {}, "armed": True,
            "target": {"hot": 0.3, "next": 0.3, "cash": 0.4},
        }
        quotes = {
            "hot": _quote("main", ["2006-01-09", "2006-01-10"], [10.0, 11.0]),
            "next": _quote("main", ["2006-01-09", "2006-01-10"], [10.0, 10.1]),
        }
        refills = [order]
        deferred = []
        _fill_due_refills(
            weights, refills, day, "cash",
            {"hot": FEE, "next": FEE, "cash": 0.0005},
            True, quotes, ["hot", "next", "cash"], 1e-12, 1e-6,
            {}, lambda *_args: 1.0, deferred)
        self.assertAlmostEqual(weights["hot"], 0.0)
        self.assertAlmostEqual(weights["next"], 0.0)
        self.assertAlmostEqual(weights["cash"], 0.5)
        self.assertEqual(len(refills), 1)
        self.assertAlmostEqual(refills[0]["proceeds"], 0.5)
        self.assertIn("refill_blocked", {row["reason"] for row in deferred})

    def test_same_day_sell_does_not_fund_or_reenter_the_refill(self):
        days = _days("2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09", "2006-01-10", "2006-01-11")
        levels = pd.DataFrame({
            "asset": [100, 100, 80, 80, 80, 80],
            "stuck": [100, 100, 100, 80, 80, 80],
            "nxt": [50, 50, 50, 50, 50, 50],
        }, index=days)
        rets = pd.DataFrame({
            "asset": [0, 0, -0.2, 0, 0, 0],
            "stuck": [0, 0, 0, -0.2, 0, 0],
            "nxt": [0, 0, 0, 0, 0, 0],
        }, index=days)
        sleeve = pd.DataFrame({
            "asset": 0.0, "stuck": 0.0, "nxt": 1.0, "cash": 0.0,
        }, index=days)
        booked = _book(
            ["asset", "stuck", "nxt"], levels, rets,
            {"2006-01-04": {"asset": 0.5, "stuck": 0.5, "nxt": 0.0, "cash": 0.0}},
            refill_targets=sleeve,
        )
        # 01-10 先卖掉 stuck，再买 nxt。nxt 的目标是 100%，但只能用 asset 已经卖出的现金，
        # stuck 刚卖出的部分留在现金里，次日开盘还能看到。
        after = booked.held.loc[days[5]]
        self.assertAlmostEqual(float(after["stuck"]), 0.0)
        self.assertGreater(float(after["nxt"]), 0.2)
        self.assertGreater(float(after["cash"]), 0.2)
        self.assertLess(float(after["nxt"]), 0.7)


class ResearchLimit(unittest.TestCase):
    def test_index_pool_a_share_uses_the_research_close(self):
        dates = pd.to_datetime(["2006-01-04", "2006-01-05"])
        research = pd.Series([10.0, 11.0], index=dates)
        traded = pd.Series([10.0, 10.1], index=dates)
        chosen = index_pool_fill_close("index", "A股宽基", research, traded)
        quote = FillQuote(close=chosen, board="main")
        flags = session_tradable({"csi300": quote}, dates[1], ["csi300"])
        self.assertEqual(flags["csi300"], (False, True))
        other = index_pool_fill_close("tradable", "A股宽基", research, traded)
        quiet = session_tradable(
            {"csi300": FillQuote(close=other, board="main")}, dates[1], ["csi300"])
        self.assertEqual(quiet["csi300"][0], True)
        self.assertEqual(fill_board_for("恒生指数", "159920", "港股"), "none")
        self.assertEqual(fill_board_for("纳斯达克100", "513100", "美股宽基"), "none")
        self.assertEqual(fill_board_for("创业板指数", "159915", "A股宽基"), "chinext")

    def test_tradable_carrier_quote_uses_that_names_own_close(self):
        day = pd.Timestamp("2006-01-05")
        earlier = pd.Timestamp("2006-01-04")
        index = pd.DatetimeIndex([day])
        on = pd.Series([True], index=index)
        etf = _Candidate(
            container="csi300", code="510300", vehicle="etf", tier=1,
            inception="", nav_start="", order=0, available=on,
            median=pd.Series([80e6], index=index), board="main")
        prints = {
            "510300": pd.Series([10.0, 10.2], index=pd.DatetimeIndex([earlier, day])),
        }
        stitched = stitch_fills({"csi300": [etf]}, index, prints, {"csi300": "A股宽基"})
        self.assertAlmostEqual(float(stitched["csi300"].close.loc[day]), 10.2)
        self.assertAlmostEqual(float(stitched["csi300"].prev.loc[day]), 10.0)
        self.assertEqual(stitched["csi300"].board.loc[day], "main")
        us = _Candidate(
            container="us-xlk", code="XLK", vehicle="spdr", tier=4,
            inception="", nav_start="", order=0, available=on,
            median=pd.Series(dtype=float), board="none")
        us_prints = {"XLK": pd.Series([20.0, 30.0], index=pd.DatetimeIndex([earlier, day]))}
        us_fill = stitch_fills({"us-xlk": [us]}, index, us_prints, {"us-xlk": "美股行业"})
        self.assertAlmostEqual(float(us_fill["us-xlk"].close.loc[day]), 20.0)
        self.assertEqual(us_fill["us-xlk"].board.loc[day], "none")


class DenominatorAndRank(unittest.TestCase):
    def test_zero_path_is_zero_and_ties_are_not_strictly_less(self):
        flat = pd.Series([8.0, 8.0, 8.0, 8.0], index=pd.bdate_range("2006-01-02", periods=4))
        efficiency = efficiency_series(flat, 2)
        self.assertEqual(float(efficiency.iloc[2]), 0.0)
        self.assertEqual(float(efficiency.iloc[3]), 0.0)
        tied = pd.Series([0.4, 0.4, 0.5], index=pd.bdate_range("2006-01-02", periods=3))
        q = percentile_q(tied, min_history=1)
        self.assertAlmostEqual(float(q.iloc[1]), 0.0)
        self.assertAlmostEqual(float(q.iloc[2]), 1.0)


if __name__ == "__main__":
    unittest.main()
