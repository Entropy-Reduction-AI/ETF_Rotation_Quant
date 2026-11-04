"""R1 抽取、换手拆分、稳健性开关和入围结论。不跑 2000 次，不跑 S1–S17。"""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.v3.engine.book import simulate, to_execution
from src.v3.engine.sessions import decision_dates
from src.v51.allocate import allocate
from src.v51.gate import conclude
from src.v51.params import V51Error
from src.v51.robustness import knobs, rank_best
from src.v51.structure import Slot, draw_paths, portfolio_nets
from src.v51.turnover import split_trade, target_weights
from src.v51.universe import Market, Universe


def _universe() -> Universe:
    return Universe((
        Market("A股", "a", ("a", "a2", "a3")),
        Market("港股", "h", ("h", "h2")),
    ), bond="cgb-10y", gold="gold", cash="cash")


def _slot(**kwargs) -> Slot:
    base = dict(
        date=pd.Timestamp("2015-06-05"), weekly=True, risk=1.0, defense="cash",
        market="a", picks=("a",), markets=("a", "h"),
        pools=(("a", "a2", "a3"), ("h", "h2")), fallback=(None, None),
    )
    base.update(kwargs)
    return Slot(**base)


class SameStructure(unittest.TestCase):
    def test_weekly_redraws_and_midweek_keeps_the_names(self):
        slots = [
            _slot(date=pd.Timestamp("2015-06-05"), weekly=True, risk=1.0),
            _slot(date=pd.Timestamp("2015-06-08"), weekly=False, risk=0.5, defense="cgb-10y", markets=(), pools=(), fallback=()),
            _slot(date=pd.Timestamp("2015-06-12"), weekly=True, risk=0.0, defense="cash", markets=(), pools=(), fallback=()),
        ]
        paths = draw_paths(slots, n=2, seed=20261101, top_n=1)
        self.assertEqual(len(paths), 2)
        first = paths[0]
        rng = np.random.default_rng(20261101)
        market = str(rng.choice(np.array(["a", "h"]), size=1, replace=False)[0])
        pool = np.array(["a", "a2", "a3"] if market == "a" else ["h", "h2"])
        picked = [str(rng.choice(pool, size=1, replace=False)[0])]
        self.assertEqual(first[0]["market"], market)
        self.assertEqual(first[0]["names"], picked)
        self.assertEqual(first[1]["names"], first[0]["names"])
        self.assertAlmostEqual(sum(first[1]["weights"][name] for name in first[1]["names"]), 0.5)
        self.assertAlmostEqual(first[1]["weights"]["cgb-10y"], 0.5)
        self.assertEqual(first[2]["names"], [])
        self.assertAlmostEqual(first[2]["weights"]["cash"], 1.0)

    def test_zero_risk_does_not_consume_the_stream(self):
        quiet = _slot(date=pd.Timestamp("2015-06-01"), weekly=True, risk=0.0, markets=(), pools=(), fallback=())
        loud = _slot(date=pd.Timestamp("2015-06-05"), weekly=True, risk=1.0)
        together = draw_paths([quiet, loud], n=1, seed=7, top_n=1)
        alone = draw_paths([loud], n=1, seed=7, top_n=1)
        self.assertEqual(together[0][1]["names"], alone[0][0]["names"])

    def test_nets_match_simulate(self):
        index = pd.to_datetime(["2015-06-01", "2015-06-02", "2015-06-03", "2015-06-04"])
        returns = pd.DataFrame({
            "cash": 0.0, "a": 0.01, "h": -0.02, "cgb-10y": 0.0001,
        }, index=index)
        fees = {name: 0.001 for name in returns.columns}
        fees["cash"] = 0.0
        path = [{
            "date": index[0],
            "weights": {"a": 0.5, "h": 0.5, "cash": 0.0},
        }, {
            "date": index[2],
            "weights": {"cgb-10y": 1.0},
        }]
        got = portfolio_nets(returns, "cash", [path], fees, trade_eps=1e-12)
        frame = pd.DataFrame(
            [{"a": 0.5, "h": 0.5, "cgb-10y": 0.0, "cash": 0.0}, {"a": 0.0, "h": 0.0, "cgb-10y": 1.0, "cash": 0.0}],
            index=pd.DatetimeIndex([index[0], index[2]]),
            columns=list(returns.columns),
        )
        book = simulate(returns, to_execution(frame, returns.index), fees, "cash", trade_eps=1e-12)
        self.assertTrue(np.allclose(got[0], book.net.to_numpy()))


