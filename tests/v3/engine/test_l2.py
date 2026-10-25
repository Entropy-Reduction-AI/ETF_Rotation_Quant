"""v3 §4 引擎：打分、成本、门禁、未来函数、随机游走、BM-主。"""
from __future__ import annotations

import hashlib
import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.dividends import GAP_LIMIT
from src.report.metrics import ann_vol, cagr, max_drawdown, performance, sharpe, yearly_returns
from src.research.prereg_v2.engine import cash_daily, haven_total_return, load_haven
from src.v3.data.universe import UNIVERSE, containers
from src.v3.engine.arms import execute
from src.v3.engine.book import simulate
from src.v3.engine.control import null_b_targets
from src.v3.engine.market import market_from_returns
from src.v3.engine.prices import align_same_day, mask_publish, returns_from_level, signal_returns, total_return_close
from src.v3.engine.runner import run
from src.v3.engine.score import Lookback, average_weights, lookback_panel, min_observations, pick_row
from src.v3.engine.sessions import decision_dates
from src.v3.engine.spec import LEDGER, load_spec, sha_matches
from src.v3.engine.universe import fee_for, pool_members, signal_kinds
from src.v3.engine.benchmark import bm_main
from src.v3.engine.book import RunnerError

ROOT = Path(__file__).resolve().parents[3]
# `python -m src.v3.data emit` 写出的登记表。手改 toml 会让这行失败。Reviewer 重签之前，这不是冻结 SHA。
UNIVERSE_SHA = "04ff3572ebd82a5159eaccced0bed5bc3531b732a1b11025f86021ebd0454be0"
FREEZE = "bfeb49cc65eb0ba419bc98348f1d643fac1211f6"
CASH = 0.02 / 252


def _days(n: int, start: str = "2006-01-03") -> pd.DatetimeIndex:
    return pd.bdate_range(start, periods=n)


def _frame(days, columns: dict[str, np.ndarray]) -> pd.DataFrame:
    return pd.DataFrame(columns, index=days)


class ScoreRules(unittest.TestCase):
    def test_formula_matches_hand_calculation(self):
        days = _days(25)
        window = np.linspace(-0.01, 0.02, 20)
        asset = np.concatenate([np.zeros(5), window])
        cash = np.full(25, CASH)
        panel = lookback_panel(_frame(days, {"asset": asset, "cash": cash}), "cash", 20)
        manual_r = float(np.prod(1.0 + window) - 1.0)
        manual_std = float(window.std(ddof=1))
        manual_s = manual_r / (manual_std * math.sqrt(20))
        self.assertAlmostEqual(float(panel.total["asset"].iloc[-1]), manual_r, places=12)
        self.assertAlmostEqual(float(panel.score["asset"].iloc[-1]), manual_s, places=12)
        self.assertTrue(bool(panel.ok["asset"].iloc[-1]))
        self.assertFalse(bool(panel.ok["cash"].iloc[-1]))
        self.assertEqual(min_observations(20), 20)
        self.assertEqual(min_observations(60), 30)
        self.assertEqual(min_observations(250), 125)

    def test_nan_day_is_left_out_of_the_product(self):
        days = _days(60)
        asset = np.full(60, 0.001)
        asset[30] = np.nan
        cash = np.zeros(60)
        panel = lookback_panel(_frame(days, {"asset": asset, "cash": cash}), "cash", 60)
        used = asset[-60:]
        used = used[np.isfinite(used)]
        manual = float(np.prod(1.0 + used) - 1.0)
        self.assertAlmostEqual(float(panel.total["asset"].iloc[-1]), manual, places=12)
        self.assertLess(abs(manual - (1.001 ** 60 - 1.0)), 1.0)
        self.assertGreater(abs(manual - (1.001 ** 60 - 1.0)), 1e-6)

    def test_history_shorter_than_lookback_is_ineligible(self):
        days = _days(30)
        asset = np.full(30, 0.01)
        cash = np.zeros(30)
        panel = lookback_panel(_frame(days, {"asset": asset, "cash": cash}), "cash", 60)
        self.assertFalse(bool(panel.ok["asset"].iloc[-1]))

    def test_absolute_filter_and_tie_break(self):
        day = pd.Timestamp("2006-01-31")
        panel = Lookback(
            total=pd.DataFrame({"a": [0.9], "b": [0.2], "c": [0.3], "flat": [0.0]}, index=[day]),
            score=pd.DataFrame({"a": [1.0], "b": [5.0], "c": [5.0], "flat": [0.0]}, index=[day]),
            ok=pd.DataFrame({"a": [True], "b": [True], "c": [True], "flat": [False]}, index=[day]),
        )
        weights = pick_row(panel, day, 2, ["b", "a", "c", "flat"], "cash",
                           {"b": "b", "a": "a", "c": "c", "flat": "flat"}, None)
        self.assertNotIn("flat", weights)
        self.assertNotIn("a", weights)
        self.assertEqual(weights["c"], 0.5)
        self.assertEqual(weights["b"], 0.5)
        self.assertAlmostEqual(weights["cash"], 0.0)
        one = pick_row(panel, day, 1, ["b", "c"], "cash", {"b": "b", "c": "c"}, None)
        self.assertEqual(one["c"], 1.0)
        self.assertNotIn("b", one)

    def test_short_list_keeps_one_nth(self):
        days = _days(25)
        asset = np.concatenate([np.zeros(5), np.full(20, 0.002)])
        cash = np.full(25, CASH)
        panel = lookback_panel(_frame(days, {"only": asset, "cash": cash}), "cash", 20)
        weights = pick_row(panel, days[-1], 3, ["only"], "cash", {"only": "only"}, None)
        self.assertAlmostEqual(weights["only"], 1.0 / 3.0)
        self.assertAlmostEqual(weights["cash"], 2.0 / 3.0)

    def test_lookbacks_are_averaged(self):
        averaged = average_weights(
            [{"x": 1.0, "cash": 0.0}, {"cash": 1.0}, {"x": 0.5, "cash": 0.5}, {"x": 0.5, "cash": 0.5}],
            ["x"], "cash")
        self.assertAlmostEqual(averaged["x"], 0.5)
        self.assertAlmostEqual(averaged["cash"], 0.5)


