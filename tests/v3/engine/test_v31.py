"""v3.1 工程接线：发布日开关、10% 离场边界、休市回归、溢价进执行链。

不计算 2016 年以后的组合收益，不写 LOCK。
"""
from __future__ import annotations

import sqlite3
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from src.v3.data.history import OFFICIAL, PUBLISH_DATE, history_floor, history_gap
from src.v3.engine.arms import execute
from src.v3.engine.exit import simulate_path, triggered
from src.v3.engine.market import load_market, market_from_returns
from src.v3.engine.prices import mask_publish, returns_from_level
from src.v3.engine.spec import load_spec
from src.v3.premium.rules import NORMAL, PULSE

ROOT = Path(__file__).resolve().parents[3]
CASH = 0.02 / 252


def _container(asset, publish="", base="", code="IDX"):
    return {
        "id": "sample",
        "asset_class": asset,
        "name": asset,
        "research": {
            "series_code": code,
            "series_status": "in_db",
            "publish_date": publish or "取不到",
            "base_date": base or "取不到",
        },
    }


class HistoryMode(unittest.TestCase):
    def test_official_uses_base_date_and_keeps_theme_listing(self):
        broad = _container("A股宽基", publish="2014-10-17", base="2004-12-31")
        self.assertEqual(history_floor(broad, OFFICIAL), "2004-12-31")
        self.assertEqual(history_floor(broad, PUBLISH_DATE), "2014-10-17")
        theme = _container("美股和全球主题", publish="2015-07-13", base="2000-01-01", code="159941")
        self.assertEqual(history_floor(theme, OFFICIAL), "2015-07-13")
        self.assertEqual(history_floor(theme, PUBLISH_DATE), "2015-07-13")
        unknown = _container("港股")
        self.assertEqual(history_floor(unknown, OFFICIAL), "")
        self.assertEqual(history_floor(unknown, PUBLISH_DATE), "")
        self.assertIn("基日无法核实", history_gap(unknown, "2000-01-03"))
        self.assertIn("发布日无法核实", history_gap(unknown, "2000-01-03"))

    def test_pre_publish_bars_stay_in_the_official_mask_only(self):
        calendar = pd.to_datetime(["2006-01-03", "2006-01-04", "2006-01-05", "2006-01-06"])
        native = pd.Series([90.0, 100.0, 110.0, 121.0], index=calendar)
        official = mask_publish(native, pd.Timestamp("2004-12-31"))
        contrasted = mask_publish(native, pd.Timestamp("2006-01-05"))
        self.assertAlmostEqual(float(returns_from_level(official).iloc[1]), 100.0 / 90.0 - 1.0)
        self.assertTrue(pd.isna(returns_from_level(contrasted).iloc[2]))
        self.assertAlmostEqual(float(returns_from_level(contrasted).iloc[3]), 0.10)

    def test_named_gaps_do_not_invent_a_series(self):
        chinext = {
            "id": "chinext", "asset_class": "A股宽基", "name": "创业板指",
            "research": {"series_code": "", "series_status": "取不到", "publish_date": "取不到", "base_date": "取不到"},
        }
        gold = {
            "id": "gold", "asset_class": "商品", "name": "黄金",
            "research": {"series_code": "Au99.99", "series_status": "partial", "publish_date": "取不到", "base_date": "取不到"},
        }
        bond = {
            "id": "cgb-10y", "asset_class": "债券", "name": "10年国债",
            "research": {"series_code": "CBA04501", "series_status": "in_db", "publish_date": "取不到", "base_date": "2007-12-29"},
        }
        nasdaq = {
            "id": "ndx100", "asset_class": "美股宽基", "name": "纳指100",
            "research": {"series_code": "XNDX", "series_status": "in_db", "publish_date": "取不到", "base_date": "取不到"},
        }
        self.assertIn("无已登记官方序列", history_gap(chinext, ""))
        self.assertIn("不补造", history_gap(gold, "2008-08-11"))
        self.assertIn("2008", history_gap(bond, "2008-01-02"))
        self.assertIn("人民币全收益", history_gap(nasdaq, "2005-01-04"))
        self.assertNotIn("CBA00601", history_floor(bond, OFFICIAL))

    def test_database_switches_csi1000_and_drops_sandy_zero(self):
        db = ROOT / "data" / "market.sqlite"
        if not db.exists() or db.stat().st_size < 1000:
            self.skipTest("market.sqlite 不在这台机器上")
        con = sqlite3.connect(db)
        try:
            sandy = con.execute(
                "SELECT close FROM bars WHERE code = 'XNDX' AND adj = 'raw' AND date = '2012-10-29'"
            ).fetchone()
            self.assertIsNone(sandy)
            bad = con.execute(
                """SELECT count(*) FROM bars
                   WHERE adj = 'raw' AND close <= 0 AND source IN ('nasdaq', 'yahoo')"""
            ).fetchone()[0]
            self.assertEqual(bad, 0)
            treasury = con.execute("SELECT count(*) FROM bars WHERE code = 'CBA00601'").fetchone()[0]
            self.assertGreater(treasury, 0)
        finally:
            con.close()
        from src.v3.data.universe import containers
        ids = {row["id"] for row in containers()}
        codes = {
            (row.get("research") or {}).get("series_code")
            for row in containers()
        }
        self.assertNotIn("CBA00601", codes)
        self.assertIn("csi1000", ids)
        spec = load_spec()
        official = load_market(db, containers(), "A", "index", "2006-02-28", spec, history_mode=OFFICIAL)
        contrasted = load_market(db, containers(), "A", "index", "2006-02-28", spec, history_mode=PUBLISH_DATE)
        self.assertGreater(int(official.signal["csi1000"].notna().sum()), 10)
        self.assertEqual(int(contrasted.signal["csi1000"].notna().sum()), 0)
        self.assertLessEqual(official.signal.index.max(), pd.Timestamp("2015-12-31"))


