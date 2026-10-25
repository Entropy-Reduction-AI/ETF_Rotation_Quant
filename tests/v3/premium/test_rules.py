"""§5.1–§5.4：状态、乘子、风险预算、同指数选代码。用手数，不读行情库。"""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.v3.engine.spec import load_spec
from src.v3.premium.apply import adjust_weights, allocate_container, representative_code
from src.v3.premium.rules import (
    BASELINE_CUT,
    HELD_EPS,
    NAV_LAG,
    NORMAL,
    PULSE,
    STRUCTURAL_DISCOUNT,
    STRUCTURAL_HIGH,
    PremiumError,
    PremiumSpec,
    classify_state,
    subject_to_premium,
)
from src.v3.premium.series import premium_frame, trailing_median
from src.v3.data.universe import containers


def _cash_book(**weights: float) -> dict[str, float]:
    weights.setdefault("cash", 0.0)
    weights["cash"] = 1.0 - sum(value for name, value in weights.items() if name != "cash")
    return weights


class Boundaries(unittest.TestCase):
    def test_only_the_preregistered_candidates(self):
        PremiumSpec(120, 0.10)
        PremiumSpec(250, 0.15)
        with self.assertRaises(PremiumError):
            PremiumSpec(window=60)
        with self.assertRaises(PremiumError):
            PremiumSpec(theta=0.08)

    def test_constants_match_the_frozen_arm_file(self):
        spec = load_spec()
        self.assertEqual(spec.nav_lag, NAV_LAG)
        self.assertEqual(spec.weight_eps, HELD_EPS)

    def test_priority_and_fixed_cuts(self):
        spec = PremiumSpec(window=250, theta=0.10)
        self.assertEqual(classify_state(0.20, 0.05, 0.15, 0.01, spec), PULSE)
        self.assertEqual(classify_state(0.20, 0.05 + 1e-4, 0.10, 0.01, spec), STRUCTURAL_HIGH)
        self.assertEqual(classify_state(0.0, 0.08, -0.05, -0.01, spec), STRUCTURAL_DISCOUNT)
        self.assertEqual(classify_state(0.0, 0.08, -0.05, 0.0, spec), NORMAL)
        self.assertEqual(classify_state(0.0, 0.08, -0.049, -0.01, spec), NORMAL)
        self.assertEqual(classify_state(0.02, 0.04, -0.02, -0.10, spec), NORMAL)
        self.assertIsNone(classify_state(float("nan"), 0.01, 0.0, 0.0, spec))
        self.assertEqual(classify_state(0.02, float("nan"), float("nan"), 0.0, spec), NORMAL)
        wide = PremiumSpec(window=120, theta=0.15)
        self.assertEqual(classify_state(0.16, 0.04, 0.12, 0.0, wide), NORMAL)
        self.assertEqual(classify_state(0.20, 0.04, 0.16, 0.0, wide), PULSE)
        self.assertEqual(BASELINE_CUT, 0.05)

    def test_which_containers_have_a_premium(self):
        by_id = {row["id"]: row for row in containers()}
        theme = next(
            row["id"] for row in containers()
            if any(ex.get("code") == "159509" for ex in row.get("execution") or [])
        )
        self.assertEqual(theme, "theme-纳斯达克科技市值加权指数")
        for name in ("ndx100", "spx", "hsi", "hstech", "crude-oil", theme):
            self.assertTrue(subject_to_premium(by_id[name]), name)
        for name in ("csi300", "gold", "soymeal", "cash"):
            self.assertFalse(subject_to_premium(by_id[name]), name)


class SeriesMath(unittest.TestCase):
    def test_median_uses_the_last_window_including_today(self):
        index = pd.bdate_range("2024-01-02", periods=6)
        premium = pd.Series([0.01, np.nan, 0.03, 0.02, 0.04, 0.05], index=index)
        median = trailing_median(premium, 4)
        self.assertTrue(np.isnan(median.iloc[3]))
        self.assertAlmostEqual(float(median.iloc[4]), 0.025, places=12)
        self.assertAlmostEqual(float(median.iloc[5]), 0.035, places=12)
        self.assertTrue(np.isnan(median.iloc[1]))

    def test_nav_published_after_t_minus_2_is_ignored(self):
        days = pd.bdate_range("2024-01-02", periods=8)
        close = pd.Series(1.10, index=days)
        nav = pd.Series(1.0, index=days)
        nav.iloc[-1] = 5.0
        nav.iloc[-2] = 4.0
        nav.iloc[-3] = 2.0
        frame = premium_frame(close, nav, days, PremiumSpec())
        day = days[-1]
        self.assertAlmostEqual(float(frame.loc[day, "nav"]), 2.0, places=12)
        self.assertAlmostEqual(float(frame.loc[day, "premium"]), 1.10 / 2.0 - 1.0, places=12)
        self.assertEqual(frame.loc[day, "state"], NORMAL)

    def test_later_prices_do_not_change_an_earlier_premium(self):
        days = pd.bdate_range("2024-01-02", periods=30)
        close = pd.Series(1.0, index=days)
        nav = pd.Series(1.0, index=days)
        before = premium_frame(close, nav, days, PremiumSpec())
        close.iloc[-1] = 9.0
        nav.iloc[-1] = 9.0
        after = premium_frame(close, nav, days, PremiumSpec())
        earlier = days[-4]
        self.assertAlmostEqual(float(before.loc[earlier, "premium"]), float(after.loc[earlier, "premium"]), places=12)


