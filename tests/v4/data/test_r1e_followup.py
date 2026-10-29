"""v4-R1e 补数的解析和缺口原因。不出网。"""
from __future__ import annotations

import unittest

from src.v4.data.r1e_followup import failure_reason, parse_sse_dayk


class ParseSse(unittest.TestCase):
    def test_keeps_ohlc_and_drops_days_after_the_cutoff(self):
        payload = {"kline": [
            [20240516, 1.045, 1.06, 1.037, 1.051, 306191500, 320130383],
            [20260930, 1.213, 1.221, 1.204, 1.22, 32122600, 38990573],
            [20261008, 1.3, 1.3, 1.3, 1.3, 100, 100],
        ]}
        rows = parse_sse_dayk(payload, "2026-09-30")
        self.assertEqual([row["date"] for row in rows], ["2024-05-16", "2026-09-30"])
        self.assertEqual(rows[0]["open"], 1.045)
        self.assertEqual(rows[0]["high"], 1.06)
        self.assertEqual(rows[0]["low"], 1.037)
        self.assertEqual(rows[0]["close"], 1.051)
        self.assertEqual(rows[0]["volume"], 306191500)
        self.assertEqual(rows[0]["amount"], 320130383)
        self.assertEqual(rows[1]["close"], 1.22)

    def test_rejects_a_bar_whose_close_is_outside_the_range(self):
        with self.assertRaises(ValueError):
            parse_sse_dayk({"kline": [[20260930, 1.0, 1.2, 1.1, 1.3, 10, 10]]}, "2026-09-30")


class FailureReason(unittest.TestCase):
    def test_names_the_eastmoney_error_and_does_not_claim_a_write(self):
        text = failure_reason({
            "eastmoney_error": "RemoteDisconnected: empty",
            "exchange_note": "上交所 dayk 是不复权 OHLC。",
            "fhsp_note": "天天基金分红送配页没有场内后复权 K 线。",
            "company_note": "基金公司页面已保存，正文没有场内后复权 K 线。",
        })
        self.assertIn("RemoteDisconnected: empty", text)
        self.assertIn("不复权", text)
        self.assertIn("未写入 adj=hfq。", text)

    def test_requires_the_eastmoney_error(self):
        with self.assertRaises(ValueError):
            failure_reason({"exchange_note": "只有不复权"})
