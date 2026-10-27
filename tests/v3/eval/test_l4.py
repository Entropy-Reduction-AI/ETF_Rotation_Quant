"""v3 §6 和 §7：随机起点、随机对照、年代、回撤、紧缩夏普、滚动前推、过拟合概率、稳健性。"""
from __future__ import annotations

import csv
import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from src.v3.engine.arms import execute
from src.v3.engine.book import simulate
from src.v3.engine.control import null_b_targets
from src.v3.engine.market import market_from_returns
from src.v3.engine.spec import LEDGER, LOCK, load_spec
from src.v3.eval.common import (
    EXPLORATION_TRIALS,
    ORCHESTRATOR_DIAGNOSTIC_TRIALS,
    EvalError,
    annualized_return,
)
from src.v3.eval.controls import criterion_2, eligibility_on_targets, null_a_targets, percentile_rank
from src.v3.eval.drawdown import criterion_4, drawdown_stats, equity_weight, position_matched
from src.v3.eval.eras import criterion_3, four_era_check
from src.v3.eval.report import action_for, evaluate_design
from src.v3.eval.robustness import best_containers, delay_targets, robustness_books, robustness_table
from src.v3.eval.selection import cscv_pbo, premium_keys, stitch_targets, walk_forward
from src.v3.eval.sharpe import (
    criterion_5,
    deflated_sharpe_ratio,
    probabilistic_sharpe_ratio,
    sharpe_moments,
    trial_count,
    variance_of_sharpes,
)
from src.v3.eval.windows import criterion_1, engineering_check_1, rolling_windows
from src.v3.eval import sharpe as sharpe_mod
from src.v3.eval import selection as selection_mod

ROOT = Path(__file__).resolve().parents[3]
CASH = 0.02 / 252
TRIAL_BASE = EXPLORATION_TRIALS + ORCHESTRATOR_DIAGNOSTIC_TRIALS


def _ledger_bytes() -> bytes | None:
    """正式 ledger 的原文。测试只比较，不创建、不删除。"""
    if not LEDGER.exists():
        return None
    return LEDGER.read_bytes()


def _write_ledger(path: Path, rows: list[str]) -> None:
    path.write_text(
        "run_at,git_sha,arm,params,segment,runner\n" + "".join(line if line.endswith("\n") else line + "\n" for line in rows),
        encoding="utf-8",
    )


def _calendar(start: str, end: str) -> pd.DatetimeIndex:
    return pd.bdate_range(start, end)


class Gate(unittest.TestCase):
    def test_post_2015_portfolio_returns_are_refused(self):
        before = _ledger_bytes()
        days = pd.bdate_range("2015-12-30", periods=4)
        self.assertGreater(days.max(), pd.Timestamp("2015-12-31"))
        series = pd.Series(0.0, index=days)
        with self.assertRaises(EvalError):
            criterion_1(series, series, days)
        with self.assertRaises(EvalError):
            criterion_3(series, series, days)
        with self.assertRaises(EvalError):
            criterion_4(series, series)
        with self.assertRaises(EvalError):
            criterion_5(series, n_trials=28, sr_variance=0.01)
        with self.assertRaises(EvalError):
            cscv_pbo(pd.DataFrame({"a": series, "b": series}))
        self.assertFalse(LOCK.exists())
        self.assertEqual(_ledger_bytes(), before)

    def test_paper_citation_is_in_the_docstring(self):
        text = sharpe_mod.__doc__ or ""
        self.assertIn("Bailey", text)
        self.assertIn("2014", text)
        self.assertIn("Deflated Sharpe Ratio", text)
        selection = selection_mod.__doc__ or ""
        self.assertIn("Probability of Backtest Overfitting", selection)
        self.assertIn("2017", selection)