class ArmBlend(unittest.TestCase):
    def test_constant_winner_averages_six_groups(self):
        spec = load_spec()
        days = _days(420)
        winner = np.full(len(days), 0.002)
        other = np.zeros(len(days))
        cash = np.full(len(days), CASH)
        signal = _frame(days, {"winner": winner, "other": other, "cash": cash})
        fees = {"winner": 0.0005, "other": 0.001, "cash": 0.0005}
        market = market_from_returns(signal, fees)
        book = execute(market, spec, "A")
        last = book.decisions.iloc[-1]
        expected = (1.0 / 3.0 + 1.0 / 5.0 + 1.0 / 8.0) / 3.0
        self.assertAlmostEqual(float(last["winner"]), expected, places=10)
        self.assertAlmostEqual(float(last["cash"]), 1.0 - expected, places=10)
        self.assertAlmostEqual(float(last.sum()), 1.0, places=10)
        self.assertLessEqual(book.net.index.max(), pd.Timestamp("2015-12-31"))

    def test_b_choice_does_not_use_the_following_year(self):
        spec = replace(
            load_spec(), lookbacks=(20,), ns=(3, 8), frequencies=("month",),
            b_first_year=2007, b_train_start="2006-01-03")
        days = _days(520)
        names = ["lead", "other"]
        signal = _frame(days, {
            "lead": np.full(len(days), 0.002),
            "other": np.zeros(len(days)),
            "cash": np.full(len(days), CASH),
        })
        fees = {"lead": 0.0005, "other": 0.001, "cash": 0.0005}
        benchmark = pd.Series(0.0, index=days)
        market = market_from_returns(signal, fees, benchmark=benchmark)
        book = execute(market, spec, "B")
        self.assertIsNone(book.choices[2006])
        self.assertIn(book.choices[2007], spec.candidates())
        shocked = signal.copy()
        shocked.loc[shocked.index > "2006-12-31", names] = 0.05
        later = execute(market_from_returns(shocked, fees, benchmark=benchmark), spec, "B")
        self.assertEqual(book.choices[2007], later.choices[2007])
        key = book.choices[2007]
        alone = execute(market, spec, "A", n=key[0], freq=key[1])
        left = book.targets[book.targets.index.year == 2007]
        right = alone.targets[alone.targets.index.year == 2007]
        pd.testing.assert_frame_equal(left, right)


