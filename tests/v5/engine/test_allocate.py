"""§4.2、§4.3、§7.1。手造权重，不读行情库，不算组合收益。"""
from __future__ import annotations

import math
import unittest

import numpy as np
import pandas as pd

from src.v3.engine.score import Lookback
from src.v5.engine.allocate import (
    BLEND_COUNT,
    VOL_DDOF,
    EngineError,
    Sleeve,
    apply_c1,
    average_lookbacks,
    group_weights,
    path_decisions,
    vol_multiplier,
)
from src.v5.engine.classes import DEFENSIVE_CLASSES, RISK_CLASSES


def sleeve(name, kind, score, *, participates=True, beats=True, total=0.0):
    return Sleeve(name, kind, score, total, participates, beats)


class GroupWeights(unittest.TestCase):
    def test_defensive_classes_are_judged_separately_then_split(self):
        rows = [
            sleeve("cgb-10y", "国债", 1.0),
            sleeve("cgb-5y", "国债", 0.4),
            sleeve("gold", "黄金", 3.0),
            sleeve("csi300", "A股", 9.0, beats=False),
        ]
        weights = group_weights(rows)
        self.assertAlmostEqual(weights["cgb-10y"], 0.5)
        self.assertAlmostEqual(weights["gold"], 0.5)
        self.assertNotIn("cgb-5y", weights)
        self.assertNotIn("csi300", weights)
        self.assertAlmostEqual(weights["cash"], 0.0)
        self.assertEqual(DEFENSIVE_CLASSES, ("国债", "黄金"))

        bond_only = group_weights([
            sleeve("cgb-10y", "国债", 1.0),
            sleeve("cgb-5y", "国债", 2.0, beats=False),
            sleeve("gold", "黄金", 5.0, beats=False),
        ])
        self.assertAlmostEqual(bond_only["cgb-10y"], 1.0)
        self.assertAlmostEqual(bond_only["cash"], 0.0)
        self.assertNotIn("gold", bond_only)

        cash = group_weights([
            sleeve("cgb-10y", "国债", 1.0, beats=False),
            sleeve("gold", "黄金", 1.0, participates=False),
        ])
        self.assertEqual(cash, {"cash": 1.0})

    def test_single_open_risk_class_takes_the_whole_group(self):
        rows = [
            sleeve("csi300", "A股", 1.0),
            sleeve("csi500", "A股", 0.2),
            sleeve("hsi", "港股", 4.0, beats=False),
            sleeve("ndx100", "美股", 8.0, participates=False),
            sleeve("gold", "黄金", 9.0),
            sleeve("cgb-10y", "国债", 9.0),
        ]
        weights = group_weights(rows)
        self.assertAlmostEqual(weights["csi300"], 1.0)
        self.assertAlmostEqual(weights["cash"], 0.0)
        self.assertNotIn("csi500", weights)
        self.assertNotIn("gold", weights)
        self.assertNotIn("hsi", weights)

    def test_several_open_risk_classes_split_equally(self):
        weights = group_weights([
            sleeve("csi300", "A股", 1.0),
            sleeve("hsi", "港股", 5.0),
            sleeve("ndx100", "美股", 0.1),
            sleeve("oil", "商品", 3.0, beats=False),
        ])
        self.assertAlmostEqual(weights["csi300"], 1.0 / 3.0)
        self.assertAlmostEqual(weights["hsi"], 1.0 / 3.0)
        self.assertAlmostEqual(weights["ndx100"], 1.0 / 3.0)
        self.assertAlmostEqual(weights["cash"], 0.0)

    def test_tie_breaks_on_container_id_not_on_total_return(self):
        # v3 会让 R 更高的 b 胜出。v5 §4.2 只写了容器 id。
        weights = group_weights([
            sleeve("b", "A股", 1.0, total=0.9),
            sleeve("a", "A股", 1.0, total=0.1),
        ])
        self.assertAlmostEqual(weights["a"], 1.0)
        self.assertNotIn("b", weights)

    def test_strongest_class_keeps_one_and_falls_back_when_none_open(self):
        rows = [
            sleeve("csi300", "A股", 1.0),
            sleeve("hsi", "港股", 2.0),
            sleeve("ndx", "美股", 2.0),
        ]
        held = group_weights(rows, structure="strongest_class")
        self.assertEqual(held, {"hsi": 1.0, "cash": 0.0})
        tied = group_weights([
            sleeve("hsi", "港股", 2.0),
            sleeve("ndx", "美股", 2.0),
        ], structure="strongest_class")
        self.assertAlmostEqual(tied["hsi"], 1.0)
        idle = [
            sleeve("csi300", "A股", 1.0, beats=False),
            sleeve("cgb-10y", "国债", 1.0),
            sleeve("gold", "黄金", 4.0),
        ]
        parked = group_weights(idle, structure="strongest_class")
        self.assertAlmostEqual(parked["cgb-10y"], 0.5)
        self.assertAlmostEqual(parked["gold"], 0.5)

    def test_fixed_budget_parks_closed_classes_in_defense(self):
        rows = [
            sleeve("csi300", "A股", 2.0),
            sleeve("hsi", "港股", 0.1, beats=False),
            sleeve("ndx", "美股", 1.0, participates=False),
            sleeve("cgb-10y", "国债", 1.0),
            sleeve("gold", "黄金", 1.0),
        ]
        weights = group_weights(rows, structure="fixed_budget")
        self.assertAlmostEqual(weights["csi300"], 0.5)
        self.assertAlmostEqual(weights["cgb-10y"], 0.25)
        self.assertAlmostEqual(weights["gold"], 0.25)
        self.assertAlmostEqual(sum(weights.values()), 1.0)
        idle = [
            sleeve("csi300", "A股", 1.0, participates=False),
            sleeve("cgb-10y", "国债", 2.0),
            sleeve("gold", "黄金", 1.0),
        ]
        parked = group_weights(idle, structure="fixed_budget")
        self.assertEqual(parked, group_weights(idle))
        self.assertAlmostEqual(parked["cgb-10y"], 0.5)
        self.assertAlmostEqual(parked["gold"], 0.5)
        self.assertAlmostEqual(parked["cash"], 0.0)
        cash = group_weights([
            sleeve("csi300", "A股", 1.0, participates=False),
            sleeve("gold", "黄金", 1.0, beats=False),
            sleeve("cgb-10y", "国债", 1.0, participates=False),
        ], structure="fixed_budget")
        self.assertEqual(cash, {"cash": 1.0})

    def test_no_defense_is_cash_when_no_risk_class_is_open(self):
        rows = [
            sleeve("csi300", "A股", 1.0, beats=False),
            sleeve("gold", "黄金", 3.0),
            sleeve("cgb-10y", "国债", 3.0),
        ]
        weights = group_weights(rows, structure="no_defense")
        self.assertEqual(weights, {"cash": 1.0})
        opened = group_weights([sleeve("csi300", "A股", 1.0), sleeve("gold", "黄金", 9.0)],
                               structure="no_defense")
        self.assertAlmostEqual(opened["csi300"], 1.0)