class Windows(unittest.TestCase):
    def test_anchors_match_the_prereg_example(self):
        calendar = _calendar("2006-01-02", "2015-12-31")
        first_36 = rolling_windows(calendar, 36)[0]
        first_60 = rolling_windows(calendar, 60)[0]
        jan = calendar[calendar.to_period("M") == "2006-01"]
        dec_2008 = calendar[calendar.to_period("M") == "2008-12"]
        dec_2010 = calendar[calendar.to_period("M") == "2010-12"]
        self.assertEqual(first_36[0], jan[0])
        self.assertEqual(first_36[1], dec_2008[-1])
        self.assertEqual(first_60[0], jan[0])
        self.assertEqual(first_60[1], dec_2010[-1])
        self.assertLess(rolling_windows(calendar, 60)[0][0], rolling_windows(calendar, 60)[1][0])

    def test_constant_edge_clears_the_numeric_check(self):
        calendar = _calendar("2006-01-02", "2015-12-31")
        strategy = pd.Series(0.001, index=calendar)
        benchmark = pd.Series(0.0, index=calendar)
        report = criterion_1(strategy, benchmark, calendar)
        expected = math.exp(252 * math.log(1.001)) - 1.0
        self.assertGreater(report["n_60"], 1)
        self.assertGreater(report["n_36"], report["n_60"])
        self.assertAlmostEqual(report["median_60"], expected, places=12)
        self.assertAlmostEqual(report["median_36"], expected, places=12)
        self.assertAlmostEqual(report["fraction_positive_60"], 1.0, places=12)
        self.assertTrue(report["engineering_check"])
        self.assertIsNone(report["formal_pass"])
        self.assertEqual(report["windows_36"][0]["n"], len(calendar[
            (calendar >= report["windows_36"][0]["start"]) & (calendar <= report["windows_36"][0]["end"])
        ]))

    def test_thresholds_and_overlap_gap(self):
        self.assertTrue(engineering_check_1(0.01, 0.01, 0.60))
        self.assertFalse(engineering_check_1(0.01, 0.01, 0.599))
        self.assertFalse(engineering_check_1(0.0, 0.01, 1.0))
        self.assertFalse(engineering_check_1(0.01, 0.0, 1.0))
        self.assertFalse(engineering_check_1(None, 0.01, 1.0))
        # 缺了一个月，跨过这个月的窗口不能成立。
        days = _calendar("2006-01-02", "2010-12-31")
        days = days[~((days.year == 2007) & (days.month == 6))]
        windows = rolling_windows(days, 36)
        self.assertTrue(windows)
        gap = pd.Period("2007-06", freq="M")
        for start, end in windows:
            months = pd.period_range(pd.Timestamp(start).to_period("M"), pd.Timestamp(end).to_period("M"), freq="M")
            self.assertNotIn(gap, months)
            self.assertEqual(pd.Timestamp(start).to_period("M") + 35, pd.Timestamp(end).to_period("M"))


class Eras(unittest.TestCase):
    def test_design_eras_are_numbers_and_later_eras_are_not_run(self):
        calendar = _calendar("2006-01-02", "2015-12-31")
        strategy = pd.Series(0.001, index=calendar)
        benchmark = pd.Series(0.0, index=calendar)
        report = criterion_3(strategy, benchmark, calendar)
        expected = math.exp(252 * math.log(1.001)) - 1.0
        by_name = {row["era"]: row for row in report["eras"]}
        self.assertEqual(by_name["2006-2010"]["status"], "ok")
        self.assertAlmostEqual(by_name["2006-2010"]["excess"], expected, places=12)
        self.assertTrue(by_name["2006-2010"]["positive"])
        self.assertEqual(by_name["2011-2015"]["status"], "ok")
        self.assertEqual(by_name["2016-2020"]["status"], "未计算")
        self.assertEqual(by_name["2021-2026"]["status"], "未计算")
        self.assertIsNone(by_name["2016-2020"]["excess"])
        self.assertIsNone(report["engineering_check"])
        self.assertIsNone(report["formal_pass"])

    def test_short_segment_is_insufficient_and_not_positive(self):
        early = _calendar("2006-01-02", "2006-01-20")
        later = _calendar("2011-01-03", "2015-12-31")
        calendar = early.append(later)
        strategy = pd.Series(0.001, index=calendar)
        benchmark = pd.Series(0.0, index=calendar)
        report = criterion_3(strategy, benchmark, calendar)
        by_name = {row["era"]: row for row in report["eras"]}
        self.assertEqual(by_name["2006-2010"]["status"], "样本不足")
        self.assertFalse(by_name["2006-2010"]["positive"])
        self.assertLess(by_name["2006-2010"]["n"], 60)
        self.assertEqual(by_name["2011-2015"]["status"], "ok")

    def test_floor_and_three_of_four(self):
        self.assertIsNone(four_era_check([
            {"status": "ok", "positive": True, "below_floor": False},
            {"status": "未计算", "positive": False, "below_floor": False},
        ]))
        self.assertTrue(four_era_check([
            {"status": "ok", "positive": True, "below_floor": False},
            {"status": "ok", "positive": True, "below_floor": False},
            {"status": "ok", "positive": True, "below_floor": False},
            {"status": "样本不足", "positive": False, "below_floor": False},
        ]))
        self.assertFalse(four_era_check([
            {"status": "ok", "positive": True, "below_floor": False},
            {"status": "ok", "positive": True, "below_floor": True},
            {"status": "ok", "positive": True, "below_floor": False},
            {"status": "ok", "positive": True, "below_floor": False},
        ]))
        self.assertFalse(four_era_check([
            {"status": "ok", "positive": True, "below_floor": False},
            {"status": "ok", "positive": True, "below_floor": False},
            {"status": "样本不足", "positive": False, "below_floor": False},
            {"status": "样本不足", "positive": False, "below_floor": False},
        ]))