class Costs(unittest.TestCase):
    """三个决策日的手工账。费率：宽基 5bp，行业 10bp，现金 5bp。"""

    def _book(self, multiplier: float = 1.0):
        days = pd.to_datetime([
            "2006-01-31", "2006-02-01", "2006-02-28", "2006-03-01", "2006-03-31", "2006-04-03",
        ])
        rows = [
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (0.0, 0.10, 0.0),
            (0.0, 0.0, 0.0),
            (0.20, -0.10, 0.0),
            (0.0, 0.0, 0.0),
        ]
        pnl = pd.DataFrame(rows, index=days, columns=["broad", "sector", "cash"])
        targets = pd.DataFrame(
            [
                {"broad": 0.0, "sector": 1.0, "cash": 0.0},
                {"broad": 0.5, "sector": 0.5, "cash": 0.0},
                {"broad": 0.0, "sector": 0.0, "cash": 1.0},
            ],
            index=pd.to_datetime(["2006-02-01", "2006-03-01", "2006-04-03"]),
        )
        fees = {"broad": 0.0005, "sector": 0.0010, "cash": 0.0005}
        return simulate(pnl, targets, fees, "cash", cost_multiplier=multiplier)

    def test_three_decision_days(self):
        book = self._book()
        first, second, third = pd.Timestamp("2006-02-01"), pd.Timestamp("2006-03-01"), pd.Timestamp("2006-04-03")
        self.assertAlmostEqual(float(book.cost.loc[first]), 0.0015, places=12)
        self.assertAlmostEqual(float(book.buy.loc[first]), 1.0, places=12)
        self.assertAlmostEqual(float(book.sell.loc[first]), 1.0, places=12)
        self.assertAlmostEqual(float(book.cost.loc[second]), 0.00075, places=12)
        self.assertAlmostEqual(float(book.buy.loc[second]), 0.5, places=12)
        self.assertAlmostEqual(float(book.sell.loc[second]), 0.5, places=12)
        exit_cost = 0.0085 / 7.0
        self.assertAlmostEqual(float(book.cost.loc[third]), exit_cost, places=12)
        self.assertAlmostEqual(float(book.buy.loc[third]), 1.0, places=12)
        self.assertAlmostEqual(float(book.sell.loc[third]), 1.0, places=12)
        self.assertAlmostEqual(float(book.held.loc[third, "broad"]), 4.0 / 7.0, places=12)
        self.assertAlmostEqual(float(book.held.loc[third, "sector"]), 3.0 / 7.0, places=12)
        quiet = pd.Timestamp("2006-02-28")
        self.assertEqual(float(book.cost.loc[quiet]), 0.0)
        self.assertEqual(float(book.buy.loc[quiet]), 0.0)

    def test_doubled_schedule_doubles_the_three_days(self):
        base = self._book(1.0)
        doubled = self._book(2.0)
        for day in ("2006-02-01", "2006-03-01", "2006-04-03"):
            self.assertAlmostEqual(float(doubled.cost.loc[day]), 2.0 * float(base.cost.loc[day]), places=12)


