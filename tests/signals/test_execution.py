"""D5 执行规则。净值是合成的 fund_nav 行，不读真实库。"""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import tests  # noqa: F401
from dataclasses import replace

from src.signals.fallback import (
    Alternate,
    AShareBook,
    FallbackConfig,
    FallbackError,
    NavRow,
    OverseasPool,
    a_share_session,
    decision_state,
    load_calendar,
    load_config,
    load_fund_nav,
    plan_targets,
    replicate,
    resolve_execution_fund,
    schedule_execution,
    select_nav,
)
from tests.signals.test_fallback import _flat_rows, _one_name_config, _write_panel


ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "outputs" / "panel-2026-09-30.sqlite"
DAYS = ["2024-03-11", "2024-03-12", "2024-03-13", "2024-03-14", "2024-03-15"]
AS_OF = "2024-03-15"
PRIMARY = (
    "510300", "510500", "512100", "159915", "159819", "512400", "515220", "512660",
    "512010", "159928", "512690", "159825", "512800", "512880", "512200", "510880",
)


def _nav(code, day, unit):
    return NavRow(code, pd.Timestamp(day), unit, "2024-03-15T16:00:00+08:00")


def _rows_for(premiums, close=1.0, day="2024-03-13"):
    rows = []
    for code, premium in premiums.items():
        rows.append(_nav(code, day, close / (1 + premium)))
        # 决策日和前一交易日的净值故意改成另一套溢价，滞后规则必须丢掉。
        rows.append(_nav(code, "2024-03-14", close / 1.5))
        rows.append(_nav(code, "2024-03-15", close / 2))
    return rows


def _prices(codes, price=1.0):
    return {code: price for code in codes}


def _cfg(**kwargs):
    books = kwargs.pop("funds", (AShareBook("医药", "512010", (
        Alternate("159938", pd.Timestamp("2015-01-08")),
        Alternate("512170", pd.Timestamp("2019-06-17")),
    )),))
    pools = kwargs.pop("pools", (
        OverseasPool("纳指100", ("513100", "159941", "513300")),
        OverseasPool("标普500", ("513500", "159612", "513650")),
    ))
    base = dict(
        design_end=pd.Timestamp("2015-12-31"),
        a_share=tuple(book.container for book in books),
        a_weight=0.70,
        overseas=tuple(pool.container for pool in pools),
        o_weight=0.30,
        out=0.25, back=0.10, judge="month_end", haven_code="511880",
        cash_annual=0.02, rebalance="monthly", cost_one_way=0.0005,
        universe=Path("/tmp/unused-universe.csv"), path=Path("/tmp/unused.toml"),
        band=0.075, premium_cap=0.10, nav_lag=2, lot_size=1,
        funds=books, pools=pools, excluded=("159509",),
    )
    base.update(kwargs)
    return FallbackConfig(**base)


def _held(result):
    return {row["code"]: row["shares"] for row in result["targets"]}


def _plan(cfg, holdings, premiums, prices=None, **kwargs):
    codes = set(premiums) | set(holdings) | {"511880", "512010", "159938", "512170"}
    if prices is None:
        prices = _prices(codes)
    else:
        prices = {**_prices(codes), **prices}
    kwargs.setdefault("a_share_due", False)
    kwargs.setdefault("in_market", True)
    return plan_targets(
        cfg, as_of=AS_OF, equity=kwargs.pop("equity", 100_000), holdings=holdings,
        prices=prices, nav_rows=_rows_for(premiums), trading_days=DAYS, **kwargs)


class ProductionConfig(unittest.TestCase):
    def test_sixteen_funds_pools_and_no_excluded_code(self):
        cfg = load_config()
        self.assertEqual(tuple(book.primary for book in cfg.funds), PRIMARY)
        self.assertEqual(cfg.pools[0].codes, ("513100", "159941", "513300"))
        self.assertEqual(cfg.pools[1].codes, ("513500", "159612", "513650"))
        self.assertEqual(cfg.excluded, ("159509",))
        self.assertNotIn("159509", [code for pool in cfg.pools for code in pool.codes])
        coal = next(book for book in cfg.funds if book.container == "煤炭")
        self.assertEqual(coal.alternates, ())
        hs300 = next(book for book in cfg.funds if book.container == "沪深300")
        self.assertEqual(resolve_execution_fund(hs300, {"510300": "suspended"})[0], "159919")
        consume = next(book for book in cfg.funds if book.container == "消费")
        self.assertLess(consume.alternates[0].list_date, pd.Timestamp("2013-09-16"))
        self.assertEqual(resolve_execution_fund(consume, {})[0], "159928")
        self.assertEqual(resolve_execution_fund(consume, {"159928": "halted"})[0], "510630")


