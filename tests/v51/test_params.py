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
from src.v51.design import design_params
from src.v51.gpool import CHINA_IDS
from src.v51.params import RULERS, load_params, long_rulers
from src.v51.universe import universe_from_names


ROOT = Path(__file__).resolve().parents[2]


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

    def test_ledger_holds_the_wrapup_rows(self):
        """设计期 2 行、R5 对照、R1、S1–S17，加 G 池 4 行。多一行或少一行都失败。"""
        path = ROOT / "results" / "v5.1" / "trial-ledger.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(list(rows[0]), COLUMNS)
        self.assertEqual(len(rows), 30)
        spec = load_spec()
        design_pools = set()
        control_pools: dict[str, set[str]] = {}
        robust_pools: dict[str, set[str]] = {}
        other = []
        seen = set()
        for row in rows:
            self.assertEqual(row["runner"], "dev")
            self.assertEqual(len(row["git_sha"]), 40)
            payload = json.loads(row["params"])
            self.assertEqual(payload["rules"], "v5.1")
            self.assertEqual(payload["case"], row["arm"])
            key = (row["segment"], row["arm"], payload["pool"])
            self.assertNotIn(key, seen)
            seen.add(key)
            if row["segment"] == "design":
                self.assertEqual(payload["end"], "2015-12-31")
                if row["arm"] == "v5.1":
                    self.assertEqual(payload["kind"], "design")
                    self.assertEqual(payload, design_params(payload["pool"], spec))
                    design_pools.add(payload["pool"])
                elif payload["kind"] == "control":
                    control_pools.setdefault(row["arm"], set()).add(payload["pool"])
                elif payload["kind"] == "robustness":
                    self.assertEqual(payload["pass_fail"], "只报告")
                    robust_pools.setdefault(row["arm"], set()).add(payload["pool"])
                else:
                    self.fail(f"设计期出现了未登记的种类：{payload['kind']}")
            elif row["segment"] == "other-market":
                other.append(row)
            else:
                self.fail(f"未登记的段：{row['segment']}")
        self.assertEqual(design_pools, {"index", "tradable"})
        self.assertEqual(control_pools, {
            "R0": {"index", "tradable"},
            "R1": {"index", "tradable"},
            "C-等权": {"index", "tradable"},
            "C-波动比": {"index"},
        })
        self.assertEqual(robust_pools, {
            **{f"S{i}": {"index"} for i in range(1, 17)},
            "S17": {"tradable"},
        })
        for arm in ("R0", "R1"):
            matched = [
                json.loads(row["params"]) for row in rows
                if row["arm"] == arm and row["segment"] == "design"
            ]
            self.assertEqual(len(matched), 2)
            for payload in matched:
                self.assertEqual(payload["n"], 2000)
                self.assertEqual(payload["seed"], 20261101)
                self.assertEqual(payload["kind"], "control")
        s17 = next(json.loads(row["params"]) for row in rows if row["arm"] == "S17")
        self.assertEqual(s17["pool"], "tradable")
        self.assertFalse(s17["allow_substitute"])
        self.assertEqual(len(other), 4)
        self.assertEqual({row["arm"] for row in other}, {"v5.1", "E2式", "A1", "R0"})
        for row in other:
            payload = json.loads(row["params"])
            self.assertEqual(payload["pool"], "G")
            self.assertEqual(payload["kind"], "other-market")
            self.assertEqual(payload["end"], "2026-09-30")
            self.assertFalse(payload["china_pnl"])
            self.assertFalse(payload["robustness"])
            self.assertFalse(CHINA_IDS & set(payload["members"]["美国"]))
        self.assertEqual(len(seen), 30)