class Adjustments(unittest.TestCase):
    def test_fake_gap_return_is_removed(self):
        self.assertEqual(GAP_LIMIT, 0.40)
        bars = pd.DataFrame({
            "date": pd.to_datetime(["2006-01-03", "2006-01-04", "2006-01-05", "2006-01-06"]),
            "open": [100.0, 110.0, 50.0, 55.0],
            "close": [100.0, 110.0, 50.0, 55.0],
        })
        level, gaps = total_return_close(bars, {})
        self.assertAlmostEqual(float(level.iloc[0]), 100.0)
        self.assertAlmostEqual(float(level.iloc[1]), 110.0)
        self.assertAlmostEqual(float(level.iloc[2]), 110.0)
        self.assertAlmostEqual(float(level.iloc[3]), 121.0)
        self.assertIn(pd.Timestamp("2006-01-05"), gaps)
        signal = signal_returns(level, gaps)
        priced = returns_from_level(level)
        self.assertTrue(pd.isna(signal.loc[pd.Timestamp("2006-01-05")]))
        self.assertAlmostEqual(float(priced.loc[pd.Timestamp("2006-01-05")]), 0.0, places=12)

    def test_dividend_is_reinvested(self):
        bars = pd.DataFrame({
            "date": pd.to_datetime(["2006-01-03", "2006-01-04"]),
            "open": [100.0, 98.0],
            "close": [100.0, 98.0],
        })
        level, gaps = total_return_close(bars, {pd.Timestamp("2006-01-04"): 0.02})
        self.assertEqual(len(gaps), 0)
        self.assertAlmostEqual(float(level.iloc[1]), 100.0, places=12)

    def test_resume_after_a_five_day_hole_keeps_the_move(self):
        calendar = pd.bdate_range("2006-01-02", periods=12)
        native = pd.Series(100.0, index=calendar)
        native.iloc[3:9] = np.nan
        native.iloc[9] = 110.0
        level, fresh = align_same_day(native, calendar, 5)
        rets = returns_from_level(level)
        self.assertAlmostEqual(float(rets.iloc[9]), 0.10, places=12)
        self.assertTrue(bool(fresh.iloc[6]))
        self.assertFalse(bool(fresh.iloc[7]))
        self.assertTrue(bool(fresh.iloc[9]))

    def test_pre_publish_close_does_not_fill_forward(self):
        calendar = pd.DatetimeIndex(pd.to_datetime(["2006-01-03", "2006-01-04", "2006-01-05"]))
        native = pd.Series([90.0, 100.0, 110.0], index=calendar)
        masked = mask_publish(native, pd.Timestamp("2006-01-04"))
        level, fresh = align_same_day(masked, calendar, 5)
        rets = returns_from_level(level)
        self.assertTrue(pd.isna(rets.iloc[1]))
        self.assertAlmostEqual(float(rets.iloc[2]), 0.10, places=12)
        self.assertFalse(bool(fresh.iloc[0]))
        self.assertTrue(bool(fresh.iloc[1]))


class Gates(unittest.TestCase):
    def test_universe_file_is_the_frozen_one(self):
        digest = hashlib.sha256(UNIVERSE.read_bytes()).hexdigest()
        self.assertEqual(digest, UNIVERSE_SHA)

    def test_default_end_and_lock(self):
        spec = load_spec()
        self.assertEqual(spec.seed, 20261024)
        self.assertEqual(tuple(spec.lookbacks), (20, 60, 120, 250))
        self.assertTrue(sha_matches(FREEZE, spec.freeze_sha))
        self.assertTrue(sha_matches("bfeb49c", spec.freeze_sha))
        self.assertFalse(sha_matches("bbbbbbb", spec.freeze_sha))
        from src.v3.engine.runner import resolve_end
        self.assertEqual(resolve_end(None, spec), pd.Timestamp("2015-12-31"))
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "LOCK"
            lock.write_text("locked\n", encoding="utf-8")
            self.assertEqual(resolve_end("2015-12-31", spec, lock_path=lock), pd.Timestamp("2015-12-31"))
            with self.assertRaises(RunnerError):
                resolve_end("2016-01-04", spec, full_period=True, freeze_sha=FREEZE, lock_path=lock)
            with self.assertRaises(RunnerError):
                resolve_end("2016-01-04", spec, full_period=True, freeze_sha=None, lock_path=Path(tmp) / "missing")
            with self.assertRaises(RunnerError):
                resolve_end("2016-01-04", spec, lock_path=Path(tmp) / "missing")
            with self.assertRaises(RunnerError):
                resolve_end("2016-06-01", spec, debug=True, lock_path=Path(tmp) / "missing")
            allowed = resolve_end("2016-01-04", spec, full_period=True, freeze_sha=FREEZE,
                                  lock_path=Path(tmp) / "missing")
            self.assertEqual(allowed, pd.Timestamp("2016-01-04"))

    def test_run_refuses_before_building_a_book(self):
        days = _days(5)
        signal = _frame(days, {"a": np.zeros(5), "cash": np.full(5, CASH)})
        market = market_from_returns(signal, {"a": 0.0005, "cash": 0.0005})
        with self.assertRaises(RunnerError):
            run("A", "index", "2016-01-04", market=market)
        self.assertFalse(LEDGER.exists())

    def test_ledger_one_row_and_debug_skips(self):
        days = _days(40)
        signal = _frame(days, {"a": np.full(40, 0.001), "cash": np.full(40, CASH)})
        market = market_from_returns(signal, {"a": 0.0005, "cash": 0.0005})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trial-ledger.csv"
            run("A", "index", "2007-12-31", market=market, ledger_path=path, debug=True)
            self.assertFalse(path.exists())
            run("A", "index", "2007-12-31", market=market, ledger_path=path)
            run("A", "index", "2007-12-31", market=market, ledger_path=path)
            run("A", "index", "2007-12-31", market=market, ledger_path=path, cost_multiplier=2.0)
            rows = list(pd.read_csv(path).itertuples(index=False))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0].arm, "A")
            self.assertEqual(rows[0].segment, "design")
            self.assertIn("index", rows[0].params)
            self.assertLessEqual(pd.Timestamp("2007-12-31"), pd.Timestamp("2015-12-31"))
        self.assertFalse(LEDGER.exists())