class AlternateRule(unittest.TestCase):
    def test_suspended_primary_switches_to_earliest_live_alternate(self):
        cfg = _cfg()
        code, state = resolve_execution_fund(cfg.funds[0], {"512010": "suspended"})
        self.assertEqual((code, state), ("159938", "suspended"))
        code, _state = resolve_execution_fund(
            cfg.funds[0], {"512010": "liquidated", "159938": "halted"})
        self.assertEqual(code, "512170")
        premiums = _flat_premiums(0.02)
        holdings = {"513100": 15_000, "513500": 15_000}
        result = _plan(cfg, holdings, premiums, statuses={"512010": "suspended"}, a_share_due=True)
        held = _held(result)
        self.assertEqual(held["159938"], 70_000)
        self.assertNotIn("512010", held)
        self.assertNotIn("512170", held)
        self.assertTrue(any(rule.startswith("primary_suspended:512010->159938") for rule in result["rules"]))

    def test_normal_primary_stays_even_if_an_alternate_listed_earlier(self):
        book = AShareBook("AI/算力", "159819", (
            Alternate("515070", pd.Timestamp("2019-12-24")),
            Alternate("159381", pd.Timestamp("2025-03-24")),
        ))
        self.assertEqual(resolve_execution_fund(book, {})[0], "159819")
        with self.assertRaises(FallbackError):
            resolve_execution_fund(book, {"159819": "halted", "515070": "suspended", "159381": "liquidated"})


class PremiumRules(unittest.TestCase):
    def test_buy_the_lowest_premium_and_ignore_excluded(self):
        premiums = {
            "513100": 0.08, "159941": 0.02, "513300": 0.05,
            "513500": 0.07, "159612": 0.09, "513650": 0.03,
            "159509": -0.20,
        }
        result = _plan(_cfg(), {}, premiums)
        held = _held(result)
        self.assertEqual(held["159941"], 15_000)
        self.assertEqual(held["513650"], 15_000)
        self.assertNotIn("513100", held)
        self.assertNotIn("159509", held)
        self.assertNotIn("159509", {row["code"] for row in result["premiums"]})
        self.assertIn("buy_lowest_premium:纳指100:159941", result["rules"])
        self.assertIn("buy_lowest_premium:标普500:513650", result["rules"])
        self.assertIn("overseas_rebalance", result["rules"])

    def test_over_cap_parks_the_buy_in_haven(self):
        premiums = _flat_premiums(0.12)
        premiums["513500"] = 0.04
        result = _plan(_cfg(), {"513100": 1_000}, premiums)
        held = _held(result)
        self.assertEqual(held["513100"], 1_000)
        self.assertEqual(held["513500"], 15_000)
        self.assertEqual(held["511880"], 14_000)
        self.assertIn("premium_cap:纳指100", result["rules"])
        self.assertIn("park_511880", result["rules"])
        self.assertNotIn("buy_lowest_premium:纳指100:513100", result["rules"])

    def test_over_cap_does_not_sell_existing_shares(self):
        premiums = _flat_premiums(0.15)
        result = _plan(_cfg(), {"513100": 20_000, "513500": 20_000}, premiums)
        held = _held(result)
        self.assertEqual(held["513100"], 20_000)
        self.assertEqual(held["513500"], 20_000)
        self.assertNotIn("511880", held)

    def test_no_trade_inside_the_band_even_if_halves_drift(self):
        premiums = _flat_premiums(0.01)
        premiums["513100"] = 0.09
        premiums["159941"] = 0.00
        holdings = {"513100": 20_000, "513500": 10_000}
        result = _plan(_cfg(), holdings, premiums)
        self.assertEqual(_held(result), holdings)
        self.assertIn("overseas_inside_band", result["rules"])
        self.assertNotIn("overseas_rebalance", result["rules"])
        edge = _plan(_cfg(), {"513100": 22_500, "513500": 15_000}, premiums)
        self.assertIn("overseas_inside_band", edge["rules"])
        outside = _plan(_cfg(), {"513100": 22_501, "513500": 15_000}, premiums)
        self.assertIn("overseas_rebalance", outside["rules"])

    def test_rebalance_outside_the_band_buys_only_the_cheap_fund(self):
        premiums = _flat_premiums(0.06)
        premiums["159941"] = 0.01
        premiums["513500"] = 0.01
        holdings = {"513100": 5_000, "159941": 5_000, "513500": 5_000}
        result = _plan(_cfg(), holdings, premiums)
        held = _held(result)
        self.assertEqual(held["513100"], 5_000)
        self.assertEqual(held["159941"], 10_000)
        self.assertEqual(held["513500"], 15_000)
        self.assertIn("overseas_rebalance", result["rules"])

    def test_sell_highest_premium_first(self):
        premiums = _flat_premiums(0.04)
        premiums["513100"] = 0.08
        premiums["159941"] = 0.01
        holdings = {"513100": 12_000, "159941": 12_000, "513500": 15_000}
        result = _plan(_cfg(), holdings, premiums)
        held = _held(result)
        self.assertEqual(held["513100"], 3_000)
        self.assertEqual(held["159941"], 12_000)
        self.assertEqual(held["513500"], 15_000)
        self.assertIn("sell_highest_premium:纳指100", result["rules"])
        self.assertFalse(any(rule.startswith("sell_highest_premium:标普500") for rule in result["rules"]))

    def test_nav_lag_drops_t_and_t_minus_one(self):
        # T−2 溢价 11% 超过上限。T−1 溢价 1%，T 溢价 0，误用都会变成买入。
        codes = list(_flat_premiums(0))
        rows = []
        for code in codes:
            rows.append(_nav(code, "2024-03-13", 1 / 1.11))
            rows.append(_nav(code, "2024-03-14", 1 / 1.01))
            rows.append(_nav(code, "2024-03-15", 1.0))
        cutoff = pd.Timestamp("2024-03-13")
        picked = select_nav(rows, "513100", cutoff)
        self.assertEqual(picked.date, cutoff)
        self.assertAlmostEqual(1.0 / picked.unit_nav - 1, 0.11)
        result = plan_targets(
            _cfg(), as_of=AS_OF, equity=100_000, holdings={}, prices=_prices(set(codes) | {"511880"}),
            nav_rows=rows, trading_days=DAYS, a_share_due=False, in_market=True)
        self.assertTrue(all(row["nav_date"] == "2024-03-13" for row in result["premiums"]))
        self.assertAlmostEqual(result["premiums"][0]["premium"], 0.11)
        self.assertEqual(_held(result).get("511880"), 30_000)
        self.assertFalse(any(rule.startswith("buy_lowest_premium") for rule in result["rules"]))
        late = [row for row in rows if row.code == "513100" and row.date > cutoff]
        with self.assertRaises(FallbackError):
            select_nav(late, "513100", cutoff)

    def test_exact_cap_still_buys(self):
        premiums = _flat_premiums(0.10)
        result = _plan(_cfg(), {}, premiums)
        self.assertIn("buy_lowest_premium:纳指100:159941", result["rules"])
        self.assertNotIn("511880", _held(result))

    def test_a_share_lots_round_down_to_100(self):
        premiums = _flat_premiums(0.02)
        prices = _prices(set(premiums) | {"512010", "511880"}, price=1.0)
        prices["512010"] = 3.0
        result = _plan(
            _cfg(lot_size=100), {"513100": 15_000, "513500": 15_000}, premiums,
            prices=prices, equity=100_000, a_share_due=True, statuses={})
        self.assertEqual(_held(result)["512010"], 23_300)
        self.assertEqual(_held(result)["512010"] % 100, 0)