class Weights(unittest.TestCase):
    def test_pulse_blocks_a_new_buy_and_halves_an_existing_one(self):
        targets = _cash_book(qdii=0.20, equity=0.50)
        blocked = adjust_weights(
            targets, states={"qdii": PULSE}, held={"qdii": 0.0}, premiums={"qdii": 0.12},
            premium_ids={"qdii"}, eligible={"equity"})
        self.assertEqual(blocked["qdii"], 0.0)
        self.assertAlmostEqual(blocked["equity"], 0.50, places=12)
        self.assertAlmostEqual(blocked["cash"], 0.50, places=12)
        held = adjust_weights(
            targets, states={"qdii": PULSE}, held={"qdii": 0.05}, premiums={"qdii": 0.12},
            premium_ids={"qdii"}, eligible={"equity"})
        self.assertAlmostEqual(held["qdii"], 0.10, places=12)
        self.assertAlmostEqual(held["cash"], 0.40, places=12)
        self.assertAlmostEqual(held["equity"], 0.50, places=12)

    def test_structural_high_halves_even_when_not_held(self):
        targets = _cash_book(qdii=0.20, equity=0.40)
        out = adjust_weights(
            targets, states={"qdii": STRUCTURAL_HIGH}, held={}, premiums={"qdii": 0.08},
            premium_ids={"qdii"}, eligible={"equity"})
        self.assertAlmostEqual(out["qdii"], 0.10, places=12)
        self.assertAlmostEqual(out["equity"], 0.40, places=12)
        self.assertAlmostEqual(out["cash"], 0.50, places=12)

    def test_discount_is_funded_only_by_cash_including_same_day_cuts(self):
        targets = _cash_book(hot=0.20, cheap=0.10, equity=0.40)
        out = adjust_weights(
            targets,
            states={"hot": STRUCTURAL_HIGH, "cheap": STRUCTURAL_DISCOUNT},
            held={"hot": 0.20, "cheap": 0.10},
            premiums={"hot": 0.08, "cheap": -0.06},
            premium_ids={"hot", "cheap"},
            eligible={"equity"},
        )
        self.assertAlmostEqual(out["hot"], 0.10, places=12)
        self.assertAlmostEqual(out["cheap"], 0.15, places=12)
        self.assertAlmostEqual(out["equity"], 0.40, places=12)
        self.assertAlmostEqual(out["cash"], 0.35, places=12)
        tight = _cash_book(cheap=0.20, equity=0.78)
        capped = adjust_weights(
            tight, states={"cheap": STRUCTURAL_DISCOUNT}, held={}, premiums={"cheap": -0.08},
            premium_ids={"cheap"}, eligible={"equity"})
        self.assertAlmostEqual(capped["cheap"], 0.22, places=12)
        self.assertAlmostEqual(capped["equity"], 0.78, places=12)
        self.assertAlmostEqual(capped["cash"], 0.0, places=12)

    def test_two_discounts_take_cash_in_section4_order(self):
        targets = _cash_book(**{"b": 0.20, "a": 0.20, "equity": 0.50})
        # 现金只有 0.10。两边都想加 0.10。§4 权重相同，id 较小的 a 先拿。
        out = adjust_weights(
            targets, states={"a": STRUCTURAL_DISCOUNT, "b": STRUCTURAL_DISCOUNT}, held={},
            premiums={"a": -0.08, "b": -0.08}, premium_ids={"a", "b"}, eligible={"equity"})
        self.assertAlmostEqual(out["a"], 0.30, places=12)
        self.assertAlmostEqual(out["b"], 0.20, places=12)
        self.assertAlmostEqual(out["cash"], 0.0, places=12)
        self.assertAlmostEqual(sum(out.values()), 1.0, places=12)

    def test_single_and_total_premium_budget(self):
        targets = _cash_book(qdii=0.40, equity=0.40, bond=0.10)
        out = adjust_weights(
            targets, states={"qdii": NORMAL}, held={"qdii": 0.40}, premiums={"qdii": 0.20},
            premium_ids={"qdii"}, eligible={"equity", "bond"})
        self.assertAlmostEqual(out["qdii"], 0.10, places=12)
        self.assertAlmostEqual(out["qdii"] * 0.20, 0.02, places=12)
        self.assertAlmostEqual(out["equity"], 0.70, places=12)
        self.assertAlmostEqual(out["bond"], 0.10, places=12)
        three = _cash_book(a=0.20, b=0.20, c=0.20, equity=0.20)
        scaled = adjust_weights(
            three, states={}, held={}, premiums={"a": 0.10, "b": 0.10, "c": 0.10},
            premium_ids={"a", "b", "c"}, eligible={"equity"})
        for name in ("a", "b", "c"):
            self.assertAlmostEqual(scaled[name], 0.20 * 5.0 / 6.0, places=10)
        exposure = sum(scaled[name] * 0.10 for name in ("a", "b", "c"))
        self.assertAlmostEqual(exposure, 0.05, places=10)
        self.assertAlmostEqual(scaled["equity"], 0.30, places=10)
        self.assertAlmostEqual(sum(scaled.values()), 1.0, places=10)

    def test_spill_skips_ineligible_and_premium_names(self):
        targets = _cash_book(qdii=0.40, equity=0.30, bond=0.10)
        out = adjust_weights(
            targets, states={"qdii": NORMAL}, held={}, premiums={"qdii": 0.20},
            premium_ids={"qdii"}, eligible={"bond", "qdii"})
        self.assertAlmostEqual(out["qdii"], 0.10, places=12)
        self.assertAlmostEqual(out["equity"], 0.30, places=12)
        self.assertAlmostEqual(out["bond"], 0.40, places=12)
        parked = adjust_weights(
            targets, states={"qdii": NORMAL}, held={}, premiums={"qdii": 0.20},
            premium_ids={"qdii"}, eligible=set())
        self.assertAlmostEqual(parked["cash"], 0.50, places=12)
        self.assertAlmostEqual(parked["equity"], 0.30, places=12)

    def test_bad_weights_and_states_are_rejected(self):
        with self.assertRaises(PremiumError):
            adjust_weights({"qdii": 0.2, "cash": 0.2}, states={}, held={}, premiums={},
                           premium_ids=set(), eligible=set())
        with self.assertRaises(PremiumError):
            adjust_weights(_cash_book(qdii=0.2), states={"qdii": "超买"}, held={}, premiums={},
                           premium_ids={"qdii"}, eligible=set())


