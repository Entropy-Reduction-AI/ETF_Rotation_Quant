"""一次性检验接线。只用构造的判据和合成日收益，不读行情。"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.report.metrics import cagr
from src.v6.guard import IsolationError
from src.v6.health_random import SEED, TRIALS, annualize
from src.v6.oneshot_prep import (
    BLOCKS,
    COST,
    D50_4,
    LEDGERS,
    ROBUSTNESS,
    SCENARIO,
    Criteria,
    SpanBook,
    attribution,
    crosses_cut,
    current_configuration,
    downgrade_for_europe,
    europe_after_conditional,
    evaluate,
    feed_flip,
    full_span,
    item_result,
    join_ledgers,
    largest_contributors,
    eight_line_table,
    line_character,
    main,
    market_query,
    month_regime,
    official_verdict,
    open_ledger,
    overall,
    passes,
    pick_detail,
    premium_pp,
    random_report,
    regime_table,
    run_exam,
    run_random_exam,
    select_judgment,
    sleeve_split,
    source_reading,
    stress_detail,
    any_start,
)


def _ok() -> Criteria:
    return Criteria(-0.20, 1.0, 0.50, 0.40, 1.0)


def _fail_excess() -> Criteria:
    return Criteria(-0.20, 1.0, 0.50, 0.40, -0.1)


def _variants(fill: Criteria | None = None) -> dict[str, Criteria]:
    base = _ok() if fill is None else fill
    return {code: base for code, _text in ROBUSTNESS}


def _flat(index: pd.DatetimeIndex, before: float, after: float) -> pd.Series:
    values = np.where(index < np.datetime64("2016-01-01"), before, after)
    return pd.Series(values, index=index)


def _book(index: pd.DatetimeIndex) -> SpanBook:
    return SpanBook(
        v6=_flat(index, 0.00040, 0.00010),
        gross=_flat(index, 0.00045, 0.00012),
        undefended=_flat(index, 0.00050, 0.00020),
        equal_weight=_flat(index, 0.00030, 0.00015),
        bm_main_total=_flat(index, 0.00035, 0.00030),
        bm_main_price=_flat(index, 0.00020, 0.00018),
        bm_same_total=_flat(index, 0.00025, 0.00008),
        bm_same_price=_flat(index, 0.00022, 0.00016),
        k2a=_flat(index, 0.00015, 0.00005),
    )


class OneshotPrepTests(unittest.TestCase):
    def test_four_criteria_and_eight_items(self):
        flags = passes(_ok())
        self.assertEqual(set(flags), {"最大回撤", "保费", "年化除以回撤", "对同仓位基准"})
        self.assertTrue(all(flags.values()))
        result = overall(_ok(), _variants())
        self.assertEqual(result["主判"], "通过")
        self.assertEqual(result["总结论"], "通过")
        self.assertEqual(len(result["稳健性"]), 8)
        self.assertTrue(all(row["敏感"] == "无变化" for row in result["稳健性"]))
        for row in result["稳健性"]:
            self.assertEqual(set(row["判据"]), set(flags))
            self.assertEqual(row["结论"], "通过")
            self.assertTrue(all(value == 0.0 for value in row["变化"].values()))

    def test_one_flip_is_conditional_and_a_value_change_is_not(self):
        variants = _variants()
        variants["S1"] = _fail_excess()
        variants["S2"] = Criteria(-0.25, 1.0, 0.50, 0.40, 1.0)
        result = overall(_ok(), variants)
        self.assertEqual(result["总结论"], "通过（有条件）")
        by_item = {row["item"]: row for row in result["稳健性"]}
        self.assertEqual(by_item["S1"]["敏感"], "很敏感")
        self.assertEqual(by_item["S1"]["结论"], "不通过")
        self.assertAlmostEqual(by_item["S1"]["变化"]["对同仓位基准"], -1.1)
        self.assertEqual(by_item["S2"]["敏感"], "有影响")
        self.assertEqual(by_item["S2"]["结论"], "通过")

    def test_main_failure_does_not_get_upgraded(self):
        variants = _variants()
        variants["S1"] = _ok()
        result = overall(_fail_excess(), variants)
        self.assertEqual(result["主判"], "不通过")
        self.assertEqual(result["总结论"], "不通过")
        by_item = {row["item"]: row for row in result["稳健性"]}
        self.assertEqual(by_item["S1"]["敏感"], "很敏感")
        self.assertEqual(by_item["S1"]["结论"], "通过")

    def test_boundaries_follow_the_frozen_inequalities(self):
        self.assertTrue(passes(Criteria(-0.40, 4.0, 0.51, 0.50, 0.0))["最大回撤"])
        self.assertTrue(passes(Criteria(-0.40, 4.0, 0.51, 0.50, 0.0))["保费"])
        self.assertTrue(passes(Criteria(-0.40, 4.0, 0.51, 0.50, 0.0))["对同仓位基准"])
        self.assertFalse(passes(Criteria(-0.40, 4.0, 0.50, 0.50, 0.0))["年化除以回撤"])
        self.assertFalse(passes(Criteria(-0.4000001, 4.01, 0.2, 0.5, -0.01))["最大回撤"])

    def test_scenario_knobs_match_the_frozen_list(self):
        self.assertEqual([code for code, _text in ROBUSTNESS], list(SCENARIO))
        self.assertEqual(SCENARIO["S1"]["成本"], COST * 2)
        self.assertEqual(SCENARIO["S1"]["成本"], 0.004)
        self.assertEqual(SCENARIO["S8"]["紧张票数"], 3)
        self.assertEqual(SCENARIO["S6"], {"美股权重": 0.5, "A股权重": 0.5})
        self.assertEqual(D50_4, "B")

    def test_d50_4_b_downgrades_again_and_stops_at_failure(self):
        self.assertEqual(downgrade_for_europe("通过", "不支持"), "通过（有条件）")
        self.assertEqual(downgrade_for_europe("通过（有条件）", "不支持"), "不通过")
        self.assertEqual(downgrade_for_europe("不通过", "不支持"), "不通过")
        self.assertEqual(downgrade_for_europe("通过（有条件）", "支持"), "通过（有条件）")
        self.assertEqual(europe_after_conditional("通过", "不支持"), "通过（有条件）")
        with self.assertRaises(IsolationError):
            europe_after_conditional()

    def test_only_exam_index_pool_enters_the_flip(self):
        variants = _variants()
        flipped = _variants()
        flipped["S1"] = _fail_excess()
        result = official_verdict({
            ("检验段", "指数池"): (_ok(), variants),
            ("全段", "指数池"): (_ok(), flipped),
            ("检验段", "可交易池"): (_fail_excess(), variants),
        })
        self.assertEqual(result["主判"], "通过")
        self.assertEqual(result["总结论"], "通过")
        self.assertEqual(result["进入翻转"], ["检验段、指数池"])
        self.assertEqual(result["只报告"]["全段、指数池"]["总结论"], "通过（有条件）")
        self.assertEqual(result["只报告"]["检验段、可交易池"]["总结论"], "不通过")
        with self.assertRaises(IsolationError):
            feed_flip("全段", "指数池", _ok(), flipped)
        with self.assertRaises(IsolationError):
            feed_flip("检验段", "可交易池", _ok(), variants)

    def test_europe_applies_only_after_the_exam_verdict(self):
        variants = _variants()
        variants["S3"] = _fail_excess()
        calm = _variants()
        result = official_verdict(
            {
                ("检验段", "指数池"): (_ok(), variants),
                ("全段", "指数池"): (_ok(), calm),
            },
            europe="不支持",
        )
        self.assertEqual(result["总结论"], "不通过")
        self.assertEqual(result["只报告"]["全段、指数池"]["总结论"], "通过")
        failed = official_verdict(
            {("检验段", "指数池"): (_fail_excess(), calm)},
            europe="不支持",
        )
        self.assertEqual(failed["总结论"], "不通过")

    def test_restart_is_reported_and_the_cutout_is_the_verdict(self):
        judged = select_judgment(_fail_excess(), _ok())
        self.assertEqual(judged["判定口径"], "连续运行截出")
        self.assertEqual(judged["主判"], "不通过")
        self.assertTrue(all(row["判定用"] == "连续运行截出" for row in judged["差异"]))
        excess = next(row for row in judged["差异"] if row["判据"] == "对同仓位基准")
        self.assertAlmostEqual(excess["差"], 1.1)
        self.assertIn("没有在 2016-01", judged["原因"])

    def test_item_result_and_premium_use_complete_years_only(self):
        index = pd.bdate_range("2014-01-02", "2015-12-31")
        book = _book(index)
        row = item_result(book, "2014-01-01", "2015-12-31")
        self.assertEqual(set(row["判据"]), {"最大回撤", "保费", "年化除以回撤", "对同仓位基准"})
        self.assertEqual(row["结论"], "通过" if all(row["判据"].values()) else "不通过")
        whole = premium_pp(book.v6, book.undefended, book.bm_main_total, "2014-01-01", "2015-12-31")
        only_2014 = premium_pp(book.v6, book.undefended, book.bm_main_total, "2014-01-01", "2014-12-31")
        cut = premium_pp(book.v6, book.undefended, book.bm_main_total, "2014-01-01", "2015-06-30")
        self.assertNotAlmostEqual(whole, only_2014)
        self.assertAlmostEqual(cut, only_2014)

    def test_full_span_reports_blocks_without_a_verdict(self):
        index = pd.bdate_range("2006-01-02", "2026-09-30")
        book = _book(index)
        rmb = _flat(index, 0.00040, 0.00020)
        usd = _flat(index, 0.00030, 0.00010)
        report = full_span(book, rmb, usd)
        self.assertTrue(report["只报告"])
        self.assertNotIn("总结论", report)
        table = report["拆账"]
        self.assertIsNone(table["总结论"])
        self.assertIsNone(table["判据格"])
        self.assertEqual([row["块"] for row in table["六块"]], list(BLOCKS))
        self.assertTrue(all(row["读法"] in ("设计期才有", "稳定", "不稳定") for row in table["六块"]))
        self.assertIn("全段", table["六块"][0])
        years = [row["年"] for row in table["逐年"]]
        self.assertIn("2006", years)
        self.assertIn("2025", years)
        self.assertIn("2026年前9个月", years)
        self.assertNotIn("2027", years)
        self.assertFalse(table["汇率"]["进入六块"])
        design = evaluate(book, "2006-01-01", "2015-12-31")
        exam = evaluate(book, "2016-01-01", "2026-09-30")
        self.assertNotEqual(design.excess_vs_same_pp, exam.excess_vs_same_pp)

    def test_source_reading_follows_the_written_order(self):
        self.assertEqual(source_reading(1.0, -0.2, [1, 1, 1, 1]), "设计期才有")
        self.assertEqual(source_reading(1.0, 0.4, [1, 1, 1, 1]), "设计期才有")
        self.assertEqual(source_reading(1.0, -0.4, [1, 1, -1, -1]), "设计期才有")
        self.assertEqual(source_reading(1.0, 0.5, [1, 1, 1, -1]), "稳定")
        self.assertEqual(source_reading(-1.0, -0.2, [-1, -1, -1, 1]), "稳定")
        self.assertEqual(source_reading(1.0, 0.5, [1, 1, -1, -1]), "不稳定")
        self.assertEqual(source_reading(0.0, 1.0, [1, 1, 1, 1]), "不稳定")
        self.assertEqual(source_reading(-1.0, 1.0, [-1, -1, -1, -1]), "不稳定")

    def test_sleeve_split_weights_and_spx_stay_out_of_the_six(self):
        index = pd.bdate_range("2015-01-05", "2015-12-31")
        series = {
            name: pd.Series(rate, index=index)
            for name, rate in {
                "A股前3": 0.0004, "A股等权": 0.0002, "A股母指数": 0.0001,
                "A股毛": 0.0005, "A股净": 0.00045,
                "美股前3": 0.0006, "美股等权": 0.0003, "美股母指数": 0.0002,
                "美股毛": 0.0007, "美股净": 0.00065, "SPX": 0.00025,
            }.items()
        }
        rows = sleeve_split(series, "2015-01-01", "2015-12-31")
        pick = next(row for row in rows if row["名额"] == "A股" and row["块"] == "挑选")
        self.assertAlmostEqual(pick["组合贡献"], pick["名额内"] * 0.4)
        us = next(row for row in rows if row["名额"] == "美股" and row["块"] == "成本")
        self.assertAlmostEqual(us["组合贡献"], us["名额内"] * 0.6)
        extra = next(row for row in rows if row["块"] == "前3减SPX")
        self.assertFalse(extra["进入六块"])
        self.assertGreater(extra["名额内"], 0.0)

    def test_pick_contribution_and_largest_names(self):
        rows = [
            {"月份": "2015-01", "名额": "A股", "候选": "甲", "下月收益": 0.10, "等权收益": 0.04},
            {"月份": "2015-01", "名额": "A股", "候选": "乙", "下月收益": 0.02, "等权收益": 0.04},
            {"月份": "2015-02", "名额": "A股", "候选": "甲", "下月收益": 0.00, "等权收益": 0.00},
        ]
        table = pick_detail(rows, {"A股": ["甲", "乙", "丙"]}, "2015-01-01", "2015-12-31")
        self.assertEqual(table["A股"]["前10"][0]["候选"], "甲")
        self.assertEqual(table["A股"]["前10"][0]["入选月数"], 2)
        self.assertAlmostEqual(table["A股"]["前10"][0]["对挑选的贡献"], 3.0)
        self.assertEqual(table["A股"]["从未入选"], ["丙"])
        self.assertEqual(largest_contributors(rows, "A股", "2015-01-01", "2015-12-31", 1), ["甲"])

    def test_stress_episodes_and_named_years(self):
        rows = [
            {"月份": "2008-01", "名额": "A股", "紧张": True, "股票仓位": 0.2, "v6": -0.01, "不设防守": -0.03},
            {"月份": "2008-02", "名额": "A股", "紧张": True, "股票仓位": 0.4, "v6": 0.00, "不设防守": -0.02},
            {"月份": "2008-04", "名额": "A股", "紧张": True, "股票仓位": 1.0, "v6": 0.01, "不设防守": 0.01},
            {"月份": "2011-06", "名额": "A股", "紧张": False, "股票仓位": 1.0, "v6": 0.02, "不设防守": 0.03},
            {"月份": "2015-08", "名额": "A股", "紧张": True, "股票仓位": 0.5, "v6": -0.04, "不设防守": -0.08},
        ]
        detail = stress_detail(rows)
        first, second, third = detail["紧张段"]
        self.assertEqual(first["起"], "2008-01")
        self.assertEqual(first["止"], "2008-02")
        self.assertAlmostEqual(first["股票平均仓位"], 0.3)
        self.assertAlmostEqual(first["累计差"], 4.0)
        self.assertEqual(second["起"], "2008-04")
        self.assertEqual(third["起"], "2015-08")
        quiet = next(row for row in detail["不紧张保费"] if row["段"] == "2011–15")
        self.assertAlmostEqual(quiet["累计保费"], 1.0)
        named = {row["时段"]: row["状态"] for row in detail["指名时段"]}
        self.assertEqual(named["2008"], "触发")
        self.assertEqual(named["2011"], "未触发")
        self.assertEqual(named["2015–16"], "触发")
        self.assertEqual(named["2018"], "数据未覆盖")
        self.assertEqual(named["2022"], "数据未覆盖")

    def test_character_regime_and_any_start_stay_inside_2015(self):
        index = pd.bdate_range("2014-01-02", "2015-12-31")
        strategy = pd.Series(0.001, index=index)
        strategy.iloc[20] = -0.08
        bench = pd.Series(0.0, index=index)
        books = {name: strategy for name in (
            "v6", "连续性版", "K2A", "A1", "A2", "现行配置", "BM-主", "BM-同仓位",
        )}
        lines = eight_line_table(books, "2014-01-01", "2015-12-31")
        self.assertEqual([row["线"] for row in lines], list(books))
        self.assertTrue(all("结论" not in row for row in lines))
        stats = line_character(strategy, "2014-01-01", "2015-12-31")
        self.assertLess(stats["最大回撤"], 0.0)
        self.assertFalse(stats["跨2015-12/2016-01"])
        self.assertGreater(stats["净值末"], 1_000_000.0)
        self.assertTrue(crosses_cut(pd.Timestamp("2015-06-12"), pd.Timestamp("2016-02-01")))
        self.assertFalse(crosses_cut(pd.Timestamp("2015-06-12"), pd.Timestamp("2015-08-01")))
        self.assertFalse(crosses_cut(pd.Timestamp("2016-02-01"), pd.Timestamp("2016-03-01")))
        level = (1.0 + bench).cumprod() * 100.0
        level.iloc[-1] = level.iloc[-21] * 1.02
        labels = month_regime(level)
        self.assertIn("牛市", set(labels.dropna()))
        table = regime_table(strategy, {"BM-主": bench}, labels)
        self.assertEqual({row["行情"] for row in table}, {"牛市", "回调", "熊市", "反弹"})
        navs = {"v6": (1.0 + strategy).cumprod(), "BM-主": (1.0 + bench).cumprod()}
        one_year = any_start(navs, "v6", 1)
        self.assertGreater(one_year["起点数"], 0)
        self.assertEqual(one_year["跑赢占比"]["BM-主"], 1.0)
        self.assertEqual(any_start(navs, "v6", 5)["起点数"], 0)

    def test_random_windows_do_not_become_a_live_exam(self):
        early = pd.bdate_range("2015-01-05", "2015-03-31")
        early_rule = pd.Series(0.001, index=early)
        early_paths = np.zeros((4, len(early)))
        early_paths[1] = 0.002
        held = random_report(early_rule, early_paths)
        by_window = {row["窗口"]: row for row in held["窗口"]}
        self.assertEqual(by_window["检验段"]["日数"], 0)
        self.assertIsNone(by_window["检验段"]["百分位"])
        self.assertGreater(by_window["全段"]["日数"], 0)
        self.assertEqual(by_window["全段"]["种子"], SEED)
        self.assertEqual(by_window["全段"]["正式试验次数"], TRIALS)
        self.assertFalse(by_window["全段"]["本次是正式检验"])
        self.assertEqual(held["口径"]["种子"], 20261122)
        self.assertEqual(held["口径"]["试验次数"], 1000)
        crossed = pd.bdate_range("2015-12-01", "2016-01-15")
        rule = pd.Series(0.001, index=crossed)
        paths = np.vstack([
            np.full(len(crossed), 0.0),
            np.full(len(crossed), 0.002),
            np.full(len(crossed), 0.001),
            np.full(len(crossed), -0.001),
        ])
        live = random_report(rule, paths)
        windows = {row["窗口"]: row for row in live["窗口"]}
        self.assertGreater(windows["检验段"]["日数"], 0)
        self.assertGreater(windows["全段"]["日数"], windows["检验段"]["日数"])
        self.assertFalse(windows["检验段"]["本次是正式检验"])
        self.assertAlmostEqual(
            float(annualize(rule.to_numpy())[0]),
            cagr(rule),
        )
        with self.assertRaises(IsolationError):
            run_random_exam()

    def test_ledgers_join_day_by_day_and_files_stay_closed(self):
        design = pd.Series([1.0, 1.01], index=pd.to_datetime(["2015-12-30", "2015-12-31"]))
        exam = pd.Series([1.01, 1.02], index=pd.to_datetime(["2015-12-31", "2016-01-04"]))
        joined = join_ledgers(design, exam, name="A1")
        self.assertEqual(joined["重叠日"], 1)
        self.assertFalse(joined["续跑"])
        self.assertEqual(
            [day.isoformat() for day in joined["序列"].index.date],
            ["2015-12-30", "2015-12-31", "2016-01-04"],
        )
        bad = exam.copy()
        bad.iloc[0] = 1.5
        with self.assertRaises(IsolationError):
            join_ledgers(design, bad, name="A1")
        late = pd.Series([1.0], index=pd.to_datetime(["2016-01-04"]))
        with self.assertRaises(IsolationError):
            join_ledgers(late, exam, name="A2")
        self.assertEqual(LEDGERS["A1"]["设计期sha256"][:8], "3c371162")
        self.assertEqual(LEDGERS["A2"]["检验段sha256前缀"], "713d9816")
        with self.assertRaises(IsolationError):
            open_ledger(LEDGERS["A1"]["检验段"])
        with self.assertRaises(IsolationError):
            open_ledger("data/market.sqlite")

    def test_live_entrypoints_refuse(self):
        with self.assertRaises(IsolationError):
            run_exam()
        with self.assertRaises(IsolationError):
            main()
        with self.assertRaises(IsolationError):
            current_configuration("2026-09-30")
        with self.assertRaises(IsolationError):
            current_configuration("2015-12-31")
        with self.assertRaises(IsolationError):
            market_query("select date, close from bars")
        with self.assertRaises(IsolationError):
            market_query(
                "select date, close from bars where date<=?",
                params=("2026-09-30",),
            )
        with self.assertRaises(IsolationError) as caught:
            market_query(
                "select date, close from bars where date<=?",
                params=("2015-12-31",),
            )
        self.assertIn("不执行行情查询", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