class ExitBoundary(unittest.TestCase):
    def test_threshold_is_strict(self):
        self.assertFalse(triggered(90.0, 100.0, 0.10))
        self.assertFalse(triggered(100.0 * 0.9, 100.0, 0.10))
        self.assertTrue(triggered(89.999, 100.0, 0.10))
        self.assertFalse(triggered(92.0, 100.0, 0.08))
        self.assertTrue(triggered(91.9, 100.0, 0.08))
        self.assertFalse(triggered(float("nan"), 100.0, 0.10))
        self.assertFalse(triggered(0.0, 100.0, 0.10))

    def _path(self, prices, targets, fees=None):
        days = pd.to_datetime(list(prices))
        level = pd.Series([prices[day] for day in prices], index=days, dtype=float)
        # 收益来自价格。第一天没有收益。
        rets = level.pct_change()
        rets.iloc[0] = 0.0
        pnl = pd.DataFrame({"asset": rets, "cash": CASH}, index=days)
        levels = pd.DataFrame({"asset": level, "cash": 1.0}, index=days)
        if fees is None:
            fees = {"asset": 0.001, "cash": 0.0005}
        frame = pd.DataFrame.from_dict(targets, orient="index")
        frame.index = pd.to_datetime(frame.index)
        return simulate_path(pnl, levels, fees, "cash", targets=frame, exit_drawdown=0.10)

    def test_equal_ninety_does_not_sell_and_a_tick_below_does(self):
        held = self._path(
            {"2006-01-03": 100.0, "2006-01-04": 100.0, "2006-01-05": 90.0, "2006-01-06": 90.0},
            {"2006-01-04": {"asset": 1.0, "cash": 0.0}},
        )
        self.assertAlmostEqual(float(held.held.loc["2006-01-06", "asset"]), 1.0, places=8)
        self.assertTrue(held.exits.empty or "exit" not in set(held.exits["kind"]))
        sold = self._path(
            {
                "2006-01-03": 100.0, "2006-01-04": 100.0, "2006-01-05": 89.0,
                "2006-01-06": 89.0, "2006-01-09": 89.0,
            },
            {"2006-01-04": {"asset": 1.0, "cash": 0.0}},
        )
        self.assertIn("signal", set(sold.exits["kind"]))
        self.assertEqual(str(pd.Timestamp(sold.exits.loc[sold.exits["kind"].eq("signal"), "date"].iloc[0]).date()), "2006-01-05")
        self.assertEqual(str(pd.Timestamp(sold.exits.loc[sold.exits["kind"].eq("exit"), "date"].iloc[0]).date()), "2006-01-06")
        self.assertAlmostEqual(float(sold.held.loc["2006-01-09", "asset"]), 0.0, places=8)
        self.assertAlmostEqual(float(sold.held.loc["2006-01-09", "cash"]), 1.0, places=8)
        self.assertAlmostEqual(float(sold.cost.loc["2006-01-06"]), 0.001, places=8)

    def test_rebalance_same_day_cancels_the_exit_without_a_second_fee(self):
        book = self._path(
            {
                "2006-01-03": 100.0, "2006-01-04": 100.0, "2006-01-05": 80.0,
                "2006-01-06": 80.0, "2006-01-09": 80.0,
            },
            {
                "2006-01-04": {"asset": 1.0, "cash": 0.0},
                "2006-01-06": {"asset": 1.0, "cash": 0.0},
            },
        )
        kinds = set(book.exits["kind"]) if not book.exits.empty else set()
        self.assertIn("signal", kinds)
        self.assertNotIn("exit", kinds)
        self.assertAlmostEqual(float(book.held.loc["2006-01-09", "asset"]), 1.0, places=6)
        self.assertAlmostEqual(float(book.cost.loc["2006-01-06"]), 0.0, places=8)
        self.assertAlmostEqual(float(book.peaks.loc["2006-01-06", "asset"]), 80.0, places=6)

    def test_invalid_price_does_not_fill_a_zero_and_does_not_sell(self):
        days = pd.to_datetime(["2006-01-03", "2006-01-04", "2006-01-05", "2006-01-06"])
        level = pd.Series([100.0, 100.0, 80.0, float("nan")], index=days)
        rets = pd.Series([0.0, 0.0, -0.2, float("nan")], index=days)
        pnl = pd.DataFrame({"asset": rets, "cash": CASH}, index=days)
        levels = pd.DataFrame({"asset": level, "cash": 1.0}, index=days)
        targets = pd.DataFrame([{"asset": 1.0, "cash": 0.0}], index=[days[1]])
        book = simulate_path(pnl, levels, {"asset": 0.001, "cash": 0.0005}, "cash", targets=targets)
        self.assertAlmostEqual(float(book.held.loc[days[3], "asset"]), 1.0, places=8)
        self.assertFalse((book.net <= -0.9).any())
        self.assertIn("missing_exit_price", set(book.deferred_exits["reason"]))
        self.assertNotIn("exit", set(book.exits["kind"]))

    def test_sold_name_can_be_bought_on_the_next_decision_not_the_same_close(self):
        days = pd.bdate_range("2006-01-02", periods=8)
        level = pd.Series(100.0, index=days)
        level.iloc[3:] = 80.0
        rets = level.pct_change().fillna(0.0)
        pnl = pd.DataFrame({"asset": rets, "cash": CASH}, index=days)
        levels = pd.DataFrame({"asset": level, "cash": 1.0}, index=days)
        decisions = pd.DataFrame(
            [{"asset": 1.0, "cash": 0.0}, {"asset": 1.0, "cash": 0.0}],
            index=[days[0], days[4]],
        )
        book = simulate_path(
            pnl, levels, {"asset": 0.001, "cash": 0.0005}, "cash", decisions=decisions)
        exit_day = pd.Timestamp(book.exits.loc[book.exits["kind"].eq("exit"), "date"].iloc[0])
        self.assertAlmostEqual(float(book.held.loc[exit_day, "asset"]), 1.0, places=6)
        later = book.held.loc[book.held.index > exit_day, "asset"]
        self.assertGreater(float(later.max()), 0.5)

    def test_arm_return_is_the_mean_of_path_returns(self):
        spec = replace(load_spec(), lookbacks=(20,), ns=(3, 5), frequencies=("month",))
        days = pd.bdate_range("2006-01-02", periods=80)
        signal = pd.DataFrame({
            "winner": np.full(len(days), 0.002),
            "other": np.full(len(days), -0.001),
            "cash": np.full(len(days), CASH),
        }, index=days)
        fees = {"winner": 0.0005, "other": 0.001, "cash": 0.0005}
        market = market_from_returns(signal, fees)
        book = execute(market, spec, "A")
        self.assertEqual(len(book.paths), 2)
        mean = sum(path.net for path in book.paths.values()) / 2.0
        pd.testing.assert_series_equal(book.net, mean, check_names=False)
        self.assertTrue((book.held.sum(axis=1) - 1.0).abs().max() < 1e-8)


