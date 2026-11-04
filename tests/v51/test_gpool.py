"""G 池的接线。不跑 2003–2026 的整段。"""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.v3.engine.book import simulate, to_execution
from src.v3.engine.ledger import COLUMNS
from src.v51.gpool import (
    BOND,
    CASH,
    CHINA_IDS,
    DEVELOPED,
    EMERGING,
    GOLD,
    LEG,
    US,
    WINDOW_END,
    WINDOW_START,
    a1_weights,
    apply_g_results,
    benchmark_g,
    cash_returns,
    fees_for,
    g_single_name_nets,
    g_universe,
    raw_tickers,
    record_g,
    traded_names,
)
from src.v51.params import V51Error


class UniverseWiring(unittest.TestCase):
    def test_three_markets_and_no_chinese_series(self):
        universe = g_universe()
        self.assertEqual([market.name for market in universe.markets], ["美国", "发达市场", "新兴市场"])
        self.assertEqual([market.representative for market in universe.markets], ["SPY", "EFA", "EEM"])
        self.assertEqual(universe.markets[0].members, US)
        self.assertEqual(universe.markets[1].members, DEVELOPED)
        self.assertEqual(universe.markets[2].members, EMERGING)
        self.assertEqual(universe.bond, BOND)
        self.assertEqual(universe.gold, GOLD)
        self.assertEqual(universe.cash, CASH)
        names = traded_names()
        self.assertEqual(names, [*US, *DEVELOPED, *EMERGING, BOND, GOLD])
        self.assertFalse(CHINA_IDS & set(names))
        self.assertNotIn("DBC", names)
        self.assertNotIn("TLT", names)
        self.assertNotIn("SHY", names)
        self.assertEqual(raw_tickers()[-1], "DTB3")

    def test_raw_files_are_real_downloads(self):
        root = Path(__file__).resolve().parents[2] / "results" / "v5" / "other-market" / "raw"
        for ticker in raw_tickers():
            blob = (root / f"{ticker}.csv").read_bytes()[:48]
            self.assertFalse(blob.startswith(b"version https://git-lfs.github.com/spec/v1"), ticker)
            self.assertTrue(blob.startswith(b"date,"), ticker)


class CashAndCosts(unittest.TestCase):
    def test_act_360_uses_the_latest_rate_on_or_before_the_session(self):
        dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-08"])
        rates = pd.Series([1.0, 2.0], index=pd.to_datetime(["2024-01-02", "2024-01-04"]))
        got = cash_returns(pd.DatetimeIndex(dates), rates, pd.Timestamp("2023-12-29"))
        self.assertAlmostEqual(float(got.iloc[0]), 0.01 * 4 / 360)
        self.assertAlmostEqual(float(got.iloc[1]), 0.01 * 1 / 360)
        self.assertAlmostEqual(float(got.iloc[2]), 0.02 * 5 / 360)

    def test_full_switch_costs_two_legs(self):
        index = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
        returns = pd.DataFrame({
            "SPY": [0.01, 0.02, -0.01],
            CASH: [0.0001, 0.0001, 0.0001],
        }, index=index)
        decisions = pd.DataFrame([{"SPY": 1.0, CASH: 0.0}], index=index[:1])
        book = simulate(
            returns, to_execution(decisions, index), fees_for(["SPY", CASH]), CASH, allow_after=True,
        )
        self.assertAlmostEqual(float(book.cost.iloc[1]), 2 * LEG)
        self.assertAlmostEqual(float(book.net.iloc[1]), 0.0001 - 2 * LEG)
        nets = g_single_name_nets(returns, index[:1], [["SPY"]])
        self.assertTrue(np.allclose(nets[0], book.net.to_numpy(dtype=float)))

    def test_benchmark_opens_at_target_and_charges_the_next_month(self):
        index = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-02-01"])
        returns = pd.DataFrame({"SPY": [0.10, 0.0, 0.0], BOND: [0.0, 0.0, 0.0]}, index=index)
        frame = benchmark_g(returns)
        self.assertAlmostEqual(float(frame["net"].iloc[0]), 0.06)
        self.assertAlmostEqual(float(frame["cost"].iloc[0]), 0.0)
        self.assertGreater(float(frame["cost"].iloc[2]), 0.0)
        self.assertAlmostEqual(float(frame["SPY"].iloc[2]), 0.60)
        self.assertAlmostEqual(float(frame[BOND].iloc[2]), 0.40)


