"""§7.5 结论报告模板。只核对章节，不填收益。"""
from __future__ import annotations

import unittest

from src.v4.report.conclusion import SECTIONS, template_text


class ConclusionTemplate(unittest.TestCase):
    def test_template_lists_the_six_sections_and_both_peers(self):
        text = template_text()
        self.assertEqual(len(SECTIONS), 6)
        for _key, heading in SECTIONS:
            self.assertIn(heading, text)
        for label in ("性格", "四种行情", "任意起点", "优劣对照", "市场和时代的变化", "适应性"):
            self.assertIn(label, text)
        for regime in ("牛市", "回调", "熊市", "反弹"):
            self.assertIn(regime, text)
        for decade in ("2006–10", "2011–15", "2016–20", "2021–26"):
            self.assertIn(decade, text)
        self.assertIn("仅一次性检验", text)
        self.assertIn("A1", text)
        self.assertIn("A2", text)
        self.assertIn("index", text)
        self.assertIn("tradable", text)
        self.assertIn("不适用", text)
        self.assertIn("BM-主", text)
        self.assertIn("纳指100", text)
        self.assertNotIn("market.sqlite", text)
        self.assertNotIn("年化 2", text)
        self.assertGreater(text.count("待填"), 20)
