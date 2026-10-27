"""PROVISIONAL — 不是 v3.1 代码冻结的签收项。

Owner D11 / addendum-1 A1 的边界测试。Reviewer #48 R1 的 B2 仍开着：
连续 5 个上交所交易日没有有效价时，A1 写「退出排名」，持仓和未成交离场挂单
「沿用现行实现」。Owner 还没有闭合这件事。本文件不改成交假设。

已经写死的部分（顺延到下一有效价、等待期用前向沿用计收益、等待期遇到常规调仓则调仓优先）
按 A1 的字面钉住 `simulate_path`：计价序列里出现 0、负数或非有限值时不成交。
`load_market` 在交给离场函数之前会把缺印的收盘前向沿用成上一笔正价格；本文件不把那条接线
当成已经批准的规则，也不改它。五日排名旗标按现有 `align_same_day` 钉住，那是 v3 §3.3
已经写过的 fresh 规则。持仓在满五日之后是否强平，只记录今天的 `simulate_path`，标 TODO B2。

夹具自己给出交易日序列，不把实盘「现行实现」当成已经批准的规则。
"""
from __future__ import annotations

import unittest

import pandas as pd

from src.v3.engine.exit import simulate_path
from src.v3.engine.prices import align_same_day

FEE = 0.001


def _run(levels: pd.Series, rets: pd.Series, targets: dict) -> object:
    days = levels.index
    pnl = pd.DataFrame({"asset": rets.to_numpy(dtype=float), "cash": 0.0}, index=days)
    frame = pd.DataFrame({"asset": levels.to_numpy(dtype=float), "cash": 1.0}, index=days)
    tgt = pd.DataFrame.from_dict(targets, orient="index", dtype=float)
    tgt.index = pd.to_datetime(list(targets))
    return simulate_path(
        pnl, frame, {"asset": FEE, "cash": 0.0005}, "cash", targets=tgt, exit_drawdown=0.10)


def _kinds(book) -> set[str]:
    if book.exits is None or book.exits.empty or "kind" not in book.exits.columns:
        return set()
    return set(book.exits["kind"])


class ProvisionalA1Defer(unittest.TestCase):
    """A1 已经写明的顺延。计划成交日的计价用原始收盘；收益用前向沿用。"""

    def test_invalid_close_defers_to_the_next_valid_session_and_charges_the_sell_fee(self):
        days = pd.to_datetime([
            "2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09", "2006-01-10", "2006-01-11",
        ])
        # 01-06 收盘跌破 90 产生信号。计划卖出日 01-09 没有有效价，01-10 才有。
        # 收益按 §3.3 前向沿用：缺价日收益为 0，下一笔有效价吃掉整段缺口。
        levels = pd.Series([100.0, 100.0, 80.0, float("nan"), 70.0, 70.0], index=days)
        rets = pd.Series([0.0, 0.0, 80.0 / 100.0 - 1.0, 0.0, 70.0 / 80.0 - 1.0, 0.0], index=days)
        book = _run(levels, rets, {"2006-01-05": {"asset": 1.0, "cash": 0.0}})
        self.assertIn("signal", _kinds(book))
        self.assertIn("exit", _kinds(book))
        signal = book.exits.loc[book.exits["kind"].eq("signal"), "date"]
        filled = book.exits.loc[book.exits["kind"].eq("exit"), "date"]
        self.assertEqual(str(pd.Timestamp(signal.iloc[0]).date()), "2006-01-06")
        self.assertEqual(str(pd.Timestamp(filled.iloc[0]).date()), "2006-01-10")
        self.assertAlmostEqual(float(book.exits.loc[book.exits["kind"].eq("exit"), "price"].iloc[0]), 70.0, places=8)
        deferred = {str(pd.Timestamp(day).date()) for day in book.deferred_exits["date"]}
        self.assertEqual(deferred, {"2006-01-09"})
        self.assertAlmostEqual(float(book.cost.loc[days[3]]), 0.0, places=12)
        self.assertAlmostEqual(float(book.net.loc[days[3]]), 0.0, places=12)
        self.assertAlmostEqual(float(book.cost.loc[days[4]]), FEE, places=8)
        self.assertAlmostEqual(float(book.sell.loc[days[4]]), 1.0, places=8)
        self.assertAlmostEqual(float(book.net.loc[days[4]]), 70.0 / 80.0 - 1.0 - FEE, places=8)
        self.assertAlmostEqual(float(book.held.loc[days[4], "asset"]), 1.0, places=8)
        self.assertAlmostEqual(float(book.held.loc[days[5], "asset"]), 0.0, places=8)
        self.assertAlmostEqual(float(book.held.loc[days[5], "cash"]), 1.0, places=8)

    def test_zero_or_negative_close_is_not_a_fill(self):
        days = pd.to_datetime(["2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09", "2006-01-10"])
        levels = pd.Series([100.0, 100.0, 80.0, 0.0, 75.0], index=days)
        rets = pd.Series([0.0, 0.0, -0.2, 0.0, 75.0 / 80.0 - 1.0], index=days)
        book = _run(levels, rets, {"2006-01-05": {"asset": 1.0, "cash": 0.0}})
        filled = book.exits.loc[book.exits["kind"].eq("exit"), "date"]
        self.assertEqual(str(pd.Timestamp(filled.iloc[0]).date()), "2006-01-10")
        self.assertAlmostEqual(float(book.cost.loc[days[3]]), 0.0, places=12)
        self.assertAlmostEqual(float(book.net.loc[days[3]]), 0.0, places=12)
        negative = levels.copy()
        negative.iloc[3] = -1.0
        book = _run(negative, rets, {"2006-01-05": {"asset": 1.0, "cash": 0.0}})
        filled = book.exits.loc[book.exits["kind"].eq("exit"), "date"]
        self.assertEqual(str(pd.Timestamp(filled.iloc[0]).date()), "2006-01-10")

    def test_rebalance_during_deferral_clears_the_pending_exit(self):
        days = pd.to_datetime([
            "2006-01-04", "2006-01-05", "2006-01-06", "2006-01-09", "2006-01-10", "2006-01-11",
        ])
        levels = pd.Series([100.0, 100.0, 80.0, float("nan"), 80.0, 80.0], index=days)
        rets = pd.Series([0.0, 0.0, -0.2, 0.0, 0.0, 0.0], index=days)
        book = _run(levels, rets, {
            "2006-01-05": {"asset": 1.0, "cash": 0.0},
            "2006-01-10": {"asset": 0.0, "cash": 1.0},
        })
        self.assertNotIn("exit", _kinds(book))
        self.assertIn("signal", _kinds(book))
        deferred = {str(pd.Timestamp(day).date()) for day in book.deferred_exits["date"]}
        self.assertEqual(deferred, {"2006-01-09"})
        # 一次常规调仓：卖出资产 0.10%，买入现金 0.05%。没有再加一笔离场费。
        self.assertAlmostEqual(float(book.cost.loc[days[4]]), FEE + 0.0005, places=8)
        self.assertAlmostEqual(float(book.sell.loc[days[4]]), 1.0, places=8)
        self.assertAlmostEqual(float(book.buy.loc[days[4]]), 1.0, places=8)
        self.assertAlmostEqual(float(book.held.loc[days[5], "asset"]), 0.0, places=8)
        self.assertAlmostEqual(float(book.held.loc[days[5], "cash"]), 1.0, places=8)
        self.assertAlmostEqual(float(book.cost.loc[days[5]]), 0.0, places=12)


