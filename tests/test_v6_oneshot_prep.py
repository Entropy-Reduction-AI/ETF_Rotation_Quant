"""一次性检验脚手架。只用构造的判据，不读行情。"""

from __future__ import annotations

import unittest

from src.v6.guard import IsolationError
from src.v6.oneshot_prep import Criteria, europe_after_conditional, overall, passes, run_exam


def _ok() -> Criteria:
    return Criteria(-0.20, 1.0, 0.50, 0.40, 1.0)


def _fail_excess() -> Criteria:
    return Criteria(-0.20, 1.0, 0.50, 0.40, -0.1)


class OneshotPrepTests(unittest.TestCase):
    def test_four_criteria_and_eight_items(self):
        flags = passes(_ok())
        self.assertEqual(set(flags), {"最大回撤", "保费", "年化除以回撤", "对同仓位基准"})
        self.assertTrue(all(flags.values()))
        variants = {f"S{i}": _ok() for i in range(1, 9)}
        result = overall(_ok(), variants)
        self.assertEqual(result["主判"], "通过")
        self.assertEqual(result["总结论"], "通过")
        self.assertEqual(len(result["稳健性"]), 8)
        self.assertTrue(all(row["敏感"] == "无变化" for row in result["稳健性"]))

    def test_one_flip_is_conditional_and_a_value_change_is_not(self):
        variants = {f"S{i}": _ok() for i in range(1, 9)}
        variants["S1"] = _fail_excess()
        variants["S2"] = Criteria(-0.25, 1.0, 0.50, 0.40, 1.0)
        result = overall(_ok(), variants)
        self.assertEqual(result["总结论"], "通过（有条件）")
        by_item = {row["item"]: row for row in result["稳健性"]}
        self.assertEqual(by_item["S1"]["敏感"], "很敏感")
        self.assertEqual(by_item["S1"]["结论"], "不通过")
        self.assertEqual(by_item["S2"]["敏感"], "有影响")
        self.assertEqual(by_item["S2"]["结论"], "通过")

    def test_main_failure_does_not_get_upgraded(self):
        variants = {f"S{i}": _ok() for i in range(1, 9)}
        result = overall(_fail_excess(), variants)
        self.assertEqual(result["主判"], "不通过")
        self.assertEqual(result["总结论"], "不通过")

    def test_exam_and_europe_followup_stay_closed(self):
        with self.assertRaises(IsolationError):
            run_exam()
        with self.assertRaises(IsolationError):
            europe_after_conditional()
