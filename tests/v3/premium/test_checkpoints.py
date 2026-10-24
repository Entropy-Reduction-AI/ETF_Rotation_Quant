"""2025-04 和 2026-03 两个时点的状态。数字来自行情库，判定按 §5.2。

不把这些权重乘成 2016 年之后的组合收益。
"""
from __future__ import annotations

import statistics
import unittest
from pathlib import Path

import pandas as pd

from src.v3.engine.prices import lag_asof
from src.v3.premium.load import connect_readonly, load_calendar, load_close, load_nav
from src.v3.premium.rules import NAV_LAG, NORMAL, PULSE, STRUCTURAL_DISCOUNT, PremiumSpec
from src.v3.premium.series import premium_frame

ROOT = Path(__file__).resolve().parents[3]
DB = ROOT / "data" / "market.sqlite"
CODES = ("513100", "159941", "159509", "161129", "160723", "501018", "159529")


class Checkpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DB.exists() or DB.stat().st_size < 1000:
            raise unittest.SkipTest("market.sqlite 不在这台机器上")
        cls.con = connect_readonly(DB)
        cls.calendar = load_calendar(cls.con)
        cls.prices = {code: load_close(cls.con, code) for code in CODES}
        cls.navs = {code: load_nav(cls.con, code) for code in CODES}
        cls.frames = {}
        for window in (120, 250):
            for theta in (0.10, 0.15):
                spec = PremiumSpec(window, theta)
                cls.frames[(window, theta)] = {
                    code: premium_frame(cls.prices[code], cls.navs[code], cls.calendar, spec)
                    for code in CODES
                }

    @classmethod
    def tearDownClass(cls):
        con = getattr(cls, "con", None)
        if con is not None:
            con.close()

    def _row(self, code: str, day: str, window: int = 250, theta: float = 0.10) -> pd.Series:
        return self.frames[(window, theta)][code].loc[pd.Timestamp(day)]

    def _assert_formula(self, code: str, day: str, window: int) -> None:
        row = self._row(code, day, window)
        level = lag_asof(self.navs[code], self.calendar, NAV_LAG)
        stamp = pd.Timestamp(day)
        self.assertAlmostEqual(float(row["nav"]), float(level.loc[stamp]), places=12)
        self.assertAlmostEqual(float(row["premium"]), float(row["close"]) / float(row["nav"]) - 1.0, places=12)
        history = self.frames[(window, 0.10)][code].loc[:stamp, "premium"].dropna()
        window_values = [float(value) for value in history.iloc[-window:]]
        self.assertEqual(len(window_values), window)
        self.assertAlmostEqual(float(row["baseline"]), statistics.median(window_values), places=10)
        position = self.frames[(window, 0.10)][code].index.get_loc(stamp)
        nav = self.frames[(window, 0.10)][code]["nav"]
        manual = float(nav.iloc[position]) / float(nav.iloc[position - 20]) - 1.0
        self.assertAlmostEqual(float(row["nav_return"]), manual, places=12)

    def test_april_2025_crash_day(self):
        """2025-04-07：纳指折价。常态线不超过 5% 的仍是常态；159509 常态线已高于 5%，判结构型折价。"""
        day = "2025-04-07"
        for window in (120, 250):
            for theta in (0.10, 0.15):
                broad = self._row("513100", day, window, theta)
                self.assertLess(float(broad["premium"]), -0.09)
                self.assertGreater(float(broad["premium"]), -0.11)
                self.assertLessEqual(float(broad["baseline"]), 0.05)
                self.assertEqual(broad["state"], NORMAL)
                peer = self._row("159941", day, window, theta)
                self.assertLess(float(peer["premium"]), -0.05)
                self.assertEqual(peer["state"], NORMAL)
                theme = self._row("159509", day, window, theta)
                self.assertLess(float(theme["premium"]), -0.05)
                self.assertGreater(float(theme["premium"]), -0.08)
                self.assertGreater(float(theme["baseline"]), 0.05)
                self.assertLessEqual(float(theme["deviation"]), -0.05)
                self.assertLess(float(theme["nav_return"]), 0.0)
                self.assertEqual(theme["state"], STRUCTURAL_DISCOUNT)
        self._assert_formula("513100", day, 250)
        self._assert_formula("159509", day, 120)

    def test_april_2025_month_end_is_back_to_normal(self):
        day = "2025-04-30"
        for code in ("513100", "159941", "159509"):
            row = self._row(code, day, 250, 0.10)
            self.assertEqual(row["state"], NORMAL, code)

    def test_march_2026_crude_pulse_and_nasdaq_normal(self):
        """2026-03-31：原油三只 LOF 是脉冲。纳指宽基仍是常态。月初原油还没脉冲。"""
        day = "2026-03-31"
        for code in ("161129", "160723", "501018"):
            for window in (120, 250):
                for theta in (0.10, 0.15):
                    row = self._row(code, day, window, theta)
                    self.assertLessEqual(float(row["baseline"]), 0.05, code)
                    self.assertGreaterEqual(float(row["deviation"]), 0.15, code)
                    self.assertEqual(row["state"], PULSE, (code, window, theta))
            early = self._row(code, "2026-03-11", 250, 0.10)
            self.assertEqual(early["state"], NORMAL, code)
        nasdaq = self._row("513100", day, 250, 0.10)
        self.assertGreater(float(nasdaq["premium"]), 0.0)
        self.assertEqual(nasdaq["state"], NORMAL)
        narrow = self._row("159529", day, 120, 0.10)
        wide = self._row("159529", day, 250, 0.15)
        self.assertEqual(narrow["state"], NORMAL)
        self.assertGreater(float(wide["baseline"]), 0.05)
        self.assertLessEqual(float(wide["deviation"]), -0.05)
        self.assertLess(float(wide["nav_return"]), 0.0)
        self.assertEqual(wide["state"], STRUCTURAL_DISCOUNT)
        self._assert_formula("161129", day, 250)
        self._assert_formula("159529", day, 250)


if __name__ == "__main__":
    unittest.main()