class A1Rule(unittest.TestCase):
    def test_tie_keeps_spy_and_cash_win_keeps_ief(self):
        months = pd.date_range("2019-07-31", periods=13, freq="ME")
        levels = pd.DataFrame({
            "SPY": np.linspace(100, 110, len(months)),
            "EFA": np.linspace(100, 110, len(months)),
            "IEF": np.linspace(100, 101, len(months)),
        }, index=months)
        cash = pd.Series(0.0, index=pd.bdate_range(months[0], months[-1]))
        day = months[-1]
        tied = a1_weights(levels, cash, months, day)
        self.assertEqual(tied["SPY"], 1.0)
        self.assertEqual(tied["EFA"], 0.0)
        levels.loc[day, "SPY"] = 100.0
        defensive = a1_weights(levels, cash, months, day)
        self.assertEqual(defensive["IEF"], 1.0)
        self.assertEqual(defensive[CASH], 0.0)


class GateAndLedger(unittest.TestCase):
    def test_criterion_five_does_not_pass_the_whole_gate_or_touch_six(self):
        rows = [
            {"item": "0", "pool": "index", "metric": "calmar", "strategy": "1", "benchmark": "0.4",
             "hurdle": "R0 的 95 分位", "status": "通过", "note": "不动"},
            {"item": "5", "pool": "G", "metric": "calmar", "strategy": "", "benchmark": "",
             "hurdle": "高于 G 的 R0 的 95 分位", "status": "待 R6", "note": "旧"},
            {"item": "5", "pool": "G", "metric": "cagr", "strategy": "", "benchmark": "",
             "hurdle": "高于基准 G", "status": "待 R6", "note": "旧"},
            {"item": "6", "pool": "index", "metric": "p_bull", "strategy": "-1", "benchmark": "0",
             "hurdle": "≥ 0", "status": "未通过", "note": "不动"},
            {"item": "入围", "pool": "both", "metric": "", "strategy": "", "benchmark": "",
             "hurdle": "0–6", "status": "未完成", "note": "旧"},
        ]
        got = apply_g_results(
            rows, calmar_value=1.2, calmar_hurdle=0.5, cagr_value=0.08, cagr_hurdle=0.07,
            n=2000, seed=20261101,
        )
        self.assertEqual(got[0]["note"], "不动")
        self.assertEqual(got[1]["status"], "通过")
        self.assertEqual(got[2]["status"], "通过")
        self.assertEqual(got[3]["status"], "未通过")
        self.assertEqual(got[3]["note"], "不动")
        self.assertEqual(got[4]["status"], "未完成")
        self.assertIn("第 6 条", got[4]["note"])
        self.assertNotIn("全部通过", got[4]["note"])
        failed = apply_g_results(
            rows, calmar_value=0.4, calmar_hurdle=0.5, cagr_value=0.08, cagr_hurdle=0.07,
            n=2000, seed=20261101,
        )
        self.assertEqual(failed[1]["status"], "未通过")
        self.assertEqual(failed[4]["status"], "未完成")

    def test_ledger_replaces_only_the_g_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trial-ledger.csv"
            design = {
                "run_at": "2026-11-04T16:58:12+08:00",
                "git_sha": "abc",
                "arm": "v5.1",
                "params": json.dumps({"case": "v5.1", "kind": "design", "pool": "index"}, sort_keys=True),
                "segment": "design",
                "runner": "dev",
            }
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
                writer.writeheader()
                writer.writerow(design)
            payload = {
                "case": "v5.1",
                "kind": "other-market",
                "pool": "G",
                "china_pnl": False,
                "robustness": False,
                "start": WINDOW_START,
                "end": WINDOW_END,
            }
            record_g(payload, path)
            record_g(payload, path)
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["segment"], "design")
        self.assertEqual(rows[1]["segment"], "other-market")
        self.assertEqual(rows[1]["arm"], "v5.1")

    def test_refuses_a_china_pnl_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trial-ledger.csv"
            with self.assertRaises(V51Error):
                record_g({
                    "case": "v5.1", "kind": "other-market", "pool": "G",
                    "china_pnl": True, "robustness": False,
                }, path)


if __name__ == "__main__":
    unittest.main()
