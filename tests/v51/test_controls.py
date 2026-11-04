"""R5 对照的接线：等权、波动比、随机抽取、单名成交、过关表。不跑 2000 次。"""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.v3.engine.book import simulate, to_execution
from src.v3.engine.sessions import decision_dates
from src.v51.allocate import allocate, select_vol_market
from src.v51.controls import apply_control_results
from src.v51.hold import decision_frame, draw_names, single_name_nets
from src.v51.params import V51Error
from src.v51.readings import read_series
from src.v51.universe import Market, Universe
from src.v51.volratio import dynamic_length, past_quantile, vol_ratio


def _universe() -> Universe:
    return Universe((
        Market("A股", "a", ("a", "a2")),
        Market("港股", "h", ("h",)),
    ), bond="cgb-10y", gold="gold", cash="cash")


class EqualWeight(unittest.TestCase):
    def test_equal_weight_is_the_mean_and_leaves_the_frontier(self):
        index = pd.bdate_range(end="2015-12-31", periods=820)
        rng = np.random.default_rng(51)
        asset = pd.Series(rng.normal(0.0004, 0.01, len(index)), index=index)
        cash = pd.Series(0.02 / 252, index=index)
        cash_log = np.log1p(cash)
        base = read_series(asset, cash_log)
        equal = read_series(asset, cash_log, equal_weight=True)
        velocity = equal["velocity"]
        defined = velocity.notna().all(axis=1)
        pd.testing.assert_series_equal(equal["H"][defined], velocity[defined].mean(axis=1), check_names=False)
        pd.testing.assert_series_equal(equal["F"], base["F"], check_names=False)
        pd.testing.assert_series_equal(equal["E"], base["E"], check_names=False)
        warm = base["warmup"].astype(bool) & defined
        self.assertTrue(warm.any())
        self.assertTrue(np.allclose(equal["H"][warm], base["H"][warm]))
        later = base["H"].notna() & ~base["warmup"].astype(bool)
        self.assertGreater(float((equal["H"][later] - base["H"][later]).abs().max()), 1e-8)


class VolRatio(unittest.TestCase):
    def test_length_hits_the_three_anchors(self):
        self.assertEqual(float(dynamic_length(np.array([0.0]))[0]), 250.0)
        self.assertEqual(float(dynamic_length(np.array([0.5]))[0]), 71.0)
        self.assertEqual(float(dynamic_length(np.array([1.0]))[0]), 20.0)

    def test_quantile_uses_only_the_past(self):
        got = past_quantile(np.array([1.0, 3.0, 2.0, 0.0]), minimum=2)
        self.assertEqual(got[0], 0.5)
        self.assertEqual(got[1], 0.5)
        self.assertEqual(got[2], 0.5)
        self.assertEqual(got[3], 0.0)

    def test_strength_is_the_log_excess_over_the_rounded_length(self):
        index = pd.bdate_range("2014-01-02", "2015-12-31")
        rng = np.random.default_rng(7)
        asset = pd.Series(rng.normal(0.0005, 0.01, len(index)), index=index)
        cash = pd.Series(0.0001, index=index)
        got = vol_ratio(pd.DataFrame({"a": asset, "cash": cash}), "cash", ["a"])
        finite = got.quantile["a"].dropna()
        self.assertGreater(len(finite), 250)
        self.assertTrue((finite.iloc[:250] == 0.5).all())
        self.assertTrue((got.length["a"].loc[finite.index[:250]] == 71).all())
        day = finite.index[10]
        logged = np.log1p(asset.fillna(0.0)).cumsum()
        cash_cum = np.log1p(cash.fillna(0.0)).cumsum()
        pos = int(asset.index.get_loc(day))
        expect = float((logged.iloc[pos] - logged.iloc[pos - 71]) - (cash_cum.iloc[pos] - cash_cum.iloc[pos - 71]))
        self.assertAlmostEqual(float(got.strength.at[day, "a"]), expect, places=10)
        sigma = float(np.log1p(asset.fillna(0.0)).rolling(250).std().at[day])
        self.assertAlmostEqual(float(got.noise.at[day, "a"]), expect / (sigma * np.sqrt(71)), places=10)

    def test_refuses_dates_after_2015(self):
        index = pd.bdate_range("2016-01-04", periods=5)
        frame = pd.DataFrame({"a": 0.0, "cash": 0.0}, index=index)
        with self.assertRaises(Exception):
            vol_ratio(frame, "cash", ["a"])


