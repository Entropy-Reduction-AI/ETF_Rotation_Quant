"""成交复用 v4 B0 的入口。手造行情，停在设计期内。"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

import pandas as pd

from src.v3.engine.book import RunnerError
from src.v3.engine.market import market_from_returns
from src.v4.r5.design import prior_positive
from src.v51.allocate import target_weights
from src.v51.execute import open_market, run_book
from src.v51.params import V51Error
from src.v51.universe import Market, Universe


def _spec():
    return SimpleNamespace(trade_eps=1e-12, weight_eps=1e-6, lookbacks=(20, 60, 120, 250))


def _market(frame: pd.DataFrame, fees: dict[str, float]):
    market = market_from_returns(frame, fees)
    close = pd.Series(10.0, index=frame.index)
    quotes = {}
    boards = {}
    prevs = {}
    for name in frame.columns:
        if name == "cash":
            continue
        quotes[name] = close
        boards[name] = "none"
        prevs[name] = prior_positive(close)
    market.fill_close = quotes
    market.fill_board = boards
    market.fill_prev = prevs
    return market


class Execute(unittest.TestCase):
    def test_targets_go_through_the_shared_fill(self):
        index = pd.bdate_range("2015-03-02", periods=10)
        names = ["csi300", "other", "cgb-10y", "gold", "cash"]
        frame = pd.DataFrame(0.0, index=index, columns=names)
        universe = Universe(
            (Market("A股", "csi300", ("csi300", "other")),),
            bond="cgb-10y", gold="gold", cash="cash",
        )
        decisions = target_weights(frame, universe).decisions
        self.assertIn("cgb-10y", decisions.columns)
        self.assertAlmostEqual(float(decisions["cgb-10y"].iloc[0]), 1.0)
        fees = {name: 0.001 if name != "cash" else 0.0 for name in names}
        book = run_book(_market(frame, fees), _spec(), decisions)
        self.assertGreater(float(book.held["cgb-10y"].max()), 0.9)
        self.assertGreater(float(book.cost.sum()), 0.0)

    def test_crash_is_not_liquidated_by_the_old_exit(self):
        index = pd.bdate_range("2015-03-02", periods=8)
        frame = pd.DataFrame({"asset": 0.0, "cash": 0.0}, index=index)
        frame.iloc[4, frame.columns.get_loc("asset")] = -0.2
        decisions = pd.DataFrame({"asset": [1.0], "cash": [0.0]}, index=pd.DatetimeIndex([index[0]]))
        fees = {"asset": 0.001, "cash": 0.0}
        book = run_book(_market(frame, fees), _spec(), decisions)
        self.assertGreater(float(book.held["asset"].iloc[-1]), 0.5)
        self.assertTrue(book.exits is None or book.exits.empty)
        self.assertGreater(float(book.buy.sum()), 0.0)

    def test_delay_uses_the_v5_path(self):
        index = pd.bdate_range("2015-03-02", periods=8)
        frame = pd.DataFrame({"asset": 0.0, "cash": 0.0}, index=index)
        decisions = pd.DataFrame({"asset": [1.0], "cash": [0.0]}, index=pd.DatetimeIndex([index[0]]))
        fees = {"asset": 0.0, "cash": 0.0}
        market = _market(frame, fees)
        base = run_book(market, _spec(), decisions)
        late = run_book(market, _spec(), decisions, decision_delay=1)

        def first_day(book):
            held = book.held["asset"]
            return held[held > 0.5].index[0]

        self.assertGreater(first_day(late), first_day(base))

    def test_refuses_2016_and_unknown_pools(self):
        index = pd.bdate_range("2016-01-04", periods=5)
        frame = pd.DataFrame({"asset": 0.0, "cash": 0.0}, index=index)
        decisions = pd.DataFrame({"cash": [1.0]}, index=pd.DatetimeIndex([index[0]]))
        with self.assertRaises(RunnerError):
            run_book(_market(frame, {"asset": 0.0, "cash": 0.0}), _spec(), decisions)
        with self.assertRaises(V51Error):
            open_market("nope", _spec())
