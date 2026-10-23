"""收手版慢阀、设计期保护和配置。行情是构造的，不读真实库。"""
import csv
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

import tests  # noqa: F401
from src.portfolio.__main__ import main
from src.portfolio.config import FallbackError, load_config
from src.portfolio.replicate import daily_book, replicate
from src.portfolio.target import target_snapshot
from src.portfolio.valve import slow_valve


ROOT = Path(__file__).resolve().parents[2]


def _cfg():
    return load_config(ROOT / "config" / "portfolio.toml")


class Config(unittest.TestCase):
    def test_file_keeps_the_d2_sleeves(self):
        cfg = _cfg()
        self.assertFalse(hasattr(cfg, "pending"))
        self.assertEqual(len(cfg.a_share), 16)
        self.assertEqual(cfg.a_share[:4], ("沪深300", "中证500", "中证1000", "创业板"))
        self.assertEqual(cfg.a_share[-1], "红利")
        self.assertEqual(cfg.overseas, ("纳指100", "标普500"))
        self.assertEqual(cfg.a_weight, 0.70)
        self.assertEqual(cfg.o_weight, 0.30)
        self.assertEqual(cfg.out, 0.25)
        self.assertEqual(cfg.back, 0.10)
        self.assertFalse(cfg.valve_enabled)
        self.assertEqual(cfg.judge, "month_end")
        self.assertEqual(cfg.haven_code, "511880")
        self.assertEqual(cfg.cash_annual, 0.02)
        self.assertEqual(cfg.cost_one_way, 0.0005)
        self.assertEqual(cfg.rebalance, "monthly")
        self.assertEqual(cfg.design_end, pd.Timestamp("2015-12-31"))
        self.assertEqual(cfg.nav_lag, 2)
        self.assertEqual(cfg.lot_size, 100)
        self.assertAlmostEqual(cfg.band, 0.075)
        self.assertAlmostEqual(cfg.premium_cap, 0.10)


class Valve(unittest.TestCase):
    def test_exit_uses_shadow_and_keeps_the_exit_month_invested(self):
        shadow = pd.Series([0.10, -0.30], index=pd.period_range("2024-01", periods=2, freq="M").to_timestamp("M"))
        held, switches, during = slow_valve(shadow, 0.25, 0.10, 0.02 / 12)
        self.assertEqual(list(during), [1, 1])
        self.assertEqual(switches, 1)
        self.assertAlmostEqual(held.iloc[0], 0.10)
        self.assertAlmostEqual(held.iloc[1], -0.30)
        shadow = pd.concat([shadow, pd.Series([0.05], index=[shadow.index[-1] + pd.offsets.MonthEnd(1)])])
        held, switches, during = slow_valve(shadow, 0.25, 0.10, 0.02 / 12)
        self.assertEqual(list(during), [1, 1, 0])
        self.assertAlmostEqual(held.iloc[2], 0.02 / 12)
        self.assertEqual(switches, 1)

    def test_reentry_resets_the_high(self):
        # 高点 1.10 后跌到 0.77 出场。反弹超过 10% 在 0.85 回场，高点重置为 0.85。
        # 下一月再跌 20%：相对新高不到 25%，仍在场。若高点还留在 1.10，这一跌会出场。
        index = pd.period_range("2024-01", periods=4, freq="M").to_timestamp("M")
        shadow = pd.Series([0.10, -0.30, 0.85 / 0.77 - 1, -0.20], index=index)
        held, switches, during = slow_valve(shadow, 0.25, 0.10, 0.0)
        self.assertEqual(list(during), [1, 1, 0, 1])
        self.assertEqual(switches, 2)
        self.assertAlmostEqual(held.iloc[2], 0.0)
        self.assertAlmostEqual(held.iloc[3], -0.20)

    def test_thresholds_are_strict(self):
        exact = pd.Series([-0.25], index=pd.period_range("2024-01", periods=1, freq="M").to_timestamp("M"))
        _held, switches, during = slow_valve(exact, 0.25, 0.10, 0.0)
        self.assertEqual(switches, 0)
        self.assertEqual(int(during.iloc[0]), 1)
        index = pd.period_range("2024-01", periods=2, freq="M").to_timestamp("M")
        # 跌一半后净值 0.5。再涨 10% 少一个很小的数，反弹不超过 back，不回场。
        shadow = pd.Series([-0.5, 0.10 - 1e-12], index=index)
        _held, switches, during = slow_valve(shadow, 0.25, 0.10, 0.0)
        self.assertEqual(list(during), [1, 0])
        self.assertEqual(switches, 1)
        shadow = pd.Series([-0.5, 0.10 + 1e-12], index=index)
        _held, switches, during = slow_valve(shadow, 0.25, 0.10, 0.0)
        self.assertEqual(list(during), [1, 0])
        self.assertEqual(switches, 2)


