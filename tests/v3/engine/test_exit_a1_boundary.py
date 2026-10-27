"""addendum-1 第 2 版 A1 第 5 条的四个边界。D12-6。

钉住现行 `align_same_day`、`pick_row` 和 `simulate_path`，不改成交分支。
上交所交易日用夹具给出的工作日序列。缺印日的计价序列由 `align_same_day` 前向沿用。
"""
from __future__ import annotations

import unittest

import pandas as pd

from src.v3.engine.exit import simulate_path
from src.v3.engine.prices import align_same_day, returns_from_level
from src.v3.engine.score import Lookback, pick_row
from src.v3.engine.spec import load_spec

FEE = 0.001
CASH_FEE = 0.0005
STALE = load_spec().stale_limit


def _run(levels: pd.Series, rets: pd.Series, targets: dict) -> object:
    days = levels.index
    pnl = pd.DataFrame({"asset": rets.to_numpy(dtype=float), "cash": 0.0}, index=days)
    frame = pd.DataFrame({"asset": levels.to_numpy(dtype=float), "cash": 1.0}, index=days)
    tgt = pd.DataFrame.from_dict(targets, orient="index", dtype=float)
    tgt.index = pd.to_datetime(list(targets))
    return simulate_path(
        pnl, frame, {"asset": FEE, "cash": CASH_FEE}, "cash", targets=tgt, exit_drawdown=0.10)


def _kinds(book) -> list[tuple[str, str]]:
    if book.exits is None or book.exits.empty or "kind" not in book.exits.columns:
        return []
    return [
        (str(kind), str(pd.Timestamp(day).date()))
        for kind, day in zip(book.exits["kind"], book.exits["date"])
    ]


def _deferred(book) -> list[str]:
    if book.deferred_exits is None or book.deferred_exits.empty:
        return []
    return [str(pd.Timestamp(day).date()) for day in book.deferred_exits["date"]]


def _price(book, kind: str) -> float:
    return float(book.exits.loc[book.exits["kind"].eq(kind), "price"].iloc[0])