class Drawdown(unittest.TestCase):
    def test_peak_to_trough_and_opening_loss(self):
        days = pd.to_datetime(["2006-01-03", "2006-01-04", "2006-01-05", "2006-01-06"])
        stats = drawdown_stats(pd.Series([0.0, 0.10, -0.20, 0.05], index=days))
        self.assertAlmostEqual(stats["max_drawdown"], -0.20, places=12)
        self.assertAlmostEqual(stats["depth"], 0.20, places=12)
        self.assertEqual(stats["peak"], pd.Timestamp("2006-01-04"))
        self.assertEqual(stats["trough"], pd.Timestamp("2006-01-05"))
        self.assertEqual(stats["underwater_days"], 2)
        self.assertEqual(stats["longest_underwater_days"], 2)
        opened = drawdown_stats(pd.Series([-0.25, 0.0], index=days[:2]))
        self.assertAlmostEqual(opened["depth"], 0.25, places=12)
        self.assertIsNone(opened["peak"])
        self.assertEqual(opened["underwater_days"], 2)

    def test_five_point_gap_includes_the_boundary(self):
        days = pd.bdate_range("2006-01-02", periods=5)
        strategy = pd.Series([-0.10, 0.0, 0.0, 0.0, 0.0], index=days)
        benchmark = pd.Series([-0.05, 0.0, 0.0, 0.0, 0.0], index=days)
        report = criterion_4(strategy, benchmark)
        self.assertAlmostEqual(report["deeper_by"], 0.05, places=12)
        self.assertTrue(report["engineering_check"])
        deeper = pd.Series([-0.11, 0.0, 0.0, 0.0, 0.0], index=days)
        self.assertFalse(criterion_4(deeper, benchmark)["engineering_check"])
        self.assertIsNone(report["formal_pass"])

    def test_position_matched_uses_the_average_equity_weight(self):
        days = pd.bdate_range("2006-01-02", periods=4)
        held = pd.DataFrame({
            "csi": [0.50, 0.50, 0.50, 0.50],
            "gold": [0.25, 0.25, 0.25, 0.25],
            "cash": [0.25, 0.25, 0.25, 0.25],
        }, index=days)
        classes = {"csi": "A股宽基", "gold": "商品", "cash": "现金"}
        weight = equity_weight(held, classes)
        self.assertTrue((weight == 0.50).all())
        matched = position_matched(pd.Series(0.01, index=days), pd.Series(0.0, index=days), weight)
        self.assertAlmostEqual(matched["average_equity_weight"], 0.50, places=12)
        self.assertTrue((matched["returns"] == 0.005).all())