class ProvisionalA1Ranking(unittest.TestCase):
    def test_five_consecutive_missing_sessions_clear_the_ranking_flag(self):
        """v3 §3.3：最近 5 个交易日都没有有效价，fresh 为假，退出排名。

        价格序列本身仍前向沿用。这只钉排名旗标，不钉持仓怎么处理。
        """
        calendar = pd.bdate_range("2006-01-03", periods=8)
        native = pd.Series([100.0], index=pd.DatetimeIndex([calendar[0]]))
        level, fresh = align_same_day(native, pd.DatetimeIndex(calendar), 5)
        self.assertTrue(bool(fresh.iloc[0]))
        self.assertTrue(bool(fresh.iloc[4]))
        self.assertFalse(bool(fresh.iloc[5]))
        self.assertFalse(bool(fresh.iloc[7]))
        self.assertAlmostEqual(float(level.iloc[5]), 100.0, places=8)

    def test_five_missing_sessions_do_not_force_sell_the_holding(self):
        # TODO(Reviewer B2 / PR #48): A1 对「持仓 + 未成交挂单」只写了沿用现行实现。
        # Owner 还没有闭合：满 5 日退出排名之后，持仓是继续留着、按最后价强平，还是挂单作废。
        # 下面只钉今天的 simulate_path：不因满 5 日把权重划进现金，挂单留到下一笔有效价。
        # 这不是代码冻结签收。
        days = pd.to_datetime([
            "2006-01-04", "2006-01-05", "2006-01-06",
            "2006-01-09", "2006-01-10", "2006-01-11", "2006-01-12", "2006-01-13",
            "2006-01-16",
        ])
        levels = pd.Series(
            [100.0, 100.0, 80.0, float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), 60.0],
            index=days,
        )
        rets = pd.Series(
            [0.0, 0.0, -0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 60.0 / 80.0 - 1.0],
            index=days,
        )
        book = _run(levels, rets, {"2006-01-05": {"asset": 1.0, "cash": 0.0}})
        missing = [str(pd.Timestamp(day).date()) for day in days[3:8]]
        deferred = [str(pd.Timestamp(day).date()) for day in book.deferred_exits["date"]]
        self.assertEqual(deferred, missing)
        filled = book.exits.loc[book.exits["kind"].eq("exit"), "date"]
        self.assertEqual(len(filled), 1)
        self.assertEqual(str(pd.Timestamp(filled.iloc[0]).date()), "2006-01-16")
        for day in days[3:8]:
            self.assertAlmostEqual(float(book.held.loc[day, "asset"]), 1.0, places=8)
            self.assertAlmostEqual(float(book.cost.loc[day]), 0.0, places=12)
            self.assertAlmostEqual(float(book.net.loc[day]), 0.0, places=12)
        self.assertAlmostEqual(float(book.cost.loc[days[8]]), FEE, places=8)


if __name__ == "__main__":
    unittest.main()