class DesignPeriod(unittest.TestCase):
    def test_premium_rules_do_not_change_design_period_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "panel.sqlite"
            _write_panel(path, _flat_rows())
            base = _one_name_config(tmp)
            other = replace(base, band=0.01, premium_cap=0.01, nav_lag=9)
            with patch("src.signals.fallback.plan_targets", side_effect=AssertionError("溢价规则不应进入复现")):
                left = replicate(path, "2015-12-31", base, haven_db=None)
                right = replicate(path, "2015-12-31", other, haven_db=None)
            self.assertEqual(left["monthly"], right["monthly"])
            self.assertEqual(left["daily"], right["daily"])
            self.assertLessEqual(pd.Timestamp(left["daily"]["last"]), pd.Timestamp("2015-12-31"))
            self.assertNotIn("premium", left)

    @unittest.skipUnless(PANEL.exists(), "设计期面板不在这台机器上")
    def test_real_design_period_stays_within_0_04pp(self):
        result = replicate(PANEL, "2015-12-31", load_config(), haven_db=ROOT / "data" / "market.sqlite")
        self.assertTrue(result["matches_d2"])
        self.assertEqual(result["monthly"]["a_valve"]["switches"], 6)
        for key in ("a_cagr_pp", "a_drawdown_pp", "blend_cagr_pp", "blend_drawdown_pp"):
            self.assertLessEqual(abs(result["d2_delta_pp"][key]), 0.04)