class LookbackAverage(unittest.TestCase):
    def test_lookback_average_divides_by_four_even_when_one_group_is_cash(self):
        names = ["csi300", "hsi"]
        groups = [
            {"csi300": 1.0, "cash": 0.0},
            {"csi300": 1.0, "cash": 0.0},
            {"csi300": 1.0, "cash": 0.0},
            {"csi300": 0.0, "cash": 1.0},
        ]
        averaged = average_lookbacks(groups, names, "cash")
        self.assertEqual(BLEND_COUNT, 4)
        self.assertAlmostEqual(averaged["csi300"], 0.75)
        self.assertAlmostEqual(averaged["hsi"], 0.0)
        self.assertAlmostEqual(averaged["cash"], 0.25)
        three = average_lookbacks(groups[:3], names, "cash")
        self.assertAlmostEqual(three["csi300"], 0.75)
        self.assertAlmostEqual(three["cash"], 0.25)

    def test_missing_lookback_in_the_path_still_counts_as_cash(self):
        day = pd.Timestamp("2006-06-30")
        panel = _panel(day, {"csi300": (0.2, 1.0, True), "cash": (0.0, 0.0, False)})
        frame = path_decisions(
            {20: panel, 60: panel, 120: panel},
            [day], "month", ["csi300", "cash"],
            {"csi300": "A股", "cash": "现金"}, "cash",
        )
        self.assertAlmostEqual(float(frame.loc[day, "csi300"]), 0.75)
        self.assertAlmostEqual(float(frame.loc[day, "cash"]), 0.25)