class VolLayer(unittest.TestCase):
    def test_noise_band_only_switches_and_a_negative_print_exits(self):
        index = pd.bdate_range("2015-04-01", periods=25)
        weeks = list(decision_dates(index, "week"))
        self.assertGreaterEqual(len(weeks), 4)
        names = ["a", "a2", "h", "cgb-10y", "gold"]
        level = pd.DataFrame(1.0, index=index, columns=names)
        share = pd.DataFrame(0.0, index=index, columns=names)
        slow = pd.DataFrame(0.0, index=index, columns=names)
        strength = pd.DataFrame(0.0, index=index, columns=names)
        noise = pd.DataFrame(0.0, index=index, columns=names)
        strength.loc[weeks[0], ["a", "h"]] = [0.30, 0.10]
        noise.loc[weeks[0], ["a", "h"]] = [1.0, 0.2]
        strength.loc[weeks[1], ["a", "h"]] = [0.20, 0.40]
        noise.loc[weeks[1], ["a", "h"]] = [1.0, 1.4]
        strength.loc[weeks[2], ["a", "h"]] = [0.20, 0.50]
        noise.loc[weeks[2], ["a", "h"]] = [1.0, 2.2]
        strength.loc[weeks[3], ["a", "h", "cgb-10y"]] = [-0.10, -0.20, 0.05]
        noise.loc[weeks[3], ["a", "h", "cgb-10y"]] = [-0.2, -0.4, 0.3]
        book = allocate(
            index, level, share, slow, _universe(),
            prices=pd.DataFrame(100.0, index=index, columns=names),
            mode="vol_ratio", strength=strength, noise=noise,
        )
        self.assertEqual(book.state.at[weeks[0], "market"], "a")
        self.assertEqual(book.state.at[weeks[0], "risk"], 1.0)
        self.assertEqual(book.state.at[weeks[1], "market"], "a")
        self.assertEqual(book.state.at[weeks[2], "market"], "h")
        self.assertEqual(book.state.at[weeks[2], "risk"], 1.0)
        self.assertEqual(book.state.at[weeks[3], "market"], "")
        self.assertEqual(book.state.at[weeks[3], "risk"], 0.0)
        self.assertEqual(book.state.at[weeks[3], "defense"], "cgb-10y")

    def test_tie_goes_to_the_smaller_id(self):
        day = pd.Timestamp("2015-06-01")
        strength = pd.DataFrame({"a": [0.2], "h": [0.2]}, index=[day])
        noise = pd.DataFrame({"a": [1.0], "h": [1.0]}, index=[day])
        held, defense = select_vol_market(None, "cash", day, _universe().markets, "cgb-10y", "gold", "cash", strength, noise, 1.0)
        self.assertEqual(held, "a")
        self.assertEqual(defense, "cash")

    def test_vol_mode_requires_the_frames(self):
        index = pd.bdate_range("2015-04-01", periods=3)
        level = pd.DataFrame({"a": 1.0}, index=index)
        with self.assertRaises(V51Error):
            allocate(index, level, level, level, Universe((Market("A股", "a", ("a",)),), bond="cgb-10y", gold="gold", cash="cash"), mode="vol_ratio")


class RandomDraw(unittest.TestCase):
    def test_seed_skips_empty_months_and_sorts_ids(self):
        eligible = [["b", "a", "a"], [], ["a"]]
        got = draw_names(eligible, n=2, seed=20261101, cash_id="cash")
        rng = np.random.default_rng(20261101)
        first = str(rng.choice(np.array(["a", "b"]), size=1, replace=False)[0])
        second = str(rng.choice(np.array(["a"]), size=1, replace=False)[0])
        third = str(rng.choice(np.array(["a", "b"]), size=1, replace=False)[0])
        fourth = str(rng.choice(np.array(["a"]), size=1, replace=False)[0])
        self.assertEqual(got, [[first, "cash", second], [third, "cash", fourth]])


