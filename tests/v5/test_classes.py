"""冻结后的大类表是草稿的原样副本。"""
from __future__ import annotations

import unittest
from pathlib import Path

from src.v5.engine.classes import EXPECTED_ROWS, load_classes

ROOT = Path(__file__).resolve().parents[2]


class ClassesTable(unittest.TestCase):
    def test_config_is_the_inventory_draft_byte_for_byte(self):
        draft = (ROOT / "results/v5/inventory/classes-draft.csv").read_bytes()
        config = (ROOT / "config/v5/classes.csv").read_bytes()
        self.assertEqual(config, draft)
        frame = load_classes()
        self.assertEqual(len(frame), EXPECTED_ROWS)
        self.assertEqual(list(frame.columns), ["container_id", "class", "basis", "source_url"])
        filled = {
            "theme-MSCI China Value Weighted Index": "港股",
            "theme-iEdge Emerging Asia Select 50 Index": "其他海外",
            "theme-中信证券印度ETP指数": "其他海外",
            "theme-中证韩交所中韩半导体指数": "其他海外",
            "theme-标普中国新经济行业指数": "港股",
            "theme-标普全球石油指数": "美股",
        }
        indexed = frame.set_index("container_id")
        for name, kind in filled.items():
            self.assertEqual(indexed.loc[name, "class"], kind)
            self.assertIn("manual_rule", indexed.loc[name, "basis"])
        self.assertEqual(int((frame["class"] == "").sum()), 0)
        self.assertEqual(int((frame["class"] == "现金").sum()), 1)


if __name__ == "__main__":
    unittest.main()
