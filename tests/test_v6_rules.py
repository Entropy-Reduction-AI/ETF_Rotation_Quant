"""v6 规则与隔离。不读 2016 年以后的行情。"""

from __future__ import annotations

import unittest

import pandas as pd

from src.v6.engine import _pick, confidence
from src.v6.execute import choose_listing
from src.v6.guard import IsolationError, assert_not_after, sql_is_capped
from src.v6.load import CUTOFF, freeze_loader_text, momentum
from src.v6.trin import clip_expanding, clip_full_sample


class GuardTests(unittest.TestCase):
    def test_rejects_2016(self):
        index = pd.to_datetime(["2015-12-31", "2016-01-04"])
        with self.assertRaises(IsolationError):
            assert_not_after(index, "probe")

    def test_accepts_design_end(self):
        assert_not_after(pd.to_datetime(["2015-12-30", "2015-12-31"]), "probe")

    def test_sql_must_be_capped(self):
        self.assertFalse(sql_is_capped("select close from bars where code=?"))
        self.assertTrue(sql_is_capped("select close from bars where date<=?"))
        self.assertTrue(sql_is_capped("select 1"))


class MomentumTests(unittest.TestCase):
    def test_anchor_is_t_minus_1_over_t_minus_12(self):
        # 13 个连续月末。信号月 T 用 T−1 / T−12 − 1。
        days = pd.bdate_range("2014-01-31", periods=13, freq="BME")
        level = pd.Series(range(100, 113), index=days, dtype=float).to_frame("x")
        score = momentum(level)
        # T = 最后一个月末，T−1 的点位是 111，T−12 的点位是 100。
        self.assertAlmostEqual(float(score.iloc[-1, 0]), 111 / 100 - 1)

    def test_loader_stops_before_french(self):
        head, _digest = freeze_loader_text()
        self.assertIn(CUTOFF[:12], open("scripts/preflight/a_official.py", encoding="utf-8").read())
        self.assertNotIn("topn_longhist.py", head)
        self.assertNotIn("2016", head)


class TrinTests(unittest.TestCase):
    def test_expanding_quantile_ignores_the_future(self):
        values = list(range(1, 21)) + [1000]
        daily = pd.Series(values, index=pd.bdate_range("2015-01-01", periods=len(values)))
        clipped = clip_expanding(daily)
        for i in range(len(daily)):
            past = daily.iloc[: i + 1]
            self.assertAlmostEqual(
                float(clipped.iloc[i]),
                float(past.clip(upper=past.quantile(0.99)).iloc[-1]),
            )
        full = clip_full_sample(daily)
        # 末尾的 1000 把全样本上限抬高，第 20 天不会被裁；扩展分位只用到当天，会裁。
        self.assertEqual(float(full.iloc[19]), 20.0)
        self.assertLess(float(clipped.iloc[19]), 20.0)


class RuleTests(unittest.TestCase):
    def test_dedupe_keeps_one_per_tag_and_skips_blank(self):
        scores = pd.Series([0.3, 0.2, 0.1]).to_numpy()
        ok = pd.Series([True, True, True]).to_numpy()
        tags = pd.Series(["医药", "医药", ""]).to_numpy()
        self.assertEqual(_pick(scores, ok, tags, 3), [0, 2])

    def test_confidence_floor(self):
        self.assertEqual(confidence([0.01] * 11), 0.5)
        self.assertEqual(confidence([0] * 12), 0.5)

    def test_listing_skips_rich_premium_and_keeps_held(self):
        self.assertEqual(choose_listing([
            {"id": "a", "deviation": 7.0, "held": False},
            {"id": "b", "deviation": 1.0, "held": False},
        ]), "b")
        self.assertIsNone(choose_listing([
            {"id": "a", "deviation": 6.0, "held": False},
        ]))
        self.assertEqual(choose_listing([
            {"id": "held", "deviation": 9.0, "held": True},
            {"id": "b", "deviation": 0.0, "held": False},
        ]), "held")


if __name__ == "__main__":
    unittest.main()