class PremiumWiring(unittest.TestCase):
    def test_pulse_blocks_a_new_buy_and_exit_is_not_bought_back(self):
        days = pd.bdate_range("2006-01-02", periods=8)
        level = pd.Series(100.0, index=days, dtype=float)
        level.iloc[4:] = 80.0
        rets = level.pct_change().fillna(0.0)
        pnl = pd.DataFrame({"qdii": rets, "cash": CASH}, index=days)
        levels = pd.DataFrame({"qdii": level, "cash": 1.0}, index=days)
        state = [NORMAL] * len(days)
        state[0] = PULSE
        panel = pd.DataFrame({
            "premium": np.full(len(days), 0.20),
            "state": state,
        }, index=days)
        premium = {
            "panels": {"qdii": {"513100": panel}},
            "ids": {"qdii"},
            "eligible_on": pd.DataFrame({"qdii": True}, index=days),
        }

        class _Gate:
            def on(self, _day):
                return premium

        decisions = pd.DataFrame(
            [{"qdii": 1.0, "cash": 0.0}, {"qdii": 1.0, "cash": 0.0}],
            index=[days[0], days[5]],
        )
        book = simulate_path(
            pnl, levels, {"qdii": 0.0015, "cash": 0.0005}, "cash",
            decisions=decisions, premium=_Gate())
        # 决策日是脉冲且未持有：成交日开盘前仍是现金，当天收盘也不会买上。
        self.assertAlmostEqual(float(book.held.loc[days[2], "qdii"]), 0.0, places=8)
        early = book.code_audit
        if not early.empty:
            early = early[pd.to_datetime(early["date"]) <= days[2]]
        self.assertTrue(early.empty)
        # 第二次决策日状态已不是脉冲。买入发生在下一交易日，不是信号当天。
        self.assertAlmostEqual(float(book.held.loc[days[5], "qdii"]), 0.0, places=8)
        bought = book.code_audit[book.code_audit["code"].eq("513100")]
        self.assertFalse(bought.empty)
        self.assertGreater(pd.Timestamp(bought["date"].iloc[0]), days[5])

    def test_new_buy_picks_the_lower_premium_code(self):
        days = pd.bdate_range("2006-01-02", periods=4)
        pnl = pd.DataFrame({"qdii": np.zeros(len(days)), "cash": CASH}, index=days)
        levels = pd.DataFrame({"qdii": np.full(len(days), 100.0), "cash": 1.0}, index=days)
        cheap = pd.DataFrame({"premium": np.full(len(days), 0.01), "state": NORMAL}, index=days)
        rich = pd.DataFrame({"premium": np.full(len(days), 0.08), "state": NORMAL}, index=days)
        premium = {
            "panels": {"qdii": {"159941": rich, "513100": cheap}},
            "ids": {"qdii"},
            "eligible_on": pd.DataFrame({"qdii": True, "local": True}, index=days),
        }

        class _Gate:
            def on(self, _day):
                return premium

        decisions = pd.DataFrame([{"qdii": 0.4, "local": 0.6, "cash": 0.0}], index=[days[0]])
        pnl["local"] = 0.0
        levels["local"] = 100.0
        book = simulate_path(
            pnl, levels, {"qdii": 0.0015, "local": 0.0005, "cash": 0.0005}, "cash",
            decisions=decisions, premium=_Gate())
        held = book.code_audit
        self.assertIn("513100", set(held["code"]))
        self.assertNotIn("159941", set(held["code"]))
        # 非溢价容器不走选代码。
        self.assertTrue(held[held["container"].eq("local")].empty)

    def test_index_pool_does_not_apply_premium(self):
        spec = replace(load_spec(), lookbacks=(20,), ns=(1,), frequencies=("month",))
        days = pd.bdate_range("2006-01-02", periods=40)
        signal = pd.DataFrame({
            "qdii": np.full(len(days), 0.01),
            "cash": np.full(len(days), CASH),
        }, index=days)
        market = market_from_returns(signal, {"qdii": 0.0015, "cash": 0.0005})
        book = execute(market, spec, "A")
        self.assertTrue(book.code_audit is None or book.code_audit.empty)
        self.assertGreater(float(book.held["qdii"].max()), 0.5)

    def test_exit_sell_is_not_reversed_the_same_close(self):
        days = pd.bdate_range("2006-01-02", periods=7)
        level = pd.Series(100.0, index=days, dtype=float)
        level.iloc[3:] = 80.0
        rets = level.pct_change().fillna(0.0)
        pnl = pd.DataFrame({"qdii": rets, "cash": CASH}, index=days)
        levels = pd.DataFrame({"qdii": level, "cash": 1.0}, index=days)
        panel = pd.DataFrame({
            "premium": np.full(len(days), -0.08),
            "state": "结构型折价",
        }, index=days)
        premium = {
            "panels": {"qdii": {"513100": panel}},
            "ids": {"qdii"},
            "eligible_on": pd.DataFrame({"qdii": True}, index=days),
        }

        class _Gate:
            def on(self, _day):
                return premium

        # 第一天决定买入。跌破后的决策日落在卖出日，新单要到下一交易日才成交。
        decisions = pd.DataFrame(
            [{"qdii": 1.0, "cash": 0.0}, {"qdii": 1.0, "cash": 0.0}],
            index=[days[0], days[4]],
        )
        book = simulate_path(
            pnl, levels, {"qdii": 0.0015, "cash": 0.0005}, "cash",
            decisions=decisions, premium=_Gate())
        exit_day = pd.Timestamp(book.exits.loc[book.exits["kind"].eq("exit"), "date"].iloc[0])
        self.assertEqual(exit_day, days[4])
        nxt = book.held.index[book.held.index.get_loc(exit_day) + 1]
        self.assertAlmostEqual(float(book.held.loc[nxt, "qdii"]), 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
