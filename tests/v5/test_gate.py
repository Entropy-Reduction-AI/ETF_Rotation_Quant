"""§6.2。手造日收益，不读候选文件，不写 component-gate.csv。"""
from __future__ import annotations

import unittest

import pandas as pd

from src.v4.scorecard.core import ScorecardError
from src.v5.scorecard.gate import COMPONENT_TARGET, GATE_COLUMNS, ComponentStep, component_gate


def _states():
    return pd.Series(
        ["牛市", "熊市", "回调", "反弹"],
        index=pd.to_datetime(["2006-01-31", "2006-02-28", "2011-01-31", "2011-02-28"]),
    )


def _index():
    return pd.to_datetime([
        "2006-01-04", "2006-01-05", "2006-02-06", "2006-02-07",
        "2011-01-04", "2011-01-05", "2011-02-08", "2011-02-09",
    ])


def _zeros():
    return pd.Series(0.0, index=_index())


def _passing_c1():
    series = _zeros()
    series.loc["2006-01-04"] = 0.02
    series.loc["2006-02-06"] = 0.01
    series.loc["2006-02-07"] = 0.01
    series.loc["2011-01-04"] = 0.02
    return series


class ComponentGate(unittest.TestCase):
    def test_s0_is_reported_and_a_clean_c1_passes(self):
        index = _index()
        benchmark = _zeros()
        s0 = _zeros()
        p1 = _passing_c1()
        index_returns = pd.DataFrame({"S0": s0, "P1": p1}, index=index)
        tradable = pd.DataFrame({"S0": s0, "P1": s0}, index=index)
        step = ComponentStep("P1", "S0", COMPONENT_TARGET["C1"])
        table = component_gate(index_returns, benchmark, _states(), [step], tradable)
        self.assertEqual(list(table.columns), list(GATE_COLUMNS))
        self.assertEqual(table["arm"].tolist(), ["S0", "P1"])
        report = table.set_index("arm").loc["S0"]
        row = table.set_index("arm").loc["P1"]
        self.assertIsNone(report["pass"])
        self.assertIsNone(report["pass_segments"])
        self.assertIsNone(report["pass_guard"])
        self.assertIsNone(report["tradable_d_s1"])
        self.assertEqual(report["base_arm"], "")
        self.assertEqual(report["pool"], "index")
        self.assertAlmostEqual(float(report["ann_excess_s1"]), 0.0)
        self.assertTrue(bool(row["pass_segments"]))
        self.assertTrue(bool(row["pass_target"]))
        self.assertTrue(bool(row["pass_guard"]))
        self.assertAlmostEqual(float(row["tradable_d_s1"]), 0.0)
        self.assertAlmostEqual(float(row["tradable_d_s2"]), 0.0)
        self.assertTrue(bool(row["pass_tradable"]))
        self.assertTrue(bool(row["pass"]))
        self.assertEqual(row["target_state"], "熊市")
        self.assertEqual(row["base_arm"], "S0")
        self.assertGreater(float(row["pp_bear"]), 0.0)

    def test_guard_boundary_is_ten_points_and_depends_on_the_target(self):
        index = _index()
        benchmark = _zeros()
        s0 = _zeros()
        on_the_line = _zeros()
        on_the_line.loc["2006-01-04"] = -0.05
        on_the_line.loc["2006-01-05"] = -0.05
        on_the_line.loc["2006-02-06"] = 0.2
        on_the_line.loc["2006-02-07"] = 0.2
        on_the_line.loc["2011-01-04"] = 0.02
        past_the_line = on_the_line.copy()
        past_the_line.loc["2006-01-05"] = -0.0500001
        index_returns = pd.DataFrame({"S0": s0, "P1": on_the_line, "P1b": past_the_line}, index=index)
        tradable = pd.DataFrame({"S0": s0, "P1": s0, "P1b": s0}, index=index)
        steps = [
            ComponentStep("P1", "S0", "熊市"),
            ComponentStep("P1b", "S0", "熊市"),
        ]
        table = component_gate(index_returns, benchmark, _states(), steps, tradable).set_index("arm")
        self.assertAlmostEqual(float(table.loc["P1", "pp_bull"]), -10.0)
        self.assertTrue(bool(table.loc["P1", "pass_guard"]))
        self.assertTrue(bool(table.loc["P1", "pass"]))
        self.assertFalse(bool(table.loc["P1b", "pass_guard"]))
        self.assertFalse(bool(table.loc["P1b", "pass"]))

        bear_hit = _zeros()
        bear_hit.loc["2006-02-06"] = -0.05
        bear_hit.loc["2006-02-07"] = -0.0500001
        bear_hit.loc["2011-01-04"] = 0.02
        bear_hit.loc["2011-01-05"] = 0.02
        c2_returns = pd.DataFrame({"S0": s0, "P2": bear_hit}, index=index)
        c2_tradable = pd.DataFrame({"S0": s0, "P2": s0}, index=index)
        c2 = component_gate(
            c2_returns, benchmark, _states(),
            [ComponentStep("P2", "S0", COMPONENT_TARGET["C2"])],
            c2_tradable,
        ).set_index("arm").loc["P2"]
        self.assertEqual(c2["target_state"], "回调")
        self.assertTrue(bool(c2["pass_target"]))
        self.assertFalse(bool(c2["pass_guard"]))

    def test_tradable_shortfall_is_in_percentage_points(self):
        index = _index()
        benchmark = _zeros()
        s0 = _zeros()
        p1 = _passing_c1()
        mild = 0.99 ** (1 / 252) - 1
        harsh = -0.01
        tradable = pd.DataFrame({
            "S0": s0,
            "P1": pd.Series(mild, index=index),
            "P1b": pd.Series(harsh, index=index),
        })
        index_returns = pd.DataFrame({"S0": s0, "P1": p1, "P1b": p1}, index=index)
        table = component_gate(
            index_returns, benchmark, _states(),
            [ComponentStep("P1", "S0", "熊市"), ComponentStep("P1b", "S0", "熊市")],
            tradable,
        ).set_index("arm")
        self.assertAlmostEqual(float(table.loc["P1", "tradable_d_s1"]), -1.0, places=6)
        self.assertAlmostEqual(float(table.loc["P1", "tradable_d_s2"]), -1.0, places=6)
        self.assertTrue(bool(table.loc["P1", "pass_tradable"]))
        self.assertTrue(bool(table.loc["P1", "pass"]))
        self.assertLess(float(table.loc["P1b", "tradable_d_s1"]), -2.0)
        self.assertFalse(bool(table.loc["P1b", "pass_tradable"]))
        self.assertFalse(bool(table.loc["P1b", "pass"]))

    def test_equal_segments_do_not_pass_and_later_dates_are_refused(self):
        index = _index()
        flat = _zeros()
        frame = pd.DataFrame({"S0": flat, "P1": flat}, index=index)
        table = component_gate(
            frame, flat, _states(), [ComponentStep("P1", "S0", "熊市")], frame,
        ).set_index("arm")
        self.assertFalse(bool(table.loc["P1", "pass_segments"]))
        self.assertFalse(bool(table.loc["P1", "pass_target"]))
        self.assertFalse(bool(table.loc["P1", "pass"]))
        late = pd.to_datetime(["2016-01-04"])
        late_frame = pd.DataFrame({"S0": [0.0]}, index=late)
        with self.assertRaises(ScorecardError):
            component_gate(late_frame, pd.Series([0.0], index=late), _states())


if __name__ == "__main__":
    unittest.main()