class MonthSession(unittest.TestCase):
    def test_aligns_only_on_the_first_session(self):
        days = ["2024-02-01", "2024-02-15", "2024-02-29", "2024-03-01", "2024-03-15", "2024-03-29"]
        flags = [(day, a_share_session(day, days)) for day in days]
        self.assertEqual(flags, [
            ("2024-02-01", True),
            ("2024-02-15", False),
            ("2024-02-29", False),
            ("2024-03-01", True),
            ("2024-03-15", False),
            ("2024-03-29", False),
        ])
        for month in ("2024-02", "2024-03"):
            aligned = [day for day, flag in flags if day.startswith(month) and flag]
            self.assertEqual(len(aligned), 1)
            self.assertTrue(aligned[0].endswith("-01"))

    def test_post_holiday_execution_date(self):
        days = load_calendar(ROOT / "data" / "market.sqlite")
        order = schedule_execution("2026-09-30", days)
        self.assertEqual(str(order["decision_date"].date()), "2026-09-30")
        self.assertEqual(str(order["execution_date"].date()), "2026-10-08")
        self.assertTrue(order["a_share_due"])
        self.assertFalse(a_share_session("2026-09-29", days))
        self.assertFalse(a_share_session("2026-09-30", days))
        self.assertTrue(a_share_session("2026-10-08", days))
        october = [day for day in days if day.strftime("%Y-%m") == "2026-10" and a_share_session(day, days)]
        self.assertEqual(october, [pd.Timestamp("2026-10-08")])

    def test_execution_day_uses_the_previous_month_end_valve(self):
        with tempfile.TemporaryDirectory() as tmp:
            panel = Path(tmp) / "panel.sqlite"
            rows = []
            for day, price in (
                ("2023-12-29", 100.0),
                ("2024-01-31", 100.0),
                ("2024-02-29", 70.0),
                ("2024-03-01", 70.0),
                ("2024-03-29", 100.0),
            ):
                rows.append((day, "甲", price, 0))
                rows.append((day, "乙", 100.0, 0))
            _write_panel(panel, rows)
            cfg = _one_name_config(tmp)
            order = schedule_execution("2024-02-29", ["2024-02-01", "2024-02-29", "2024-03-01", "2024-03-29"])
            state = decision_state(panel, order["decision_date"], cfg)
            later = decision_state(panel, "2024-03-29", cfg)
            self.assertEqual(str(order["execution_date"].date()), "2024-03-01")
            self.assertTrue(order["a_share_due"])
            self.assertEqual(str(state["signal_date"].date()), "2024-02-29")
            self.assertFalse(state["in_market"])
            self.assertTrue(later["in_market"])
            result = plan_targets(
                cfg, as_of=order["decision_date"], equity=100_000, holdings={},
                prices={"510300": 1.0, "511880": 1.0, "513100": 1.0},
                nav_rows=_rows_for({"513100": 0.02}),
                trading_days=["2024-02-27", "2024-02-28", "2024-02-29"],
                in_market=state["in_market"], a_share_due=order["a_share_due"],
                decision_date=order["decision_date"], execution_date=order["execution_date"])
            held = _held(result)
            self.assertEqual(held.get("511880"), 70_000)
            self.assertNotIn("510300", held)
            self.assertEqual(result["decision_date"], "2024-02-29")
            self.assertEqual(result["execution_date"], "2024-03-01")
            self.assertEqual(result["valve"], "出场")


class FundNavTable(unittest.TestCase):
    def test_snapshot_fixture_has_a_later_decoy_nav(self):
        import csv
        path = ROOT / "tests" / "signals" / "fixtures" / "fund_nav_2026-09-30.csv"
        with path.open(encoding="utf-8") as fh:
            raw = list(csv.DictReader(fh))
        rows = [NavRow(row["code"], pd.Timestamp(row["date"]), float(row["unit_nav"]), row["fetched_at"]) for row in raw]
        picked = select_nav(rows, "159941", pd.Timestamp("2026-09-28"))
        self.assertEqual(str(picked.date.date()), "2026-09-28")
        later = [row for row in rows if row.code == "159941" and row.date > picked.date]
        self.assertEqual([str(row.date.date()) for row in later], ["2026-09-29", "2026-09-30"])
        self.assertNotAlmostEqual(later[-1].unit_nav, picked.unit_nav)
        codes = {row["code"] for row in raw}
        self.assertIn("159509", codes)

    def test_loader_reads_the_task_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "nav.sqlite"
            con = sqlite3.connect(db)
            con.execute(
                """CREATE TABLE fund_nav (
                    code TEXT, date TEXT, unit_nav REAL, accum_nav REAL,
                    subscribe_status TEXT, redeem_status TEXT,
                    source TEXT, run_id TEXT, fetched_at TEXT)""")
            con.execute(
                "INSERT INTO fund_nav VALUES (?,?,?,?,?,?,?,?,?)",
                ("513100", "2024-03-13", 1.0, 1.2, "开放", "开放", "synthetic_fixture", "0", "2024-03-15T16:00:00+08:00"))
            con.commit()
            con.close()
            rows = load_fund_nav(db)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].code, "513100")
            self.assertAlmostEqual(rows[0].unit_nav, 1.0)


def _flat_premiums(value):
    return {
        "513100": value, "159941": value, "513300": value,
        "513500": value, "159612": value, "513650": value,
    }


if __name__ == "__main__":
    unittest.main()
