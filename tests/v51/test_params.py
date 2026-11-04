"""冻结参数、大类表和设计期账本。"""
from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

import numpy as np

from src.v3.engine.book import DESIGN_END
from src.v3.engine.exit import EXIT_DRAWDOWN
from src.v3.engine.ledger import COLUMNS
from src.v5.engine.classes import load_classes
from src.v3.engine.spec import load_spec
from src.v51.controls import _control_params as control_params
from src.v51.design import design_params
from src.v51.gpool import CHINA_IDS, _base_params
from src.v51.hold import N_SIMS, SEED
from src.v51.params import RULERS, load_params, long_rulers
from src.v51.robustness import CASES, _case_params
from src.v51.structure import _control_params as r1_params
from src.v51.universe import universe_from_names


ROOT = Path(__file__).resolve().parents[2]


def _expected_control(pool: str, spec, arm: str) -> dict:
    if arm == "C-等权" and pool in {"index", "tradable"}:
        return control_params(pool, spec, arm, weights="equal")
    if arm == "C-波动比" and pool == "index":
        return control_params(
            pool, spec, arm, layer1_rule="vol-ratio",
            strength="L-day log excess over cash", quantile_short_history=0.5,
        )
    if arm == "R0" and pool in {"index", "tradable"}:
        return control_params(
            pool, spec, arm, n=N_SIMS, seed=SEED, decision="month",
            eligibility="layer1 members with H F E", hold="one full",
        )
    raise AssertionError(f"没有这行对照：{arm} {pool}")


def _expected_other_market() -> list[dict]:
    return [
        _base_params("v5.1"),
        {**_base_params("E2式"), "engine": "v3.1 A", "paths": "3/5/8 × week/month", "exit_drawdown": 0.10},
        {**_base_params("A1"), "rule": "SPY 12m vs cash; else higher of SPY and EFA; else IEF", "lookback_months": 12},
        {**_base_params("R0"), "n": N_SIMS, "seed": SEED, "decision": "month",
         "eligibility": "layer1 members with H F E", "hold": "one full"},
    ]


class Params(unittest.TestCase):
    def test_file_matches_the_frozen_rulers(self):
        loaded = load_params()
        self.assertEqual(loaded.params.rulers, RULERS)
        self.assertEqual(len(RULERS), 28)
        self.assertEqual(len(long_rulers()), 10)
        self.assertEqual(long_rulers()[0], 63)
        self.assertEqual(long_rulers()[-1], 250)
        rounded = tuple(sorted({int(round(float(value))) for value in np.geomspace(3, 250, 30)}))
        self.assertEqual(rounded, RULERS)
        self.assertEqual(loaded.params.frontier, 0.5)
        self.assertEqual(loaded.params.noise_band, 1.0)
        self.assertEqual(loaded.params.breadth_min, 3)
        self.assertEqual(loaded.params.top_n, 3)
        self.assertEqual(loaded.params.hard_stop, EXIT_DRAWDOWN)
        self.assertEqual(loaded.params.quantile_min, 250)
        self.assertEqual(loaded.params.design_end, str(DESIGN_END.date()))
        self.assertEqual(loaded.params.pools, ("index", "tradable"))
        self.assertEqual(loaded.params.classes, "config/v5/classes.csv")
        self.assertTrue(loaded.params.classes_path().is_file())

    def test_layer1_uses_the_v5_class_table(self):
        table = load_classes(load_params().params.classes_path())
        mapping = dict(zip(table["container_id"], table["class"]))
        names = ["csi300", "hsi", "spx", "crude-oil", "cgb-10y", "gold", "cash"]
        universe = universe_from_names(names, mapping)
        self.assertEqual(tuple(market.name for market in universe.markets), ("A股", "港股", "美股"))
        members = {name for market in universe.markets for name in market.members}
        self.assertEqual(members, {"csi300", "hsi", "spx"})
        self.assertEqual(universe.bond, "cgb-10y")

    def test_ledger_matches_registered_segments_and_arms(self):
        """账本盖住 design 与 other-market：v5.1 两池、R0/R1/C、S1–S17。"""
        path = ROOT / "results" / "v5.1" / "trial-ledger.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            self.assertEqual(reader.fieldnames, COLUMNS)
            rows = list(reader)
        spec = load_spec()
        grouped = {"design": [], "other-market": []}
        seen = set()
        for row in rows:
            self.assertEqual(list(row), COLUMNS)
            self.assertEqual(row["runner"], "dev")
            self.assertEqual(len(row["git_sha"]), 40)
            self.assertIn(row["segment"], grouped)
            payload = json.loads(row["params"])
            key = (row["segment"], row["arm"], payload["pool"])
            self.assertNotIn(key, seen)
            seen.add(key)
            grouped[row["segment"]].append((row, payload))

        design_arms = {}
        cases = {case["id"]: case for case in CASES}
        self.assertEqual(set(cases), {f"S{index}" for index in range(1, 18)})
        for row, payload in grouped["design"]:
            self.assertEqual(payload["end"], "2015-12-31")
            design_arms.setdefault(row["arm"], set()).add(payload["pool"])
            if row["arm"] == "v5.1":
                self.assertEqual(payload, design_params(payload["pool"], spec))
            elif row["arm"] == "R1":
                self.assertEqual(payload, r1_params(payload["pool"], spec))
                self.assertEqual(payload["n"], N_SIMS)
                self.assertEqual(payload["seed"], SEED)
            elif row["arm"] in {"R0", "C-等权", "C-波动比"}:
                self.assertEqual(payload, _expected_control(payload["pool"], spec, row["arm"]))
                if row["arm"] == "R0":
                    self.assertEqual(payload["n"], N_SIMS)
                    self.assertEqual(payload["seed"], SEED)
            elif row["arm"] in cases:
                case = cases[row["arm"]]
                dropped = list(payload.get("dropped", []))
                if case.get("drop_best"):
                    self.assertEqual(payload["drop_best"], case["drop_best"])
                    self.assertEqual(len(dropped), case["drop_best"])
                    self.assertEqual(len(set(dropped)), case["drop_best"])
                self.assertEqual(payload, _case_params(case["pool"], spec, case, dropped))
            else:
                self.fail(f"design 段出现未登记的臂 {row['arm']}")
        self.assertEqual(design_arms, {
            "v5.1": {"index", "tradable"},
            "R0": {"index", "tradable"},
            "R1": {"index", "tradable"},
            "C-等权": {"index", "tradable"},
            "C-波动比": {"index"},
            **{case_id: {cases[case_id]["pool"]} for case_id in cases},
        })

        expected_other = {item["case"]: item for item in _expected_other_market()}
        other_arms = {}
        for row, payload in grouped["other-market"]:
            self.assertIn(row["arm"], expected_other)
            self.assertEqual(payload, expected_other[row["arm"]])
            self.assertEqual(payload["pool"], "G")
            self.assertEqual(payload["kind"], "other-market")
            self.assertEqual(payload["end"], "2026-09-30")
            self.assertFalse(payload["china_pnl"])
            self.assertFalse(payload["robustness"])
            self.assertFalse(CHINA_IDS & set(payload["members"]["美国"]))
            other_arms.setdefault(row["arm"], set()).add(payload["pool"])
        self.assertEqual(other_arms, {arm: {"G"} for arm in ("v5.1", "E2式", "A1", "R0")})
        self.assertEqual(set(other_arms), set(expected_other))