class SharpePaper(unittest.TestCase):
    """Bailey & López de Prado (2014), A Numerical Example."""

    def _paper(self, n_trials: int, skew: float, kurtosis: float) -> dict:
        sr = 2.5 / math.sqrt(250.0)
        variance = 0.5 / 250.0
        return deflated_sharpe_ratio(sr, variance, n_trials, 1250, skew, kurtosis)

    def test_published_numbers(self):
        main = self._paper(100, -3.0, 10.0)
        self.assertAlmostEqual(main["sr0"], 0.1132, places=4)
        self.assertAlmostEqual(main["probability"], 0.9004, places=4)
        self.assertAlmostEqual(self._paper(46, -3.0, 10.0)["probability"], 0.9505, places=4)
        self.assertAlmostEqual(self._paper(88, 0.0, 3.0)["probability"], 0.9505, places=4)
        sr = 2.5 / math.sqrt(250.0)
        self.assertGreater(probabilistic_sharpe_ratio(sr, 0.0, 1250, -3.0, 10.0), 0.999)
        self.assertTrue(main["engineering_check"])
        self.assertIsNone(main["formal_pass"])

    def test_moments_follow_pandas_and_cash_is_subtracted(self):
        days = pd.bdate_range("2006-01-02", periods=8)
        values = pd.Series([-0.02, 0.01, 0.00, 0.03, -0.01, 0.02, 0.01, -0.04], index=days)
        moments = sharpe_moments(values)
        excess = values - 0.0
        self.assertAlmostEqual(moments["sr"], float(excess.mean() / excess.std(ddof=1)), places=12)
        self.assertAlmostEqual(moments["skew"], float(values.skew()), places=12)
        self.assertAlmostEqual(moments["kurtosis"], float(values.kurtosis()) + 3.0, places=12)
        cash = pd.Series(0.01, index=days)
        net = sharpe_moments(values, cash)
        spread = values - cash
        self.assertAlmostEqual(net["sr"], float(spread.mean() / spread.std(ddof=1)), places=12)

    def test_trial_count_adds_the_exploration_block(self):
        """D11-3：行数 + 28 + 31。无 ledger 为 59；10 行正式配置为 69。不碰仓库里的 ledger。"""
        before = _ledger_bytes()
        self.assertEqual(EXPLORATION_TRIALS, 28)
        self.assertEqual(ORCHESTRATOR_DIAGNOSTIC_TRIALS, 31)
        self.assertEqual(TRIAL_BASE, 59)
        missing = ROOT / "results" / "v3" / "missing-ledger.csv"
        self.assertFalse(missing.exists())
        self.assertEqual(trial_count(missing), TRIAL_BASE)
        with tempfile.TemporaryDirectory() as tmp:
            two = Path(tmp) / "two.csv"
            _write_ledger(two, [
                "2026-10-25T00:00:00+08:00,abc,A,{},design,dev",
                "2026-10-25T00:00:01+08:00,abc,B,{},design,dev",
            ])
            self.assertEqual(trial_count(two), 2 + TRIAL_BASE)
            ten = Path(tmp) / "ten.csv"
            _write_ledger(ten, [
                f"2026-10-25T00:00:{i:02d}+08:00,abc,A,{{}},design,dev" for i in range(10)
            ])
            with ten.open(encoding="utf-8", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 10)
            self.assertEqual(trial_count(ten), 69)
            # B1：即使某一行写着影子 C1，也不从 31 里扣掉。那是另一套公式，本次不做。
            shadow = Path(tmp) / "shadow-c1.csv"
            _write_ledger(shadow, [
                "2026-10-27T00:00:00+08:00,abc,A,shadow-C1,design,dev",
            ])
            self.assertEqual(trial_count(shadow), 1 + TRIAL_BASE)
        self.assertAlmostEqual(variance_of_sharpes([0.1, 0.3, 0.2]), float(pd.Series([0.1, 0.3, 0.2]).var(ddof=1)))
        self.assertEqual(_ledger_bytes(), before)
        self.assertFalse(missing.exists())

    def test_checked_in_formal_ledger_counts_sixty_nine(self):
        """当前仓库的正式 ledger 是 10 行 v3.1 设计期配置，trial_count() 为 69。只读。"""
        self.assertTrue(LEDGER.is_file())
        before = _ledger_bytes()
        with LEDGER.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 10)
        self.assertTrue(all("v3.1" in (row.get("params") or "") for row in rows))
        self.assertEqual(trial_count(), 69)
        self.assertEqual(trial_count(LEDGER), 69)
        self.assertEqual(_ledger_bytes(), before)


