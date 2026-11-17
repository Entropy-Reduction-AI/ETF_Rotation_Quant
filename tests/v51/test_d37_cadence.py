"""D37 节奏开关。默认必须和冻结路径同一套持仓。"""
from __future__ import annotations

import unittest

import pandas as pd

from src.v3.engine.sessions import decision_dates
from src.v51.allocate import allocate
from src.v51.d37_round3 import parse_nikkei_month
from src.v51.d37_plan_b import plan_b_markets, vs_rows
from src.v51.d37_round4 import catalogue_dates
from src.v51.universe import Market, Universe
from src.v51.s1_scope import (
    buyable_frame, calendar_index_returns, fx_series_for, listed_funds, rolling_amount_ok,
    series_truncated_at_listing, splice_before_list,
)
from src.v51.universe import Market, Universe, universe_s1
from tests.v51.test_allocate import _frames, _picks, _prices, _universe


class FrozenDefault(unittest.TestCase):
    def test_explicit_frozen_matches_the_default_path(self):
        index = pd.bdate_range("2015-02-02", periods=10)
        weeks = list(decision_dates(index, "week"))
        w0, w1 = weeks[0], weeks[1]
        between = [day for day in index if w0 < day < w1]
        names = ["m", "p", "q"]
        level, share, slow = _frames(index, names)
        level["p"] = -1.0
        level["q"] = -1.0
        share.loc[w0, "m"] = 0.8
        level.loc[between[1], "m"] = -1.0
        share.loc[between[1], ["p", "q"]] = 0.9
        universe = _universe(Market("A股", "m", tuple(names)))
        prices = _prices(index, names)
        base = allocate(index, level, share, slow, universe, prices=prices)
        frozen = allocate(index, level, share, slow, universe, prices=prices, cadence="frozen")
        pd.testing.assert_frame_equal(base.state, frozen.state)
        pd.testing.assert_frame_equal(base.decisions, frozen.decisions)
        pd.testing.assert_frame_equal(base.exits, frozen.exits)
        self.assertEqual(base.state.at[between[1], "market"], "")
        self.assertFalse(frozen.legs.empty)


class Cadence(unittest.TestCase):
    def _book(self, cadence: str):
        index = pd.bdate_range("2015-02-02", periods=12)
        weeks = list(decision_dates(index, "week"))
        w0, w1 = weeks[0], weeks[1]
        names = ["m", "a", "b", "n", "c", "d"]
        level, share, slow = _frames(index, names, height=1.0, share=0.1)
        level["m"] = 2.0
        level["n"] = 0.5
        half = index[index.get_loc(w0) + 1]
        zero = index[index.get_loc(w0) + 2]
        back = index[index.get_loc(w0) + 3]
        share.loc[half, ["a", "b"]] = 0.9
        share.loc[zero, ["a", "b"]] = 0.9
        level.loc[zero, "m"] = -1.0
        level.loc[index >= back, "n"] = 5.0
        universe = _universe(
            Market("A股", "m", ("m", "a", "b")),
            Market("美股", "n", ("n", "c", "d")),
        )
        book = allocate(
            index, level, share, slow, universe, prices=_prices(index, names), cadence=cadence,
        )
        return book, w0, w1, half, zero, back

    def test_weekly_does_not_change_rung_off_the_decision_day(self):
        book, w0, _w1, half, zero, _back = self._book("weekly")
        self.assertEqual(book.state.at[w0, "risk"], 1.0)
        self.assertEqual(book.state.at[half, "risk"], 1.0)
        self.assertEqual(book.state.at[zero, "market"], "m")
        self.assertEqual(book.state.at[zero, "risk"], 1.0)

    def test_resonance_keeps_a_half_cut_and_exits_only_at_zero(self):
        book, _w0, _w1, half, zero, _back = self._book("resonance")
        self.assertEqual(book.state.at[half, "risk"], 1.0)
        self.assertEqual(book.state.at[zero, "market"], "")
        self.assertEqual(book.state.at[zero, "risk"], 0.0)

    def test_daily_follows_the_score_up_and_back_into_the_same_market(self):
        book, _w0, w1, half, zero, back = self._book("daily")
        self.assertEqual(book.state.at[half, "risk"], 0.5)
        self.assertEqual(book.state.at[zero, "market"], "")
        self.assertEqual(book.state.at[back, "market"], "m")
        self.assertEqual(book.state.at[back, "risk"], 1.0)
        self.assertNotEqual(book.state.at[back, "market"], "n")
        self.assertEqual(book.state.at[w1, "market"], "n")

    def test_resonance_daily_skips_the_half_cut_and_adds_back(self):
        book, _w0, _w1, half, zero, back = self._book("resonance_daily")
        self.assertEqual(book.state.at[half, "risk"], 1.0)
        self.assertEqual(book.state.at[zero, "market"], "")
        self.assertEqual(book.state.at[back, "market"], "m")
        self.assertEqual(book.state.at[back, "risk"], 1.0)

    def test_reentry_does_not_buy_a_name_sold_by_the_frontier(self):
        index = pd.bdate_range("2015-06-01", periods=12)
        weeks = list(decision_dates(index, "week"))
        w0 = weeks[0]
        names = ["m", "a", "b", "c", "d"]
        level, share, slow = _frames(index, names, height=0.4, share=0.1)
        level["a"] = 4.0
        level["b"] = 3.0
        level["c"] = 2.0
        level["d"] = 1.0
        sell = index[index.get_loc(w0) + 1]
        flat = index[index.get_loc(w0) + 2]
        back = index[index.get_loc(w0) + 3]
        share.loc[sell, "a"] = 0.8
        share.loc[flat, "m"] = 0.9
        level.loc[flat, "m"] = -1.0
        book = allocate(
            index, level, share, slow,
            _universe(Market("A股", "m", tuple(names))),
            prices=_prices(index, names), cadence="daily",
        )
        self.assertEqual(_picks(book.state, w0), ["a", "b", "c"])
        self.assertNotIn("a", _picks(book.state, back))
        self.assertIn("b", _picks(book.state, back))