class Switches(unittest.TestCase):
    def _book(self, **kwargs):
        index = pd.bdate_range("2015-04-01", periods=20)
        names = ["a", "a2", "a3", "h", "h2", "cgb-10y", "gold"]
        level = pd.DataFrame(1.0, index=index, columns=names)
        share = pd.DataFrame(0.0, index=index, columns=names)
        slow = pd.DataFrame(0.0, index=index, columns=names)
        prices = pd.DataFrame(100.0, index=index, columns=names)
        week = list(decision_dates(index, "week"))
        share.loc[week[1] + pd.offsets.BDay(1):, "a"] = 0.9
        prices.loc[week[1] + pd.offsets.BDay(1):, "a"] = 80.0
        return allocate(
            index, level, share, slow, _universe(), prices=prices, params=knobs(), **kwargs,
        ), week

    def test_weekly_only_does_not_sell_before_the_next_week(self):
        book, week = self._book()
        held, _week = self._book(daily_look=False)
        gap = week[1] + pd.offsets.BDay(1)
        self.assertNotIn("a", str(book.state.at[gap, "picks"]).split("|"))
        self.assertIn("a", str(held.state.at[gap, "picks"]).split("|"))

    def test_hard_stop_off_keeps_the_name(self):
        index = pd.bdate_range("2015-04-01", periods=15)
        names = ["a", "a2", "a3", "h", "h2", "cgb-10y", "gold"]
        level = pd.DataFrame(1.0, index=index, columns=names)
        share = pd.DataFrame(0.0, index=index, columns=names)
        slow = pd.DataFrame(0.0, index=index, columns=names)
        prices = pd.DataFrame(100.0, index=index, columns=names)
        prices.iloc[8:, 0] = 80.0
        stopped = allocate(index, level, share, slow, _universe(), prices=prices, params=knobs())
        open_stop = allocate(index, level, share, slow, _universe(), prices=prices, params=knobs(hard_stop=None))
        self.assertIn("硬闸门", set(stopped.exits["why"]))
        self.assertNotIn("硬闸门", set(open_stop.exits["why"]))

    def test_layer_b_can_hold_both_markets(self):
        index = pd.bdate_range("2015-04-01", periods=12)
        names = ["a", "a2", "a3", "h", "h2", "cgb-10y", "gold"]
        level = pd.DataFrame(0.2, index=index, columns=names)
        level["h"] = 3.0
        level["h2"] = 2.5
        level["a"] = 2.0
        share = pd.DataFrame(0.0, index=index, columns=names)
        slow = pd.DataFrame(0.0, index=index, columns=names)
        book = allocate(
            index, level, share, slow, _universe(),
            prices=pd.DataFrame(100.0, index=index, columns=names),
            params=knobs(), selection="all",
        )
        week = list(decision_dates(index, "week"))[-1]
        picks = str(book.state.at[week, "picks"]).split("|")
        self.assertEqual(picks, ["h", "h2", "a"])
        self.assertIn("h", str(book.state.at[week, "market"]))
        self.assertIn("a", str(book.state.at[week, "market"]))

    def test_best_names_use_only_finite_design_returns(self):
        index = pd.to_datetime(["2015-12-30", "2015-12-31"])
        pnl = pd.DataFrame({"b": [0.1, 0.0], "a": [0.1, 0.0], "c": [np.nan, np.nan]}, index=index)
        self.assertEqual(rank_best(pnl, ["b", "a", "c"], "2006-01-01", "2015-12-31")[:2], ["a", "b"])


