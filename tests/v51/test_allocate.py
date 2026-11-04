"""§3 持仓。宽度、国债、卖后不买回、同分、硬闸门。"""
from __future__ import annotations

import unittest

import pandas as pd

from src.v3.engine.book import RunnerError
from src.v3.engine.sessions import decision_dates
from src.v51.allocate import allocate, breadth
from src.v51.universe import Market, Universe


def _universe(*markets: Market, bond: str = "cgb-10y", gold: str = "gold", cash: str = "cash") -> Universe:
    return Universe(tuple(markets), bond=bond, gold=gold, cash=cash)


def _frames(index, names, *, height=1.0, share=0.0, slow=0.0):
    return (
        pd.DataFrame(height, index=index, columns=list(names), dtype=float),
        pd.DataFrame(share, index=index, columns=list(names), dtype=float),
        pd.DataFrame(slow, index=index, columns=list(names), dtype=float),
    )


def _prices(index, names, value=100.0) -> pd.DataFrame:
    return pd.DataFrame(value, index=index, columns=list(names), dtype=float)


def _picks(state: pd.DataFrame, day) -> list[str]:
    text = state.at[day, "picks"]
    return [] if not text else str(text).split("|")


class Breadth(unittest.TestCase):
    def test_width_is_missing_below_three_containers(self):
        index = pd.bdate_range("2015-04-01", periods=5)
        thin = pd.DataFrame({"a": 0.1, "b": 0.9}, index=index)
        self.assertTrue(pd.isna(breadth(thin, ("a", "b")).iloc[-1]))
        wide = thin.copy()
        wide["c"] = 0.5
        found = breadth(wide, ("a", "b", "c"))
        self.assertAlmostEqual(float(found.iloc[-1]), 2.0 / 3.0)
        edge = pd.DataFrame({"a": 0.1, "b": 0.5, "c": 0.49}, index=index)
        self.assertAlmostEqual(float(breadth(edge, ("a", "b", "c")).iloc[-1]), 1.0 / 3.0)

    def test_missing_width_does_not_close_the_first_leg(self):
        index = pd.bdate_range("2015-04-06", periods=5)
        week = list(decision_dates(index, "week"))[-1]
        level, share, slow = _frames(index, ("m", "n"))
        thin = allocate(index, level, share, slow, _universe(Market("A股", "m", ("m", "n"))), prices=_prices(index, ("m", "n")))
        self.assertEqual(thin.state.at[week, "market"], "m")
        self.assertEqual(thin.state.at[week, "risk"], 1.0)

        level3, share3, slow3 = _frames(index, ("m", "n", "o"))
        share3["n"] = 0.9
        share3["o"] = 0.9
        blocked = allocate(
            index, level3, share3, slow3,
            _universe(Market("A股", "m", ("m", "n", "o"))),
            prices=_prices(index, ("m", "n", "o")),
        )
        self.assertEqual(blocked.state.at[week, "risk"], 0.5)


class Defense(unittest.TestCase):
    def test_bond_is_held_when_its_readings_are_missing(self):
        index = pd.bdate_range("2015-04-06", periods=10)
        weeks = list(decision_dates(index, "week"))
        names = ["m", "cgb-10y", "gold"]
        level, share, slow = _frames(index, names, height=float("nan"), share=float("nan"), slow=float("nan"))
        returns = pd.DataFrame(0.0, index=index, columns=names + ["cash"])
        returns.loc[index > weeks[0], "cgb-10y"] = float("nan")
        book = allocate(
            index, level, share, slow,
            _universe(Market("A股", "m", ("m",))),
            prices=_prices(index, names),
            returns=returns,
        )
        self.assertEqual(book.state.at[weeks[0], "defense"], "cgb-10y")
        self.assertEqual(book.state.at[weeks[0], "risk"], 0.0)
        self.assertAlmostEqual(float(book.decisions.loc[weeks[0], "cgb-10y"]), 1.0)
        monday = index[index.get_loc(weeks[0]) + 1]
        self.assertLess(monday, weeks[1])
        self.assertEqual(book.state.at[monday, "defense"], "cgb-10y")
        self.assertEqual(book.state.at[weeks[1], "defense"], "cash")
        self.assertAlmostEqual(float(book.decisions.loc[weeks[1], "cash"]), 1.0)