class Controls(unittest.TestCase):
    def test_rank_definition(self):
        rank = percentile_rank(0.10, [0.0, 0.2, 0.10, -0.1])
        self.assertEqual(rank["n_better"], 1)
        self.assertEqual(rank["n_tie"], 1)
        self.assertEqual(rank["n_worse"], 2)
        self.assertAlmostEqual(rank["percentile"], 0.75, places=12)
        self.assertFalse(rank["in_top_decile"])
        self.assertEqual(rank["rank_from_best"], 2)
        top = percentile_rank(1.0, [0.0] * 10)
        self.assertTrue(top["in_top_decile"])
        self.assertAlmostEqual(top["percentile"], 1.0, places=12)

    def test_null_a_matches_null_b_when_everyone_is_eligible(self):
        days = pd.bdate_range("2006-02-01", periods=6)
        names = ["a", "b", "c", "d"]
        targets = pd.DataFrame(
            [{"a": 0.5, "b": 0.0, "c": 0.0, "d": 0.5, "cash": 0.0},
             {"a": 0.0, "b": 1.0, "c": 0.0, "d": 0.0, "cash": 0.0}],
            index=[days[1], days[4]])
        eligible = pd.DataFrame(True, index=targets.index, columns=names)
        left = null_b_targets(targets, names, "cash", np.random.default_rng(20261024), 1e-6)
        right = null_a_targets(targets, names, "cash", np.random.default_rng(20261024), 1e-6, eligible)
        pd.testing.assert_frame_equal(left, right)

    def test_null_a_stays_inside_the_eligible_set(self):
        days = pd.bdate_range("2006-03-01", periods=3)
        names = ["a", "b", "c"]
        targets = pd.DataFrame([{"a": 0.5, "b": 0.5, "c": 0.0, "cash": 0.0}], index=[days[0]])
        eligible = pd.DataFrame({"a": [True], "b": [True], "c": [False]}, index=targets.index)
        drawn = null_a_targets(targets, names, "cash", np.random.default_rng(7), 1e-6, eligible)
        self.assertAlmostEqual(float(drawn.iloc[0]["c"]), 0.0, places=12)
        self.assertAlmostEqual(float(drawn.iloc[0][["a", "b", "c", "cash"]].sum()), 1.0, places=12)

    def test_zero_cost_path_matches_the_subset_mean(self):
        days = pd.bdate_range("2006-04-03", periods=6)
        names = ["a", "b", "c"]
        rng = np.random.default_rng(3)
        pnl = pd.DataFrame(rng.normal(0.0, 0.01, size=(len(days), 3)), index=days, columns=names)
        pnl["cash"] = 0.0
        targets = pd.DataFrame([{"a": 1.0, "b": 0.0, "c": 0.0, "cash": 0.0}], index=[days[0]])
        fees = {name: 0.0 for name in pnl.columns}
        drawn = null_b_targets(targets, names, "cash", np.random.default_rng(11), 1e-6)
        book = simulate(pnl, drawn, fees, "cash")
        chosen = [name for name in names if float(drawn.iloc[0][name]) > 1e-8]
        self.assertAlmostEqual(float(book.net.iloc[0]), 0.0, places=12)
        expected = pnl[chosen].mean(axis=1).iloc[1:].to_numpy(dtype=float)
        np.testing.assert_allclose(book.net.iloc[1:].to_numpy(dtype=float), expected, atol=1e-12)

    def test_random_walk_ranks_are_near_uniform(self):
        rng = np.random.default_rng(20261024)
        reps = 400
        n_controls = 80
        stats = np.empty(reps)
        for _ in range(reps):
            rets = rng.normal(0.0, 0.01, size=(120, 10))
            strategy = rets[:, rng.choice(10, size=3, replace=False)].mean(axis=1)
            strategy_ann = annualized_return(strategy)
            nulls = np.empty(n_controls)
            for j in range(n_controls):
                subset = rets[:, rng.choice(10, size=3, replace=False)].mean(axis=1)
                nulls[j] = annualized_return(subset)
            stats[_] = percentile_rank(strategy_ann, nulls)["fraction_strictly_worse"]
        self.assertGreater(float(stats.mean()), 0.45)
        self.assertLess(float(stats.mean()), 0.55)
        counts, _edges = np.histogram(stats, bins=np.linspace(0.0, 1.0, 11))
        expected = reps / 10.0
        chi = float(((counts - expected) ** 2 / expected).sum())
        self.assertLess(chi, 23.0)
        # 有漂移的那一只不该再像均匀分布。
        edged = rng.normal(0.0, 0.01, size=(80, 8))
        edged[:, 0] += 0.02
        strategy_ann = annualized_return(edged[:, 0])
        nulls = np.array([
            annualized_return(edged[:, int(rng.integers(0, 8))])
            for _ in range(200)
        ])
        self.assertGreaterEqual(percentile_rank(strategy_ann, nulls)["percentile"], 0.90)

    def test_simulated_control_on_random_walk_is_not_stuck_at_an_extreme(self):
        ranks = []
        rng = np.random.default_rng(20261024)
        for rep in range(20):
            days = pd.bdate_range("2006-05-01", periods=30)
            names = [f"a{i}" for i in range(6)]
            pnl = pd.DataFrame(rng.normal(0.0, 0.01, size=(len(days), 6)), index=days, columns=names)
            pnl["cash"] = 0.0
            pick = list(rng.choice(names, size=2, replace=False))
            row = {name: (0.5 if name in pick else 0.0) for name in names}
            row["cash"] = 0.0
            targets = pd.DataFrame([row], index=[days[0]])
            fees = {name: 0.0 for name in pnl.columns}
            book = simulate(pnl, targets, fees, "cash")
            report = criterion_2(
                book.net, pnl, targets, fees, names, "cash", n_trials=12, seed=20261024 + rep)
            ranks.append(report["null_b"]["fraction_strictly_worse"])
            self.assertIsNone(report["formal_pass"])
            self.assertLessEqual(pd.Timestamp(book.net.index.max()), pd.Timestamp("2015-12-31"))
        self.assertGreater(float(np.mean(ranks)), 0.20)
        self.assertLess(float(np.mean(ranks)), 0.80)

    def test_eligibility_follows_the_decision_day_not_the_fill(self):
        spec = replace(load_spec(), lookbacks=(20,), ns=(1,), frequencies=("month",))
        days = pd.bdate_range("2006-01-02", periods=60)
        signal = pd.DataFrame({
            "hot": np.full(len(days), 0.01),
            "cold": np.full(len(days), -0.01),
            "cash": np.full(len(days), CASH),
        }, index=days)
        fees = {"hot": 0.001, "cold": 0.001, "cash": 0.0005}
        market = market_from_returns(signal, fees)
        book = execute(market, spec, "A")
        gate = eligibility_on_targets(market, spec, book.targets)
        self.assertTrue(bool(gate["hot"].iloc[-1]))
        self.assertFalse(bool(gate["cold"].iloc[-1]))
        self.assertEqual(criterion_2.__kwdefaults__["n_trials"], 1000)
        self.assertEqual(load_spec().seed, 20261024)