class TurnoverSplit(unittest.TestCase):
    def test_parts_sum_to_the_leg_cost(self):
        fees = {"a": 0.001, "b": 0.002, "c": 0.003, "cash": 0.0, "cgb-10y": 0.0004, "gold": 0.0005}
        before = target_weights(1.0, ["a", "b"], "cash")
        after = target_weights(0.5, ["a", "c"], "gold")
        parts = split_trade(
            before, after, risk_before=1.0, risk_after=0.5, market_before="a", market_after="h",
            defense_before="cash", defense_after="gold", exit_why={"b": "F"}, fees=fees,
        )
        self.assertGreater(parts["第一层档位"]["cost"], 0.0)
        self.assertGreater(parts["换市场"]["cost"], 0.0)
        self.assertEqual(parts["前沿离场"]["cost"], 0.0)
        same = target_weights(1.0, ["a", "b", "c"], "cash")
        sold = target_weights(1.0, ["b", "c"], "cash")
        parts = split_trade(
            same, sold, risk_before=1.0, risk_after=1.0, market_before="a", market_after="a",
            defense_before="cash", defense_after="cash", exit_why={"a": "硬闸门"}, fees=fees,
        )
        self.assertGreater(parts["硬闸门"]["cost"], 0.0)
        self.assertEqual(parts["第一层档位"]["cost"], 0.0)
        held = target_weights(0.5, ["a"], "cash")
        moved = target_weights(0.5, ["a"], "cgb-10y")
        parts = split_trade(
            held, moved, risk_before=0.5, risk_after=0.5, market_before="a", market_after="a",
            defense_before="cash", defense_after="cgb-10y", exit_why={}, fees=fees,
        )
        self.assertAlmostEqual(parts["换防守"]["turnover_one_way"], 0.5)
        self.assertEqual(parts["第一层档位"]["turnover_one_way"], 0.0)


class GateConclusion(unittest.TestCase):
    def _rows(self, *, two="通过", five="未通过", six="未通过"):
        return [
            {"item": "2", "metric": "monthly_excess_t", "status": two, "note": "旧", "strategy": "1", "benchmark": "", "hurdle": "-2"},
            {"item": "5", "metric": "calmar", "status": five, "note": "旧", "strategy": "", "benchmark": "", "hurdle": ""},
            {"item": "5", "metric": "cagr", "status": five, "note": "旧", "strategy": "", "benchmark": "", "hurdle": ""},
            {"item": "6", "metric": "p_bull", "status": six, "note": "旧", "strategy": "", "benchmark": "", "hurdle": ""},
            {"item": "6", "metric": "rebound_t", "status": six, "note": "旧", "strategy": "", "benchmark": "", "hurdle": ""},
            {"item": "6", "metric": "p_bear", "status": "只报告", "note": "不动", "strategy": "1", "benchmark": "", "hurdle": ""},
            {"item": "1", "metric": "cagr", "status": "通过", "note": "不动", "strategy": "1", "benchmark": "0", "hurdle": ""},
            {"item": "入围", "metric": "", "status": "未完成", "note": "草稿", "strategy": "", "benchmark": "", "hurdle": "0–6"},
        ]

    def test_names_b0_and_leaves_the_scored_rows(self):
        rows = conclude(self._rows())
        self.assertEqual(rows[-1]["status"], "不入围")
        self.assertEqual(rows[-1]["strategy"], "B0")
        self.assertIn("A1 退路不启用", rows[-1]["note"])
        self.assertIn("入围名单 = B0", rows[-1]["note"])
        self.assertEqual(rows[0]["note"], "旧")
        self.assertEqual(rows[-2]["note"], "不动")

    def test_refuses_when_criterion_two_failed(self):
        with self.assertRaises(V51Error):
            conclude(self._rows(two="未通过"))
