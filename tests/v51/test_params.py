"""冻结参数、大类表和空账本。"""
from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from src.v3.engine.book import DESIGN_END
from src.v3.engine.exit import EXIT_DRAWDOWN
from src.v3.engine.ledger import COLUMNS
from src.v5.engine.classes import load_classes
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

    def test_ledger_is_only_a_header(self):
        text = (ROOT / "results" / "v5.1" / "trial-ledger.csv").read_text(encoding="utf-8")
        self.assertEqual(text.splitlines(), [",".join(COLUMNS)])