class Membership(unittest.TestCase):
    def test_pools_and_fees(self):
        spec = load_spec()
        rows = containers()
        s2 = pool_members(rows, "S2", "index")
        ids = {row["id"] for row in s2}
        self.assertIn("s2-煤炭", ids)
        self.assertIn("s2-沪深300", ids)
        self.assertIn("hsi", ids)
        self.assertIn("cash", ids)
        self.assertNotIn("csi300", ids)
        self.assertNotIn("allshare-energy", ids)
        main = pool_members(rows, "A", "index")
        main_ids = {row["id"] for row in main}
        self.assertIn("csi300", main_ids)
        self.assertNotIn("s2-煤炭", main_ids)
        for row in rows:
            fee_for(row, spec)
        qdii = next(
            row for row in rows
            if any(ex.get("code") == "159509" for ex in row.get("execution") or [])
        )
        self.assertEqual(qdii["id"], "theme-纳斯达克科技市值加权指数")
        self.assertEqual(qdii["asset_class"], "美股和全球主题")
        self.assertEqual(signal_kinds(qdii, "A", "index"), ("nav", "nav"))
        self.assertEqual(signal_kinds(qdii, "S1", "index"), ("price", "nav"))
        self.assertEqual(signal_kinds(qdii, "A", "tradable"), ("nav", "price"))
        self.assertEqual(signal_kinds(qdii, "S1", "tradable"), ("price", "price"))
        broad = next(row for row in rows if row["id"] == "csi300")
        self.assertEqual(signal_kinds(broad, "A", "index"), ("research", "research"))

    def test_decision_calendar(self):
        days = pd.to_datetime(["2006-01-03", "2006-01-04", "2006-01-05", "2006-01-30", "2006-01-31", "2006-02-01"])
        month = decision_dates(pd.DatetimeIndex(days), "month")
        self.assertEqual(list(month.date), [pd.Timestamp("2006-01-31").date(), pd.Timestamp("2006-02-01").date()])


class Lookahead(unittest.TestCase):
    def test_future_prices_do_not_change_weights_through_t(self):
        spec = load_spec()
        rng = np.random.default_rng(7)
        days = _days(280)
        names = ["a1", "a2", "a3", "a4"]
        shock = rng.normal(0.0002, 0.01, size=(len(days), len(names)))
        columns = {name: shock[:, i] for i, name in enumerate(names)}
        columns["cash"] = np.full(len(days), CASH)
        signal = _frame(days, columns)
        fees = {name: 0.001 for name in names}
        fees["cash"] = 0.0005
        book = execute(market_from_returns(signal, fees), spec, "A")
        cut = days[160]
        shocked = signal.copy()
        shocked.loc[shocked.index > cut, names] = shocked.loc[shocked.index > cut, names].to_numpy() * 0.0 + 0.2
        later = execute(market_from_returns(shocked, fees), spec, "A")
        held = book.held.loc[:cut]
        pd.testing.assert_frame_equal(held, later.held.loc[:cut])
        left = book.decisions.loc[:cut]
        right = later.decisions.loc[:cut]
        pd.testing.assert_frame_equal(left, right)
        self.assertFalse(left.empty)