class SameIndex(unittest.TestCase):
    def test_buy_the_cheapest_and_sell_the_richest(self):
        bought, left = allocate_container(0.25, {"513100": 0.10, "159941": 0.10},
                                          {"513100": 0.05, "159941": 0.02, "513300": 0.01})
        self.assertEqual(left, 0.0)
        self.assertAlmostEqual(bought["513100"], 0.10, places=12)
        self.assertAlmostEqual(bought["159941"], 0.10, places=12)
        self.assertAlmostEqual(bought["513300"], 0.05, places=12)
        sold, left = allocate_container(0.05, {"513100": 0.10, "159941": 0.10},
                                        {"513100": 0.05, "159941": 0.02})
        self.assertEqual(left, 0.0)
        self.assertNotIn("513100", sold)
        self.assertAlmostEqual(sold["159941"], 0.05, places=12)

    def test_ties_break_toward_the_smaller_code(self):
        bought, _ = allocate_container(0.10, {}, {"159941": 0.03, "513100": 0.03})
        self.assertEqual(list(bought), ["159941"])
        sold, _ = allocate_container(0.05, {"159941": 0.05, "513100": 0.05},
                                     {"159941": 0.03, "513100": 0.03})
        self.assertNotIn("159941", sold)
        self.assertAlmostEqual(sold["513100"], 0.05, places=12)

    def test_a_buy_with_no_premium_stays_in_cash(self):
        book, left = allocate_container(0.10, {}, {"513100": float("nan")})
        self.assertEqual(book, {})
        self.assertAlmostEqual(left, 0.10, places=12)

    def test_representative_code_follows_the_trade(self):
        premiums = {"513100": 0.06, "159941": 0.02}
        self.assertEqual(representative_code(premiums, {}), "159941")
        self.assertEqual(representative_code(premiums, {"513100": 0.10}), "513100")
        self.assertEqual(representative_code(premiums, {"513100": 0.04, "159941": 0.08}), "513100")
        self.assertIsNone(representative_code({"513100": float("nan")}, {}))


if __name__ == "__main__":
    unittest.main()