class Protection(unittest.TestCase):
    def test_replicate_rejects_an_end_after_the_design_window(self):
        missing = Path("/tmp/r4-no-such-panel.sqlite")
        with self.assertRaises(FallbackError) as caught:
            replicate(missing, "2016-01-01", _cfg(), haven_db=None)
        self.assertIn("拒绝", str(caught.exception))
        self.assertFalse(missing.exists())
        code = main(["replicate", "--panel", str(missing), "--end", "2016-01-01", "--haven-db", str(missing)])
        self.assertEqual(code, 2)

    def test_replicate_accepts_the_design_end_on_a_synthetic_panel(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "panel.sqlite"
            _write_panel(path, _flat_rows())
            result = replicate(path, "2015-12-31", _one_name_config(tmp), haven_db=None)
            self.assertEqual(result["end"], "2015-12-31")
            self.assertIn("monthly", result)
            self.assertLessEqual(pd.Timestamp(result["daily"]["last"]), pd.Timestamp("2015-12-31"))


class DailyLag(unittest.TestCase):
    def test_exit_trades_on_the_next_session_and_pays_cost(self):
        cfg = _one_name_config_inline()
        index = pd.to_datetime(["2024-01-31", "2024-02-29", "2024-03-01", "2024-03-04"])
        closes = pd.DataFrame({"甲": [100.0, 70.0, 70.0, 70.0]}, index=index)
        # 二月 −30% 在场；二月月末出场。三月第一个交易日的收益仍按在场计，收盘换成货币并扣成本。
        state = pd.Series([1, 0], index=pd.to_datetime(["2024-02-29", "2024-03-31"]))
        book = daily_book(closes, state, cfg, pd.Series(0.0, index=index))
        self.assertEqual(list(book.index.strftime("%Y-%m-%d")), ["2024-02-29", "2024-03-01", "2024-03-04"])
        self.assertAlmostEqual(book.iloc[0], -0.30)
        # 3 月 1 日价格没变，换仓把 100% 从甲换成货币：成交金额 2，成本 2 × 0.0005。
        self.assertAlmostEqual(book.iloc[1], -2 * cfg.cost_one_way)
        self.assertAlmostEqual(book.iloc[2], 0.0)


class Target(unittest.TestCase):
    def test_snapshot_has_weights_and_no_performance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_universe(root / "universe.csv")
            panel = root / "panel.sqlite"
            _write_panel(panel, _crash_rows())
            cfg = _one_name_config(tmp)
            shot = target_snapshot(panel, "2024-03-31", cfg)
            self.assertEqual(shot["valve"], "出场")
            self.assertEqual(shot["qdii_premium"], "未接入")
            self.assertAlmostEqual(shot["a_share_drawdown_from_high"], -0.30)
            self.assertNotIn("cagr", shot)
            self.assertNotIn("max_drawdown", shot)
            weights = {row["execution_code"]: row["weight"] for row in shot["weights"]}
            self.assertAlmostEqual(weights["511880"], 0.70)
            self.assertAlmostEqual(weights["513100"], 0.30)
            self.assertTrue(all(row["qdii_premium"] == "未接入" for row in shot["weights"]))
            self.assertNotIn("510300", weights)


def _one_name_config(tmp: str):
    cfg = _cfg()
    return cfg.__class__(
        design_end=cfg.design_end,
        a_share=("甲",), a_weight=0.70, overseas=("乙",), o_weight=0.30,
        out=cfg.out, back=cfg.back, judge=cfg.judge, haven_code="511880",
        cash_annual=cfg.cash_annual, rebalance=cfg.rebalance, cost_one_way=cfg.cost_one_way,
        universe=Path(tmp) / "universe.csv", path=cfg.path)


def _one_name_config_inline():
    cfg = _cfg()
    return cfg.__class__(
        design_end=pd.Timestamp("2015-12-31"),
        a_share=("甲",), a_weight=1.0, overseas=(), o_weight=0.0,
        out=0.25, back=0.10, judge="month_end", haven_code="511880",
        cash_annual=0.02, rebalance="monthly", cost_one_way=0.0005,
        universe=Path("/tmp/unused-universe.csv"), path=cfg.path)


def _write_universe(path: Path):
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["theme", "execution_fund_code"])
        writer.writeheader()
        writer.writerows([
            {"theme": "甲", "execution_fund_code": "510300"},
            {"theme": "乙", "execution_fund_code": "513100"},
            {"theme": "现金", "execution_fund_code": "511880"},
        ])


def _write_panel(path: Path, rows: list[tuple]):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE panel (date TEXT, container TEXT, close REAL, data_hole INTEGER)")
    con.executemany("INSERT INTO panel VALUES (?, ?, ?, ?)", rows)
    con.commit()
    con.close()


def _flat_rows():
    rows = []
    for day, price in (("2015-01-30", 100.0), ("2015-02-27", 101.0), ("2015-03-31", 102.0)):
        rows.append((day, "甲", price, 0))
        rows.append((day, "乙", price, 0))
    return rows


def _crash_rows():
    rows = []
    for day, price in (("2024-01-31", 100.0), ("2024-02-28", 100.0), ("2024-03-29", 70.0)):
        rows.append((day, "甲", price, 0))
        rows.append((day, "乙", 100.0, 0))
    return rows


if __name__ == "__main__":
    unittest.main()