class Scope(unittest.TestCase):
    def test_s1_markets_skip_the_bond_and_keep_the_three_frozen_markets(self):
        names = ["csi300", "hsi", "spx", "soymeal", "theme-法国CAC40指数", "theme-巴克莱资本美国综合债券指数"]
        classes = {
            "csi300": "A股", "hsi": "港股", "spx": "美股", "soymeal": "商品",
            "theme-法国CAC40指数": "其他海外", "theme-巴克莱资本美国综合债券指数": "其他海外",
        }
        universe = universe_s1(names, classes)
        reps = [market.representative for market in universe.markets]
        self.assertEqual(reps[:3], ["csi300", "hsi", "spx"])
        self.assertIn("soymeal", reps)
        self.assertIn("theme-法国CAC40指数", reps)
        self.assertNotIn("theme-巴克莱资本美国综合债券指数", reps)
        self.assertIsInstance(universe, Universe)

    def test_splice_fills_only_the_hole_before_listing(self):
        index = pd.bdate_range("2015-01-05", periods=6)
        signal = pd.Series([float("nan"), float("nan"), 0.1, 0.2, float("nan"), 0.3], index=index)
        extra = pd.Series(0.01, index=index)
        got = splice_before_list(signal, extra, index[0], index[3])
        self.assertAlmostEqual(float(got.iloc[0]), 0.01)
        self.assertAlmostEqual(float(got.iloc[2]), 0.1)
        self.assertTrue(pd.isna(got.iloc[4]))

    def test_listing_day_uses_whatever_amount_days_exist(self):
        calendar = pd.bdate_range("2019-12-02", periods=8)
        opened = calendar[1]
        amounts = pd.Series([3_000_000.0, 100_000.0], index=[opened, calendar[2]])
        flag = rolling_amount_ok(amounts, opened, calendar)
        self.assertFalse(bool(flag.loc[calendar[0]]))
        self.assertTrue(bool(flag.loc[opened]))
        self.assertFalse(bool(flag.loc[calendar[2]]))
        thin = pd.Series([100.0] * 5, index=calendar[:5])
        self.assertFalse(bool(rolling_amount_ok(thin, calendar[0], calendar).iloc[-1]))

    def test_buyable_frame_accepts_any_listed_fund(self):
        calendar = pd.bdate_range("2019-12-02", periods=4)
        opened = pd.Timestamp(calendar[1]).strftime("%Y-%m-%d")
        container = {"execution": [
            {"code": "159985", "list_date": opened, "name": "豆粕ETF"},
            {"code": "000001", "list_date": "取不到", "name": "场外"},
        ]}
        funds = listed_funds(container)
        self.assertEqual([fund.code for fund in funds], ["159985"])
        amounts = pd.Series([2_500_000.0], index=[calendar[1]])
        frame = buyable_frame(calendar, {"soymeal": [(funds[0], amounts)]})
        self.assertTrue(bool(frame.at[calendar[1], "soymeal"]))
        self.assertFalse(bool(frame.at[calendar[0], "soymeal"]))

    def test_listing_truncation_keeps_a_series_that_already_starts_earlier(self):
        self.assertTrue(series_truncated_at_listing("2021-04-08", "2019-06-25"))
        self.assertTrue(series_truncated_at_listing("2022-11-02", "2022-12-22"))
        self.assertTrue(series_truncated_at_listing("", "2019-12-05"))
        self.assertFalse(series_truncated_at_listing("2020-07-27", "2021-05-25"))
        self.assertFalse(series_truncated_at_listing("2020-07-27", ""))

    def test_nikkei_month_table_parses_official_columns(self):
        html = """
        <tr>
            <td>2019.01.04</td>
            <td>19,655.13</td>
            <td>19,692.58</td>
            <td>19,241.37</td>
            <td>19,561.96</td>
        </tr>
        """
        rows = parse_nikkei_month(html)
        self.assertEqual(rows[0]["date"], "2019-01-04")
        self.assertEqual(rows[0]["open"], "19655.13")
        self.assertEqual(rows[0]["close"], "19561.96")

    def test_usd_index_return_uses_the_fx_level_on_the_decision_calendar(self):
        calendar = pd.bdate_range("2016-01-04", periods=6)
        closes = pd.Series([100.0, 110.0], index=[calendar[0] - pd.Timedelta(days=3), calendar[0]])
        fx = pd.Series([6.0, 6.0], index=[calendar[0] - pd.Timedelta(days=3), calendar[0]])
        got = calendar_index_returns(closes, calendar, fx)
        self.assertEqual(list(got.index), list(pd.DatetimeIndex(calendar).normalize()))
        self.assertTrue(got.iloc[1:].notna().any())

    def test_jpy_mid_rate_is_quoted_per_hundred_yen(self):
        raw = pd.Series([4.9788, 5.0], index=pd.to_datetime(["2024-01-04", "2024-01-05"]))
        got = fx_series_for("JPY", lambda code: raw if code == "JPYCNY" else None)
        self.assertAlmostEqual(float(got.iloc[0]), 4.9788 / 100)
        self.assertIsNone(fx_series_for("LOCAL", lambda code: raw))

    def test_catalogue_line_keeps_launch_not_base_date(self):
        text = (
            "Hang Seng SCHK 50 Index 恒生港股通50指数 .HSSC50 - 31-12-2021 13-01-2025\n"
            "Hang Seng SCHK Telecommunications .HSSCTU - 31-12-2020 17-07-2023\n"
        )
        base, launch = catalogue_dates(text, "HSSC50")
        self.assertEqual(base, "2021-12-31")
        self.assertEqual(launch, "2025-01-13")
        self.assertIsNone(catalogue_dates(text, "HSSCT"))

    def test_plan_b_counts_markets_and_splits_contribution(self):
        index = pd.to_datetime(["2016-01-04", "2016-01-05"])
        held = pd.DataFrame({"a": [0.5, 0.0], "b": [0.5, 1.0]}, index=index)
        pnl = pd.DataFrame({"a": [0.1, 0.0], "b": [0.0, 0.2]}, index=index)
        state = pd.DataFrame({"market": ["m1|m2", "m2"]}, index=index)
        universe = Universe(
            (Market("甲", "a", ("a",)), Market("乙", "b", ("b",))),
            bond="bond", gold="gold", cash="cash",
        )
        table, summary = plan_b_markets(held, pnl, state, universe)
        self.assertEqual(summary["avg_markets_per_day"], 1.5)
        self.assertEqual(summary["market_days"], {"0": 0, "1": 1, "2": 1})
        by = dict(zip(table["market"], table["contribution"]))
        self.assertAlmostEqual(by["甲"], 0.05)
        self.assertAlmostEqual(by["乙"], 0.2)

    def test_vs_v0_subtracts_the_same_segment(self):
        rows = vs_rows(
            {"ann": 0.1, "max_drawdown": -0.2, "trades": 10, "trades_per_year": 1.0, "cost": 0.05, "cost_per_year": 0.01},
            {"ann": 0.3, "max_drawdown": -0.4, "trades": 4, "trades_per_year": 0.4, "cost": 0.02, "cost_per_year": 0.004},
        )
        by = {row["metric"]: row["B_minus_V0"] for row in rows}
        self.assertAlmostEqual(by["ann"], -0.2)
        self.assertAlmostEqual(by["max_drawdown"], 0.2)
        self.assertEqual(by["trades"], 6)


if __name__ == "__main__":
    unittest.main()