class RandomWalk(unittest.TestCase):
    def test_noise_has_no_significant_edge_versus_random_control(self):
        spec = load_spec()
        rng = np.random.default_rng(spec.seed)
        excess = []
        top = 0
        seeds = 20
        controls = 30
        for _ in range(seeds):
            days = _days(260)
            names = [f"n{i}" for i in range(5)]
            shock = rng.normal(0.0, 0.01, size=(len(days), len(names)))
            columns = {name: shock[:, i] for i, name in enumerate(names)}
            columns["cash"] = np.full(len(days), CASH)
            signal = _frame(days, columns)
            fees = {name: 0.0005 for name in names}
            fees["cash"] = 0.0005
            market = market_from_returns(signal, fees)
            book = execute(market, spec, "A", n=3, freq="month")
            sample = []
            for _control in range(controls):
                targets = null_b_targets(book.targets, names, "cash", rng, spec.weight_eps)
                control = simulate(market.pnl, targets, fees, "cash", trade_eps=spec.trade_eps)
                sample.append(cagr(control.net))
            strategy = cagr(book.net)
            excess.append(strategy - float(np.median(sample)))
            if strategy > float(np.quantile(sample, 0.9)):
                top += 1
        excess = np.asarray(excess, dtype=float)
        scale = float(excess.std(ddof=1) / math.sqrt(len(excess)))
        t_stat = float(excess.mean() / scale) if scale else 0.0
        self.assertLess(t_stat, 2.5)
        self.assertLessEqual(top, 6)


class Benchmark(unittest.TestCase):
    def test_design_window_matches_phase1_report(self):
        db = ROOT / "data" / "market.sqlite"
        if not db.exists() or db.stat().st_size < 1000:
            self.skipTest("market.sqlite 不在这台机器上")
        series = bm_main(db, "2015-12-31")
        self.assertLessEqual(series.index.max(), pd.Timestamp("2015-12-31"))
        published = json_row()
        closes, dividends = load_haven(db, "511880", pd.Timestamp("2015-12-31"))
        from src.v3.engine.benchmark import _calendar, _connect
        con = _connect(db)
        try:
            full_cal = _calendar(con, "2015-12-31")
        finally:
            con.close()
        rf = haven_total_return(closes, dividends, full_cal, cash_daily())
        rf.index = pd.to_datetime(rf.index)
        got = performance(series, rf)
        for key in ("cagr", "ann_vol", "max_drawdown", "sharpe", "calmar"):
            self.assertLessEqual(abs(got[key] - published[key]), 0.001)
            self.assertAlmostEqual(got[key], published[key], places=9)
        self.assertEqual(got["start"], published["start"])
        self.assertEqual(got["end"], "2015-12-31")
        self.assertEqual(got["n"], published["n"])
        self.assertEqual(got["max_drawdown_peak"], published["max_drawdown_peak"])
        self.assertEqual(got["max_drawdown_trough"], published["max_drawdown_trough"])
        annual = pd.read_csv(ROOT / "results" / "report" / "annual.csv")
        years = yearly_returns(series)
        for _, row in annual.iterrows():
            year = int(row["year"])
            if year > 2015 or not np.isfinite(row["BM-主"]):
                continue
            self.assertLessEqual(abs(years[year] - float(row["BM-主"])), 0.001)
            self.assertAlmostEqual(years[year], float(row["BM-主"]), places=9)
        self.assertAlmostEqual(cagr(series), published["cagr"], places=12)
        self.assertAlmostEqual(ann_vol(series), published["ann_vol"], places=12)
        self.assertAlmostEqual(max_drawdown(series)["max_drawdown"], published["max_drawdown"], places=12)
        self.assertAlmostEqual(sharpe(series, rf), published["sharpe"], places=12)


def json_row() -> dict:
    import json
    payload = json.loads((ROOT / "results" / "report" / "benchmark.json").read_text(encoding="utf-8"))
    for row in payload["rows"]:
        if row["series"] == "BM-主" and row["window"] == "设计期":
            return row
    raise AssertionError("报告里没有设计期 BM-主")


class Smoke(unittest.TestCase):
    def test_index_arm_a_stays_inside_the_design_window(self):
        db = ROOT / "data" / "market.sqlite"
        if not db.exists() or db.stat().st_size < 1000:
            self.skipTest("market.sqlite 不在这台机器上")
        book = run("A", "index", "2008-12-31", debug=True, db_path=db)
        self.assertFalse(book.net.empty)
        self.assertLessEqual(book.net.index.max(), pd.Timestamp("2008-12-31"))
        self.assertLessEqual(book.held.index.max(), pd.Timestamp("2008-12-31"))
        sums = book.decisions.sum(axis=1)
        self.assertLess(float((sums - 1.0).abs().max()), 1e-8)
        self.assertFalse(LEDGER.exists())


if __name__ == "__main__":
    unittest.main()