class Replacement(unittest.TestCase):
    def test_names_sold_this_week_are_not_bought_back(self):
        index = pd.bdate_range("2015-06-01", periods=20)
        weeks = list(decision_dates(index, "week"))
        self.assertGreaterEqual(len(weeks), 4)
        w0, w1, w2, w3 = weeks[:4]
        names = ["m", "a", "b", "c", "d"]
        level, share, slow = _frames(index, names, height=0.2)
        level["a"] = 4.0
        level["b"] = 3.0
        level["c"] = 2.0
        level["d"] = 1.0
        share[:] = 0.1
        sell_a = index[index.get_loc(w0) + 1]
        share.loc[sell_a, "a"] = 0.5
        share.loc[w1, "b"] = 0.5
        book = allocate(
            index, level, share, slow,
            _universe(Market("A股", "m", tuple(names))),
            prices=_prices(index, names),
        )
        self.assertEqual(_picks(book.state, w0), ["a", "b", "c"])
        self.assertNotIn("a", _picks(book.state, sell_a))
        self.assertIn("d", _picks(book.state, sell_a))
        self.assertIn("a", set(book.state.at[sell_a, "blocked"].split("|")))
        sold = book.exits[(book.exits["t"] == sell_a) & (book.exits["id"] == "a")]
        self.assertEqual(sold["why"].tolist(), ["F"])
        self.assertNotIn("a", _picks(book.state, w1))
        self.assertNotIn("b", _picks(book.state, w1))
        self.assertEqual(
            book.exits[(book.exits["t"] == w1) & (book.exits["id"] == "b")]["why"].tolist(),
            ["F"],
        )
        self.assertEqual(_picks(book.state, w2), ["a", "c", "d"])
        self.assertEqual(_picks(book.state, w3), ["a", "b", "c"])

    def test_ties_break_on_container_id(self):
        index = pd.bdate_range("2015-05-04", periods=5)
        week = list(decision_dates(index, "week"))[-1]
        names = ("d", "a", "c", "b")
        level, share, slow = _frames(index, names)
        book = allocate(
            index, level, share, slow,
            _universe(Market("A股", "a", names)),
            prices=_prices(index, names),
        )
        self.assertEqual(_picks(book.state, week), ["a", "b", "c"])

    def test_hard_gate_fires_while_frontier_is_still_open(self):
        index = pd.bdate_range("2015-06-01", periods=15)
        weeks = list(decision_dates(index, "week"))
        w0 = weeks[0]
        names = ["m", "x", "y"]
        level, share, slow = _frames(index, names, height=0.3, share=0.2)
        level["x"] = 2.0
        level["y"] = 1.0
        prices = _prices(index, names)
        peak_day = index[index.get_loc(w0) + 1]
        exact = index[index.get_loc(w0) + 2]
        crash = index[index.get_loc(w0) + 3]
        prices.loc[exact, "x"] = 90.0
        prices.loc[crash, "x"] = 89.0
        book = allocate(
            index, level, share, slow,
            _universe(Market("A股", "m", tuple(names))),
            prices=prices,
        )
        self.assertIn("x", _picks(book.state, exact))
        self.assertTrue(book.exits[(book.exits["t"] == exact) & (book.exits["id"] == "x")].empty)
        hit = book.exits[(book.exits["t"] == crash) & (book.exits["id"] == "x")]
        self.assertEqual(hit["why"].tolist(), ["硬闸门"])
        self.assertLess(float(share.at[crash, "x"]), 0.5)
        self.assertNotIn("x", _picks(book.state, crash))
        self.assertNotIn("x", _picks(book.state, weeks[1]))
        self.assertIn("x", _picks(book.state, weeks[2]))