class VolatilityScale(unittest.TestCase):
    def test_c1_scales_risk_weights_and_leaves_defense_alone(self):
        class_of = {"csi300": "A股", "gold": "黄金"}
        scaled = apply_c1(
            {"csi300": 0.5, "gold": 0.5, "cash": 0.0},
            {"csi300": 0.5, "gold": 0.25},
            class_of, "cash",
        )
        self.assertAlmostEqual(scaled["csi300"], 0.25)
        self.assertAlmostEqual(scaled["gold"], 0.5)
        self.assertAlmostEqual(scaled["cash"], 0.25)

    def test_multiplier_uses_last_valid_returns_and_sample_std(self):
        calm = np.zeros(230)
        wild = np.resize(np.array([0.1, -0.1]), 20)
        values = np.concatenate([calm, wild])
        # 中间塞一个无效点，不应占掉有效个数。
        values = np.insert(values, 10, np.nan)
        day = pd.Timestamp("2006-01-03") + pd.offsets.BDay(len(values) - 1)
        index = pd.bdate_range(end=day, periods=len(values))
        series = pd.Series(values, index=index)
        self.assertLess(day, pd.Timestamp("2015-12-31"))
        found = vol_multiplier(series, day)
        self.assertAlmostEqual(found, math.sqrt(19 / 249))
        self.assertEqual(VOL_DDOF, 1)
        short = series.iloc[:-1]
        self.assertEqual(vol_multiplier(short, short.index[-1]), 1.0)
        later = day + pd.offsets.BDay(5)
        spiked = pd.concat([series, pd.Series([0.5, -0.5, 0.5, -0.5], index=pd.bdate_range(day, periods=5)[1:])])
        self.assertAlmostEqual(vol_multiplier(spiked, day), found)
        self.assertNotAlmostEqual(vol_multiplier(spiked, spiked.index[-1]), found)

    def test_zero_short_vol_does_not_cut(self):
        day = pd.Timestamp("2006-12-29")
        series = pd.Series(0.0, index=pd.bdate_range(end=day, periods=250))
        self.assertEqual(vol_multiplier(series, day), 1.0)
        with self.assertRaises(EngineError):
            vol_multiplier(series, pd.Timestamp("2016-01-04"))


class PathAssembly(unittest.TestCase):
    def test_missing_carrier_keeps_the_class_closed(self):
        day = pd.Timestamp("2006-06-30")
        names = {"csi300": (0.1, 1.0, True), "hsi": (0.2, 3.0, True), "cash": (0.0, 0.0, False)}
        panel = _panel(day, names)
        panels = {length: panel for length in (20, 60, 120, 250)}
        class_of = {"csi300": "A股", "hsi": "港股", "cash": "现金"}
        liquidity = pd.DataFrame({"csi300": [True], "hsi": [False]}, index=[day])
        frame = path_decisions(
            panels, [day], "week", ["csi300", "hsi", "cash"], class_of, "cash", liquidity=liquidity)
        self.assertAlmostEqual(float(frame.loc[day, "csi300"]), 1.0)
        self.assertAlmostEqual(float(frame.loc[day, "hsi"]), 0.0)
        self.assertEqual(RISK_CLASSES[0], "A股")


def _panel(day, columns):
    index = pd.DatetimeIndex([day])
    total = pd.DataFrame([{name: values[0] for name, values in columns.items()}], index=index)
    score = pd.DataFrame([{name: values[1] for name, values in columns.items()}], index=index)
    rankable = pd.DataFrame([{name: values[2] for name, values in columns.items()}], index=index)
    return Lookback(total=total, score=score, ok=rankable.copy(), rankable=rankable)


if __name__ == "__main__":
    unittest.main()