class SingleHold(unittest.TestCase):
    def _frame(self):
        index = pd.to_datetime(["2015-06-01", "2015-06-02", "2015-06-03", "2015-06-04", "2015-06-05"])
        returns = pd.DataFrame({
            "cash": [0.0, 0.0, 0.0, 0.0, 0.0],
            "A": [0.01, 0.01, 0.01, 0.01, 0.01],
            "B": [0.02, 0.02, 0.02, 0.02, 0.02],
        }, index=index)
        fees = {"cash": 0.0, "A": 0.001, "B": 0.002}
        flags = np.ones((len(index), 3), dtype=bool)
        return index, returns, fees, flags

    def test_clear_days_match_the_book(self):
        index, returns, fees, flags = self._frame()
        decisions = pd.DatetimeIndex([index[0], index[2]])
        picks = [["A", "B"]]
        got = single_name_nets(returns, "cash", decisions, picks, fees, flags, flags.copy())
        frame = decision_frame(list(returns.columns), "cash", decisions, picks[0])
        book = simulate(
            returns, to_execution(frame, index), fees, "cash", trade_eps=1e-12, cost_multiplier=1.0,
        )
        self.assertTrue(np.allclose(got[0], book.net.to_numpy()))

    def test_blocked_buy_waits_and_blocked_sell_stays(self):
        index, returns, fees, flags = self._frame()
        buy = flags.copy()
        sell = flags.copy()
        buy[1, 1] = False
        decisions = pd.DatetimeIndex([index[0]])
        got = single_name_nets(returns, "cash", decisions, [["A"]], fees, buy, sell)
        self.assertTrue(np.allclose(got[0], [0.0, 0.0, -0.001, 0.01, 0.01]))

        buy2 = flags.copy()
        sell2 = flags.copy()
        sell2[2, 1] = False
        decisions = pd.DatetimeIndex([index[0], index[1]])
        got = single_name_nets(returns, "cash", decisions, [["A", "B"]], fees, buy2, sell2)
        self.assertTrue(np.allclose(got[0], [0.0, -0.001, 0.01, 0.01 - 0.003, 0.02]))

        buy3 = flags.copy()
        buy3[2, 2] = False
        got = single_name_nets(returns, "cash", decisions, [["A", "B"]], fees, buy3, flags.copy())
        self.assertTrue(np.allclose(got[0], [0.0, -0.001, 0.01 - 0.001, -0.002, 0.02]))


class GatePatch(unittest.TestCase):
    def test_scores_zero_and_three_and_leaves_the_rest(self):
        rows = [
            {"item": "0", "pool": "index", "metric": "calmar", "strategy": "1.5", "benchmark": "", "status": "待 R5", "note": "旧"},
            {"item": "0", "pool": "index", "metric": "cagr", "strategy": "0.10", "benchmark": "", "status": "待 R5", "note": "旧"},
            {"item": "0", "pool": "tradable", "metric": "calmar", "strategy": "0.2", "benchmark": "", "status": "待 R5", "note": "旧"},
            {"item": "0", "pool": "tradable", "metric": "cagr", "strategy": "0.20", "benchmark": "", "status": "待 R5", "note": "旧"},
            {"item": "1", "pool": "index", "metric": "cagr", "strategy": "0.3", "benchmark": "0.1", "status": "通过", "note": "不动"},
            {"item": "3", "pool": "index", "metric": "cagr", "strategy": "0.30", "benchmark": "", "status": "待 R5", "note": "旧"},
            {"item": "5", "pool": "G", "metric": "cagr", "strategy": "", "benchmark": "", "status": "待 R6", "note": "不动"},
            {"item": "6", "pool": "index", "metric": "p_bull", "strategy": "-1", "benchmark": "0", "status": "未通过", "note": "不动"},
            {"item": "入围", "pool": "both", "metric": "", "strategy": "", "benchmark": "", "status": "未完成", "note": "旧"},
        ]
        r0 = {
            "index": {"calmar_p95": 1.0, "cagr_median": 0.12, "n": 2000, "seed": 20261101},
            "tradable": {"calmar_p95": 0.5, "cagr_median": 0.05, "n": 2000, "seed": 20261101},
        }
        got = apply_control_results(rows, r0, 0.2, 0.25)
        self.assertEqual(got[0]["status"], "通过")
        self.assertEqual(got[1]["status"], "未通过")
        self.assertEqual(got[2]["status"], "未通过")
        self.assertEqual(got[3]["status"], "通过")
        self.assertEqual(got[4]["note"], "不动")
        self.assertEqual(got[5]["status"], "通过")
        self.assertIn("0.2", got[5]["note"])
        self.assertIn("0.25", got[5]["note"])
        self.assertEqual(got[6]["status"], "待 R6")
        self.assertEqual(got[7]["note"], "不动")
        self.assertEqual(got[8]["status"], "未完成")
        self.assertIn("R5", got[8]["note"])


if __name__ == "__main__":
    unittest.main()