class Schedule(unittest.TestCase):
    def test_daily_path_only_reduces_and_waits_for_the_next_week(self):
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
        book = allocate(
            index, level, share, slow,
            _universe(Market("A股", "m", tuple(names))),
            prices=_prices(index, names),
        )
        self.assertEqual(book.state.at[w0, "risk"], 0.5)
        self.assertEqual(book.state.at[between[0], "risk"], 0.5)
        self.assertEqual(book.state.at[between[1], "market"], "")
        self.assertEqual(
            book.exits[(book.exits["t"] == between[1]) & (book.exits["id"] == "m")]["why"].tolist(),
            ["市场退出"],
        )
        self.assertEqual(book.state.at[between[2], "market"], "")
        self.assertEqual(book.state.at[w1, "market"], "m")
        self.assertEqual(book.state.at[w1, "risk"], 1.0)

    def test_noise_band_keeps_the_held_market_until_the_weekly_decision(self):
        index = pd.bdate_range("2015-03-02", periods=15)
        weeks = list(decision_dates(index, "week"))
        w0, w1, w2 = weeks[:3]
        names = ["a0", "a1", "a2", "b0", "b1", "b2"]
        level, share, slow = _frames(index, names, height=0.5)
        level.loc[index <= w0, "a0"] = 3.0
        level.loc[index <= w0, "b0"] = 1.0
        level.loc[(index > w0) & (index <= w1), "a0"] = 2.0
        level.loc[(index > w0) & (index <= w1), "b0"] = 3.0
        level.loc[index > w1, "a0"] = 2.0
        level.loc[index > w1, "b0"] = 4.0
        book = allocate(
            index, level, share, slow,
            _universe(
                Market("A股", "a0", ("a0", "a1", "a2")),
                Market("美股", "b0", ("b0", "b1", "b2")),
            ),
            prices=_prices(index, names),
        )
        self.assertEqual(book.state.at[w0, "market"], "a0")
        self.assertEqual(book.state.at[w1, "market"], "a0")
        day_before = index[index.get_loc(w2) - 1]
        self.assertEqual(book.state.at[day_before, "market"], "a0")
        self.assertEqual(book.state.at[w2, "market"], "b0")

    def test_market_without_a_buyable_name_is_skipped(self):
        index = pd.bdate_range("2015-05-04", periods=5)
        week = list(decision_dates(index, "week"))[-1]
        names = ["a0", "a1", "a2", "b0", "b1", "b2"]
        level, share, slow = _frames(index, names, height=1.0)
        level["b0"] = 10.0
        eligible = pd.DataFrame(True, index=index, columns=names)
        eligible[["b0", "b1", "b2"]] = False
        book = allocate(
            index, level, share, slow,
            _universe(
                Market("A股", "a0", ("a0", "a1", "a2")),
                Market("美股", "b0", ("b0", "b1", "b2")),
            ),
            prices=_prices(index, names),
            eligible=eligible,
        )
        self.assertEqual(book.state.at[week, "market"], "a0")

    def test_representative_without_a_carrier_uses_the_highest_buyable_name(self):
        index = pd.bdate_range("2015-05-04", periods=5)
        week = list(decision_dates(index, "week"))[-1]
        names = ["m", "y", "z"]
        level, share, slow = _frames(index, names, height=3.0, share=0.9)
        level["m"] = 9.0
        level["z"] = 5.0
        eligible = pd.DataFrame(True, index=index, columns=names)
        eligible["m"] = False
        book = allocate(
            index, level, share, slow,
            _universe(Market("A股", "m", tuple(names))),
            prices=_prices(index, names),
            eligible=eligible,
        )
        self.assertEqual(_picks(book.state, week), ["z"])
        self.assertEqual(book.state.at[week, "market"], "m")

    def test_refuses_the_contaminated_window(self):
        index = pd.bdate_range("2016-01-04", periods=5)
        level, share, slow = _frames(index, ("m",))
        with self.assertRaises(RunnerError):
            allocate(index, level, share, slow, _universe(Market("A股", "m", ("m",))))