class Selection(unittest.TestCase):
    def test_walk_forward_matches_the_engine_and_ignores_the_next_year(self):
        spec = replace(
            load_spec(), lookbacks=(20,), ns=(3, 8), frequencies=("month",),
            b_first_year=2007, b_train_start="2006-01-03")
        days = pd.bdate_range("2006-01-03", periods=520)
        signal = pd.DataFrame({
            "lead": np.full(len(days), 0.002),
            "other": np.zeros(len(days)),
            "cash": np.full(len(days), CASH),
        }, index=days)
        fees = {"lead": 0.0005, "other": 0.001, "cash": 0.0005}
        benchmark = pd.Series(0.0, index=days)
        market = market_from_returns(signal, fees, benchmark=benchmark)
        book = execute(market, spec, "B")
        candidates = {}
        frames = {}
        for key in spec.candidates():
            alone = execute(market, spec, "A", n=key[0], freq=key[1])
            candidates[key] = alone.net
            frames[key] = alone.targets
        chosen = walk_forward(
            candidates, benchmark, train_start=spec.b_train_start,
            first_apply_year=spec.b_first_year, dates=market.dates, keys=list(spec.candidates()))
        self.assertEqual(chosen["choices"], book.choices)
        pd.testing.assert_frame_equal(stitch_targets(frames, chosen["choices"]), book.targets)
        shocked = signal.copy()
        shocked.loc[shocked.index.year >= 2007, ["lead", "other"]] = -0.01
        later_market = market_from_returns(shocked, fees, benchmark=benchmark)
        later_book = execute(later_market, spec, "B")
        self.assertEqual(book.choices[2007], later_book.choices[2007])

    def test_premium_tie_keeps_the_smaller_pair(self):
        days = pd.bdate_range("2006-01-03", periods=400)
        series = pd.Series(0.001, index=days)
        benchmark = pd.Series(0.0, index=days)
        keys = premium_keys()
        self.assertEqual(keys, ((120, 0.10), (120, 0.15), (250, 0.10), (250, 0.15)))
        chosen = walk_forward(
            {key: series for key in keys}, benchmark, train_start="2006-01-03",
            first_apply_year=2007, dates=days, keys=list(keys))
        self.assertEqual(chosen["choices"][2007], (120, 0.10))
        flipped = walk_forward(
            {key: series for key in keys}, benchmark, train_start="2006-01-03",
            first_apply_year=2007, dates=days, keys=list(reversed(keys)))
        self.assertEqual(flipped["choices"][2007], (250, 0.15))
        shocked = series.copy()
        shocked.loc[shocked.index.year >= 2007] = -0.02
        later = walk_forward(
            {(120, 0.10): shocked, (250, 0.15): series}, benchmark, train_start="2006-01-03",
            first_apply_year=2007, dates=days, keys=[(120, 0.10), (250, 0.15)])
        self.assertEqual(chosen["choices"][2007], later["choices"][2007])
        with self.assertRaises(EvalError):
            walk_forward(
                {(120, 0.10): pd.Series(0.0, index=pd.bdate_range("2016-01-04", periods=5))},
                pd.Series(0.0, index=pd.bdate_range("2016-01-04", periods=5)),
                train_start="2006-01-01", first_apply_year=2011,
                dates=pd.bdate_range("2016-01-04", periods=5))

    def test_pbo_hand_cases_and_noise(self):
        overfit = np.concatenate([
            np.tile([0.01, -0.01], (4, 1)),
            np.tile([-0.01, 0.01], (4, 1)),
        ])
        self.assertAlmostEqual(cscv_pbo(overfit, n_blocks=2)["pbo"], 1.0, places=12)
        dominant = np.column_stack([np.full(8, 0.01), np.full(8, -0.01)])
        self.assertAlmostEqual(cscv_pbo(dominant, n_blocks=2)["pbo"], 0.0, places=12)
        tied = np.column_stack([np.full(8, 0.01), np.full(8, 0.01)])
        # 样本内并列取第一列。两列样本外也相同，名次不会低于中位，PBO 为 0。
        self.assertAlmostEqual(cscv_pbo(tied, n_blocks=2)["pbo"], 0.0, places=12)
        rng = np.random.default_rng(20261024)
        scores = []
        for _ in range(40):
            noise = rng.normal(0.0, 0.01, size=(320, 8))
            result = cscv_pbo(noise, n_blocks=16)
            self.assertEqual(result["n_splits"], 12870)
            self.assertEqual(result["dropped_rows"], 0)
            scores.append(result["pbo"])
        # 同一条噪声矩阵上的 12,870 个拆分高度相关，单次 PBO 可以离 0.5 较远。
        # 全是噪声时，多次独立候选集的 PBO 平均值靠近 0.5。
        self.assertAlmostEqual(float(np.mean(scores)), 0.5, delta=0.10)
        dated = pd.DataFrame(rng.normal(0.0, 0.01, size=(32, 2)), index=pd.bdate_range("2006-01-02", periods=32))
        self.assertGreaterEqual(cscv_pbo(dated, n_blocks=2)["pbo"], 0.0)
        self.assertEqual(cscv_pbo(np.resize(noise, (17, 8))[:17], n_blocks=16)["dropped_rows"], 1)