class A1Boundary(unittest.TestCase):
    """A1 §5 的四种情况。预期和现行成交一致。"""

    def test_holiday_without_own_price_fills_at_the_carried_close(self):
        """计划卖出日没有自身价格，计价序列已前向沿用 → 当天按沿用值成交。"""
        days = pd.to_datetime([
            "2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09", "2006-01-10", "2006-01-11",
        ])
        native = pd.Series([100.0, 100.0, 80.0, float("nan"), 70.0, 70.0], index=days)
        level, _fresh = align_same_day(native, pd.DatetimeIndex(days), STALE)
        sell = days[3]
        self.assertTrue(pd.isna(native.loc[sell]))
        self.assertAlmostEqual(float(level.loc[sell]), 80.0, places=8)
        rets = returns_from_level(level).fillna(0.0)
        book = _run(level, rets, {"2006-01-05": {"asset": 1.0, "cash": 0.0}})
        self.assertEqual(_kinds(book), [("signal", "2006-01-06"), ("exit", "2006-01-09")])
        self.assertAlmostEqual(_price(book, "exit"), 80.0, places=8)
        self.assertEqual(_deferred(book), [])
        self.assertAlmostEqual(float(book.cost.loc[sell]), FEE, places=8)
        self.assertAlmostEqual(float(book.sell.loc[sell]), 1.0, places=8)
        self.assertAlmostEqual(float(book.net.loc[sell]), -FEE, places=8)
        self.assertAlmostEqual(float(book.held.loc[sell, "asset"]), 1.0, places=8)
        self.assertAlmostEqual(float(book.held.loc[days[4], "asset"]), 0.0, places=8)
        self.assertAlmostEqual(float(book.held.loc[days[4], "cash"]), 1.0, places=8)
        self.assertAlmostEqual(float(book.cost.loc[days[4]]), 0.0, places=12)

    def test_zero_or_nan_planned_sell_does_not_fill_until_the_next_valid_day(self):
        """计划卖出日计价为 0、负数、NaN 或非有限值 → 当天不成交，下一个有效日成交。"""
        days = pd.to_datetime([
            "2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09", "2006-01-10", "2006-01-11",
        ])
        rets = pd.Series([0.0, 0.0, -0.2, 0.0, 75.0 / 80.0 - 1.0, 0.0], index=days)
        zero = pd.Series([100.0, 100.0, 80.0, 0.0, 75.0, 75.0], index=days)
        aligned, _fresh = align_same_day(zero, pd.DatetimeIndex(days), STALE)
        self.assertAlmostEqual(float(aligned.iloc[3]), 0.0, places=8)
        marks = {
            "zero": aligned,
            "nan": pd.Series([100.0, 100.0, 80.0, float("nan"), 75.0, 75.0], index=days),
            "negative": pd.Series([100.0, 100.0, 80.0, -1.0, 75.0, 75.0], index=days),
            "nonfinite": pd.Series([100.0, 100.0, 80.0, float("inf"), 75.0, 75.0], index=days),
        }
        for name, levels in marks.items():
            with self.subTest(mark=name):
                book = _run(levels, rets, {"2006-01-05": {"asset": 1.0, "cash": 0.0}})
                self.assertEqual(_kinds(book), [("signal", "2006-01-06"), ("exit", "2006-01-10")])
                self.assertAlmostEqual(_price(book, "exit"), 75.0, places=8)
                self.assertEqual(_deferred(book), ["2006-01-09"])
                self.assertAlmostEqual(float(book.cost.loc[days[3]]), 0.0, places=12)
                self.assertAlmostEqual(float(book.net.loc[days[3]]), 0.0, places=12)
                self.assertAlmostEqual(float(book.held.loc[days[3], "asset"]), 1.0, places=8)
                self.assertAlmostEqual(float(book.held.loc[days[4], "asset"]), 1.0, places=8)
                self.assertAlmostEqual(float(book.cost.loc[days[4]]), FEE, places=8)
                self.assertAlmostEqual(float(book.sell.loc[days[4]]), 1.0, places=8)
                self.assertAlmostEqual(float(book.net.loc[days[4]]), 75.0 / 80.0 - 1.0 - FEE, places=8)
                self.assertAlmostEqual(float(book.held.loc[days[5], "asset"]), 0.0, places=8)
                self.assertAlmostEqual(float(book.held.loc[days[5], "cash"]), 1.0, places=8)

    def test_rebalance_on_a_pending_exit_day_clears_the_order_and_charges_once(self):
        """挂单遇到常规调仓日 → 调仓优先，挂单清除，只收这一次调仓费。"""
        days = pd.to_datetime(["2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09", "2006-01-10"])
        levels = pd.Series([100.0, 100.0, 80.0, 80.0, 80.0], index=days)
        rets = pd.Series([0.0, 0.0, -0.2, 0.0, 0.0], index=days)
        book = _run(levels, rets, {
            "2006-01-05": {"asset": 1.0, "cash": 0.0},
            "2006-01-09": {"asset": 0.0, "cash": 1.0},
        })
        self.assertEqual(_kinds(book), [("signal", "2006-01-06")])
        self.assertEqual(_deferred(book), [])
        self.assertAlmostEqual(float(book.cost.loc[days[3]]), FEE + CASH_FEE, places=8)
        self.assertAlmostEqual(float(book.sell.loc[days[3]]), 1.0, places=8)
        self.assertAlmostEqual(float(book.buy.loc[days[3]]), 1.0, places=8)
        self.assertAlmostEqual(float(book.held.loc[days[4], "asset"]), 0.0, places=8)
        self.assertAlmostEqual(float(book.held.loc[days[4], "cash"]), 1.0, places=8)
        self.assertAlmostEqual(float(book.cost.loc[days[4]]), 0.0, places=12)

    def test_five_missing_sessions_drop_ranking_and_pending_exit_fills_at_carry(self):
        """连续 5 个上交所交易日没有自身价格：第 5 日起退出排名，下一调仓日按沿用值调出。

        若离场挂单已经存在，下一交易日按沿用值成交，不等到第 5 日，也不等到之后的新价格。
        """
        self.assertEqual(STALE, 5)
        days = pd.to_datetime([
            "2006-01-04", "2006-01-05", "2006-01-06",
            "2006-01-09", "2006-01-10", "2006-01-11", "2006-01-12", "2006-01-13",
            "2006-01-16", "2006-01-17",
        ])
        native = pd.Series([100.0, 100.0, 100.0, *([float("nan")] * 7)], index=days)
        level, fresh = align_same_day(native, pd.DatetimeIndex(days), STALE)
        fifth = days[7]
        fourth = days[6]
        rebalance = days[8]
        self.assertTrue(bool(fresh.loc[fourth]))
        self.assertFalse(bool(fresh.loc[fifth]))
        self.assertFalse(bool(fresh.loc[rebalance]))
        self.assertTrue(pd.isna(native.loc[fifth]))
        self.assertAlmostEqual(float(level.loc[fifth]), 100.0, places=8)
        self.assertAlmostEqual(float(level.loc[rebalance]), 100.0, places=8)
        panel = Lookback(
            total=pd.DataFrame({"asset": 0.2, "cash": 0.0}, index=days),
            score=pd.DataFrame({"asset": 1.0, "cash": 0.0}, index=days),
            ok=pd.DataFrame({"asset": True, "cash": False}, index=days),
        )
        liquidity = pd.DataFrame({"asset": fresh.to_numpy()}, index=days)
        still = pick_row(panel, fourth, 1, ["asset"], "cash", {"asset": "asset"}, liquidity)
        dropped = pick_row(panel, fifth, 1, ["asset"], "cash", {"asset": "asset"}, liquidity)
        self.assertAlmostEqual(float(still["asset"]), 1.0, places=8)
        self.assertNotIn("asset", dropped)
        self.assertAlmostEqual(float(dropped["cash"]), 1.0, places=8)
        rets = returns_from_level(level).fillna(0.0)
        book = _run(level, rets, {
            "2006-01-05": {"asset": 1.0, "cash": 0.0},
            "2006-01-16": {"asset": float(dropped.get("asset", 0.0)), "cash": float(dropped["cash"])},
        })
        self.assertEqual(_kinds(book), [])
        self.assertEqual(_deferred(book), [])
        self.assertAlmostEqual(float(book.held.loc[fifth, "asset"]), 1.0, places=8)
        self.assertAlmostEqual(float(book.cost.loc[fifth]), 0.0, places=12)
        self.assertAlmostEqual(float(book.cost.loc[rebalance]), FEE + CASH_FEE, places=8)
        self.assertAlmostEqual(float(book.sell.loc[rebalance]), 1.0, places=8)
        self.assertAlmostEqual(float(book.buy.loc[rebalance]), 1.0, places=8)
        self.assertAlmostEqual(float(book.net.loc[rebalance]), -(FEE + CASH_FEE), places=8)
        self.assertAlmostEqual(float(book.held.loc[days[9], "asset"]), 0.0, places=8)
        self.assertAlmostEqual(float(book.held.loc[days[9], "cash"]), 1.0, places=8)

        pending = pd.Series(
            [100.0, 100.0, 80.0, *([float("nan")] * 5), 60.0, 60.0], index=days)
        carried, pending_fresh = align_same_day(pending, pd.DatetimeIndex(days), STALE)
        self.assertTrue(pd.isna(pending.loc[days[3]]))
        self.assertAlmostEqual(float(carried.loc[days[3]]), 80.0, places=8)
        self.assertFalse(bool(pending_fresh.loc[fifth]))
        self.assertAlmostEqual(float(carried.loc[days[8]]), 60.0, places=8)
        book = _run(carried, returns_from_level(carried).fillna(0.0), {"2006-01-05": {"asset": 1.0, "cash": 0.0}})
        self.assertEqual(_kinds(book), [("signal", "2006-01-06"), ("exit", "2006-01-09")])
        self.assertAlmostEqual(_price(book, "exit"), 80.0, places=8)
        self.assertEqual(_deferred(book), [])
        self.assertAlmostEqual(float(book.cost.loc[days[3]]), FEE, places=8)
        self.assertAlmostEqual(float(book.held.loc[days[4], "asset"]), 0.0, places=8)
        self.assertAlmostEqual(float(book.cost.loc[days[8]]), 0.0, places=12)


if __name__ == "__main__":
    unittest.main()