class Robustness(unittest.TestCase):
    def _market(self):
        days = pd.bdate_range("2006-01-02", periods=80)
        names = ["winner", "us", "gold", "quiet"]
        signal = pd.DataFrame({
            "winner": np.full(len(days), 0.004),
            "us": np.full(len(days), 0.0005),
            "gold": np.zeros(len(days)),
            "quiet": np.full(len(days), -0.001),
            "cash": np.full(len(days), CASH),
        }, index=days)
        fees = {name: 0.001 for name in signal.columns}
        fees["cash"] = 0.0005
        return market_from_returns(signal, fees, benchmark=pd.Series(0.0, index=days))

    def test_seven_cases_report_criterion_1_without_a_verdict(self):
        market = self._market()
        classes = {"winner": "A股宽基", "us": "美股和全球主题", "gold": "商品", "quiet": "A股行业"}
        self.assertEqual(best_containers(market.pnl, list(market.names), 3), ["winner", "us", "gold"])
        spec = replace(load_spec(), lookbacks=(20,), ns=(1,), frequencies=("month",))
        books = robustness_books(market, spec, "A", classes)
        self.assertAlmostEqual(float(books["cost_double"].cost.sum()), 2.0 * float(books["base"].cost.sum()), places=10)
        self.assertGreater(float(books["base"].cost.sum()), 0.0)
        delayed = delay_targets(books["base"].targets, market.dates)
        self.assertFalse(delayed.empty)
        shifted = pd.DatetimeIndex(delayed.index)
        original = pd.DatetimeIndex(books["base"].targets.sort_index().index)
        self.assertGreater(shifted.min(), original.min())
        held = books["drop_best_1"].decisions.iloc[-1]
        self.assertLess(float(held.get("winner", 0.0)), 1e-8)
        us_held = books["drop_us_theme"].decisions.iloc[-1]
        self.assertLess(float(us_held.get("us", 0.0)), 1e-8)
        table = robustness_table(books, market.benchmark, market.dates)
        self.assertEqual([row["case"] for row in table["cases"]], [
            "base", "cost_double", "delay_1d", "drop_us_theme", "drop_commodity",
            "drop_best_1", "drop_best_2", "drop_best_3",
        ])
        self.assertNotIn("formal_pass", table)
        self.assertFalse(LOCK.exists())

    def test_delay_does_not_invent_a_date_past_the_sample(self):
        days = pd.bdate_range("2006-06-01", periods=4)
        targets = pd.DataFrame({"a": [1.0], "cash": [0.0]}, index=[days[-1]])
        delayed = delay_targets(targets, days)
        self.assertTrue(delayed.empty)


class Report(unittest.TestCase):
    def test_design_report_does_not_judge(self):
        before = _ledger_bytes()
        calendar = _calendar("2006-01-02", "2010-12-31")
        strategy = pd.Series(0.0004, index=calendar)
        strategy.iloc[::5] = -0.001
        benchmark = pd.Series(0.0, index=calendar)
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "trial-ledger.csv"
            _write_ledger(ledger, [
                "2026-10-25T00:00:00+08:00,abc,A,{},design,dev",
                "2026-10-25T00:00:01+08:00,abc,B,{},design,dev",
            ])
            report = evaluate_design(
                strategy, benchmark, calendar, sr_variance=0.002, cash=benchmark, ledger_path=ledger)
        self.assertEqual(report["period"], "design")
        self.assertEqual(report["end"], "2015-12-31")
        self.assertIsNone(report["formal_pass"])
        self.assertEqual(report["action"]["action"], "未判定")
        self.assertIsNone(report["criterion_1"]["formal_pass"])
        self.assertEqual(report["criterion_3"]["eras"][2]["status"], "未计算")
        self.assertIsNone(report["criterion_3"]["eras"][2]["excess"])
        self.assertEqual(report["trial_count"], 2 + TRIAL_BASE)
        self.assertIn("probability", report["criterion_5"])
        self.assertFalse(LOCK.exists())
        self.assertEqual(_ledger_bytes(), before)

    def test_action_table(self):
        self.assertEqual(action_for(
            criterion_1=True, criterion_2=True, criterion_3=True, criterion_4=True, criterion_5=True,
            formal=False)["action"], "未判定")
        self.assertEqual(action_for(
            criterion_1=True, criterion_2=True, criterion_3=True, criterion_4=True, criterion_5=True,
            formal=True)["action"], "进入前向模拟盘")
        self.assertEqual(action_for(
            criterion_1=True, criterion_2=False, criterion_3=True, criterion_4=True, criterion_5=True,
            formal=True)["action"], "不作为轮动策略")
        self.assertEqual(action_for(
            criterion_1=False, criterion_2=True, criterion_3=True, criterion_4=True, criterion_5=True,
            formal=True)["action"], "关闭 v3")
        self.assertEqual(action_for(
            criterion_1=True, criterion_2=True, criterion_3=True, criterion_4=True, criterion_5=False,
            formal=True)["action"], "进入前向模拟盘")
        weak = action_for(
            criterion_1=True, criterion_2=True, criterion_3=True, criterion_4=True, criterion_5=False,
            formal=True)
        self.assertIn("证据弱", weak["reason"])
        self.assertEqual(action_for(
            criterion_1=True, criterion_2=True, criterion_3=False, criterion_4=True, criterion_5=True,
            formal=True)["action"], "未列入 §7.3 的组合")


if __name__ == "__main__":
    unittest.main()
